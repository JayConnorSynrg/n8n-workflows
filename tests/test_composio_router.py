"""
Pytest suite for src/tools/composio_router.py.

Groups:
  1. initiate_service_connection  (tests 1-7)
  2. execute_composio_tool error classification  (tests 8-12)
  3. _extract_redirect_url_from_dict  (tests 13-18)
  4. Circuit breaker behaviour  (tests 19-20)
"""
import asyncio
import sys
import time
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test.
# conftest.py loads composio_router via spec_from_file_location and registers
# it under "src.tools.composio_router" in sys.modules before any test runs.
# We just pull it from there.
# ---------------------------------------------------------------------------
import sys
router = sys.modules["src.tools.composio_router"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_execute_return(
    *,
    successful: bool = True,
    data: dict | None = None,
    error: str = "",
    log_id: str = "log-test",
) -> dict:
    return {
        "successful": successful,
        "data": data if data is not None else {},
        "error": error,
        "log_id": log_id,
    }


def _stub_slug(slug: str, toolkit: str = "microsoft_teams") -> None:
    """Register a slug so slug resolution and service-key lookups work."""
    upper = slug.upper()
    if upper not in router._canonical_slugs:
        router._canonical_slugs.append(upper)
    router._slug_to_toolkit[upper] = toolkit
    router._slugs_by_service.setdefault(toolkit, []).append(upper)


# ===========================================================================
# GROUP 1 — initiate_service_connection
# ===========================================================================


@pytest.mark.asyncio
async def test_initiate_no_action_param(mock_client):
    """Attempt 1 meta-tool call must NOT include an 'action' key."""
    mock_client.tools.execute.return_value = _make_execute_return(
        data={
            "results": {
                "microsoft_teams": {
                    "redirect_url": "https://connect.composio.dev/link/test123"
                }
            }
        }
    )

    await router.initiate_service_connection("microsoft_teams", force_reauth=False)

    args, kwargs = mock_client.tools.execute.call_args
    payload = args[1]
    assert "action" not in payload


@pytest.mark.asyncio
async def test_initiate_reinitiate_all_true_when_force_reauth(mock_client):
    """force_reauth=True must map to reinitiate_all=True in the SDK call."""
    mock_client.tools.execute.return_value = _make_execute_return(
        data={
            "results": {
                "microsoft_teams": {
                    "redirect_url": "https://connect.composio.dev/link/forced"
                }
            }
        }
    )

    await router.initiate_service_connection("microsoft_teams", force_reauth=True)

    args, _ = mock_client.tools.execute.call_args
    payload = args[1]
    assert payload.get("reinitiate_all") is True


@pytest.mark.asyncio
async def test_initiate_reinitiate_all_false_when_not_force_reauth(mock_client):
    """force_reauth=False must map to reinitiate_all=False in the SDK call."""
    mock_client.tools.execute.return_value = _make_execute_return(
        data={
            "results": {
                "microsoft_teams": {
                    "redirect_url": "https://connect.composio.dev/link/normal"
                }
            }
        }
    )

    await router.initiate_service_connection("microsoft_teams", force_reauth=False)

    args, _ = mock_client.tools.execute.call_args
    payload = args[1]
    assert payload.get("reinitiate_all") is False


@pytest.mark.asyncio
async def test_initiate_already_active_returns_url(mock_client):
    """When meta-tool returns a redirect URL the function returns (url, display_name)."""
    url = "https://connect.composio.dev/link/test123"
    mock_client.tools.execute.return_value = _make_execute_return(
        data={"results": {"microsoft_teams": {"redirect_url": url}}}
    )

    result_url, display_name = await router.initiate_service_connection(
        "microsoft_teams", force_reauth=False
    )

    assert result_url == url
    assert isinstance(display_name, str)
    assert len(display_name) > 0


@pytest.mark.asyncio
async def test_initiate_no_active_account_gets_url(mock_client):
    """Service with no prior connection — meta-tool returns fresh URL."""
    url = "https://connect.composio.dev/link/new-service"
    mock_client.tools.execute.return_value = _make_execute_return(
        data={"results": {"slack": {"redirect_url": url}}}
    )

    result_url, display_name = await router.initiate_service_connection(
        "slack", force_reauth=False
    )

    assert result_url == url
    assert display_name == "Slack"


@pytest.mark.asyncio
async def test_initiate_fallback_to_sdk_direct(mock_client):
    """When meta-tool returns no URL, Attempt 2 (SDK connected_accounts.initiate) is tried."""
    # Attempt 1: successful=True but no URL in data
    mock_client.tools.execute.return_value = _make_execute_return(data={})

    # Attempt 2: SDK direct returns an object with redirect_url
    sdk_result = MagicMock()
    sdk_result.redirect_url = "https://sdk-direct.composio.dev/link/sdk"
    mock_client.connected_accounts.initiate.return_value = sdk_result

    # Auth config lookup must return one matching config
    cfg = MagicMock()
    cfg.id = "auth-cfg-001"
    cfg.appName = "microsoft_teams"
    cfg.name = "auth_config_microsoft_teams_1234"
    mock_client.auth_configs.list.return_value = MagicMock(items=[cfg])

    # _extract_items_from_response uses duck-typing — feed items attr
    def _list_return(**_kw):
        m = MagicMock()
        m.items = [cfg]
        return m

    mock_client.auth_configs.list.return_value = _list_return()

    result_url, _ = await router.initiate_service_connection(
        "microsoft_teams", force_reauth=False
    )

    assert mock_client.connected_accounts.initiate.called
    assert result_url == "https://sdk-direct.composio.dev/link/sdk"


@pytest.mark.asyncio
async def test_initiate_fallback_to_rest_api(mock_client):
    """When meta-tool AND SDK both fail, Attempt 3 (httpx REST) is tried."""
    # Attempt 1: no URL
    mock_client.tools.execute.return_value = _make_execute_return(data={})
    # Attempt 2: SDK initiate raises
    mock_client.auth_configs.list.return_value = MagicMock(items=[])
    mock_client.connected_accounts.initiate.side_effect = ValueError("no config")

    rest_url = "https://backend.composio.dev/link/rest-attempt"

    # Patch httpx.AsyncClient via its sys.modules path (our stub module is what
    # the router sees when it does `import httpx` inside the function body).
    mock_http_client = AsyncMock()
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    # /api/v1/integrations GET
    integ_resp = MagicMock()
    integ_resp.status_code = 200
    integ_resp.json.return_value = {
        "items": [{"appName": "microsoft_teams", "id": "integ-001"}]
    }

    # /api/v3/connectedAccounts POST
    acct_resp = MagicMock()
    acct_resp.status_code = 201
    acct_resp.json.return_value = {"redirectUrl": rest_url}

    mock_http_client.get = AsyncMock(return_value=integ_resp)
    mock_http_client.post = AsyncMock(return_value=acct_resp)

    with patch("httpx.AsyncClient", return_value=mock_http_client):
        result_url, _ = await router.initiate_service_connection(
            "microsoft_teams", force_reauth=False
        )

    # POST to /api/v3/connectedAccounts must have been attempted
    assert mock_http_client.post.called
    post_call = mock_http_client.post.call_args
    assert "v3/connectedAccounts" in post_call.args[0]
    assert result_url == rest_url


# ===========================================================================
# GROUP 2 — execute_composio_tool error classification
# ===========================================================================


@pytest.mark.asyncio
async def test_403_ms_graph_auth_error_classification(mock_client):
    """MS Graph 403 'No authorization information present' must trip the auth circuit breaker."""
    _stub_slug("MICROSOFT_TEAMS_SEND_MESSAGE", "microsoft_teams")

    mock_client.tools.execute.return_value = _make_execute_return(
        successful=False,
        data={"status_code": 403},
        error="No authorization information present",
    )
    # Token refresh attempt returns empty list
    mock_client.connected_accounts.list.return_value = MagicMock(items=[])

    result = await router.execute_composio_tool(
        "MICROSOFT_TEAMS_SEND_MESSAGE", {"body": "hi"}
    )

    assert router._service_auth_failed.get("microsoft_teams") is True
    assert "re-authorized" in result.lower() or "reconnect" in result.lower()


@pytest.mark.asyncio
async def test_403_permission_error_not_auth(mock_client):
    """403 'Access denied — missing scope' is a permission error, NOT an auth expiry."""
    _stub_slug("MICROSOFT_TEAMS_LIST_CHANNELS", "microsoft_teams")

    mock_client.tools.execute.return_value = _make_execute_return(
        successful=False,
        data={"status_code": 403},
        error="Access denied — missing scope",
    )

    result = await router.execute_composio_tool(
        "MICROSOFT_TEAMS_LIST_CHANNELS", {}
    )

    # Must NOT trip the service-level auth circuit breaker
    assert not router._service_auth_failed.get("microsoft_teams")
    # Response should reference permissions, not re-auth
    assert "permission" in result.lower()
    assert "re-authorized" not in result.lower()


@pytest.mark.asyncio
async def test_401_trips_circuit_breaker(mock_client):
    """401 response sets _service_auth_failed and returns re-auth language."""
    _stub_slug("GMAIL_SEND_EMAIL", "gmail")

    mock_client.tools.execute.return_value = _make_execute_return(
        successful=False,
        data={"status_code": 401},
        error="Unauthorized — token expired",
    )
    mock_client.connected_accounts.list.return_value = MagicMock(items=[])

    result = await router.execute_composio_tool("GMAIL_SEND_EMAIL", {"to": "a@b.com"})

    assert router._service_auth_failed.get("gmail") is True
    assert "re-authorized" in result.lower() or "reconnect" in result.lower()


@pytest.mark.asyncio
async def test_429_does_not_trip_circuit_breaker(mock_client):
    """429 rate-limit response must NOT set _service_auth_failed."""
    _stub_slug("SLACK_SEND_MESSAGE", "slack")

    mock_client.tools.execute.return_value = _make_execute_return(
        successful=False,
        data={"status_code": 429},
        error="Too many requests",
    )

    result = await router.execute_composio_tool("SLACK_SEND_MESSAGE", {"text": "hi"})

    assert not router._service_auth_failed.get("slack")
    assert "rate" in result.lower() or "limit" in result.lower() or "moment" in result.lower()


@pytest.mark.asyncio
async def test_successful_execution_returns_voice_result(mock_client):
    """Successful tool call returns a non-empty string (voice-friendly result)."""
    _stub_slug("SLACK_SEND_MESSAGE", "slack")

    mock_client.tools.execute.return_value = _make_execute_return(
        successful=True,
        data={"message": "Message sent successfully to #general"},
    )

    result = await router.execute_composio_tool("SLACK_SEND_MESSAGE", {"text": "hello"})

    assert isinstance(result, str)
    assert len(result) > 0


# ===========================================================================
# GROUP 3 — _extract_redirect_url_from_dict
# ===========================================================================
#
# _extract_redirect_url_from_dict is a nested function defined inside
# initiate_service_connection.  We exercise it via the public async interface
# by constructing inputs that route through each code path.
#
# For direct unit-level testing we extract the function by calling
# initiate_service_connection with a mock that triggers the nested function,
# OR we grab it from a partial call trace.  The cleanest approach is to
# isolate the logic by testing through the actual initiate path with
# controlled meta-tool responses — each test below controls 'data' so only
# one URL-extraction path is reachable.
#
# NOTE: because the function is nested we also test it by calling into
# initiate_service_connection and asserting on the RETURNED url.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_nested_results_redirect_url(mock_client):
    """data.results.{service}.redirect_url path is extracted correctly."""
    url = "https://test.com/nested-results"
    mock_client.tools.execute.return_value = _make_execute_return(
        data={"results": {"microsoft_teams": {"redirect_url": url}}}
    )

    result_url, _ = await router.initiate_service_connection("microsoft_teams")
    assert result_url == url


@pytest.mark.asyncio
async def test_extract_flat_response_data(mock_client):
    """data.response_data.redirect_url (snake_case) is extracted correctly."""
    url = "https://test.com/flat-response-data"
    mock_client.tools.execute.return_value = _make_execute_return(
        data={"response_data": {"redirect_url": url}}
    )

    result_url, _ = await router.initiate_service_connection("microsoft_teams")
    assert result_url == url


@pytest.mark.asyncio
async def test_extract_flat_response_data_camelcase(mock_client):
    """data.response_data.redirectUrl (camelCase) is extracted correctly."""
    url = "https://test.com/flat-redirect-url-camel"
    mock_client.tools.execute.return_value = _make_execute_return(
        data={"response_data": {"redirectUrl": url}}
    )

    result_url, _ = await router.initiate_service_connection("microsoft_teams")
    assert result_url == url


@pytest.mark.asyncio
async def test_extract_empty_dict_returns_none(mock_client):
    """Empty data dict means no URL is extracted; function falls through to Attempt 2."""
    mock_client.tools.execute.return_value = _make_execute_return(data={})
    # Make Attempt 2 also fail so we can observe the overall failure
    mock_client.auth_configs.list.return_value = MagicMock(items=[])
    mock_client.connected_accounts.initiate.side_effect = ValueError("no config")

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=MagicMock(status_code=404, json=MagicMock(return_value={})))
    mock_http.post = AsyncMock(return_value=MagicMock(status_code=404, text="not found"))

    with patch("httpx.AsyncClient", return_value=mock_http):
        result_url, display = await router.initiate_service_connection("microsoft_teams")

    # All paths exhausted — returns error string with empty display_name
    assert display == ""
    assert "unavailable" in result_url.lower() or "failed" in result_url.lower()


@pytest.mark.asyncio
async def test_extract_non_dict_returns_none(mock_client):
    """Non-dict data (string) does not crash and falls through to Attempt 2."""
    # Patch asyncio.to_thread so the meta-tool call returns a string-valued "data"
    # We simulate this by returning successful=False with a string error
    mock_client.tools.execute.return_value = {
        "successful": False,
        "data": "this is a string not a dict",
        "error": "bad shape",
    }
    mock_client.auth_configs.list.return_value = MagicMock(items=[])
    mock_client.connected_accounts.initiate.side_effect = ValueError("no config")

    mock_http = AsyncMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=MagicMock(status_code=404, json=MagicMock(return_value={})))
    mock_http.post = AsyncMock(return_value=MagicMock(status_code=404, text="not found"))

    with patch("httpx.AsyncClient", return_value=mock_http):
        result_url, display = await router.initiate_service_connection("microsoft_teams")

    # No crash; failure fallback triggered
    assert isinstance(result_url, str)


@pytest.mark.asyncio
async def test_extract_prioritizes_flat_over_nested(mock_client):
    """response_data.redirect_url is checked before results.{svc}.redirect_url."""
    flat_url = "https://test.com/flat-wins"
    nested_url = "https://test.com/nested-loses"

    mock_client.tools.execute.return_value = _make_execute_return(
        data={
            "response_data": {"redirect_url": flat_url},
            "results": {"microsoft_teams": {"redirect_url": nested_url}},
        }
    )

    result_url, _ = await router.initiate_service_connection("microsoft_teams")
    assert result_url == flat_url


# ===========================================================================
# GROUP 4 — Circuit breaker behaviour
# ===========================================================================


@pytest.mark.asyncio
async def test_circuit_breaker_trips_after_max_failures(mock_client):
    """After _CB_MAX_FAILURES slug failures the circuit opens and blocks further SDK calls."""
    slug = "NONEXISTENT_FAKE_SLUG_XYZ"
    slug_upper = slug.upper()

    # Populate canonical slugs with unrelated entries so the index is non-empty.
    # _resolve_slug_fast returns (raw_slug, TIER_EXACT) when _canonical_slugs is []
    # (the "no index, pass through" guard), which would allow execution to succeed.
    # With a non-empty index that does NOT contain our slug, resolution genuinely fails.
    router._canonical_slugs[:] = ["SLACK_SEND_MESSAGE", "GMAIL_SEND_EMAIL"]
    router._slug_index_built = True
    # SDK search also finds nothing
    mock_client.tools.get_raw_composio_tools.return_value = []

    # First call — slug unresolvable → error message + failure counter incremented
    result1 = await router.execute_composio_tool(slug, {})
    assert (
        "not found" in result1.lower()
        or "does not exist" in result1.lower()
        or "check the catalog" in result1.lower()
    )

    # Second call — second failure reaches CB threshold (_CB_MAX_FAILURES=2)
    result2 = await router.execute_composio_tool(slug, {})

    # Third call — circuit breaker is OPEN; client.tools.execute must NOT be called
    execute_call_count_before = mock_client.tools.execute.call_count
    result3 = await router.execute_composio_tool(slug, {})
    execute_call_count_after = mock_client.tools.execute.call_count

    assert "does not exist" in result3.lower() or "not exist" in result3.lower()
    assert execute_call_count_after == execute_call_count_before  # no new SDK call


@pytest.mark.asyncio
async def test_circuit_breaker_does_not_trip_on_permission_error(mock_client):
    """403 permission error increments slug counter but must NOT set _service_auth_failed."""
    _stub_slug("ONE_DRIVE_LIST_FILES", "one_drive")

    mock_client.tools.execute.return_value = _make_execute_return(
        successful=False,
        data={"status_code": 403},
        error="forbidden — you do not have access to this folder",
    )

    await router.execute_composio_tool("ONE_DRIVE_LIST_FILES", {})

    # Auth circuit breaker for the service must stay clear
    assert not router._service_auth_failed.get("one_drive")
    # Slug failure counter should have incremented (permission errors still count toward slug CB)
    # _failed_slugs now stores (count, timestamp) tuples — extract count from index 0
    _slug_entry = router._failed_slugs.get("ONE_DRIVE_LIST_FILES")
    _slug_count = _slug_entry[0] if isinstance(_slug_entry, tuple) else (_slug_entry or 0)
    assert _slug_count >= 1
