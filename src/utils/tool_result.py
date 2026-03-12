"""AIO Voice Agent — ToolResult dataclass and unified announcement interface.

Centralises tool execution result announcement so that all call paths
(evaluate_and_execute_from_speech, run_background_delegation,
_gamma_notification_monitor) share identical suppression logic and error
handling.

Sentinel strings must stay in sync with:
  - composio_router._CB_TRIPPED_PREFIX  ("CB_TRIPPED:")
  - composio_router._extract_voice_result Gamma branch ("Gamma presentation ready:")
  - tool_executor._NO_TOOL_SENTINEL ("NO_ACTION")
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Sentinels (must match composio_router and tool_executor) ──────────────────
_GAMMA_RESULT_PREFIX = "Gamma presentation ready:"
_CB_TRIPPED_PREFIX_CHECK = "CB_TRIPPED:"
_NO_TOOL_SENTINEL = "NO_ACTION"


@dataclasses.dataclass(frozen=True, slots=True)
class ToolResult:
    """Immutable result token produced by the tool executor.

    Attributes:
        tool_name: Identifier for logging (e.g. "speech_eval", "bg_delegation").
        result: The raw string result from the tool executor.
        announce_via_llm: If False, skip all announcement (caller handles it).
        suppress_if_gamma: If True, suppress announcement when result is a Gamma URL.
            Set to False when the caller IS the gamma monitor.
        custom_instructions: If set, use these instructions verbatim instead of
            the default result-based instruction template.
        is_timeout: If True, use the timeout apology template.
        is_error: If True, use the error apology template.
    """

    tool_name: str
    result: str
    announce_via_llm: bool = True
    suppress_if_gamma: bool = True
    custom_instructions: str | None = None
    is_timeout: bool = False
    is_error: bool = False


async def announce_tool_result(
    session: Any,
    tool_result: ToolResult,
    *,
    session_id: str = "",
) -> None:
    """Announce a tool execution result via the LiveKit AgentSession.

    Applies all suppression checks in a fixed order, then calls
    session.generate_reply(). Silently swallows exceptions so a failed
    announcement never crashes the caller.

    Suppression order:
      1. announce_via_llm=False — caller explicitly opted out
      2. CB_TRIPPED prefix — conversation LLM handles auth errors
      3. Gamma prefix (when suppress_if_gamma=True) — monitor owns it
      4. NO_ACTION / empty — purely conversational turn

    Args:
        session: LiveKit AgentSession instance. If None, silently skips.
        tool_result: The immutable ToolResult token to announce.
        session_id: Used only for log context.
    """
    if session is None:
        logger.debug(f"[announce] no session — skip announce session_id={session_id}")
        return

    if not tool_result.announce_via_llm:
        logger.debug(f"[announce] announce_via_llm=False — skip session_id={session_id}")
        return

    result = tool_result.result

    # CB_TRIPPED — conversation LLM handles auth errors naturally
    if result.startswith(_CB_TRIPPED_PREFIX_CHECK):
        logger.debug(
            f"[announce] CB_TRIPPED suppressed — conversation LLM handles session_id={session_id}"
        )
        return

    # Gamma — _gamma_notification_monitor owns announcement
    if tool_result.suppress_if_gamma and result.startswith(_GAMMA_RESULT_PREFIX):
        logger.debug(
            f"[announce] Gamma result suppressed — monitor owns session_id={session_id}"
        )
        return

    # NO_ACTION / empty — purely conversational, no tool ran
    if not result or result.strip() == _NO_TOOL_SENTINEL:
        logger.debug(f"[announce] NO_ACTION — skip session_id={session_id}")
        return

    # Build announcement instructions
    if tool_result.custom_instructions:
        instructions = tool_result.custom_instructions
    elif tool_result.is_timeout:
        instructions = (
            "A background tool operation timed out. Apologize briefly and offer to retry."
        )
    elif tool_result.is_error:
        instructions = (
            "A background tool operation encountered an error. Apologize briefly and offer to retry."
        )
    else:
        instructions = (
            f"Tool execution completed. Result: {result[:500]}. "
            "Announce this conversationally and concisely to the user. "
            "Do NOT repeat any prior response — only announce the new result."
        )

    try:
        await session.generate_reply(instructions=instructions)
    except Exception as err:
        logger.warning(
            f"[announce] generate_reply failed tool={tool_result.tool_name} session_id={session_id}: {err}"
        )
