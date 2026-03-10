#!/usr/bin/env python3
"""
AIO Test Runner — validates AIO Voice Agent features during or after manual testing.

MODES:
  live    — tails Railway logs, classifies patterns in real-time, prints PASS/WARN/FAIL events
  post    — queries DB for a completed session, generates scored validation report

USAGE:
  python scripts/aio_test_runner.py --mode live [--focus FOCUS]
  python scripts/aio_test_runner.py --mode post --session-id SESSION_ID [--focus FOCUS] [--db-url URL]

FOCUS options: composio, auth, task, history, all (default: all)
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[91m"
ANSI_CYAN = "\033[36m"
ANSI_BLUE = "\033[34m"

SEVERITY_COLOR = {
    "CRITICAL": "\033[91m",
    "HIGH": "\033[31m",
    "MEDIUM": "\033[33m",
    "LOW": "\033[36m",
}

SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

VERDICT_COLOR = {
    "PASS": ANSI_GREEN,
    "WARN": ANSI_YELLOW,
    "FAIL": ANSI_RED,
}

OVERALL_COLOR = {
    "HEALTHY": ANSI_GREEN,
    "DEGRADED": ANSI_YELLOW,
    "CRITICAL": ANSI_RED,
}


def bold(text: str) -> str:
    return f"{ANSI_BOLD}{text}{ANSI_RESET}"


def dim(text: str) -> str:
    return f"{ANSI_DIM}{text}{ANSI_RESET}"


def colorize(color: str, text: str) -> str:
    return f"{color}{text}{ANSI_RESET}"


def verdict_str(verdict: str) -> str:
    color = VERDICT_COLOR.get(verdict, "")
    symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(verdict, "?")
    return f"{color}{symbol} {verdict}{ANSI_RESET}"


# ---------------------------------------------------------------------------
# Pattern registry (inline — not imported from live_trace.py)
# ---------------------------------------------------------------------------

PATTERNS: dict[str, dict] = {
    "META_TOOL_VIA_SDK": {
        "regex": r"Blocked meta-tool call to (\w+)",
        "severity": "HIGH",
        "component": "composio_router",
        "focus": "composio",
    },
    "PERMISSION_ERROR": {
        "regex": r"(?i)(permission denied|\b403\b|forbidden|not authorized|access denied|is_permission_error)",
        "severity": "HIGH",
        "component": "composio_router",
        "focus": "auth",
    },
    "EXPIRED_ACCOUNT": {
        "regex": r"(?i)(1820|ConnectedAccountExpired|EXPIRED state|Error code: 410|actionexecute_connectedaccountexpired)",
        "severity": "CRITICAL",
        "component": "composio_router",
        "focus": "auth",
    },
    "CIRCUIT_BREAKER": {
        "regex": r"(?i)(circuit.*open|auth_failed.*True|service.*marked.*fail|_service_auth_failed)",
        "severity": "CRITICAL",
        "component": "composio_router",
        "focus": "auth",
    },
    "SLUG_NOT_FOUND": {
        "regex": r"(?i)(Tool .{3,40} not found|Unknown slug|slug not found|unresolved.*slug|no slug.*found)",
        "severity": "MEDIUM",
        "component": "composio_router",
        "focus": "composio",
    },
    "N8N_WEBHOOK_FAIL": {
        "regex": r"(?i)(n8n.*error|webhook.*fail|HTTP [45]\d\d.*webhook|timeout.*webhook|ConnectionRefused.*webhook|n8n_post.*fail)",
        "severity": "HIGH",
        "component": "n8n_webhook",
        "focus": "task",
    },
    "WAKE_GATE_SUPPRESS": {
        "regex": r"(?i)(wake.*gate.*suppress|_wake_gate_suppress|no wake word|suppressing.*input|wake word not detected)",
        "severity": "LOW",
        "component": "agent_guards",
        "focus": "task",
    },
    "HEARTBEAT_STALL": {
        "regex": r"(?i)(stall detected|max.*continuation|heartbeat.*trigger|generate_reply.*instructions.*stall|continuation.*\d+/\d+)",
        "severity": "MEDIUM",
        "component": "task_tracker",
        "focus": "task",
    },
}

# Sessions detected in live mode — populated as new rooms connect
_seen_session_ids: set[str] = set()

# Tool call sequence tracking patterns for live mode
_TOOL_CALL_RE = re.compile(r"(?i)(tool[._\s]call|execute.*tool|calling.*tool|tool.*invok)", )
_TOOL_EXEC_RE = re.compile(r"(?i)(executing.*tool|tool.*execut|running.*slug|composio.*execute)", )
_TOOL_DONE_RE = re.compile(r"(?i)(tool.*complet|tool.*result|tool.*success|tool.*finish|execute.*result)", )
_TOOL_ERR_RE = re.compile(r"(?i)(tool.*error|tool.*fail|execute.*fail|slug.*fail|composio.*error)", )

# Pre-compile all pattern regexes
_COMPILED: dict[str, re.Pattern] = {
    name: re.compile(p["regex"]) for name, p in PATTERNS.items()
}

_PATTERNS_BY_SEVERITY = sorted(
    PATTERNS.items(),
    key=lambda kv: SEVERITY_RANK.get(kv[1]["severity"], 0),
    reverse=True,
)

# Focus → pattern names mapping
FOCUS_PATTERNS: dict[str, set[str]] = {
    "composio": {"META_TOOL_VIA_SDK", "SLUG_NOT_FOUND"},
    "auth": {"PERMISSION_ERROR", "EXPIRED_ACCOUNT", "CIRCUIT_BREAKER"},
    "task": {"N8N_WEBHOOK_FAIL", "WAKE_GATE_SUPPRESS", "HEARTBEAT_STALL"},
    "history": set(),  # history focus has no direct log patterns; show all
    "all": set(PATTERNS.keys()),
}


# ---------------------------------------------------------------------------
# Live mode: tool call sequence tracker
# ---------------------------------------------------------------------------

class ToolCallTracker:
    """
    Tracks tool.call → tool.executing → tool.completed sequences in log lines.
    Flags stalls when a call has no completion within STALL_SECS.
    """

    STALL_SECS: float = 30.0

    def __init__(self) -> None:
        # {seq_key: timestamp of first call seen}
        self._pending: dict[str, float] = {}
        self._stall_reported: set[str] = set()

    def ingest(self, line: str) -> Optional[str]:
        """
        Returns a stall warning string if a pending call just timed out,
        or None. Also clears completed entries.
        """
        now = time.monotonic()

        if _TOOL_CALL_RE.search(line):
            # Use a short key derived from the line to track this pending call
            key = line[:80]
            self._pending[key] = now

        if _TOOL_DONE_RE.search(line) or _TOOL_ERR_RE.search(line):
            # Try to clear any pending call (imprecise match — clear oldest)
            if self._pending:
                oldest_key = min(self._pending, key=lambda k: self._pending[k])
                self._pending.pop(oldest_key, None)

        # Check for stalled pending calls
        stalled = [
            k for k, ts in self._pending.items()
            if (now - ts) >= self.STALL_SECS and k not in self._stall_reported
        ]
        if stalled:
            self._stall_reported.update(stalled)
            count = len(stalled)
            return (
                f"STALL WARNING: {count} tool call(s) pending for >{self.STALL_SECS:.0f}s "
                f"with no completion signal"
            )
        return None


# ---------------------------------------------------------------------------
# Live mode: event counter / summary
# ---------------------------------------------------------------------------

class LiveSummary:
    def __init__(self) -> None:
        self.start_time = time.monotonic()
        self.lines_scanned: int = 0
        self.pattern_counts: dict[str, int] = collections.defaultdict(int)
        self.stall_count: int = 0
        self.critical_count: int = 0

    def record_pattern(self, pattern_name: str, severity: str) -> None:
        self.pattern_counts[pattern_name] += 1
        if severity == "CRITICAL":
            self.critical_count += 1

    def overall_verdict(self) -> str:
        if self.critical_count > 0:
            return "CRITICAL"
        warn_patterns = {"SLUG_NOT_FOUND", "HEARTBEAT_STALL", "N8N_WEBHOOK_FAIL",
                         "META_TOOL_VIA_SDK", "PERMISSION_ERROR"}
        if any(self.pattern_counts.get(p, 0) > 0 for p in warn_patterns):
            return "DEGRADED"
        if self.stall_count > 0:
            return "DEGRADED"
        return "HEALTHY"

    def print_final(self) -> None:
        elapsed = time.monotonic() - self.start_time
        h, rem = divmod(int(elapsed), 3600)
        m, s = divmod(rem, 60)
        elapsed_str = f"{h}h {m}m {s}s" if h else (f"{m}m {s}s" if m else f"{s}s")

        print()
        print(bold("=" * 60))
        print(bold("  AIO LIVE MODE — SESSION SUMMARY"))
        print(bold("=" * 60))
        print(f"  Duration        : {elapsed_str}")
        print(f"  Lines scanned   : {self.lines_scanned}")
        print(f"  Stall warnings  : {self.stall_count}")
        print()
        print(bold("  PATTERN COUNTS:"))

        if not self.pattern_counts:
            print(f"  {colorize(ANSI_GREEN, 'No patterns matched')} — clean session")
        else:
            for name in sorted(self.pattern_counts, key=lambda k: -self.pattern_counts[k]):
                severity = PATTERNS[name]["severity"]
                color = SEVERITY_COLOR.get(severity, "")
                count = self.pattern_counts[name]
                verdict = "FAIL" if severity in ("CRITICAL", "HIGH") else "WARN"
                print(
                    f"  {colorize(color, f'{name:<24}')} "
                    f"count={count:<4} "
                    f"{verdict_str(verdict)}"
                )

        overall = self.overall_verdict()
        overall_color = OVERALL_COLOR.get(overall, "")
        print()
        print(bold(f"  Overall: {colorize(overall_color, overall)}"))
        print(bold("=" * 60))


# ---------------------------------------------------------------------------
# Live mode: classify a log line
# ---------------------------------------------------------------------------

def classify_line(line: str) -> Optional[tuple[str, dict]]:
    for name, pattern in _PATTERNS_BY_SEVERITY:
        if _COMPILED[name].search(line):
            return name, pattern
    return None


# ---------------------------------------------------------------------------
# Live mode: format a match event
# ---------------------------------------------------------------------------

def _focus_matches(pattern_name: str, focus: str) -> bool:
    if focus == "all":
        return True
    return pattern_name in FOCUS_PATTERNS.get(focus, set())


def format_live_event(
    pattern_name: str,
    pattern: dict,
    line: str,
    ts: str,
) -> str:
    severity = pattern["severity"]
    color = SEVERITY_COLOR.get(severity, "")
    comp = pattern["component"]
    return (
        f"{color}[{ts}] [{severity}] {bold(pattern_name)}{ANSI_RESET} "
        f"{dim(f'({comp})')}  {dim(line[:120])}"
    )


# ---------------------------------------------------------------------------
# Live mode: main runner
# ---------------------------------------------------------------------------

_shutdown_requested: bool = False


def _handle_sigterm(signum: int, frame: Any) -> None:
    global _shutdown_requested
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _handle_sigterm)


def run_live(focus: str) -> None:
    global _shutdown_requested

    # Verify railway CLI is available before starting
    try:
        result = subprocess.run(
            ["railway", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError("non-zero exit")
    except (FileNotFoundError, RuntimeError, subprocess.TimeoutExpired):
        print(
            f"{ANSI_RED}WARNING: 'railway' CLI not found or not responding.{ANSI_RESET}\n"
            f"  Install: npm install -g @railway/cli\n"
            f"  Login:   railway login",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = ["railway", "logs", "--service", "livekit-voice-agent"]

    print(bold("[aio_test_runner] LIVE MODE"))
    print(f"  Focus   : {focus}")
    print(f"  Command : {' '.join(cmd)}")
    print(f"  Patterns: {', '.join(sorted(FOCUS_PATTERNS.get(focus, set()) or set(PATTERNS.keys())))}")
    print(dim("Press Ctrl-C to stop and print session summary."))
    print()
    sys.stdout.flush()

    summary = LiveSummary()
    tracker = ToolCallTracker()
    dedupe_window: dict[str, float] = {}
    DEDUPE_SECS = 5.0

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        print(
            f"{ANSI_RED}ERROR: 'railway' CLI not found.{ANSI_RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        for raw_line in proc.stdout:  # type: ignore[union-attr]
            if _shutdown_requested:
                break

            line = raw_line.rstrip()
            if not line:
                continue

            summary.lines_scanned += 1
            ts = datetime.now().strftime("%H:%M:%S")

            # Print the raw line dimmed so the user sees the full stream
            print(dim(line))
            sys.stdout.flush()

            # ── Session detection ────────────────────────────────────────────
            # LiveKit Agents framework logs the room name when the entrypoint
            # is called. Patterns observed in Railway logs:
            #   "Starting job in room <room_name>"
            #   "Participant <identity> joined room <room_name>"
            #   "entrypoint called" with room context
            #   "worker registered" with job/room info
            # We extract the room name and surface it as the session_id.
            _session_match = re.search(
                r"(?i)(?:"
                r"Starting job in room\s+([A-Za-z0-9_\-]+)"
                r"|Participant .+? joined room\s+([A-Za-z0-9_\-]+)"
                r"|room[_\s=:]+([A-Za-z0-9_\-]{6,})"
                r"|session[_\s=:]+([A-Za-z0-9_\-]{6,})"
                r")",
                line,
            )
            if _session_match:
                _sid = next((g for g in _session_match.groups() if g), None)
                if _sid and _sid not in _seen_session_ids:
                    _seen_session_ids.add(_sid)
                    print(
                        f"\n{ANSI_CYAN}{'═' * 60}{ANSI_RESET}\n"
                        f"{ANSI_CYAN}  NEW SESSION DETECTED{ANSI_RESET}\n"
                        f"{ANSI_CYAN}  session_id = {bold(_sid)}{ANSI_RESET}\n"
                        f"{ANSI_CYAN}  timestamp  = {ts}{ANSI_RESET}\n"
                        f"{ANSI_CYAN}{'─' * 60}{ANSI_RESET}\n"
                        f"{ANSI_CYAN}  Post-session analysis:{ANSI_RESET}\n"
                        f"{ANSI_CYAN}  python scripts/aio_test_runner.py --mode post --session-id {_sid}{ANSI_RESET}\n"
                        f"{ANSI_CYAN}{'═' * 60}{ANSI_RESET}\n"
                    )
                    sys.stdout.flush()
            # ── End session detection ─────────────────────────────────────────

            # Tool call sequence tracking
            stall_warn = tracker.ingest(line)
            if stall_warn:
                summary.stall_count += 1
                print(f"{ANSI_YELLOW}[{ts}] {bold('STALL')} {stall_warn}{ANSI_RESET}")
                sys.stdout.flush()

            # Pattern classification
            result = classify_line(line)
            if result is None:
                continue

            pattern_name, pattern = result
            severity = pattern["severity"]

            # Focus filter
            if not _focus_matches(pattern_name, focus):
                continue

            # Deduplication within DEDUPE_SECS
            now = time.monotonic()
            last = dedupe_window.get(pattern_name, 0.0)
            if (now - last) < DEDUPE_SECS:
                continue
            dedupe_window[pattern_name] = now

            summary.record_pattern(pattern_name, severity)

            # Emit event line
            event = format_live_event(pattern_name, pattern, line, ts)
            print(event)

            # CRITICAL/EXPIRED_ACCOUNT → prominent alert
            if severity == "CRITICAL":
                print(
                    f"{ANSI_RED}{bold(f'  !! CRITICAL ALERT: {pattern_name} — immediate attention required')}{ANSI_RESET}"
                )

            # CIRCUIT_BREAKER specifically
            if pattern_name == "CIRCUIT_BREAKER":
                print(
                    f"{ANSI_RED}  !! CIRCUIT BREAKER OPEN — service auth failed. "
                    f"No further tool calls will succeed for that service this session.{ANSI_RESET}"
                )

            sys.stdout.flush()

    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    summary.print_final()


# ---------------------------------------------------------------------------
# Post mode: check result dataclass
# ---------------------------------------------------------------------------

class CheckResult:
    __slots__ = ("label", "verdict", "detail")

    def __init__(self, label: str, verdict: str, detail: str) -> None:
        self.label = label
        self.verdict = verdict  # PASS | WARN | FAIL
        self.detail = detail

    def __repr__(self) -> str:
        return f"CheckResult({self.label!r}, {self.verdict!r})"


# ---------------------------------------------------------------------------
# Post mode: DB query helpers
# ---------------------------------------------------------------------------

async def _connect(db_url: str):
    try:
        import asyncpg  # type: ignore
    except ImportError:
        print(
            f"{ANSI_RED}ERROR: asyncpg not installed. Run: pip install asyncpg{ANSI_RESET}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        conn = await asyncpg.connect(db_url, timeout=15)
        return conn
    except Exception as exc:
        print(
            f"{ANSI_RED}ERROR: Could not connect to PostgreSQL: {exc}{ANSI_RESET}",
            file=sys.stderr,
        )
        sys.exit(1)


async def _table_exists(conn, table: str) -> bool:
    row = await conn.fetchrow(
        "SELECT 1 FROM information_schema.tables WHERE table_name = $1",
        table,
    )
    return row is not None


# ---------------------------------------------------------------------------
# Post mode: composio checks
# ---------------------------------------------------------------------------

async def check_composio(conn, session_id: str) -> list[CheckResult]:
    results: list[CheckResult] = []

    # 1. Total tool calls for session
    if await _table_exists(conn, "tool_calls"):
        row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS total
            FROM tool_calls
            WHERE session_id = $1
            """,
            session_id,
        )
        total = row["total"] if row else 0
        verdict = "PASS" if total > 0 else "WARN"
        results.append(CheckResult(
            "Tool calls executed",
            verdict,
            str(total),
        ))

        # 4. Idempotency: duplicate calls within 5 minutes (same function_name + parameters)
        dup_rows = await conn.fetch(
            """
            SELECT function_name, parameters, COUNT(*) AS cnt
            FROM tool_calls
            WHERE session_id = $1
              AND created_at IS NOT NULL
            GROUP BY function_name, parameters
            HAVING COUNT(*) > 1
              AND (MAX(created_at) - MIN(created_at)) < INTERVAL '5 minutes'
            """,
            session_id,
        )
        if dup_rows:
            detail_parts = [
                f"{r['function_name']} x{r['cnt']}" for r in dup_rows
            ]
            results.append(CheckResult(
                "Duplicate calls detected",
                "WARN",
                "; ".join(detail_parts),
            ))
        else:
            results.append(CheckResult(
                "Duplicate calls detected",
                "PASS",
                "none",
            ))
    else:
        results.append(CheckResult("Tool calls executed", "WARN", "tool_calls table missing"))
        results.append(CheckResult("Duplicate calls detected", "WARN", "tool_calls table missing"))

    # 2. Tool errors for session
    if await _table_exists(conn, "tool_error_log"):
        error_rows = await conn.fetch(
            """
            SELECT error_type, COUNT(*) AS cnt
            FROM tool_error_log
            WHERE session_id = $1
            GROUP BY error_type
            ORDER BY cnt DESC
            """,
            session_id,
        )
        if error_rows:
            breakdown = ", ".join(f"{r['error_type']}={r['cnt']}" for r in error_rows)
            total_errors = sum(r["cnt"] for r in error_rows)
            verdict = "FAIL" if total_errors > 5 else "WARN"
            results.append(CheckResult(
                "Composio errors",
                verdict,
                f"{total_errors} ({breakdown})",
            ))
        else:
            results.append(CheckResult("Composio errors", "PASS", "0"))

        # 3. SLUG_NOT_FOUND occurrences
        snf_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM tool_error_log
            WHERE session_id = $1
              AND error_type = 'SLUG_NOT_FOUND'
            """,
            session_id,
        )
        snf_count = snf_row["cnt"] if snf_row else 0
        verdict = "FAIL" if snf_count > 2 else ("WARN" if snf_count > 0 else "PASS")
        results.append(CheckResult(
            "SLUG_NOT_FOUND occurrences",
            verdict,
            str(snf_count),
        ))
    else:
        results.append(CheckResult("Composio errors", "WARN", "tool_error_log table missing"))
        results.append(CheckResult("SLUG_NOT_FOUND occurrences", "WARN", "tool_error_log table missing"))

    return results


# ---------------------------------------------------------------------------
# Post mode: auth checks
# ---------------------------------------------------------------------------

async def check_auth(conn, session_id: str) -> list[CheckResult]:
    results: list[CheckResult] = []

    if not await _table_exists(conn, "conversation_log"):
        results.append(CheckResult("Auth flow", "WARN", "conversation_log table missing"))
        results.append(CheckResult("Post-auth tools", "WARN", "conversation_log table missing"))
        return results

    # 5. Did auth flow trigger? Look for "sent a connection link" or "already connected"
    auth_rows = await conn.fetch(
        """
        SELECT id, created_at, content
        FROM conversation_log
        WHERE session_id = $1
          AND role = 'assistant'
          AND (
            content ILIKE '%sent a connection link%'
            OR content ILIKE '%already connected%'
            OR content ILIKE '%connection link%'
            OR content ILIKE '%authenticate%'
            OR content ILIKE '%connect your%'
          )
        ORDER BY created_at ASC
        LIMIT 5
        """,
        session_id,
    )

    auth_triggered = len(auth_rows) > 0
    verdict = "PASS" if auth_triggered else "PASS"  # Not triggering is also fine
    detail = f"triggered ({len(auth_rows)} auth message(s))" if auth_triggered else "not triggered"
    results.append(CheckResult("Auth flow", verdict, detail))

    # 6. After auth message, did subsequent tool calls use composio slugs?
    if auth_triggered and await _table_exists(conn, "tool_calls"):
        first_auth_ts = auth_rows[0]["created_at"]
        post_auth_rows = await conn.fetch(
            """
            SELECT function_name, status, created_at
            FROM tool_calls
            WHERE session_id = $1
              AND created_at > $2
            ORDER BY created_at ASC
            LIMIT 10
            """,
            session_id,
            first_auth_ts,
        )
        if post_auth_rows:
            composio_calls = [
                r for r in post_auth_rows
                if r["function_name"] and (
                    "composio" in r["function_name"].lower()
                    or "execute" in r["function_name"].lower()
                    or "Drive" in (r["function_name"] or "")
                    or "Gmail" in (r["function_name"] or "")
                    or "Teams" in (r["function_name"] or "")
                    or "Sheets" in (r["function_name"] or "")
                )
            ]
            if composio_calls:
                detail = f"available ({len(composio_calls)} composio call(s) post-auth)"
                verdict = "PASS"
            else:
                detail = f"unknown ({len(post_auth_rows)} tool call(s) post-auth, none matched composio)"
                verdict = "WARN"
        else:
            detail = "unknown (no tool calls after auth message)"
            verdict = "WARN"
    elif not auth_triggered:
        detail = "N/A (no auth flow detected)"
        verdict = "PASS"
    else:
        detail = "unknown (tool_calls table missing)"
        verdict = "WARN"

    results.append(CheckResult("Post-auth tools", verdict, detail))
    return results


# ---------------------------------------------------------------------------
# Post mode: task checks
# ---------------------------------------------------------------------------

async def check_task(conn, session_id: str) -> list[CheckResult]:
    results: list[CheckResult] = []

    # 7. Stalled tools (status=EXECUTING, no completed_at)
    if await _table_exists(conn, "tool_calls"):
        stall_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM tool_calls
            WHERE session_id = $1
              AND status = 'EXECUTING'
              AND completed_at IS NULL
            """,
            session_id,
        )
        stall_count = stall_row["cnt"] if stall_row else 0
        verdict = "FAIL" if stall_count > 0 else "PASS"
        results.append(CheckResult("Stalled tools", verdict, str(stall_count)))

        # 10. Average execution time
        avg_row = await conn.fetchrow(
            """
            SELECT ROUND(AVG(execution_time_ms)) AS avg_ms
            FROM tool_calls
            WHERE session_id = $1
              AND execution_time_ms IS NOT NULL
            """,
            session_id,
        )
        avg_ms = int(avg_row["avg_ms"]) if avg_row and avg_row["avg_ms"] is not None else None
        if avg_ms is None:
            results.append(CheckResult("Avg execution time", "WARN", "no timing data"))
        else:
            verdict = "FAIL" if avg_ms > 10000 else ("WARN" if avg_ms > 5000 else "PASS")
            results.append(CheckResult("Avg execution time", verdict, f"{avg_ms}ms"))

        # 9. Agent responded (assistant turn count)
        agent_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM conversation_log
            WHERE session_id = $1
              AND role = 'assistant'
            """,
            session_id,
        ) if await _table_exists(conn, "conversation_log") else None

        if agent_row:
            resp_count = agent_row["cnt"]
            verdict = "FAIL" if resp_count == 0 else "PASS"
            results.append(CheckResult("Agent responses", verdict, str(resp_count)))
        else:
            results.append(CheckResult("Agent responses", "WARN", "conversation_log table missing"))
    else:
        results.append(CheckResult("Stalled tools", "WARN", "tool_calls table missing"))
        results.append(CheckResult("Avg execution time", "WARN", "tool_calls table missing"))
        results.append(CheckResult("Agent responses", "WARN", "tool_calls table missing"))

    # 8. DLQ entries for session
    if await _table_exists(conn, "tool_dlq"):
        dlq_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM tool_dlq
            WHERE session_id = $1
            """,
            session_id,
        )
        dlq_count = dlq_row["cnt"] if dlq_row else 0
        unresolved_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM tool_dlq
            WHERE session_id = $1
              AND resolved_at IS NULL
            """,
            session_id,
        )
        unresolved = unresolved_row["cnt"] if unresolved_row else 0
        if unresolved > 0:
            verdict = "WARN"
            detail = f"{dlq_count} total, {unresolved} unresolved"
        elif dlq_count > 0:
            verdict = "PASS"
            detail = f"{dlq_count} (all resolved)"
        else:
            verdict = "PASS"
            detail = "0"
        results.append(CheckResult("DLQ entries", verdict, detail))
    else:
        results.append(CheckResult("DLQ entries", "WARN", "tool_dlq table missing"))

    return results


# ---------------------------------------------------------------------------
# Post mode: history checks
# ---------------------------------------------------------------------------

async def check_history(conn, session_id: str) -> list[CheckResult]:
    results: list[CheckResult] = []

    # 11. Session facts stored
    if await _table_exists(conn, "session_facts_log"):
        facts_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM session_facts_log
            WHERE session_id = $1
            """,
            session_id,
        )
        facts_count = facts_row["cnt"] if facts_row else 0
        verdict = "PASS" if facts_count > 0 else "WARN"
        results.append(CheckResult("Session facts stored", verdict, str(facts_count)))
    else:
        results.append(CheckResult("Session facts stored", "WARN", "session_facts_log table missing"))

    if await _table_exists(conn, "conversation_log"):
        # 12. Enough user turns for recall test
        user_turn_row = await conn.fetchrow(
            """
            SELECT COUNT(*) AS cnt
            FROM conversation_log
            WHERE session_id = $1
              AND role = 'user'
            """,
            session_id,
        )
        user_turns = user_turn_row["cnt"] if user_turn_row else 0
        verdict = "PASS" if user_turns > 3 else "WARN"
        detail = f"{user_turns} user turns"
        results.append(CheckResult("User turn depth (recall readiness)", verdict, detail))
    else:
        results.append(CheckResult("User turn depth (recall readiness)", "WARN", "conversation_log table missing"))

    # 13. Memory tools used
    if await _table_exists(conn, "tool_calls"):
        memory_rows = await conn.fetch(
            """
            SELECT DISTINCT function_name
            FROM tool_calls
            WHERE session_id = $1
              AND (
                function_name ILIKE '%recall%'
                OR function_name ILIKE '%checkContext%'
                OR function_name ILIKE '%deepStore%'
                OR function_name ILIKE '%searchMemory%'
                OR function_name ILIKE '%storeMemory%'
                OR function_name ILIKE '%checkContext%'
              )
            """,
            session_id,
        )
        memory_tools_used = [r["function_name"] for r in memory_rows]
        verdict = "PASS" if memory_tools_used else "WARN"
        detail = ", ".join(memory_tools_used) if memory_tools_used else "none"
        results.append(CheckResult("Memory tools used", verdict, detail))
    else:
        results.append(CheckResult("Memory tools used", "WARN", "tool_calls table missing"))

    return results


# ---------------------------------------------------------------------------
# Post mode: report printer
# ---------------------------------------------------------------------------

DIVIDER = "=" * 52


def _section_header(label: str) -> str:
    return f"\n{bold(f'[{label}]')}"


def _check_line(check: CheckResult) -> str:
    color = VERDICT_COLOR.get(check.verdict, "")
    symbol = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗"}.get(check.verdict, "?")
    return f"  {color}{symbol}{ANSI_RESET} {check.label}: {check.detail}"


def print_post_report(
    session_id: str,
    composio_results: list[CheckResult],
    auth_results: list[CheckResult],
    task_results: list[CheckResult],
    history_results: list[CheckResult],
    focus: str,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    all_results: list[CheckResult] = []

    passes = 0
    warns = 0
    fails = 0

    def tally(results: list[CheckResult]) -> None:
        nonlocal passes, warns, fails
        all_results.extend(results)
        for r in results:
            if r.verdict == "PASS":
                passes += 1
            elif r.verdict == "WARN":
                warns += 1
            elif r.verdict == "FAIL":
                fails += 1

    print()
    print(bold(DIVIDER))
    print(bold("AIO POST-SESSION VALIDATION REPORT"))
    print(f"Session   : {session_id}")
    print(f"Timestamp : {now}")
    print(f"Focus     : {focus}")
    print(bold(DIVIDER))

    sections: list[tuple[str, list[CheckResult]]] = []

    if focus in ("composio", "all"):
        sections.append(("COMPOSIO", composio_results))
    if focus in ("auth", "all"):
        sections.append(("AUTH", auth_results))
    if focus in ("task", "all"):
        sections.append(("TASK", task_results))
    if focus in ("history", "all"):
        sections.append(("HISTORY", history_results))

    for section_label, section_results in sections:
        print(_section_header(section_label))
        for check in section_results:
            print(_check_line(check))
        tally(section_results)

    # Verdict block
    if fails > 0:
        overall = "CRITICAL"
    elif warns > 0:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"

    overall_color = OVERALL_COLOR.get(overall, "")

    print()
    print(_section_header("VERDICT"))
    print(
        f"  {colorize(ANSI_GREEN, f'PASS: {passes}')} / "
        f"{colorize(ANSI_YELLOW, f'WARN: {warns}')} / "
        f"{colorize(ANSI_RED, f'FAIL: {fails}')}"
    )
    print(f"  Overall: {colorize(overall_color, bold(overall))}")
    print()
    print(bold(DIVIDER))
    print()


# ---------------------------------------------------------------------------
# Post mode: orchestrator
# ---------------------------------------------------------------------------

async def run_post(session_id: str, focus: str, db_url: Optional[str]) -> None:
    if not db_url:
        db_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_PUBLIC_URL")

    if not db_url:
        print(
            f"{ANSI_YELLOW}WARNING: No --db-url provided and POSTGRES_URL env var not set. "
            f"DB checks skipped.{ANSI_RESET}",
            file=sys.stderr,
        )
        # Print an empty report with all WARN checks
        empty: list[CheckResult] = [
            CheckResult("Database connection", "FAIL", "no DB URL configured")
        ]
        print_post_report(session_id, empty, empty, empty, empty, focus)
        return

    conn = await _connect(db_url)
    try:
        composio_results = await check_composio(conn, session_id) if focus in ("composio", "all") else []
        auth_results = await check_auth(conn, session_id) if focus in ("auth", "all") else []
        task_results = await check_task(conn, session_id) if focus in ("task", "all") else []
        history_results = await check_history(conn, session_id) if focus in ("history", "all") else []
    finally:
        await conn.close()

    print_post_report(
        session_id=session_id,
        composio_results=composio_results,
        auth_results=auth_results,
        task_results=task_results,
        history_results=history_results,
        focus=focus,
    )


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aio_test_runner.py",
        description=(
            "AIO Test Runner — validates AIO Voice Agent features during or after manual testing.\n\n"
            "MODES:\n"
            "  live  — tails Railway logs, classifies patterns in real-time\n"
            "  post  — queries DB for a completed session, generates scored validation report"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--mode",
        choices=["live", "post"],
        required=True,
        help="Operating mode: 'live' for real-time log monitoring, 'post' for session analysis",
    )

    parser.add_argument(
        "--session-id",
        metavar="SESSION_ID",
        default=None,
        help="[post mode] Session ID to analyze (required for --mode post)",
    )

    parser.add_argument(
        "--focus",
        choices=["composio", "auth", "task", "history", "all"],
        default="all",
        help="Limit checks to a specific domain (default: all)",
    )

    parser.add_argument(
        "--db-url",
        metavar="URL",
        default=None,
        help=(
            "[post mode] PostgreSQL connection URL. "
            "Defaults to POSTGRES_URL or DATABASE_PUBLIC_URL env var."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "live":
        run_live(focus=args.focus)

    elif args.mode == "post":
        if not args.session_id:
            parser.error("--mode post requires --session-id SESSION_ID")
        asyncio.run(run_post(
            session_id=args.session_id,
            focus=args.focus,
            db_url=args.db_url,
        ))


if __name__ == "__main__":
    main()
