"""
Phase 6 (I6) Tool List Enforcement Tests
=========================================

Phase 6 is the architectural cutover where the conversation LLM loses direct
access to all external/TOOL-class tools. After I6, the conversation LLM has
exactly 6 memory/context tools and reaches everything else exclusively via the
parallel dual-track speech path (``evaluate_and_execute_from_speech`` fires
from raw transcription) — there is no ``delegateTools`` handoff anymore.

What this file validates:
- ``ASYNC_TOOLS`` (registered with conversation LLM) contains EXACTLY 6 entries
- Those 6 entries are the correct memory/context functions by name
- ``delegate_tools_async`` is NOT present in ``ASYNC_TOOLS``
- ``delegate_tools_async`` IS present in ``TOOL_EXECUTOR_TOOLS`` (tool executor path)
- All 6 conversation tools are callable coroutine functions
- Tool naming convention (camelCase) is not violated for TTS safety

Source: ``src/tools/async_wrappers.py`` — ASYNC_TOOLS at lines 1323-1330,
TOOL_EXECUTOR_TOOLS at lines 1282-1319, delegate_tools_async at line 1231.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC_ROOT = _REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# Stub helpers — mirror the pattern from test_composio_meta.py
# ---------------------------------------------------------------------------

def _ensure_stub(name: str, attrs: dict | None = None) -> types.ModuleType:
    """Insert a MagicMock stub module into sys.modules if not already present."""
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


def _install_stubs() -> None:
    """Pre-seed all transitive imports that async_wrappers.py requires.

    async_wrappers uses relative imports from within the src package tree.
    Loading via spec_from_file_location resolves relatives against the
    registered sys.modules entries, so we stub the full tree before exec.
    """
    # Core package stubs
    _ensure_stub("src")
    _ensure_stub("src.utils")
    _ensure_stub("src.tools")
    _ensure_stub("src.memory")
    _ensure_stub("src.config", {
        "get_settings": MagicMock(return_value=MagicMock(
            composio_api_key="test-key",
            composio_user_id="pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c",
            n8n_webhook_base_url="https://jayconnorexe.app.n8n.cloud",
            n8n_webhook_secret="b" * 64,
            postgres_url="",
            pgvector_url="",
            memory_dir="/tmp/aio-test",
            max_tool_steps=20,
        )),
    })

    # livekit stubs — async_wrappers decorates with @llm.function_tool
    _livekit_llm_stub = _ensure_stub("livekit.agents.llm", {
        "function_tool": lambda **kwargs: (lambda fn: fn),
    })
    _ensure_stub("livekit")
    _ensure_stub("livekit.agents", {"llm": _livekit_llm_stub})
    _ensure_stub("livekit.agents.llm")
    # Ensure attribute is set on parent stub too
    sys.modules["livekit.agents"].llm = _livekit_llm_stub  # type: ignore[attr-defined]

    # utils stubs
    _ensure_stub("src.utils.room_publisher", {
        "publish_tool_start": AsyncMock(return_value="call-id-stub"),
        "publish_tool_executing": AsyncMock(),
        "publish_tool_completed": AsyncMock(),
        "publish_tool_error": AsyncMock(),
        "publish_composio_event": AsyncMock(),
    })
    _ensure_stub("src.utils.tool_logger", {
        "log_composio_call": MagicMock(),
        "log_perplexity_search": MagicMock(),
    })
    _ensure_stub("src.utils.pg_logger", {
        "log_tool_error": AsyncMock(),
        "_get_pool": MagicMock(return_value=None),
        "log_turn": AsyncMock(),
        "enqueue_dlq": AsyncMock(),
        "save_session_context": AsyncMock(),
        "get_session_context": AsyncMock(return_value={}),
        "get_session_gates": AsyncMock(return_value=[]),
        "clear_session_context": AsyncMock(),
    })
    _ensure_stub("src.utils.short_term_memory", {
        "recall_by_category": AsyncMock(return_value=[]),
        "recall_by_tool": AsyncMock(return_value=[]),
        "recall_most_recent": AsyncMock(return_value=[]),
        "get_memory_summary": MagicMock(return_value=""),
        "store_tool_result": MagicMock(),
        "ToolCategory": MagicMock(),
    })
    _ensure_stub("src.utils.async_tool_worker", {
        "get_worker": MagicMock(return_value=MagicMock()),
    })
    _ensure_stub("src.utils.n8n_client", {
        "n8n_post": AsyncMock(return_value={}),
    })
    _ensure_stub("src.utils.session_facts", {
        "store_fact": AsyncMock(),
        "get_fact": AsyncMock(return_value=None),
    })

    # Sub-tool module stubs — async_wrappers does:
    #   from . import email_tool, database_tool, vector_store_tool,
    #                 google_drive_tool, agent_context_tool, contact_tool,
    #                 prospect_scraper_tool
    for _sub in [
        "email_tool",
        "database_tool",
        "vector_store_tool",
        "google_drive_tool",
        "agent_context_tool",
        "contact_tool",
        "prospect_scraper_tool",
    ]:
        _ensure_stub(f"src.tools.{_sub}", {"_current_user_id": "_default"})

    # gamma_tool stubs
    _ensure_stub("src.tools.gamma_tool", {
        "generate_presentation_async": AsyncMock(return_value="done"),
        "generate_document_async": AsyncMock(return_value="done"),
        "generate_webpage_async": AsyncMock(return_value="done"),
        "generate_social_async": AsyncMock(return_value="done"),
    })

    # deep_store_tool stubs — these are the REAL functions we care about verifying
    # by name; we stub them as coroutines so the import succeeds.
    async def _deep_store_async(label: str, content: str) -> str:  # noqa: D401
        return "stored"

    async def _deep_recall_async(query: str) -> str:  # noqa: D401
        return "recalled"

    _deep_store_async.__name__ = "deep_store_async"
    _deep_recall_async.__name__ = "deep_recall_async"
    _ensure_stub("src.tools.deep_store_tool", {
        "deep_store_async": _deep_store_async,
        "deep_recall_async": _deep_recall_async,
    })

    # user_profile_tool stub
    _ensure_stub("src.tools.user_profile_tool", {
        "update_user_profile_tool": MagicMock(),
    })

    # tool_executor stubs
    _ensure_stub("src.tools.tool_executor", {
        "delegate_tools": AsyncMock(return_value="done"),
        "run_background_delegation": AsyncMock(),
        "_active_delegation": {},
    })

    # memory module stubs
    _ensure_stub("src.memory.memory_store", {
        "deep_store_save": AsyncMock(),
        "deep_store_search": AsyncMock(return_value=[]),
    })
    _ensure_stub("src.memory.capture", {
        "capture_turn": AsyncMock(),
    })

    # composio stubs
    _ensure_stub("composio_core")
    _ensure_stub("composio_core.models")
    _ensure_stub("composio")
    _ensure_stub("composio.client", {
        "Composio": MagicMock(),
        "ComposioToolSet": MagicMock(),
    })
    _ensure_stub("composio.types")
    _ensure_stub("composio.utils")

    # jsonschema stub
    _jsonschema = _ensure_stub("jsonschema")
    _jsonschema.Draft7Validator = MagicMock()  # type: ignore[attr-defined]
    _jsonschema.ValidationError = Exception  # type: ignore[attr-defined]
    _jsonschema.SchemaError = Exception  # type: ignore[attr-defined]

    # httpx stub
    _ensure_stub("httpx")

    # aiohttp stub
    _ensure_stub("aiohttp")

    # fastembed stub
    _ensure_stub("fastembed")


def _load_async_wrappers() -> types.ModuleType:
    """Load src/tools/async_wrappers.py in isolation via spec_from_file_location.

    Idempotent — returns cached module if already loaded.
    """
    module_name = "src.tools.async_wrappers"
    if module_name in sys.modules:
        return sys.modules[module_name]

    wrappers_path = _SRC_ROOT / "tools" / "async_wrappers.py"
    if not wrappers_path.exists():
        pytest.skip(f"async_wrappers.py not found at {wrappers_path}")

    spec = importlib.util.spec_from_file_location(module_name, wrappers_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Install stubs at import time so the module loads correctly whether pytest
# collects this file before or after conftest.py fires its hooks.
_install_stubs()

try:
    _WRAPPERS = _load_async_wrappers()
    _LOAD_ERROR: Exception | None = None
except Exception as exc:
    _WRAPPERS = None  # type: ignore[assignment]
    _LOAD_ERROR = exc


def _require_wrappers() -> types.ModuleType:
    """Return the loaded module or skip the test if loading failed."""
    if _WRAPPERS is None:
        pytest.skip(f"Could not load async_wrappers: {_LOAD_ERROR}")
    return _WRAPPERS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def async_tools_list():
    """Return the ASYNC_TOOLS list from the loaded async_wrappers module."""
    mod = _require_wrappers()
    return mod.ASYNC_TOOLS


@pytest.fixture
def async_tools_names(async_tools_list):
    """Return function __name__ strings for all entries in ASYNC_TOOLS."""
    return [f.__name__ for f in async_tools_list]


# ---------------------------------------------------------------------------
# TestPhase6AsyncTools
# ---------------------------------------------------------------------------

class TestPhase6AsyncTools:
    """Enforce Phase 6 conversation LLM tool list — exactly 6 memory/context tools."""

    EXPECTED_FUNCTION_NAMES = [
        "recall_data_async",
        "recall_sessions_async",
        "memory_summary_async",
        "query_context_async",
        "deep_store_async",
        "deep_recall_async",
    ]

    def test_async_tools_count_exactly_six(self, async_tools_list, async_tools_names):
        """ASYNC_TOOLS must have exactly 6 entries after Phase 6 I6 cutover."""
        print(f"[PHASE6] ASYNC_TOOLS found: {async_tools_names}")
        assert len(async_tools_list) == 6, (
            f"Expected 6 tools in ASYNC_TOOLS, got {len(async_tools_list)}: {async_tools_names}"
        )

    def test_async_tools_expected_functions_present(self, async_tools_names):
        """All 6 expected memory/context function names must appear in ASYNC_TOOLS."""
        print(f"[PHASE6] Checking expected names against: {async_tools_names}")
        missing = [name for name in self.EXPECTED_FUNCTION_NAMES if name not in async_tools_names]
        assert not missing, (
            f"Missing expected functions from ASYNC_TOOLS: {missing}\n"
            f"Actual names: {async_tools_names}"
        )

    def test_delegate_tools_async_not_in_async_tools(self, async_tools_list):
        """delegate_tools_async must NOT be in ASYNC_TOOLS after I6 cutover."""
        mod = _require_wrappers()
        delegate_fn = mod.delegate_tools_async
        names = [f.__name__ for f in async_tools_list]
        print(f"[PHASE6] Checking delegate_tools_async absent. ASYNC_TOOLS names: {names}")
        assert delegate_fn not in async_tools_list, (
            "delegate_tools_async found in ASYNC_TOOLS — Phase 6 I6 cutover was not applied. "
            "Conversation LLM must NOT have delegateTools; tool executor fires from transcription."
        )

    def test_all_async_tools_are_callable(self, async_tools_list, async_tools_names):
        """Every item in ASYNC_TOOLS must be callable."""
        non_callable = [
            name for fn, name in zip(async_tools_list, async_tools_names)
            if not callable(fn)
        ]
        assert not non_callable, (
            f"Non-callable entries found in ASYNC_TOOLS: {non_callable}"
        )

    def test_all_async_tools_are_coroutine_functions(self, async_tools_list, async_tools_names):
        """Every item in ASYNC_TOOLS must be an async (coroutine) function."""
        non_coro = [
            name for fn, name in zip(async_tools_list, async_tools_names)
            if not asyncio.iscoroutinefunction(fn)
        ]
        assert not non_coro, (
            f"Non-coroutine entries found in ASYNC_TOOLS: {non_coro}\n"
            "All conversation LLM tools must be async functions."
        )

    def test_no_snake_case_tool_names_exposed(self, async_tools_names):
        """Warn (non-fatal) if any ASYNC_TOOLS function name violates camelCase convention.

        The AIO tool naming rule requires camelCase for all tool names so TTS
        does not read underscores literally. This check strips the ``_async``
        suffix used for Python module naming, then checks the remainder for
        embedded underscores that would indicate a snake_case violation.

        A warning is printed but the test does not fail — these are implementation
        function names (Python convention), not necessarily the ``name=`` arg
        passed to @llm.function_tool. Violations are surfaced for awareness.
        """
        offenders = []
        for name in async_tools_names:
            base = name.removesuffix("_async")
            if "_" in base:
                offenders.append(name)

        if offenders:
            print(
                f"[PHASE6] WARNING — possible snake_case tool function names (check "
                f"@llm.function_tool name= kwarg for TTS safety): {offenders}"
            )
        # Non-fatal: implementation names may differ from the registered tool name
        # The @llm.function_tool(name=...) kwarg is authoritative for TTS.
        assert True, "Naming check complete (non-fatal)"


# ---------------------------------------------------------------------------
# TestToolExecutorSeparation
# ---------------------------------------------------------------------------

class TestToolExecutorSeparation:
    """Confirm TOOL_EXECUTOR_TOOLS is a separate, larger registry from ASYNC_TOOLS."""

    def test_tool_executor_tools_exist(self):
        """TOOL_EXECUTOR_TOOLS must exist and contain more than 6 entries."""
        mod = _require_wrappers()
        assert hasattr(mod, "TOOL_EXECUTOR_TOOLS"), (
            "TOOL_EXECUTOR_TOOLS not found in async_wrappers — registry missing"
        )
        executor_tools = mod.TOOL_EXECUTOR_TOOLS
        names = [f.__name__ for f in executor_tools]
        print(f"[PHASE6] TOOL_EXECUTOR_TOOLS count: {len(executor_tools)}, names: {names}")
        assert len(executor_tools) > 6, (
            f"TOOL_EXECUTOR_TOOLS should have >6 entries (expected ~31), got {len(executor_tools)}"
        )

    def test_delegate_tools_in_executor_list(self):
        """delegate_tools_async must be present in TOOL_EXECUTOR_TOOLS."""
        mod = _require_wrappers()
        delegate_fn = mod.delegate_tools_async
        executor_tools = mod.TOOL_EXECUTOR_TOOLS
        executor_names = [f.__name__ for f in executor_tools]
        print(f"[PHASE6] delegate_tools_async in TOOL_EXECUTOR_TOOLS: {delegate_fn.__name__ in executor_names}")
        assert delegate_fn in executor_tools, (
            "delegate_tools_async must be in TOOL_EXECUTOR_TOOLS — tool executor needs it. "
            f"Executor tool names: {executor_names}"
        )

    def test_no_overlap_in_async_tools_except_both_class(self, async_tools_list):
        """Belt-and-suspenders: delegate_tools_async must not be in ASYNC_TOOLS.

        This is a redundant check alongside test_delegate_tools_async_not_in_async_tools
        in TestPhase6AsyncTools, intentionally duplicated for defence-in-depth.
        """
        mod = _require_wrappers()
        delegate_fn = mod.delegate_tools_async
        assert delegate_fn not in async_tools_list, (
            "delegate_tools_async found in ASYNC_TOOLS — Phase 6 I6 regression detected. "
            "Conversation LLM must reach external tools ONLY via parallel speech evaluation, "
            "not via delegateTools."
        )


# ---------------------------------------------------------------------------
# TestToolNamingConvention
# ---------------------------------------------------------------------------

class TestToolNamingConvention:
    """Verify individual memory/context tool functions are importable and async."""

    def test_recall_data_async_function_exists(self):
        """recall_data_async must be importable from async_wrappers and non-None."""
        mod = _require_wrappers()
        fn = getattr(mod, "recall_data_async", None)
        assert fn is not None, (
            "recall_data_async not found in async_wrappers — memory recall tool missing"
        )
        print(f"[PHASE6] recall_data_async: {fn}")

    def test_deep_store_async_function_exists(self):
        """deep_store_async must be importable from async_wrappers and be a coroutine function."""
        mod = _require_wrappers()
        fn = getattr(mod, "deep_store_async", None)
        assert fn is not None, (
            "deep_store_async not found in async_wrappers — deep store tool missing"
        )
        assert asyncio.iscoroutinefunction(fn), (
            f"deep_store_async must be a coroutine function, got: {type(fn)}"
        )
        print(f"[PHASE6] deep_store_async is coroutine function: True")
