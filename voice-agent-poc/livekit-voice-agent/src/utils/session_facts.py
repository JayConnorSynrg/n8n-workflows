"""Session-level key-value store for important extracted facts.

OpenClaw-style secondary memory: captures URLs, IDs, entities, and decisions
that are important for multi-turn coherence (e.g., gammaUrl after generation).

Complements short_term_memory.py (which stores structured tool results).
Thread-safe, session-scoped, in-process store. Cleared at session end.
"""
import threading
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_facts: Dict[str, Dict[str, Any]] = {}  # session_id -> {key: {value, timestamp, metadata}}


def store_fact(session_id: str, key: str, value: str, metadata: Optional[Dict] = None) -> None:
    """Store a key-value fact for a session."""
    with _lock:
        if session_id not in _facts:
            _facts[session_id] = {}
        _facts[session_id][key] = {
            "value": value,
            "timestamp": time.monotonic(),
            "metadata": metadata or {},
        }
    val_preview = str(value)[:60] if len(str(value)) > 60 else str(value)
    logger.debug(f"[SessionFacts] Stored: {key}={val_preview}")


def get_fact(session_id: str, key: str) -> Optional[str]:
    """Get a fact value by key."""
    with _lock:
        session_data = _facts.get(session_id, {})
        entry = session_data.get(key)
        return entry["value"] if entry else None


def get_all_facts(session_id: str) -> Dict[str, str]:
    """Get all facts for a session as a simple {key: value} dict."""
    with _lock:
        session_data = _facts.get(session_id, {})
        return {k: v["value"] for k, v in session_data.items()}


def build_context_string(session_id: str) -> str:
    """Build a compact context string summarising session facts for LLM awareness."""
    facts = get_all_facts(session_id)
    if not facts:
        return ""
    lines = ["[Session context]"]
    for k, v in facts.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def clear_facts(session_id: str) -> int:
    """Clear all facts for a session. Returns count cleared."""
    with _lock:
        count = len(_facts.get(session_id, {}))
        _facts.pop(session_id, None)
    if count:
        logger.info(f"[SessionFacts] Cleared {count} facts for session {session_id}")
    return count


async def flush_facts_to_db(session_id: str, postgres_url: Optional[str]) -> None:
    """Persist all in-memory facts for a session to the session_facts_log table.

    Uses a single asyncpg connection (no pool) — this is a one-shot flush at
    session end.  Silently skips if postgres_url is not set, there are no facts,
    or any DB error occurs.  Never raises.
    """
    if not postgres_url:
        return

    facts = get_all_facts(session_id)
    if not facts:
        logger.debug(f"[SessionFacts] No facts to flush for session {session_id}")
        return

    try:
        import asyncpg  # type: ignore
        conn = await asyncpg.connect(postgres_url, command_timeout=8)
        try:
            for key, value in facts.items():
                await conn.execute(
                    """
                    INSERT INTO session_facts_log (session_id, key, value, metadata_json, created_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (session_id, key)
                    DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
                    """,
                    session_id,
                    key,
                    str(value),
                    None,
                )
            logger.info(
                f"[SessionFacts] Flushed {len(facts)} facts to DB for session {session_id}"
            )
        finally:
            await conn.close()
    except ImportError:
        logger.warning("[SessionFacts] asyncpg not installed — DB flush skipped")
    except Exception as exc:
        logger.warning(f"[SessionFacts] DB flush failed (non-critical): {exc}")
