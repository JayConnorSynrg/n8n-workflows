"""Agent context access tool for querying session history and system data.

The n8n workflow provides universal database query access:
- session_context: Get context for a specific session
- tool_history: View tool call history
- global_context: Get cross-session context
- search_history: Search through past interactions
- custom_query: Natural language question -> AI-generated SQL (for outlier questions)

Requires confirmation gating before executing any query.
"""
import json
import uuid
from typing import Optional, Literal

import aiohttp
from livekit.agents import llm

from ..config import get_settings

settings = get_settings()

QueryType = Literal[
    "session_context",
    "tool_history",
    "global_context",
    "search_history",
    "custom_query"
]


@llm.function_tool(
    name="query_context",
    description="""Query the agent's context database for session history, tool calls, or system data.

    Available query types:
    - session_context: Get context for current or specific session
    - tool_history: View history of tool calls and their results
    - global_context: Get cross-session persistent context
    - search_history: Search through past interactions by keyword
    - custom_query: Ask any question about the data (AI will generate appropriate query)

    IMPORTANT: For sensitive data queries, always confirm with user first.""",
)
async def query_context_tool(
    query_type: str,
    session_id: Optional[str] = None,
    search_query: Optional[str] = None,
    function_name: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Query the context database via n8n webhook.

    Args:
        query_type: Type of query (session_context, tool_history, global_context, search_history, custom_query)
        session_id: Session ID for session-specific queries (optional, defaults to current)
        search_query: Search term for search_history or natural language for custom_query
        function_name: Filter tool_history by function name (optional)
        limit: Maximum results to return

    Returns:
        Query results formatted for voice or error message
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/agent-context-query"

    intent_id = f"lk_{uuid.uuid4().hex[:12]}"

    # Build payload based on query type
    payload = {
        "intent_id": intent_id,
        "session_id": session_id or "livekit-agent",
        "callback_url": f"{settings.n8n_webhook_base_url}/callback-noop",
        "query_type": query_type,
        "limit": limit,
    }

    # Add query-type specific parameters
    if query_type == "tool_history" and function_name:
        payload["function_name"] = function_name

    if query_type in ("search_history", "custom_query") and search_query:
        payload["search_query"] = search_query
    elif query_type == "custom_query" and not search_query:
        return "Custom query requires a search_query parameter with your question."

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                result = await response.json()

                if response.status == 200:
                    status = result.get("status", "")

                    # Handle gated response
                    if status == "COMPLETED":
                        voice_response = result.get("voice_response")
                        if voice_response:
                            return voice_response
                    elif status == "CANCELLED":
                        return result.get("voice_response", "Query was cancelled")

                    # Format results based on query type
                    return _format_context_results(query_type, result)
                else:
                    error_msg = result.get("error", result.get("message", "Unknown error"))
                    return f"Query failed: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error querying context: {str(e)}"
    except Exception as e:
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
        # Custom query returns AI-formatted response
        data = result.get("data", result.get("results", []))
        sql_used = result.get("generated_sql", "")

        if not data:
            return "No results found for your custom query."

        # Return the data summary
        if isinstance(data, list):
            return f"Found {len(data)} results from custom query."
        return str(data)[:500]  # Truncate long responses

    return f"Query completed with {results_count} results."


@llm.function_tool(
    name="get_session_summary",
    description="""Get a summary of the current session including all tool calls and context.
    Use this to understand what has happened in the conversation so far.""",
)
async def get_session_summary_tool(
    session_id: Optional[str] = None,
) -> str:
    """Get session summary via n8n webhook.

    Args:
        session_id: Session ID (optional, defaults to current session)

    Returns:
        Session summary or error message
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/agent-context-query"

    intent_id = f"lk_{uuid.uuid4().hex[:12]}"
    payload = {
        "intent_id": intent_id,
        "session_id": session_id or "livekit-agent",
        "callback_url": f"{settings.n8n_webhook_base_url}/callback-noop",
        "query_type": "session_context",
        "include_summary": True,
        "limit": 50,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                result = await response.json()

                if response.status == 200:
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
        return f"Network error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
