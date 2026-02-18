"""[DEPRECATED] Composio LangChain integration for the AIO LiveKit Voice Agent.

DEPRECATION NOTICE (2026-02-17)
--------------------------------
This module has been superseded by LiveKit's native MCP support (livekit-agents[mcp]).

The Composio toolkits (SUPABASE, EXCEL, APIFY, FIRECRAWL, MICROSOFT_TEAMS, ONE_DRIVE,
GOOGLEDRIVE, CANVA, COMPOSIO_SEARCH) are now loaded automatically via MCPServerHTTP in
src/agent.py using the MCP_SERVER_URL environment variable. This eliminates the heavy
composio-langchain + langchain dependency chain.

DO NOT import this module in agent.py or __init__.py - it is no longer in the active
tool stack. It is retained here for reference and as a fallback if MCP connectivity is
unavailable.

Migration path:
    Old: ASYNC_TOOLS + COMPOSIO_TOOLS (LangChain wrappers loaded at startup)
    New: ASYNC_TOOLS + mcp_servers=[mcp.MCPServerHTTP(MCP_SERVER_URL)] (auto-discovery)

To re-enable this module:
    1. Restore composio-langchain dependencies in requirements.txt
    2. Re-add `from .composio_tools import COMPOSIO_TOOLS` to agent.py
    3. Add COMPOSIO_TOOLS back to the tools= list in Agent()

Original docstring
------------------
Composio supplements existing n8n webhook tools with unified multi-service auth.
This module is config-driven and fully optional - if COMPOSIO_API_KEY is not set,
COMPOSIO_TOOLS will be an empty list and nothing changes for the existing tool stack.

Configuration (environment variables):
    COMPOSIO_API_KEY     - Composio API key (required to enable this module)
    COMPOSIO_TOOLKITS    - Comma-separated toolkit names, e.g. "GMAIL,GOOGLEDRIVE"
    COMPOSIO_USER_ID     - Entity/user ID for Composio (default: "default")

Design:
    - Each Composio LangChain tool is wrapped as a LiveKit @llm.function_tool
    - Wrappers accept a single `query: str` param (natural language instruction)
    - All results are converted to voice-friendly strings (no raw JSON)
    - Sync Composio calls are run via asyncio.to_thread (agent is fully async)
    - Errors are caught and returned as strings (never raised to the LLM)
"""
import asyncio
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attempt imports - graceful degradation if Composio is not installed
# ---------------------------------------------------------------------------
try:
    from composio_langchain import Action, ComposioToolSet
    _COMPOSIO_AVAILABLE = True
except ImportError:
    _COMPOSIO_AVAILABLE = False
    logger.debug("Composio packages not installed - Composio tools disabled")


def _result_to_voice_string(result) -> str:
    """Convert any Composio/LangChain tool result to a voice-friendly string.

    LangChain tool results can be:
      - str                -> use directly (truncated)
      - dict with "output" -> extract that field
      - dict with "result" -> extract that field
      - any other dict     -> str() it
      - anything else      -> str() it

    Always truncate to 1000 chars so TTS doesn't get a novel.
    """
    if isinstance(result, str):
        return result[:1000]

    if isinstance(result, dict):
        # Prefer structured output/result keys
        for key in ("output", "result", "message", "text", "content"):
            if key in result and result[key]:
                value = result[key]
                if isinstance(value, str):
                    return value[:1000]
                return str(value)[:1000]
        # Fallback: stringify the whole dict but keep it short
        return str(result)[:1000]

    return str(result)[:1000]


def _create_composio_wrapper(composio_tool):
    """Factory: create a LiveKit function_tool wrapper around a Composio LangChain tool.

    The wrapper:
      - Has a stable name: composio_{tool_name_lower}
      - Exposes a single `query: str` parameter for natural-language instructions
      - Runs the (potentially sync) LangChain tool in a thread pool
      - Returns a voice-friendly string

    We use a factory to avoid the classic closure-in-loop variable capture bug.
    Each call to this function produces a new, independent async function bound
    to its own `composio_tool` reference.
    """
    from livekit.agents import llm  # local import so module loads even if livekit absent

    tool_name = f"composio_{composio_tool.name.lower().replace(' ', '_').replace('-', '_')}"
    # Truncate description for LLM context window; LangChain tools can have long descriptions
    tool_description = (composio_tool.description or "Composio tool")[:500]

    @llm.function_tool(
        name=tool_name,
        description=tool_description,
    )
    async def wrapper(query: str) -> str:
        """Dynamic Composio tool wrapper - executes in thread pool."""
        try:
            # LangChain tools may be synchronous; run in thread to avoid blocking event loop
            result = await asyncio.to_thread(composio_tool.invoke, query)
            return _result_to_voice_string(result)
        except Exception as e:
            logger.warning(f"Composio tool '{tool_name}' error: {e}")
            return f"Composio tool error: {str(e)}"

    return wrapper


def _load_composio_tools() -> List:
    """Load and wrap Composio tools based on environment configuration.

    Returns:
        List of LiveKit function_tool callables, or [] if Composio is disabled.
    """
    # ------------------------------------------------------------------
    # Guard 1: Package availability
    # ------------------------------------------------------------------
    if not _COMPOSIO_AVAILABLE:
        logger.info("Composio: Disabled (packages not installed)")
        return []

    # ------------------------------------------------------------------
    # Guard 2: API key presence
    # ------------------------------------------------------------------
    api_key = os.environ.get("COMPOSIO_API_KEY", "").strip()
    if not api_key:
        logger.info("Composio: Disabled (no COMPOSIO_API_KEY set)")
        return []

    # ------------------------------------------------------------------
    # Guard 3: Toolkits configured
    # ------------------------------------------------------------------
    toolkits_raw = os.environ.get("COMPOSIO_TOOLKITS", "").strip()
    if not toolkits_raw:
        logger.info("Composio: Disabled (COMPOSIO_TOOLKITS is empty)")
        return []

    toolkit_names = [t.strip().upper() for t in toolkits_raw.split(",") if t.strip()]
    if not toolkit_names:
        logger.info("Composio: Disabled (no valid toolkit names parsed)")
        return []

    # ------------------------------------------------------------------
    # Initialize Composio toolset
    # ------------------------------------------------------------------
    entity_id = os.environ.get("COMPOSIO_USER_ID", "default").strip() or "default"

    try:
        toolset = ComposioToolSet(api_key=api_key, entity_id=entity_id)
    except Exception as e:
        logger.error(f"Composio: Failed to initialize ComposioToolSet: {e}")
        return []

    # ------------------------------------------------------------------
    # Fetch tools for each configured toolkit
    # ------------------------------------------------------------------
    wrapped_tools: List = []
    loaded_toolkits: List[str] = []
    failed_toolkits: List[str] = []

    for toolkit_name in toolkit_names:
        try:
            # get_tools returns a list of LangChain BaseTool instances
            lc_tools = toolset.get_tools(apps=[toolkit_name])

            if not lc_tools:
                logger.warning(f"Composio: Toolkit '{toolkit_name}' returned 0 tools")
                continue

            for lc_tool in lc_tools:
                try:
                    wrapper = _create_composio_wrapper(lc_tool)
                    wrapped_tools.append(wrapper)
                except Exception as wrap_err:
                    logger.warning(
                        f"Composio: Could not wrap tool '{getattr(lc_tool, 'name', '?')}' "
                        f"from {toolkit_name}: {wrap_err}"
                    )

            loaded_toolkits.append(toolkit_name)

        except Exception as e:
            logger.error(f"Composio: Failed to load toolkit '{toolkit_name}': {e}")
            failed_toolkits.append(toolkit_name)

    # ------------------------------------------------------------------
    # Startup summary
    # ------------------------------------------------------------------
    if wrapped_tools:
        logger.info(
            f"Composio: Loaded {len(wrapped_tools)} tools from "
            f"{len(loaded_toolkits)} toolkit(s): {', '.join(loaded_toolkits)}"
        )
    else:
        logger.warning(
            f"Composio: Initialized but 0 tools loaded. "
            f"Attempted: {toolkit_names}. Failed: {failed_toolkits}"
        )

    if failed_toolkits:
        logger.warning(f"Composio: Failed toolkits (skipped): {', '.join(failed_toolkits)}")

    return wrapped_tools


# ---------------------------------------------------------------------------
# Public export - populated at module load time
# ---------------------------------------------------------------------------
# This is [] when Composio is not configured, so callers can always do:
#   all_tools = ASYNC_TOOLS + COMPOSIO_TOOLS
COMPOSIO_TOOLS: List = _load_composio_tools()
