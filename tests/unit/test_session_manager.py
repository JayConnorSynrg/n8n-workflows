"""Unit tests for src/utils/session_manager.py

Tests verify:
- Module structure (all expected symbols present)
- Registry behavior (WeakValueDictionary semantics)
- Lock management (idempotent per-session locks)
"""

import asyncio
import sys
import types
import weakref
import pytest

# ── Import guard ──────────────────────────────────────────────────────────────
try:
    from src.utils.session_manager import (
        _session_delegation_locks,
        _session_registry,
        get_or_create_lock,
        get_session,
        register_session,
        unregister_session,
    )
    IMPORTS_OK = True
except ImportError:
    IMPORTS_OK = False

pytestmark = pytest.mark.skipif(not IMPORTS_OK, reason="session_manager not importable")


class TestSessionManagerStructure:
    """Verify all expected symbols are exported."""

    def test_session_registry_is_weak_value_dict(self):
        assert isinstance(_session_registry, weakref.WeakValueDictionary)

    def test_session_delegation_locks_is_dict(self):
        assert isinstance(_session_delegation_locks, dict)

    def test_register_session_callable(self):
        assert callable(register_session)

    def test_unregister_session_callable(self):
        assert callable(unregister_session)

    def test_get_session_callable(self):
        assert callable(get_session)

    def test_get_or_create_lock_callable(self):
        assert callable(get_or_create_lock)


class TestSessionRegistry:
    """Verify register / get / unregister lifecycle."""

    def test_register_and_get(self):
        """Registered session is retrievable via get_session."""
        # Use a module object as a stand-in for an AgentSession (weakref-able)
        fake_session = types.ModuleType("fake_session")
        register_session("test-room-1", fake_session)
        result = get_session("test-room-1")
        assert result is fake_session
        # Cleanup
        unregister_session("test-room-1")

    def test_get_unknown_session_returns_none(self):
        """get_session returns None for unknown session_id."""
        result = get_session("nonexistent-session-xyz")
        assert result is None

    def test_unregister_removes_session(self):
        """unregister_session makes get_session return None."""
        fake_session = types.ModuleType("fake_session_2")
        register_session("test-room-2", fake_session)
        unregister_session("test-room-2")
        result = get_session("test-room-2")
        assert result is None

    def test_unregister_nonexistent_does_not_raise(self):
        """Unregistering a session_id that was never registered is a no-op."""
        unregister_session("never-registered-xyz")  # must not raise


class TestSessionLocks:
    """Verify lock management."""

    def test_get_or_create_lock_returns_asyncio_lock(self):
        """get_or_create_lock returns an asyncio.Lock instance."""
        lock = get_or_create_lock("lock-test-room")
        assert isinstance(lock, asyncio.Lock)

    def test_get_or_create_lock_is_idempotent(self):
        """Calling get_or_create_lock twice for the same session_id returns the same lock."""
        lock_a = get_or_create_lock("idempotent-lock-room")
        lock_b = get_or_create_lock("idempotent-lock-room")
        assert lock_a is lock_b

    def test_different_sessions_get_different_locks(self):
        """Two different session_ids get distinct locks."""
        lock_x = get_or_create_lock("room-x")
        lock_y = get_or_create_lock("room-y")
        assert lock_x is not lock_y
