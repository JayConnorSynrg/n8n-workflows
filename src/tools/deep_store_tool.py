"""AIO Deep Store Tool — Unlimited persistent storage for large, important content.

Complements the memories table (capped at 1 KB, auto-captured) with an
unrestricted archive the user controls explicitly:

  deepStore — user says "deep store that" → stores whatever content with a label
  deepRecall — user says "recall the deep store" → retrieves by label or text query

Both tools operate on the per-user SQLite database (same file as memories,
separate table). Data persists across all sessions with no expiry.
"""
import asyncio
import logging
from typing import Optional

from livekit.agents import llm

from ..utils.room_publisher import (
    publish_tool_start,
    publish_tool_executing,
    publish_tool_completed,
    publish_tool_error,
)

logger = logging.getLogger(__name__)

# Memory module — same singleton used by other tools, already reinit'd per-user
try:
    from ..memory import memory_store as _memory_store
    _MEMORY_AVAILABLE = True
except Exception:
    _memory_store = None  # type: ignore[assignment]
    _MEMORY_AVAILABLE = False

try:
    from . import agent_context_tool as _agent_context_tool
    _AGENT_CONTEXT_AVAILABLE = True
except Exception:
    _agent_context_tool = None  # type: ignore[assignment]
    _AGENT_CONTEXT_AVAILABLE = False


@llm.function_tool(
    name="deepStore",
    description=(
        "Permanently save important content, facts, or preferences to the user's personal database. "
        "Call this when the user asks you to remember, save, note, keep, or store any information — "
        "including personal details (name, email, preferences, favorite things), "
        "important facts, decisions, or any content they want recalled in future sessions. "
        "Trigger phrases: 'remember that', 'save that', 'note that', 'keep that', "
        "'my favorite X is Y', 'I want you to know', 'store this', 'deep store that'. "
        "Provide a short descriptive label so the content can be recalled precisely. "
        "The content persists across all future sessions — it never expires. "
        "IMPORTANT: Always call this tool BEFORE saying you have saved something."
    ),
)
async def deep_store_async(
    content: str,
    label: str = "",
) -> str:
    """Store large content permanently in the deep_store table (no size limit)."""
    call_id = await publish_tool_start("deepStore", {"label": label[:40] or "(no label)"})
    await publish_tool_executing(call_id)

    if not _MEMORY_AVAILABLE or _memory_store is None:
        await publish_tool_error(call_id, "Memory unavailable")
        return "Deep storage is not available right now"

    _sid = (
        _agent_context_tool._current_session_id
        if _AGENT_CONTEXT_AVAILABLE and _agent_context_tool is not None
        else None
    ) or ""
    _uid = (
        _agent_context_tool._current_user_id
        if _AGENT_CONTEXT_AVAILABLE and _agent_context_tool is not None
        else None
    ) or "_default"
    entry_id = await asyncio.to_thread(
        _memory_store.deep_store_save,
        content,
        label or "unlabeled",
        _sid,
        _uid,
    )

    if entry_id:
        label_str = label.strip() or "item"
        await publish_tool_completed(call_id, f"Stored: {label_str[:60]}")
        return f"Deep stored — saved '{label_str}' permanently to your database"
    else:
        await publish_tool_error(call_id, "Storage failed")
        return "Could not deep store that right now — storage error"


@llm.function_tool(
    name="deepRecall",
    description=(
        "Retrieve content previously saved with deepStore. "
        "Use label to find a specific item by name, or use query to search across all deep stored content. "
        "If neither is given, returns the most recently stored items. "
        "Returns full content without any truncation."
    ),
)
async def deep_recall_async(
    query: str = "",
    label: str = "",
) -> str:
    """Retrieve deep stored content by label or full-text search."""
    search_term = label or query or ""
    call_id = await publish_tool_start("deepRecall", {"search": search_term[:40]})
    await publish_tool_executing(call_id)

    if not _MEMORY_AVAILABLE or _memory_store is None:
        await publish_tool_error(call_id, "Memory unavailable")
        return "Deep storage is not available right now"

    results = await asyncio.to_thread(
        _memory_store.deep_store_search,
        query,
        label,
        3,
    )

    if not results:
        await publish_tool_completed(call_id, "No results")
        qualifier = f" matching '{search_term}'" if search_term else ""
        return f"No deep stored items found{qualifier}"

    if len(results) == 1:
        r = results[0]
        await publish_tool_completed(call_id, f"Found: {r['label'][:40]}")
        return f"Deep store — {r['label']}: {r['content']}"

    # Multiple results
    parts = [f"Found {len(results)} deep stored items:"]
    for r in results:
        snippet = r['content'][:600] + ("..." if len(r['content']) > 600 else "")
        parts.append(f"[{r['label']}] {snippet}")

    await publish_tool_completed(call_id, f"Found {len(results)} items")
    return "\n\n".join(parts)
