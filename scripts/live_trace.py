#!/usr/bin/env python3
"""
live_trace.py — Railway livekit-voice-agent log tracer and incident classifier.

Streams Railway logs continuously, classifies errors against 8 known AIO patterns,
prints structured INCIDENT reports with ANSI color coding, and emits ready-to-paste
/aiodebug prompts for each detected incident.

Usage examples:
    # Continuous monitoring (default)
    python scripts/live_trace.py

    # Snapshot of last 100 lines then exit
    python scripts/live_trace.py --snapshot

    # Only show HIGH and CRITICAL incidents
    python scripts/live_trace.py --min-severity HIGH

    # Print all patterns and exit
    python scripts/live_trace.py --dump-patterns

    # Include 10 context lines per incident
    python scripts/live_trace.py --context-lines 10

    # Monitor a different Railway service
    python scripts/live_trace.py --service some-other-service
"""

from __future__ import annotations

import argparse
import collections
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------

ANSI_RESET = "\033[0m"
ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"

SEVERITY_COLOR = {
    "CRITICAL": "\033[91m",   # bright red
    "HIGH":     "\033[31m",   # red
    "MEDIUM":   "\033[33m",   # yellow
    "LOW":      "\033[36m",   # cyan
}

SEVERITY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

BOX_TOP     = "╔══════════════════════════════════════════════════════════════"
BOX_DIV     = "╠══════════════════════════════════════════════════════════════"
BOX_BOTTOM  = "╚══════════════════════════════════════════════════════════════"
BOX_ROW     = "║"


def colorize(severity: str, text: str) -> str:
    color = SEVERITY_COLOR.get(severity, "")
    return f"{color}{text}{ANSI_RESET}"


def dim(text: str) -> str:
    return f"{ANSI_DIM}{text}{ANSI_RESET}"


def bold(text: str) -> str:
    return f"{ANSI_BOLD}{text}{ANSI_RESET}"


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

PATTERNS: dict[str, dict] = {
    "META_TOOL_VIA_SDK": {
        "regex": r"Blocked meta-tool call to (\w+)",
        "severity": "HIGH",
        "component": "composio_router",
        "description": "Agent called Composio MCP meta-tool via SDK (e.g. COMPOSIO_MULTI_EXECUTE_TOOL)",
        "fix_hint": "System prompt or LLM is routing meta-tool calls through execute_composio_tool(). Check _COMPOSIO_META_SLUGS guard.",
        "rca_file": "src/tools/composio_router.py",
        "rca_prompt_template": (
            "Focus: _COMPOSIO_META_SLUGS guard in composio_router.py. "
            "Why did execute_composio_tool() receive a meta-tool slug? "
            "Trace from system prompt → LLM tool call → execute_composio_tool()."
        ),
    },
    "PERMISSION_ERROR": {
        "regex": r"(?i)(permission denied|\b403\b|forbidden|not authorized|access denied|is_permission_error)",
        "severity": "HIGH",
        "component": "composio_router",
        "description": "Composio tool returned 403/forbidden — wrong account or OAuth scope",
        "fix_hint": "Check _preferred_account_by_toolkit — may point to wrong/expired account. Run action=status.",
        "rca_file": "src/tools/composio_router.py",
        "rca_prompt_template": (
            "Focus: _preferred_account_by_toolkit dict in composio_router.py. "
            "Why did tools.execute() return 403? Which connected_account_id was selected? "
            "Is it the wrong account?"
        ),
    },
    "EXPIRED_ACCOUNT": {
        "regex": r"(?i)(1820|ConnectedAccountExpired|EXPIRED state|Error code: 410|actionexecute_connectedaccountexpired)",
        "severity": "CRITICAL",
        "component": "composio_router",
        "description": "Connected account expired (HTTP 410, error 1820) — needs re-auth",
        "fix_hint": "Run manageConnections(action=initiate, service=X) to get new OAuth link. Old account is 410 dead.",
        "rca_file": "src/tools/composio_router.py",
        "rca_prompt_template": (
            "Focus: _preferred_account_by_toolkit in composio_router.py. "
            "Why did execute_composio_tool() select an expired account (410/1820)? "
            "What does _discover_connected_toolkits() return?"
        ),
    },
    "CIRCUIT_BREAKER": {
        "regex": r"(?i)(circuit.*open|auth_failed.*True|service.*marked.*fail|_service_auth_failed)",
        "severity": "CRITICAL",
        "component": "composio_router",
        "description": "Circuit breaker tripped — service permanently marked as auth_failed for this session",
        "fix_hint": "Auth failure triggered circuit break. Service blocked until re-auth. Check _service_auth_failed dict.",
        "rca_file": "src/tools/composio_router.py",
        "rca_prompt_template": (
            "Focus: _service_auth_failed dict in composio_router.py. "
            "What triggered the circuit break? Which auth error cascaded into it? "
            "How to clear it without restart?"
        ),
    },
    "SLUG_NOT_FOUND": {
        "regex": r"(?i)(Tool .{3,40} not found|Unknown slug|slug not found|unresolved.*slug|no slug.*found)",
        "severity": "MEDIUM",
        "component": "composio_router",
        "description": "Tool slug not found in slug index — LLM hallucinated slug or index not built",
        "fix_hint": "Check ensure_slug_index() completed. Verify tool is in _slugs_by_service. LLM may be fabricating slug names.",
        "rca_file": "src/tools/composio_router.py",
        "rca_prompt_template": (
            "Focus: 6-tier slug resolution in composio_router.py. "
            "Why did the slug fail all 6 resolution tiers? "
            "Is the slug index populated? Did the LLM hallucinate the slug?"
        ),
    },
    "N8N_WEBHOOK_FAIL": {
        "regex": r"(?i)(n8n.*error|webhook.*fail|HTTP [45]\d\d.*webhook|timeout.*webhook|ConnectionRefused.*webhook|n8n_post.*fail)",
        "severity": "HIGH",
        "component": "n8n_webhook",
        "description": "n8n webhook call failed — non-200 response or timeout",
        "fix_hint": "Check n8n workflow is active. Verify X-AIO-Webhook-Secret matches. Check n8n cloud status.",
        "rca_file": "src/utils/n8n_client.py",
        "rca_prompt_template": (
            "Focus: src/utils/n8n_client.py n8n_post() function. "
            "What HTTP status was returned? Is the workflow active in n8n cloud? "
            "Is X-AIO-Webhook-Secret set correctly?"
        ),
    },
    "WAKE_GATE_SUPPRESS": {
        "regex": r"(?i)(wake.*gate.*suppress|_wake_gate_suppress|no wake word|suppressing.*input|wake word not detected)",
        "severity": "LOW",
        "component": "agent_guards",
        "description": "Wake word gate suppressed user input — user spoke without 'AIO' trigger",
        "fix_hint": "Expected behavior. If false positive: check _WAKE_GATE_GRACE_PERIOD_SECS (30s) and _CONVERSATIONAL_BYPASS_PHRASES.",
        "rca_file": "src/agent.py",
        "rca_prompt_template": (
            "Focus: _wake_gate_suppress and _WAKE_GATE_GRACE_PERIOD_SECS in agent.py. "
            "Was this suppression correct or a false positive? "
            "Check if _last_agent_listening_time is recent."
        ),
    },
    "HEARTBEAT_STALL": {
        "regex": r"(?i)(stall detected|max.*continuation|heartbeat.*trigger|generate_reply.*instructions.*stall|continuation.*\d+/\d+)",
        "severity": "MEDIUM",
        "component": "task_tracker",
        "description": "Heartbeat detected task stall and triggered forced continuation",
        "fix_hint": "Check if task completed. If looping: verify tool returns proper result. Max 5 continuations before stop.",
        "rca_file": "src/utils/task_tracker.py",
        "rca_prompt_template": (
            "Focus: task_tracker.py stall detection. "
            "Which tool caused the stall? Did it return a result? "
            "Is max_continuations (5) being hit?"
        ),
    },
}

# Pre-compile all regexes once at import time
_COMPILED: dict[str, re.Pattern] = {
    name: re.compile(p["regex"]) for name, p in PATTERNS.items()
}

# Patterns sorted by severity descending (CRITICAL first) for priority matching
_PATTERNS_BY_SEVERITY = sorted(
    PATTERNS.items(),
    key=lambda kv: SEVERITY_RANK.get(kv[1]["severity"], 0),
    reverse=True,
)


# ---------------------------------------------------------------------------
# Stats tracker
# ---------------------------------------------------------------------------

class Stats:
    def __init__(self) -> None:
        self.start_time = time.monotonic()
        self.lines_scanned: int = 0
        self.incidents_total: int = 0
        self.incidents_by_severity: dict[str, int] = collections.defaultdict(int)
        self.incidents_by_pattern: dict[str, int] = collections.defaultdict(int)
        self.last_print: float = time.monotonic()

    def record_incident(self, pattern_name: str, severity: str) -> None:
        self.incidents_total += 1
        self.incidents_by_severity[severity] += 1
        self.incidents_by_pattern[pattern_name] += 1

    def should_print(self, interval: float = 60.0) -> bool:
        return (time.monotonic() - self.last_print) >= interval

    def print_summary(self, header: str = "STATS (60s)") -> None:
        self.last_print = time.monotonic()
        elapsed = time.monotonic() - self.start_time
        elapsed_str = _fmt_elapsed(elapsed)

        top_pattern = ""
        if self.incidents_by_pattern:
            top_pattern = max(self.incidents_by_pattern, key=lambda k: self.incidents_by_pattern[k])

        print()
        print(dim("─" * 64))
        print(bold(f"  {header}  |  elapsed: {elapsed_str}"))
        print(dim("─" * 64))
        print(f"  Lines scanned  : {self.lines_scanned}")
        print(f"  Total incidents: {self.incidents_total}")
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            count = self.incidents_by_severity.get(sev, 0)
            color = SEVERITY_COLOR.get(sev, "")
            print(f"  {color}{sev:<8}{ANSI_RESET}      : {count}")
        if top_pattern:
            print(f"  Top pattern    : {top_pattern} ({self.incidents_by_pattern[top_pattern]}x)")
        print(dim("─" * 64))
        print()


def _fmt_elapsed(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {sec}s"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"


# ---------------------------------------------------------------------------
# Incident deduplication window
# ---------------------------------------------------------------------------

class DedupeWindow:
    """
    Within a 5-second window, collapse repeated matches of the same pattern
    into a single incident so noisy log bursts don't flood output.
    """

    WINDOW_SECS = 5.0

    def __init__(self) -> None:
        self._last_seen: dict[str, float] = {}

    def should_emit(self, pattern_name: str) -> bool:
        now = time.monotonic()
        last = self._last_seen.get(pattern_name, 0.0)
        if (now - last) >= self.WINDOW_SECS:
            self._last_seen[pattern_name] = now
            return True
        return False


# ---------------------------------------------------------------------------
# Incident reporter
# ---------------------------------------------------------------------------

class IncidentReporter:
    def __init__(self, context_lines: int = 3) -> None:
        self.context_lines = context_lines
        self._incident_counter = 0
        self._line_buffer: collections.deque[str] = collections.deque(maxlen=50)

    def push_line(self, line: str) -> None:
        self._line_buffer.append(line)

    def _recent_context(self, n: int) -> list[str]:
        buf = list(self._line_buffer)
        return buf[-n:] if len(buf) >= n else buf

    def emit(self, pattern_name: str, pattern: dict, matched_line: str, ts: str) -> None:
        self._incident_counter += 1
        severity = pattern["severity"]
        color = SEVERITY_COLOR.get(severity, "")

        context = self._recent_context(self.context_lines)

        # Build the aio-debugger prompt body
        ctx_text = "\n".join(context[-self.context_lines:]) if context else matched_line
        aio_prompt = (
            f"/aiodebug {pattern_name} detected in livekit-voice-agent.\n"
            f"\n"
            f"Log context:\n"
            f"{ctx_text}\n"
            f"\n"
            f"{pattern['rca_prompt_template']}\n"
            f"Perform 5-why RCA. Why did this error occur and what is the root fix?"
        )

        lines_out: list[str] = []
        lines_out.append(f"{color}{BOX_TOP}{ANSI_RESET}")
        lines_out.append(
            f"{color}{BOX_ROW}{ANSI_RESET} "
            f"{bold(f'INCIDENT #{self._incident_counter}')}  "
            f"{color}[{severity}]{ANSI_RESET}  "
            f"{bold(pattern_name)}  @ {ts}"
        )
        lines_out.append(
            f"{color}{BOX_ROW}{ANSI_RESET} Component: {pattern['component']}"
        )
        lines_out.append(
            f"{color}{BOX_ROW}{ANSI_RESET} Description: {pattern['description']}"
        )

        lines_out.append(f"{color}{BOX_DIV}{ANSI_RESET}")
        lines_out.append(f"{color}{BOX_ROW}{ANSI_RESET} LOG CONTEXT ({len(context)} lines):")
        for ctx_line in context:
            lines_out.append(f"{color}{BOX_ROW}{ANSI_RESET}   {dim('>')} {ctx_line.rstrip()}")

        lines_out.append(f"{color}{BOX_DIV}{ANSI_RESET}")
        lines_out.append(
            f"{color}{BOX_ROW}{ANSI_RESET} FIX HINT: {pattern['fix_hint']}"
        )
        lines_out.append(
            f"{color}{BOX_ROW}{ANSI_RESET} RCA FILE : {pattern['rca_file']}"
        )

        lines_out.append(f"{color}{BOX_DIV}{ANSI_RESET}")
        lines_out.append(f"{color}{BOX_ROW}{ANSI_RESET} AIO-DEBUGGER PROMPT (paste into Claude):")
        lines_out.append(f"{color}{BOX_ROW}{ANSI_RESET} {dim('---')}")
        for prompt_line in aio_prompt.splitlines():
            lines_out.append(f"{color}{BOX_ROW}{ANSI_RESET} {prompt_line}")
        lines_out.append(f"{color}{BOX_ROW}{ANSI_RESET} {dim('---')}")

        lines_out.append(f"{color}{BOX_BOTTOM}{ANSI_RESET}")

        print("\n".join(lines_out))
        print()
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Pattern dumper
# ---------------------------------------------------------------------------

def dump_patterns() -> None:
    header_color = "\033[1;34m"  # bold blue
    print()
    print(f"{header_color}{'PATTERN':<22} {'SEVERITY':<10} {'COMPONENT':<18} {'RCA FILE':<35}{ANSI_RESET}")
    print("─" * 90)
    for name, p in _PATTERNS_BY_SEVERITY:
        color = SEVERITY_COLOR.get(p["severity"], "")
        print(
            f"{bold(name):<22} "
            f"{color}{p['severity']:<10}{ANSI_RESET} "
            f"{p['component']:<18} "
            f"{dim(p['rca_file'])}"
        )
        print(f"  {dim('desc:')} {p['description']}")
        print(f"  {dim('hint:')} {p['fix_hint']}")
        print(f"  {dim('regex:')} {p['regex']}")
        print()
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Log line classifier
# ---------------------------------------------------------------------------

def classify_line(line: str) -> Optional[tuple[str, dict]]:
    """
    Test line against all patterns in severity order (CRITICAL first).
    Returns (pattern_name, pattern_dict) for the first match, or None.
    """
    for name, pattern in _PATTERNS_BY_SEVERITY:
        if _COMPILED[name].search(line):
            return name, pattern
    return None


# ---------------------------------------------------------------------------
# Railway subprocess streaming
# ---------------------------------------------------------------------------

def build_railway_cmd(service: str, snapshot: bool) -> list[str]:
    if snapshot:
        return ["railway", "logs", "--service", service, "-n", "100"]
    return ["railway", "logs", "--service", service, "-f"]


def stream_logs(
    service: str,
    snapshot: bool,
    min_severity: str,
    context_lines: int,
) -> None:
    cmd = build_railway_cmd(service, snapshot)
    mode = "SNAPSHOT" if snapshot else "FOLLOW"
    min_rank = SEVERITY_RANK.get(min_severity.upper(), 0)

    print(bold(f"[live_trace] Starting Railway log stream"))
    print(f"  Service     : {service}")
    print(f"  Mode        : {mode}")
    print(f"  Min severity: {min_severity.upper()}")
    print(f"  Context     : {context_lines} lines")
    print(f"  Command     : {' '.join(cmd)}")
    print(dim("Press Ctrl-C to stop and print final stats."))
    print()
    sys.stdout.flush()

    stats = Stats()
    dedupe = DedupeWindow()
    reporter = IncidentReporter(context_lines=context_lines)

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
            f"\033[91mERROR: 'railway' CLI not found. "
            f"Install it: npm install -g @railway/cli\033[0m",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        for raw_line in proc.stdout:  # type: ignore[union-attr]
            line = raw_line.rstrip()
            if not line:
                continue

            stats.lines_scanned += 1
            reporter.push_line(line)

            # Print raw line in dim style so users see the stream
            print(dim(line))
            sys.stdout.flush()

            result = classify_line(line)
            if result is not None:
                pattern_name, pattern = result
                sev_rank = SEVERITY_RANK.get(pattern["severity"], 0)

                if sev_rank >= min_rank and dedupe.should_emit(pattern_name):
                    ts = datetime.now().strftime("%H:%M:%S")
                    reporter.emit(pattern_name, pattern, line, ts)
                    stats.record_incident(pattern_name, pattern["severity"])

            if stats.should_print(interval=60.0):
                stats.print_summary()

    except KeyboardInterrupt:
        pass
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    stats.print_summary(header="FINAL STATS")


# ---------------------------------------------------------------------------
# Snapshot mode: process fixed block
# ---------------------------------------------------------------------------

def run_snapshot(
    service: str,
    min_severity: str,
    context_lines: int,
) -> None:
    stream_logs(
        service=service,
        snapshot=True,
        min_severity=min_severity,
        context_lines=context_lines,
    )


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _handle_sigterm(signum: int, frame) -> None:  # noqa: ANN001
    global _shutdown_requested
    _shutdown_requested = True


signal.signal(signal.SIGTERM, _handle_sigterm)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="live_trace.py",
        description=(
            "Live-trace Railway livekit-voice-agent logs. "
            "Classifies errors into 8 AIO patterns and emits /aiodebug prompts."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--service",
        default="livekit-voice-agent",
        metavar="NAME",
        help="Railway service name (default: livekit-voice-agent)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--snapshot",
        action="store_true",
        help="Fetch last 100 log lines and exit (default: continuous follow)",
    )
    mode_group.add_argument(
        "--follow",
        action="store_true",
        default=True,
        help="Continuous log follow mode (default)",
    )
    parser.add_argument(
        "--min-severity",
        default="LOW",
        choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
        metavar="LEVEL",
        help="Minimum severity to report (LOW|MEDIUM|HIGH|CRITICAL). Default: LOW",
    )
    parser.add_argument(
        "--context-lines",
        type=int,
        default=3,
        metavar="N",
        help="Number of log lines to include in incident context (default: 3)",
    )
    parser.add_argument(
        "--dump-patterns",
        action="store_true",
        help="Print all 8 patterns in table format and exit",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.dump_patterns:
        dump_patterns()
        sys.exit(0)

    stream_logs(
        service=args.service,
        snapshot=args.snapshot,
        min_severity=args.min_severity,
        context_lines=args.context_lines,
    )


if __name__ == "__main__":
    main()
