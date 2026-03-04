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
import logging
import uuid
from typing import Optional

import aiohttp
from livekit.agents import llm

from ..utils.n8n_client import n8n_post
from ..utils.short_term_memory import store_tool_result

logger = logging.getLogger(__name__)


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
    # Build payload matching n8n workflow expected format
    intent_id = f"lk_{uuid.uuid4().hex[:12]}"

    payload = {
        "query": query,
        "top_k": max_results,
        "intent_id": intent_id,
    }

    try:
        # 20s timeout — sufficient for Pinecone embedding+query; 60s is too long for voice UX
        http_status, result = await n8n_post("voice-query-vector-db", payload, timeout=20)

        if http_status == 200:
            # Support all response shapes from z02K1a54akYXMkyj and legacy workflows:
            # z02K1a54akYXMkyj shape: { success, voice_response, result: [...], results_count }
            #   result is a LIST of {text, candidateName, candidateId, score, id, metadata}
            # AIO shape:    { status, voice_response, result: { documents: [...] } }
            # Legacy shape: { results: [...], query, totalResults }
            voice_response = result.get("voice_response")

            # Normalise result field — may be a list (z02K1a54akYXMkyj) or a dict (AIO shape)
            _result_raw = result.get("result", {})
            if isinstance(_result_raw, list):
                # z02K1a54akYXMkyj: result is a flat list of match objects
                raw_results = _result_raw
                documents = [
                    {
                        "title": r.get("candidateName") or (r.get("metadata") or {}).get("candidateName") or (r.get("metadata") or {}).get("name") or f"Result {i+1}",
                        "snippet": (r.get("text") or (r.get("metadata") or {}).get("text_excerpt") or "")[:300],
                        "score": r.get("score", 0),
                        "candidate_id": r.get("candidateId") or (r.get("metadata") or {}).get("candidateId") or r.get("id", ""),
                    }
                    for i, r in enumerate(raw_results)
                ]
            else:
                # AIO dict shape: result.documents or result.top_results
                _result_obj = _result_raw  # dict
                documents = _result_obj.get("documents", [])
                if not documents:
                    raw_results = _result_obj.get("top_results", []) or result.get("results", [])
                    documents = [
                        {
                            "title": r.get("candidateName") or (r.get("metadata") or {}).get("candidateName") or (r.get("metadata") or {}).get("name") or f"Result {i+1}",
                            "snippet": (r.get("content") or (r.get("metadata") or {}).get("text_excerpt") or "")[:300],
                            "score": r.get("score", 0),
                            "candidate_id": r.get("candidateId") or (r.get("metadata") or {}).get("candidateId") or r.get("id", ""),
                        }
                        for i, r in enumerate(raw_results)
                    ]

            # Store to short-term memory for cross-tool use
            if documents:
                summary = f"Found {len(documents)} results for: {query[:50]}"
                store_tool_result(
                    tool_name="query_database",
                    operation="search",
                    data=documents,
                    summary=summary,
                    suggested_uses=["email_report", "reference", "analysis"],
                )
                logger.info(f"Database query results stored to STM: {len(documents)} items")

            if voice_response:
                return voice_response + "\n\n[Memory: Results saved for follow-up use]"

            if not documents:
                return result.get("message", "No results found for your query.")

            # Format results for voice
            formatted = []
            for i, r in enumerate(documents[:max_results], 1):
                title = r.get("title", f"Result {i}")
                snippet = r.get("snippet", r.get("text", r.get("content", "")))[:200]
                formatted.append(f"{i}. {title}: {snippet}")

            return "\n".join(formatted) + "\n\n[Memory: Results saved for follow-up use]"
        else:
            error_msg = result.get("error", result.get("message", "Unknown error"))
            return f"Search failed: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error querying database: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


async def vector_search_tool(
    query: str,
    max_results: Optional[int] = 5,
    session_id: str = "livekit-agent",
) -> dict:
    """Search the knowledge base via n8n vector search webhook.

    Wired to n8n workflow z02K1a54akYXMkyj (Voice Tool: Query Vector DB).
    Webhook path: /voice-query-vector-db

    Args:
        query: Natural language search query
        max_results: Maximum number of results to return (default 5)
        session_id: Session identifier for the tool call record

    Returns:
        dict with:
          success: bool
          voice_response: str (pre-formatted for TTS, if present)
          results: list of {score, text, metadata}
          error: str (on failure)
    """
    intent_id = f"lk_{uuid.uuid4().hex[:12]}"

    payload = {
        "query": query,
        "top_k": max_results,
        "intent_id": intent_id,
        "session_id": session_id,
    }

    try:
        http_status, data = await n8n_post("voice-query-vector-db", payload)

        if http_status != 200:
            return {
                "success": False,
                "error": f"Vector search returned HTTP {http_status}",
            }

        # Prefer pre-formatted voice_response from workflow
        voice_response = data.get("voice_response") or ""

        # Extract result array — flat list of {score, text, metadata} objects
        raw_result = data.get("result", [])
        if isinstance(raw_result, dict):
            # Older shape: result.documents or result.top_results
            raw_result = (
                raw_result.get("documents")
                or raw_result.get("top_results")
                or []
            )

        results = []
        for item in raw_result:
            if not isinstance(item, dict):
                continue
            results.append({
                "score": item.get("score", 0.0),
                "text": item.get("text", ""),
                "metadata": item.get("metadata", {}),
            })

        return {
            "success": True,
            "voice_response": voice_response,
            "results": results,
            "status": data.get("status", "COMPLETED"),
        }

    except aiohttp.ClientError as e:
        logger.error(f"vector_search_tool network error: {e}")
        return {"success": False, "error": f"Network error: {str(e)}"}
    except Exception as e:
        logger.error(f"vector_search_tool unexpected error: {e}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
