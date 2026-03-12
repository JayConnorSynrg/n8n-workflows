"""
tests/e2e/test_tool_execution.py

Regression guards for:
  1. runLeadGen n8n_post migration  — aiohttp must NOT appear in runLeadGen block
  2. context_hints user_id propagation — correct Composio entity resolution
  3. n8n_post centralization — no bare aiohttp.ClientSession in tool files

Source analysis tests use plain file reads (no src imports required).
Integration tests that call live tool functions are marked @pytest.mark.integration.
"""
from __future__ import annotations

import os
import re
import sys
import textwrap
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent.parent
SRC_ROOT = REPO_ROOT / "src"
TOOLS_DIR = SRC_ROOT / "tools"

TOOL_EXECUTOR_PATH = TOOLS_DIR / "tool_executor.py"
ASYNC_WRAPPERS_PATH = TOOLS_DIR / "async_wrappers.py"
N8N_CLIENT_PATH = SRC_ROOT / "utils" / "n8n_client.py"
CONFIG_PATH = SRC_ROOT / "config.py"

# Production Composio entity prefix
COMPOSIO_PROD_PREFIX = "pg-test"
COMPOSIO_PROD_ENTITY = "pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_block(source: str, start_marker: str, stop_pattern: str = r"^\s+elif ") -> str:
    """Extract a block of source text between start_marker and the next matching stop_pattern.

    Args:
        source: Full source code string.
        start_marker: Literal string that begins the block (must appear exactly once in context).
        stop_pattern: Regex applied line-by-line to detect block end.

    Returns:
        The extracted block as a string, or empty string if start_marker not found.
    """
    start_idx = source.find(start_marker)
    if start_idx == -1:
        return ""

    block_lines: list[str] = []
    in_block = False
    for line in source[start_idx:].splitlines():
        if not in_block:
            block_lines.append(line)
            in_block = True
            continue
        # Stop at the next elif/else at the same or outer indentation level
        if re.match(stop_pattern, line):
            break
        block_lines.append(line)

    return "\n".join(block_lines)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def tool_executor_source() -> str:
    """Contents of src/tools/tool_executor.py as a string."""
    return TOOL_EXECUTOR_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def async_wrappers_source() -> str:
    """Contents of src/tools/async_wrappers.py as a string."""
    return ASYNC_WRAPPERS_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def n8n_client_source() -> str:
    """Contents of src/utils/n8n_client.py as a string."""
    return N8N_CLIENT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def config_source() -> str:
    """Contents of src/config.py as a string."""
    return CONFIG_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def runleadgen_block(tool_executor_source: str) -> str:
    """Extracted source block for the runLeadGen elif branch in _dispatch_tool_call."""
    block = _extract_block(
        tool_executor_source,
        start_marker='elif tool_name == "runLeadGen":',
        stop_pattern=r"^\s+elif ",
    )
    print(f"\n[AUDIT] tool_executor.py runLeadGen block:\n{textwrap.indent(block, '  ')}")
    return block


@pytest.fixture(scope="session")
def all_tool_py_files() -> list[Path]:
    """All .py files in src/tools/ excluding __init__."""
    return [
        p for p in TOOLS_DIR.glob("*.py")
        if p.name != "__init__.py"
    ]


# ---------------------------------------------------------------------------
# Class 1: TestRunLeadGenMigration
# ---------------------------------------------------------------------------

class TestRunLeadGenMigration:
    """Verify runLeadGen uses n8n_post (centralized client) and not bare aiohttp."""

    def test_runleadgen_uses_n8n_post_not_aiohttp(self, runleadgen_block: str) -> None:
        """runLeadGen elif block must NOT contain aiohttp.ClientSession and MUST use n8n_post."""
        assert runleadgen_block, (
            'runLeadGen block not found in tool_executor.py — '
            'marker "elif tool_name == \\"runLeadGen\\":" missing'
        )

        has_aiohttp = "aiohttp.ClientSession" in runleadgen_block
        has_n8n_post = (
            "_n8n_tep_post" in runleadgen_block
            or "n8n_post" in runleadgen_block
        )

        assert not has_aiohttp, (
            "runLeadGen block still uses aiohttp.ClientSession — migration to n8n_post incomplete.\n"
            f"Block:\n{runleadgen_block}"
        )
        assert has_n8n_post, (
            "runLeadGen block does not call _n8n_tep_post or n8n_post — "
            "expected centralized n8n_client usage.\n"
            f"Block:\n{runleadgen_block}"
        )

    def test_n8n_post_import_in_runleadgen(self, runleadgen_block: str) -> None:
        """runLeadGen block must import n8n_post from n8n_client (inline import pattern)."""
        assert runleadgen_block, "runLeadGen block not found — see test_runleadgen_uses_n8n_post_not_aiohttp"

        # Inline import pattern used in _dispatch_tool_call:
        # from ..utils.n8n_client import n8n_post as _n8n_tep_post
        has_import = (
            "from ..utils.n8n_client import n8n_post" in runleadgen_block
            or "n8n_client" in runleadgen_block  # tolerates alternate import forms
        )
        assert has_import, (
            "runLeadGen block does not import n8n_post from n8n_client.\n"
            "Expected: 'from ..utils.n8n_client import n8n_post as _n8n_tep_post'\n"
            f"Block:\n{runleadgen_block}"
        )

    def test_no_aiohttp_clientsession_in_tool_files(self, all_tool_py_files: list[Path]) -> None:
        """Regression guard: no tool file may use bare aiohttp.ClientSession for n8n webhook calls.

        n8n_client.py is the centralized wrapper — all n8n webhook traffic must go through it.
        Generic external HTTP calls (e.g. S3 fetch, third-party APIs) are permitted to use
        aiohttp.ClientSession directly; those are not n8n migration violations.

        Detection heuristic: within a ±5 line window of each aiohttp.ClientSession usage, if
        any line references 'N8N_WEBHOOK_BASE_URL', 'webhook/', or n8n base URLs, it is a
        violation. Pure external fetch (S3, Composio S3 download, etc.) is not flagged.
        """
        N8N_PATTERNS = re.compile(r"N8N_WEBHOOK_BASE_URL|webhook/|n8n\.cloud")
        violations: list[tuple[Path, int, str]] = []

        for py_file in all_tool_py_files:
            # n8n_client is the centralized wrapper — its internal aiohttp usage is intentional
            if py_file.name == "n8n_client.py":
                continue

            source = py_file.read_text(encoding="utf-8")
            lines = source.splitlines()
            for lineno, line in enumerate(lines, start=1):
                if "aiohttp.ClientSession" in line and not line.strip().startswith("#"):
                    # Check ±5 line context window for n8n webhook references
                    window_start = max(0, lineno - 6)
                    window_end = min(len(lines), lineno + 5)
                    window = "\n".join(lines[window_start:window_end])
                    if N8N_PATTERNS.search(window):
                        violations.append((py_file, lineno, line.strip()))

        if violations:
            report = "\n".join(
                f"  {p.name}:{lineno}  {line}"
                for p, lineno, line in violations
            )
            pytest.fail(
                f"Bare aiohttp.ClientSession used for n8n webhook calls in {len(violations)} location(s):\n"
                f"{report}\n"
                "All n8n webhook calls must go through src/utils/n8n_client.py::n8n_post()."
            )

        print(f"\n[AUDIT] Scanned {len(all_tool_py_files)} tool files — 0 n8n-targeted aiohttp.ClientSession violations")

    def test_n8n_post_adds_webhook_secret_header(self, n8n_client_source: str) -> None:
        """n8n_client.py must inject X-AIO-Webhook-Secret and Content-Type on every request."""
        assert "X-AIO-Webhook-Secret" in n8n_client_source, (
            "n8n_client.py does not inject X-AIO-Webhook-Secret header. "
            "All n8n webhook calls require this authentication header."
        )
        assert "Content-Type" in n8n_client_source, (
            "n8n_client.py does not set Content-Type header."
        )
        print("\n[AUDIT] n8n_client.py: X-AIO-Webhook-Secret and Content-Type headers confirmed present")

    @pytest.mark.integration
    async def test_runleadgen_returns_descriptive_message_on_200(self) -> None:
        """_dispatch_tool_call('runLeadGen', ...) returns a lead generation message on HTTP 200."""
        try:
            # Inline import — may fail if env is not configured
            from src.tools.tool_executor import _dispatch_tool_call  # type: ignore[import]
        except (ImportError, ModuleNotFoundError) as exc:
            pytest.skip(f"Cannot import _dispatch_tool_call — env not configured: {exc}")

        mock_post = AsyncMock(return_value=(200, {"status": "ok"}))

        with patch("src.tools.tool_executor._n8n_tep_post", mock_post):
            result: str = await _dispatch_tool_call(
                "runLeadGen",
                {"lead_type": "saas", "mode": "results", "limit": 5},
                session_id="test-session-leadgen",
                say_callback=AsyncMock(),
                context_hints={},
            )

        assert isinstance(result, str), f"Expected str result, got {type(result)}"
        assert "lead" in result.lower() or "generation" in result.lower(), (
            f"runLeadGen 200 response did not mention lead generation: {result!r}"
        )
        print(f"\n[AUDIT] runLeadGen 200 result: {result!r}")


# ---------------------------------------------------------------------------
# Class 2: TestContextHintsPropagation
# ---------------------------------------------------------------------------

class TestContextHintsPropagation:
    """Verify user_id flows from delegate_tools_async into Composio entity resolution."""

    def test_delegate_tools_async_reads_current_user_id(self, async_wrappers_source: str) -> None:
        """delegate_tools_async must read agent_context_tool._current_user_id."""
        # Extract the delegate_tools_async function body
        fn_marker = "async def delegate_tools_async"
        fn_start = async_wrappers_source.find(fn_marker)
        assert fn_start != -1, (
            "delegate_tools_async not found in async_wrappers.py"
        )

        # Take a reasonable window (3000 chars) after the function signature
        fn_body = async_wrappers_source[fn_start: fn_start + 3000]

        assert "agent_context_tool._current_user_id" in fn_body, (
            "delegate_tools_async does not read agent_context_tool._current_user_id.\n"
            "user_id must be extracted from the context tool for correct Composio entity resolution.\n"
            f"Function window:\n{fn_body[:800]}"
        )
        print("\n[AUDIT] async_wrappers.py: agent_context_tool._current_user_id read confirmed in delegate_tools_async")

    def test_context_hints_user_id_key_passed(self, async_wrappers_source: str) -> None:
        """_run_background_delegation must receive context_hints={"user_id": _bg_user_id}."""
        fn_marker = "async def delegate_tools_async"
        fn_start = async_wrappers_source.find(fn_marker)
        assert fn_start != -1, "delegate_tools_async not found in async_wrappers.py"

        fn_body = async_wrappers_source[fn_start: fn_start + 3000]

        # Must pass context_hints with user_id key to background delegation
        has_context_hints_call = (
            'context_hints={"user_id": _bg_user_id}' in fn_body
            or "context_hints" in fn_body and "_bg_user_id" in fn_body
        )
        assert has_context_hints_call, (
            "delegate_tools_async does not pass context_hints with user_id to _run_background_delegation.\n"
            "Without this, background delegation resolves to default Composio entity (48 tools instead of 453).\n"
            f"Function window:\n{fn_body[:800]}"
        )
        print("\n[AUDIT] async_wrappers.py: context_hints user_id propagation confirmed")

    def test_default_fallback_when_user_id_missing(self, async_wrappers_source: str) -> None:
        """When agent_context_tool._current_user_id is unavailable, fallback must be '_default'."""
        fn_marker = "async def delegate_tools_async"
        fn_start = async_wrappers_source.find(fn_marker)
        assert fn_start != -1, "delegate_tools_async not found in async_wrappers.py"

        fn_body = async_wrappers_source[fn_start: fn_start + 3000]

        assert '"_default"' in fn_body or "'_default'" in fn_body, (
            "No '_default' fallback found in delegate_tools_async.\n"
            "When user_id is unavailable, the code must fall back to '_default' to avoid AttributeError.\n"
            f"Function window:\n{fn_body[:800]}"
        )

        # Also confirm hasattr guard is present
        assert "hasattr" in fn_body, (
            "No hasattr guard found near agent_context_tool._current_user_id in delegate_tools_async.\n"
            "Missing guard causes AttributeError when agent_context_tool is not initialized.\n"
            f"Function window:\n{fn_body[:800]}"
        )
        print("\n[AUDIT] async_wrappers.py: hasattr guard and '_default' fallback confirmed")

    def test_composio_entity_id_env_var(self, config_source: str) -> None:
        """config.py must declare COMPOSIO_USER_ID; if env set, must have 'pg-test' prefix."""
        assert "COMPOSIO_USER_ID" in config_source, (
            "src/config.py does not declare COMPOSIO_USER_ID field.\n"
            "This field is required to route Composio tool calls to the correct entity (453 tools)."
        )
        assert "composio_user_id" in config_source, (
            "src/config.py does not have composio_user_id snake_case attribute.\n"
            "Pydantic alias mapping for COMPOSIO_USER_ID is missing."
        )

        env_value = os.environ.get("COMPOSIO_USER_ID", "")
        if env_value:
            masked = env_value[:12] + "..." + ("*" * max(0, len(env_value) - 12))
            print(f"\n[AUDIT] COMPOSIO_USER_ID (masked): {masked}")
            assert env_value.startswith(COMPOSIO_PROD_PREFIX), (
                f"COMPOSIO_USER_ID does not start with '{COMPOSIO_PROD_PREFIX}'.\n"
                f"Wrong entity → only 48 tools instead of 453.\n"
                f"Got prefix: {env_value[:12]!r}"
            )
        else:
            print("\n[AUDIT] COMPOSIO_USER_ID not set in env — skipping prefix check (unit test mode)")

        print(f"[AUDIT] config.py COMPOSIO_USER_ID field: PRESENT")


# ---------------------------------------------------------------------------
# Class 3: TestN8nClientCentralization
# ---------------------------------------------------------------------------

class TestN8nClientCentralization:
    """Regression guard: all tool files that make n8n HTTP calls must use n8n_client."""

    def test_all_tool_files_import_n8n_post_not_aiohttp(
        self, all_tool_py_files: list[Path]
    ) -> None:
        """Any tool file touching n8n webhooks must import from n8n_client, not aiohttp directly.

        Prints a table of all tool files with their HTTP client usage for audit visibility.
        """
        header = f"\n[AUDIT] Tool file HTTP client audit ({len(all_tool_py_files)} files):"
        rows: list[str] = [header, f"  {'FILE':<40} {'N8N_REF':>8} {'N8N_CLIENT':>10} {'AIOHTTP_BARE':>12}"]
        rows.append("  " + "-" * 72)

        violations: list[str] = []

        for py_file in all_tool_py_files:
            source = py_file.read_text(encoding="utf-8")

            # Detect n8n webhook reference patterns
            has_n8n_ref = bool(
                "N8N_WEBHOOK_BASE_URL" in source
                or re.search(r'"webhook/', source)
                or re.search(r"'webhook/", source)
            )

            # Detect centralized client import
            has_n8n_client = bool(
                "n8n_client" in source
                or "n8n_post" in source
            )

            # Detect bare aiohttp.ClientSession used for n8n webhook calls (non-comment lines only).
            # Generic external HTTP (S3 fetch, Composio download, etc.) is NOT a violation.
            _n8n_pattern = re.compile(r"N8N_WEBHOOK_BASE_URL|webhook/|n8n\.cloud")
            _src_lines = source.splitlines()
            bare_aiohttp_lines = []
            for _lno, _line in enumerate(_src_lines, start=1):
                if "aiohttp.ClientSession" in _line and not _line.strip().startswith("#"):
                    _win_start = max(0, _lno - 6)
                    _win_end = min(len(_src_lines), _lno + 5)
                    _window = "\n".join(_src_lines[_win_start:_win_end])
                    if _n8n_pattern.search(_window):
                        bare_aiohttp_lines.append(_line.strip())
            has_bare_aiohttp = bool(bare_aiohttp_lines)

            rows.append(
                f"  {py_file.name:<40} {'YES' if has_n8n_ref else 'no':>8} "
                f"{'YES' if has_n8n_client else 'no':>10} "
                f"{'VIOLATION' if has_bare_aiohttp else 'clean':>12}"
            )

            # n8n_client.py itself uses aiohttp internally — that's intentional
            if py_file.name == "n8n_client.py":
                continue

            if has_n8n_ref and not has_n8n_client:
                violations.append(
                    f"  {py_file.name}: references n8n webhooks but does not import n8n_client"
                )
            if has_bare_aiohttp:
                violations.append(
                    f"  {py_file.name}: bare aiohttp.ClientSession in non-client file"
                )

        print("\n".join(rows))

        if violations:
            pytest.fail(
                f"\n{len(violations)} n8n HTTP centralization violation(s) detected:\n"
                + "\n".join(violations)
                + "\n\nAll n8n webhook calls must use src/utils/n8n_client.py::n8n_post()."
            )

        print("\n[AUDIT] n8n_post centralization check: PASS — all tool files compliant")
