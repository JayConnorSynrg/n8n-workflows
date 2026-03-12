"""AIO Voice Agent — Tool Executor LLM module.

Implements the secondary Fireworks agentic loop for TOOL-class tools.
The conversation LLM delegates via delegateTools() → this module runs a
capped agentic loop (max 10 steps) and returns a result string.

Architecture:
- Never imports LiveKit @function_tool wrappers — calls underlying async functions directly.
- _composio_semaphore limits concurrent Fireworks API calls to 4 (undocumented soft limit).
- requestGate intercept: tool executor may request user confirmation before WRITE ops.
  Sentinel format: __GATE__:{json_payload}
- Context is trimmed to prevent unbounded growth inside a delegation run.
"""

import asyncio
import inspect
import json
import logging
import time
import uuid
from contextvars import ContextVar
import weakref
from typing import Any, Callable, Optional

import httpx

from ..config import get_settings
from ..prompts import TOOL_SYSTEM_PROMPT
from ..utils.session_facts import store_fact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

# Per-session message history for the tool executor LLM (NOT the conversation LLM)
_tool_session_chat_ctx: dict[str, list] = {}

# Active asyncio Tasks per session — used by heartbeat to check is_delegation_active()
_active_delegation: dict[str, set] = {}

# LiveKit AgentSession registry — keyed by session_id for background delegation callbacks
_session_registry: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
_session_delegation_locks: dict[str, asyncio.Lock] = {}

# ContextVar allowing _dispatch_tool_call to know the current session without closure
_current_session_id: ContextVar[str] = ContextVar("_current_session_id", default="")

# Fireworks undocumented ~4-request concurrent soft limit
_composio_semaphore = asyncio.Semaphore(4)

# Prefix that signals the tool executor wants a user confirmation gate
_GATE_SENTINEL = "__GATE__:"
_NO_TOOL_SENTINEL = "NO_ACTION"

# Fireworks API endpoint
_FIREWORKS_API_URL = "https://api.fireworks.ai/inference/v1/chat/completions"

# requestGate tool schema injected alongside TOOL-class schemas
_REQUEST_GATE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "requestGate",
        "description": (
            "Request user confirmation before a WRITE/DESTRUCTIVE/PAYMENT operation. "
            "Returns a gate sentinel. Always call this BEFORE any send/delete/pay action."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "gate_type": {
                    "type": "string",
                    "enum": ["WRITE", "DESTRUCTIVE", "PAYMENT"],
                },
                "content": {
                    "type": "string",
                    "description": "What will be done — shown to user",
                },
                "voice_prompt": {
                    "type": "string",
                    "description": "What AIO says to request confirmation",
                },
                "continuation_hint": {
                    "type": "string",
                    "description": "What to do after confirmation",
                },
            },
            "required": ["gate_type", "content", "voice_prompt"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool schema registry
# ---------------------------------------------------------------------------

# Manually maintained OpenAI-format schemas for all TOOL-class tools.
# Derived from reading async_wrappers.py function signatures and docstrings.
_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "sendEmail",
            "description": "Send an email. Confirm recipient, subject, and message with user first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body text"},
                    "cc": {"type": "string", "description": "CC email address (optional)"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "searchDrive",
            "description": (
                "Search Google Drive for documents by keyword or topic. "
                "NOTE: Gamma presentations are NOT in Google Drive."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getFile",
            "description": "Retrieve a specific file from Google Drive by file ID from a previous search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string", "description": "Google Drive file ID"},
                },
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listFiles",
            "description": "List recent files in Google Drive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Max results (default 10)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recallDrive",
            "description": "Recall previous Drive search or listing results from memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "description": "Operation type filter (optional)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "knowledgeBase",
            "description": "Search or store in the knowledge base. For search execute immediately. For store confirm first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action: search, find, query, or store"},
                    "content": {"type": "string", "description": "Content or search query"},
                    "category": {"type": "string", "description": "Category for storage (optional)"},
                },
                "required": ["action", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "queryDatabase",
            "description": (
                "Semantic vector search over the Auto Pay Plus candidate database. "
                "Use for candidates, applicants, hiring records. Execute immediately — no confirmation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vectorSearch",
            "description": "Search the knowledge base for information. Returns ranked results by relevance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "addContact",
            "description": "Add a new contact. Uses 3-step confirmation: spell name, spell email, then save.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Contact name"},
                    "email": {"type": "string", "description": "Email address (optional)"},
                    "phone": {"type": "string", "description": "Phone number (optional)"},
                    "company": {"type": "string", "description": "Company name (optional)"},
                    "notes": {"type": "string", "description": "Additional notes (optional)"},
                    "gate": {"type": "integer", "description": "Gate step (1, 2, or 3)"},
                    "name_confirmed": {"type": "boolean", "description": "Name confirmed by user"},
                    "email_confirmed": {"type": "boolean", "description": "Email confirmed by user"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getContact",
            "description": "Look up a contact by name, email, or ID. Returns contact details immediately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "General search query"},
                    "name": {"type": "string", "description": "Contact name"},
                    "email": {"type": "string", "description": "Contact email"},
                    "contact_id": {"type": "string", "description": "Contact ID"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "searchContacts",
            "description": "Search contacts by name, email, or company. Returns matching contacts immediately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "manageConnections",
            "description": (
                "Manage connected services. "
                "action=status: see which services are connected. "
                "action=connect: set up a new connection. "
                "action=select: switch active account. "
                "action=refresh: update available tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "status, connect, select, or refresh"},
                    "service": {"type": "string", "description": "Service name (for connect/select)"},
                    "recipient": {"type": "string", "description": "Email recipient for auth link"},
                    "account_id": {"type": "string", "description": "Account ID (for select)"},
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "listComposioTools",
            "description": (
                "List exact tool slugs available for connected services grouped by service. "
                "Call FIRST when identifying which slugs exist for a service."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service filter (optional, e.g. microsoft_teams)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planComposioTask",
            "description": (
                "Fetch schemas for all tools you plan to use in one batch. "
                "Call AFTER listComposioTools and BEFORE composioBatchExecute."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_slugs": {"type": "string", "description": "Comma-separated list of exact slugs"},
                },
                "required": ["tool_slugs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "getComposioToolSchema",
            "description": "Get required and optional parameters for a specific Composio tool slug.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_slug": {"type": "string", "description": "Exact Composio tool slug"},
                },
                "required": ["tool_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "composioBatchExecute",
            "description": (
                "Execute one or more actions on connected services. "
                "Pass tools_json as a JSON array with tool_slug and arguments. "
                "Add step field to control execution order."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tools_json": {
                        "type": "string",
                        "description": 'JSON array: [{"tool_slug":"X","arguments":{...}}]',
                    },
                },
                "required": ["tools_json"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "composioExecute",
            "description": (
                "Execute a SINGLE action synchronously when you need the result to continue. "
                "Only use for READ queries. For all other actions use composioBatchExecute."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_slug": {"type": "string", "description": "Exact Composio tool slug"},
                    "arguments_json": {"type": "string", "description": "JSON object of arguments"},
                },
                "required": ["tool_slug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "runLeadGen",
            "description": (
                "Generate a targeted lead list and deliver results via email. "
                "Confirm lead_type, mode, and limit with user before running."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lead_type": {"type": "string", "description": "Type of leads to generate"},
                    "mode": {"type": "string", "description": "results or enrich (default: results)"},
                    "limit": {"type": "integer", "description": "Max leads (default: 5)"},
                },
                "required": ["lead_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scrapeProspects",
            "description": (
                "Search LinkedIn for prospects matching a job title, location, and optional company. "
                "Confirm job_title and filters before running."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "job_title": {"type": "string", "description": "Target job title"},
                    "location": {"type": "string", "description": "Location (default: United States)"},
                    "company": {"type": "string", "description": "Company filter (optional)"},
                    "limit": {"type": "integer", "description": "Max results 1-50 (default: 10)"},
                },
                "required": ["job_title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generatePresentation",
            "description": "Generate a Gamma AI slide deck or presentation on any topic. Runs in background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Presentation topic"},
                    "slide_count": {"type": "integer", "description": "Number of slides (default: 10)"},
                    "tone": {"type": "string", "description": "Tone, e.g. professional (default: professional)"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generateDocument",
            "description": "Generate a Gamma AI document or report on any topic. Runs in background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Document topic"},
                    "tone": {"type": "string", "description": "Tone (default: professional)"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generateWebpage",
            "description": "Generate a Gamma AI webpage or landing page on any topic. Runs in background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Webpage topic"},
                    "tone": {"type": "string", "description": "Tone (default: professional)"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generateSocial",
            "description": "Generate Gamma AI social media posts. Runs in background.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Social content topic"},
                    "platform": {"type": "string", "description": "Platform: instagram, linkedin, tiktok"},
                    "tone": {"type": "string", "description": "Tone (default: engaging)"},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "updateUserProfile",
            "description": (
                "Save the user's name, role, and company to their persistent profile. "
                "Call after learning who the user is during onboarding."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "User's name"},
                    "role": {"type": "string", "description": "User's role or job title"},
                    "company": {"type": "string", "description": "User's company"},
                    "timezone": {"type": "string", "description": "User's timezone"},
                    "notes": {"type": "string", "description": "Additional notes"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deepStore",
            "description": (
                "Permanently save important content, facts, or preferences to the user's database. "
                "Call when user asks to remember, save, note, keep, or store any information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to store"},
                    "label": {"type": "string", "description": "Short descriptive label"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deepRecall",
            "description": (
                "Retrieve content previously saved with deepStore. "
                "Use label for specific item by name, or query to search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Full-text search query"},
                    "label": {"type": "string", "description": "Exact label to retrieve"},
                },
                "required": [],
            },
        },
    },
]

# All tool schemas including requestGate
_ALL_TOOL_SCHEMAS: list[dict] = _TOOL_SCHEMAS + [_REQUEST_GATE_SCHEMA]


# ---------------------------------------------------------------------------
# Public interface: is_delegation_active / get_active_delegation
# ---------------------------------------------------------------------------

def is_delegation_active(session_id: str) -> bool:
    """Return True if a delegation task is currently running for this session."""
    tasks = _active_delegation.get(session_id, set())
    return bool(tasks)


def get_active_delegation(session_id: str) -> set:
    """Return the set of active asyncio Tasks for this session."""
    return _active_delegation.get(session_id, set())


def register_session(session_id: str, session: Any) -> None:
    """Register a LiveKit AgentSession for background delegation callbacks."""
    _session_registry[session_id] = session


def unregister_session(session_id: str) -> None:
    """Remove a session from the registry when it ends."""
    _session_registry.pop(session_id, None)


async def run_background_delegation(session_id: str, request: str, context_hints: dict | None = None) -> None:
    """Run tool delegation as a background task and announce completion via session.generate_reply().

    Allows delegate_tools_async to return immediately while Fireworks + Composio
    execute asynchronously. When delegation completes, the registered session
    generates a reply to announce the result conversationally.

    P0-2: session fetched AFTER await to avoid stale reference.
    P0-1: Gamma results suppressed — _gamma_notification_monitor owns Gamma announcements.
    P1-1: per-session lock prevents concurrent generate_reply calls.
    P1-2: context_hints passed through so user_id reaches Composio entity resolution.
    P3-1: outer 300s timeout prevents infinite hang.
    """
    if context_hints is None:
        context_hints = {}
    result: str = ""
    try:
        result = await asyncio.wait_for(
            delegate_tools(
                session_id=session_id,
                request=request,
                context_hints=context_hints,
                say_callback=None,
                task_tracker=None,
                pg_logger_module=None,
            ),
            timeout=300.0,
        )
        # P0-2: Re-fetch session after the long-running await — avoids stale reference
        session = _session_registry.get(session_id)
        # P0-1: Gamma has its own _gamma_notification_monitor — skip generate_reply to avoid double-announcement
        # Also suppress CB_TRIPPED results — conversation LLM handles auth errors naturally
        _is_cb_result = "do not retry" in result or "needs to be re-authenticated" in result or "needs to be re-authorized" in result
        if session and not result.startswith("Gamma presentation ready:") and not _is_cb_result:
            _lock = _session_delegation_locks.setdefault(session_id, asyncio.Lock())
            async with _lock:
                try:
                    instructions = (
                        f"Background tool execution completed. Result: {result[:500]}. "
                        "Announce this conversationally and concisely to the user. "
                        "Do NOT repeat any prior response — only announce the result."
                    )
                    await session.generate_reply(instructions=instructions)
                except Exception as announce_err:
                    logger.warning(f"[bg_delegation] generate_reply failed session={session_id}: {announce_err}")
    except asyncio.TimeoutError:
        logger.error(f"[bg_delegation] Delegation timed out after 300s session={session_id}")
        session = _session_registry.get(session_id)
        if session:
            try:
                await session.generate_reply(
                    instructions="A background tool operation timed out. Apologize briefly and offer to retry."
                )
            except Exception:
                pass
    except asyncio.CancelledError:
        logger.info(f"[bg_delegation] Task cancelled session={session_id}")
    except Exception as e:
        logger.error(f"[bg_delegation] Delegation failed session={session_id}: {e}")
        session = _session_registry.get(session_id)
        if session:
            try:
                await session.generate_reply(
                    instructions="A background tool operation encountered an error. Apologize briefly and offer to retry."
                )
            except Exception:
                pass


async def evaluate_and_execute_from_speech(
    transcript: str,
    session_id: str,
    context_hints: dict | None = None,
    recent_context: list[str] | None = None,
) -> None:
    """Parallel tool track — evaluates raw user speech and executes tools if actionable.

    Fires on every valid user turn simultaneously with the conversation LLM.
    Never produces voice output directly — announces via session.generate_reply() on completion.
    Returns immediately (NO_ACTION) for purely conversational inputs.

    Args:
        transcript: Raw user speech transcription
        session_id: Current session identifier
        context_hints: Dict with user_id for Composio entity resolution
        recent_context: Last few conversation messages for reference resolution
    """
    if not transcript or len(transcript.strip().split()) < 3:
        return

    # Build request with recent conversation context for pronoun/reference resolution
    if recent_context:
        ctx_str = "\n".join(f"- {m}" for m in recent_context[-3:] if m)
        request = f"[Recent conversation]\n{ctx_str}\n\n[Current user request]\n{transcript}"
    else:
        request = transcript

    result: str = ""
    try:
        result = await asyncio.wait_for(
            delegate_tools(
                session_id=session_id,
                request=request,
                context_hints=context_hints or {},
                say_callback=None,
                task_tracker=None,
                pg_logger_module=None,
            ),
            timeout=300.0,
        )
    except asyncio.TimeoutError:
        logger.error(f"[speech_eval] Timed out after 300s session={session_id}")
        _session = _session_registry.get(session_id)
        if _session:
            try:
                await _session.generate_reply(
                    instructions="A background tool operation timed out. Apologize briefly and offer to retry."
                )
            except Exception:
                pass
        return
    except asyncio.CancelledError:
        logger.info(f"[speech_eval] Cancelled session={session_id}")
        return
    except Exception as e:
        logger.error(f"[speech_eval] Error session={session_id}: {e}")
        return

    # Purely conversational — tool LLM determined no action needed
    if not result or result.strip() == _NO_TOOL_SENTINEL:
        logger.debug(f"[speech_eval] NO_ACTION — no tool execution needed session={session_id}")
        return

    # Gamma has its own _gamma_notification_monitor — skip to avoid double-announcement
    if result.startswith("Gamma presentation ready:"):
        return

    # CB_TRIPPED or auth-expired — conversation LLM handles naturally; suppress bg announce
    if "do not retry" in result or "needs to be re-authenticated" in result or "needs to be re-authorized" in result:
        logger.debug(f"[speech_eval] CB result suppressed — conversation LLM will handle session={session_id}")
        return

    # Announce result via conversation session
    _session = _session_registry.get(session_id)
    if _session:
        _lock = _session_delegation_locks.setdefault(session_id, asyncio.Lock())
        async with _lock:
            try:
                await _session.generate_reply(
                    instructions=(
                        f"Tool execution completed. Result: {result[:500]}. "
                        "Announce this conversationally and concisely to the user. "
                        "Do NOT repeat any prior response — only announce the new result."
                    )
                )
            except Exception as _ann_err:
                logger.warning(f"[speech_eval] generate_reply failed session={session_id}: {_ann_err}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_session(session_id: str) -> None:
    """Remove all tool executor state for a session. Call on session end."""
    _tool_session_chat_ctx.pop(session_id, None)
    _active_delegation.pop(session_id, None)
    logger.debug("[tool_executor] Cleaned up session %s", session_id)


# ---------------------------------------------------------------------------
# Context trimming
# ---------------------------------------------------------------------------

def _trim_tool_context(session_id: str) -> None:
    """Trim tool context to prevent unbounded growth within a delegation run."""
    ctx = _tool_session_chat_ctx.get(session_id)
    if not ctx or len(ctx) <= 40:
        return

    before = len(ctx)

    system_msgs = [m for m in ctx if m.get("role") == "system"]
    # Never trim assistant messages that have tool_calls — they are the function call records
    asst_with_tool_calls = [
        m for m in ctx
        if m.get("role") == "assistant" and m.get("tool_calls")
    ]
    # Keep last 5 tool-result messages
    tool_results = [m for m in ctx if m.get("role") == "tool"][-5:]
    # Keep last 10 user/assistant messages without tool_calls
    other = [
        m for m in ctx
        if m.get("role") in ("user", "assistant") and not m.get("tool_calls")
    ][-10:]

    # Reconstruct preserving chronological order from the original list
    kept_set: set[int] = set()
    for i, m in enumerate(ctx):
        if m in system_msgs or m in asst_with_tool_calls or m in tool_results or m in other:
            kept_set.add(i)

    new_ctx = [m for i, m in enumerate(ctx) if i in kept_set]
    _tool_session_chat_ctx[session_id] = new_ctx

    after = len(new_ctx)
    logger.debug("[tool_executor] Trimmed context %s: %d → %d", session_id, before, after)


# ---------------------------------------------------------------------------
# Filler helpers
# ---------------------------------------------------------------------------

async def _fire_filler(say_callback: Callable) -> None:
    """Fire a filler phrase 50ms after delegation begins."""
    await asyncio.sleep(0.05)
    try:
        say_callback("One moment...")
    except Exception:
        pass


def _build_context_block(context_hints: dict) -> str:
    """Build a [Context] block string from context_hints dict."""
    parts = []
    for k in ("user_id", "last_result", "session_summary"):
        v = context_hints.get(k)
        if v:
            parts.append(f"{k}: {str(v)[:500]}")
    return ("[Context]\n" + "\n".join(parts)) if parts else ""


# ---------------------------------------------------------------------------
# requestGate: tool executor calls this before any WRITE operation
# ---------------------------------------------------------------------------

async def requestGate(
    gate_type: str,
    content: str,
    voice_prompt: str,
    continuation_hint: str = "",
) -> str:
    """Request user confirmation before a WRITE/DESTRUCTIVE/PAYMENT action.

    Returns a sentinel string the agentic loop checks for. The sentinel
    is caught in delegate_tools() which returns it upstream to the
    conversation LLM so the user is asked for confirmation.
    """
    gate_id = uuid.uuid4().hex[:8]
    session_id = _current_session_id.get("")

    gate_payload = {
        "gate_id": gate_id,
        "gate_type": gate_type,
        "content": content,
        "voice_prompt": voice_prompt,
        "continuation_hint": continuation_hint,
        "session_id": session_id,
        "timestamp": time.time(),
    }

    # Best-effort persistence to pg_logger session context
    try:
        from ..utils.pg_logger import save_session_context
        await save_session_context(
            session_id=session_id,
            context_key=f"gate:{gate_id}",
            context_value=json.dumps(gate_payload),
        )
    except Exception as exc:
        logger.debug("[tool_executor] Gate persist skipped: %s", exc)

    return f"{_GATE_SENTINEL}{json.dumps(gate_payload)}"


# ---------------------------------------------------------------------------
# Fireworks streaming call
# ---------------------------------------------------------------------------

async def _call_fireworks_streaming(
    messages: list[dict],
    tools: list[dict],
    session_id: str,
) -> dict:
    """Stream a Fireworks chat completion and return the assembled message dict.

    Returns:
        {"role": "assistant", "content": str|None, "tool_calls": [...]}

    Fireworks delivers function call arguments in fragments keyed by call_id.
    We accumulate all fragments before returning.
    """
    settings = get_settings()

    payload = {
        "model": settings.fireworks_model,
        "messages": messages,
        "tools": tools,
        "temperature": 0.3,
        "parallel_tool_calls": True,
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {settings.fireworks_api_key}",
        "Content-Type": "application/json",
    }

    content_parts: list[str] = []
    # call_id → list of arg fragments
    arg_buffer: dict[str, list[str]] = {}
    # call_id → {id, name, index}
    tool_calls_meta: dict[str, dict] = {}

    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            _FIREWORKS_API_URL,
            json=payload,
            headers=headers,
        ) as resp:
            resp.raise_for_status()
            async for raw_line in resp.aiter_lines():
                line = raw_line.strip()
                if not line:
                    continue
                if line == "data: [DONE]":
                    break
                if line.startswith("data: "):
                    line = line[6:]
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                # Accumulate content
                if delta.get("content"):
                    content_parts.append(delta["content"])

                # Accumulate tool call fragments
                for tc in delta.get("tool_calls", []):
                    # Use call id if present, otherwise fall back to index-based key
                    tc_id = tc.get("id") or f"idx_{tc.get('index', 0)}"
                    if tc_id not in arg_buffer:
                        arg_buffer[tc_id] = []
                        tool_calls_meta[tc_id] = {
                            "id": tc.get("id") or tc_id,
                            "name": "",
                            "index": tc.get("index", 0),
                        }
                    fn = tc.get("function", {})
                    if fn.get("name"):
                        tool_calls_meta[tc_id]["name"] = fn["name"]
                    if fn.get("arguments"):
                        arg_buffer[tc_id].append(fn["arguments"])

    # Assemble final tool_calls list
    assembled_tool_calls: list[dict] = []
    for tc_id, fragments in arg_buffer.items():
        raw_args = "".join(fragments)
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {"_raw": raw_args}
        meta = tool_calls_meta[tc_id]
        assembled_tool_calls.append(
            {
                "id": meta["id"],
                "type": "function",
                "function": {
                    "name": meta["name"],
                    "arguments": json.dumps(args),
                },
            }
        )

    # Sort by original index for deterministic order
    assembled_tool_calls.sort(
        key=lambda tc: tool_calls_meta.get(tc["id"], {}).get("index", 0)
    )

    return {
        "role": "assistant",
        "content": "".join(content_parts) if content_parts else None,
        "tool_calls": assembled_tool_calls,
    }


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

async def _dispatch_tool_call(
    tool_name: str,
    args: dict,
    session_id: str,
) -> Any:
    """Dispatch a tool call to the underlying async implementation.

    Calls underlying async functions directly — never the LiveKit @function_tool wrappers.
    """
    _current_session_id.set(session_id)

    # -- Lazy imports of underlying tool modules (avoids circular import at module load) --
    try:
        from . import email_tool as _email_tool
        from . import database_tool as _database_tool
        from . import vector_store_tool as _vector_store_tool
        from . import google_drive_tool as _google_drive_tool
        from . import agent_context_tool as _agent_context_tool
        from . import contact_tool as _contact_tool
        from . import prospect_scraper_tool as _prospect_scraper_tool
        from .gamma_tool import (
            generate_presentation_async,
            generate_document_async,
            generate_webpage_async,
            generate_social_async,
        )
        from .deep_store_tool import deep_store_async, deep_recall_async
        from .user_profile_tool import update_user_profile_tool as _update_user_profile_tool
        from .composio_router import (
            execute_composio_tool,
            batch_execute_composio_tools,
            ensure_slug_index,
            get_tool_catalog,
            get_tool_schema,
            get_connected_services_status,
            initiate_service_connection,
            refresh_slug_index,
            _format_cached_schema,
            _resolve_slug_fast,
        )
    except Exception as import_exc:
        logger.error("[tool_executor] Import error in _dispatch_tool_call: %s", import_exc)
        return f"Tool {tool_name} unavailable: import error — {import_exc}"

    try:
        # ----------------------------------------------------------------
        # EMAIL
        # ----------------------------------------------------------------
        if tool_name == "sendEmail":
            to = args.get("to", "")
            subject = args.get("subject", "")
            body = args.get("body", "")
            cc = args.get("cc")
            return await _email_tool.send_email_tool(to, subject, body, cc)

        # ----------------------------------------------------------------
        # GOOGLE DRIVE
        # ----------------------------------------------------------------
        elif tool_name == "searchDrive":
            return await _google_drive_tool.search_documents_tool(
                args.get("query", ""),
                args.get("max_results", 5),
            )

        elif tool_name == "getFile":
            return await _google_drive_tool.get_document_tool(args.get("file_id", ""))

        elif tool_name == "listFiles":
            return await _google_drive_tool.list_drive_files_tool(
                args.get("max_results", 10)
            )

        elif tool_name == "recallDrive":
            return await _google_drive_tool.recall_drive_data_tool(
                args.get("operation")
            )

        # ----------------------------------------------------------------
        # DATABASE / VECTOR SEARCH
        # ----------------------------------------------------------------
        elif tool_name == "queryDatabase":
            return await _database_tool.query_database_tool(args.get("query", ""))

        elif tool_name == "vectorSearch":
            result = await _database_tool.vector_search_tool(
                query=args.get("query", ""),
                max_results=args.get("max_results", 5),
            )
            if isinstance(result, dict):
                return result.get("voice_response") or str(result)
            return str(result)

        elif tool_name == "knowledgeBase":
            action = args.get("action", "search").lower()
            content = args.get("content", "")
            category = args.get("category")
            if action in ("search", "find", "query"):
                return await _database_tool.query_database_tool(content)
            else:
                return await _vector_store_tool.store_knowledge_tool(
                    content, category or "general", None
                )

        # ----------------------------------------------------------------
        # CONTACTS
        # ----------------------------------------------------------------
        elif tool_name == "addContact":
            return await _contact_tool.add_contact_tool(
                name=args.get("name", ""),
                email=args.get("email"),
                phone=args.get("phone"),
                company=args.get("company"),
                notes=args.get("notes"),
                gate=args.get("gate", 1),
                name_confirmed=args.get("name_confirmed", False),
                email_confirmed=args.get("email_confirmed", False),
            )

        elif tool_name == "getContact":
            return await _contact_tool.get_contact_tool(
                query=args.get("query"),
                name=args.get("name"),
                email=args.get("email"),
                contact_id=args.get("contact_id"),
            )

        elif tool_name == "searchContacts":
            return await _contact_tool.search_contacts_tool(args.get("query", ""))

        # ----------------------------------------------------------------
        # COMPOSIO — connection management
        # ----------------------------------------------------------------
        elif tool_name == "manageConnections":
            action = args.get("action", "status")
            service = args.get("service", "")
            recipient = args.get("recipient", "")
            account_id = args.get("account_id", "")

            if action.lower() == "status":
                return await get_connected_services_status()

            elif action.lower() == "refresh":
                catalog = await refresh_slug_index()
                tool_count = catalog.count("\n") if catalog else 0
                return f"Tools refreshed. {tool_count} tools available.\n{catalog}"

            elif action.lower() == "connect":
                if not service:
                    return "Which service would you like to connect?"
                auth_url, display_name = await initiate_service_connection(service, force_reauth=True)
                if not display_name:
                    return auth_url
                return f"Connection link for {display_name} generated. Send to {recipient or 'your email'}."

            else:
                return f"Unknown manageConnections action: {action}"

        # ----------------------------------------------------------------
        # COMPOSIO — catalog / schema lookup
        # ----------------------------------------------------------------
        elif tool_name == "listComposioTools":
            await ensure_slug_index()
            service = args.get("service", "")
            return get_tool_catalog(service_filter=service if service else None)

        elif tool_name == "planComposioTask":
            await ensure_slug_index()
            tool_slugs_str = args.get("tool_slugs", "")
            slugs = [s.strip().upper() for s in tool_slugs_str.split(",") if s.strip()]
            if not slugs:
                return "No slugs provided."
            results = []
            for slug in slugs[:10]:
                resolved, _ = _resolve_slug_fast(slug)
                actual = resolved or slug
                schema_text = _format_cached_schema(actual)
                results.append(
                    f"=== {actual} ===\n{schema_text}"
                    if schema_text
                    else f"=== {actual} ===\nNo cached schema."
                )
            return "PLAN SCHEMAS:\n\n" + "\n\n".join(results)

        elif tool_name == "getComposioToolSchema":
            return await get_tool_schema(args.get("tool_slug", ""))

        # ----------------------------------------------------------------
        # COMPOSIO — execution
        # ----------------------------------------------------------------
        elif tool_name == "composioExecute":
            tool_slug = args.get("tool_slug", "")
            arguments_json = args.get("arguments_json", "{}")
            try:
                arguments = json.loads(arguments_json) if isinstance(arguments_json, str) else arguments_json
            except json.JSONDecodeError:
                return "Could not parse arguments_json — pass valid JSON"
            async with _composio_semaphore:
                return await execute_composio_tool(
                    tool_slug=tool_slug,
                    arguments=arguments,
                )

        elif tool_name == "composioBatchExecute":
            tools_json = args.get("tools_json", "[]")
            try:
                tools_list = json.loads(tools_json) if isinstance(tools_json, str) else tools_json
            except json.JSONDecodeError:
                return "Could not parse tools_json — pass valid JSON array"
            if isinstance(tools_list, dict):
                tools_list = [tools_list]
            if not isinstance(tools_list, list) or not tools_list:
                return "tools_json must be a non-empty array"

            # Group by step
            step_groups: dict[int, list] = {}
            for t in tools_list:
                step = t.get("step", 1)
                if not isinstance(step, int) or step < 1:
                    step = 1
                step_groups.setdefault(step, []).append(t)

            all_results: list[str] = []
            for step_num in sorted(step_groups.keys()):
                async with _composio_semaphore:
                    group_result = await batch_execute_composio_tools(step_groups[step_num])
                all_results.append(group_result)

            return " | ".join(all_results) if len(all_results) > 1 else (all_results[0] if all_results else "No tools executed")

        # ----------------------------------------------------------------
        # LEAD GENERATION / PROSPECT SCRAPER
        # ----------------------------------------------------------------
        elif tool_name == "runLeadGen":
            from ..utils.n8n_client import n8n_post as _n8n_tep_post
            lead_type = args.get("lead_type", "")
            mode = args.get("mode", "results")
            limit = args.get("limit", 5)
            _status, _body = await _n8n_tep_post(
                "webhook/aio-lead-gen",
                {"lead_type": lead_type, "mode": mode, "limit": limit},
                timeout=15,
            )
            if _status in (200, 201, 202):
                mode_desc = "enriched leads with a Gmail draft" if mode == "enrich" else "a lead list with CSV link"
                return f"Lead generation started for {lead_type}. You'll receive {mode_desc} via email shortly."
            return f"Lead generation failed to start. Status: {_status}"

        elif tool_name == "scrapeProspects":
            clamped_limit = max(1, min(50, args.get("limit", 10)))
            return await _prospect_scraper_tool.scrape_prospects_tool(
                job_title=args.get("job_title", ""),
                location=args.get("location", "United States"),
                company=args.get("company", ""),
                limit=clamped_limit,
            )

        # ----------------------------------------------------------------
        # GAMMA CONTENT GENERATION
        # ----------------------------------------------------------------
        elif tool_name == "generatePresentation":
            return await generate_presentation_async(
                topic=args.get("topic", ""),
                slide_count=args.get("slide_count", 10),
                tone=args.get("tone", "professional"),
            )

        elif tool_name == "generateDocument":
            return await generate_document_async(
                topic=args.get("topic", ""),
                tone=args.get("tone", "professional"),
            )

        elif tool_name == "generateWebpage":
            return await generate_webpage_async(
                topic=args.get("topic", ""),
                tone=args.get("tone", "professional"),
            )

        elif tool_name == "generateSocial":
            return await generate_social_async(
                topic=args.get("topic", ""),
                platform=args.get("platform", "linkedin"),
                tone=args.get("tone", "engaging"),
            )

        # ----------------------------------------------------------------
        # USER PROFILE
        # ----------------------------------------------------------------
        elif tool_name == "updateUserProfile":
            return await _update_user_profile_tool(
                name=args.get("name", ""),
                role=args.get("role", ""),
                company=args.get("company", ""),
                timezone=args.get("timezone", ""),
                notes=args.get("notes", ""),
            )

        # ----------------------------------------------------------------
        # DEEP STORE / DEEP RECALL
        # ----------------------------------------------------------------
        elif tool_name == "deepStore":
            return await deep_store_async(
                content=args.get("content", ""),
                label=args.get("label", ""),
            )

        elif tool_name == "deepRecall":
            return await deep_recall_async(
                query=args.get("query", ""),
                label=args.get("label", ""),
            )

        # ----------------------------------------------------------------
        # requestGate — handled inline
        # ----------------------------------------------------------------
        elif tool_name == "requestGate":
            return await requestGate(
                gate_type=args.get("gate_type", "WRITE"),
                content=args.get("content", ""),
                voice_prompt=args.get("voice_prompt", ""),
                continuation_hint=args.get("continuation_hint", ""),
            )

        else:
            return f"Tool {tool_name} not available in tool executor"

    except Exception as exc:
        logger.error("[tool_executor] _dispatch_tool_call %s failed: %s", tool_name, exc, exc_info=True)
        return f"Tool {tool_name} error: {str(exc)[:200]}"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def delegate_tools(
    session_id: str,
    request: str,
    context_hints: dict,
    say_callback: Optional[Callable] = None,
    task_tracker: Any = None,
    pg_logger_module: Any = None,
) -> str:
    """Run the tool executor agentic loop for a delegated request.

    Args:
        session_id: Current session ID.
        request: The task description from the conversation LLM.
        context_hints: Dict with optional keys: user_id, last_result, session_summary.
        say_callback: Optional callable that speaks a phrase (for filler).
        task_tracker: Optional task tracker with record_tool_call_started/completed.
        pg_logger_module: Optional pg_logger module (unused directly; kept for API compat).

    Returns:
        Result string for the conversation LLM, OR a gate sentinel if confirmation needed.
    """
    _current_session_id.set(session_id)

    # Register current task for heartbeat guard
    current_task = asyncio.current_task()
    if session_id not in _active_delegation:
        _active_delegation[session_id] = set()
    if current_task:
        _active_delegation[session_id].add(current_task)

    # Signal heartbeat that a tool is in flight
    if task_tracker is not None:
        try:
            task_tracker.record_tool_call_started()
        except Exception:
            pass

    # Fire filler phrase asynchronously
    if say_callback is not None:
        asyncio.create_task(_fire_filler(say_callback))

    try:
        # ----------------------------------------------------------------
        # Initialise or retrieve per-session chat context
        # ----------------------------------------------------------------
        if session_id not in _tool_session_chat_ctx:
            _tool_session_chat_ctx[session_id] = [
                {"role": "system", "content": TOOL_SYSTEM_PROMPT}
            ]

        ctx = _tool_session_chat_ctx[session_id]

        # Build user message with optional context block
        context_block = _build_context_block(context_hints)
        user_content = f"{context_block}\n\n{request}".strip() if context_block else request
        ctx.append({"role": "user", "content": user_content})

        # ----------------------------------------------------------------
        # Agentic loop (max 10 steps)
        # ----------------------------------------------------------------
        result_str: str = "I completed the task but have no specific result to report."

        for step in range(10):
            # Call Fireworks under semaphore
            async with _composio_semaphore:
                try:
                    assistant_msg = await asyncio.wait_for(
                        _call_fireworks_streaming(ctx, _ALL_TOOL_SCHEMAS, session_id),
                        timeout=120.0,
                    )
                except asyncio.TimeoutError:
                    logger.error("[tool_executor] Fireworks streaming timed out at step %d (120s limit)", step)
                    result_str = "I ran into a timeout while processing that request. Please try again."
                    break
                except Exception as api_exc:
                    logger.error("[tool_executor] Fireworks API error step %d: %s", step, api_exc)
                    result_str = f"I encountered an API error while processing: {api_exc}"
                    break

            ctx.append(assistant_msg)

            tool_calls = assistant_msg.get("tool_calls", [])

            # No tool calls → LLM is done
            if not tool_calls:
                result_str = assistant_msg.get("content") or result_str
                break

            # Execute all tool calls
            tool_results: list[dict] = []
            gate_result: Optional[str] = None

            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    raw_args = fn.get("arguments", "{}")
                    tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    tool_args = {}

                # Execute (gate check inline for requestGate)
                tool_result = await _dispatch_tool_call(tool_name, tool_args, session_id)

                result_content = str(tool_result) if tool_result is not None else ""

                # Check for gate sentinel
                if result_content.startswith(_GATE_SENTINEL):
                    gate_result = result_content
                    break

                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result_content,
                    }
                )

            # Gate intercept — return sentinel immediately
            if gate_result is not None:
                return gate_result

            # Append tool results to context
            ctx.extend(tool_results)
            _trim_tool_context(session_id)

            # If no content yet, keep looping
            if assistant_msg.get("content"):
                result_str = assistant_msg["content"]

        # ----------------------------------------------------------------
        # Persist last_tool_result for per-turn context injection
        # ----------------------------------------------------------------
        try:
            store_fact(session_id, "last_tool_result", result_str[:2000])
        except Exception:
            pass

        return result_str

    finally:
        # Always remove task from active set and signal tracker
        if current_task and session_id in _active_delegation:
            _active_delegation[session_id].discard(current_task)

        if task_tracker is not None:
            try:
                task_tracker.record_tool_call_completed()
            except Exception:
                pass
