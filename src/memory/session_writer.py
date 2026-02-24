"""
AIO Voice System — Session Writer

Responsibilities:
1. Create MEMORY.md and USER.md with starter templates if they don't exist.
2. Load MEMORY.md and USER.md content for injection into system prompt.
3. Write a session log entry to memory/sessions/YYYY-MM-DD.md on disconnect.
4. Flush auto-captured facts from a session into the SQLite memory store.

All I/O operations are synchronous file operations.
All async entry points are thin wrappers that run sync ops in executor.
Designed to be called with a timeout — failures must not block agent disconnect.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────────
# Templates for first-run initialization
# ────────────────────────────────────────────────────────────────────────────────

_MEMORY_MD_TEMPLATE = """\
# MEMORY.md — AIO Voice System Long-Term Memory

This file contains facts, preferences, and decisions that persist across voice sessions.
AIO reads this file at the start of every session.

## User Preferences
<!-- Add preferences as they are learned, e.g.:
- Prefers concise summaries under 3 bullet points
- Uses formal tone for external emails
-->

## Key Facts
<!-- Persistent facts about projects, people, and context -->

## Decisions
<!-- Important decisions made with AIO's assistance -->
"""

_USER_MD_TEMPLATE = """\
# USER.md — User Profile

AIO learns about the user over time. This file is read at every session start.

## Identity
- Name: (not yet learned)
- Preferred address: (not yet learned)
- Timezone: (not yet learned)

## Work Context
<!-- Projects, roles, organizations the user works with -->

## Communication Style
<!-- How the user prefers to communicate, email tone, etc. -->

## Ongoing Priorities
<!-- What the user is currently focused on -->
"""

_SOUL_MD_TEMPLATE = """\
# SOUL.md — AIO Agent Identity

This file captures how AIO has learned to best serve this user over time.
AIO updates this through conversations. Edit directly to adjust agent behavior.

## Communication Adaptations
<!-- How AIO has learned to communicate with this user -->

## Working Patterns
<!-- Recurring workflows and processes this user follows -->

## Trusted Context
<!-- Background knowledge that helps AIO be more useful -->
"""


# ────────────────────────────────────────────────────────────────────────────────
# Initialization
# ────────────────────────────────────────────────────────────────────────────────

def ensure_memory_files(memory_dir: str) -> None:
    """
    Create MEMORY.md and USER.md with starter templates if they don't exist.
    Also ensures the sessions/ subdirectory exists.
    Safe to call multiple times.
    """
    os.makedirs(memory_dir, exist_ok=True)
    os.makedirs(os.path.join(memory_dir, "sessions"), exist_ok=True)
    print(f"[Memory] Session writer ready at {memory_dir}", flush=True)

    memory_md = os.path.join(memory_dir, "MEMORY.md")
    if not os.path.exists(memory_md):
        with open(memory_md, "w", encoding="utf-8") as f:
            f.write(_MEMORY_MD_TEMPLATE)
        logger.info("[SessionWriter] Created MEMORY.md at %s", memory_md)

    user_md = os.path.join(memory_dir, "USER.md")
    if not os.path.exists(user_md):
        with open(user_md, "w", encoding="utf-8") as f:
            f.write(_USER_MD_TEMPLATE)
        logger.info("[SessionWriter] Created USER.md at %s", user_md)

    soul_md = os.path.join(memory_dir, "SOUL.md")
    if not os.path.exists(soul_md):
        with open(soul_md, "w", encoding="utf-8") as f:
            f.write(_SOUL_MD_TEMPLATE)
        logger.info("[SessionWriter] Created SOUL.md at %s", soul_md)


# ────────────────────────────────────────────────────────────────────────────────
# Context loading for system prompt injection
# ────────────────────────────────────────────────────────────────────────────────

def load_memory_context(memory_dir: str, max_tokens: int = 500) -> str:
    """
    Load MEMORY.md and USER.md and return a formatted string for system prompt injection.
    Content is capped at approximately max_tokens (estimated at 4 chars per token).

    Returns empty string if files don't exist or are empty.
    """
    max_chars = max_tokens * 4  # rough estimate
    parts: list[str] = []

    for filename, label in [
        ("SOUL.md", "Agent Identity"),
        ("MEMORY.md", "Long-Term Memory"),
        ("USER.md", "User Profile"),
    ]:
        filepath = os.path.join(memory_dir, filename)
        try:
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content and not _is_template_only(content):
                    parts.append(f"### {label}\n{content}")
        except Exception as exc:
            logger.warning("[SessionWriter] Failed to load %s: %s", filename, exc)

    if not parts:
        return ""

    combined = "\n\n".join(parts)
    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n[Memory truncated — full content in /app/data/memory/]"

    return combined


def _is_template_only(content: str) -> bool:
    """Return True if the file only contains the starter template (no real data)."""
    # Heuristic: if all non-empty non-comment lines start with # or <!-- it's template-only
    real_lines = [
        line for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("<!--")
    ]
    return len(real_lines) == 0


# ────────────────────────────────────────────────────────────────────────────────
# Session log writing
# ────────────────────────────────────────────────────────────────────────────────

def write_session_log(
    memory_dir: str,
    session_summary: str,
    captured_facts: Optional[list[str]] = None,
) -> None:
    """
    Append a session summary entry to today's session log file.

    Args:
        memory_dir: Path to memory directory
        session_summary: Brief summary of what happened this session
        captured_facts: List of facts auto-captured during the session
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = os.path.join(memory_dir, "sessions", f"{today}.md")
    timestamp = datetime.now(timezone.utc).strftime("%H:%M UTC")

    lines = [f"\n## Session — {timestamp}\n", session_summary.strip()]

    if captured_facts:
        lines.append("\n**Captured facts:**")
        for fact in captured_facts:
            lines.append(f"- {fact}")

    lines.append("")  # trailing newline

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        logger.info("[SessionWriter] Session log written to %s", log_path)
    except Exception as exc:
        logger.error("[SessionWriter] Failed to write session log: %s", exc)


# ────────────────────────────────────────────────────────────────────────────────
# Async entry point (called from agent.py on disconnect)
# ────────────────────────────────────────────────────────────────────────────────

async def flush_session(
    memory_dir: str,
    tool_summary: str,
    captured_facts: Optional[list[str]] = None,
) -> None:
    """
    Async entry point for session end. Runs synchronous file I/O in executor.
    Designed to be called with asyncio.wait_for(..., timeout=8.0).
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        write_session_log,
        memory_dir,
        tool_summary,
        captured_facts,
    )


# ────────────────────────────────────────────────────────────────────────────────
# LLM Synthesis — OpenClaw write-back
# Synthesizes session transcript into USER.md, SOUL.md, MEMORY.md updates.
# Called at session end with a 25s timeout — failures never block disconnect.
# ────────────────────────────────────────────────────────────────────────────────

async def _call_fireworks(
    prompt: str,
    api_key: str,
    model: str,
    max_tokens: int = 350,
) -> Optional[str]:
    """Direct Fireworks chat completion for memory synthesis. Returns text or None."""
    try:
        import httpx
        url = "https://api.fireworks.ai/inference/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        logger.warning("[Memory] Fireworks synthesis call failed: %s", exc)
        return None


def _append_dated_block(file_path: str, content: str) -> None:
    """Append a dated markdown block to a file."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    block = f"\n\n---\n*Updated {today}*\n\n{content}\n"
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(block)
        logger.info("[Memory] Wrote synthesis to %s", os.path.basename(file_path))
    except Exception as exc:
        logger.error("[Memory] Failed to write %s: %s", file_path, exc)


def _read_file_safe(file_path: str, max_chars: int = 1500) -> str:
    """Read file content capped at max_chars. Returns empty string on failure."""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()[:max_chars]
    except Exception:
        pass
    return ""


def _format_transcript(transcript: list, max_turns: int = 40, max_chars_per_turn: int = 300) -> str:
    """Format session transcript list for LLM prompt. Caps at max_turns."""
    turns = transcript[-max_turns:]
    lines = []
    for t in turns:
        role = "User" if t.get("role") == "user" else "AIO"
        content = (t.get("content") or "")[:max_chars_per_turn]
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def synthesize_and_update(
    memory_dir: str,
    transcript: list,
    api_key: str,
    model: str,
) -> dict:
    """
    OpenClaw write-back: run LLM synthesis on session transcript and update memory files.

    USER.md  — new facts/preferences inferred from conversation
    SOUL.md  — agent self-reflection on how to better serve this user
    MEMORY.md — episodic summary of the session

    Returns dict of {filename: was_updated}.
    Designed for asyncio.wait_for(timeout=25.0). All errors are swallowed.
    """
    results = {"USER.md": False, "SOUL.md": False, "MEMORY.md": False}

    if not api_key or len(transcript) < 4:
        logger.info(
            "[Memory] Synthesis skipped — api_key=%s turns=%d",
            bool(api_key), len(transcript),
        )
        return results

    transcript_str = _format_transcript(transcript)

    user_md_path = os.path.join(memory_dir, "USER.md")
    soul_md_path = os.path.join(memory_dir, "SOUL.md")
    memory_md_path = os.path.join(memory_dir, "MEMORY.md")

    current_user = _read_file_safe(user_md_path)
    current_soul = _read_file_safe(soul_md_path)

    user_prompt = (
        "You are updating a voice assistant\'s persistent user profile.\n\n"
        f"Current USER.md:\n{current_user}\n\n"
        f"Session transcript:\n{transcript_str}\n\n"
        "Based ONLY on this session, write any NEW facts about the user not already "
        "captured above.\n"
        "Focus on: preferences, work context, communication style, current priorities.\n"
        "Write as concise markdown bullet points (no section headers needed).\n"
        "If nothing new was learned, respond exactly: NO_UPDATE"
    )

    soul_prompt = (
        "You are an AI voice assistant reflecting on a completed session to improve "
        "future interactions with this specific user.\n\n"
        f"Current SOUL.md:\n{current_soul}\n\n"
        f"Session transcript:\n{transcript_str}\n\n"
        "Write any NEW observations about how to better communicate with or assist "
        "this user.\n"
        "Focus on: what worked well, communication patterns, working style, things "
        "to remember next time.\n"
        "Write as concise markdown bullet points (no section headers needed).\n"
        "If nothing new was learned, respond exactly: NO_UPDATE"
    )

    memory_prompt = (
        "Write a 2-3 sentence episodic memory entry for a voice assistant session.\n"
        "Focus on: what was discussed, decisions made, tasks completed, outcomes.\n"
        "Be specific and concrete. Avoid filler phrases like \'the user asked about\'.\n\n"
        f"Session transcript:\n{transcript_str}"
    )

    # Run all three synthesis calls in parallel
    user_result, soul_result, memory_result = await asyncio.gather(
        _call_fireworks(user_prompt, api_key, model),
        _call_fireworks(soul_prompt, api_key, model),
        _call_fireworks(memory_prompt, api_key, model, max_tokens=200),
        return_exceptions=True,
    )

    # Write USER.md
    if isinstance(user_result, str) and user_result and user_result.strip().upper() != "NO_UPDATE":
        _append_dated_block(user_md_path, user_result)
        results["USER.md"] = True

    # Write SOUL.md
    if isinstance(soul_result, str) and soul_result and soul_result.strip().upper() != "NO_UPDATE":
        _append_dated_block(soul_md_path, soul_result)
        results["SOUL.md"] = True

    # Write MEMORY.md — episodic entry with timestamp header
    if isinstance(memory_result, str) and memory_result:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        entry = f"\n\n## {ts}\n{memory_result}\n"
        try:
            with open(memory_md_path, "a", encoding="utf-8") as f:
                f.write(entry)
            results["MEMORY.md"] = True
            logger.info("[Memory] Episodic entry written to MEMORY.md")
        except Exception as exc:
            logger.error("[Memory] Failed to write MEMORY.md: %s", exc)

    written = [k for k, v in results.items() if v]
    logger.info("[Memory] Synthesis complete — updated: %s", written or "none")
    return results
