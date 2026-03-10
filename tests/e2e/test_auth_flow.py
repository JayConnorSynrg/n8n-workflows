"""
E2E test suite: Composio auth link flow for the AIO Voice Agent.

Coverage:
  Cat 1 — _extract_redirect_url_from_dict URL parsing (4 unit tests)
  Cat 2 — API-key service bypass logic (2 unit tests)
  Cat 3 — connect action email send path (2 unit tests)
  Cat 4 — refresh action + 30-second cooldown (2 unit tests)
  Cat 5 — Live integration smoke tests (2 tests, --run-integration only)

All non-integration tests:
  - Make zero real HTTP calls
  - Do not invoke Railway, Railway CLI, or git
  - Patch aiohttp.ClientSession and composio_router internals at the boundary

Bootstrap strategy:
  async_wrappers.py has a hard dependency on livekit.agents (imported at module
  level). Since livekit IS installed in this environment, the import succeeds
  directly. Heavy Composio SDK deps (asyncpg, jsonschema) are stubbed in
  sys.modules before the first import of composio_router so they do not require
  the Railway network or DB to be reachable.

  _extract_redirect_url_from_dict is defined as a closure-local function inside
  initiate_service_connection and is therefore not directly importable. The test
  file mirrors the exact production implementation (as of monorepo commit
  7866009) and tests it in isolation. Any logic change in the production closure
  must be reflected here.
"""

from __future__ import annotations

import asyncio
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Sys.modules pre-stubs — inject before any src.* import so heavy optional
# deps that are absent in the test environment do not block collection.
# ---------------------------------------------------------------------------

def _make_stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    if name not in sys.modules:
        sys.modules[name] = mod
    return mod


def _bootstrap_stubs() -> None:
    """Install minimal stubs for deps that are absent in the local test env.

    Only stub packages that are genuinely not installed. Packages that ARE
    installed (httpx, jsonschema, livekit) must NOT be stubbed — replacing a
    real package with a stub breaks transitive imports within the same chain
    (e.g. openai -> httpx.URL would fail against a stub module).
    """
    # asyncpg — PostgreSQL async driver, only needed at Railway runtime
    _make_stub("asyncpg")

    # composio SDK — not installed in local dev env; only needed at Railway runtime
    _make_stub("composio")
    _make_stub("composio.tools")
    _make_stub("composio.tools.toolset")

    # fastembed / sentence_transformers — ONNX embedding deps, only on Railway
    _make_stub("fastembed")
    _make_stub("sentence_transformers")


_bootstrap_stubs()

# ---------------------------------------------------------------------------
# Minimal environment variables so pydantic Settings.model_validate succeeds
# without real Railway secrets.
# ---------------------------------------------------------------------------

_TEST_ENV = {
    "LIVEKIT_URL": "wss://fake.livekit.cloud",
    "LIVEKIT_API_KEY": "test-livekit-key",
    "LIVEKIT_API_SECRET": "test-livekit-secret",
    "DEEPGRAM_API_KEY": "test-deepgram-key",
    "CARTESIA_API_KEY": "test-cartesia-key",
    "COMPOSIO_API_KEY": "test-composio-key",
    "COMPOSIO_USER_ID": "pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c",
    "N8N_WEBHOOK_BASE_URL": "https://jayconnorexe.app.n8n.cloud",
    "N8N_WEBHOOK_SECRET": "b425d5890244b951ae8deecd05dbb629a39d5f81e4f95d21b4e52cdfc40fdcb8",
}

for _k, _v in _TEST_ENV.items():
    os.environ.setdefault(_k, _v)

# ---------------------------------------------------------------------------
# Repo root on path — required for src.* relative imports
# ---------------------------------------------------------------------------

import pathlib as _pathlib

_REPO_ROOT = str(_pathlib.Path(__file__).parent.parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# Module imports — after stubs + env are in place
# ---------------------------------------------------------------------------

import src.tools.async_wrappers as _aw_mod
from src.tools.async_wrappers import manage_connections_async
import src.tools.composio_router as _router_mod


# ---------------------------------------------------------------------------
# Mirror of _extract_redirect_url_from_dict (closure-local in
# composio_router.initiate_service_connection — not directly importable).
#
# This is an exact copy of the production closure as of monorepo commit
# 7866009 / composio_router.py lines 2547-2575. If the production
# implementation changes, update this mirror and add a regression comment.
# ---------------------------------------------------------------------------

def _extract_redirect_url_from_dict(data: dict) -> str | None:
    """Mirror of closure-local helper in initiate_service_connection.

    Probes multiple key shapes because the SDK redirect URL field name
    varies across Composio SDK versions and MANAGE_CONNECTIONS nests the
    URL under data.results.{service_name}.redirect_url.
    """
    if not isinstance(data, dict):
        return None
    response_data = data.get("response_data", {}) or {}
    # Flat probes (older SDK shapes)
    flat = (
        response_data.get("redirect_url")
        or response_data.get("redirectUrl")
        or response_data.get("connectionUrl")
        or response_data.get("authUrl")
        or data.get("redirect_url")
        or data.get("redirectUrl")
        or data.get("connectionUrl")
        or data.get("authUrl")
    )
    if flat:
        return flat
    # MANAGE_CONNECTIONS shape: data.results.{service_name}.redirect_url
    for svc_data in (data.get("results") or {}).values():
        if isinstance(svc_data, dict):
            url = svc_data.get("redirect_url") or svc_data.get("redirectUrl")
            if url:
                return url
    return None


# ---------------------------------------------------------------------------
# Shared patch helpers — reduce boilerplate in every async test
# ---------------------------------------------------------------------------

def _tool_lifecycle_patches():
    """Context manager stack that silences publish_tool_* calls."""
    return (
        patch("src.tools.async_wrappers.publish_tool_start", new_callable=AsyncMock, return_value="test-call-id"),
        patch("src.tools.async_wrappers.publish_tool_executing", new_callable=AsyncMock),
        patch("src.tools.async_wrappers.publish_tool_completed", new_callable=AsyncMock),
        patch("src.tools.async_wrappers.publish_tool_error", new_callable=AsyncMock),
    )


def _make_aiohttp_ok_session() -> MagicMock:
    """Build a mock aiohttp.ClientSession that returns HTTP 200 with no error body."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"status": "OK"})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


# ===========================================================================
# Category 1 — _extract_redirect_url_from_dict URL parsing
# ===========================================================================


class TestExtractRedirectUrl:
    """Unit tests for the URL extraction helper (closure-local mirror).

    These tests validate the multi-shape fallback logic that handles
    different Composio SDK response formats without making any network calls.
    """

    def test_extract_redirect_url_nested_results(self):
        """MANAGE_CONNECTIONS canonical shape: data.results.{service}.redirect_url."""
        data = {
            "results": {
                "gmail": {
                    "redirect_url": "https://auth.example.com",
                    "status": "INITIATED",
                }
            }
        }
        result = _extract_redirect_url_from_dict(data)
        assert result == "https://auth.example.com"

    def test_extract_redirect_url_flat_response_data(self):
        """Older SDK shape: data.response_data.redirect_url."""
        data = {
            "response_data": {
                "redirect_url": "https://flat.example.com",
            }
        }
        result = _extract_redirect_url_from_dict(data)
        assert result == "https://flat.example.com"

    def test_extract_redirect_url_top_level(self):
        """Fallback shape: data.redirect_url at top level."""
        data = {"redirect_url": "https://top.example.com"}
        result = _extract_redirect_url_from_dict(data)
        assert result == "https://top.example.com"

    def test_extract_redirect_url_none_when_missing(self):
        """Returns None for empty dict and for results dict with no URLs."""
        assert _extract_redirect_url_from_dict({}) is None
        assert _extract_redirect_url_from_dict({"results": {}}) is None
        # results present but inner dicts have no redirect key
        assert _extract_redirect_url_from_dict({"results": {"gmail": {"status": "ACTIVE"}}}) is None
        # non-dict input
        assert _extract_redirect_url_from_dict(None) is None  # type: ignore[arg-type]


# ===========================================================================
# Category 2 — API-key service bypass
# ===========================================================================


class TestApiKeyServiceBypass:
    """Validates that API-key-only services are short-circuited on connect.

    The connect action must not attempt OAuth initiation for services that
    use API-key auth (gamma, notion, perplexity, perplexityai, composio,
    composio_search) when they are already indexed in _slugs_by_service.
    """

    def test_api_key_services_set_contains_known_services(self):
        """_API_KEY_ONLY_SERVICES frozenset must cover all known API-key services.

        This is verified by inspecting the set defined inline in the connect
        branch of manage_connections_async. We drive the behaviour through
        the function rather than reading the frozenset directly, so the test
        stays valid even if the set is ever moved to module scope.
        """
        # The frozenset is defined inline; verify membership through the
        # observable bypass behaviour (tested in test_connect_api_key_service).
        # As a static assertion, check the expected members are a subset of
        # what the implementation protects.
        expected_members = {"gamma", "notion", "perplexity", "perplexityai"}
        # Confirm by exercising the bypass for each service with a stub slug.
        for svc in expected_members:
            original = _router_mod._slugs_by_service.copy()
            try:
                _router_mod._slugs_by_service[svc] = [f"{svc.upper()}_FAKE_TOOL"]
                # If the implementation sees the service in both the index and
                # the API-key set it must return the bypass message.
                async def _check(s=svc):
                    return await manage_connections_async(action="connect", service=s)

                with (
                    patch("src.tools.async_wrappers.publish_tool_start", new_callable=AsyncMock, return_value="cid"),
                    patch("src.tools.async_wrappers.publish_tool_executing", new_callable=AsyncMock),
                    patch("src.tools.async_wrappers.publish_tool_completed", new_callable=AsyncMock),
                ):
                    result = asyncio.get_event_loop().run_until_complete(_check())
                assert "already connected" in result.lower(), (
                    f"Service '{svc}' should be bypassed — got: {result!r}"
                )
            finally:
                # Restore original state so other tests are unaffected
                _router_mod._slugs_by_service.clear()
                _router_mod._slugs_by_service.update(original)

    async def test_connect_api_key_service_already_indexed_returns_connected(self):
        """Gamma already in slug index → bypass with 'already connected', no email sent."""
        original = _router_mod._slugs_by_service.copy()
        try:
            _router_mod._slugs_by_service["gamma"] = ["GAMMA_GENERATE_GAMMA"]

            with (
                patch("src.tools.async_wrappers.publish_tool_start", new_callable=AsyncMock, return_value="cid"),
                patch("src.tools.async_wrappers.publish_tool_executing", new_callable=AsyncMock),
                patch("src.tools.async_wrappers.publish_tool_completed", new_callable=AsyncMock),
                # initiate_service_connection must NOT be called for API-key services
                patch(
                    "src.tools.composio_router.initiate_service_connection",
                    new_callable=AsyncMock,
                ) as mock_init,
                patch("aiohttp.ClientSession") as mock_session_cls,
            ):
                result = await manage_connections_async(action="connect", service="gamma")

            assert "already connected" in result.lower()
            mock_init.assert_not_called()
            mock_session_cls.assert_not_called()
        finally:
            _router_mod._slugs_by_service.clear()
            _router_mod._slugs_by_service.update(original)


# ===========================================================================
# Category 3 — connect action email path
# ===========================================================================


class TestConnectActionEmailPath:
    """Tests for the OAuth connect → email dispatch path.

    Covers the success case (aiohttp returns 200) and the graceful
    degradation case (aiohttp raises an exception mid-call).
    """

    async def test_connect_service_success_path(self):
        """Email delivered → response contains 'sent a connection link'."""
        mock_session = _make_aiohttp_ok_session()

        with (
            patch("src.tools.async_wrappers.publish_tool_start", new_callable=AsyncMock, return_value="cid"),
            patch("src.tools.async_wrappers.publish_tool_executing", new_callable=AsyncMock),
            patch("src.tools.async_wrappers.publish_tool_completed", new_callable=AsyncMock),
            patch(
                "src.tools.composio_router.initiate_service_connection",
                new_callable=AsyncMock,
                return_value=("https://auth.composio.dev/xxx", "Gmail"),
            ),
            patch("aiohttp.ClientSession", return_value=mock_session),
        ):
            result = await manage_connections_async(action="connect", service="gmail")

        assert "sent a connection link" in result
        assert "Gmail" in result

    async def test_connect_service_email_fail_graceful(self):
        """aiohttp.ClientSession raises → graceful degradation, no crash.

        The function must catch the exception, log a warning internally, and
        return a user-facing message indicating the email could not be sent.
        The auth URL must NOT be leaked to the voice response.
        """
        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(side_effect=Exception("network timeout"))
        mock_session_cm.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.tools.async_wrappers.publish_tool_start", new_callable=AsyncMock, return_value="cid"),
            patch("src.tools.async_wrappers.publish_tool_executing", new_callable=AsyncMock),
            patch("src.tools.async_wrappers.publish_tool_completed", new_callable=AsyncMock),
            patch(
                "src.tools.composio_router.initiate_service_connection",
                new_callable=AsyncMock,
                return_value=("https://auth.composio.dev/yyy", "Gmail"),
            ),
            patch("aiohttp.ClientSession", return_value=mock_session_cm),
        ):
            result = await manage_connections_async(action="connect", service="gmail")

        # Must NOT raise
        assert isinstance(result, str)
        assert "could not send it via email" in result
        # Raw auth URL must not be exposed in voice response
        assert "https://auth.composio.dev" not in result


# ===========================================================================
# Category 4 — refresh action
# ===========================================================================


class TestRefreshAction:
    """Tests for the refresh action: slug index rebuild + 30-second cooldown."""

    async def test_refresh_updates_slug_index(self):
        """refresh calls refresh_slug_index and returns 'Tools refreshed' message."""
        # Reset cooldown so the first call is not blocked
        _aw_mod._last_refresh_time = 0.0
        mock_catalog = "GMAIL_SEND_EMAIL\nGOOGLEDRIVE_FIND_FILE\n"

        with (
            patch("src.tools.async_wrappers.publish_tool_start", new_callable=AsyncMock, return_value="cid"),
            patch("src.tools.async_wrappers.publish_tool_executing", new_callable=AsyncMock),
            patch("src.tools.async_wrappers.publish_tool_completed", new_callable=AsyncMock),
            patch(
                "src.tools.composio_router.refresh_slug_index",
                new_callable=AsyncMock,
                return_value=mock_catalog,
            ) as mock_refresh,
        ):
            result = await manage_connections_async(action="refresh")

        assert "Tools refreshed" in result
        mock_refresh.assert_called_once()

    async def test_refresh_has_30s_cooldown(self):
        """Second refresh within 30 seconds returns cooldown message without calling refresh_slug_index."""
        # Ensure first call is allowed
        _aw_mod._last_refresh_time = 0.0
        mock_catalog = "GMAIL_SEND_EMAIL\nGOOGLEDRIVE_FIND_FILE\n"

        with (
            patch("src.tools.async_wrappers.publish_tool_start", new_callable=AsyncMock, return_value="cid"),
            patch("src.tools.async_wrappers.publish_tool_executing", new_callable=AsyncMock),
            patch("src.tools.async_wrappers.publish_tool_completed", new_callable=AsyncMock),
            patch(
                "src.tools.composio_router.refresh_slug_index",
                new_callable=AsyncMock,
                return_value=mock_catalog,
            ) as mock_refresh,
        ):
            first = await manage_connections_async(action="refresh")
            # Second call immediately — cooldown not yet expired
            second = await manage_connections_async(action="refresh")

        assert "Tools refreshed" in first
        # Cooldown message
        assert "already up to date" in second
        # refresh_slug_index called exactly once — second call was blocked
        mock_refresh.assert_called_once()


# ===========================================================================
# Category 5 — Live integration tests
# ===========================================================================


class TestManageConnectionsIntegration:
    """Live integration smoke tests.

    These tests make real network calls to the deployed Railway agent and
    Composio API. They are skipped unless --run-integration is passed.

    Both tests accept either the success or the graceful-degradation message
    because the test environment may not have a Gmail OAuth session active.
    The goal is to verify the code path executes end-to-end without crashing.
    """

    @pytest.mark.integration
    async def test_manage_connections_status_returns_string(self):
        """status action returns a non-empty string — smoke test for the full stack."""
        result = await manage_connections_async(action="status")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.integration
    async def test_manage_connections_connect_gmail_sends_email(self):
        """connect gmail runs without crash and returns one of the two valid messages.

        Two acceptable outcomes:
          1. 'sent a connection link' — Composio returned a URL and email was sent.
          2. 'could not send it via email' — URL generated but n8n webhook failed.

        Any other outcome (exception, empty string, unrecognised message) is a failure.
        """
        result = await manage_connections_async(
            action="connect",
            service="gmail",
            recipient="test@example.com",
        )
        assert isinstance(result, str)
        valid = "sent a connection link" in result or "could not send it via email" in result
        assert valid, f"Unexpected result from connect gmail: {result!r}"
