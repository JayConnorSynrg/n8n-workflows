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


def _friendly_name(tool_slug: str) -> str:
    """Convert a tool slug like TEAMS_SEND_MESSAGE to a voice-friendly name.

    Strips common prefixes (service names) and produces natural phrases.
    E.g. GOOGLESHEETS_BATCH_UPDATE -> batch update sheets
         TEAMS_SEND_MESSAGE -> send message in Teams
    """
    slug = tool_slug.upper()
    # Known service prefixes → natural suffix
    service_map = {
        "TEAMS_": "in Teams",
        "MICROSOFTTEAMS_": "in Teams",
        "ONEDRIVE_": "on OneDrive",
        "GOOGLESHEETS_": "in Sheets",
        "GOOGLEDOCS_": "in Docs",
        "EXCEL_": "in Excel",
        "SLACK_": "in Slack",
        "GMAIL_": "via email",
        "GITHUB_": "on GitHub",
        "CANVA_": "in Canva",
        "APIFY_": "",
        "FIRECRAWL_": "",
        "SUPABASE_": "in the database",
    }
    suffix = ""
    action_part = slug
    for prefix, svc_suffix in service_map.items():
        if slug.startswith(prefix):
            action_part = slug[len(prefix):]
            suffix = svc_suffix
            break

    # Convert ACTION_NAME to "action name"
    action = action_part.replace("_", " ").lower().strip()
    if suffix:
        return f"{action} {suffix}"
    return action


def _extract_voice_result(data, tool_slug: str, tool_display: str) -> str:
    """Extract a meaningful voice-friendly result from Composio response data.

    Tries multiple strategies to find useful content in the response:
    1. Explicit message field
    2. Title/name/subject fields (common in search/list results)
    3. Count of items (for list operations)
    4. Body/content/text fields (for content retrieval)
    5. Fallback to generic completion message
    """
    if not isinstance(data, dict):
        if isinstance(data, str) and len(data) > 5:
            return data[:200]
        return f"Completed {tool_display}"

    # 1. Explicit message
    message = data.get("message", "")
    if message and isinstance(message, str) and len(message) > 3:
        return message[:200]

    # 2. Response data nested in 'data' or 'response_data'
    inner = data.get("data", data.get("response_data", data))
    if isinstance(inner, dict) and inner is not data:
        msg = inner.get("message", "")
        if msg and isinstance(msg, str) and len(msg) > 3:
            return msg[:200]

    # 3. List of items (search results, file lists, messages)
    for key in ("items", "results", "messages", "files", "values", "records"):
        items = data.get(key, inner.get(key, None) if isinstance(inner, dict) else None)
        if isinstance(items, list):
            count = len(items)
            if count == 0:
                return f"No results found for {tool_display}"
            # Try to extract names/titles from first few items
            names = []
            for item in items[:5]:
                if isinstance(item, dict):
                    name = item.get("name", item.get("title", item.get("subject", "")))
                    if name:
                        names.append(str(name))
            if names:
                listing = " and ".join(names[:3])
                if count > 3:
                    listing += f" and {count - 3} more"
                return f"Found {count} results including {listing}"
            return f"Found {count} results for {tool_display}"

    # 4. Single item with title/name
    for key in ("title", "name", "subject", "fileName", "file_name"):
        val = data.get(key, "")
        if val and isinstance(val, str):
            return f"Got it {val}"

    # 5. Status/success indicators
    if data.get("success") or data.get("ok") or data.get("status") == "ok":
        return f"Done {tool_display}"

    # 6. Fallback
    return f"Completed {tool_display}"


async def execute_composio_tool(tool_slug: str, arguments: dict) -> str:
    """Execute a Composio tool via SDK and return a voice-friendly result string.

    Runs the synchronous SDK call in a thread executor to avoid blocking
    the asyncio event loop. Returns a natural language string suitable
    for TTS output (never raw JSON).

    IMPORTANT: Error returns use "I was not able to" language to signal the LLM
    to stop retrying and inform the user instead.

    Args:
        tool_slug: Tool identifier from COMPOSIO_SEARCH_TOOLS (e.g. COMPOSIO_SEARCH_WEB)
        arguments: Dict of arguments matching the tool's schema

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
        user_id = settings.composio_user_id.strip()
        logger.info(f"Composio SDK execute: slug={tool_slug}, user_id={user_id}, args_keys={list(arguments.keys())}")

        result = await asyncio.to_thread(
            lambda: client.tools.execute(
                slug=tool_slug,
                user_id=user_id,
                arguments=arguments,
            )
        )

        tool_display = _friendly_name(tool_slug)

        if result.get("successful"):
            data = result.get("data", {})
            logger.info(f"[TOOL_CALL] Composio OK: {tool_slug} data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}")
            # Extract meaningful content from the response
            return _extract_voice_result(data, tool_slug, tool_display)
        else:
            error = result.get("error", "unknown error")
            logger.warning(f"[TOOL_CALL] Composio FAIL: {tool_slug} error={error}")
            # CRITICAL: Use "I was not able to" language so LLM does NOT retry
            return f"I was not able to complete {tool_display} the service returned an error do not retry this tool"

    except Exception as exc:
        logger.error(f"[TOOL_CALL] Composio ERROR: {tool_slug} exception={exc}")
        tool_display = _friendly_name(tool_slug)
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
        )
        for t in tools
        if t.get("tool_slug")
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    summaries = []
    for tool_spec, result in zip(tools, results):
        slug = tool_spec.get("tool_slug", "unknown")
        display = _friendly_name(slug)
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
