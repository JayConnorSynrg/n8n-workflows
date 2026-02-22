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

    for filename, label in [("MEMORY.md", "Long-Term Memory"), ("USER.md", "User Profile")]:
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
