"""Composio Tool Router MCP session factory.

Creates a Composio MCP session with all desired toolkits configured.
The Tool Router pattern exposes only up to 10 meta-tools to the LLM
(COMPOSIO_SEARCH_TOOLS, COMPOSIO_MULTI_EXECUTE_TOOL, etc.) instead
of hundreds of individual action schemas. The LLM discovers and
executes specific tools on demand at runtime.

Toolkits define what's SEARCHABLE — not what's loaded into context.
Whether 1 toolkit or 100, the LLM always sees only up to 10 meta-tools.

See docs/COMPOSIO-TOOL-ROUTER-APPROACH.md for full architecture.

Usage in agent.py:
    from .tools.composio_router import get_composio_mcp_url, COMPOSIO_ALLOWED_TOOLS
    result = get_composio_mcp_url(settings)
    if result:
        url, headers = result
        mcp_servers.append(mcp.MCPServerHTTP(
            url=url, headers=headers, timeout=15,
            allowed_tools=COMPOSIO_ALLOWED_TOOLS,
        ))
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Composio meta-toolkits — these load the Tool Router meta-tools,
# NOT individual service schemas. External services (gmail, drive, etc.)
# are controlled by connected accounts on the Composio dashboard.
#   "composio"        → execute + manage_connections meta-tools
#   "composio_search" → search meta-tool (discovers tools across all connected apps)
COMPOSIO_TOOLKITS = ["composio", "composio_search"]

# Filter the meta-tools loaded into LLM context to just these 3.
# Composio may expose additional tools — this keeps context tight.
COMPOSIO_ALLOWED_TOOLS = [
    "COMPOSIO_SEARCH_TOOLS",         # Discover the right tool by query
    "COMPOSIO_MULTI_EXECUTE_TOOL",   # Execute discovered tools (up to 50 parallel)
    "COMPOSIO_MANAGE_CONNECTIONS",   # Handle OAuth/auth when connection is missing
]


def get_composio_mcp_url(settings) -> Optional[tuple[str, dict]]:
    """Create a Composio Tool Router MCP session and return (url, headers).

    Creates a session scoped to the configured user with all toolkits
    from COMPOSIO_TOOLKITS. The Tool Router serves up to 10 meta-tools that
    let the LLM discover and execute the right tool on demand.

    Latency: ~700-1500ms per tool call (search + execute).
    Mitigate with filler speech in the agent's system prompt.

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
        client = Composio(api_key=settings.composio_api_key)

        # Tool Router: toolkits define searchable scope, NOT LLM context.
        # The MCP session serves up to 10 meta-tools regardless of toolkit count.
        session = client.create(
            user_id=user_id,
            toolkits=COMPOSIO_TOOLKITS,
        )

        mcp_url: str = session.mcp.url
        mcp_headers: dict = getattr(session.mcp, "headers", None) or {}

        logger.info(
            f"Composio: Tool Router session created — "
            f"user_id={user_id!r}, toolkits={len(COMPOSIO_TOOLKITS)}"
        )
        return (mcp_url, mcp_headers)

    except Exception as exc:
        logger.error(f"Composio: Failed to create MCP session - {exc}")
        return None
