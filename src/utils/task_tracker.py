"""In-session task tracker for heartbeat-driven continuation.

Tracks multi-step tool execution state so the heartbeat loop can detect when
a task has stalled and inject a continuation signal — without speaking unless
the agent is genuinely idle with an incomplete objective.

Design principles:
- Thread-safe (state updated from synchronous callbacks, read from async loop)
- Zero latency impact on normal conversation flow
- Self-limiting: max 3 continuations per objective to prevent infinite loops
- Stall detection only fires when tools were involved (not idle chat)
- Silent after task completion: heartbeat NEVER fires after the agent has
  already responded to a tool result — only fires on genuine unaddressed stalls
"""
import time
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TaskTracker:
    """Tracks in-session task state for heartbeat-driven continuation.

    State flow:
      User message → record_user_message() → sets objective if task-like
      Tool starts  → record_tool_call_started()
      Tool ends    → record_tool_call_completed()
      Agent speaks → record_agent_responding()
      Agent idle   → record_agent_idle()
      Heartbeat    → should_inject_continuation() → get_continuation_prompt()
    """

    #: Keywords that indicate the user is requesting an action (not just chatting)
    _TASK_KEYWORDS = (
        "send", "email", "find", "search", "get", "fetch", "list",
        "create", "make", "write", "save", "store", "add", "update",
        "delete", "remove", "move", "copy", "download", "upload",
        "check", "look up", "look for", "pull up", "open",
        "tell me", "show me", "give me", "read me", "summarize",
        "can you", "please", "could you", "help me", "i need",
        "schedule", "book", "set up", "configure", "connect",
        "draft", "compose", "reply", "respond", "message",
        "query", "analyse", "analyze", "report", "calculate",
    )

    def __init__(self, stall_threshold_seconds: float = 8.0,
                 max_continuations_per_objective: int = 3):
        self._lock = threading.Lock()

        # Task state
        self._current_objective: Optional[str] = None
        self._objective_completed: bool = True

        # Activity timestamps
        self._last_activity_at: float = time.monotonic()
        self._last_user_message_at: float = time.monotonic()
        self._session_start: float = time.monotonic()

        # Tool call tracking
        self._tool_calls_pending: int = 0
        self._total_tool_calls_for_objective: int = 0
        # True only between a tool completing and the agent responding.
        # The heartbeat fires ONLY in this window — never after the agent has
        # already addressed the tool result (which would be post-task noise).
        self._tool_completed_since_last_response: bool = False

        # Agent state
        self._agent_is_responding: bool = False

        # Continuation limits
        self._continuation_count: int = 0
        self._max_continuations: int = max_continuations_per_objective
        self._stall_threshold: float = stall_threshold_seconds

        logger.info(
            f"[Heartbeat] TaskTracker initialized "
            f"(stall={stall_threshold_seconds}s, max_continuations={max_continuations_per_objective})"
        )

    # ── State update methods (called from event hooks) ──────────────────────

    def record_user_message(self, text: str) -> None:
        """Called when the user speaks. Sets objective if message is task-like."""
        with self._lock:
            now = time.monotonic()
            self._last_activity_at = now
            self._last_user_message_at = now
            # Reset continuation counter — new message, fresh start
            self._continuation_count = 0

            if self._is_task_request(text):
                self._current_objective = text[:300]
                self._objective_completed = False
                self._total_tool_calls_for_objective = 0
                self._tool_completed_since_last_response = False
                logger.debug(
                    f"[Heartbeat] Objective captured: '{text[:60]}...'"
                    if len(text) > 60 else f"[Heartbeat] Objective captured: '{text}'"
                )

    def record_tool_call_started(self) -> None:
        """Called when a tool begins executing."""
        with self._lock:
            self._tool_calls_pending += 1
            self._total_tool_calls_for_objective += 1
            self._last_activity_at = time.monotonic()
            logger.debug(
                f"[Heartbeat] Tool started "
                f"(pending={self._tool_calls_pending}, total={self._total_tool_calls_for_objective})"
            )

    def record_tool_call_completed(self) -> None:
        """Called when a tool finishes executing.

        Also increments the total counter — this is the sole production hook
        (on_function_tools_executed). record_tool_call_started() is optional
        and only used if a started hook becomes available.
        """
        with self._lock:
            self._tool_calls_pending = max(0, self._tool_calls_pending - 1)
            self._total_tool_calls_for_objective += 1
            self._tool_completed_since_last_response = True  # arm the stall detector
            self._last_activity_at = time.monotonic()
            logger.debug(
                f"[Heartbeat] Tool completed "
                f"(pending={self._tool_calls_pending}, total={self._total_tool_calls_for_objective})"
            )

    def record_agent_responding(self) -> None:
        """Called when agent starts speaking (thinking→speaking transition).

        Disarms the stall detector — the agent has addressed the tool result,
        so the heartbeat must not fire again until another tool completes.
        """
        with self._lock:
            self._agent_is_responding = True
            self._tool_completed_since_last_response = False  # disarm stall detector
            self._last_activity_at = time.monotonic()

    def record_agent_idle(self) -> None:
        """Called when agent transitions to listening/idle state."""
        with self._lock:
            self._agent_is_responding = False
            self._last_activity_at = time.monotonic()

    def mark_objective_complete(self) -> None:
        """Mark current objective as done. Stops heartbeat from injecting."""
        with self._lock:
            self._objective_completed = True
            self._continuation_count = 0
            self._tool_calls_pending = 0
            self._tool_completed_since_last_response = False
            logger.debug("[Heartbeat] Objective marked complete")

    # ── Heartbeat decision methods ────────────────────────────────────────────

    def should_inject_continuation(self) -> bool:
        """Returns True if the heartbeat should inject a continuation signal.

        Two detection cases:

        CASE 1 — Tool-result stall (tight 4s threshold):
          A tool completed but the agent has not yet responded. The flag
          `_tool_completed_since_last_response` is armed on tool completion and
          disarmed when the agent starts speaking. Only fires within this window.

        CASE 2 — No-tool stall (16s threshold):
          The current objective has zero tool calls. The agent spoke (or was
          asked) but never executed a tool — catches LLM hallucination stalls
          where the model claims to be working without actually calling anything.
          `_total_tool_calls_for_objective` is reset to 0 on each new user task
          message, so this correctly detects per-task inaction.

        Both cases require: active objective + agent idle + < max continuations.
        """
        with self._lock:
            # No active task
            if self._objective_completed or self._current_objective is None:
                return False

            # Agent is still working
            if self._agent_is_responding:
                return False

            # Continuation limit reached — give up to prevent loops
            if self._continuation_count >= self._max_continuations:
                logger.debug(
                    f"[Heartbeat] Max continuations ({self._max_continuations}) reached for objective"
                )
                return False

            idle_seconds = time.monotonic() - self._last_activity_at

            # CASE 1: Tool completed, agent hasn't responded yet — tight stall window
            if (self._total_tool_calls_for_objective > 0 and
                    self._tool_completed_since_last_response and
                    idle_seconds >= self._stall_threshold):
                return True

            # CASE 2: No tools called for this objective — agent may be stalling
            # without taking action (spoke but didn't execute). Longer threshold
            # avoids false positives on brief agent responses.
            if (self._total_tool_calls_for_objective == 0 and
                    idle_seconds >= self._stall_threshold * 4):  # 16s
                return True

            return False

    def get_continuation_prompt(self) -> str:
        """Build the continuation instructions for the LLM.

        Increments the continuation counter to enforce the limit.
        """
        with self._lock:
            self._continuation_count += 1
            objective = self._current_objective or "the current task"
            count = self._continuation_count
            max_c = self._max_continuations

            prompt = (
                f"You are mid-task. The user's objective was: '{objective}'. "
                f"You used {self._total_tool_calls_for_objective} tool call(s) so far. "
                f"Check whether the task is fully complete. If any steps remain, "
                f"continue executing them now without waiting for the user to prompt you again. "
                f"If the task is done, summarize what was accomplished. "
                f"[Internal continuation {count}/{max_c}]"
            )
            logger.info(
                f"[Heartbeat] Continuation prompt {count}/{max_c} for objective: '{objective[:50]}...'"
                if len(objective) > 50 else
                f"[Heartbeat] Continuation prompt {count}/{max_c} for objective: '{objective}'"
            )
            return prompt

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def has_active_objective(self) -> bool:
        with self._lock:
            return self._current_objective is not None and not self._objective_completed

    @property
    def is_agent_responding(self) -> bool:
        with self._lock:
            return self._agent_is_responding

    @property
    def session_age_seconds(self) -> float:
        return time.monotonic() - self._session_start

    @property
    def idle_seconds(self) -> float:
        with self._lock:
            return time.monotonic() - self._last_activity_at

    # ── Private helpers ───────────────────────────────────────────────────────

    @classmethod
    def _is_task_request(cls, text: str) -> bool:
        """Heuristic: does this utterance contain a task/action request?"""
        text_lower = text.lower()
        return any(kw in text_lower for kw in cls._TASK_KEYWORDS)
