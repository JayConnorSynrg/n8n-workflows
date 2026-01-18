"""Agent context access tool for querying session history and system data.

CACHE-FIRST PATTERN:
1. Check in-memory cache for recent data
2. If cache hit and fresh: return immediately (< 1ms)
3. If cache miss or stale: query n8n webhook
4. Cache the result for future requests

Cache TTLs:
- session_context: 5 minutes (frequently accessed)
- tool_history: 2 minutes (more volatile)
- global_context: 10 minutes (stable data)
- custom_query: 1 minute (fresh data preferred)
"""
import hashlib
import json
import logging
import uuid
from typing import Any, Dict, Optional, Literal

import aiohttp
from livekit.agents import llm

from ..config import get_settings
from ..utils.context_cache import get_cache_manager

logger = logging.getLogger(__name__)
settings = get_settings()

QueryType = Literal[
    "session_context",
    "tool_history",
    "global_context",
    "search_history",
    "custom_query"
]

# Cache TTLs by query type (seconds)
CACHE_TTLS = {
    "session_context": 300.0,   # 5 minutes
    "tool_history": 120.0,      # 2 minutes
    "global_context": 600.0,    # 10 minutes
    "search_history": 60.0,     # 1 minute
    "custom_query": 60.0,       # 1 minute
}


def _make_cache_key(
    query_type: str,
    session_id: str,
    search_query: Optional[str] = None,
    function_name: Optional[str] = None,
    limit: int = 10
) -> str:
    """Generate a unique cache key for the query."""
    parts = [query_type, session_id, str(limit)]
    if search_query:
        parts.append(search_query)
    if function_name:
        parts.append(function_name)
    key_string = ":".join(parts)
    # Use hash for long keys
    if len(key_string) > 100:
        return f"{query_type}:{hashlib.md5(key_string.encode()).hexdigest()}"
    return key_string


async def _fetch_from_webhook(
    query_type: str,
    session_id: str,
    search_query: Optional[str] = None,
    function_name: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Fetch context from n8n webhook (backend source of truth)."""
    webhook_url = f"{settings.n8n_webhook_base_url}/agent-context-query"
    intent_id = f"lk_{uuid.uuid4().hex[:12]}"

    payload = {
        "intent_id": intent_id,
        "session_id": session_id,
        # No callback_url = skip confirmation gate (direct query mode)
        "query_type": query_type,
        "limit": limit,
    }

    if query_type == "tool_history" and function_name:
        payload["function_name"] = function_name

    if query_type in ("search_history", "custom_query") and search_query:
        payload["search_query"] = search_query

    async with aiohttp.ClientSession() as http_session:
        async with http_session.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=30),  # Reduced from 60s
        ) as response:
            return await response.json()


@llm.function_tool(
    name="query_context",
    description="""Query the agent's context database for session history, tool calls, or system data.

    Available query types:
    - session_context: Get context for current or specific session
    - tool_history: View history of tool calls and their results
    - global_context: Get cross-session persistent context
    - search_history: Search through past interactions by keyword
    - custom_query: Ask any question about the data (AI will generate appropriate query)

    Results are cached for fast repeated access.""",
)
async def query_context_tool(
    query_type: str,
    session_id: Optional[str] = None,
    search_query: Optional[str] = None,
    function_name: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Query the context database with cache-first pattern.

    Args:
        query_type: Type of query (session_context, tool_history, global_context, search_history, custom_query)
        session_id: Session ID for session-specific queries (optional, defaults to current)
        search_query: Search term for search_history or natural language for custom_query
        function_name: Filter tool_history by function name (optional)
        limit: Maximum results to return

    Returns:
        Query results formatted for voice or error message
    """
    effective_session_id = session_id or "livekit-agent"

    # Validate custom_query has search_query
    if query_type == "custom_query" and not search_query:
        return "Custom query requires a search_query parameter with your question."

    # Generate cache key
    cache_key = _make_cache_key(
        query_type, effective_session_id, search_query, function_name, limit
    )

    # Check cache first
    cache_manager = get_cache_manager()
    cached_result = cache_manager.query_cache.get(cache_key)

    if cached_result is not None:
        logger.debug(f"Cache HIT for {query_type} (key={cache_key[:50]}...)")
        return _format_context_results(query_type, cached_result)

    logger.debug(f"Cache MISS for {query_type}, fetching from webhook...")

    # Cache miss - fetch from webhook
    try:
        result = await _fetch_from_webhook(
            query_type=query_type,
            session_id=effective_session_id,
            search_query=search_query,
            function_name=function_name,
            limit=limit,
        )

        # Check for errors
        if result.get("status") == "CANCELLED":
            return result.get("voice_response", "Query was cancelled")

        # Cache the successful result
        ttl = CACHE_TTLS.get(query_type, 60.0)
        cache_manager.query_cache.set(cache_key, result, ttl)
        logger.debug(f"Cached {query_type} result with TTL={ttl}s")

        # Also update specialized caches for common query types
        if query_type == "session_context":
            cache_manager.set_session_context(effective_session_id, result, ttl)
        elif query_type == "tool_history":
            cache_manager.set_tool_history(
                result.get("data", []),
                session_id=effective_session_id,
                function_name=function_name,
                ttl=ttl
            )
        elif query_type == "global_context":
            cache_manager.set_global_context(result, ttl=ttl)

        return _format_context_results(query_type, result)

    except aiohttp.ClientError as e:
        logger.error(f"Network error querying context: {e}")
        return f"Network error querying context: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in query_context: {e}")
        return f"Unexpected error: {str(e)}"


def _format_context_results(query_type: str, result: dict) -> str:
    """Format query results for voice output."""

    results_count = result.get("results_count", 0)
    message = result.get("message", result.get("summary", ""))

    if message:
        return message

    if query_type == "session_context":
        data = result.get("data", result.get("results", []))
        if not data:
            return "No context found for this session."
        return f"Found {len(data)} context entries for this session."

    elif query_type == "tool_history":
        data = result.get("data", result.get("results", []))
        if not data:
            return "No tool call history found."

        # Summarize tool calls
        tools_used = {}
        for item in data:
            fn = item.get("function_name", "unknown")
            tools_used[fn] = tools_used.get(fn, 0) + 1

        summary = ", ".join([f"{fn}: {count}" for fn, count in tools_used.items()])
        return f"Found {len(data)} tool calls. Summary: {summary}"

    elif query_type == "global_context":
        data = result.get("data", result.get("results", []))
        if not data:
            return "No global context entries found."
        return f"Found {len(data)} global context entries."

    elif query_type == "search_history":
        data = result.get("data", result.get("results", []))
        if not data:
            return "No matching history found for your search."
        return f"Found {len(data)} matching entries in history."

    elif query_type == "custom_query":
        data = result.get("data", result.get("results", []))
        if not data:
            return "No results found for your custom query."
        if isinstance(data, list):
            return f"Found {len(data)} results from custom query."
        return str(data)[:500]

    return f"Query completed with {results_count} results."


@llm.function_tool(
    name="get_session_summary",
    description="""Get a summary of the current session including all tool calls and context.
    Use this to understand what has happened in the conversation so far.
    Results are cached for instant access on repeated calls.""",
)
async def get_session_summary_tool(
    session_id: Optional[str] = None,
) -> str:
    """Get session summary with cache-first pattern.

    Args:
        session_id: Session ID (optional, defaults to current session)

    Returns:
        Session summary or error message
    """
    effective_session_id = session_id or "livekit-agent"

    # Check specialized session cache first
    cache_manager = get_cache_manager()
    cached_context = cache_manager.get_session_context(effective_session_id)

    if cached_context is not None:
        logger.debug(f"Session cache HIT for {effective_session_id}")
        # Format cached context as summary
        data = cached_context.get("data", [])
        tool_calls = cached_context.get("tool_calls", [])

        parts = []
        if data:
            parts.append(f"{len(data)} context entries")
        if tool_calls:
            parts.append(f"{len(tool_calls)} tool calls")

        if parts:
            return f"Session summary (cached): {', '.join(parts)}."
        return "No activity recorded for this session yet."

    logger.debug(f"Session cache MISS for {effective_session_id}, fetching...")

    # Cache miss - fetch from webhook
    try:
        webhook_url = f"{settings.n8n_webhook_base_url}/agent-context-query"
        intent_id = f"lk_{uuid.uuid4().hex[:12]}"

        payload = {
            "intent_id": intent_id,
            "session_id": effective_session_id,
            # No callback_url = skip confirmation gate
            "query_type": "session_context",
            "include_summary": True,
            "limit": 50,
        }

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                result = await response.json()

                if response.status == 200:
                    # Cache the result
                    cache_manager.set_session_context(
                        effective_session_id,
                        result,
                        ttl=300.0  # 5 minutes
                    )

                    voice_response = result.get("voice_response")
                    if voice_response:
                        return voice_response

                    summary = result.get("summary", result.get("message", ""))
                    if summary:
                        return summary

                    # Build summary from data
                    data = result.get("data", [])
                    tool_calls = result.get("tool_calls", [])

                    parts = []
                    if data:
                        parts.append(f"{len(data)} context entries")
                    if tool_calls:
                        parts.append(f"{len(tool_calls)} tool calls")

                    if parts:
                        return f"Session summary: {', '.join(parts)}."
                    return "No activity recorded for this session yet."
                else:
                    error_msg = result.get("error", "Unknown error")
                    return f"Failed to get session summary: {error_msg}"

    except aiohttp.ClientError as e:
        logger.error(f"Network error getting session summary: {e}")
        return f"Network error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in get_session_summary: {e}")
        return f"Unexpected error: {str(e)}"


# -------------------------------------------------------------------------
# Cache Management Functions (for agent lifecycle)
# -------------------------------------------------------------------------

async def warm_session_cache(session_id: str) -> None:
    """Pre-warm cache with session context at session start.

    Call this when the agent joins a room to pre-fetch context.
    """
    logger.info(f"Pre-warming cache for session: {session_id}")
    try:
        result = await _fetch_from_webhook(
            query_type="session_context",
            session_id=session_id,
            limit=50
        )
        cache_manager = get_cache_manager()
        cache_manager.set_session_context(session_id, result, ttl=300.0)
        logger.info(f"Cache pre-warmed for session: {session_id}")
    except Exception as e:
        logger.warning(f"Failed to pre-warm cache: {e}")


def invalidate_session_cache(session_id: str) -> None:
    """Invalidate all cached data for a session.

    Call this when session ends or context changes significantly.
    """
    cache_manager = get_cache_manager()
    cache_manager.invalidate_session(session_id)
    logger.info(f"Cache invalidated for session: {session_id}")


def get_cache_stats() -> Dict[str, Any]:
    """Get current cache statistics for monitoring."""
    return get_cache_manager().get_all_stats()
