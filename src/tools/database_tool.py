"""Database query tool for vector search via n8n webhook.

The n8n workflow implements a gated execution pattern with context storage:
1. Voice agent asks user for query
2. n8n executes vector search
3. Results stored in session_context table (1-hour TTL)
4. Results returned for voice announcement

For the initial LiveKit deployment, we use simplified direct execution
without the callback gates (callback_url is set to a no-op endpoint).

Short-Term Memory:
All query results are automatically stored in short-term memory for 5 minutes,
enabling cross-tool data reuse (e.g., email query results, save to vector store).
"""
import json
import logging
import uuid
from typing import Optional

import aiohttp
from livekit.agents import llm

from ..config import get_settings
from ..utils.short_term_memory import store_tool_result

logger = logging.getLogger(__name__)
settings = get_settings()


@llm.function_tool(
    name="query_database",
    description="""Search the knowledge base for information.
    Use this to look up data, find documents, or answer questions about stored content.
    Results are ranked by relevance to your query.
    Results are auto-saved to short-term memory for cross-tool use.""",
)
async def query_database_tool(
    query: str,
    filters: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """Query the vector database via n8n webhook.

    Args:
        query: Natural language search query
        filters: Optional JSON string of filters (e.g., '{"date_range": "2024"}')
        max_results: Maximum number of results to return

    Returns:
        Search results formatted as text with memory offer
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/voice-query-vector-db"

    # Build payload matching n8n workflow expected format
    intent_id = f"lk_{uuid.uuid4().hex[:12]}"

    # Build structured query from user input
    structured_query = {"semantic_query": query}
    if filters:
        try:
            structured_query["filters"] = json.loads(filters)
        except json.JSONDecodeError:
            pass

    payload = {
        "intent_id": intent_id,
        "session_id": "livekit-agent",
        # For initial deployment, use no-op callback
        "callback_url": f"{settings.n8n_webhook_base_url}/callback-noop",
        "parameters": {
            "user_query": query,
            "structured_query": structured_query,
            "max_results": max_results,
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                # Increased timeout for gated workflow execution
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                result = await response.json()

                if response.status == 200:
                    status = result.get("status", "")
                    if status == "COMPLETED":
                        # Prefer voice_response if available
                        voice_response = result.get("voice_response")

                        # Get results for memory storage
                        results = result.get("result", {}).get("documents", [])

                        # Store to short-term memory for cross-tool use
                        if results:
                            summary = f"Found {len(results)} results for: {query[:50]}"
                            store_tool_result(
                                tool_name="query_database",
                                operation="search",
                                data=results,
                                summary=summary,
                                suggested_uses=["email_report", "reference", "analysis"],
                            )
                            logger.info(f"Database query results stored to STM: {len(results)} items")

                        if voice_response:
                            return voice_response + "\n\n[Memory: Results saved for follow-up use]"

                        # Fall back to formatting results
                        if not results:
                            return "No results found for your query."

                        # Format results for voice
                        formatted = []
                        for i, r in enumerate(results[:max_results], 1):
                            title = r.get("title", f"Result {i}")
                            snippet = r.get("snippet", r.get("content", ""))[:200]
                            formatted.append(f"{i}. {title}: {snippet}")

                        return "\n".join(formatted) + "\n\n[Memory: Results saved for follow-up use]"
                    elif status == "CANCELLED":
                        return result.get("voice_response", "Search was cancelled")
                    else:
                        return "Search completed but no results returned."
                else:
                    error_msg = result.get("error", result.get("voice_response", "Unknown error"))
                    return f"Search failed: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error querying database: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
