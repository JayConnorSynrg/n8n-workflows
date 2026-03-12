"""
E2E test suite: Parallel Dual-Track Speech Architecture for AIO Voice Agent.

Coverage:
  1. evaluate_and_execute_from_speech — short-utterance guard (word count < 3)
  2. evaluate_and_execute_from_speech — 3-word minimum fires delegate_tools
  3. NO_ACTION sentinel suppresses generate_reply
  4. Gamma result suppresses generate_reply (owned by _gamma_notification_monitor)
  5. Normal tool result triggers generate_reply with result in instructions
  6. context_hints dict is forwarded intact to delegate_tools
  7. recent_context prepended to the request string passed to delegate_tools
  8. 300-second asyncio.TimeoutError yields apology generate_reply

  Integration tests (--run-integration flag):
  9.  evaluate_and_execute_from_speech elapsed-time logged to tool_calls table
  10. Last-10 conversation_log rows snapshot for manual inspection

Architecture under test:
  - evaluate_and_execute_from_speech(transcript, session_id, context_hints, recent_context)
    lives at src/tools/tool_executor.py line ~645.
  - _NO_TOOL_SENTINEL = "NO_ACTION" (line 55)
  - _session_registry: weakref.WeakValueDictionary (line 44)
  - _session_delegation_locks: dict[str, asyncio.Lock] (line 45)
  - Minimum word threshold enforced before task is spawned in agent.py: len(text.split()) >= 3
  - recent_context: last 4 chat messages from user/assistant roles
  - context_hints={"user_id": _user_id} ensures correct Composio entity (453 tools, not 48)

All non-integration tests run without any external calls (no Railway, no DB, no Composio).
asyncio_mode=auto is assumed via pytest.ini; @pytest.mark.asyncio is added for explicitness.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import types
import uuid
import weakref
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# Suppress the "coroutine was never awaited" warning emitted when AsyncMock creates a
# coroutine that the function under test never reaches (e.g. early-return path tests).
# This is expected behaviour for tests asserting delegate_tools is NOT called.
import warnings
warnings.filterwarnings(
    "ignore",
    message="coroutine.*was never awaited",
    category=RuntimeWarning,
)

# ---------------------------------------------------------------------------
# Path bootstrap — load src/tools/tool_executor.py via spec_from_file_location
# so that relative package imports resolve correctly through sys.modules stubs.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SRC_ROOT = _REPO_ROOT / "src"


def _ensure_stub(name: str, attrs: dict | None = None) -> types.ModuleType:
    """Insert a stub module into sys.modules if not already present."""
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# ── Core package stubs ───────────────────────────────────────────────────────
_ensure_stub("src")
_ensure_stub("src.utils")
_ensure_stub("src.tools")
_ensure_stub("src.prompts")
_ensure_stub("src.config")
_ensure_stub("src.memory")

# config stub — get_settings() must return an object with max_tool_steps.
# We must set the attribute on the module object directly (not only via _ensure_stub attrs
# dict) because spec_from_file_location resolves `from ..config import get_settings` via
# getattr on the already-registered sys.modules["src.config"] module object.
_settings_obj = MagicMock()
_settings_obj.max_tool_steps = 20
_settings_obj.composio_api_key = "test-key"
_settings_obj.composio_user_id = "pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c"
_settings_obj.n8n_webhook_base_url = "https://example.n8n.cloud"
_settings_obj.n8n_webhook_secret = "x" * 64
_settings_obj.postgres_url = os.environ.get("POSTGRES_URL", "")
_config_stub = _ensure_stub("src.config")
_config_stub.get_settings = MagicMock(return_value=_settings_obj)  # type: ignore[attr-defined]

# prompts stub — TOOL_SYSTEM_PROMPT is referenced at import time.
# Must be set as an attribute on the module object for `from ..prompts import` to resolve.
_prompts_stub = _ensure_stub("src.prompts")
_prompts_stub.TOOL_SYSTEM_PROMPT = "stub-system-prompt"  # type: ignore[attr-defined]

# session_facts stub — same attribute-on-module pattern.
_session_facts_stub = _ensure_stub("src.utils.session_facts")
_session_facts_stub.store_fact = AsyncMock()  # type: ignore[attr-defined]
_session_facts_stub.get_fact = AsyncMock(return_value=None)  # type: ignore[attr-defined]

# room_publisher stubs
_ensure_stub(
    "src.utils.room_publisher",
    {
        "publish_tool_start": AsyncMock(return_value="call-id-stub"),
        "publish_tool_executing": AsyncMock(),
        "publish_tool_completed": AsyncMock(),
        "publish_tool_error": AsyncMock(),
        "publish_composio_event": AsyncMock(),
    },
)

# tool_logger stubs
_ensure_stub(
    "src.utils.tool_logger",
    {
        "log_composio_call": MagicMock(),
        "log_perplexity_search": MagicMock(),
    },
)

# pg_logger stubs
_ensure_stub(
    "src.utils.pg_logger",
    {
        "log_tool_error": AsyncMock(),
        "_get_pool": MagicMock(return_value=None),
        "log_turn": AsyncMock(),
        "enqueue_dlq": AsyncMock(),
        "save_session_context": AsyncMock(),
        "get_session_context": AsyncMock(return_value=None),
        "get_session_gates": AsyncMock(return_value=[]),
        "clear_session_context": AsyncMock(),
    },
)

# n8n_client stub
_ensure_stub(
    "src.utils.n8n_client",
    {"n8n_post": AsyncMock(return_value={"ok": True})},
)

# composio SDK stubs (tool_executor does not import composio directly, but
# composio_router — which is imported transitively — does)
_ensure_stub("composio")
_ensure_stub("composio.client", {"Composio": MagicMock(), "ComposioToolSet": MagicMock()})
_ensure_stub("composio.types")
_ensure_stub("composio.utils")
_ensure_stub("composio_core")
_ensure_stub("composio_core.models")

# httpx stub (used inside tool_executor for Fireworks streaming)
_httpx_stub = _ensure_stub("httpx")
_httpx_stub.AsyncClient = MagicMock()  # type: ignore[attr-defined]
_httpx_stub.RequestError = Exception  # type: ignore[attr-defined]
_httpx_stub.HTTPStatusError = Exception  # type: ignore[attr-defined]
_httpx_stub.TimeoutException = Exception  # type: ignore[attr-defined]

# jsonschema stub
_jsonschema_stub = _ensure_stub("jsonschema")
_jsonschema_stub.Draft7Validator = MagicMock()  # type: ignore[attr-defined]
_jsonschema_stub.ValidationError = Exception  # type: ignore[attr-defined]
_jsonschema_stub.SchemaError = Exception  # type: ignore[attr-defined]

# ── Load tool_executor via spec_from_file_location ───────────────────────────
import importlib.util as _ilu

_TOOL_EXECUTOR_PATH = _SRC_ROOT / "tools" / "tool_executor.py"
_MODULE_NAME = "src.tools.tool_executor"


def _load_tool_executor() -> types.ModuleType:
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = _ilu.spec_from_file_location(_MODULE_NAME, _TOOL_EXECUTOR_PATH)
    mod = _ilu.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_te = _load_tool_executor()

# Grab symbols we'll patch / assert on — bound at collection time
_evaluate_and_execute_from_speech = _te.evaluate_and_execute_from_speech
_NO_TOOL_SENTINEL: str = _te._NO_TOOL_SENTINEL  # "NO_ACTION"
_session_registry: weakref.WeakValueDictionary = _te._session_registry
_session_delegation_locks: dict = _te._session_delegation_locks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_id() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


def _timing_print(label: str, start: float) -> None:
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n[TIMING] {label}: {elapsed_ms:.1f}ms")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session_id() -> str:
    return _make_session_id()


@pytest.fixture
def mock_session() -> MagicMock:
    """A MagicMock that mimics a LiveKit AgentSession with async generate_reply."""
    sess = MagicMock()
    sess.generate_reply = AsyncMock(return_value=None)
    return sess


@pytest.fixture
def mock_session_registry(session_id: str, mock_session: MagicMock):
    """Patch _session_registry inside tool_executor to contain our mock session."""
    _session_registry[session_id] = mock_session
    yield mock_session
    _session_registry.pop(session_id, None)


@pytest.fixture
def postgres_url() -> str:
    url = os.environ.get("POSTGRES_URL", "")
    if not url:
        pytest.skip("POSTGRES_URL not set — skipping integration test")
    return url


# ---------------------------------------------------------------------------
# Class: TestEvaluateAndExecuteFromSpeech
# ---------------------------------------------------------------------------


class TestEvaluateAndExecuteFromSpeech:
    """Unit tests for evaluate_and_execute_from_speech.

    All tests in this class are fully isolated — no Railway, DB, or Composio calls.
    delegate_tools is always mocked so Fireworks is never contacted.
    """

    @pytest.mark.asyncio
    async def test_short_utterance_returns_early(self, session_id: str) -> None:
        """Transcripts with fewer than 3 words must return before calling delegate_tools.

        Uses a plain MagicMock (not AsyncMock) so no coroutine is created — avoiding
        the "coroutine was never awaited" RuntimeWarning on the never-reached call path.
        """
        start = time.perf_counter()

        with patch.object(_te, "delegate_tools", new=MagicMock()) as mock_delegate:
            # "hi there" = 2 words — below the minimum threshold
            await _evaluate_and_execute_from_speech(
                transcript="hi there",
                session_id=session_id,
            )
            mock_delegate.assert_not_called()

        _timing_print("test_short_utterance_returns_early", start)

    @pytest.mark.asyncio
    async def test_three_word_minimum_fires(self, session_id: str) -> None:
        """Exactly 3-word transcript must proceed to delegate_tools (word gate passes)."""
        start = time.perf_counter()

        with patch.object(_te, "delegate_tools", new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = _NO_TOOL_SENTINEL

            await _evaluate_and_execute_from_speech(
                transcript="schedule a meeting",  # exactly 3 words
                session_id=session_id,
            )
            mock_delegate.assert_called_once()

        _timing_print("test_three_word_minimum_fires", start)

    @pytest.mark.asyncio
    async def test_no_action_sentinel_suppresses_reply(
        self,
        session_id: str,
        mock_session_registry: MagicMock,
    ) -> None:
        """When delegate_tools returns NO_ACTION, generate_reply must NOT be called."""
        start = time.perf_counter()

        with patch.object(_te, "delegate_tools", new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = _NO_TOOL_SENTINEL

            await _evaluate_and_execute_from_speech(
                transcript="what time is it now",
                session_id=session_id,
            )

        mock_session_registry.generate_reply.assert_not_called()
        _timing_print("test_no_action_sentinel_suppresses_reply", start)

    @pytest.mark.asyncio
    async def test_gamma_suppression(
        self,
        session_id: str,
        mock_session_registry: MagicMock,
    ) -> None:
        """Gamma results must NOT trigger generate_reply — monitor owns that channel."""
        gamma_result = "Gamma presentation ready: https://gamma.app/docs/xyz-abc123"
        start = time.perf_counter()

        with patch.object(_te, "delegate_tools", new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = gamma_result

            await _evaluate_and_execute_from_speech(
                transcript="create a presentation about our Q4 roadmap",
                session_id=session_id,
            )

        mock_session_registry.generate_reply.assert_not_called()
        _timing_print("test_gamma_suppression", start)

    @pytest.mark.asyncio
    async def test_normal_result_triggers_reply(
        self,
        session_id: str,
        mock_session_registry: MagicMock,
    ) -> None:
        """A concrete tool result must trigger generate_reply with the result in instructions."""
        tool_result = "Email sent to John."
        start = time.perf_counter()

        with patch.object(_te, "delegate_tools", new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = tool_result

            await _evaluate_and_execute_from_speech(
                transcript="send John an email about tomorrow's meeting",
                session_id=session_id,
            )

        mock_session_registry.generate_reply.assert_called_once()
        call_kwargs = mock_session_registry.generate_reply.call_args.kwargs
        assert "instructions" in call_kwargs, "generate_reply must be called with instructions="
        assert tool_result[:50] in call_kwargs["instructions"], (
            f"Result text must appear in instructions. Got: {call_kwargs['instructions']!r}"
        )

        _timing_print("test_normal_result_triggers_reply", start)

    @pytest.mark.asyncio
    async def test_context_hints_passed_to_delegate(self, session_id: str) -> None:
        """context_hints dict must be forwarded verbatim to delegate_tools as context_hints=."""
        user_id = "pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c"
        hints = {"user_id": user_id}
        start = time.perf_counter()

        with patch.object(_te, "delegate_tools", new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = _NO_TOOL_SENTINEL

            await _evaluate_and_execute_from_speech(
                transcript="check my calendar for tomorrow",
                session_id=session_id,
                context_hints=hints,
            )

        mock_delegate.assert_called_once()
        captured_kwargs = mock_delegate.call_args.kwargs
        # evaluate_and_execute_from_speech passes context_hints as a keyword arg
        assert "context_hints" in captured_kwargs, (
            "delegate_tools must receive context_hints kwarg"
        )
        assert captured_kwargs["context_hints"].get("user_id") == user_id, (
            f"user_id must be preserved. Got: {captured_kwargs['context_hints']}"
        )

        _timing_print("test_context_hints_passed_to_delegate", start)

    @pytest.mark.asyncio
    async def test_recent_context_prepended_to_request(self, session_id: str) -> None:
        """recent_context entries must appear in the request string before the transcript."""
        recent = ["User: what was that slide about?", "Assistant: It covered Q3 revenue."]
        transcript = "create a slide showing those numbers"
        start = time.perf_counter()

        with patch.object(_te, "delegate_tools", new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = _NO_TOOL_SENTINEL

            await _evaluate_and_execute_from_speech(
                transcript=transcript,
                session_id=session_id,
                recent_context=recent,
            )

        mock_delegate.assert_called_once()
        captured_kwargs = mock_delegate.call_args.kwargs
        assert "request" in captured_kwargs, "delegate_tools must receive request kwarg"
        request_str: str = captured_kwargs["request"]

        # The transcript must be present
        assert transcript in request_str, (
            f"transcript must appear in request. Got: {request_str!r}"
        )

        # At least one of the recent context lines must appear (last 3 are kept per impl)
        context_present = any(
            m in request_str for m in recent
        )
        assert context_present, (
            f"recent_context lines must appear in request. Got: {request_str!r}"
        )

        # Context must come before the transcript
        for m in recent:
            if m in request_str:
                assert request_str.index(m) < request_str.index(transcript), (
                    "recent_context must precede the current transcript in the request"
                )

        _timing_print("test_recent_context_prepended_to_request", start)

    @pytest.mark.asyncio
    async def test_timeout_fires_after_300s(
        self,
        session_id: str,
        mock_session_registry: MagicMock,
    ) -> None:
        """When asyncio.wait_for raises TimeoutError, generate_reply is called with apology.

        Patches asyncio.wait_for with a synchronous callable that raises TimeoutError
        immediately, avoiding coroutine creation inside evaluate_and_execute_from_speech
        and the resulting "coroutine was never awaited" RuntimeWarning.
        """
        start = time.perf_counter()

        async def _raise_timeout(*_args: Any, **_kwargs: Any) -> str:
            raise asyncio.TimeoutError()

        with patch.object(_te, "delegate_tools", new=MagicMock()):
            with patch("asyncio.wait_for", side_effect=_raise_timeout):
                await _evaluate_and_execute_from_speech(
                    transcript="run the full quarterly lead generation pipeline",
                    session_id=session_id,
                )

        mock_session_registry.generate_reply.assert_called_once()
        call_kwargs = mock_session_registry.generate_reply.call_args.kwargs
        assert "instructions" in call_kwargs
        instructions: str = call_kwargs["instructions"].lower()
        # The instructions must communicate failure/apology — check for key semantics
        assert any(word in instructions for word in ("timeout", "timed out", "apologize", "apolog", "retry")), (
            f"Timeout apology not found in instructions: {call_kwargs['instructions']!r}"
        )

        _timing_print("test_timeout_fires_after_300s", start)


# ---------------------------------------------------------------------------
# Class: TestParallelTrackLogging
# ---------------------------------------------------------------------------


class TestParallelTrackLogging:
    """Integration and logging tests that require a live POSTGRES_URL.

    All tests in this class are marked @pytest.mark.integration and are skipped
    unless --run-integration is passed to pytest.
    """

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_evaluate_records_timing(
        self,
        session_id: str,
        postgres_url: str,
    ) -> None:
        """Run evaluate_and_execute_from_speech end-to-end and log elapsed timing to DB.

        The test does NOT assert that a real tool executes — it measures and logs
        the wall-clock time of the full function, then writes a row to tool_calls
        (or tool_call_log depending on schema) for observability.

        Integration guard: pytest.fixture postgres_url skips when POSTGRES_URL is unset.
        """
        import asyncpg  # type: ignore[import]

        transcript = "what documents did we discuss last week"
        context_hints = {"user_id": "pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c"}

        start = time.perf_counter()
        # We wrap delegate_tools to avoid actual Fireworks call while still
        # exercising the real function path (word guard, context building, etc.)
        with patch.object(_te, "delegate_tools", new_callable=AsyncMock) as mock_delegate:
            mock_delegate.return_value = _NO_TOOL_SENTINEL
            await _evaluate_and_execute_from_speech(
                transcript=transcript,
                session_id=session_id,
                context_hints=context_hints,
            )
        elapsed_ms = (time.perf_counter() - start) * 1000
        _timing_print("test_evaluate_records_timing", start)

        print(f"\n[INTEGRATION] evaluate_and_execute_from_speech elapsed: {elapsed_ms:.1f}ms")

        # Write timing observation to DB for longitudinal tracking
        try:
            conn = await asyncpg.connect(postgres_url)
            try:
                # tool_calls table may or may not exist — use a best-effort INSERT
                await conn.execute(
                    """
                    INSERT INTO tool_calls
                        (session_id, tool_name, status, duration_ms, created_at)
                    VALUES
                        ($1, $2, $3, $4, NOW())
                    ON CONFLICT DO NOTHING
                    """,
                    session_id,
                    "evaluate_and_execute_from_speech",
                    "NO_ACTION",
                    int(elapsed_ms),
                )
                print(f"[INTEGRATION] Timing row written to tool_calls. session={session_id}")
            except Exception as db_err:
                # Table may not exist or schema may differ — log and continue
                print(f"[INTEGRATION] Could not write to tool_calls: {db_err} (non-fatal)")
            finally:
                await conn.close()
        except Exception as conn_err:
            print(f"[INTEGRATION] DB connection failed: {conn_err} (non-fatal)")

        # Assert the function completed within a reasonable wall-clock budget
        # (mocked delegate_tools should resolve in < 2000ms)
        assert elapsed_ms < 2000, (
            f"evaluate_and_execute_from_speech took {elapsed_ms:.1f}ms with mocked delegate — "
            "overhead in pre-processing is unexpectedly large"
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_parallel_track_db_snapshot(self, postgres_url: str) -> None:
        """Query conversation_log for the last 10 rows and print them for inspection.

        This is a pure observability test — it never asserts on content, only on
        connectivity. Useful for post-deploy sanity checks via --run-integration.
        """
        import asyncpg  # type: ignore[import]

        start = time.perf_counter()

        conn = await asyncpg.connect(postgres_url)
        try:
            rows = await conn.fetch(
                """
                SELECT id, session_id, user_id, role, LEFT(content, 120) AS content_preview,
                       created_at
                FROM   conversation_log
                ORDER  BY created_at DESC
                LIMIT  10
                """
            )
        finally:
            await conn.close()

        _timing_print("test_parallel_track_db_snapshot", start)

        print(f"\n[SNAPSHOT] conversation_log — last {len(rows)} rows:")
        for row in rows:
            print(
                f"  id={row['id']} session={row['session_id']} "
                f"user={row['user_id']} role={row['role']} "
                f"created={row['created_at']} "
                f"content={row['content_preview']!r}"
            )

        # Connectivity assertion only
        assert isinstance(rows, list), "Expected a list of records from conversation_log"
