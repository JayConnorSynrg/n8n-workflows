"""
AIO Voice System — Auto-Capture

Detects memory-worthy facts from user utterances during voice sessions.
Triggered from on_conversation_item_added event in agent.py.

Captured facts are queued in-session and flushed to memory_store on disconnect.
Thread-safe: capture queue is append-only, flushed once at session end.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────────
# Trigger patterns
# ────────────────────────────────────────────────────────────────────────────────

# English patterns that signal a memory-worthy statement
_MEMORY_TRIGGERS = re.compile(
    r"\b("
    r"remember\s+(this|that)|"
    r"I\s+prefer|"
    r"I\s+always|"
    r"I\s+never|"
    r"important(?:\s*:|,)|"
    r"note(?:\s*:|,)|"
    r"my\s+\w+\s+is\s+|"
    r"I'?m\s+using\s+|"
    r"I\s+use\s+|"
    r"I\s+work\s+(at|for)|"
    r"don'?t\s+forget|"
    r"keep\s+in\s+mind|"
    r"for\s+future\s+reference"
    r")\b",
    re.IGNORECASE,
)

# Minimum length for a captured fact to be worth storing
_MIN_FACT_LENGTH = 15
# Maximum length before we truncate (characters)
_MAX_FACT_LENGTH = 500


# ────────────────────────────────────────────────────────────────────────────────
# Session-scoped capture queue
# ────────────────────────────────────────────────────────────────────────────────

# Module-level list — reset each session via reset_session()
_pending_facts: list[tuple[str, str]] = []  # (text, category)


def reset_session() -> None:
    """Clear the pending facts queue. Call at session start."""
    global _pending_facts
    _pending_facts = []


def get_pending_facts() -> list[tuple[str, str]]:
    """Return a copy of pending facts. Safe to call from any thread."""
    return list(_pending_facts)


# ────────────────────────────────────────────────────────────────────────────────
# Detection
# ────────────────────────────────────────────────────────────────────────────────

def detect_and_queue(text: str, category: str = "general") -> Optional[str]:
    """
    Check user utterance for memory trigger patterns. If found, queue for storage.

    Args:
        text: The user utterance text
        category: Memory category (default: 'general')

    Returns:
        The queued fact text if captured, None otherwise
    """
    if not text or len(text) < _MIN_FACT_LENGTH:
        return None

    if not _MEMORY_TRIGGERS.search(text):
        return None

    # Truncate if too long
    fact = text[:_MAX_FACT_LENGTH].strip()
    if len(text) > _MAX_FACT_LENGTH:
        fact += "…"

    _pending_facts.append((fact, category))
    logger.debug("[Capture] Queued fact: [%s] %.60s...", category, fact)
    return fact


async def flush_to_store(memory_store_module) -> list[str]:
    """
    Flush all pending facts to the memory store.

    Args:
        memory_store_module: The memory_store module (passed to avoid circular imports)

    Returns:
        List of fact texts that were successfully stored
    """
    if not _pending_facts:
        return []

    stored: list[str] = []
    for fact_text, cat in _pending_facts:
        result = memory_store_module.store(fact_text, category=cat, source="auto")
        if result:
            stored.append(fact_text)
            logger.info("[Capture] Stored fact: [%s] %.60s...", cat, fact_text)

    reset_session()
    return stored
