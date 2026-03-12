"""Unit tests for src/utils/tool_result.py

Tests verify:
- ToolResult dataclass fields and defaults
- announce_tool_result suppression logic (all 4 suppression paths)
- announce_tool_result instruction selection (success / timeout / error / custom)
- Exception safety (generate_reply failure does not re-raise)
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

# ── Import guard ──────────────────────────────────────────────────────────────
try:
    from src.utils.tool_result import (
        ToolResult,
        _CB_TRIPPED_PREFIX_CHECK,
        _GAMMA_RESULT_PREFIX,
        _NO_TOOL_SENTINEL,
        announce_tool_result,
    )
    IMPORTS_OK = True
except ImportError:
    IMPORTS_OK = False

pytestmark = pytest.mark.skipif(not IMPORTS_OK, reason="tool_result not importable")


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_session():
    """Return a mock session with an awaitable generate_reply."""
    session = MagicMock()
    session.generate_reply = AsyncMock()
    return session


def run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Sentinel value tests ──────────────────────────────────────────────────────

class TestSentinelValues:
    """Sentinel strings must match composio_router and tool_executor."""

    def test_gamma_result_prefix(self):
        assert _GAMMA_RESULT_PREFIX == "Gamma presentation ready:"

    def test_cb_tripped_prefix(self):
        assert _CB_TRIPPED_PREFIX_CHECK == "CB_TRIPPED:"

    def test_no_tool_sentinel(self):
        assert _NO_TOOL_SENTINEL == "NO_ACTION"


# ── ToolResult dataclass tests ────────────────────────────────────────────────

class TestToolResultDataclass:
    """ToolResult fields, defaults, and immutability."""

    def test_required_fields(self):
        tr = ToolResult(tool_name="test", result="some result")
        assert tr.tool_name == "test"
        assert tr.result == "some result"

    def test_defaults(self):
        tr = ToolResult(tool_name="t", result="r")
        assert tr.announce_via_llm is True
        assert tr.suppress_if_gamma is True
        assert tr.custom_instructions is None
        assert tr.is_timeout is False
        assert tr.is_error is False

    def test_frozen(self):
        tr = ToolResult(tool_name="t", result="r")
        with pytest.raises((AttributeError, TypeError)):
            tr.result = "mutated"  # type: ignore[misc]

    def test_custom_instructions_override(self):
        tr = ToolResult(tool_name="t", result="r", custom_instructions="Say hello")
        assert tr.custom_instructions == "Say hello"

    def test_is_timeout_flag(self):
        tr = ToolResult(tool_name="t", result="", is_timeout=True)
        assert tr.is_timeout is True

    def test_is_error_flag(self):
        tr = ToolResult(tool_name="t", result="", is_error=True)
        assert tr.is_error is True


# ── announce_tool_result suppression tests ────────────────────────────────────

class TestAnnounceSuppression:
    """Verify all 4 suppression paths return without calling generate_reply."""

    def test_none_session_skips(self):
        tr = ToolResult(tool_name="t", result="hello")
        run(announce_tool_result(None, tr, session_id="s1"))
        # No session — nothing to assert except no exception raised

    def test_announce_via_llm_false_skips(self):
        session = make_session()
        tr = ToolResult(tool_name="t", result="hello", announce_via_llm=False)
        run(announce_tool_result(session, tr, session_id="s2"))
        session.generate_reply.assert_not_called()

    def test_cb_tripped_suppressed(self):
        session = make_session()
        tr = ToolResult(tool_name="t", result="CB_TRIPPED: auth expired")
        run(announce_tool_result(session, tr, session_id="s3"))
        session.generate_reply.assert_not_called()

    def test_gamma_suppressed_when_flag_true(self):
        session = make_session()
        tr = ToolResult(
            tool_name="t",
            result="Gamma presentation ready: https://gamma.app/x",
            suppress_if_gamma=True,
        )
        run(announce_tool_result(session, tr, session_id="s4"))
        session.generate_reply.assert_not_called()

    def test_gamma_not_suppressed_when_flag_false(self):
        session = make_session()
        tr = ToolResult(
            tool_name="t",
            result="Gamma presentation ready: https://gamma.app/x",
            suppress_if_gamma=False,
        )
        run(announce_tool_result(session, tr, session_id="s5"))
        session.generate_reply.assert_called_once()

    def test_no_action_suppressed(self):
        session = make_session()
        tr = ToolResult(tool_name="t", result="NO_ACTION")
        run(announce_tool_result(session, tr, session_id="s6"))
        session.generate_reply.assert_not_called()

    def test_empty_result_suppressed(self):
        session = make_session()
        tr = ToolResult(tool_name="t", result="")
        run(announce_tool_result(session, tr, session_id="s7"))
        session.generate_reply.assert_not_called()


# ── announce_tool_result instruction selection tests ──────────────────────────

class TestAnnounceInstructions:
    """Verify instruction template selection."""

    def test_success_instructions_include_result(self):
        session = make_session()
        tr = ToolResult(tool_name="t", result="Found 5 files")
        run(announce_tool_result(session, tr, session_id="s8"))
        call_kwargs = session.generate_reply.call_args
        instructions = call_kwargs.kwargs.get("instructions", "")
        assert "Found 5 files" in instructions

    def test_custom_instructions_used_verbatim(self):
        session = make_session()
        tr = ToolResult(
            tool_name="t", result="r", custom_instructions="Custom message here"
        )
        run(announce_tool_result(session, tr, session_id="s9"))
        call_kwargs = session.generate_reply.call_args
        instructions = call_kwargs.kwargs.get("instructions", "")
        assert instructions == "Custom message here"

    def test_timeout_instructions(self):
        session = make_session()
        tr = ToolResult(tool_name="t", result="timeout", is_timeout=True)
        run(announce_tool_result(session, tr, session_id="s10"))
        call_kwargs = session.generate_reply.call_args
        instructions = call_kwargs.kwargs.get("instructions", "")
        assert "timed out" in instructions.lower()

    def test_error_instructions(self):
        session = make_session()
        tr = ToolResult(tool_name="t", result="error", is_error=True)
        run(announce_tool_result(session, tr, session_id="s11"))
        call_kwargs = session.generate_reply.call_args
        instructions = call_kwargs.kwargs.get("instructions", "")
        assert "error" in instructions.lower()


# ── announce_tool_result exception safety ─────────────────────────────────────

class TestAnnounceExceptionSafety:
    """generate_reply failure must not propagate."""

    def test_generate_reply_exception_does_not_raise(self):
        session = MagicMock()
        session.generate_reply = AsyncMock(side_effect=RuntimeError("LK disconnected"))
        tr = ToolResult(tool_name="t", result="some result")
        # Must not raise
        run(announce_tool_result(session, tr, session_id="s12"))
