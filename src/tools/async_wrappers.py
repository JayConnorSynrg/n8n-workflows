"""AIO Ecosystem Tool Wrappers - Executive Assistant Edition

Architecture:
- Tools return natural language summaries, never JSON
- Descriptions guide LLM behavior for executive UX
- Background execution with conversational result announcements
- Tool names use camelCase (no underscores) to prevent TTS saying "underscore"
- Every tool publishes lifecycle events (tool.call → tool.executing → tool.completed)
  to the LiveKit data channel for real-time client-side observability
"""
import asyncio
import time
from contextvars import ContextVar
from typing import Optional

try:
    from ..utils.tool_logger import log_composio_call as _log_native_call
    _TOOL_LOGGER_AVAILABLE = True
except Exception:
    _TOOL_LOGGER_AVAILABLE = False
    _log_native_call = None  # type: ignore[assignment]


def _fire_native_log(slug: str, arguments: dict, voice_result: str, duration_ms: int) -> None:
    """Best-effort fire-and-forget log for native (non-Composio) tool calls."""
    if not _TOOL_LOGGER_AVAILABLE or _log_native_call is None:
        return
    try:
        _log_native_call(
            user_id=None,
            slug=slug,
            arguments=arguments,
            result_data=None,
            voice_result=voice_result,
            success=True,
            error_message=None,
            duration_ms=duration_ms,
            source="native",
        )
    except Exception:  # nosec B110 — fire-and-forget logging; import failure is non-fatal
        pass

from livekit.agents import llm

from ..config import get_settings as _get_settings
from ..utils.async_tool_worker import get_worker
from ..utils.room_publisher import (
    publish_tool_start,
    publish_tool_executing,
    publish_tool_completed,
    publish_tool_error,
)
from ..utils.short_term_memory import (
    recall_by_category,
    recall_by_tool,
    recall_most_recent,
    get_memory_summary,
    store_tool_result,
    ToolCategory,
)
from . import email_tool, database_tool, vector_store_tool, google_drive_tool, agent_context_tool, contact_tool, prospect_scraper_tool
from .gamma_tool import generate_presentation_async, generate_document_async, generate_webpage_async, generate_social_async
from .deep_store_tool import deep_store_async, deep_recall_async
from .user_profile_tool import update_user_profile_tool as _update_user_profile_tool
from .tool_executor import (
    delegate_tools as _delegate_tools_impl,
    run_background_delegation as _run_background_delegation,
    _active_delegation,
)
from ..utils.n8n_client import n8n_post as _n8n_post

# Memory module — cross-session persistent memory (optional, gracefully disabled if unavailable)
try:
    from ..memory import memory_store as _memory_store
    from ..memory import capture as _memory_capture
    _MEMORY_AVAILABLE = True
except Exception:
    _memory_store = None  # type: ignore[assignment]
    _memory_capture = None  # type: ignore[assignment]
    _MEMORY_AVAILABLE = False

# Session ID context variable — set by agent.py before each LLM turn
# Allows delegate_tools_async to know the current session without closure access
_tool_session_id: ContextVar[str] = ContextVar("_tool_session_id", default="")


# =============================================================================
# EMAIL - WRITE OPERATION (REQUIRES CONFIRMATION)
# =============================================================================

@llm.function_tool(
    name="sendEmail",
    description="Send an email. Confirm recipient subject and message with user first.",
)
async def send_email_async(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
) -> str:
    """Send email synchronously — LLM gets real confirmation back to confirm task completion."""
    call_id = await publish_tool_start("sendEmail", {"to": to, "subject": subject})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    await email_tool.send_email_tool(to, subject, body, cc)
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, "Email sent", duration_ms=_dur)
    result = f"Email sent to {to.split('@')[0].replace('.', ' ').title()}"
    _fire_native_log("send_email", {"to": to, "subject": subject}, result, _dur)
    # Capture recipient preference for fast-path email (non-blocking, best-effort)
    try:
        store_tool_result(
            tool_name="sendEmail",
            operation="recipient_preference",
            data={"email": to},
            summary=f"Known email recipient: {to}",
            metadata={"preference_key": f"known_email_recipient:{to}"},
        )
    except Exception:  # nosec B110
        pass  # Never block email delivery for preference capture failure
    return result


# =============================================================================
# GOOGLE DRIVE - READ OPERATIONS (IMMEDIATE EXECUTION)
# =============================================================================

@llm.function_tool(
    name="searchDrive",
    description=(
        "Search Google Drive for documents by keyword or topic. Summarize findings for the user. "
        "NOTE: Gamma presentations and slide decks are NOT stored in Google Drive — they live on gamma.app. "
        "For a Gamma created this session use recall(query='gamma presentation'). "
        "For saved Gamma content use composioExecute GAMMA_LIST_FOLDERS. "
        "Never call this tool when the user is asking about a presentation, slide deck, or Gamma."
    ),
)
async def search_documents_async(
    query: str,
    max_results: int = 5,
) -> str:
    """Search Drive documents - runs synchronously for immediate results."""
    call_id = await publish_tool_start("searchDrive", {"query": query})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await google_drive_tool.search_documents_tool(query, max_results)
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
    _fire_native_log("search_drive", {"query": query, "max_results": max_results}, result, _dur)
    return result


@llm.function_tool(
    name="getFile",
    description="Retrieve a specific file from Google Drive by file ID from a previous search.",
)
async def get_document_async(file_id: str) -> str:
    """Get document content - runs synchronously for immediate results."""
    call_id = await publish_tool_start("getFile", {"file_id": file_id})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await google_drive_tool.get_document_tool(file_id)
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
    _fire_native_log("get_file", {"file_id": file_id}, result, _dur)
    return result


@llm.function_tool(
    name="listFiles",
    description=(
        "List recent files in Google Drive. Summarize results naturally. "
        "NOTE: Gamma presentations are hosted on gamma.app and do NOT appear in Drive listings. "
        "Use recall(query='gamma presentation') for a Gamma created this session."
    ),
)
async def list_drive_files_async(max_results: int = 10) -> str:
    """List Drive files - runs synchronously for immediate results."""
    call_id = await publish_tool_start("listFiles", {"max_results": max_results})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await google_drive_tool.list_drive_files_tool(max_results)
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
    _fire_native_log("list_files", {"max_results": max_results}, result, _dur)
    return result


# =============================================================================
# KNOWLEDGE BASE - MIXED OPERATIONS
# =============================================================================

@llm.function_tool(
    name="knowledgeBase",
    description="Search or store in the knowledge base. For search execute immediately. For store confirm with user first.",
)
async def vector_store_async(
    action: str,
    content: str,
    category: Optional[str] = None,
) -> str:
    """Knowledge base operations."""
    if action.lower() in ["search", "find", "query"]:
        call_id = await publish_tool_start("knowledgeBase", {"action": "search", "content": content[:40]})
        await publish_tool_executing(call_id)
        _t0 = time.monotonic()
        result = await database_tool.query_database_tool(content)
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_completed(call_id, result[:100] if result else "", duration_ms=_dur)
        return result
    else:
        call_id = await publish_tool_start("knowledgeBase", {"action": "store", "content": content[:40]})
        await publish_tool_executing(call_id)
        worker = get_worker()
        if not worker:
            _t0 = time.monotonic()
            result = await vector_store_tool.store_knowledge_tool(content, category or "general", None)
            _dur = int((time.monotonic() - _t0) * 1000)
            await publish_tool_completed(call_id, "Stored", duration_ms=_dur)
            return result
        await worker.dispatch(
            tool_name="storeKnowledge",
            tool_func=vector_store_tool.store_knowledge_tool,
            kwargs={"content": content, "category": category or "general", "source": None},
            call_id=call_id,
        )
        return "Storing to knowledge base"


# =============================================================================
# DATABASE - READ OPERATION
# =============================================================================

@llm.function_tool(
    name="queryDatabase",
    description=(
        "Semantic vector search over the Auto Pay Plus candidate database. "
        "Use this to find candidates, applicants, hiring records, job postings, or any Auto Pay Plus HR/recruitment data. "
        "Connects to Pinecone vector database via n8n webhook (voice-query-vector-db). "
        "Returns ranked results by relevance. Execute immediately - no confirmation needed."
    ),
)
async def database_query_async(query: str) -> str:
    """Query database - runs synchronously for immediate results."""
    call_id = await publish_tool_start("queryDatabase", {"query": query})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await database_tool.query_database_tool(query)
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
    _fire_native_log("query_database", {"query": query}, result, _dur)
    return result


@llm.function_tool(
    name="vectorSearch",
    description=(
        "Search the knowledge base for information. "
        "Use when the user asks to look up, find, or search for documents or stored information. "
        "Returns ranked results by relevance. Execute immediately - no confirmation needed."
    ),
)
async def vector_search_async(
    query: str,
    max_results: Optional[int] = 5,
) -> str:
    """Search knowledge base via Pinecone vector search - runs synchronously for immediate results."""
    call_id = await publish_tool_start("vectorSearch", {"query": query, "max_results": max_results})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await database_tool.vector_search_tool(query=query, max_results=max_results)
    _dur = int((time.monotonic() - _t0) * 1000)

    if not result.get("success"):
        error_msg = result.get("error", "Unknown error")
        await publish_tool_completed(call_id, "Search failed", duration_ms=_dur)
        _fire_native_log("vector_search", {"query": query}, error_msg, _dur)
        return f"I was unable to search the knowledge base. {error_msg}"

    # Use pre-formatted voice_response from the workflow if available
    voice_response = result.get("voice_response", "")
    if voice_response:
        await publish_tool_completed(call_id, voice_response[:100], duration_ms=_dur)
        _fire_native_log("vector_search", {"query": query}, voice_response, _dur)
        return voice_response

    # Format the flat result array into a readable response
    results = result.get("results", [])
    if not results:
        msg = "I searched the knowledge base but found no matching results for that query."
        await publish_tool_completed(call_id, msg, duration_ms=_dur)
        _fire_native_log("vector_search", {"query": query}, msg, _dur)
        return msg

    lines = []
    for i, item in enumerate(results[:max_results], 1):
        text = item.get("text", "").strip()
        if text:
            lines.append(f"{i}. {text[:200]}")

    formatted = f"Found {len(results)} result{'s' if len(results) != 1 else ''}: " + " | ".join(lines)
    await publish_tool_completed(call_id, formatted[:100], duration_ms=_dur)
    _fire_native_log("vector_search", {"query": query}, formatted, _dur)
    return formatted


# =============================================================================
# SESSION CONTEXT - READ OPERATION
# =============================================================================

@llm.function_tool(
    name="checkContext",
    description=(
        "Query the PostgreSQL session database to recall this conversation. "
        "ALWAYS call this when the user asks what was discussed, what they said, what happened earlier, "
        "or wants to recall anything from this session. "
        "Use query_type='session_context' (default) for full history. "
        "Use query_type='search_history' with search_query to find a specific topic. "
        "Pass session_id from recallSessions results to retrieve a PAST session transcript. "
        "Never claim you cannot access session history without calling this tool first."
    ),
)
async def query_context_async(
    query_type: str = "session_context",
    search_query: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """Query session context - runs synchronously for immediate results."""
    call_id = await publish_tool_start("checkContext", {"query_type": query_type})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await agent_context_tool.query_context_tool(query_type=query_type, search_query=search_query, session_id=session_id)
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100] if result else "", duration_ms=_dur)
    _fire_native_log("check_context", {"query_type": query_type, "search_query": search_query or ""}, result or "", _dur)
    return result


# =============================================================================
# MEMORY RECALL - READ OPERATIONS
# =============================================================================

@llm.function_tool(
    name="recall",
    description=(
        "Recall data from memory. "
        "Use query= to search cross-session long-term memory for preferences, decisions, or past context. "
        "Use category= or tool_name= to recall recent in-session data. "
        "Use show_all=True for a full in-session memory overview."
    ),
)
async def recall_data_async(
    query: Optional[str] = None,
    category: Optional[str] = None,
    tool_name: Optional[str] = None,
    show_all: bool = False,
) -> str:
    call_id = await publish_tool_start("recall", {"query": (query or "")[:40], "show_all": show_all})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    try:
        # Level 1: In-session short-term memory (fast path — always checked first)
        if show_all:
            result = get_memory_summary()
            _dur = int((time.monotonic() - _t0) * 1000)
            await publish_tool_completed(call_id, "Memory summary", duration_ms=_dur)
            return result

        if tool_name:
            r = recall_by_tool(tool_name)
            if r:
                result = _format_recall(r)
                _dur = int((time.monotonic() - _t0) * 1000)
                await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
                return result

        if category:
            try:
                cat = ToolCategory(category.lower())
                r = recall_by_category(cat)
                if r:
                    result = _format_recall(r)
                    _dur = int((time.monotonic() - _t0) * 1000)
                    await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
                    return result
            except ValueError:
                pass

        # Level 2: Cross-session SQLite memory (only when a query is provided)
        if query and _MEMORY_AVAILABLE and _memory_store is not None:
            try:
                results = _memory_store.search(query, top_k=3)
                if results:
                    lines = ["From long-term memory:"]
                    for i, r in enumerate(results, 1):
                        lines.append(f"{i}. [{r['category']}] {r['text_safe']}")
                    result = " | ".join(lines)
                    _dur = int((time.monotonic() - _t0) * 1000)
                    await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
                    return result
            except Exception as exc:
                import logging
                logging.getLogger(__name__).error("[recall] Memory search failed: %s", exc)

        # Level 1 fallback: most recent in-session entry
        if not query:
            r = recall_most_recent()
            if r:
                result = _format_recall(r)
                _dur = int((time.monotonic() - _t0) * 1000)
                await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
                return result

        if query:
            result = f"No memory found for: {query}"
        else:
            result = "No data in memory yet"
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
        return result
    except Exception as e:
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_error(call_id, str(e)[:100], duration_ms=_dur)
        raise


def _format_recall(result: dict) -> str:
    """Format recalled data for voice output."""
    data = result.get("data")
    summary = result.get("summary", "Data found")

    if isinstance(data, list) and data:
        names = []
        for item in data[:5]:
            if isinstance(item, dict):
                name = item.get("name", item.get("title", item.get("file_name", "")))
                if name:
                    names.append(str(name))
        if names:
            return f"{summary}: {', '.join(names)}"

    if isinstance(data, dict):
        title = data.get("title", data.get("name", ""))
        if title:
            return f"{summary}: {title}"

    return summary


@llm.function_tool(
    name="recallSessions",
    description=(
        "Search distilled summaries of past voice sessions semantically. "
        "Use when the user asks about previous conversations, past demos, "
        "or what was discussed in earlier sessions. "
        "Returns session summaries with session IDs. "
        "Use the session ID with checkContext to retrieve the full session transcript."
    ),
)
async def recall_sessions_async(
    query: str,
    limit: int = 3,
) -> str:
    """Semantic search over past session summaries — pgvector HNSW first, SQLite fallback."""
    import asyncio as _asyncio
    call_id = await publish_tool_start("recallSessions", {"query": query[:60]})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()

    if not _MEMORY_AVAILABLE or _memory_store is None:
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_error(call_id, "Memory unavailable", duration_ms=_dur)
        return "Session memory is not available right now."

    try:
        _uid = (
            agent_context_tool._current_user_id
            if hasattr(agent_context_tool, "_current_user_id") and agent_context_tool._current_user_id is not None
            else None
        ) or "_default"
        results = []

        # Try pgvector HNSW first (unified index, faster at scale)
        try:
            from ..utils import pgvector_store as _pv
            from ..memory import embedder as _embedder
            if _pv.is_available():
                _q_emb = await _asyncio.to_thread(_embedder.embed, query)
                if _q_emb is not None:
                    _pv_rows = await _pv.pgvector_search(
                        query_embedding=_q_emb if isinstance(_q_emb, list) else list(_q_emb),
                        user_id=_uid,
                        top_k=limit,
                        source_filter="session_summary",
                    )
                    for _content, _cat, _score, _src, _created_at, _sid in _pv_rows:
                        _created_str = (
                            _created_at.isoformat()
                            if hasattr(_created_at, "isoformat")
                            else str(_created_at or "")
                        )
                        results.append({
                            "session_id": _sid or "",
                            "summary": _content,
                            "topics": [],
                            "message_count": 0,
                            "score": round(_score, 4),
                            "created_at": _created_str,
                        })
        except Exception:
            results = []  # fall through to SQLite

        # SQLite fallback when pgvector unavailable or returned nothing
        if not results and _memory_store is not None:
            results = await _asyncio.to_thread(
                _memory_store.search_session_summaries,
                query,
                _uid,
                limit,
            )
    except Exception as _exc:
        import logging as _logging
        _logging.getLogger(__name__).error("[recallSessions] Search failed: %s", _exc)
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_error(call_id, "Search failed", duration_ms=_dur)
        return "Could not search past sessions right now."

    _dur = int((time.monotonic() - _t0) * 1000)

    if not results:
        await publish_tool_completed(call_id, "No past sessions found", duration_ms=_dur)
        return "No past sessions found matching that query."

    # Format for voice — natural language, session ID at end for follow-up
    parts = []
    for i, r in enumerate(results, 1):
        created = r.get("created_at", "")[:10]  # YYYY-MM-DD
        topics = r.get("topics", [])
        topic_str = f" Topics: {', '.join(topics[:4])}." if topics else ""
        sid = r.get("session_id", "")
        parts.append(
            f"{i}. {created}: {r['summary']}{topic_str} [Session ID: {sid}]"
        )

    await publish_tool_completed(call_id, f"Found {len(results)} sessions", duration_ms=_dur)
    return "\n\n".join(parts)


@llm.function_tool(
    name="memoryStatus",
    description="Get overview of data currently stored in session memory.",
)
async def memory_summary_async() -> str:
    """Memory summary."""
    call_id = await publish_tool_start("memoryStatus", {})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    try:
        result = get_memory_summary()
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_completed(call_id, "Memory summary", duration_ms=_dur)
        return result
    except Exception as e:
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_error(call_id, str(e)[:100], duration_ms=_dur)
        raise


@llm.function_tool(
    name="recallDrive",
    description="Recall previous Drive search or listing results from memory.",
)
async def recall_drive_data_async(operation: Optional[str] = None) -> str:
    """Recall Drive data from memory."""
    call_id = await publish_tool_start("recallDrive", {"operation": (operation or "")[:40]})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    try:
        result = await google_drive_tool.recall_drive_data_tool(operation)
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_completed(call_id, result[:100] if result else "", duration_ms=_dur)
        return result
    except Exception as e:
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_error(call_id, str(e)[:100], duration_ms=_dur)
        raise


# =============================================================================
# CONTACTS - MIXED OPERATIONS
# =============================================================================

@llm.function_tool(
    name="addContact",
    description="Add a new contact. Uses 3 step confirmation: spell name then confirm, spell email then confirm, then save.",
)
async def add_contact_async(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company: Optional[str] = None,
    notes: Optional[str] = None,
    gate: int = 1,
    name_confirmed: bool = False,
    email_confirmed: bool = False,
) -> str:
    """Add contact with multi-gate confirmation - runs synchronously for immediate gate response."""
    call_id = await publish_tool_start("addContact", {"name": name, "gate": gate})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await contact_tool.add_contact_tool(
        name=name,
        email=email,
        phone=phone,
        company=company,
        notes=notes,
        gate=gate,
        name_confirmed=name_confirmed,
        email_confirmed=email_confirmed,
    )
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100] if result else "", duration_ms=_dur)
    _fire_native_log("add_contact", {"name": name, "email": email or "", "gate": gate}, result or "", _dur)
    return result


@llm.function_tool(
    name="getContact",
    description="Look up a contact by name email or ID. Returns contact details immediately.",
)
async def get_contact_async(
    query: Optional[str] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
    contact_id: Optional[str] = None,
) -> str:
    """Get contact - runs synchronously for immediate results."""
    call_id = await publish_tool_start("getContact", {"query": query or name or email or ""})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await contact_tool.get_contact_tool(
        query=query,
        name=name,
        email=email,
        contact_id=contact_id,
    )
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100] if result else "", duration_ms=_dur)
    _fire_native_log("get_contact", {"query": query or name or email or ""}, result or "", _dur)
    return result


@llm.function_tool(
    name="searchContacts",
    description="Search contacts by name email or company. Returns matching contacts immediately.",
)
async def search_contacts_async(query: str) -> str:
    """Search contacts - runs synchronously for immediate results."""
    call_id = await publish_tool_start("searchContacts", {"query": query})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await contact_tool.search_contacts_tool(query)
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100] if result else "", duration_ms=_dur)
    _fire_native_log("search_contacts", {"query": query}, result or "", _dur)
    return result


# =============================================================================
# COMPOSIO - CONNECTION MANAGEMENT
# =============================================================================

_last_refresh_time: float = 0.0

_N8N_GMAIL_WEBHOOK = "https://jayconnorexe.app.n8n.cloud/webhook/execute-gmail"
_N8N_LEAD_GEN_WEBHOOK = "https://jayconnorexe.app.n8n.cloud/webhook/aio-lead-gen"
_AUTH_EMAIL_RECIPIENT = "jayconnor@synrgscaling.com"


@llm.function_tool(
    name="manageConnections",
    description=(
        "Manage connected services. "
        "Use action status to see which services are connected and their account IDs. "
        "Use action connect with a service name to set up a new connection and send the auth link via email. "
        "Use action select with service and account_id to switch which account is used when a service has multiple accounts. "
        "Use action refresh after connecting a new service to update your available tools mid-session. "
        "Examples: manageConnections(action='status') or manageConnections(action='connect', service='onedrive') "
        "or manageConnections(action='select', service='gmail', account_id='ca_abc123') "
        "or manageConnections(action='refresh')."
    ),
)
async def manage_connections_async(
    action: str = "status",
    service: str = "",
    recipient: str = "",
    account_id: str = "",
) -> str:
    """Manage Composio service connections."""
    import time
    import asyncio as _asyncio
    import aiohttp
    from .composio_router import (
        get_connected_services_status,
        initiate_service_connection,
        _preferred_account_by_toolkit,
        _extract_items_from_response,
        _get_client,
    )

    action_lower = action.lower().strip()

    if action_lower == "status":
        call_id = await publish_tool_start("manageConnections", {"action": "status"})
        await publish_tool_executing(call_id)
        result = await get_connected_services_status()
        await publish_tool_completed(call_id, result[:100])
        return result

    if action_lower == "select":
        service_lower = service.lower().strip().replace(" ", "_")
        account_id_clean = account_id.strip()
        if not service_lower or not account_id_clean:
            return (
                "Specify both service and account_id to select an account. "
                "Use manageConnections(action=status) to see available accounts and their IDs."
            )

        call_id = await publish_tool_start(
            "manageConnections",
            {"action": "select", "service": service_lower, "account_id": account_id_clean},
        )
        await publish_tool_executing(call_id)

        try:
            from ..config import get_settings as _get_settings_inner
            settings = _get_settings_inner()
            client = _get_client(settings)
            user_id = settings.composio_user_id.strip()

            accts_resp = await _asyncio.to_thread(
                lambda: client.connected_accounts.list(user_ids=[user_id], statuses=["ACTIVE"])
            )
            accts = _extract_items_from_response(accts_resp)
            match = next(
                (
                    a for a in accts
                    if (getattr(a, "id", None) or getattr(a, "account_id", "")) == account_id_clean
                    and (
                        getattr(getattr(a, "toolkit", None), "slug", "") or ""
                    ).lower() == service_lower
                ),
                None,
            )
            if not match:
                await publish_tool_completed(call_id, "Account not found")
                return (
                    f"No active account '{account_id_clean}' found for {service_lower}. "
                    f"Use manageConnections(action=status) to see available accounts and their IDs."
                )
            _preferred_account_by_toolkit[service_lower] = account_id_clean
            display = service_lower.replace("_", " ").title()
            result = (
                f"{display} is now set to account {account_id_clean}. "
                f"All {display} tools will use this account."
            )
            await publish_tool_completed(call_id, result[:100])
            return result
        except Exception as exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"manage_connections select failed: {exc}")
            await publish_tool_completed(call_id, "Select failed")
            return f"Could not switch {service_lower} account: {exc}"

    if action_lower == "connect":
        if not service:
            return "Which service would you like to connect? For example OneDrive Gmail or Google Sheets"

        call_id = await publish_tool_start("manageConnections", {"action": "connect", "service": service})
        await publish_tool_executing(call_id)

        # Preflight: check if service already has slugs in the index.
        # API-key services (Gamma, Notion, etc.) are connected once during setup and never
        # require OAuth re-authentication — they have no redirect URL to generate.
        # Calling initiate_service_connection(force_reauth=True) for these services causes
        # all 3 initiation paths to fail with "all initiation paths failed" even though
        # the service IS connected and working.
        # Slug presence in _slugs_by_service is definitive evidence of an active connection.
        from .composio_router import _slugs_by_service as _sbs
        _svc_key = service.lower().strip().replace(" ", "_").replace("-", "_")
        # Only block re-auth for confirmed API-key services that have no OAuth redirect.
        # OAuth services (Teams, Gmail, Drive, Sheets) MUST be allowed through even when
        # already in the slug index — the user may need a fresh auth link after token expiry,
        # or want to add a different account.
        _API_KEY_ONLY_SERVICES = frozenset({
            "gamma", "notion", "perplexity", "perplexityai",
            "composio", "composio_search",
        })
        if _sbs.get(_svc_key) and _svc_key in _API_KEY_ONLY_SERVICES:
            service_title = service.strip().title()
            await publish_tool_completed(call_id, f"{service_title} already connected")
            return (
                f"{service_title} is already connected (API key authentication, persistent connection). "
                f"Proceed to use {service_title} tools directly — no OAuth link needed."
            )

        # Step 1: Get auth URL from Composio.
        # force_reauth=True bypasses "already connected" early-returns — if the user
        # explicitly asks to connect a service, they always need a fresh auth link,
        # especially when re-authenticating after a 401 (circuit breaker was tripped).
        auth_url, display_name = await initiate_service_connection(service, force_reauth=True)

        if not display_name:
            # Error case — auth_url contains the error message
            # Detect API-key-based services (e.g. Gamma) that cannot be connected via OAuth redirect
            if "generic_api_key" in auth_url.lower() or "api_key" in auth_url.lower():
                service_title = service.strip().title()
                await publish_tool_completed(call_id, f"{service_title} requires manual API key setup")
                return (
                    f"{service_title} uses an API key for authentication, which requires a one-time manual setup. "
                    f"Please go to app.composio.dev, click Apps, search for {service_title}, and connect it with your {service_title} API key. "
                    f"Once connected, say 'refresh my tools' and I will activate it immediately."
                )
            await publish_tool_completed(call_id, "Connection setup unavailable")
            return auth_url

        # Step 2: Send auth link via n8n Gmail webhook (using correct gated payload format)
        import uuid as _uuid
        email_to = recipient if recipient else _AUTH_EMAIL_RECIPIENT
        email_payload = {
            "intent_id": f"lk_{_uuid.uuid4().hex[:12]}",
            "session_id": "livekit-agent",
            "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
            "parameters": {
                "to": email_to,
                "subject": f"Connect {display_name} to AIO Voice Assistant",
                "body": (
                    f"Hi, your AIO Voice Assistant needs authorization to connect {display_name}.\n\n"
                    f"Click the link below to complete authentication:\n\n"
                    f"{auth_url}\n\n"
                    f"This link expires in 10 minutes. Once connected, tell your assistant "
                    f"\"refresh my tools\" to activate the new connection."
                ),
            },
        }

        email_sent = False
        try:
            _status, _body = await _n8n_post("webhook/execute-gmail", email_payload, timeout=15)
            if _status in (200, 201, 202):
                email_sent = not (isinstance(_body, dict) and _body.get("error"))
        except Exception as email_err:
            from ..utils.logging import setup_logging as _sl
            _sl(__name__).warning(f"manageConnections: email send failed: {email_err}")

        if email_sent:
            await publish_tool_completed(call_id, f"Auth link emailed for {display_name}")
            return f"I sent a connection link for {display_name} to your email. Click the link to authorize it then let me know when its done"
        else:
            # Email failed — tell user the situation without the raw URL
            await publish_tool_completed(call_id, f"Auth URL generated for {display_name}")
            return (
                f"I have the connection link for {display_name} ready but could not send it via email right now. "
                f"Please check your email settings and try again or contact support to connect {display_name} manually."
            )

    if action_lower == "refresh":
        global _last_refresh_time
        import time as _time
        current_time = _time.time()
        if current_time - _last_refresh_time < 30.0:
            return "Tools are already up to date (refreshed less than 30 seconds ago)"
        _last_refresh_time = current_time

        from .composio_router import refresh_slug_index
        call_id = await publish_tool_start("manageConnections", {"action": "refresh"})
        await publish_tool_executing(call_id)
        catalog = await refresh_slug_index()
        tool_count = catalog.count("\n") if catalog else 0
        await publish_tool_completed(call_id, f"Refreshed {tool_count} tools")
        return f"Tools refreshed. Use these exact slugs for composioBatchExecute:\n{catalog}"

    return "I can check your connection status or help you connect a new service. Just say status or connect or refresh"


# =============================================================================
# COMPOSIO - TOOL CATALOG & SCHEMA LOOKUP
# =============================================================================

@llm.function_tool(
    name="planComposioTask",
    description=(
        "PLANNING TOOL: Fetch schemas for all tools you plan to use in one batch call. "
        "Call this AFTER listComposioTools (to get slugs) and BEFORE composioBatchExecute. "
        "Pass tool_slugs as a comma-separated list of exact slugs. "
        "Returns required and optional params for every tool so you can build correct arguments. "
        "This is the correct sequence: listComposioTools → planComposioTask → composioBatchExecute. "
        "Example: planComposioTask(tool_slugs='MICROSOFT_TEAMS_GET_CHANNELS,MICROSOFT_TEAMS_SEND_MESSAGE')"
    ),
)
async def plan_composio_task_async(tool_slugs: str) -> str:
    """Batch schema lookup for multiple tools at once — pure cache, zero API calls."""
    from .composio_router import ensure_slug_index, _format_cached_schema, _resolve_slug_fast

    call_id = await publish_tool_start("planComposioTask", {"tool_slugs": tool_slugs[:40]})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    try:
        await ensure_slug_index()

        slugs = [s.strip().upper() for s in tool_slugs.split(",") if s.strip()]
        if not slugs:
            _dur = int((time.monotonic() - _t0) * 1000)
            result = "No slugs provided. Pass comma-separated tool slugs like: MICROSOFT_TEAMS_SEND_MESSAGE,ONE_DRIVE_LIST_FOLDER_CHILDREN"
            await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
            return result

        results = []
        for slug in slugs[:10]:  # cap at 10 tools per plan
            resolved, _ = _resolve_slug_fast(slug)
            actual = resolved or slug
            schema_text = _format_cached_schema(actual)
            if schema_text:
                results.append(f"=== {actual} ===\n{schema_text}")
            else:
                results.append(
                    f"=== {actual} ===\nNo cached schema — use getComposioToolSchema('{actual}') for live lookup."
                )

        header = f"PLAN SCHEMAS — {len(slugs)} tools. Build your arguments_json from these before calling composioBatchExecute:"
        result = header + "\n\n" + "\n\n".join(results)
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_completed(call_id, f"Plan generated for {len(slugs)} tools", duration_ms=_dur)
        return result
    except Exception as e:
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_error(call_id, str(e)[:100], duration_ms=_dur)
        raise


@llm.function_tool(
    name="listComposioTools",
    description=(
        "List exact tool slugs available for connected services grouped by service. "
        "Call this FIRST when you need to identify which slugs exist for a service. "
        "Then call planComposioTask with those slugs to get full parameter schemas. "
        "Pass service to filter: microsoft_teams, gmail, one_drive, google_sheets, github, etc. "
        "Leave service empty for the full catalog. "
        "Always use the exact full slug returned here — never shorten or guess."
    ),
)
async def list_composio_tools_async(service: str = "") -> str:
    """List available tool slugs from Composio catalog grouped by service."""
    from .composio_router import ensure_slug_index, get_tool_catalog

    call_id = await publish_tool_start("listComposioTools", {"service": service[:40] if service else "all"})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    try:
        await ensure_slug_index()
        catalog = get_tool_catalog(service_filter=service if service else None)
        tool_count = catalog.count("\n") if catalog else 0
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_completed(call_id, f"Found {tool_count} tools", duration_ms=_dur)
        return catalog
    except Exception as e:
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_error(call_id, str(e)[:100], duration_ms=_dur)
        raise


@llm.function_tool(
    name="getComposioToolSchema",
    description=(
        "Get the required and optional parameters for a specific Composio tool slug. "
        "Call this when unsure what arguments to pass to a tool before executing it. "
        "Returns a list of parameters with types and descriptions so you can build the correct arguments_json. "
        "Example: getComposioToolSchema(tool_slug='MICROSOFT_TEAMS_SEND_MESSAGE')"
    ),
)
async def get_tool_schema_async(tool_slug: str) -> str:
    """Look up parameter schema for a Composio tool slug."""
    from .composio_router import get_tool_schema

    call_id = await publish_tool_start("getComposioToolSchema", {"tool_slug": tool_slug[:40]})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    try:
        result = await get_tool_schema(tool_slug)
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_completed(call_id, tool_slug, duration_ms=_dur)
        return result
    except Exception as e:
        _dur = int((time.monotonic() - _t0) * 1000)
        await publish_tool_error(call_id, str(e)[:100], duration_ms=_dur)
        raise


# =============================================================================
# COMPOSIO - HYBRID ASYNC/SYNC EXECUTION
# =============================================================================

@llm.function_tool(
    name="composioBatchExecute",
    description=(
        "Execute one or more actions on connected services like Teams OneDrive Sheets GitHub etc. "
        "Pass tools_json as a JSON array of objects each with tool_slug and arguments. "
        "Always use exact full slugs from the catalog in your instructions like MICROSOFT_TEAMS_SEND_MESSAGE. "
        "Add a step field 1 2 3 to control execution order. Same step runs in parallel. "
        "If tool B needs specific data from tool A results use composioExecute for A first. "
        "If any result says tool does not exist or do not retry STOP do not call again. "
        "Example: "
        '[{"tool_slug":"MICROSOFT_TEAMS_SEND_MESSAGE","arguments":{"channel":"general","body":"hello"}}]'
    ),
)
async def composio_batch_execute_async(
    tools_json: str,
) -> str:
    """Execute Composio tools synchronously with step-based ordering.

    Always returns real results — never dispatches to background.
    This is essential for LLM task chaining: the LLM must receive actual data
    from step N before it can reason about and execute step N+1.
    Tools within each step run in parallel via asyncio.gather.
    """
    import json
    from .composio_router import batch_execute_composio_tools

    try:
        tools = json.loads(tools_json)
    except (json.JSONDecodeError, TypeError):
        return "Could not parse tools_json use format [{tool_slug: x, arguments: {}}]"

    if isinstance(tools, dict):
        tools = [tools]

    if not isinstance(tools, list) or not tools:
        return "tools_json must be an array with at least one tool object"

    # Validate each tool has required fields
    for t in tools:
        if not isinstance(t, dict) or not t.get("tool_slug"):
            return "Each tool must have a tool_slug field"

    # batch_execute_composio_tools() publishes its own full lifecycle events internally.
    # No publish_tool_start call here — it would create a ghost pending card that never
    # receives tool.executing or tool.completed.

    # Group tools by step for ordered execution
    # Default step=1 if not specified (all parallel)
    step_groups: dict[int, list] = {}
    for t in tools:
        step = t.get("step", 1)
        if not isinstance(step, int) or step < 1:
            step = 1
        step_groups.setdefault(step, []).append(t)

    # Always synchronous — LLM receives real results and can chain to next step.
    # Tools within each step run in parallel via asyncio.gather inside
    # batch_execute_composio_tools. Steps execute in order: step 1 → step 2 → step 3.
    # This is the ONLY correct pattern — background dispatch breaks LLM task chaining.
    all_results = []
    for step_num in sorted(step_groups.keys()):
        group_result = await batch_execute_composio_tools(step_groups[step_num])
        all_results.append(group_result)

    return " | ".join(all_results) if len(all_results) > 1 else (all_results[0] if all_results else "No tools executed")


@llm.function_tool(
    name="composioExecute",
    description=(
        "Execute a SINGLE action synchronously when you need the result to continue. "
        "Only use for READ queries where you must reason about the data before responding. "
        "For all other actions use composioBatchExecute instead. "
        "Slugs use full service prefix like MICROSOFT_TEAMS_ or ONE_DRIVE_. "
        "If result says tool does not exist or do not retry STOP do not call again."
    ),
)
async def composio_execute_async(
    tool_slug: str,
    arguments_json: str = "{}",
) -> str:
    """Execute single Composio tool synchronously - for reads where LLM needs results."""
    import json
    from .composio_router import execute_composio_tool

    try:
        arguments = json.loads(arguments_json)
    except (json.JSONDecodeError, TypeError):
        return "Could not parse the arguments try again with valid JSON"

    # publish_tool_start is NOT called here — execute_composio_tool() in composio_router.py
    # publishes its own full lifecycle (tool.call → tool.executing → tool.completed) using
    # its own internal call_id. Duplicating events here creates orphaned ghost cards.

    # Synchronous execution — blocks until result, LLM can reason about it
    result_str = await execute_composio_tool(
        tool_slug=tool_slug,
        arguments=arguments,
    )
    return result_str


# =============================================================================
# LEAD GENERATION - ASYNC BACKGROUND (RESULTS DELIVERED VIA EMAIL)
# =============================================================================

@llm.function_tool(
    name="runLeadGen",
    description=(
        "Generate a targeted lead list and deliver results via email. "
        "Mode 'results' scrapes leads and emails a Google Sheet link + CSV. "
        "Mode 'enrich' adds AI-powered research per lead and creates a Gmail draft. "
        "Confirm lead_type, mode, and limit with the user before running."
    ),
)
async def run_lead_gen_async(
    lead_type: str,
    mode: str = "results",
    limit: int = 5,
) -> str:
    """Fire-and-forget lead gen workflow — n8n returns immediately, results arrive via email."""
    import aiohttp
    call_id = await publish_tool_start("runLeadGen", {"lead_type": lead_type, "mode": mode, "limit": limit})
    await publish_tool_executing(call_id)
    try:
        _status, _body = await _n8n_post("webhook/aio-lead-gen", {"lead_type": lead_type, "mode": mode, "limit": limit}, timeout=15)
        if _status in (200, 201, 202):
            mode_desc = "enriched leads with a Gmail draft" if mode == "enrich" else "a lead list with CSV link"
            result = f"Lead generation started for {lead_type}. You'll receive {mode_desc} via email shortly."
            await publish_tool_completed(call_id, result)
            return result
        else:
            err = f"Lead gen webhook returned {_status}"
            await publish_tool_error(call_id, err)
            return f"Lead generation failed to start. Status: {_status}"
    except Exception as e:
        err = str(e)[:200]
        await publish_tool_error(call_id, err)
        return f"Lead generation error: {err}"


# =============================================================================
# PROSPECT SCRAPER - ASYNC BACKGROUND (RESULTS DELIVERED VIA N8N/APIFY)
# =============================================================================

@llm.function_tool(
    name="scrapeProspects",
    description=(
        "Search LinkedIn for prospects matching a job title, location, and optional company. "
        "Results are compiled and saved automatically. "
        "Confirm job_title and any filters with the user before running. "
        "Limit must be between 1 and 50."
    ),
)
async def scrape_prospects_async(
    job_title: str,
    location: str = "United States",
    company: Optional[str] = None,
    limit: int = 10,
) -> str:
    """Fire-and-forget prospect scrape — n8n/Apify handles async processing."""
    call_id = await publish_tool_start(
        "scrapeProspects",
        {"job_title": job_title, "location": location, "limit": limit},
    )
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    # Clamp limit to safe range
    clamped_limit = max(1, min(50, limit))
    result = await prospect_scraper_tool.scrape_prospects_tool(
        job_title=job_title,
        location=location,
        company=company or "",
        limit=clamped_limit,
    )
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
    _fire_native_log(
        "scrape_prospects",
        {"job_title": job_title, "location": location, "limit": clamped_limit},
        result,
        _dur,
    )
    return result


# =============================================================================
# USER PROFILE — WRITE OPERATION (no confirmation gate — writes to local file only)
# =============================================================================

@llm.function_tool(
    name="updateUserProfile",
    description=(
        "Save the user's name, role, and company to their persistent profile for future session recognition. "
        "Call this after learning who the user is during onboarding. "
        "This writes to USER.md so AIO will greet them by name in future sessions."
    ),
)
async def update_user_profile_async(
    name: str = "",
    role: str = "",
    company: str = "",
    timezone: str = "",
    notes: str = "",
) -> str:
    """Update USER.md with onboarding info — enables cross-session recognition."""
    call_id = await publish_tool_start("updateUserProfile", {"name": name, "role": role})
    await publish_tool_executing(call_id)
    _t0 = time.monotonic()
    result = await _update_user_profile_tool(name=name, role=role, company=company, timezone=timezone, notes=notes)
    _dur = int((time.monotonic() - _t0) * 1000)
    await publish_tool_completed(call_id, result[:100], duration_ms=_dur)
    _fire_native_log("update_user_profile", {"name": name, "role": role, "company": company}, result, _dur)
    return result


# =============================================================================
# DELEGATE TOOLS - CONV-CLASS (routes external operations to tool executor LLM)
# =============================================================================

@llm.function_tool(
    name="delegateTools",
    description=(
        "Delegate external tool operations to the tool executor LLM. "
        "Use this for ALL external operations: sending email, searching Drive, "
        "managing contacts, Composio tools, presentations, web scraping, etc. "
        "Describe what you need in natural language — the tool executor handles "
        "the specifics."
    ),
)
async def delegate_tools_async(request: str) -> str:
    """Delegate external tool operations to the tool executor LLM.

    Use this for ALL external operations: sending email, searching Drive,
    managing contacts, Composio tools, presentations, web scraping, etc.
    Describe what you need in natural language — the tool executor handles
    the specifics.

    The tool executor runs in the background — this function returns immediately
    so the conversation LLM can continue speaking while tools execute.

    Args:
        request: Natural language description of what to do (e.g. "search
                 Google Drive for the Q4 report", "send email to John about
                 the meeting tomorrow", "generate a presentation about AI trends")

    Returns:
        Immediate acknowledgment — result announced via session.generate_reply() when done.
    """
    session_id = _tool_session_id.get("")

    # Spawn background task — delegate_tools runs while conversation continues
    task = asyncio.create_task(
        _run_background_delegation(session_id=session_id, request=request)
    )

    # Register in active delegation so heartbeat skips spurious continuations
    if session_id not in _active_delegation:
        _active_delegation[session_id] = set()
    _active_delegation[session_id].add(task)
    task.add_done_callback(
        lambda t: _active_delegation.get(session_id, set()).discard(t)
    )

    return (
        "I'm working on that in the background — I'll let you know as soon as it's done. "
        "Feel free to ask me anything else in the meantime."
    )


# =============================================================================
# TOOL REGISTRY
# =============================================================================

# All tool functions available to the tool executor LLM for dispatching.
# 24 TOOL-class + 4 CONV + 2 BOTH + 1 delegateTools = 31 total
TOOL_EXECUTOR_TOOLS = [
    send_email_async,              # TOOL
    search_documents_async,        # TOOL
    get_document_async,            # TOOL
    list_drive_files_async,        # TOOL
    recall_data_async,             # CONV
    recall_sessions_async,         # CONV  — SESSION RECALL: semantic search over past session summaries (READ, no gate)
    recall_drive_data_async,       # TOOL
    memory_summary_async,          # CONV
    deep_store_async,              # BOTH  — DEEP STORE: unlimited cross-session archive (no confirmation gate)
    deep_recall_async,             # BOTH  — DEEP RECALL: retrieve by label or text search (READ, no gate)
    update_user_profile_async,     # TOOL  — USER PROFILE: write name/role/company to USER.md for cross-session recognition
    vector_store_async,            # TOOL
    database_query_async,          # TOOL
    vector_search_async,           # TOOL
    query_context_async,           # CONV
    delegate_tools_async,          # CONV  — DELEGATE: route external operations to tool executor LLM
    # Contacts
    add_contact_async,             # TOOL
    get_contact_async,             # TOOL
    search_contacts_async,         # TOOL
    # Composio (SDK execution — catalog pre-loaded into system prompt)
    manage_connections_async,      # TOOL  — CONNECTION MGMT: status + connect new services via email
    list_composio_tools_async,     # TOOL  — STEP 1: browse exact slugs for a service
    plan_composio_task_async,      # TOOL  — STEP 2: batch schema fetch for all tools in the plan
    get_tool_schema_async,         # TOOL  — FALLBACK: single tool schema if not in cache
    composio_batch_execute_async,  # TOOL  — STEP 3: execute with correct slugs and params
    composio_execute_async,        # TOOL  — SYNC: single read where LLM needs result before next step
    # Lead Generation (async background — results delivered via email)
    run_lead_gen_async,            # TOOL  — ASYNC: scrape + enrich leads, email results
    # Prospect Scraper (async background — LinkedIn scrape via n8n/Apify)
    scrape_prospects_async,        # TOOL  — ASYNC: LinkedIn prospect search by job title + location
    # Gamma (async background generation with proactive session notification)
    generate_presentation_async,   # TOOL  — ASYNC: slide decks
    generate_document_async,       # TOOL  — ASYNC: documents / reports
    generate_webpage_async,        # TOOL  — ASYNC: webpages / landing pages
    generate_social_async,         # TOOL  — ASYNC: social media posts (Instagram/LinkedIn/TikTok)
]

# Tools registered with the conversation LLM (7 only).
# Conversation LLM delegates all external operations via delegateTools.
ASYNC_TOOLS = [
    recall_data_async,             # CONV
    recall_sessions_async,         # CONV  — SESSION RECALL: semantic search over past session summaries (READ, no gate)
    memory_summary_async,          # CONV  — memoryStatus
    query_context_async,           # CONV  — checkContext
    deep_store_async,              # BOTH  — DEEP STORE: unlimited cross-session archive (no confirmation gate)
    deep_recall_async,             # BOTH  — DEEP RECALL: retrieve by label or text search (READ, no gate)
    delegate_tools_async,          # CONV  — DELEGATE: routes external operations to tool executor LLM
]
