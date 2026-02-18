"""Composio MCP session factory using the official Composio Python SDK.

Creates a scoped MCP session for the configured user with the specified toolkits.
The resulting MCP URL is passed to LiveKit's MCPServerHTTP - the LLM sees the
tool schemas natively without any meta-tool indirection.

Usage in agent.py:
    from .tools.composio_router import get_composio_mcp_url
    result = get_composio_mcp_url(settings)
    if result:
        url, headers = result
        mcp_servers.append(mcp.MCPServerHTTP(url=url, timeout=15))
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Toolkits exposed through the Composio MCP session
DEFAULT_TOOLKITS = [
    "MICROSOFT_TEAMS",
    "ONEDRIVE",
    "EXCEL",
    "CANVA",
    "APIFY",
    "FIRECRAWL",
    "SUPABASE",
    "COMPOSIO_SEARCH",
]


def get_composio_mcp_url(settings) -> Optional[tuple[str, dict]]:
    """Create a scoped Composio MCP session and return (url, headers).

    This is a synchronous function - it runs at agent init time before the
    asyncio event loop is active. The Composio SDK is synchronous by default.

    Returns:
        (mcp_url, mcp_headers) tuple on success, or None if Composio is
        not configured or session creation fails.
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
            "Run: pip install composio>=0.7.0"
        )
        return None

    try:
        client = Composio(api_key=settings.composio_api_key)

        # Create a scoped session for the user with only the configured toolkits.
        # This keeps the MCP tool list focused rather than dumping all 500+
        # Composio actions into the LLM context.
        session = client.create(
            user_id=user_id,
            toolkits=DEFAULT_TOOLKITS,
        )

        mcp_url: str = session.mcp.url
        mcp_headers: dict = session.mcp.headers or {}

        logger.info(
            f"Composio: SDK MCP session created for user_id={user_id!r} "
            f"toolkits={DEFAULT_TOOLKITS}"
        )
        return (mcp_url, mcp_headers)

    except Exception as exc:
        logger.error(f"Composio: Failed to create MCP session - {exc}")
        return None
