"""In-session task tracker for heartbeat-driven continuation.

Tracks multi-step tool execution state so the heartbeat loop can detect when
a task has stalled and inject a continuation signal — without speaking unless
the agent is genuinely idle with an incomplete objective.

Design principles:
- Thread-safe (state updated from synchronous callbacks, read from async loop)
- Zero latency impact on normal conversation flow
- Self-limiting: max N continuations per objective to prevent infinite loops
- Three-case stall detection (see should_inject_continuation docstring)
- Inspired by OpenClaw's isLikelyInterimCronMessage() for phrase detection
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
      Agent thinks → record_agent_responding()
      Agent speaks → record_agent_speech(text)
      Agent idle   → record_agent_idle()
      Heartbeat    → should_inject_continuation() → get_continuation_prompt()
    """

    #: Short phrases the LLM uses when mid-task but hasn't called a tool yet.
    #: Adapted from OpenClaw's isLikelyInterimCronMessage() heuristic.
    #: Match condition: ≤50 words AND contains one of these phrases.
    _INTERIM_PHRASES = (
        "on it",
        "working on it",
        "let me try",
        "let me check",
        "let me look",
        "let me find",
        "let me get",
        "let me fetch",
        "let me send",
        "let me create",
        "let me search",
        "let me see if",
        "let me see what",
        "let me attempt",
        "give me a",
        "one moment",
        "one second",
        "one sec",
        "just a moment",
        "just a second",
        "hold on",
        "i'll try",
        "i will try",
        "i'm trying",
        "i am trying",
        "trying to",
        "attempting to",
        "i need to create",
        "i need to get",
        "i need to find",
        "i need to send",
        "i need to fetch",
        "pulling that",
        "gathering that",
        "stand by",
        "bear with me",
        "retrying",
        "let me retry",
    )

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
                 max_continuations_per_objective: int = 5,
                 min_continuation_gap_seconds: float = 8.0):
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
        # Armed when a tool completes, disarmed when agent starts responding.
        # Case 1 stall detection window.
        self._tool_completed_since_last_response: bool = False

        # Agent state
        self._agent_is_responding: bool = False
        # Set when agent's speech contains an interim phrase (OpenClaw-style).
        # Stays armed until: tool runs, new user message, definitive response, or injection.
        self._agent_gave_interim_response: bool = False

        # Continuation limits
        self._continuation_count: int = 0
        self._max_continuations: int = max_continuations_per_objective
        self._stall_threshold: float = stall_threshold_seconds

        # Cooldown: minimum gap between consecutive continuations.
        # Prevents rapid-fire when generate_reply resolves in 1-2s without speech —
        # which would otherwise leave _agent_gave_interim_response armed and re-trigger
        # Case 3 every 4 seconds until max_continuations is exhausted.
        self._last_continuation_at: float = 0.0
        self._min_continuation_gap: float = min_continuation_gap_seconds

        logger.info(
            f"[Heartbeat] TaskTracker initialized "
            f"(stall={stall_threshold_seconds}s, max_continuations={max_continuations_per_objective}, "
            f"min_gap={min_continuation_gap_seconds}s)"
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
            self._agent_gave_interim_response = False

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

        This is the sole production hook (on_function_tools_executed).
        Arms Case 1 stall detection and clears the interim-phrase flag
        (agent acted, so prior interim speech is resolved).
        """
        with self._lock:
            self._tool_calls_pending = max(0, self._tool_calls_pending - 1)
            self._total_tool_calls_for_objective += 1
            self._tool_completed_since_last_response = True  # arm Case 1
            self._agent_gave_interim_response = False          # resolved by tool action
            self._last_activity_at = time.monotonic()
            logger.debug(
                f"[Heartbeat] Tool completed "
                f"(pending={self._tool_calls_pending}, total={self._total_tool_calls_for_objective})"
            )

    def record_agent_responding(self) -> None:
        """Called when agent starts thinking (thinking state transition).

        Disarms Case 1 — the agent is addressing the tool result.
        """
        with self._lock:
            self._agent_is_responding = True
            self._tool_completed_since_last_response = False  # disarm Case 1
            self._last_activity_at = time.monotonic()

    def record_agent_speech(self, text: str) -> None:
        """Called with the agent's actual spoken text after speech completes.

        OpenClaw-style interim-phrase detection: if the agent's response is
        short (≤50 words) and contains a phrase like "let me try" or "working
        on it", it's flagged as an interim response. Case 3 will fire if the
        agent then goes idle without calling a tool.

        If the text is substantive (not interim), the flag is cleared — the
        agent gave a definitive response and the heartbeat should stay silent.
        """
        with self._lock:
            if not text:
                return
            text_lower = text.lower()
            word_count = len(text_lower.split())
            is_interim = (
                word_count <= 50 and
                any(phrase in text_lower for phrase in self._INTERIM_PHRASES)
            )
            if is_interim:
                self._agent_gave_interim_response = True
                logger.debug(
                    f"[Heartbeat] Interim phrase in agent speech: '{text[:80]}'"
                )
            else:
                # Definitive response — agent addressed the situation
                self._agent_gave_interim_response = False

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
            self._agent_gave_interim_response = False
            logger.debug("[Heartbeat] Objective marked complete")

    def is_max_continuations_reached(self) -> bool:
        """Returns True when continuation limit is exhausted for the current objective.

        Distinct from should_inject_continuation() returning False — this signals
        that the agent has genuinely hit the ceiling and needs to announce it, rather
        than silently freezing. Only meaningful when has_active_objective is True.
        """
        with self._lock:
            if self._objective_completed or self._current_objective is None:
                return False
            return self._continuation_count >= self._max_continuations

    # ── Heartbeat decision methods ────────────────────────────────────────────

    def should_inject_continuation(self) -> bool:
        """Returns True if the heartbeat should inject a continuation signal.

        Three detection cases (all require: active objective + agent idle +
        < max continuations):

        CASE 1 — Tool-result stall (tight stall_threshold):
          A tool completed but the agent has NOT yet responded. Flag
          `_tool_completed_since_last_response` is armed by tool completion
          and disarmed when the agent starts thinking. Catches: agent freezes
          between tool result and its next response.

        CASE 2 — No-tool stall (4× stall_threshold = 16s):
          Zero tool calls for the current objective. Agent spoke (or was
          asked) but never executed a tool. Catches: LLM hallucination stalls
          where the model claims to be working without calling anything.
          `_total_tool_calls_for_objective` resets on each new task message.

        CASE 3 — Interim-phrase stall (stall_threshold):
          Agent's last speech matched an interim phrase (≤50 words + "let me
          try", "working on it", etc.) and the agent is now idle. Catches:
          multi-step stalls where tool 1 ran, agent said an interim phrase for
          tool 2, then stalled. Inspired by OpenClaw's isLikelyInterimCronMessage.
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

            # CASE 1: Tool completed, agent hasn't responded yet — tight stall.
            # No cooldown applied — tool-result stalls need immediate response.
            if (self._total_tool_calls_for_objective > 0 and
                    self._tool_completed_since_last_response and
                    idle_seconds >= self._stall_threshold):
                logger.info("[Heartbeat] CASE 1 stall: tool ran, no response yet")
                return True

            # Rate-limit Cases 2 and 3 — enforce minimum gap between continuations.
            # Without this, generate_reply resolves in ~1.5s without speech, leaving
            # _agent_gave_interim_response armed, causing Case 3 to fire again 4s later
            # and consuming all 3 continuations in ~11 seconds.
            gap_since_last = time.monotonic() - self._last_continuation_at
            if gap_since_last < self._min_continuation_gap:
                return False  # Too soon — cooldown not expired

            # CASE 2: No tools called for objective — agent may be stalling without
            # taking action (spoke but didn't execute). Longer threshold.
            if (self._total_tool_calls_for_objective == 0 and
                    idle_seconds >= self._stall_threshold * 4):  # 16s default
                logger.info("[Heartbeat] CASE 2 stall: no tools called, long idle")
                return True

            # CASE 3: Agent gave interim phrase response then went silent.
            # Tool action (if any) would have cleared this flag.
            if (self._agent_gave_interim_response and
                    idle_seconds >= self._stall_threshold):
                logger.info("[Heartbeat] CASE 3 stall: interim phrase + idle")
                return True

            return False

    def get_continuation_prompt(self, last_tool_result: str = "") -> str:
        """Build the continuation instructions for the LLM.

        Increments the continuation counter and starts the cooldown window.
        Clears _agent_gave_interim_response so Case 3 cannot re-fire until
        the agent speaks a new interim phrase (prevents rapid-fire when
        generate_reply resolves in ~1.5s without producing speech).

        Args:
            last_tool_result: Optional snippet of the last tool's output.
                Injected into the prompt so the LLM has result context when
                chat_ctx has been trimmed by the heartbeat's periodic trim.
                Defaults to "" (no injection) — all existing call sites are
                unaffected.
        """
        with self._lock:
            self._continuation_count += 1
            now = time.monotonic()
            self._last_continuation_at = now        # start cooldown
            self._agent_gave_interim_response = False  # disarm Case 3

            objective = self._current_objective or "the current task"
            count = self._continuation_count
            max_c = self._max_continuations
            tool_count = self._total_tool_calls_for_objective

            prompt = (
                f"CONTINUE THE TASK NOW. Do not explain or apologize — take action immediately. "
                f"The user's request was: '{objective}'. "
                f"You have made {tool_count} tool call(s) so far but the objective is NOT complete. "
                f"Pick the most relevant available tool and call it right now to make progress. "
                f"Do not give up. Do not speak until you have called a tool and received a result. "
            )
            if last_tool_result:
                prompt += f"\n\nContext from last tool: {last_tool_result[:250]}"
            prompt += f"[Internal heartbeat continuation {count}/{max_c}]"
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
