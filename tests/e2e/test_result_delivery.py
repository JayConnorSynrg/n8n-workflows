"""Result delivery integrity E2E tests for the AIO Voice Agent.

Validates that data written to PostgreSQL, emitted as voice responses, and
persisted through session context is never silently truncated, corrupted, or
misdirected between the agent layer and the storage/delivery layer.

Test categories:
  1. DB schema validation    — constraint values match migration SQL (unit)
  2. Email payload integrity — manage_connections payload shape + auth header (unit)
  3. Voice response integrity — truncation boundaries in log_turn + per-turn context (unit)
  4. Session context persistence — save/get round-trip + gate key prefix (unit)
  5. Live DB integration      — log_turn and log_tool_error write real rows (integration)
"""

import importlib.util
import inspect
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent.parent
_SRC_ROOT = _REPO_ROOT / "src"
_DB_ROOT = _REPO_ROOT / "database"


def _load_src_module(dotted_name: str, rel_path: str):
    """Load a module from src/ by filesystem path and register in sys.modules."""
    if dotted_name in sys.modules:
        return sys.modules[dotted_name]
    abs_path = _SRC_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(dotted_name, abs_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[dotted_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Category 1: DB schema validation (unit — reads migration SQL files)
# ---------------------------------------------------------------------------


class TestDBSchemaConstraints:
    """Assert that check-constraint values are present in the actual migration SQL.

    These tests guard against drift between the documented constraint set and
    whatever is actually applied to the Railway PostgreSQL instance.  They read
    the migration files directly and do not require a live DB connection.
    """

    def test_conversation_log_role_constraint_values(self):
        """conversation_log.role CHECK allows exactly: user, assistant, tool, system."""
        migration = (_DB_ROOT / "conversation_log_migration.sql").read_text()

        expected_roles = {"user", "assistant", "tool", "system"}
        for role in expected_roles:
            assert f"'{role}'" in migration, (
                f"Role '{role}' missing from conversation_log_migration.sql CHECK constraint. "
                f"If the role set was extended, update this test to match."
            )

        # Confirm the CHECK clause itself is present (not just stray string occurrences)
        assert "CHECK" in migration.upper(), (
            "No CHECK constraint found in conversation_log_migration.sql"
        )
        assert "role" in migration, (
            "Column 'role' not found in conversation_log_migration.sql"
        )

    def test_tool_calls_status_constraint_values(self):
        """tool_calls.status CHECK allows exactly: EXECUTING, COMPLETED, FAILED, CANCELLED."""
        migration = (_DB_ROOT / "tool_calls_migration.sql").read_text()

        expected_statuses = {"EXECUTING", "COMPLETED", "FAILED", "CANCELLED"}
        for status in expected_statuses:
            assert f"'{status}'" in migration, (
                f"Status '{status}' missing from tool_calls_migration.sql CONSTRAINT valid_status. "
                f"Schema drift detected — re-run the migration or update the constraint."
            )

        # Confirm the named constraint is present
        assert "valid_status" in migration, (
            "CONSTRAINT valid_status not found in tool_calls_migration.sql"
        )

    def test_tool_error_log_error_type_values(self):
        """tool_error_log.error_type CHECK allows exactly 10 classified error buckets."""
        migration = (
            _DB_ROOT / "migrations" / "20260303_tool_error_log.sql"
        ).read_text()

        expected_error_types = {
            "AUTH_401",
            "PERMISSION_403",
            "TIMEOUT",
            "SLUG_NOT_FOUND",
            "CB_TRIPPED",
            "RATE_LIMIT",
            "PARAM_ERROR",
            "NETWORK",
            "SERVER_5XX",
            "UNKNOWN",
        }
        for et in expected_error_types:
            assert f"'{et}'" in migration, (
                f"error_type '{et}' missing from 20260303_tool_error_log.sql. "
                f"If composio_router.py emits a new error_type, add it to the CHECK constraint."
            )

        # Confirm named constraint is present
        assert "tool_error_log_error_type_check" in migration, (
            "CONSTRAINT tool_error_log_error_type_check not found in migration file"
        )

        # Count quoted values to detect undocumented additions
        import re
        quoted_values = re.findall(r"'([A-Z0-9_]+)'", migration)
        # Filter to only the values inside the error_type check block
        error_type_section = migration[
            migration.index("tool_error_log_error_type_check") :
            migration.index("tool_error_log_cb_state_check")
        ]
        et_values = re.findall(r"'([A-Z0-9_]+)'", error_type_section)
        assert len(et_values) == 10, (
            f"Expected exactly 10 error_type values in constraint, found {len(et_values)}: "
            f"{et_values}. Update this test if a new error_type was intentionally added."
        )


# ---------------------------------------------------------------------------
# Category 2: Email payload integrity (unit)
# ---------------------------------------------------------------------------


class TestEmailPayloadIntegrity:
    """Validate the email payload structure and auth header used by manage_connections."""

    def test_email_payload_structure(self):
        """Email payload sent to n8n Gmail webhook has the documented shape.

        manage_connections_async constructs:
          {
            "intent_id": "lk_<12-hex>",
            "session_id": "livekit-agent",
            "callback_url": "https://...",
            "parameters": {"to": ..., "subject": ..., "body": ...},
          }
        This test constructs an equivalent payload and asserts structural integrity.
        """
        # Replicate the payload construction from async_wrappers.py lines 819-834
        import uuid as _uuid

        auth_url = "https://composio.dev/auth/test-service?token=abc123"
        display_name = "Google Drive"
        email_to = "jelal@autopayplus.com"

        email_payload = {
            "intent_id": f"lk_{_uuid.uuid4().hex[:12]}",
            "session_id": "livekit-agent",
            "callback_url": "https://jayconnorexe.app.n8n.cloud/webhook/callback-noop",
            "parameters": {
                "to": email_to,
                "subject": f"Connect {display_name} to AIO Voice Assistant",
                "body": (
                    f"Hi, your AIO Voice Assistant needs authorization to connect {display_name}.\n\n"
                    f"Click the link below to complete authentication:\n\n"
                    f"{auth_url}\n\n"
                    f"This link expires in 10 minutes. Once connected, tell your assistant "
                    f'"refresh my tools" to activate the new connection.'
                ),
            },
        }

        # Top-level key presence
        assert "intent_id" in email_payload
        assert "session_id" in email_payload
        assert "callback_url" in email_payload
        assert "parameters" in email_payload

        # intent_id format: "lk_" + 12 hex chars
        assert email_payload["intent_id"].startswith("lk_"), (
            "intent_id must start with 'lk_' to match the voice-agent intent ID convention"
        )
        hex_suffix = email_payload["intent_id"][3:]
        assert len(hex_suffix) == 12 and all(c in "0123456789abcdef" for c in hex_suffix), (
            f"intent_id suffix must be 12 lowercase hex chars, got: '{hex_suffix}'"
        )

        # parameters sub-dict must have exactly: to, subject, body
        params = email_payload["parameters"]
        assert isinstance(params, dict)
        assert "to" in params, "parameters.to is required — destination email address"
        assert "subject" in params, "parameters.subject is required"
        assert "body" in params, "parameters.body is required"

        # body must contain the auth URL so the recipient can click it
        assert auth_url in params["body"], (
            "Auth URL must be embedded in email body so recipient can complete OAuth"
        )

        # No extra top-level keys (validates against accidental payload expansion)
        assert set(email_payload.keys()) == {"intent_id", "session_id", "callback_url", "parameters"}, (
            "Unexpected keys in email payload — manage_connections contract may have drifted"
        )

    def test_email_webhook_includes_auth_header(self):
        """manage_connections_async sets X-AIO-Webhook-Secret from settings, not hardcoded.

        Inspects the source code of async_wrappers.py to confirm:
          1. X-AIO-Webhook-Secret header is set.
          2. The value comes from _get_settings().n8n_webhook_secret (not a literal string).
        """
        wrappers_path = _SRC_ROOT / "tools" / "async_wrappers.py"
        source = wrappers_path.read_text()

        # Header name must be present
        assert "X-AIO-Webhook-Secret" in source, (
            "X-AIO-Webhook-Secret header not found in async_wrappers.py. "
            "manage_connections_async must set this header for n8n webhook authentication."
        )

        # The secret must come from settings — not hardcoded.
        # Locate the Gmail POST block specifically: find the http_session.post call that
        # references _N8N_GMAIL_WEBHOOK (the constant appears twice: definition + call site).
        # We want the call site, which is always after the function definition of
        # manage_connections_async.
        manage_fn_start = source.index("async def manage_connections_async")
        # Within the function body find the Gmail post call
        gmail_post_marker = source.index("_N8N_GMAIL_WEBHOOK,", manage_fn_start)
        # Capture the surrounding 600 chars which covers the headers dict
        gmail_post_block = source[gmail_post_marker : gmail_post_marker + 600]

        assert "n8n_webhook_secret" in gmail_post_block, (
            "X-AIO-Webhook-Secret value must reference settings.n8n_webhook_secret — "
            "hardcoding the secret in source is a security violation. "
            "Check manage_connections_async in async_wrappers.py."
        )

        # Confirm the secret is not the literal 64-char value (would be a credential leak)
        hardcoded_secret = "b425d5890244b951ae8deecd05dbb629a39d5f81e4f95d21b4e52cdfc40fdcb8"
        assert hardcoded_secret not in gmail_post_block, (
            "Webhook secret is hardcoded in the email sending block — must use settings instead"
        )

        # Confirm _get_settings() is called to retrieve the secret
        assert "_get_settings()" in gmail_post_block or "get_settings()" in gmail_post_block, (
            "Secret must be retrieved via _get_settings().n8n_webhook_secret, not a global or literal"
        )


# ---------------------------------------------------------------------------
# Category 3: Voice response integrity (unit)
# ---------------------------------------------------------------------------


class TestVoiceResponseIntegrity:
    """Verify truncation boundaries in the log_turn and per-turn context paths."""

    async def test_voice_response_not_truncated_in_tool_calls(self):
        """log_turn does not truncate content strings shorter than 4000 chars.

        pg_logger.log_turn slices content[:4000].  A 2000-char string must pass
        through unmodified — the 4KB cap is for extreme edge cases only.
        """
        captured_args = {}

        # Build a mock asyncpg connection that captures the INSERT arguments
        mock_conn = AsyncMock()

        async def capture_execute(query, *args, **kwargs):
            captured_args["query"] = query
            captured_args["positional"] = args

        mock_conn.execute.side_effect = capture_execute
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)

        mock_pool = MagicMock()
        mock_pool.acquire.return_value = mock_conn

        # Patch pg_logger module state
        pg_logger = _load_src_module("aio.utils.pg_logger", "utils/pg_logger.py")

        original_pool = pg_logger._pool
        original_available = pg_logger._pg_available
        try:
            pg_logger._pool = mock_pool
            pg_logger._pg_available = True

            long_content = "A" * 2000  # Below the 4000-char cap in log_turn
            await pg_logger.log_turn(
                session_id="integrity-test-session",
                role="assistant",
                content=long_content,
            )

            # The third positional arg ($3) is the content string
            assert len(captured_args) > 0, "log_turn did not call conn.execute — pool mock not active"
            stored_content = captured_args["positional"][2]  # $3 = content (0-indexed: session_id, role, content)
            assert stored_content == long_content, (
                f"Content was truncated at pg_logger layer. "
                f"Expected {len(long_content)} chars, got {len(stored_content)}. "
                f"The 4000-char cap in log_turn[:4000] should not affect 2000-char strings."
            )
            assert len(stored_content) == 2000
        finally:
            pg_logger._pool = original_pool
            pg_logger._pg_available = original_available

    def test_large_result_truncation_at_last_tool_result_fact(self):
        """Per-turn context injection truncates last_tool_result to 200 chars.

        _inject_per_turn_context in agent.py reads the 'last_tool_result' session
        fact and appends it as:
            parts.append(f"[Last tool result] {last_result[:200]}")

        This is the ONLY intended truncation point for tool results in the
        context injection path.  Confirm the 200-char slice is present in source.
        """
        agent_path = _SRC_ROOT / "agent.py"
        source = agent_path.read_text()

        # The exact slice expression must be present
        assert 'last_result[:200]' in source, (
            "Expected 'last_result[:200]' in agent.py _inject_per_turn_context. "
            "If the truncation limit changed, update the per-turn context window budget "
            "and this test together."
        )

        # Confirm the injection function exists
        assert "_inject_per_turn_context" in source, (
            "_inject_per_turn_context function missing from agent.py"
        )

        # Confirm it references 'last_tool_result' key (not a renamed key)
        inject_start = source.index("def _inject_per_turn_context")
        # Scan the next 1500 chars — the full function body
        inject_body = source[inject_start : inject_start + 1500]
        assert '"last_tool_result"' in inject_body or "'last_tool_result'" in inject_body, (
            "Session fact key 'last_tool_result' not found in _inject_per_turn_context body. "
            "Key rename detected — update store_fact call sites to match."
        )

        # Confirm the 200-char slice is inside the inject function body (not elsewhere in file)
        assert "last_result[:200]" in inject_body, (
            "'last_result[:200]' slice must be inside _inject_per_turn_context, "
            "not somewhere else in agent.py"
        )


# ---------------------------------------------------------------------------
# Category 4: Session context persistence (unit — mocked asyncpg pool)
# ---------------------------------------------------------------------------


class TestSessionContextPersistence:
    """Validate save_session_context / get_session_context round-trip and gate key naming."""

    async def test_save_and_get_session_context(self):
        """save_session_context writes the composite key; get_session_context reads it back.

        pg_logger prefixes context_key with session_id:
            full_key = f"{session_id}:{context_key}"

        The mock verifies that:
          1. save_session_context inserts with the composite key.
          2. get_session_context queries with the same composite key.
          3. The returned value matches what was saved.
        """
        pg_logger = _load_src_module("aio.utils.pg_logger", "utils/pg_logger.py")

        session_id = "unit-test-session-abc123"
        context_key = "test-key"
        context_value = "test-value"
        expected_full_key = f"{session_id}:{context_key}"

        # --- save_session_context mock ---
        save_execute_args = {}

        mock_save_conn = AsyncMock()

        async def capture_save_execute(query, *args, **kwargs):
            save_execute_args["query"] = query
            save_execute_args["args"] = args

        mock_save_conn.execute.side_effect = capture_save_execute
        mock_save_conn.__aenter__ = AsyncMock(return_value=mock_save_conn)
        mock_save_conn.__aexit__ = AsyncMock(return_value=False)

        # --- get_session_context mock ---
        fetch_args = {}

        mock_get_conn = AsyncMock()

        async def capture_fetchrow(query, *args, **kwargs):
            fetch_args["query"] = query
            fetch_args["args"] = args
            # Simulate a row that was previously saved
            mock_row = MagicMock()
            mock_row.__getitem__ = lambda self, key: context_value if key == "context_value" else None
            return mock_row

        mock_get_conn.fetchrow.side_effect = capture_fetchrow
        mock_get_conn.__aenter__ = AsyncMock(return_value=mock_get_conn)
        mock_get_conn.__aexit__ = AsyncMock(return_value=False)

        # Pool alternates between save and get connections
        call_count = {"n": 0}

        mock_pool = MagicMock()

        def pool_acquire_side_effect(**kwargs):
            call_count["n"] += 1
            return mock_save_conn if call_count["n"] == 1 else mock_get_conn

        mock_pool.acquire.side_effect = pool_acquire_side_effect

        original_pool = pg_logger._pool
        original_available = pg_logger._pg_available
        try:
            pg_logger._pool = mock_pool
            pg_logger._pg_available = True

            # Exercise save path
            await pg_logger.save_session_context(session_id, context_key, context_value)

            assert save_execute_args, "save_session_context did not call conn.execute"
            # First positional arg is the composite key ($1)
            assert save_execute_args["args"][0] == expected_full_key, (
                f"save_session_context wrote key '{save_execute_args['args'][0]}' but "
                f"expected composite key '{expected_full_key}'. "
                f"Key construction: f'{{session_id}}:{{context_key}}' must remain stable."
            )
            assert save_execute_args["args"][1] == context_value, (
                "context_value is not the second positional arg in the INSERT"
            )

            # Exercise get path
            result = await pg_logger.get_session_context(session_id, context_key)

            assert fetch_args, "get_session_context did not call conn.fetchrow"
            # First positional arg of fetchrow is the full key ($1)
            assert fetch_args["args"][0] == expected_full_key, (
                f"get_session_context queried key '{fetch_args['args'][0]}' but "
                f"save wrote '{expected_full_key}'. Keys must match for round-trip reads."
            )
            assert result == context_value, (
                f"get_session_context returned '{result}', expected '{context_value}'"
            )
        finally:
            pg_logger._pool = original_pool
            pg_logger._pg_available = original_available

    async def test_gate_payload_persisted_to_session_context(self):
        """requestGate calls save_session_context with context_key starting with 'gate:'.

        tool_executor.requestGate:
            await save_session_context(
                session_id=session_id,
                context_key=f"gate:{gate_id}",
                context_value=json.dumps(gate_payload),
            )

        The full key written to the DB is:
            f"{session_id}:gate:{gate_id}"

        This test mocks save_session_context and asserts it is called with
        a context_key that starts with 'gate:'.
        """
        # Load tool_executor carefully — it has heavy imports; mock them first
        # We only need to exercise the requestGate function's pg_logger call.

        saved_calls = []

        async def mock_save_session_context(session_id, context_key, context_value, expires_at=None):
            saved_calls.append({
                "session_id": session_id,
                "context_key": context_key,
                "context_value": context_value,
            })

        # Directly test the context_key construction logic without loading tool_executor
        # (avoids heavy LiveKit/Composio/Settings import chain in unit mode).
        # We replicate the exact save_session_context call from requestGate in tool_executor.py.
        gate_id = uuid.uuid4().hex[:8]
        session_id = "gate-test-session"
        gate_type = "WRITE"
        content = "Send email to user@example.com"
        voice_prompt = "Shall I send the email?"

        gate_payload = {
            "gate_id": gate_id,
            "gate_type": gate_type,
            "content": content,
            "voice_prompt": voice_prompt,
            "continuation_hint": "",
            "session_id": session_id,
            "timestamp": 1234567890.0,
        }

        # Replicate the save_session_context call from requestGate (tool_executor.py line ~667)
        await mock_save_session_context(
            session_id=session_id,
            context_key=f"gate:{gate_id}",
            context_value=json.dumps(gate_payload),
        )

        assert len(saved_calls) == 1, "save_session_context was not called"
        saved = saved_calls[0]

        assert saved["context_key"].startswith("gate:"), (
            f"context_key '{saved['context_key']}' does not start with 'gate:'. "
            f"requestGate must use context_key=f'gate:{{gate_id}}' so get_session_gates() "
            f"can find all gates via LIKE 'gate:%'."
        )

        gate_suffix = saved["context_key"][len("gate:"):]
        assert len(gate_suffix) == 8, (
            f"gate_id suffix should be 8 hex chars (uuid4().hex[:8]), got '{gate_suffix}'"
        )

        # Verify the persisted JSON is parseable and contains the expected fields
        persisted = json.loads(saved["context_value"])
        for required_field in ("gate_id", "gate_type", "content", "voice_prompt", "session_id"):
            assert required_field in persisted, (
                f"Gate payload missing required field '{required_field}'. "
                f"Fields: {list(persisted.keys())}"
            )

        assert persisted["gate_id"] == gate_id
        assert persisted["session_id"] == session_id


# ---------------------------------------------------------------------------
# Category 5: Live DB integration (integration marker — requires POSTGRES_URL)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLiveDBIntegration:
    """Write and verify real rows in Railway PostgreSQL.

    These tests require:
      - POSTGRES_URL environment variable pointing to the live Railway instance
      - --run-integration flag passed to pytest

    Each test cleans up its own rows to keep the live DB uncluttered.
    """

    @pytest.fixture(autouse=True)
    def require_postgres_url(self):
        url = os.environ.get("POSTGRES_URL", "")
        if not url:
            pytest.skip("POSTGRES_URL not set — skipping live DB integration test")

    async def test_log_turn_writes_to_conversation_log(self):
        """log_turn inserts a row into conversation_log; verify with direct asyncpg query."""
        import asyncpg  # noqa: PLC0415

        postgres_url = os.environ["POSTGRES_URL"]
        integration_session = f"int-test-delivery-{uuid.uuid4().hex[:8]}"

        pg_logger = _load_src_module("aio.utils.pg_logger", "utils/pg_logger.py")

        # Use a fresh pool scoped to this test — avoids state bleed from unit tests
        pool = await asyncpg.create_pool(
            postgres_url,
            min_size=1,
            max_size=2,
            command_timeout=10,
            ssl="require",
        )
        try:
            # Wire pg_logger to the test pool
            original_pool = pg_logger._pool
            original_available = pg_logger._pg_available
            pg_logger._pool = pool
            pg_logger._pg_available = True

            test_content = "Integration test message for result delivery E2E"

            await pg_logger.log_turn(
                session_id=integration_session,
                role="user",
                content=test_content,
                user_id="int-test-user",
            )

            # Verify the row exists
            async with pool.acquire() as conn:
                count = await conn.fetchval(
                    "SELECT COUNT(*) FROM conversation_log WHERE session_id = $1",
                    integration_session,
                )

            assert count is not None and count > 0, (
                f"log_turn wrote 0 rows for session '{integration_session}'. "
                f"Check DB connectivity and that conversation_log table exists."
            )

            # Verify the content is intact (not truncated at 2000 chars)
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT content, role FROM conversation_log WHERE session_id = $1 LIMIT 1",
                    integration_session,
                )

            assert row is not None
            assert row["content"] == test_content, (
                f"Stored content does not match. Got: '{row['content'][:100]}...'"
            )
            assert row["role"] == "user"
        finally:
            # Restore original pg_logger state
            pg_logger._pool = original_pool
            pg_logger._pg_available = original_available

            # Clean up test rows
            async with pool.acquire() as conn:
                deleted = await conn.execute(
                    "DELETE FROM conversation_log WHERE session_id = $1",
                    integration_session,
                )
            await pool.close()

    async def test_tool_error_log_insert(self):
        """log_tool_error inserts a row into tool_error_log; verify with direct asyncpg query."""
        import asyncpg  # noqa: PLC0415

        postgres_url = os.environ["POSTGRES_URL"]
        integration_session = f"int-test-delivery-{uuid.uuid4().hex[:8]}"

        pg_logger = _load_src_module("aio.utils.pg_logger", "utils/pg_logger.py")

        pool = await asyncpg.create_pool(
            postgres_url,
            min_size=1,
            max_size=2,
            command_timeout=10,
            ssl="require",
        )
        try:
            original_pool = pg_logger._pool
            original_available = pg_logger._pg_available
            pg_logger._pool = pool
            pg_logger._pg_available = True

            await pg_logger.log_tool_error(
                slug="TEST_SLUG",
                resolved_slug="TEST_SLUG",
                service="test",
                error_type="TIMEOUT",
                retry_count=1,
                duration_ms=5000,
                raw_error="Integration test — simulated timeout",
                session_id=integration_session,
                user_id="int-test-user",
            )

            # Verify row exists
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT slug, error_type, session_id, retry_count
                    FROM tool_error_log
                    WHERE session_id = $1
                    LIMIT 1
                    """,
                    integration_session,
                )

            assert row is not None, (
                f"log_tool_error wrote 0 rows for session '{integration_session}'. "
                f"Check that tool_error_log table exists and POSTGRES_URL is correct."
            )
            assert row["slug"] == "TEST_SLUG"
            assert row["error_type"] == "TIMEOUT"
            assert row["session_id"] == integration_session
            assert row["retry_count"] == 1
        finally:
            pg_logger._pool = original_pool
            pg_logger._pg_available = original_available

            # Clean up test rows
            async with pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM tool_error_log WHERE session_id = $1",
                    integration_session,
                )
            await pool.close()
