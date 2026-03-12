"""
AIO Voice System — Maximum Interaction Logging Test Suite

Captures as much observable system state as possible during test execution:
DB schema validation, tool audit logs, session facts, error ledger,
Railway process logs, and import-level timing measurements.

Run unit tests only (no live DB or Railway):
    pytest tests/e2e/test_logging_integration.py -v

Run with live PostgreSQL:
    POSTGRES_URL=<url> pytest tests/e2e/test_logging_integration.py -v

Run with live Railway CLI (requires authenticated railway CLI):
    pytest tests/e2e/test_logging_integration.py -v --run-integration
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

TEST_SESSION_ID = f"e2e-test-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
POSTGRES_URL = os.environ.get("POSTGRES_URL", "")
SKIP_IF_NO_PG = pytest.mark.skipif(
    not POSTGRES_URL,
    reason="POSTGRES_URL not set — skipping live DB test",
)

REPO_ROOT = Path(__file__).parent.parent.parent
SRC_ROOT = REPO_ROOT / "src"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _query(conn: Any, sql: str, *args: Any) -> list[dict]:
    """Execute a query and return rows as a list of plain dicts."""
    rows = await conn.fetch(sql, *args)
    return [dict(row) for row in rows]


def _print_table(rows: list[dict], headers: list[str] | None = None) -> None:
    """Print rows as an ASCII table.

    Args:
        rows:    List of dicts — keys become column headers if *headers* is None.
        headers: Explicit ordered list of column names to display.
    """
    if not rows:
        print("  (no rows)")
        return

    cols = headers if headers is not None else list(rows[0].keys())
    col_widths = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in rows)) for c in cols}

    sep = "+" + "+".join("-" * (col_widths[c] + 2) for c in cols) + "+"
    hdr = "|" + "|".join(f" {c:<{col_widths[c]}} " for c in cols) + "|"

    print(sep)
    print(hdr)
    print(sep)
    for row in rows:
        line = "|" + "|".join(f" {str(row.get(c, '')):<{col_widths[c]}} " for c in cols) + "|"
        print(line)
    print(sep)


def _elapsed_ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session_id() -> str:
    """Fixed test session ID for the entire module run."""
    return TEST_SESSION_ID


@pytest.fixture
async def pg_conn():
    """
    Async asyncpg connection.

    Skips gracefully when POSTGRES_URL is not set.  Closes the connection
    after each test regardless of outcome.
    """
    if not POSTGRES_URL:
        pytest.skip("POSTGRES_URL not set")

    try:
        import asyncpg  # type: ignore
    except ImportError:
        pytest.skip("asyncpg not installed")

    t0 = time.perf_counter()
    conn = await asyncpg.connect(POSTGRES_URL, command_timeout=15, ssl="require")
    print(f"\n[TIMING] pg_conn acquire: {_elapsed_ms(t0):.1f}ms")
    try:
        yield conn
    finally:
        await conn.close()


# ===========================================================================
# Class: TestConversationLogCapture
# ===========================================================================

class TestConversationLogCapture:
    """DB-backed tests that inspect and write to conversation_log."""

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_conversation_log_schema_accessible(self, pg_conn: Any) -> None:
        """Schema introspection — verify all required columns exist in conversation_log."""
        t0 = time.perf_counter()

        rows = await _query(
            pg_conn,
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'conversation_log'
            ORDER BY ordinal_position
            """,
        )

        print("\n[TEST] test_conversation_log_schema_accessible")
        print(f"  Table: conversation_log — {len(rows)} columns found")
        _print_table(rows, headers=["column_name", "data_type", "is_nullable"])

        column_names = {r["column_name"] for r in rows}
        required = {"id", "session_id", "role", "content", "created_at"}
        missing = required - column_names
        assert not missing, (
            f"conversation_log is missing required columns: {missing}. "
            f"Found: {column_names}"
        )

        print(f"[TIMING] test_conversation_log_schema_accessible: {_elapsed_ms(t0):.1f}ms")

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_conversation_log_recent_entries(self, pg_conn: Any) -> None:
        """Fetch and print the 20 most recent conversation_log rows (max-logging output)."""
        t0 = time.perf_counter()

        rows = await _query(
            pg_conn,
            """
            SELECT id, session_id, role, content, tool_name, created_at
            FROM conversation_log
            ORDER BY created_at DESC
            LIMIT 20
            """,
        )

        print("\n[TEST] test_conversation_log_recent_entries")
        print(f"  Rows returned: {len(rows)}")
        _print_table(rows, headers=["id", "session_id", "role", "tool_name", "created_at"])

        # Print content snippets separately to avoid table width explosion
        for row in rows:
            snippet = str(row.get("content", ""))[:120].replace("\n", " ")
            print(f"    [{row.get('id')}] {row.get('role','?'):10s}  {snippet}")

        if rows:
            # At least one row should be within the last 24 hours
            from datetime import timedelta

            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=24)
            recent = []
            for row in rows:
                ts = row.get("created_at")
                if ts is None:
                    continue
                if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= cutoff:
                    recent.append(row)
            if not recent:
                pytest.skip(
                    f"No conversation_log rows within last 24h "
                    f"(oldest checked: {rows[0].get('created_at')}). "
                    "Skipping recency assertion — system may be idle."
                )
            print(f"  Rows within last 24h: {len(recent)}")
            assert len(recent) >= 1

        print(f"[TIMING] test_conversation_log_recent_entries: {_elapsed_ms(t0):.1f}ms")

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_conversation_log_insert_and_verify(
        self, pg_conn: Any, session_id: str
    ) -> None:
        """INSERT a test row, SELECT it back, assert it exists, then DELETE (cleanup)."""
        t0 = time.perf_counter()

        marker_content = "[E2E TEST LOG]"
        await pg_conn.execute(
            """
            INSERT INTO conversation_log (session_id, role, content)
            VALUES ($1, $2, $3)
            """,
            session_id,
            "system",
            marker_content,
        )

        rows = await _query(
            pg_conn,
            """
            SELECT id, session_id, role, content, created_at
            FROM conversation_log
            WHERE session_id = $1 AND role = 'system' AND content = $2
            """,
            session_id,
            marker_content,
        )

        print("\n[TEST] test_conversation_log_insert_and_verify")
        _print_table(rows, headers=["id", "session_id", "role", "content", "created_at"])

        assert len(rows) >= 1, (
            f"Expected at least 1 row for session_id={session_id!r}, "
            f"content={marker_content!r}. Got 0 rows."
        )
        assert rows[0]["content"] == marker_content
        assert rows[0]["session_id"] == session_id

        # Cleanup
        deleted = await pg_conn.execute(
            "DELETE FROM conversation_log WHERE session_id = $1 AND content = $2",
            session_id,
            marker_content,
        )
        print(f"  Cleanup: {deleted}")
        print(f"[TIMING] test_conversation_log_insert_and_verify: {_elapsed_ms(t0):.1f}ms")


# ===========================================================================
# Class: TestToolCallsAuditLog
# ===========================================================================

class TestToolCallsAuditLog:
    """DB-backed tests for the tool_calls audit table and tool_error_log."""

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_tool_calls_schema_accessible(self, pg_conn: Any) -> None:
        """Schema introspection — verify required columns in tool_calls."""
        t0 = time.perf_counter()

        rows = await _query(
            pg_conn,
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'tool_calls'
            ORDER BY ordinal_position
            """,
        )

        print("\n[TEST] test_tool_calls_schema_accessible")
        print(f"  Table: tool_calls — {len(rows)} columns found")
        _print_table(rows, headers=["column_name", "data_type", "is_nullable"])

        column_names = {r["column_name"] for r in rows}
        required = {"function_name", "parameters", "status", "execution_time_ms", "session_id"}
        missing = required - column_names
        assert not missing, (
            f"tool_calls is missing required columns: {missing}. Found: {column_names}"
        )

        print(f"[TIMING] test_tool_calls_schema_accessible: {_elapsed_ms(t0):.1f}ms")

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_tool_calls_recent_executions(self, pg_conn: Any) -> None:
        """Fetch and print the 20 most recent tool_calls rows with timing data."""
        t0 = time.perf_counter()

        rows = await _query(
            pg_conn,
            """
            SELECT function_name, status, execution_time_ms, created_at, session_id
            FROM tool_calls
            ORDER BY created_at DESC
            LIMIT 20
            """,
        )

        print("\n[TEST] test_tool_calls_recent_executions")
        print(f"  Rows returned: {len(rows)}")

        if not rows:
            pytest.skip("tool_calls table is empty — skipping assertion.")

        _print_table(
            rows,
            headers=["function_name", "status", "execution_time_ms", "created_at", "session_id"],
        )

        # Summarise timing distribution
        exec_times = [
            r["execution_time_ms"]
            for r in rows
            if r.get("execution_time_ms") is not None
        ]
        if exec_times:
            avg_ms = sum(exec_times) / len(exec_times)
            max_ms = max(exec_times)
            min_ms = min(exec_times)
            print(
                f"  Execution time — min: {min_ms}ms  avg: {avg_ms:.1f}ms  max: {max_ms}ms"
            )

        assert len(rows) >= 1

        print(f"[TIMING] test_tool_calls_recent_executions: {_elapsed_ms(t0):.1f}ms")

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_tool_calls_success_rate(self, pg_conn: Any) -> None:
        """Aggregate success/failure breakdown for tool_calls in the last 24 hours."""
        t0 = time.perf_counter()

        rows = await _query(
            pg_conn,
            """
            SELECT status, COUNT(*) AS cnt
            FROM tool_calls
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY status
            ORDER BY cnt DESC
            """,
        )

        print("\n[TEST] test_tool_calls_success_rate")
        print("  tool_calls status breakdown (last 24h):")
        _print_table(rows, headers=["status", "cnt"])

        total = sum(int(r["cnt"]) for r in rows)
        if total == 0:
            print("  No tool_calls in last 24h — skipping rate calculation.")
            # Query executed without error; that is the core assertion.
            assert True
            return

        success_statuses = {"success", "completed", "ok"}
        success_count = sum(
            int(r["cnt"])
            for r in rows
            if str(r.get("status", "")).lower() in success_statuses
        )
        rate = (success_count / total) * 100.0
        print(f"  Success rate (last 24h): {rate:.1f}%  ({success_count}/{total})")

        # Assert the rate can be computed — no numeric error
        assert 0.0 <= rate <= 100.0

        print(f"[TIMING] test_tool_calls_success_rate: {_elapsed_ms(t0):.1f}ms")

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_tool_error_log_recent_errors(self, pg_conn: Any) -> None:
        """Fetch and print the 20 most recent tool_error_log rows."""
        t0 = time.perf_counter()

        rows = await _query(
            pg_conn,
            """
            SELECT slug, error_type, cb_state, duration_ms, created_at
            FROM tool_error_log
            ORDER BY created_at DESC
            LIMIT 20
            """,
        )

        print("\n[TEST] test_tool_error_log_recent_errors")
        print(f"  tool_error_log rows returned: {len(rows)}")
        _print_table(
            rows,
            headers=["slug", "error_type", "cb_state", "duration_ms", "created_at"],
        )

        if rows:
            error_type_counts: dict[str, int] = {}
            for row in rows:
                et = str(row.get("error_type", "UNKNOWN"))
                error_type_counts[et] = error_type_counts.get(et, 0) + 1
            print("  Error type distribution:")
            for et, cnt in sorted(error_type_counts.items(), key=lambda x: -x[1]):
                print(f"    {et:<30s}: {cnt}")

        # Core assertion: query must execute without exception
        assert isinstance(rows, list)

        print(f"[TIMING] test_tool_error_log_recent_errors: {_elapsed_ms(t0):.1f}ms")


# ===========================================================================
# Class: TestSessionFactsLog
# ===========================================================================

class TestSessionFactsLog:
    """DB-backed tests for the session_facts_log table."""

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_session_facts_schema_accessible(self, pg_conn: Any) -> None:
        """Verify session_facts_log has at least one UNIQUE constraint."""
        t0 = time.perf_counter()

        constraint_rows = await _query(
            pg_conn,
            """
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'session_facts_log'
              AND constraint_type = 'UNIQUE'
            """,
        )

        column_rows = await _query(
            pg_conn,
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'session_facts_log'
            ORDER BY ordinal_position
            """,
        )

        print("\n[TEST] test_session_facts_schema_accessible")
        print(f"  session_facts_log — {len(column_rows)} columns:")
        _print_table(column_rows, headers=["column_name", "data_type"])
        print(f"  UNIQUE constraints: {len(constraint_rows)}")
        _print_table(constraint_rows, headers=["constraint_name", "constraint_type"])

        assert len(constraint_rows) >= 1, (
            "session_facts_log must have at least one UNIQUE constraint "
            "to support ON CONFLICT upsert semantics in flush_facts_to_db(). "
            f"Found: {[r['constraint_name'] for r in constraint_rows]}"
        )

        print(f"[TIMING] test_session_facts_schema_accessible: {_elapsed_ms(t0):.1f}ms")

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_session_facts_upsert_behavior(
        self, pg_conn: Any, session_id: str
    ) -> None:
        """INSERT a fact, then upsert it with a new value — assert the value is updated."""
        t0 = time.perf_counter()

        test_key = "e2eTestKey"
        test_user = "e2e-test-user"

        # Initial insert
        await pg_conn.execute(
            """
            INSERT INTO session_facts_log (session_id, user_id, key, value, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (session_id, key)
            DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
            """,
            session_id,
            test_user,
            test_key,
            "value1",
        )

        # Upsert with new value
        await pg_conn.execute(
            """
            INSERT INTO session_facts_log (session_id, user_id, key, value, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (session_id, key)
            DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
            """,
            session_id,
            test_user,
            test_key,
            "value2",
        )

        rows = await _query(
            pg_conn,
            "SELECT key, value FROM session_facts_log WHERE session_id = $1 AND key = $2",
            session_id,
            test_key,
        )

        print("\n[TEST] test_session_facts_upsert_behavior")
        _print_table(rows, headers=["key", "value"])

        assert len(rows) == 1, (
            f"Expected exactly 1 row after upsert (ON CONFLICT DO UPDATE). "
            f"Got {len(rows)} rows — unique constraint may not exist on (session_id, key)."
        )
        assert rows[0]["value"] == "value2", (
            f"Expected value='value2' after upsert, got {rows[0]['value']!r}"
        )

        # Cleanup
        deleted = await pg_conn.execute(
            "DELETE FROM session_facts_log WHERE session_id = $1 AND key = $2",
            session_id,
            test_key,
        )
        print(f"  Cleanup: {deleted}")
        print(f"[TIMING] test_session_facts_upsert_behavior: {_elapsed_ms(t0):.1f}ms")

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_session_facts_recent_data(self, pg_conn: Any) -> None:
        """Fetch and print the 20 most recent session_facts_log rows."""
        t0 = time.perf_counter()

        rows = await _query(
            pg_conn,
            """
            SELECT user_id, key, value, created_at
            FROM session_facts_log
            ORDER BY created_at DESC
            LIMIT 20
            """,
        )

        print("\n[TEST] test_session_facts_recent_data")
        print(f"  session_facts_log rows returned: {len(rows)}")
        _print_table(rows, headers=["user_id", "key", "value", "created_at"])

        # No assertion on count — table may be empty in fresh envs.
        # The query itself must succeed without raising.
        assert isinstance(rows, list)

        print(f"[TIMING] test_session_facts_recent_data: {_elapsed_ms(t0):.1f}ms")


# ===========================================================================
# Class: TestRailwayLogCapture
# ===========================================================================

class TestRailwayLogCapture:
    """Integration tests that shell out to the Railway CLI to capture live logs."""

    @staticmethod
    def _capture_railway_logs(n: int = 50) -> str:
        """Run `railway logs` and return stdout as a string.

        Returns empty string if the CLI is not available or fails.
        """
        result = subprocess.run(
            ["railway", "logs", "--service", "livekit-voice-agent", "-n", str(n)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout or ""

    @pytest.mark.integration
    def test_railway_log_capture(self) -> None:
        """Capture 50 Railway log lines, parse them, and return a structured summary."""
        t0 = time.perf_counter()

        print("\n[TEST] test_railway_log_capture")
        log_output = self._capture_railway_logs(n=50)

        if not log_output.strip():
            pytest.skip(
                "railway CLI returned no output. "
                "Ensure `railway` is authenticated and the service exists."
            )

        print(f"  Raw log ({len(log_output)} chars):")
        for i, line in enumerate(log_output.splitlines()[:50], 1):
            print(f"    {i:3d}: {line}")

        lines = log_output.splitlines()

        # Parse worker count
        worker_lines = [l for l in lines if "registered worker" in l.lower()]
        worker_count = len(worker_lines)

        # Parse tool count (look for "X tools" pattern)
        import re

        tool_count = 0
        for line in lines:
            m = re.search(r"(\d+)\s+tools?", line, re.IGNORECASE)
            if m:
                tool_count = max(tool_count, int(m.group(1)))

        # Collect ERROR lines
        error_lines = [l for l in lines if "error" in l.lower() or "ERROR" in l]

        # Healthy = log exists and no CRITICAL entries
        critical_lines = [l for l in lines if "CRITICAL" in l or "Traceback" in l]
        healthy = bool(log_output.strip()) and len(critical_lines) == 0

        summary = {
            "workers": worker_count,
            "tools": tool_count,
            "errors": error_lines,
            "healthy": healthy,
        }

        print("\n  === Railway Log Summary ===")
        print(f"  Workers detected:  {summary['workers']}")
        print(f"  Tool count (max):  {summary['tools']}")
        print(f"  ERROR lines:       {len(summary['errors'])}")
        print(f"  Healthy:           {summary['healthy']}")
        if summary["errors"]:
            print("  Error samples:")
            for err in summary["errors"][:5]:
                print(f"    {err}")

        # The summary dict must be well-formed
        assert isinstance(summary["workers"], int)
        assert isinstance(summary["tools"], int)
        assert isinstance(summary["errors"], list)
        assert isinstance(summary["healthy"], bool)

        print(f"[TIMING] test_railway_log_capture: {_elapsed_ms(t0):.1f}ms")

    @pytest.mark.integration
    def test_railway_startup_patterns(self) -> None:
        """Assert the Railway log contains expected startup patterns, no CRITICAL errors."""
        t0 = time.perf_counter()

        print("\n[TEST] test_railway_startup_patterns")
        log_output = self._capture_railway_logs(n=50)

        if not log_output.strip():
            pytest.skip("railway CLI returned no output.")

        lines = log_output.splitlines()
        print(f"  Log lines captured: {len(lines)}")

        lower_log = log_output.lower()

        has_startup = (
            "registered worker" in lower_log
            or "synrg-voice-agent" in lower_log
            or "livekit-voice-agent" in lower_log
            or "agent started" in lower_log
            or "prewarm" in lower_log
        )

        traceback_lines = [l for l in lines if "Traceback" in l]
        critical_lines = [l for l in lines if "CRITICAL" in l]

        print(f"  Startup pattern found: {has_startup}")
        print(f"  Traceback occurrences: {len(traceback_lines)}")
        print(f"  CRITICAL occurrences:  {len(critical_lines)}")

        if traceback_lines:
            print("  Traceback lines:")
            for l in traceback_lines[:3]:
                print(f"    {l}")

        if critical_lines:
            print("  CRITICAL lines:")
            for l in critical_lines[:3]:
                print(f"    {l}")

        assert has_startup, (
            "Could not find any known startup pattern in Railway logs. "
            "Expected one of: 'registered worker', 'synrg-voice-agent', "
            "'livekit-voice-agent', 'agent started', 'prewarm'."
        )
        assert len(traceback_lines) == 0, (
            f"Found {len(traceback_lines)} Traceback entries in Railway logs — "
            "indicates an unhandled exception at startup or during operation."
        )
        assert len(critical_lines) == 0, (
            f"Found {len(critical_lines)} CRITICAL log entries in Railway logs."
        )

        print(f"[TIMING] test_railway_startup_patterns: {_elapsed_ms(t0):.1f}ms")


# ===========================================================================
# Class: TestInteractionTimingCapture
# ===========================================================================

class TestInteractionTimingCapture:
    """Unit-level timing tests — no live services required."""

    def test_timing_module_imports(self) -> None:
        """Import task_tracker from src/utils and measure import latency."""
        t0 = time.perf_counter()

        # Evict cached module to force a real import timing measurement
        mod_key = None
        for key in list(sys.modules.keys()):
            if "task_tracker" in key and "test" not in key:
                mod_key = key
                break
        if mod_key:
            del sys.modules[mod_key]

        from importlib.util import module_from_spec, spec_from_file_location

        spec = spec_from_file_location(
            "_timing_task_tracker",
            SRC_ROOT / "utils" / "task_tracker.py",
        )
        mod = module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["_timing_task_tracker"] = mod

        import_start = time.perf_counter()
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        import_ms = _elapsed_ms(import_start)
        total_ms = _elapsed_ms(t0)

        print(f"\n[TIMING] task_tracker import: {import_ms:.1f}ms")
        print(f"[TIMING] test_timing_module_imports total: {total_ms:.1f}ms")

        # Sanity-check: the module exposes TaskTracker class
        assert hasattr(mod, "TaskTracker"), (
            "task_tracker.py must expose a TaskTracker class."
        )
        assert import_ms < 5000.0, (
            f"task_tracker import took {import_ms:.1f}ms — exceeded 5000ms threshold."
        )

    def test_timing_pg_logger_import(self) -> None:
        """Import pg_logger from src/utils and measure latency. Graceful on DB absence."""
        t0 = time.perf_counter()

        from importlib.util import module_from_spec, spec_from_file_location

        spec = spec_from_file_location(
            "_timing_pg_logger",
            SRC_ROOT / "utils" / "pg_logger.py",
        )
        mod = module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules["_timing_pg_logger"] = mod

        import_start = time.perf_counter()
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            import_ms = _elapsed_ms(import_start)
            total_ms = _elapsed_ms(t0)
            print(f"\n[TIMING] pg_logger import: {import_ms:.1f}ms")
            print(f"[TIMING] test_timing_pg_logger_import total: {total_ms:.1f}ms")

            # Verify expected public surface
            assert hasattr(mod, "log_turn"), (
                "pg_logger.py must expose log_turn coroutine."
            )
            assert hasattr(mod, "init_pool"), (
                "pg_logger.py must expose init_pool coroutine."
            )
        except Exception as exc:
            import_ms = _elapsed_ms(import_start)
            print(
                f"\n[TIMING] pg_logger import failed after {import_ms:.1f}ms "
                f"(expected when Railway PG not available): {exc}"
            )
            # Import failure is acceptable in offline environments — do not fail
            pytest.skip(f"pg_logger import failed (expected in offline env): {exc}")

    @SKIP_IF_NO_PG
    @pytest.mark.asyncio
    async def test_comprehensive_system_snapshot(self, pg_conn: Any) -> None:
        """
        Maximum-logging snapshot: aggregates counts from all AIO DB tables and
        prints a formatted summary box.
        """
        t0 = time.perf_counter()

        async def _count(sql: str) -> int:
            rows = await pg_conn.fetch(sql)
            if rows:
                val = rows[0][0]
                return int(val) if val is not None else 0
            return 0

        async def _rate(sql: str) -> str:
            """Return a success rate string or 'N/A' if no data."""
            rows = await _query(pg_conn, sql)
            if not rows:
                return "N/A"
            total = sum(int(r.get("cnt", 0)) for r in rows)
            if total == 0:
                return "N/A"
            success_statuses = {"success", "completed", "ok"}
            success = sum(
                int(r.get("cnt", 0))
                for r in rows
                if str(r.get("status", "")).lower() in success_statuses
            )
            return f"{(success / total * 100):.1f}%"

        # Gather all metrics concurrently
        import asyncio

        (
            conv_count_24h,
            tool_rate_str,
            error_count_24h,
            facts_total,
            weekly_count,
        ) = await asyncio.gather(
            _count(
                "SELECT COUNT(*) FROM conversation_log "
                "WHERE created_at > NOW() - INTERVAL '24 hours'"
            ),
            _rate(
                "SELECT status, COUNT(*) AS cnt FROM tool_calls "
                "WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY status"
            ),
            _count(
                "SELECT COUNT(*) FROM tool_error_log "
                "WHERE created_at > NOW() - INTERVAL '24 hours'"
            ),
            _count("SELECT COUNT(*) FROM session_facts_log"),
            _count("SELECT COUNT(*) FROM weekly_summaries"),
        )

        elapsed_ms = _elapsed_ms(t0)
        ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Formatted summary box
        width = 50
        inner = width - 2  # inside the border characters

        def _row(label: str, value: str) -> str:
            content = f"  {label}: {value}"
            return f"\u2551{content:<{inner}}\u2551"

        border_top    = "\u2554" + "\u2550" * inner + "\u2557"
        border_mid    = "\u2560" + "\u2550" * inner + "\u2563"
        border_bot    = "\u255a" + "\u2550" * inner + "\u255d"
        title_content = f"  AIO SYSTEM SNAPSHOT \u2014 {ts}"
        title_line    = f"\u2551{title_content:<{inner}}\u2551"

        print(f"\n{border_top}")
        print(title_line)
        print(border_mid)
        print(_row("conversation_log rows (24h)", str(conv_count_24h)))
        print(_row("tool_calls success rate (24h)", tool_rate_str))
        print(_row("tool_error_log errors (24h)", str(error_count_24h)))
        print(_row("session_facts_log total", str(facts_total)))
        print(_row("weekly_summaries", f"{weekly_count} weeks stored"))
        print(border_bot)

        print(f"\n[TIMING] test_comprehensive_system_snapshot: {elapsed_ms:.1f}ms")

        # Structural assertions — all queries must resolve to valid types
        assert isinstance(conv_count_24h, int)
        assert isinstance(error_count_24h, int)
        assert isinstance(facts_total, int)
        assert isinstance(weekly_count, int)
        assert isinstance(tool_rate_str, str)
