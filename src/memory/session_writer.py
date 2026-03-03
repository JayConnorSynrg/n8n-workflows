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
from datetime import datetime, timedelta, timezone
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

_AGENTS_MD_TEMPLATE = """\
# AIO Agent Behavior & Session Rules

## Memory Loading
- Every session: SOUL.md, USER.md, today's session log, yesterday's session log
- Always inject cross-session memory context (max 500 tokens) into system prompt

## Response Rules
- Always respond to direct questions and requests
- Use wake word gate (AIO/aye-yo) to filter unsolicited speech during standby
- During active tasks: respond without wake word requirement

## Proactive Work
- No mental notes — store important information using deepStore immediately
- Write facts to memory when the user says "remember", "save that", "note that"
- Confirm destructive actions (email send, contact add) before executing

## Tool Behavior
- Prefer Composio tools for standard app integrations
- Use n8n webhooks for internal data (Drive, contacts, vector DB)
- Always confirm WRITE operations with user before executing

## Communication Style
- Voice-first: responses must be spoken aloud naturally (no markdown tables in speech)
- Concise: prefer 1-2 sentences unless asked for detail
- Proactive: surface relevant context without being asked
"""

_IDENTITY_MD_TEMPLATE = """\
# AIO Voice Assistant

- **Name**: AIO (pronounced "aye-yo")
- **Type**: AI Voice Assistant
- **Wake Word**: AIO / aye-yo / eye-oh
- **Voice**: Cartesia Sonic-3
- **Platform**: LiveKit voice rooms
- **Emoji**: 🔊
- **Purpose**: Enterprise voice assistant for productivity and automation
"""

_TOOLS_MD_TEMPLATE = """\
# AIO Environment & Infrastructure

## n8n Webhooks
- Base URL: configured via N8N_WEBHOOK_BASE_URL env var
- All calls authenticated via X-AIO-Webhook-Secret header

## Active Tool Categories
- Google Drive: search, get, list documents
- Gmail: send email (confirmation required)
- Contacts: search, add, update
- Vector DB: semantic search (Pinecone)
- Composio: 400+ app integrations (dynamic)
- Gamma: AI presentation generation

## Notes
- Add environment-specific infrastructure notes here
- Device names, room names, SSH hosts, custom nicknames
"""

_HEARTBEAT_MD_TEMPLATE = """\
# AIO Periodic Tasks

## Session Monitoring
- Heartbeat loop: 4s, stall threshold 6s, max 5 continuations
- Chat context trim: every 20s idle, keeps system + last 15 messages

## Scheduled Work
<!-- Add periodic monitoring tasks here, e.g.: -->
<!-- - Check calendar every morning session -->
<!-- - Surface pending emails on session start -->
<!-- - Remind about follow-ups -->
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

    agents_md = os.path.join(memory_dir, "AGENTS.md")
    if not os.path.exists(agents_md):
        with open(agents_md, "w", encoding="utf-8") as f:
            f.write(_AGENTS_MD_TEMPLATE)
        logger.info("[SessionWriter] Created AGENTS.md at %s", agents_md)

    identity_md = os.path.join(memory_dir, "IDENTITY.md")
    if not os.path.exists(identity_md):
        with open(identity_md, "w", encoding="utf-8") as f:
            f.write(_IDENTITY_MD_TEMPLATE)
        logger.info("[SessionWriter] Created IDENTITY.md at %s", identity_md)

    tools_md = os.path.join(memory_dir, "TOOLS.md")
    if not os.path.exists(tools_md):
        with open(tools_md, "w", encoding="utf-8") as f:
            f.write(_TOOLS_MD_TEMPLATE)
        logger.info("[SessionWriter] Created TOOLS.md at %s", tools_md)

    heartbeat_md = os.path.join(memory_dir, "HEARTBEAT.md")
    if not os.path.exists(heartbeat_md):
        with open(heartbeat_md, "w", encoding="utf-8") as f:
            f.write(_HEARTBEAT_MD_TEMPLATE)
        logger.info("[SessionWriter] Created HEARTBEAT.md at %s", heartbeat_md)


# ────────────────────────────────────────────────────────────────────────────────
# Weekly session index for compact system prompt injection
# ────────────────────────────────────────────────────────────────────────────────

def _build_weekly_session_index(sessions_dir: str, days: int = 7) -> str:
    """
    Scan sessions/ directory for files from the past `days` days.
    Extract one-line descriptor per session block.
    Returns a compact string for system prompt injection, or empty string if none.

    Session file format (written by write_session_log):
        ## Session — HH:MM UTC
        Voice session. Tools: N calls (Category1, Category2).
        ...
    """
    now = datetime.now(timezone.utc)
    entries: list[tuple[str, Optional[str]]] = []

    try:
        if not os.path.isdir(sessions_dir):
            return ""

        # Collect files from the past `days` days
        for offset in range(days):
            day = now - timedelta(days=offset)
            date_str = day.strftime("%Y-%m-%d")
            log_path = os.path.join(sessions_dir, f"{date_str}.md")
            if not os.path.exists(log_path):
                continue

            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                continue

            # Extract all session blocks from this file
            for line in content.splitlines():
                if line.startswith("## Session — "):
                    # Parse time from "## Session — HH:MM UTC"
                    time_part = line.replace("## Session — ", "").replace(" UTC", "").strip()
                    # Format as "Feb 28 14:32"
                    try:
                        label = day.strftime("%b %-d") + " " + time_part
                    except ValueError:
                        label = date_str + " " + time_part
                    entries.append((label, None))  # placeholder for descriptor
                elif entries and entries[-1][1] is None and line.strip():
                    # First non-blank line after a session header = descriptor
                    descriptor = line.strip()
                    # Cap at 80 chars
                    if len(descriptor) > 80:
                        descriptor = descriptor[:77] + "..."
                    entries[-1] = (entries[-1][0], descriptor)

    except Exception as exc:
        logger.warning("[SessionWriter] Failed to build session index: %s", exc)
        return ""

    # Filter out any entries without a descriptor
    valid = [(label, desc) for label, desc in entries if desc]
    if not valid:
        return ""

    lines = ["## Recent Sessions (say 'recall session' for full details)"]
    for label, desc in valid:
        lines.append(f"- {label} — {desc}")

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────────────────
# Context loading for system prompt injection
# ────────────────────────────────────────────────────────────────────────────────

def load_memory_context(memory_dir: str, max_tokens: int = 500) -> str:
    """
    Load SOUL.md, MEMORY.md, and USER.md and return a formatted string for
    system prompt injection.
    Content is capped at approximately max_tokens (estimated at 4 chars per token).

    Returns empty string if files don't exist or are empty.

    Session logs NOT auto-loaded — use recall() tool for cross-session search.
    Full session logs available in sessions/YYYY-MM-DD.md but loaded on-demand only.
    Reason: session log files are append-only per day and grow unboundedly;
    captured_facts are already persisted to MEMORY.md and SQLite via flush_session().
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

    # Append compact weekly session index (lightweight — titles only)
    sessions_dir = os.path.join(memory_dir, "sessions")
    session_index = _build_weekly_session_index(sessions_dir)
    if session_index:
        parts.append(session_index)

    combined = "\n\n".join(parts) if parts else ""

    if not combined:
        return ""

    if len(combined) > max_chars:
        combined = combined[:max_chars] + "\n\n[Memory truncated — full content in /app/data/memory/]"

    return combined


def _is_template_only(content: str) -> bool:
    """Return True if the file only contains the starter template (no real data)."""
    _PLACEHOLDERS = frozenset([
        "(not yet learned)",
        "Add preferences as they are learned",
        "Persistent facts about projects",
        "Important decisions made",
        "Projects, roles, organizations",
        "How the user prefers to communicate",
        "What the user is currently focused on",
        "How AIO has learned to communicate",
        "Recurring workflows and processes",
        "Background knowledge that helps AIO",
        "Add environment-specific infrastructure notes here",
        "Add periodic monitoring tasks here",
        "Device names, room names, SSH hosts",
        "Check calendar every morning session",
        "Surface pending emails on session start",
        "Remind about follow-ups",
    ])
    real_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        if any(ph in stripped for ph in _PLACEHOLDERS):
            continue
        real_lines.append(stripped)
    return len(real_lines) == 0


# ────────────────────────────────────────────────────────────────────────────────
# MEMORY.md write-back (auto-append captured facts)
# ────────────────────────────────────────────────────────────────────────────────

def _append_to_memory_md(memory_dir: str, facts: list[str]) -> None:
    """
    Append auto-captured session facts to MEMORY.md.
    Always appends — never truncates or overwrites existing content.

    Args:
        memory_dir: Path to user memory directory (contains MEMORY.md)
        facts: Non-empty list of fact strings to persist
    """
    memory_md = os.path.join(memory_dir, "MEMORY.md")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    lines = [f"\n## [{timestamp}]"]
    for fact in facts:
        lines.append(f"- {fact}")
    lines.append("")  # trailing newline

    try:
        with open(memory_md, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        logger.info("[SessionWriter] Appended %d facts to MEMORY.md", len(facts))
    except Exception as exc:
        logger.error("[SessionWriter] Failed to append to MEMORY.md: %s", exc)


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

    Writes:
    1. Session log entry to sessions/YYYY-MM-DD.md (always)
    2. Captured facts appended to MEMORY.md (only when captured_facts is non-empty)
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        write_session_log,
        memory_dir,
        tool_summary,
        captured_facts,
    )
    # Write-back: persist captured facts to MEMORY.md for cross-session recall
    if captured_facts:
        await loop.run_in_executor(
            None,
            _append_to_memory_md,
            memory_dir,
            captured_facts,
        )
