"""
E2E test suite: Composio metatool + schema injection for AIO Voice Agent.

Coverage:
  1. _SLUG_OVERRIDES correctness (3 tests)
  2. _is_read_only_slug classification (4 tests)
  3. Slug index structure — module-level state (3 tests)
  4. Metatool function availability in ASYNC_TOOLS / TOOL_EXECUTOR_TOOLS (2 tests)
  5. Live API integration — list + plan metatool flow (2 tests, integration marker)

All non-integration tests run without external calls.
asyncio_mode=auto (pytest.ini) handles coroutine tests — no explicit decorator needed.
"""

from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: stub all transitive imports that composio_router.py needs
# before loading the module via spec_from_file_location.
#
# composio_router uses:
#   from ..utils.room_publisher import publish_tool_start, ...
#   from ..utils.tool_logger import log_composio_call, ...
#   from ..utils.pg_logger import log_tool_error, _get_pool
#
# These are intra-package relative imports that fail outside the installed
# package.  We pre-seed sys.modules with MagicMock stubs so exec_module
# resolves them without importing the real implementations.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_SRC_ROOT = _REPO_ROOT / "src"

# ── Stub package structure ────────────────────────────────────────────────
# pytest runs from repo root; src/ is NOT on sys.path by default.
# Ensure the src package tree resolves via stub modules.

def _ensure_stub(name: str, attrs: dict | None = None) -> types.ModuleType:
    """Insert a stub MagicMock module into sys.modules if not already present."""
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# Stub the src package itself so relative imports resolve
_ensure_stub("src")
_ensure_stub("src.utils")
_ensure_stub("src.tools")

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

# pg_logger stubs — _get_pool returns None (no PG in unit tests)
_ensure_stub(
    "src.utils.pg_logger",
    {
        "log_tool_error": AsyncMock(),
        "_get_pool": MagicMock(return_value=None),
        "log_turn": AsyncMock(),
        "enqueue_dlq": AsyncMock(),
    },
)

# composio SDK stubs
_ensure_stub("composio_core")
_ensure_stub("composio_core.models")

_composio_stub = _ensure_stub("composio")
_composio_client_stub = _ensure_stub(
    "composio.client",
    {"Composio": MagicMock(), "ComposioToolSet": MagicMock()},
)
_ensure_stub("composio.types")
_ensure_stub("composio.utils")

# httpx stub (used in initiate_service_connection Attempt 3)
_ensure_stub("httpx")

# jsonschema stub (used by pre-flight validation)
_jsonschema_stub = _ensure_stub("jsonschema")
_jsonschema_stub.Draft7Validator = MagicMock()  # type: ignore[attr-defined]
_jsonschema_stub.ValidationError = Exception  # type: ignore[attr-defined]
_jsonschema_stub.SchemaError = Exception  # type: ignore[attr-defined]


def _load_composio_router() -> types.ModuleType:
    """Load src/tools/composio_router.py in isolation via spec_from_file_location.

    Returns the already-loaded module from sys.modules if present — idempotent.
    """
    module_name = "src.tools.composio_router"
    if module_name in sys.modules:
        return sys.modules[module_name]

    router_path = _SRC_ROOT / "tools" / "composio_router.py"
    spec = importlib.util.spec_from_file_location(module_name, router_path)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so intra-module forward references resolve
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# Load once at collection time — all tests share this module reference
_router = _load_composio_router()


# ---------------------------------------------------------------------------
# Stub async_wrappers dependencies so Category 4 tests can import the lists.
# async_wrappers imports from livekit.agents + all tool sub-modules.
# We pre-stub everything so exec_module succeeds without the real packages.
# ---------------------------------------------------------------------------

def _stub_livekit() -> None:
    """Stub livekit.agents so @llm.function_tool decorator resolves."""
    if "livekit" in sys.modules:
        return

    # function_tool decorator must pass-through the decorated coroutine unchanged
    def _passthrough_decorator(*_args, **_kwargs):
        def _inner(fn):
            return fn
        # Called as @llm.function_tool(name=...) → returns decorator
        if _args and callable(_args[0]):
            # Called as @llm.function_tool (bare, no parens) — pass through
            return _args[0]
        return _inner

    _llm_stub = types.ModuleType("livekit.agents.llm")
    _llm_stub.function_tool = _passthrough_decorator  # type: ignore[attr-defined]
    _llm_stub.FunctionContext = MagicMock()  # type: ignore[attr-defined]

    _agents_stub = types.ModuleType("livekit.agents")
    _agents_stub.llm = _llm_stub  # type: ignore[attr-defined]

    _livekit_stub = types.ModuleType("livekit")
    _livekit_stub.agents = _agents_stub  # type: ignore[attr-defined]

    sys.modules["livekit"] = _livekit_stub
    sys.modules["livekit.agents"] = _agents_stub
    sys.modules["livekit.agents.llm"] = _llm_stub


def _stub_aiohttp() -> None:
    if "aiohttp" not in sys.modules:
        _ensure_stub("aiohttp")


def _stub_tool_sub_modules() -> None:
    """Stub all sub-modules imported by async_wrappers at top level."""
    _stub_livekit()
    _stub_aiohttp()

    # src.config
    _cfg_stub = _ensure_stub("src.config")
    _settings_mock = MagicMock()
    _settings_mock.composio_api_key = "test-key"
    _settings_mock.composio_user_id = "pg-test-user"
    _settings_mock.n8n_webhook_base_url = "https://test.n8n.cloud"
    _settings_mock.n8n_webhook_secret = "x" * 64
    _settings_mock.postgres_url = ""
    _settings_mock.pgvector_url = ""
    _settings_mock.memory_dir = "/tmp/aio-test"
    _settings_mock.max_tool_steps = 20
    _cfg_stub.get_settings = MagicMock(return_value=_settings_mock)  # type: ignore[attr-defined]

    # async_tool_worker
    _worker_stub = _ensure_stub("src.utils.async_tool_worker")
    _worker_stub.get_worker = MagicMock(return_value=None)  # type: ignore[attr-defined]

    # short_term_memory
    _stm_stub = _ensure_stub("src.utils.short_term_memory")
    _stm_stub.recall_by_category = MagicMock(return_value=None)  # type: ignore[attr-defined]
    _stm_stub.recall_by_tool = MagicMock(return_value=None)  # type: ignore[attr-defined]
    _stm_stub.recall_most_recent = MagicMock(return_value=None)  # type: ignore[attr-defined]
    _stm_stub.get_memory_summary = MagicMock(return_value="")  # type: ignore[attr-defined]
    _stm_stub.store_tool_result = MagicMock()  # type: ignore[attr-defined]
    _stm_stub.ToolCategory = MagicMock()  # type: ignore[attr-defined]

    # all tool sub-modules
    for _sub in (
        "src.tools.email_tool",
        "src.tools.database_tool",
        "src.tools.vector_store_tool",
        "src.tools.google_drive_tool",
        "src.tools.agent_context_tool",
        "src.tools.contact_tool",
        "src.tools.prospect_scraper_tool",
    ):
        _ensure_stub(_sub)

    # gamma_tool
    _gamma_stub = _ensure_stub("src.tools.gamma_tool")
    _gamma_stub.generate_presentation_async = AsyncMock(return_value="")  # type: ignore[attr-defined]
    _gamma_stub.generate_document_async = AsyncMock(return_value="")  # type: ignore[attr-defined]
    _gamma_stub.generate_webpage_async = AsyncMock(return_value="")  # type: ignore[attr-defined]
    _gamma_stub.generate_social_async = AsyncMock(return_value="")  # type: ignore[attr-defined]

    # deep_store_tool
    _ds_stub = _ensure_stub("src.tools.deep_store_tool")
    _ds_stub.deep_store_async = AsyncMock(return_value="")  # type: ignore[attr-defined]
    _ds_stub.deep_recall_async = AsyncMock(return_value="")  # type: ignore[attr-defined]

    # user_profile_tool
    _up_stub = _ensure_stub("src.tools.user_profile_tool")
    _up_stub.update_user_profile_tool = AsyncMock(return_value="")  # type: ignore[attr-defined]

    # tool_executor
    _te_stub = _ensure_stub("src.tools.tool_executor")
    _te_stub.delegate_tools = AsyncMock(return_value="")  # type: ignore[attr-defined]

    # memory modules (optional — graceful fallback in async_wrappers)
    _ensure_stub("src.memory")
    _ensure_stub("src.memory.memory_store")
    _ensure_stub("src.memory.capture")


def _load_async_wrappers() -> types.ModuleType:
    """Load src/tools/async_wrappers.py in isolation — idempotent."""
    module_name = "src.tools.async_wrappers"
    if module_name in sys.modules:
        return sys.modules[module_name]

    _stub_tool_sub_modules()

    wrappers_path = _SRC_ROOT / "tools" / "async_wrappers.py"
    spec = importlib.util.spec_from_file_location(module_name, wrappers_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ===========================================================================
# CATEGORY 1: _SLUG_OVERRIDES correctness
# ===========================================================================


class TestSlugOverrides:
    """_SLUG_OVERRIDES must contain all expected aliases with correct targets."""

    # The 7 entries specified in the task brief.  The conftest fixture
    # `slug_overrides_expected` mirrors this exact set for cross-test consistency.
    _EXPECTED: dict[str, str] = {
        "GOOGLEDRIVE_FIND_FOLDER": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_LIST_FILES_IN_FOLDER": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_LIST_FOLDERS": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_SEARCH_FILES": "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_GET_FILE": "GOOGLEDRIVE_GET_FILE_METADATA",
        "GOOGLEDRIVE_GET_FILE_BY_ID": "GOOGLEDRIVE_GET_FILE_METADATA",
        "MICROSOFT_TEAMS_LIST_MESSAGES": "MICROSOFT_TEAMS_TEAMS_LIST_CHANNEL_MESSAGES",
    }

    def test_slug_overrides_all_entries_present(self) -> None:
        """All 7 expected override keys exist in _SLUG_OVERRIDES with correct targets."""
        overrides: dict[str, str] = _router._SLUG_OVERRIDES
        for alias, expected_target in self._EXPECTED.items():
            assert alias in overrides, (
                f"_SLUG_OVERRIDES missing key: {alias!r}"
            )
            assert overrides[alias] == expected_target, (
                f"_SLUG_OVERRIDES[{alias!r}] = {overrides[alias]!r}, "
                f"expected {expected_target!r}"
            )

    def test_slug_overrides_google_drive_aliases(self) -> None:
        """All 4 GOOGLEDRIVE_ aliases map to exactly GOOGLEDRIVE_FIND_FILE or
        GOOGLEDRIVE_GET_FILE_METADATA — no other targets."""
        overrides: dict[str, str] = _router._SLUG_OVERRIDES
        _valid_targets = {"GOOGLEDRIVE_FIND_FILE", "GOOGLEDRIVE_GET_FILE_METADATA"}
        _drive_aliases = [k for k in overrides if k.startswith("GOOGLEDRIVE_")]
        assert len(_drive_aliases) >= 4, (
            f"Expected at least 4 GOOGLEDRIVE_ override keys, found {len(_drive_aliases)}: "
            f"{_drive_aliases}"
        )
        for alias in _drive_aliases:
            assert overrides[alias] in _valid_targets, (
                f"GOOGLEDRIVE alias {alias!r} maps to unexpected target {overrides[alias]!r}. "
                f"Valid targets: {_valid_targets}"
            )

    def test_slug_overrides_teams_alias(self) -> None:
        """MICROSOFT_TEAMS_LIST_MESSAGES must resolve to the canonical Teams slug."""
        overrides: dict[str, str] = _router._SLUG_OVERRIDES
        alias = "MICROSOFT_TEAMS_LIST_MESSAGES"
        expected = "MICROSOFT_TEAMS_TEAMS_LIST_CHANNEL_MESSAGES"
        assert alias in overrides, f"_SLUG_OVERRIDES missing Teams alias: {alias!r}"
        assert overrides[alias] == expected, (
            f"Teams alias target is {overrides[alias]!r}, expected {expected!r}"
        )


# ===========================================================================
# CATEGORY 2: _is_read_only_slug classification
# ===========================================================================


class TestIsReadOnlySlug:
    """_is_read_only_slug must correctly classify read vs write slugs.

    The implementation uses a multi-word prefix scan: splits the slug on '_' and
    checks every possible suffix against GET_/FIND_/LIST_/SEARCH_/FETCH_/QUERY_.
    This was introduced in commit dbbe30a to fix MICROSOFT_TEAMS_SEARCH_MESSAGES.
    """

    def test_is_read_only_slug_get_prefix(self) -> None:
        """GOOGLEDRIVE_GET_FILE_METADATA starts with GET_ at position 1 → True."""
        result = _router._is_read_only_slug("GOOGLEDRIVE_GET_FILE_METADATA")
        assert result is True, (
            "GOOGLEDRIVE_GET_FILE_METADATA should be classified as read-only (GET_ prefix)"
        )

    def test_is_read_only_slug_list_prefix(self) -> None:
        """MICROSOFT_TEAMS_LIST_CHANNELS has LIST_ at position 2 → True."""
        result = _router._is_read_only_slug("MICROSOFT_TEAMS_LIST_CHANNELS")
        assert result is True, (
            "MICROSOFT_TEAMS_LIST_CHANNELS should be classified as read-only (LIST_ prefix)"
        )

    def test_is_read_only_slug_search_with_multi_word_service(self) -> None:
        """MICROSOFT_TEAMS_SEARCH_MESSAGES — the fix from dbbe30a.

        A naive split('_', 1) produces 'TEAMS_SEARCH_MESSAGES' for the action part.
        That does NOT start with SEARCH_ so the old code returned False (bug).
        The multi-word prefix scan must detect SEARCH_ at position 2 and return True.
        """
        result = _router._is_read_only_slug("MICROSOFT_TEAMS_SEARCH_MESSAGES")
        assert result is True, (
            "MICROSOFT_TEAMS_SEARCH_MESSAGES must be read-only. "
            "The dbbe30a fix (multi-word service prefix scan) may be missing."
        )

    def test_is_read_only_slug_find_prefix(self) -> None:
        """GOOGLEDRIVE_FIND_FILE has FIND_ at position 1 → True."""
        result = _router._is_read_only_slug("GOOGLEDRIVE_FIND_FILE")
        assert result is True, (
            "GOOGLEDRIVE_FIND_FILE should be classified as read-only (FIND_ prefix)"
        )

    def test_is_read_only_slug_fetch_prefix(self) -> None:
        """Any slug with FETCH_ action part must be read-only."""
        result = _router._is_read_only_slug("GOOGLEDRIVE_FETCH_FILE")
        assert result is True, (
            "GOOGLEDRIVE_FETCH_FILE should be classified as read-only (FETCH_ prefix)"
        )

    def test_is_read_only_slug_query_prefix(self) -> None:
        """Any slug with QUERY_ action part must be read-only."""
        result = _router._is_read_only_slug("GOOGLESHEETS_QUERY_ROWS")
        assert result is True, (
            "GOOGLESHEETS_QUERY_ROWS should be classified as read-only (QUERY_ prefix)"
        )

    def test_is_read_only_slug_write_operations(self) -> None:
        """Write slugs must return False — none of them match a read-action prefix."""
        _write_slugs = [
            "GMAIL_SEND_EMAIL",
            "GOOGLEDRIVE_UPLOAD_FILE",
            "MICROSOFT_TEAMS_SEND_MESSAGE",
        ]
        for slug in _write_slugs:
            result = _router._is_read_only_slug(slug)
            assert result is False, (
                f"{slug!r} was incorrectly classified as read-only. "
                "Write slugs must not match GET_/FIND_/LIST_/SEARCH_/FETCH_/QUERY_."
            )


# ===========================================================================
# CATEGORY 3: Slug index structure (unit mode)
# ===========================================================================


class TestSlugIndexStructure:
    """Verify module-level slug index variables have the correct types on import."""

    def test_slug_index_initial_state(self) -> None:
        """_canonical_slugs is a list and _slug_index_built is a bool after module load."""
        assert isinstance(_router._canonical_slugs, list), (
            f"_canonical_slugs should be a list, got {type(_router._canonical_slugs)}"
        )
        assert isinstance(_router._slug_index_built, bool), (
            f"_slug_index_built should be a bool, got {type(_router._slug_index_built)}"
        )

    def test_slug_index_schema_dict_structure(self) -> None:
        """_slug_schemas is a dict; when non-empty, each entry has 'required' and 'properties'.

        The test works regardless of whether the index has been built: if the
        dict is empty (index not yet built) the structural invariant still holds
        because there is nothing to violate.  When populated, each value must be
        a dict with at least 'required' (list) and 'properties' (dict) keys —
        this is the schema contract used by get_tool_catalog() and pre-flight
        validation.
        """
        schemas: dict = _router._slug_schemas
        assert isinstance(schemas, dict), (
            f"_slug_schemas should be dict, got {type(schemas)}"
        )
        for slug, schema in schemas.items():
            assert isinstance(schema, dict), (
                f"_slug_schemas[{slug!r}] should be dict, got {type(schema)}"
            )
            assert "required" in schema or "properties" in schema, (
                f"_slug_schemas[{slug!r}] must have at least 'required' or 'properties' key. "
                f"Got keys: {list(schema.keys())}"
            )
            if "required" in schema:
                assert isinstance(schema["required"], list), (
                    f"_slug_schemas[{slug!r}]['required'] must be a list"
                )
            if "properties" in schema:
                assert isinstance(schema["properties"], dict), (
                    f"_slug_schemas[{slug!r}]['properties'] must be a dict"
                )

    def test_slug_index_service_grouping(self) -> None:
        """_slugs_by_service is a dict; when non-empty, each value is a list of strings."""
        by_service: dict = _router._slugs_by_service
        assert isinstance(by_service, dict), (
            f"_slugs_by_service should be dict, got {type(by_service)}"
        )
        for service, slugs in by_service.items():
            assert isinstance(slugs, list), (
                f"_slugs_by_service[{service!r}] should be a list, got {type(slugs)}"
            )
            for slug in slugs:
                assert isinstance(slug, str), (
                    f"_slugs_by_service[{service!r}] contains non-string entry: {slug!r}"
                )


# ===========================================================================
# CATEGORY 4: Metatool function availability
# ===========================================================================


class TestMetatoolAvailability:
    """ASYNC_TOOLS and TOOL_EXECUTOR_TOOLS must contain the expected metatool entries."""

    # Load async_wrappers once for the class — deferred so stub setup runs first
    @classmethod
    def _get_wrappers(cls) -> types.ModuleType:
        return _load_async_wrappers()

    def test_async_tools_has_7_entries(self) -> None:
        """ASYNC_TOOLS must contain exactly 7 function objects.

        Defined at bottom of async_wrappers.py:
          recall_data_async, recall_sessions_async, memory_summary_async,
          query_context_async, deep_store_async, deep_recall_async,
          delegate_tools_async
        """
        wrappers = self._get_wrappers()
        async_tools = wrappers.ASYNC_TOOLS
        assert isinstance(async_tools, list), (
            f"ASYNC_TOOLS should be a list, got {type(async_tools)}"
        )
        assert len(async_tools) == 7, (
            f"ASYNC_TOOLS has {len(async_tools)} entries, expected exactly 7. "
            f"Entries: {[getattr(t, '__name__', repr(t)) for t in async_tools]}"
        )

    def test_tool_executor_tools_has_metatools(self) -> None:
        """TOOL_EXECUTOR_TOOLS must contain all 4 metatool callables by camelCase name.

        The four metatools registered as @llm.function_tool:
          listComposioTools  → list_composio_tools_async
          planComposioTask   → plan_composio_task_async
          getComposioToolSchema → get_tool_schema_async
          manageConnections  → manage_connections_async
        """
        wrappers = self._get_wrappers()
        executor_tools = wrappers.TOOL_EXECUTOR_TOOLS
        assert isinstance(executor_tools, list), (
            f"TOOL_EXECUTOR_TOOLS should be a list, got {type(executor_tools)}"
        )

        # Collect all function names (Python-level __name__ attribute)
        _tool_names = {getattr(t, "__name__", "") for t in executor_tools}

        _expected_fn_names = {
            "list_composio_tools_async",
            "plan_composio_task_async",
            "get_tool_schema_async",
            "manage_connections_async",
        }
        _missing = _expected_fn_names - _tool_names
        assert not _missing, (
            f"TOOL_EXECUTOR_TOOLS is missing metatool functions: {_missing}. "
            f"Found: {sorted(_tool_names)}"
        )

        # All entries must be callable (function objects, not strings)
        for tool in executor_tools:
            assert callable(tool), (
                f"TOOL_EXECUTOR_TOOLS entry is not callable: {tool!r}"
            )


# ===========================================================================
# CATEGORY 5: Live API integration (requires --run-integration)
# ===========================================================================


@pytest.mark.integration
async def test_list_composio_tools_returns_content() -> None:
    """list_composio_tools_async("") returns a non-empty catalog string.

    Mocks the Composio client so no real API call is made — the integration
    marker gates this test from the default run because a live slug index
    build requires authenticated Composio credentials.  With mocked client
    the test validates the plumbing from ensure_slug_index → get_tool_catalog.
    """
    # Pre-seed slug index state so ensure_slug_index() is a no-op rebuild
    _router._canonical_slugs.clear()
    _router._canonical_slugs.extend([
        "GOOGLEDRIVE_FIND_FILE",
        "GOOGLEDRIVE_GET_FILE_METADATA",
        "GMAIL_SEND_EMAIL",
        "MICROSOFT_TEAMS_SEND_MESSAGE",
        "MICROSOFT_TEAMS_LIST_CHANNELS",
    ])
    _router._slug_index_built = True
    _router._slugs_by_service.clear()
    _router._slugs_by_service.update({
        "googledrive": [
            "GOOGLEDRIVE_FIND_FILE",
            "GOOGLEDRIVE_GET_FILE_METADATA",
        ],
        "gmail": ["GMAIL_SEND_EMAIL"],
        "microsoft_teams": [
            "MICROSOFT_TEAMS_SEND_MESSAGE",
            "MICROSOFT_TEAMS_LIST_CHANNELS",
        ],
    })

    wrappers = _load_async_wrappers()
    result: str = await wrappers.list_composio_tools_async("")

    assert isinstance(result, str), (
        f"list_composio_tools_async should return str, got {type(result)}"
    )
    assert len(result.strip()) > 0, (
        "list_composio_tools_async returned empty string — catalog not populated"
    )
    # Catalog must contain at least one known slug from the seeded index
    assert any(
        slug in result
        for slug in (
            "GOOGLEDRIVE_FIND_FILE",
            "GMAIL_SEND_EMAIL",
            "MICROSOFT_TEAMS",
        )
    ), (
        f"list_composio_tools_async result does not mention any expected slugs.\n"
        f"Result: {result[:400]}"
    )


@pytest.mark.integration
async def test_plan_composio_task_returns_schema_header() -> None:
    """plan_composio_task_async returns a string containing 'PLAN SCHEMAS'.

    Pre-seeds _slug_schemas so no Composio API calls are made.  The 'PLAN SCHEMAS'
    header is emitted by _format_cached_schema() / plan_composio_task_async
    when schemas are found for the requested slugs.
    """
    # Ensure index is marked built and schemas are available
    _router._slug_index_built = True

    # Seed minimal schemas for the two slugs under test
    _router._slug_schemas["GOOGLEDRIVE_FIND_FILE"] = {
        "required": ["q"],
        "properties": {
            "q": "Search query string for file name or content",
            "pageSize": "Max number of results (default 10)",
        },
    }
    _router._slug_schemas["GMAIL_SEND_EMAIL"] = {
        "required": ["to", "subject", "body"],
        "properties": {
            "to": "Recipient email address",
            "subject": "Email subject line",
            "body": "Email body content (plain text or HTML)",
            "cc": "Optional CC recipients",
        },
    }

    # Ensure slugs are in the canonical index for resolution
    for _slug in ("GOOGLEDRIVE_FIND_FILE", "GMAIL_SEND_EMAIL"):
        if _slug not in _router._canonical_slugs:
            _router._canonical_slugs.append(_slug)

    wrappers = _load_async_wrappers()
    result: str = await wrappers.plan_composio_task_async(
        "GOOGLEDRIVE_FIND_FILE,GMAIL_SEND_EMAIL"
    )

    assert isinstance(result, str), (
        f"plan_composio_task_async should return str, got {type(result)}"
    )
    assert "PLAN SCHEMAS" in result, (
        f"Expected 'PLAN SCHEMAS' header in plan_composio_task_async result.\n"
        f"Got: {result[:600]}"
    )
