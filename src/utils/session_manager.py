"""AIO Voice Agent — Session lifecycle registry.

Centralises the per-session AgentSession registry and per-session delegation
locking so that tool_executor.py is not the owner of cross-cutting session
state.
"""

import asyncio
import weakref
from typing import Any

# WeakValueDictionary — registry never prevents GC of a dead session.
_session_registry: weakref.WeakValueDictionary = weakref.WeakValueDictionary()

# Per-session asyncio.Lock — serialises generate_reply calls so two concurrent
# tool completions do not both try to speak simultaneously.
_session_delegation_locks: dict[str, asyncio.Lock] = {}


def register_session(session_id: str, session: Any) -> None:
    """Register a LiveKit AgentSession for background delegation callbacks."""
    _session_registry[session_id] = session


def unregister_session(session_id: str) -> None:
    """Remove a session from the registry when it ends."""
    _session_registry.pop(session_id, None)


def get_session(session_id: str) -> Any | None:
    """Return the registered AgentSession for session_id, or None."""
    return _session_registry.get(session_id)


def get_or_create_lock(session_id: str) -> asyncio.Lock:
    """Return the per-session delegation lock, creating it if absent."""
    return _session_delegation_locks.setdefault(session_id, asyncio.Lock())
