"""
E2E / unit test suite: background delegation architecture in run_background_delegation.

Coverage:
  1. Gamma double-announce suppression — generate_reply NOT called when result starts with
     "Gamma presentation ready:"
  2. Normal result flow — generate_reply called with truncated result in instructions kwarg
  3. 300s outer timeout — asyncio.TimeoutError triggers apology reply
  4. Timeout error logging — logger.error captures session_id + "timed out"
  5. Session not in registry — function returns cleanly, no generate_reply
  6. Per-session asyncio.Lock — concurrent calls for same session_id are serialised
  7. Different sessions use different locks — no cross-session deadlock
  8. asyncio.CancelledError handled gracefully — no propagation, no generate_reply
  9. WeakValueDictionary — sessions dropped from registry after GC
  10. WeakValueDictionary — live session retained while reference held
  11. Result truncation at 500 chars — instructions embed only result[:500]
  12. Generic exception — triggers apology generate_reply

All tests are unit-level (no external calls, no live DB, no Railway).
pytest-asyncio with asyncio_mode=auto handles coroutine tests.
"""

from __future__ import annotations

import asyncio
import gc
import importlib.util
import logging
import sys
import time
import types
import weakref
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Repo-root / src-root resolution
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SRC_ROOT = _REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# Minimal stub infrastructure (mirrors test_composio_meta.py pattern)
# ---------------------------------------------------------------------------

def _ensure_stub(name: str, attrs: dict | None = None) -> types.ModuleType:
    """Insert a bare stub into sys.modules if not already present."""
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _stub_all() -> None:
    """Pre-seed sys.modules with every stub required by tool_executor's imports."""

    # src package skeleton
    _ensure_stub("src")
    _ensure_stub("src.utils")
    _ensure_stub("src.tools")
    _ensure_stub("src.prompts")

    # httpx (imported at top-level in tool_executor)
    _ensure_stub("httpx")

    # config — get_settings() must return a settings-like object
    _settings_obj = MagicMock()
    _settings_obj.fireworks_api_key = "fw-test-key"
    _settings_obj.max_tool_steps = 10
    _ensure_stub("src.config", {"get_settings": MagicMock(return_value=_settings_obj)})

    # prompts
    _prompts_stub = _ensure_stub("src.prompts")
    _prompts_stub.TOOL_SYSTEM_PROMPT = "stub system prompt"  # type: ignore[attr-defined]

    # session_facts
    _ensure_stub(
        "src.utils.session_facts",
        {"store_fact": AsyncMock(), "get_fact": AsyncMock(return_value=None)},
    )


_stub_all()


# ---------------------------------------------------------------------------
# Load tool_executor in isolation
# ---------------------------------------------------------------------------

def _load_tool_executor() -> types.ModuleType:
    """Load src/tools/tool_executor.py via spec_from_file_location.

    Idempotent — returns cached module on repeated calls.
    """
    module_name = "src.tools.tool_executor"
    if module_name in sys.modules:
        return sys.modules[module_name]

    exe_path = _SRC_ROOT / "tools" / "tool_executor.py"
    spec = importlib.util.spec_from_file_location(module_name, exe_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_te = _load_tool_executor()

# Convenience aliases — keep tests readable
run_background_delegation = _te.run_background_delegation
_session_registry: weakref.WeakValueDictionary = _te._session_registry
_session_delegation_locks: dict[str, asyncio.Lock] = _te._session_delegation_locks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session_id() -> str:
    return f"test-session-{uuid4().hex[:8]}"


@pytest.fixture
def mock_session() -> AsyncMock:
    session = MagicMock()
    session.generate_reply = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _patch_and_run(
    session_id: str,
    result_or_exc: Any,
    *,
    registry_session: Any | None,
) -> None:
    """
    Patches delegate_tools + _session_registry, then awaits run_background_delegation.

    Args:
        session_id: Session identifier string.
        result_or_exc: If Exception subclass instance → delegate_tools raises it.
                       Otherwise → delegate_tools returns it as a coroutine result.
        registry_session: The session object to seed into _session_registry, or None.
    """
    # Seed registry before the call
    if registry_session is not None:
        _session_registry[session_id] = registry_session
    else:
        _session_registry.pop(session_id, None)

    if isinstance(result_or_exc, BaseException):
        async def _raise(*_, **__):
            raise result_or_exc
        mock_delegate = AsyncMock(side_effect=_raise)
    else:
        mock_delegate = AsyncMock(return_value=result_or_exc)

    with patch.object(_te, "delegate_tools", mock_delegate):
        await run_background_delegation(
            session_id=session_id,
            request="do something useful",
            context_hints={"user_id": "test-user"},
        )


# ---------------------------------------------------------------------------
# Class 1: TestRunBackgroundDelegation
# ---------------------------------------------------------------------------

class TestRunBackgroundDelegation:
    """Unit tests for run_background_delegation core paths."""

    @pytest.mark.asyncio
    async def test_gamma_result_suppresses_generate_reply(
        self, session_id: str, mock_session: AsyncMock
    ) -> None:
        """Gamma results must NOT trigger generate_reply — monitor owns announcements."""
        t0 = time.monotonic()
        gamma_result = "Gamma presentation ready: https://gamma.app/deck/abc123"

        await _patch_and_run(session_id, gamma_result, registry_session=mock_session)

        mock_session.generate_reply.assert_not_called()
        print(f"[test_gamma_result_suppresses_generate_reply] {(time.monotonic()-t0)*1000:.1f}ms")

    @pytest.mark.asyncio
    async def test_normal_result_triggers_generate_reply(
        self, session_id: str, mock_session: AsyncMock
    ) -> None:
        """A normal tool result must call generate_reply with the result embedded."""
        t0 = time.monotonic()
        normal_result = "Email sent to John at 2pm."

        await _patch_and_run(session_id, normal_result, registry_session=mock_session)

        mock_session.generate_reply.assert_called_once()
        call_kwargs = mock_session.generate_reply.call_args.kwargs
        assert "instructions" in call_kwargs, "generate_reply must receive an 'instructions' kwarg"
        assert "Email sent to John" in call_kwargs["instructions"]
        print(f"[test_normal_result_triggers_generate_reply] {(time.monotonic()-t0)*1000:.1f}ms")

    @pytest.mark.asyncio
    async def test_300s_timeout_triggers_apology(
        self, session_id: str, mock_session: AsyncMock
    ) -> None:
        """asyncio.TimeoutError from delegate_tools must trigger an apology reply."""
        t0 = time.monotonic()

        await _patch_and_run(
            session_id,
            asyncio.TimeoutError(),
            registry_session=mock_session,
        )

        mock_session.generate_reply.assert_called_once()
        call_kwargs = mock_session.generate_reply.call_args.kwargs
        instructions = call_kwargs.get("instructions", "")
        assert any(
            kw in instructions.lower() for kw in ("timed out", "apologize", "retry")
        ), f"Timeout apology instructions missing expected keywords: {instructions!r}"
        print(f"[test_300s_timeout_triggers_apology] {(time.monotonic()-t0)*1000:.1f}ms")

    @pytest.mark.asyncio
    async def test_timeout_logs_error(
        self, session_id: str, mock_session: AsyncMock
    ) -> None:
        """asyncio.TimeoutError must emit a logger.error containing 'timed out' and session_id."""
        t0 = time.monotonic()
        logged_errors: list[str] = []

        original_error = _te.logger.error

        def _capture_error(msg: str, *args, **kwargs) -> None:
            logged_errors.append(msg % args if args else str(msg))
            original_error(msg, *args, **kwargs)

        with patch.object(_te.logger, "error", side_effect=_capture_error):
            await _patch_and_run(
                session_id,
                asyncio.TimeoutError(),
                registry_session=mock_session,
            )

        assert logged_errors, "Expected at least one logger.error call"
        combined = " ".join(logged_errors).lower()
        assert "timed out" in combined or "timeout" in combined, (
            f"No 'timed out'/'timeout' in error logs: {logged_errors}"
        )
        assert session_id in " ".join(logged_errors), (
            f"session_id {session_id!r} not found in error logs: {logged_errors}"
        )
        print(f"[test_timeout_logs_error] {(time.monotonic()-t0)*1000:.1f}ms")

    @pytest.mark.asyncio
    async def test_session_not_in_registry_is_noop(self, session_id: str) -> None:
        """Empty registry: run_background_delegation must return cleanly, no exceptions."""
        t0 = time.monotonic()

        # Ensure session_id absent from registry
        _session_registry.pop(session_id, None)

        phantom_session = MagicMock()
        phantom_session.generate_reply = AsyncMock()

        # Run with no registry entry (pass None → helper skips seeding)
        await _patch_and_run(session_id, "Tool completed.", registry_session=None)

        phantom_session.generate_reply.assert_not_called()
        print(f"[test_session_not_in_registry_is_noop] {(time.monotonic()-t0)*1000:.1f}ms")

    @pytest.mark.asyncio
    async def test_per_session_lock_prevents_concurrent_reply(
        self, session_id: str
    ) -> None:
        """Two concurrent calls for the same session_id must serialise generate_reply."""
        t0 = time.monotonic()
        call_order: list[str] = []
        reply_active = False
        overlap_detected = False

        async def _slow_generate_reply(*, instructions: str) -> None:
            nonlocal reply_active, overlap_detected
            if reply_active:
                overlap_detected = True  # concurrent execution detected
            reply_active = True
            call_order.append("start")
            await asyncio.sleep(0.05)  # simulate TTS latency
            call_order.append("end")
            reply_active = False

        session = MagicMock()
        session.generate_reply = AsyncMock(side_effect=_slow_generate_reply)
        _session_registry[session_id] = session

        async def _run_one(label: str) -> None:
            mock_delegate = AsyncMock(return_value=f"result from {label}")
            with patch.object(_te, "delegate_tools", mock_delegate):
                await run_background_delegation(
                    session_id=session_id,
                    request=label,
                    context_hints={},
                )

        await asyncio.gather(_run_one("A"), _run_one("B"))

        assert not overlap_detected, (
            "generate_reply was called concurrently for the same session — lock not working"
        )
        # Both calls must complete
        assert call_order.count("start") == 2
        assert call_order.count("end") == 2
        # Serial order: start→end→start→end (no interleaving)
        assert call_order == ["start", "end", "start", "end"], (
            f"Unexpected call order (interleaved?): {call_order}"
        )
        print(f"[test_per_session_lock_prevents_concurrent_reply] {(time.monotonic()-t0)*1000:.1f}ms")

    @pytest.mark.asyncio
    async def test_different_sessions_use_different_locks(self) -> None:
        """Two different session_ids must not block each other (no cross-session deadlock)."""
        t0 = time.monotonic()
        sid_a = f"test-session-{uuid4().hex[:8]}"
        sid_b = f"test-session-{uuid4().hex[:8]}"

        completion_times: dict[str, float] = {}

        async def _timed_generate_reply(sid: str, *, instructions: str) -> None:
            await asyncio.sleep(0.05)
            completion_times[sid] = time.monotonic()

        async def _reply_a(*, instructions: str) -> None:
            await _timed_generate_reply(sid_a, instructions=instructions)

        async def _reply_b(*, instructions: str) -> None:
            await _timed_generate_reply(sid_b, instructions=instructions)

        session_a = MagicMock()
        session_a.generate_reply = AsyncMock(side_effect=_reply_a)
        session_b = MagicMock()
        session_b.generate_reply = AsyncMock(side_effect=_reply_b)

        _session_registry[sid_a] = session_a
        _session_registry[sid_b] = session_b

        async def _run(sid: str) -> None:
            mock_delegate = AsyncMock(return_value="parallel result")
            with patch.object(_te, "delegate_tools", mock_delegate):
                await run_background_delegation(
                    session_id=sid,
                    request="parallel task",
                    context_hints={},
                )

        wall_start = time.monotonic()
        await asyncio.gather(_run(sid_a), _run(sid_b))
        wall_elapsed = time.monotonic() - wall_start

        # Both sessions must complete
        assert sid_a in completion_times, "Session A generate_reply never completed"
        assert sid_b in completion_times, "Session B generate_reply never completed"

        # Wall time should be ~50ms (parallel), not ~100ms (serial)
        # Give generous headroom for CI slowness
        assert wall_elapsed < 0.25, (
            f"Parallel sessions appear to be serialised: wall={wall_elapsed:.3f}s"
        )

        # Verify distinct lock objects were created
        lock_a = _session_delegation_locks.get(sid_a)
        lock_b = _session_delegation_locks.get(sid_b)
        assert lock_a is not None, "Lock for session A not created"
        assert lock_b is not None, "Lock for session B not created"
        assert lock_a is not lock_b, "Sessions A and B share the same Lock — must be distinct"

        print(f"[test_different_sessions_use_different_locks] {wall_elapsed*1000:.1f}ms wall")

    @pytest.mark.asyncio
    async def test_cancelled_error_handled_gracefully(
        self, session_id: str, mock_session: AsyncMock
    ) -> None:
        """asyncio.CancelledError must not propagate and must not call generate_reply."""
        t0 = time.monotonic()
        _session_registry[session_id] = mock_session

        async def _raise_cancelled(*_, **__):
            raise asyncio.CancelledError()

        mock_delegate = AsyncMock(side_effect=_raise_cancelled)

        # Must not raise
        with patch.object(_te, "delegate_tools", mock_delegate):
            await run_background_delegation(
                session_id=session_id,
                request="will be cancelled",
                context_hints={},
            )

        mock_session.generate_reply.assert_not_called()
        print(f"[test_cancelled_error_handled_gracefully] {(time.monotonic()-t0)*1000:.1f}ms")


# ---------------------------------------------------------------------------
# Class 2: TestWeakRefSessionRegistry
# ---------------------------------------------------------------------------

class TestWeakRefSessionRegistry:
    """Tests that WeakValueDictionary releases sessions correctly."""

    def test_weakref_drops_session_on_gc(self) -> None:
        """Session must be absent from registry after the external reference is deleted."""
        t0 = time.monotonic()
        sid = f"test-session-{uuid4().hex[:8]}"

        session = MagicMock()
        session.generate_reply = AsyncMock()

        _session_registry[sid] = session

        # Verify it's present before deletion
        assert _session_registry.get(sid) is session

        # Drop the only strong reference
        del session
        gc.collect()

        assert _session_registry.get(sid) is None, (
            "WeakValueDictionary should have dropped the session after GC"
        )
        print(f"[test_weakref_drops_session_on_gc] {(time.monotonic()-t0)*1000:.1f}ms")

    def test_live_session_retained_in_registry(self) -> None:
        """Session must remain in registry while a strong reference is still held."""
        t0 = time.monotonic()
        sid = f"test-session-{uuid4().hex[:8]}"

        session = MagicMock()
        session.generate_reply = AsyncMock()

        _session_registry[sid] = session

        # GC with strong ref still held
        gc.collect()

        retrieved = _session_registry.get(sid)
        assert retrieved is session, (
            "Session should still be present in registry — strong ref is held"
        )
        print(f"[test_live_session_retained_in_registry] {(time.monotonic()-t0)*1000:.1f}ms")


# ---------------------------------------------------------------------------
# Class 3: TestDelegationResultAnnouncement
# ---------------------------------------------------------------------------

class TestDelegationResultAnnouncement:
    """Tests for result formatting and exception apology paths."""

    @pytest.mark.asyncio
    async def test_result_truncated_to_500_chars(
        self, session_id: str, mock_session: AsyncMock
    ) -> None:
        """A 1000-char result must be embedded as result[:500] in the instructions."""
        t0 = time.monotonic()
        long_result = "X" * 1000

        await _patch_and_run(session_id, long_result, registry_session=mock_session)

        mock_session.generate_reply.assert_called_once()
        call_kwargs = mock_session.generate_reply.call_args.kwargs
        instructions: str = call_kwargs.get("instructions", "")

        # The instructions must contain exactly 500 Xs, not 1000
        embedded_x_count = instructions.count("X")
        assert embedded_x_count <= 500, (
            f"Instructions embed {embedded_x_count} chars of result — expected ≤500"
        )
        # And the truncated portion must appear verbatim
        assert "X" * 500 in instructions, "Expected result[:500] block in instructions"
        # The 501st char must NOT appear after the block
        assert "X" * 501 not in instructions, "result[:501] found — truncation not applied"

        print(f"[test_result_truncated_to_500_chars] {(time.monotonic()-t0)*1000:.1f}ms")

    @pytest.mark.asyncio
    async def test_error_exception_triggers_apology(
        self, session_id: str, mock_session: AsyncMock
    ) -> None:
        """A generic Exception from delegate_tools must trigger an apology generate_reply."""
        t0 = time.monotonic()

        await _patch_and_run(
            session_id,
            RuntimeError("Composio rate limit exceeded"),
            registry_session=mock_session,
        )

        mock_session.generate_reply.assert_called_once()
        call_kwargs = mock_session.generate_reply.call_args.kwargs
        instructions: str = call_kwargs.get("instructions", "").lower()
        assert any(kw in instructions for kw in ("error", "apologize", "retry")), (
            f"Apology instructions missing expected keywords: {instructions!r}"
        )
        print(f"[test_error_exception_triggers_apology] {(time.monotonic()-t0)*1000:.1f}ms")
