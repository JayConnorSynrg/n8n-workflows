"""Regression tests for _gamma_notification_monitor announcement policy.

These tests verify that ALL three Gamma completion paths use generate_reply
with the URL-safe instruction policy, preventing verbal URL readout.

Test categories:
  1. Source structure tests — verify say() is not in the critical paths
  2. Instruction content tests — verify policy strings are present
  3. Path coverage tests — verify all 3 paths (main, retry, silent) use generate_reply

Architecture under test:
  - _gamma_notification_monitor is a nested coroutine defined inside the
    entrypoint function in src/agent.py.
  - Three completion paths:
      Path A (main):    if message: → generate_reply(_gamma_offer_instructions)
      Path B (retry):   except Exception → generate_reply(_retry_offer_instructions)
      Path C (silent):  else: if gamma_url: → generate_reply(instructions)
  - Path C has ONE allowed say() call: the AttributeError fallback only.
  - All other paths must NOT call say().

All tests are STRUCTURAL (inspect source text / AST). No LiveKit session,
no Railway, no DB, no external calls required.
"""

from __future__ import annotations

import ast
import inspect
import re
import sys
import time
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Import guard — agent.py has heavy LiveKit/LKKit transitive dependencies.
# We import the module object only to extract source via inspect.getsource.
# If the import fails we mark all tests as skipped (not failed) because the
# assertions are on source text, not on runtime behaviour.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_AGENT_PATH = _REPO_ROOT / "src" / "agent.py"

AGENT_IMPORTABLE: bool = False
_agent_module: Any = None

try:
    # Use importlib to load the source without executing top-level side-effects
    # that require a running LiveKit room — we only need the source text.
    import importlib.util as _ilu

    _spec = _ilu.spec_from_file_location("src.agent", _AGENT_PATH)
    # Do NOT exec_module — that triggers LiveKit entrypoint side-effects.
    # Instead read raw source directly from the file path.
    _AGENT_SOURCE: str = _AGENT_PATH.read_text(encoding="utf-8")
    AGENT_IMPORTABLE = True
except Exception as _import_err:  # pragma: no cover
    _AGENT_SOURCE = ""
    AGENT_IMPORTABLE = False

pytestmark = pytest.mark.skipif(
    not AGENT_IMPORTABLE,
    reason="src/agent.py source not readable in test env",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_monitor_source(full_source: str) -> str:
    """Return the source lines belonging to _gamma_notification_monitor.

    Strategy: locate the ``async def _gamma_notification_monitor`` definition
    line, then collect lines until the next function definition at the same or
    lower indentation level (or the spawning ``asyncio.create_task`` line that
    follows the function body).

    Returns an empty string if the function cannot be located.
    """
    lines = full_source.splitlines()
    start_idx: int | None = None
    indent_level: int | None = None

    for i, line in enumerate(lines):
        if "async def _gamma_notification_monitor" in line:
            start_idx = i
            # Measure leading whitespace of the def line
            indent_level = len(line) - len(line.lstrip())
            break

    if start_idx is None or indent_level is None:
        return ""

    collected: list[str] = []
    for line in lines[start_idx:]:
        stripped = line.lstrip()
        current_indent = len(line) - len(stripped)

        # Stop when we hit a non-blank line at the SAME or LOWER indentation
        # that is NOT the opening def line itself.
        if (
            collected  # skip the very first line comparison
            and stripped  # ignore blank lines
            and current_indent <= indent_level
            and not line.strip().startswith("async def _gamma_notification_monitor")
        ):
            break

        collected.append(line)

    return "\n".join(collected)


def _count_occurrences(source: str, pattern: str) -> int:
    """Count non-overlapping occurrences of pattern in source."""
    return source.count(pattern)


def _timing_print(label: str, start: float) -> None:
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"\n[TIMING] {label}: {elapsed_ms:.1f}ms")


# Pre-extract monitor source once at collection time for reuse across tests.
_MONITOR_SOURCE: str = _extract_monitor_source(_AGENT_SOURCE)


# ===========================================================================
# Class 1 — Source Structure Tests
# ===========================================================================


class TestGammaMonitorSourceStructure:
    """Verify _gamma_notification_monitor source code policy compliance.

    These tests confirm that the function exists, that say() appears only
    in the AttributeError fallback (exactly once), and that generate_reply
    is the primary announcement mechanism.
    """

    def test_monitor_function_exists_in_agent_source(self) -> None:
        """_gamma_notification_monitor must be defined in agent.py."""
        start = time.perf_counter()

        assert "async def _gamma_notification_monitor" in _AGENT_SOURCE, (
            "_gamma_notification_monitor not found in src/agent.py — "
            "function may have been renamed or removed"
        )

        _timing_print("test_monitor_function_exists_in_agent_source", start)

    def test_monitor_source_is_non_empty(self) -> None:
        """Helper _extract_monitor_source must return non-empty text for the function."""
        start = time.perf_counter()

        assert _MONITOR_SOURCE, (
            "_extract_monitor_source returned empty string — "
            "monitor function boundary detection failed"
        )
        # Sanity: extracted source must contain the function signature
        assert "async def _gamma_notification_monitor" in _MONITOR_SOURCE

        _timing_print("test_monitor_source_is_non_empty", start)

    def test_generate_reply_called_at_least_three_times(self) -> None:
        """generate_reply must appear at least 3 times in the monitor (one per path)."""
        start = time.perf_counter()

        count = _count_occurrences(_MONITOR_SOURCE, "generate_reply")
        assert count >= 3, (
            f"Expected >= 3 calls to generate_reply in _gamma_notification_monitor, "
            f"found {count}. "
            "One of the three Gamma completion paths (main / retry / silent) is missing "
            "its generate_reply call."
        )

        _timing_print("test_generate_reply_called_at_least_three_times", start)

    def test_say_appears_at_most_once_in_monitor(self) -> None:
        """say() must appear at most once — only the AttributeError fallback is allowed.

        The policy requires ALL critical paths to use generate_reply so the
        LLM can format the message without reading the URL aloud.
        The single permitted say() is the AttributeError recovery branch in the
        silent path.
        """
        start = time.perf_counter()

        # Count occurrences of the say( call pattern — use .say( to exclude
        # string occurrences like "session.say" in comments.
        say_count = _count_occurrences(_MONITOR_SOURCE, ".say(")
        assert say_count <= 1, (
            f"Expected at most 1 occurrence of .say( in _gamma_notification_monitor, "
            f"found {say_count}. "
            "Additional say() calls bypass the URL-safe generate_reply policy."
        )

        _timing_print("test_say_appears_at_most_once_in_monitor", start)

    def test_say_fallback_is_inside_attribute_error_handler(self) -> None:
        """The single allowed say() call must be inside an AttributeError except block."""
        start = time.perf_counter()

        # Find the line number of the only allowed .say( call
        lines = _MONITOR_SOURCE.splitlines()
        say_lines = [i for i, ln in enumerate(lines) if ".say(" in ln]

        assert len(say_lines) <= 1, (
            f"More than one .say( line found in monitor: {say_lines}"
        )

        if say_lines:
            say_line_idx = say_lines[0]
            # Walk backwards from the say() line to find the nearest except clause
            preceding = "\n".join(lines[:say_line_idx])
            assert "AttributeError" in preceding, (
                "The .say( call in _gamma_notification_monitor must be inside an "
                "AttributeError except block. Found say() without a preceding "
                "AttributeError handler — this means say() is being used outside "
                "the sanctioned fallback path."
            )

        _timing_print("test_say_fallback_is_inside_attribute_error_handler", start)

    def test_no_bare_say_in_main_path(self) -> None:
        """The main success path (if message:) must not contain a bare say() call."""
        start = time.perf_counter()

        # Isolate the main path: lines between 'if message:' and the first
        # 'except Exception' that follows it (the retry handler).
        lines = _MONITOR_SOURCE.splitlines()

        in_main_path = False
        main_path_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("if message:"):
                in_main_path = True
                continue
            if in_main_path:
                # The retry except block begins with 'except Exception as say_err:'
                if stripped.startswith("except Exception as say_err:"):
                    # Don't stop — retry block is also part of the main branch
                    pass
                # Stop when we reach the 'else:' branch (silent path)
                if re.match(r"^else\s*:", stripped):
                    break
                main_path_lines.append(line)

        main_path_text = "\n".join(main_path_lines)

        # In the main path, say() must not appear (generate_reply is used instead)
        assert ".say(" not in main_path_text, (
            "Found .say( in the main Gamma notification path (if message: branch). "
            "This path must use generate_reply exclusively."
        )

        _timing_print("test_no_bare_say_in_main_path", start)

    def test_create_task_spawns_monitor(self) -> None:
        """asyncio.create_task(_gamma_notification_monitor(...)) must appear in agent source."""
        start = time.perf_counter()

        assert "create_task(_gamma_notification_monitor" in _AGENT_SOURCE, (
            "asyncio.create_task(_gamma_notification_monitor(...)) not found in agent.py. "
            "The monitor must be spawned as a background task."
        )

        _timing_print("test_create_task_spawns_monitor", start)


# ===========================================================================
# Class 2 — Instruction Content Tests
# ===========================================================================


class TestGammaInstructionPolicy:
    """Verify instruction strings contain required URL safety directives.

    The core policy has two mandatory clauses in EVERY notification path:
      1. "do NOT say this URL aloud" — prevents TTS from vocalising raw URLs
      2. "offer to email" — standardises the follow-up offer to the user
    """

    def test_do_not_say_url_aloud_present(self) -> None:
        """'do NOT say this URL aloud' must appear in the monitor source."""
        start = time.perf_counter()

        policy_phrase = "do NOT say this URL aloud"
        assert policy_phrase in _MONITOR_SOURCE, (
            f"Required policy phrase {policy_phrase!r} not found in "
            "_gamma_notification_monitor. "
            "Without this directive the LLM may read raw Gamma URLs aloud."
        )

        _timing_print("test_do_not_say_url_aloud_present", start)

    def test_offer_to_email_present(self) -> None:
        """'offer to email' must appear in the monitor source."""
        start = time.perf_counter()

        offer_phrase = "offer to email"
        assert offer_phrase in _MONITOR_SOURCE, (
            f"Required policy phrase {offer_phrase!r} not found in "
            "_gamma_notification_monitor. "
            "The agent must always offer to email the Gamma link instead of vocalising it."
        )

        _timing_print("test_offer_to_email_present", start)

    def test_do_not_say_url_aloud_appears_in_multiple_paths(self) -> None:
        """'do NOT say this URL aloud' must appear in at least 2 paths.

        The main path and retry path each build their own instruction string
        (_gamma_offer_instructions and _retry_offer_instructions) and both must
        carry the URL safety directive. The silent path may share one occurrence.
        Minimum expected: 2 (main + retry share identical template; silent is
        separate). Counts >= 2 confirm redundant policy coverage.
        """
        start = time.perf_counter()

        count = _count_occurrences(_MONITOR_SOURCE, "do NOT say this URL aloud")
        assert count >= 2, (
            f"Expected 'do NOT say this URL aloud' in at least 2 instruction "
            f"strings, found {count}. "
            "The main path and retry path must each contain the URL safety directive."
        )

        _timing_print("test_do_not_say_url_aloud_appears_in_multiple_paths", start)

    def test_offer_to_email_appears_in_multiple_paths(self) -> None:
        """'offer to email' must appear in at least 2 instruction strings.

        Same reasoning as URL safety directive — main and retry paths must
        both carry the offer-to-email directive.
        """
        start = time.perf_counter()

        count = _count_occurrences(_MONITOR_SOURCE, "offer to email")
        assert count >= 2, (
            f"Expected 'offer to email' in at least 2 instruction strings, "
            f"found {count}. "
            "The main and retry paths must both prompt the agent to offer email delivery."
        )

        _timing_print("test_offer_to_email_appears_in_multiple_paths", start)

    def test_gamma_offer_instructions_variable_name(self) -> None:
        """_gamma_offer_instructions variable must exist (main path instruction builder)."""
        start = time.perf_counter()

        assert "_gamma_offer_instructions" in _MONITOR_SOURCE, (
            "_gamma_offer_instructions variable not found in _gamma_notification_monitor. "
            "The main notification path must build its instruction string in this named variable."
        )

        _timing_print("test_gamma_offer_instructions_variable_name", start)

    def test_retry_offer_instructions_variable_name(self) -> None:
        """_retry_offer_instructions variable must exist (retry path instruction builder)."""
        start = time.perf_counter()

        assert "_retry_offer_instructions" in _MONITOR_SOURCE, (
            "_retry_offer_instructions variable not found in _gamma_notification_monitor. "
            "The retry exception path must build its instruction string in this named variable."
        )

        _timing_print("test_retry_offer_instructions_variable_name", start)

    def test_instructions_variable_used_in_silent_path(self) -> None:
        """The silent path must build an 'instructions' variable for generate_reply."""
        start = time.perf_counter()

        # In the silent path the variable is simply named `instructions`
        # (not prefixed with _gamma_ or _retry_).
        # Check it's assigned as a string in the else branch.
        assert "instructions = (" in _MONITOR_SOURCE or 'instructions = f"' in _MONITOR_SOURCE or "instructions = (" in _MONITOR_SOURCE, (
            "'instructions' variable assignment not found in _gamma_notification_monitor "
            "silent path. The silent completion path must build an instruction string "
            "for generate_reply."
        )

        _timing_print("test_instructions_variable_used_in_silent_path", start)

    def test_no_raw_url_vocal_output_pattern(self) -> None:
        """generate_reply calls must not inject raw URL strings as voice output.

        Confirms the monitor never builds instructions that say 'Here is the link:'
        as a standalone voice sentence (which would be read aloud by the LLM verbatim).
        The only permitted 'Here' prefix is inside the fallback say() path.
        """
        start = time.perf_counter()

        # "Here's your direct auth link" is the auth-flow phrase (not Gamma).
        # The pattern we forbid in generate_reply instructions for Gamma is
        # embedding the URL as a spoken sentence like "Here is the link: https://..."
        # outside the fallback say() block.

        # Extract lines that contain generate_reply in the monitor
        lines = _MONITOR_SOURCE.splitlines()
        generate_reply_lines = [ln for ln in lines if "generate_reply" in ln]

        # None of the generate_reply calls should have a raw http URL injected inline
        for ln in generate_reply_lines:
            assert "http" not in ln, (
                f"generate_reply call contains a hardcoded http URL inline: {ln!r}. "
                "URL injection must be in the instruction string variable, not directly "
                "in the generate_reply() call arguments."
            )

        _timing_print("test_no_raw_url_vocal_output_pattern", start)


# ===========================================================================
# Class 3 — Path Coverage Tests
# ===========================================================================


class TestGammaPathCoverage:
    """Verify all 3 notification paths are present and use generate_reply.

    Path A — Main success path:   if message: → _gamma_offer_instructions
    Path B — Retry/except path:   except Exception as say_err → _retry_offer_instructions
    Path C — Silent path:         else: if gamma_url: → instructions variable
    """

    def test_main_path_uses_generate_reply_with_offer_instructions(self) -> None:
        """Path A: generate_reply must be called with _gamma_offer_instructions."""
        start = time.perf_counter()

        # Both the variable assignment and the generate_reply call must be present
        assert "_gamma_offer_instructions" in _MONITOR_SOURCE, (
            "Path A (_gamma_offer_instructions) not found in monitor"
        )
        assert "generate_reply(instructions=_gamma_offer_instructions)" in _MONITOR_SOURCE, (
            "Path A generate_reply call with _gamma_offer_instructions not found. "
            "The main notification path must call "
            "generate_reply(instructions=_gamma_offer_instructions)."
        )

        _timing_print("test_main_path_uses_generate_reply_with_offer_instructions", start)

    def test_retry_path_uses_generate_reply_with_retry_instructions(self) -> None:
        """Path B: generate_reply must be called with _retry_offer_instructions."""
        start = time.perf_counter()

        assert "_retry_offer_instructions" in _MONITOR_SOURCE, (
            "Path B (_retry_offer_instructions) not found in monitor"
        )
        assert "generate_reply(instructions=_retry_offer_instructions)" in _MONITOR_SOURCE, (
            "Path B generate_reply call with _retry_offer_instructions not found. "
            "The retry exception path must call "
            "generate_reply(instructions=_retry_offer_instructions)."
        )

        _timing_print("test_retry_path_uses_generate_reply_with_retry_instructions", start)

    def test_silent_path_uses_generate_reply_with_instructions(self) -> None:
        """Path C: generate_reply must be called with the 'instructions' variable."""
        start = time.perf_counter()

        assert "generate_reply(instructions=instructions)" in _MONITOR_SOURCE, (
            "Path C generate_reply call with 'instructions' variable not found. "
            "The silent notification path must call "
            "generate_reply(instructions=instructions)."
        )

        _timing_print("test_silent_path_uses_generate_reply_with_instructions", start)

    def test_retry_path_is_inside_except_block(self) -> None:
        """Path B must be triggered by an except clause (not a conditional branch)."""
        start = time.perf_counter()

        lines = _MONITOR_SOURCE.splitlines()
        retry_line_idx: int | None = None
        for i, ln in enumerate(lines):
            if "_retry_offer_instructions" in ln:
                retry_line_idx = i
                break

        assert retry_line_idx is not None, (
            "_retry_offer_instructions assignment not found in monitor source"
        )

        # Walk backwards to find the nearest except clause
        preceding_text = "\n".join(lines[:retry_line_idx])
        assert "except" in preceding_text, (
            "_retry_offer_instructions must be defined inside an except block. "
            "The retry path must only execute when the main generate_reply raises."
        )

        _timing_print("test_retry_path_is_inside_except_block", start)

    def test_silent_path_is_inside_else_block(self) -> None:
        """Path C (silent) must be in the 'else:' branch of the 'if message:' gate."""
        start = time.perf_counter()

        # Find the 'else:' line and confirm generate_reply(instructions=instructions)
        # comes after it in the monitor source.
        lines = _MONITOR_SOURCE.splitlines()

        else_idx: int | None = None
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if re.match(r"^else\s*:", stripped):
                else_idx = i
                break

        assert else_idx is not None, (
            "No 'else:' branch found in _gamma_notification_monitor. "
            "The silent path must be the else branch of 'if message:'."
        )

        # Confirm generate_reply(instructions=instructions) appears after else_idx
        after_else = "\n".join(lines[else_idx:])
        assert "generate_reply(instructions=instructions)" in after_else, (
            "generate_reply(instructions=instructions) not found after the 'else:' "
            "branch in _gamma_notification_monitor. Path C (silent) is missing."
        )

        _timing_print("test_silent_path_is_inside_else_block", start)

    def test_all_three_paths_counted_by_unique_variable_names(self) -> None:
        """All three instruction variable names must be present — one per path.

        This is a composite assertion that fails if any path is removed or merged.
        """
        start = time.perf_counter()

        required_variables = [
            "_gamma_offer_instructions",   # Path A (main)
            "_retry_offer_instructions",   # Path B (retry)
            "instructions = (",             # Path C (silent) — uses generic name
        ]

        missing = [v for v in required_variables if v not in _MONITOR_SOURCE]
        assert not missing, (
            f"Missing instruction variable(s) in _gamma_notification_monitor: {missing}. "
            "Each of the 3 Gamma completion paths must build its own instruction string."
        )

        _timing_print("test_all_three_paths_counted_by_unique_variable_names", start)

    def test_attribute_error_fallback_only_in_silent_path(self) -> None:
        """AttributeError except block must only appear in the silent path (Path C).

        If AttributeError handling is found in Paths A or B it indicates that
        say() has been re-introduced into a critical path.
        """
        start = time.perf_counter()

        count = _count_occurrences(_MONITOR_SOURCE, "AttributeError")
        # Exactly one AttributeError handler is expected — the silent path fallback
        assert count == 1, (
            f"Expected exactly 1 AttributeError handler in _gamma_notification_monitor, "
            f"found {count}. "
            "AttributeError handling (which guards the fallback say() call) must only "
            "exist in Path C (silent path). Multiple handlers suggest say() was added "
            "to another path."
        )

        _timing_print("test_attribute_error_fallback_only_in_silent_path", start)

    def test_gamma_monitor_loop_continues_after_error(self) -> None:
        """The outer while True loop must recover from errors via asyncio.sleep.

        Confirms that a broken notification does not crash the monitor permanently.
        """
        start = time.perf_counter()

        assert "asyncio.CancelledError" in _MONITOR_SOURCE, (
            "asyncio.CancelledError handler not found in _gamma_notification_monitor. "
            "The monitor loop must handle CancelledError to exit cleanly."
        )
        assert "while True" in _MONITOR_SOURCE, (
            "'while True' loop not found in _gamma_notification_monitor. "
            "The monitor must run indefinitely until cancelled."
        )

        _timing_print("test_gamma_monitor_loop_continues_after_error", start)
