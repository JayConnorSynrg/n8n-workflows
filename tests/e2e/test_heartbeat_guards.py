"""tests/e2e/test_heartbeat_guards.py

Tests for the heartbeat guard fixes in agent.py:
  - asyncio.create_task (NOT ensure_future) for progress say
  - .add_done_callback for exception logging
  - elif _hb_session_id: guard (not bare else:)

Source: /Users/jelalconnor/CODING/N8N/Workflows/src/agent.py
        /Users/jelalconnor/CODING/N8N/Workflows/src/utils/task_tracker.py
"""

import asyncio
import time
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_AGENT_PATH = "/Users/jelalconnor/CODING/N8N/Workflows/src/agent.py"
_TASK_TRACKER_PATH = "/Users/jelalconnor/CODING/N8N/Workflows/src/utils/task_tracker.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def agent_source() -> str:
    """Return the full contents of src/agent.py as a string."""
    with open(_AGENT_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def task_tracker_source() -> str:
    """Return the full contents of src/utils/task_tracker.py as a string."""
    with open(_TASK_TRACKER_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Helper: extract a window of lines around a match
# ---------------------------------------------------------------------------

def _lines_around(source: str, anchor: str, before: int = 20, after: int = 20) -> str:
    """Return the slice of *source* spanning *before* lines before and *after*
    lines after the first line that contains *anchor*.  Returns empty string
    if the anchor is not found."""
    lines = source.splitlines()
    for idx, line in enumerate(lines):
        if anchor in line:
            start = max(0, idx - before)
            end = min(len(lines), idx + after + 1)
            return "\n".join(lines[start:end])
    return ""


def _lines_after(source: str, anchor: str, n: int = 5) -> str:
    """Return *n* lines starting from (and including) the line that contains
    *anchor*.  Returns empty string if the anchor is not found."""
    lines = source.splitlines()
    for idx, line in enumerate(lines):
        if anchor in line:
            end = min(len(lines), idx + n + 1)
            return "\n".join(lines[idx:end])
    return ""


# ===========================================================================
# Class: TestHeartbeatSourceCode
# Static analysis of agent.py / task_tracker.py — no imports required.
# ===========================================================================

class TestHeartbeatSourceCode:
    """Verify the heartbeat guard implementation via source-level assertions."""

    # -----------------------------------------------------------------------
    # 1. asyncio.create_task — NOT ensure_future
    # -----------------------------------------------------------------------

    def test_create_task_not_ensure_future_in_heartbeat(self, agent_source: str) -> None:
        """The progress-say call inside the heartbeat must use create_task."""
        anchor = "still working on that in the background"
        window = _lines_around(agent_source, anchor, before=20, after=20)

        assert window, (
            f"Could not find anchor '{anchor}' in {_AGENT_PATH}. "
            "The heartbeat progress-say block may have moved."
        )
        assert "asyncio.create_task" in window, (
            "Expected 'asyncio.create_task' within ±20 lines of the heartbeat "
            "progress-say anchor.  Found window:\n" + window
        )
        assert "asyncio.ensure_future" not in window, (
            "Found forbidden 'asyncio.ensure_future' within ±20 lines of the "
            "heartbeat progress-say anchor.  Window:\n" + window
        )

    # -----------------------------------------------------------------------
    # 2. add_done_callback present on the say task
    # -----------------------------------------------------------------------

    def test_done_callback_present_on_say_task(self, agent_source: str) -> None:
        """The asyncio.create_task(session_ref.say(...)) call must be
        immediately followed (within 5 lines) by .add_done_callback(."""
        anchor = "asyncio.create_task(session_ref.say("
        window = _lines_after(agent_source, anchor, n=5)

        assert window, (
            f"Could not find anchor '{anchor}' in {_AGENT_PATH}."
        )
        assert ".add_done_callback(" in window, (
            "Expected '.add_done_callback(' within 5 lines of "
            "'asyncio.create_task(session_ref.say('. Found:\n" + window
        )

    # -----------------------------------------------------------------------
    # 3. done_callback logs a warning with exception text
    # -----------------------------------------------------------------------

    def test_done_callback_logs_warning(self, agent_source: str) -> None:
        """The done-callback lambda must invoke logger.warning and mention
        t.exception()."""
        anchor = ".add_done_callback("
        window = _lines_after(agent_source, anchor, n=3)

        assert window, (
            f"Could not find '.add_done_callback(' in {_AGENT_PATH}."
        )
        assert "logger.warning" in window, (
            "Expected 'logger.warning' inside the done_callback.  Found:\n" + window
        )
        assert "t.exception()" in window, (
            "Expected 't.exception()' inside the done_callback (exception "
            "introspection).  Found:\n" + window
        )

    # -----------------------------------------------------------------------
    # 4. elif guard — not bare else:
    # -----------------------------------------------------------------------

    def test_elif_not_else_for_session_cleanup(self, agent_source: str) -> None:
        """Cleanup pops must be guarded by 'elif _hb_session_id:' not 'else:'.

        Strategy: anchor on 'elif _hb_session_id:' and verify the pop calls
        appear within the next 5 lines.  Then verify there is no bare 'else:'
        between the elif line and those pop calls (a tight 3-line window that
        would not capture the unrelated inner `else:` from the 60s-elapsed
        branch above).
        """
        elif_anchor = "elif _hb_session_id:"
        # Find the elif line and take the next 5 lines to locate the pops.
        window_elif = _lines_after(agent_source, elif_anchor, n=5)

        assert window_elif, (
            f"Could not find '{elif_anchor}' in {_AGENT_PATH}. "
            "The delegation-cleanup block may have moved."
        )

        # Both pop calls must appear within 5 lines of the elif.
        assert "_delegation_active_since.pop(_hb_session_id" in window_elif, (
            "Expected '_delegation_active_since.pop(_hb_session_id' within 5 lines "
            "of 'elif _hb_session_id:'.  Found:\n" + window_elif
        )
        assert "_delegation_progress_said.pop(_hb_session_id" in window_elif, (
            "Expected '_delegation_progress_said.pop(_hb_session_id' within 5 lines "
            "of 'elif _hb_session_id:'.  Found:\n" + window_elif
        )

        # Within this tight elif→pop window, no bare 'else:' should appear
        # (that would indicate the old unguarded else: pattern).
        lines = window_elif.splitlines()
        bare_else_lines = [ln for ln in lines if ln.strip() == "else:"]
        assert not bare_else_lines, (
            "Found bare 'else:' in the elif→pop window — the fix requires "
            "'elif _hb_session_id:' as the sole guard.  Offending lines:\n"
            + "\n".join(bare_else_lines)
        )

    # -----------------------------------------------------------------------
    # 5. Heartbeat interval constant ≤ 4.0 s
    # -----------------------------------------------------------------------

    def test_heartbeat_interval_constant(self, agent_source: str) -> None:
        """HEARTBEAT_INTERVAL must be defined and ≤ 4.0 seconds.

        Scans ALL lines in agent.py for the assignment pattern to avoid
        matching comment/docstring mentions first.
        """
        # Scan every line for the assignment (not a comment or docstring mention).
        for line in agent_source.splitlines():
            stripped = line.strip()
            # Must be an assignment: 'HEARTBEAT_INTERVAL = <number>'
            # Skip lines where the token appears only after a '#' or in a '-'.
            if not stripped.startswith("HEARTBEAT_INTERVAL"):
                continue
            if "=" not in stripped:
                continue
            lhs, _, rhs = stripped.partition("=")
            if lhs.strip() != "HEARTBEAT_INTERVAL":
                continue
            # rhs may be "4.0   # Assess every 4 seconds"
            value_str = rhs.strip().split()[0].rstrip(",;)")
            try:
                value = float(value_str)
                assert value <= 4.0, (
                    f"HEARTBEAT_INTERVAL is {value}s — must be ≤ 4.0s per KPI."
                )
                return
            except ValueError:
                pass

        pytest.fail(
            f"Could not find a numeric HEARTBEAT_INTERVAL assignment in {_AGENT_PATH}.  "
            "Expected a line like: HEARTBEAT_INTERVAL = 4.0"
        )

    # -----------------------------------------------------------------------
    # 6. Stall threshold constant ≤ 8.0 s
    # -----------------------------------------------------------------------

    def test_stall_threshold_constant(self, task_tracker_source: str) -> None:
        """TaskTracker default stall_threshold_seconds must be ≤ 8.0 s."""
        anchor = "stall_threshold_seconds"
        window = _lines_around(task_tracker_source, anchor, before=2, after=2)

        assert window, (
            f"Could not find 'stall_threshold_seconds' in {_TASK_TRACKER_PATH}."
        )

        # The default is in the __init__ signature: stall_threshold_seconds: float = 8.0
        for line in window.splitlines():
            if "stall_threshold_seconds" in line and "=" in line:
                parts = line.split("=")
                try:
                    value = float(parts[-1].strip().rstrip("),"))
                    assert value <= 8.0, (
                        f"stall_threshold_seconds default is {value}s — "
                        "must be ≤ 8.0s per KPI green threshold."
                    )
                    return
                except ValueError:
                    pass

        pytest.fail(
            f"Could not parse a numeric default for stall_threshold_seconds.  "
            f"Context:\n{window}"
        )


# ===========================================================================
# Class: TestHeartbeatBehavior
# Unit tests using standard asyncio + unittest.mock — no live env required.
# ===========================================================================

class TestHeartbeatBehavior:
    """Behavioral unit tests for the heartbeat guard patterns."""

    # -----------------------------------------------------------------------
    # 7. done_callback captures exception
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_task_captures_exception_via_callback(self) -> None:
        """Verify that the add_done_callback pattern correctly captures an
        exception raised inside a task — mirrors the production pattern."""
        _t0 = time.monotonic()

        captured: list[BaseException] = []

        async def _raises() -> None:
            raise ValueError("heartbeat-test-error")

        task = asyncio.create_task(_raises())
        task.add_done_callback(
            lambda t: captured.append(t.exception())
            if not t.cancelled() and t.exception()
            else None
        )

        # Wait for the task to complete (suppress the unhandled-exception log).
        try:
            await task
        except ValueError:
            pass

        # Yield control so callbacks are dispatched.
        await asyncio.sleep(0)

        elapsed_ms = (time.monotonic() - _t0) * 1000
        print(f"[TIMING] test_create_task_captures_exception_via_callback: {elapsed_ms:.1f}ms")

        assert len(captured) == 1, (
            "Expected exactly one exception captured by done_callback; "
            f"got {captured!r}"
        )
        assert isinstance(captured[0], ValueError), (
            f"Expected ValueError, got {type(captured[0])}"
        )
        assert "heartbeat-test-error" in str(captured[0])

    # -----------------------------------------------------------------------
    # 8. elif guard prevents empty-session cleanup
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_elif_guard_prevents_empty_session_cleanup(self) -> None:
        """Simulate the elif _hb_session_id: guard.

        Empty string (falsy) must NOT trigger pop.
        Non-empty string MUST trigger pop.
        """
        _t0 = time.monotonic()

        tracking: dict[str, float] = {"real-session-123": 1234.5}

        def _cleanup(session_id: str) -> None:
            """Mirrors the production elif guard."""
            if session_id:  # elif _hb_session_id:
                tracking.pop(session_id, None)

        # Empty string — must NOT pop.
        _cleanup("")
        assert "real-session-123" in tracking, (
            "Pop was called with empty session_id — the elif guard is broken."
        )

        # Non-empty string — MUST pop.
        _cleanup("real-session-123")
        assert "real-session-123" not in tracking, (
            "Pop was NOT called with a valid session_id — the elif guard blocked it."
        )

        elapsed_ms = (time.monotonic() - _t0) * 1000
        print(f"[TIMING] test_elif_guard_prevents_empty_session_cleanup: {elapsed_ms:.1f}ms")

    # -----------------------------------------------------------------------
    # 9. max_continuations constant and is_max_continuations_reached()
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_max_continuations_respected(self, task_tracker_source: str) -> None:
        """max_continuations_per_objective default must be 5 and
        is_max_continuations_reached() must return True when count >= 5."""
        _t0 = time.monotonic()

        # --- source-level check ---
        anchor = "max_continuations_per_objective"
        found_default = False
        for line in task_tracker_source.splitlines():
            if "max_continuations_per_objective" in line and "=" in line:
                parts = line.split("=")
                try:
                    val = int(parts[-1].strip().rstrip("),"))
                    assert val == 5, (
                        f"max_continuations_per_objective default is {val}, expected 5."
                    )
                    found_default = True
                    break
                except ValueError:
                    pass
        assert found_default, (
            "Could not find a numeric default for max_continuations_per_objective "
            f"in {_TASK_TRACKER_PATH}."
        )

        # --- runtime check (import TaskTracker) ---
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "task_tracker", _TASK_TRACKER_PATH
        )
        assert spec is not None and spec.loader is not None, (
            f"Could not load module spec from {_TASK_TRACKER_PATH}"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        TaskTracker = module.TaskTracker  # type: ignore[attr-defined]

        tracker = TaskTracker()

        # Simulate an active objective with 5 continuations exhausted.
        tracker.record_user_message("send an email to the team")
        # Manually drive the continuation count to max.
        for _ in range(5):
            tracker._continuation_count += 1  # bypass cooldown for test

        assert tracker.is_max_continuations_reached(), (
            "is_max_continuations_reached() returned False when continuation "
            "count == max_continuations (5).  Fix the guard."
        )

        elapsed_ms = (time.monotonic() - _t0) * 1000
        print(f"[TIMING] test_max_continuations_respected: {elapsed_ms:.1f}ms")


# ===========================================================================
# Class: TestHeartbeatInteractionLogging
# Diagnostic assertions with printed timing tables.
# ===========================================================================

class TestHeartbeatInteractionLogging:
    """Logging/diagnostic tests for heartbeat timing constants."""

    @pytest.mark.asyncio
    async def test_heartbeat_timing_constants_logged(
        self, agent_source: str, task_tracker_source: str
    ) -> None:
        """Import TaskTracker (or fall back to source parsing) and emit a
        diagnostic table of all heartbeat timing constants, then assert each
        is within the expected range."""
        _t0 = time.monotonic()

        # --- Parse HEARTBEAT_INTERVAL from agent.py ---
        heartbeat_interval: float | None = None
        for line in agent_source.splitlines():
            if "HEARTBEAT_INTERVAL" in line and "=" in line and "#" not in line.split("=")[0]:
                rhs = line.split("=", 1)[1].strip()
                try:
                    heartbeat_interval = float(rhs.split()[0].rstrip("#"))
                    break
                except ValueError:
                    pass

        # --- Parse TaskTracker constants from task_tracker.py source ---
        stall_threshold: float | None = None
        max_continuations: int | None = None
        min_gap: float | None = None

        for line in task_tracker_source.splitlines():
            stripped = line.strip()
            if "stall_threshold_seconds" in stripped and "=" in stripped and "float" not in stripped:
                try:
                    stall_threshold = float(stripped.split("=")[-1].strip().rstrip("),"))
                except ValueError:
                    pass
            if "max_continuations_per_objective" in stripped and "=" in stripped and "int" not in stripped:
                try:
                    max_continuations = int(stripped.split("=")[-1].strip().rstrip("),"))
                except ValueError:
                    pass
            if "min_continuation_gap_seconds" in stripped and "=" in stripped and "float" not in stripped:
                try:
                    min_gap = float(stripped.split("=")[-1].strip().rstrip("),"))
                except ValueError:
                    pass

        # --- Try live import for authoritative values ---
        try:
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location("task_tracker_live", _TASK_TRACKER_PATH)
            if _spec and _spec.loader:
                _mod = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
                _tt = _mod.TaskTracker()
                stall_threshold = _tt._stall_threshold
                max_continuations = _tt._max_continuations
                min_gap = _tt._min_continuation_gap
        except Exception:
            pass  # Fall back to source-parsed values

        # --- Emit diagnostic table ---
        print(
            f"\n[HEARTBEAT] interval={heartbeat_interval}s, "
            f"stall_threshold={stall_threshold}s, "
            f"max_continuations={max_continuations}, "
            f"min_gap={min_gap}s"
        )

        elapsed_ms = (time.monotonic() - _t0) * 1000
        print(f"[TIMING] test_heartbeat_timing_constants_logged: {elapsed_ms:.1f}ms")

        # --- Assertions ---
        assert heartbeat_interval is not None, (
            "Could not parse HEARTBEAT_INTERVAL from agent.py"
        )
        assert heartbeat_interval <= 4.0, (
            f"HEARTBEAT_INTERVAL={heartbeat_interval}s exceeds 4.0s KPI limit."
        )

        assert stall_threshold is not None, (
            "Could not determine stall_threshold_seconds from task_tracker.py"
        )
        assert stall_threshold <= 8.0, (
            f"stall_threshold_seconds={stall_threshold}s exceeds 8.0s KPI green threshold."
        )

        assert max_continuations is not None, (
            "Could not determine max_continuations_per_objective from task_tracker.py"
        )
        assert max_continuations == 5, (
            f"max_continuations_per_objective={max_continuations}, expected 5."
        )

        assert min_gap is not None, (
            "Could not determine min_continuation_gap_seconds from task_tracker.py"
        )
        assert min_gap <= 10.0, (
            f"min_continuation_gap_seconds={min_gap}s exceeds 10.0s upper bound."
        )
