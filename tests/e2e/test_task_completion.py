"""AIO Voice Agent — Task Completion Consistency E2E Tests.

Verifies that the tool_executor module's gate sentinel, session lifecycle,
context trimming, and async_wrappers registry behave correctly.

Categories:
    1. GATE sentinel format          (3 tests, unit)
    2. Session lifecycle             (3 tests, unit)
    3. Context trimming              (3 tests, unit)
    4. Async wrappers integration    (2 tests, unit)
    5. Live delegation integration   (2 tests, integration marker)

Loading strategy:
    tool_executor.py has relative imports (..config, ..prompts, ..utils.*).
    We pre-stub every dependency in sys.modules before loading so the
    module executes in isolation without a real Railway environment.

    async_wrappers.py additionally imports livekit.agents.llm at module
    level. We stub that too, then load it the same way.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SRC_ROOT = _REPO_ROOT / "src"
_TOOL_EXECUTOR_PATH = _SRC_ROOT / "tools" / "tool_executor.py"
_ASYNC_WRAPPERS_PATH = _SRC_ROOT / "tools" / "async_wrappers.py"


# ---------------------------------------------------------------------------
# Minimal stub builders
# ---------------------------------------------------------------------------

def _make_stub(name: str) -> ModuleType:
    """Return a MagicMock registered under *name* in sys.modules."""
    stub = MagicMock(spec=ModuleType(name))
    stub.__name__ = name
    stub.__spec__ = None
    sys.modules[name] = stub
    return stub


def _ensure_parent_packages(dotted: str) -> None:
    """Register empty parent package stubs so relative imports resolve."""
    parts = dotted.split(".")
    for i in range(1, len(parts)):
        pkg_name = ".".join(parts[:i])
        if pkg_name not in sys.modules:
            pkg = ModuleType(pkg_name)
            pkg.__path__ = []  # marks it as a package
            pkg.__package__ = pkg_name
            sys.modules[pkg_name] = pkg


def _stub_tool_executor_deps() -> None:
    """Pre-stub every dependency imported by tool_executor.py."""
    # Outer package hierarchy
    _ensure_parent_packages("src.tools.tool_executor")

    stubs = [
        "src",
        "src.config",
        "src.prompts",
        "src.utils",
        "src.utils.session_facts",
        "src.utils.pg_logger",
        # httpx is a real package but may not be installed in test env
    ]
    for name in stubs:
        if name not in sys.modules:
            _make_stub(name)

    # get_settings must return an object with fireworks_api_key + max_tool_steps
    settings_mock = MagicMock()
    settings_mock.fireworks_api_key = "test-fw-key"
    settings_mock.max_tool_steps = 20
    settings_mock.postgres_url = os.environ.get("POSTGRES_URL", "")
    sys.modules["src.config"].get_settings = MagicMock(return_value=settings_mock)

    # prompts module needs TOOL_SYSTEM_PROMPT string
    sys.modules["src.prompts"].TOOL_SYSTEM_PROMPT = "You are the tool executor. Be concise."

    # session_facts: store_fact is called fire-and-forget
    sys.modules["src.utils.session_facts"].store_fact = AsyncMock()

    # pg_logger: save_session_context is called in requestGate try/except
    sys.modules["src.utils.pg_logger"].save_session_context = AsyncMock()

    # httpx — stub if not importable
    try:
        import httpx  # noqa: F401
    except ImportError:
        _make_stub("httpx")


def _load_tool_executor() -> ModuleType:
    """Load tool_executor.py via spec_from_file_location and return the module."""
    mod_name = "src.tools.tool_executor"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    _stub_tool_executor_deps()

    spec = importlib.util.spec_from_file_location(mod_name, _TOOL_EXECUTOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src.tools"
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _stub_async_wrappers_deps() -> None:
    """Pre-stub every dependency imported by async_wrappers.py."""
    _ensure_parent_packages("src.tools.async_wrappers")

    # livekit hierarchy
    lk_stub = _make_stub("livekit")
    lk_agents_stub = _make_stub("livekit.agents")
    lk_llm_stub = _make_stub("livekit.agents.llm")

    # @llm.function_tool decorator must be a pass-through (returns the decorated fn)
    def _passthrough_decorator(*args, **kwargs):
        """Return a decorator that returns the original function unchanged."""
        def _inner(fn):
            return fn
        # Handle both @llm.function_tool and @llm.function_tool(name=...) usage
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return _inner

    lk_llm_stub.function_tool = _passthrough_decorator
    lk_agents_stub.llm = lk_llm_stub

    stubs_needed = [
        "src.utils.async_tool_worker",
        "src.utils.room_publisher",
        "src.utils.short_term_memory",
        "src.utils.tool_logger",
        "src.tools",
        "src.tools.email_tool",
        "src.tools.database_tool",
        "src.tools.vector_store_tool",
        "src.tools.google_drive_tool",
        "src.tools.agent_context_tool",
        "src.tools.contact_tool",
        "src.tools.prospect_scraper_tool",
        "src.tools.gamma_tool",
        "src.tools.deep_store_tool",
        "src.tools.user_profile_tool",
        "src.tools.composio_router",
        "src.memory",
        "src.memory.memory_store",
        "src.memory.capture",
        "aiohttp",
    ]
    for name in stubs_needed:
        if name not in sys.modules:
            _make_stub(name)

    # async_tool_worker.get_worker must return None (no background worker in tests)
    sys.modules["src.utils.async_tool_worker"].get_worker = MagicMock(return_value=None)

    # room_publisher: all publish_* are AsyncMocks returning a call_id string
    pub = sys.modules["src.utils.room_publisher"]
    pub.publish_tool_start = AsyncMock(return_value="call-test-id")
    pub.publish_tool_executing = AsyncMock(return_value=None)
    pub.publish_tool_completed = AsyncMock(return_value=None)
    pub.publish_tool_error = AsyncMock(return_value=None)

    # short_term_memory exports
    stm = sys.modules["src.utils.short_term_memory"]
    stm.recall_by_category = MagicMock(return_value=None)
    stm.recall_by_tool = MagicMock(return_value=None)
    stm.recall_most_recent = MagicMock(return_value=None)
    stm.get_memory_summary = MagicMock(return_value="Memory summary: empty")
    stm.store_tool_result = MagicMock(return_value=None)
    stm.ToolCategory = MagicMock()

    # gamma_tool exports used directly (not via the module stub)
    sys.modules["src.tools.gamma_tool"].generate_presentation_async = AsyncMock(return_value="Presentation done")
    sys.modules["src.tools.gamma_tool"].generate_document_async = AsyncMock(return_value="Document done")
    sys.modules["src.tools.gamma_tool"].generate_webpage_async = AsyncMock(return_value="Webpage done")
    sys.modules["src.tools.gamma_tool"].generate_social_async = AsyncMock(return_value="Social done")

    # deep_store_tool
    sys.modules["src.tools.deep_store_tool"].deep_store_async = AsyncMock(return_value="Stored")
    sys.modules["src.tools.deep_store_tool"].deep_recall_async = AsyncMock(return_value="Recalled")

    # user_profile_tool
    sys.modules["src.tools.user_profile_tool"].update_user_profile_tool = AsyncMock(return_value="Profile updated")

    # tool_executor — must already be loaded (delegate_tools_impl import)
    # If not present yet, stub it to avoid circular load
    te_name = "src.tools.tool_executor"
    if te_name not in sys.modules:
        te_stub = _make_stub(te_name)
        te_stub.delegate_tools = AsyncMock(return_value="Delegated")


def _load_async_wrappers() -> ModuleType:
    """Load async_wrappers.py via spec_from_file_location and return the module."""
    mod_name = "src.tools.async_wrappers"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    # tool_executor must be loaded first — async_wrappers imports from it
    _load_tool_executor()
    _stub_async_wrappers_deps()

    spec = importlib.util.spec_from_file_location(mod_name, _ASYNC_WRAPPERS_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "src.tools"
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Module-level fixtures — loaded once per session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def te_mod() -> ModuleType:
    """tool_executor module loaded in isolation."""
    return _load_tool_executor()


@pytest.fixture(scope="session")
def aw_mod() -> ModuleType:
    """async_wrappers module loaded in isolation."""
    return _load_async_wrappers()


# ---------------------------------------------------------------------------
# Category 1: GATE sentinel format (3 tests, unit)
# ---------------------------------------------------------------------------

class TestGateSentinelFormat:
    """Verify the __GATE__: sentinel constant and requestGate return shape."""

    def test_gate_sentinel_prefix_value(self, te_mod):
        """_GATE_SENTINEL constant must equal the documented literal."""
        assert te_mod._GATE_SENTINEL == "__GATE__:"

    async def test_request_gate_returns_sentinel_prefix(self, te_mod):
        """requestGate() must return a string that begins with __GATE__:."""
        pg_logger_stub = sys.modules.get("src.utils.pg_logger")
        if pg_logger_stub is not None:
            pg_logger_stub.save_session_context = AsyncMock()

        with patch.object(
            sys.modules["src.utils.pg_logger"],
            "save_session_context",
            new_callable=AsyncMock,
        ):
            result = await te_mod.requestGate(
                gate_type="WRITE",
                content="Send email?",
                voice_prompt="Shall I send?",
            )

        assert isinstance(result, str)
        assert result.startswith("__GATE__:")

    async def test_request_gate_payload_structure(self, te_mod):
        """The JSON payload after __GATE__: must contain all required keys."""
        with patch.object(
            sys.modules["src.utils.pg_logger"],
            "save_session_context",
            new_callable=AsyncMock,
        ):
            result = await te_mod.requestGate(
                gate_type="WRITE",
                content="Send email to Alice?",
                voice_prompt="Shall I send the email to Alice?",
                continuation_hint="Then confirm with user",
            )

        sentinel_prefix = te_mod._GATE_SENTINEL  # "__GATE__:"
        assert result.startswith(sentinel_prefix)

        raw_json = result[len(sentinel_prefix):]
        payload = json.loads(raw_json)

        required_keys = {"gate_id", "gate_type", "content", "voice_prompt", "session_id", "timestamp"}
        for key in required_keys:
            assert key in payload, f"Missing key in gate payload: {key!r}"

        assert payload["gate_type"] == "WRITE"
        assert payload["content"] == "Send email to Alice?"
        assert payload["voice_prompt"] == "Shall I send the email to Alice?"


# ---------------------------------------------------------------------------
# Category 2: Session lifecycle (3 tests, unit)
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    """Verify cleanup_session and is_delegation_active behaviour."""

    def test_cleanup_session_removes_context(self, te_mod):
        """cleanup_session must remove the session from _tool_session_chat_ctx."""
        session_id = "test-session-ctx-001"
        te_mod._tool_session_chat_ctx[session_id] = [
            {"role": "system", "content": "You are AIO."},
            {"role": "user", "content": "Hello"},
        ]
        assert session_id in te_mod._tool_session_chat_ctx

        te_mod.cleanup_session(session_id)

        assert session_id not in te_mod._tool_session_chat_ctx

    def test_cleanup_session_removes_delegation(self, te_mod):
        """cleanup_session must remove the session from _active_delegation."""
        session_id = "test-session-deleg-001"
        fake_task = MagicMock()
        te_mod._active_delegation[session_id] = {fake_task}
        assert session_id in te_mod._active_delegation

        te_mod.cleanup_session(session_id)

        assert session_id not in te_mod._active_delegation

    def test_is_delegation_active_false_for_unknown_session(self, te_mod):
        """is_delegation_active must return False for a session not in the dict."""
        result = te_mod.is_delegation_active("no-such-session-xyzabc")
        assert result is False


# ---------------------------------------------------------------------------
# Category 3: Context trimming (3 tests, unit)
# ---------------------------------------------------------------------------

class TestContextTrimming:
    """Verify _trim_tool_context retention policy."""

    def _build_base_ctx(self) -> list[dict]:
        """Return a single system message as the base."""
        return [{"role": "system", "content": "You are the tool executor."}]

    def test_trim_context_keeps_system_messages(self, te_mod):
        """System messages must always be retained after trimming."""
        session_id = "trim-test"

        # 1 system + 45 plain user/assistant pairs — total 46, exceeds threshold of 40
        ctx: list[dict] = [{"role": "system", "content": "System prompt here."}]
        for i in range(45):
            role = "user" if i % 2 == 0 else "assistant"
            ctx.append({"role": role, "content": f"Message {i}"})

        te_mod._tool_session_chat_ctx[session_id] = ctx

        te_mod._trim_tool_context(session_id)

        result = te_mod._tool_session_chat_ctx[session_id]
        system_msgs_in_result = [m for m in result if m.get("role") == "system"]
        assert len(system_msgs_in_result) == 1
        assert system_msgs_in_result[0]["content"] == "System prompt here."

    def test_trim_context_keeps_all_tool_call_messages(self, te_mod):
        """Assistant messages with tool_calls must always be retained."""
        session_id = "trim-test2"

        ctx: list[dict] = [{"role": "system", "content": "System."}]
        # Add 3 assistant messages that carry tool_calls
        tool_call_msgs = []
        for i in range(3):
            msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": f"call_{i}", "function": {"name": "sendEmail", "arguments": "{}"}}],
            }
            tool_call_msgs.append(msg)
            ctx.append(msg)

        # Pad to >40 total with plain user messages
        for i in range(40):
            ctx.append({"role": "user", "content": f"Filler user message {i}"})

        te_mod._tool_session_chat_ctx[session_id] = ctx

        te_mod._trim_tool_context(session_id)

        result = te_mod._tool_session_chat_ctx[session_id]
        result_with_tool_calls = [m for m in result if m.get("tool_calls")]
        assert len(result_with_tool_calls) == 3, (
            f"Expected 3 tool_call assistant messages to be retained, "
            f"got {len(result_with_tool_calls)}"
        )
        for msg in tool_call_msgs:
            assert msg in result, "A tool_call assistant message was dropped by trim"

    def test_trim_context_keeps_last_5_tool_results(self, te_mod):
        """Only the last 5 role='tool' messages must survive trimming."""
        session_id = "trim-test3"

        ctx: list[dict] = [{"role": "system", "content": "System."}]
        tool_msgs = []
        for i in range(10):
            msg = {
                "role": "tool",
                "tool_call_id": f"call_{i}",
                "content": f"Tool result {i}",
            }
            tool_msgs.append(msg)
            ctx.append(msg)

        # Add enough filler to exceed the 40-message threshold
        for i in range(35):
            ctx.append({"role": "user", "content": f"Filler {i}"})

        te_mod._tool_session_chat_ctx[session_id] = ctx

        te_mod._trim_tool_context(session_id)

        result = te_mod._tool_session_chat_ctx[session_id]
        remaining_tool_msgs = [m for m in result if m.get("role") == "tool"]
        assert len(remaining_tool_msgs) == 5, (
            f"Expected 5 tool result messages after trim, got {len(remaining_tool_msgs)}"
        )
        # The retained messages must be the last 5 (indices 5–9)
        expected_last_5 = tool_msgs[-5:]
        for msg in expected_last_5:
            assert msg in remaining_tool_msgs, (
                f"Expected tool result {msg['content']!r} to be retained but it was dropped"
            )
        # The first 5 tool messages must have been dropped
        dropped = tool_msgs[:5]
        for msg in dropped:
            assert msg not in remaining_tool_msgs, (
                f"Tool result {msg['content']!r} should have been trimmed but was kept"
            )


# ---------------------------------------------------------------------------
# Category 4: Async wrappers integration (2 tests, unit)
# ---------------------------------------------------------------------------

class TestAsyncWrappersIntegration:
    """Verify ASYNC_TOOLS and TOOL_EXECUTOR_TOOLS registry correctness."""

    def test_async_tools_contains_delegate_tools(self, aw_mod):
        """ASYNC_TOOLS must include a function whose LiveKit tool name is 'delegateTools'."""
        async_tools = aw_mod.ASYNC_TOOLS
        assert async_tools, "ASYNC_TOOLS is empty"

        # Each entry is a function decorated with @llm.function_tool.
        # In the stubbed environment the decorator is a pass-through, so the
        # Python callable name is delegate_tools_async.
        # We match on __name__ only — getattr(..., "name") can return an AsyncMock
        # whose .lower() produces a coroutine rather than a string, so we avoid it.
        found = False
        for fn in async_tools:
            fn_name = fn.__name__ if hasattr(fn, "__name__") and isinstance(fn.__name__, str) else ""
            if "delegate" in fn_name.lower():
                found = True
                break

        assert found, (
            "ASYNC_TOOLS does not contain a function whose __name__ includes 'delegate'. "
            f"Present names: {[getattr(f, '__name__', repr(f)) for f in async_tools]}"
        )

    def test_tool_executor_tools_is_superset_of_async_tools(self, aw_mod):
        """Every function in ASYNC_TOOLS must also appear in TOOL_EXECUTOR_TOOLS."""
        async_tools = aw_mod.ASYNC_TOOLS
        tool_executor_tools = aw_mod.TOOL_EXECUTOR_TOOLS

        assert async_tools, "ASYNC_TOOLS is empty — nothing to check"
        assert tool_executor_tools, "TOOL_EXECUTOR_TOOLS is empty"

        for fn in async_tools:
            assert fn in tool_executor_tools, (
                f"Function {getattr(fn, '__name__', fn)!r} is in ASYNC_TOOLS "
                f"but missing from TOOL_EXECUTOR_TOOLS"
            )


# ---------------------------------------------------------------------------
# Category 5: Live delegation integration (2 tests, integration marker)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestLiveDelegation:
    """Live end-to-end delegation tests — require --run-integration and POSTGRES_URL."""

    @pytest.fixture(autouse=True)
    def require_postgres_url(self):
        """Skip the entire class if POSTGRES_URL is not set in the environment."""
        if not os.environ.get("POSTGRES_URL"):
            pytest.skip("POSTGRES_URL not set — skipping live delegation tests")

    async def test_delegate_tools_simple_request(self, te_mod):
        """delegate_tools must return a non-trivial string for a read-only request.

        Uses a request that should not trigger a gate (list/status, no writes).
        """
        session_id = f"int-test-{uuid.uuid4().hex[:8]}"
        result = await te_mod.delegate_tools(
            session_id=session_id,
            request="List connected services",
            context_hints={},
            say_callback=None,
            task_tracker=None,
            pg_logger_module=None,
        )

        assert isinstance(result, str), f"Expected str, got {type(result)}"
        assert len(result) > 10, (
            f"Result too short ({len(result)} chars), expected meaningful output. "
            f"Got: {result!r}"
        )

        # Cleanup to avoid state leakage between tests
        te_mod.cleanup_session(session_id)

    async def test_delegate_tools_gate_request(self, te_mod):
        """delegate_tools for a write-like request must either gate or execute.

        A gate sentinel is the correct response. A plain string result (tool
        executed) is also acceptable — the LLM decides whether to gate based on
        session context and system prompt interpretation.
        """
        session_id = f"int-test-{uuid.uuid4().hex[:8]}"
        result = await te_mod.delegate_tools(
            session_id=session_id,
            request="Send email to test@test.com saying hello",
            context_hints={},
            say_callback=None,
            task_tracker=None,
            pg_logger_module=None,
        )

        assert isinstance(result, str), f"Expected str, got {type(result)}"

        if result.startswith(te_mod._GATE_SENTINEL):
            # Gate was triggered — verify the payload is well-formed
            raw_json = result[len(te_mod._GATE_SENTINEL):]
            try:
                payload = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                pytest.fail(f"Gate sentinel payload is not valid JSON: {exc}\nRaw: {raw_json!r}")

            assert "gate_id" in payload, "Gate payload missing gate_id"
            assert "gate_type" in payload, "Gate payload missing gate_type"
            assert "voice_prompt" in payload, "Gate payload missing voice_prompt"
        else:
            # Tool executed without a gate — still a valid outcome
            assert len(result) > 0, "Empty result from delegate_tools"

        te_mod.cleanup_session(session_id)
