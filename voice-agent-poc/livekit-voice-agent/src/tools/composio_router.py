"""Composio Tool Router — MCP discovery + SDK execution.

Architecture (hybrid MCP + Python SDK):
  MCP (5 meta-tools in LLM context):
    - COMPOSIO_SEARCH_TOOLS        — discover tools by use case
    - COMPOSIO_MANAGE_CONNECTIONS  — handle OAuth/auth flows
    - COMPOSIO_GET_TOOL_SCHEMAS    — load full schema when search returns schemaRef
    - COMPOSIO_WAIT_FOR_CONNECTION — wait for user to complete auth
    - COMPOSIO_CREATE_PLAN         — build execution plan for complex workflows

  Python SDK (execution via AsyncToolWorker):
    - composioBatchExecute  — DEFAULT: parallel execution, always background
    - composioExecute       — FALLBACK: single sync reads when LLM needs results

See docs/COMPOSIO-TOOL-ROUTER-APPROACH.md for full architecture.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Composio meta-toolkits — these load the Tool Router meta-tools,
# NOT individual service schemas. External services (gmail, drive, etc.)
# are controlled by connected accounts on the Composio dashboard.
#   "composio"        → execute + manage_connections meta-tools
#   "composio_search" → search meta-tool (discovers tools across all connected apps)
COMPOSIO_TOOLKITS = ["composio", "composio_search"]

# MCP tools loaded into LLM context — discovery, auth, schema loading.
# Execution is handled by the Python composioExecute wrapper, not MCP.
COMPOSIO_ALLOWED_TOOLS = [
    "COMPOSIO_SEARCH_TOOLS",         # Discover the right tool by query
    "COMPOSIO_MANAGE_CONNECTIONS",   # Handle OAuth/auth when connection is missing
    "COMPOSIO_GET_TOOL_SCHEMAS",     # Load full schema when search returns schemaRef
    "COMPOSIO_WAIT_FOR_CONNECTION",  # Wait for user to complete OAuth flow
    "COMPOSIO_CREATE_PLAN",          # Build execution plan for complex workflows
]

# Cached Composio client (initialized on first use)
_composio_client = None


def _get_client(settings):
    """Get or create a cached Composio SDK client."""
    global _composio_client
    if _composio_client is None:
        from composio import Composio  # type: ignore[import]
        _composio_client = Composio(api_key=settings.composio_api_key)
        logger.info("Composio: SDK client initialized")
    return _composio_client


async def execute_composio_tool(tool_slug: str, arguments: dict, toolkit_version: str = "latest") -> str:
    """Execute a Composio tool via SDK and return a voice-friendly result string.

    Runs the synchronous SDK call in a thread executor to avoid blocking
    the asyncio event loop. Returns a natural language string suitable
    for TTS output (never raw JSON).

    IMPORTANT: Error returns use "I was not able to" language to signal the LLM
    to stop retrying and inform the user instead.

    Args:
        tool_slug: Tool identifier from COMPOSIO_SEARCH_TOOLS (e.g. MICROSOFT_TEAMS_SEND_MESSAGE)
        arguments: Dict of arguments matching the tool's schema
        toolkit_version: Toolkit version from search results (default "latest")

    Returns:
        Voice-friendly result string
    """
    from ..config import get_settings
    settings = get_settings()

    if not settings.composio_api_key or not settings.composio_user_id:
        return "I was not able to run this tool because Composio is not configured on this instance"

    try:
        client = _get_client(settings)
    except ImportError:
        return "I was not able to run this tool because the Composio package is not installed"

    try:
        # Build execute kwargs — include toolkit_version to avoid
        # "Toolkit version not specified" errors from Composio API
        execute_kwargs = {
            "slug": tool_slug,
            "user_id": settings.composio_user_id.strip(),
            "arguments": arguments,
        }
        if toolkit_version:
            execute_kwargs["toolkit_version"] = toolkit_version

        result = await asyncio.to_thread(
            lambda: client.tools.execute(**execute_kwargs)
        )

        tool_display = tool_slug.replace("_", " ").lower()

        if result.get("successful"):
            data = result.get("data", {})
            # Try to extract a meaningful message from the response
            if isinstance(data, dict):
                message = data.get("message", "")
                if message and isinstance(message, str):
                    return message
            return f"Completed {tool_display}"
        else:
            error = result.get("error", "unknown error")
            logger.warning(f"Composio execute failed for {tool_slug}: {error}")
            # CRITICAL: Use "I was not able to" language so LLM does NOT retry
            return f"I was not able to complete {tool_display} the service returned an error do not retry this tool"

    except Exception as exc:
        logger.error(f"Composio execute error for {tool_slug}: {exc}")
        tool_display = tool_slug.replace("_", " ").lower()
        # CRITICAL: Use "I was not able to" language so LLM does NOT retry
        return f"I was not able to run {tool_display} due to a connection error do not retry this tool"


async def batch_execute_composio_tools(tools: list) -> str:
    """Execute multiple Composio tools in parallel via SDK.

    Each tool in the list must have 'tool_slug' and 'arguments' keys.
    Uses asyncio.gather for true parallel execution on Composio's servers.

    Returns a voice-friendly summary of all results.
    """
    if not tools:
        return "No tools to execute"

    tasks = [
        execute_composio_tool(
            tool_slug=t.get("tool_slug", ""),
            arguments=t.get("arguments", {}),
            toolkit_version=t.get("toolkit_version", "latest"),
        )
        for t in tools
        if t.get("tool_slug")
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    summaries = []
    for tool_spec, result in zip(tools, results):
        slug = tool_spec.get("tool_slug", "unknown")
        display = slug.replace("_", " ").lower()
        if isinstance(result, Exception):
            summaries.append(f"{display} failed")
            logger.error(f"Composio batch: {slug} raised {result}")
        else:
            summaries.append(str(result))

    return " and ".join(summaries) if summaries else "All tools completed"


def get_composio_mcp_url(settings) -> Optional[tuple[str, dict]]:
    """Create a Composio Tool Router MCP session and return (url, headers).

    MCP is used for COMPOSIO_SEARCH_TOOLS (discovery) and
    COMPOSIO_MANAGE_CONNECTIONS (auth). Execution goes through
    execute_composio_tool() via the Python SDK instead.

    Returns:
        (mcp_url, mcp_headers) tuple on success, or None on failure.
    """
    if not settings.composio_api_key:
        logger.debug("Composio: COMPOSIO_API_KEY not set, skipping")
        return None

    user_id = getattr(settings, "composio_user_id", "").strip()
    if not user_id:
        logger.warning(
            "Composio: COMPOSIO_USER_ID not set. "
            "Set it to scope tool access to a specific connected account."
        )
        return None

    try:
        from composio import Composio  # type: ignore[import]
    except ImportError:
        logger.error(
            "Composio: 'composio' package not installed. "
            "Run: pip install composio>=0.11.0"
        )
        return None

    try:
        client = _get_client(settings)

        # Tool Router: toolkits define searchable scope, NOT LLM context.
        session = client.create(
            user_id=user_id,
            toolkits=COMPOSIO_TOOLKITS,
        )

        mcp_url: str = session.mcp.url
        mcp_headers: dict = getattr(session.mcp, "headers", None) or {}

        logger.info(
            f"Composio: MCP session created (search + auth) — "
            f"user_id={user_id!r}, toolkits={len(COMPOSIO_TOOLKITS)}"
        )
        return (mcp_url, mcp_headers)

    except Exception as exc:
        logger.error(f"Composio: Failed to create MCP session - {exc}")
        return None
