"""PostgreSQL-backed secondary memory: session fact persistence + context retrieval.

Secondary memory layer that persists structured facts (URLs, decisions, topics)
from session_facts.py to PostgreSQL for durability across sessions and restarts.

Architecture:
  PRIMARY:    memory_store.py   — SQLite, full-text memories with vector search
  SECONDARY:  pg_session_store  — PostgreSQL, structured facts + conversation log
  IN-SESSION: session_facts.py  — volatile in-memory, flushed here at session end

Key operations:
  save_session_facts()   — persist volatile facts to PG at session END
  load_user_context()    — retrieve prior facts for chat_ctx injection at session START
  search_prior_sessions()  — agent-callable FTS over conversation_log

Requires:
  - pg_logger.init_pool() called first (shares the same asyncpg pool)
  - session_facts_log table created via session_facts_log_migration.sql
"""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Module-level user ID — set by agent.py at session start so the recallSession
# tool can query the right user's data without needing session context passed in.
_current_user_id: str = "_default"


def set_current_user_id(user_id: str) -> None:
    """Register the current session's user ID. Called by agent.py at session start."""
    global _current_user_id
    _current_user_id = user_id
    logger.debug(f"[PgStore] Current user_id set: {user_id[:20]}")


def get_current_user_id() -> str:
    """Return the current session's user ID."""
    return _current_user_id


def _get_pool():
    """Lazy-import the shared asyncpg pool from pg_logger."""
    try:
        from . import pg_logger as _pg
        return _pg._pool
    except Exception:
        return None


# ── Keys to exclude from cross-session context injection ─────────────────────
# These are volatile / low signal outside the session they were captured in.
_EXCLUDE_FROM_CROSS_SESSION = frozenset({
    "last_tool_called",
    "last_tool_output",
    "gamma_generation_started",
    "gamma_generation_output",
})


# =============================================================================
# WRITE PATH — called at session end
# =============================================================================

async def save_session_facts(
    session_id: str,
    user_id: str,
    facts: Dict[str, str],
) -> int:
    """Persist session facts dict to session_facts_log.

    Called at session end, before session_facts.clear_facts().
    Errors are suppressed — this must never block session cleanup.
    Returns count of rows inserted.
    """
    pool = _get_pool()
    if not pool or not facts:
        return 0

    rows = [(session_id, user_id, k, v[:2000]) for k, v in facts.items()]
    try:
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO session_facts_log (session_id, user_id, key, value)
                VALUES ($1, $2, $3, $4)
                """,
                rows,
            )
        logger.info(f"[PgStore] Saved {len(rows)} facts (session={session_id[:12]} user={user_id[:12]})")
        return len(rows)
    except Exception as e:
        logger.warning(f"[PgStore] save_session_facts failed (non-critical): {e}")
        return 0


# =============================================================================
# READ PATH — called at session start and by tools
# =============================================================================

async def load_user_context(user_id: str, max_facts: int = 30) -> Dict[str, str]:
    """Load the most recent value per fact key across all prior sessions for a user.

    Uses DISTINCT ON to deduplicate — only the latest value per key is returned.
    Called at session start; result is injected into chat_ctx.
    Returns {} if no prior facts exist or pool is unavailable.
    """
    pool = _get_pool()
    if not pool:
        return {}

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (key) key, value
                FROM session_facts_log
                WHERE user_id = $1
                ORDER BY key, created_at DESC
                LIMIT $2
                """,
                user_id,
                max_facts,
            )
        result = {r["key"]: r["value"] for r in rows}
        if result:
            logger.info(f"[PgStore] Loaded {len(result)} prior facts for user={user_id[:12]}")
        return result
    except Exception as e:
        logger.warning(f"[PgStore] load_user_context failed (non-critical): {e}")
        return {}


async def search_prior_sessions(
    user_id: str,
    query: str,
    limit: int = 6,
) -> List[Dict]:
    """Full-text search (ILIKE) over conversation_log for a user's sessions.

    Restricts to sessions that have session_facts_log entries for this user.
    Falls back to searching all conversation_log if no user sessions are indexed yet.
    Returns list of {session_id, role, content, tool_name, created_at} dicts.
    """
    pool = _get_pool()
    if not pool or not query.strip():
        return []

    try:
        async with pool.acquire() as conn:
            # Discover this user's session IDs from fact log
            user_session_rows = await conn.fetch(
                "SELECT DISTINCT session_id FROM session_facts_log WHERE user_id = $1",
                user_id,
            )
            user_session_ids = [r["session_id"] for r in user_session_rows]

            if user_session_ids:
                rows = await conn.fetch(
                    """
                    SELECT session_id, role, content, tool_name, created_at
                    FROM conversation_log
                    WHERE content ILIKE $1
                      AND session_id = ANY($2::text[])
                    ORDER BY created_at DESC
                    LIMIT $3
                    """,
                    f"%{query.strip()}%",
                    user_session_ids,
                    limit,
                )
            else:
                # No indexed sessions yet — search globally (first deployment)
                rows = await conn.fetch(
                    """
                    SELECT session_id, role, content, tool_name, created_at
                    FROM conversation_log
                    WHERE content ILIKE $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    f"%{query.strip()}%",
                    limit,
                )
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"[PgStore] search_prior_sessions failed (non-critical): {e}")
        return []


async def get_recent_turns(
    session_id: str,
    limit: int = 20,
) -> List[Dict]:
    """Retrieve the most recent N turns for a specific session from conversation_log."""
    pool = _get_pool()
    if not pool:
        return []

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content, tool_name, created_at
                FROM conversation_log
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                session_id,
                limit,
            )
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"[PgStore] get_recent_turns failed (non-critical): {e}")
        return []


# =============================================================================
# FORMATTING
# =============================================================================

def build_context_injection(facts: Dict[str, str]) -> str:
    """Build a compact context block suitable for chat_ctx injection.

    Filters out volatile/low-signal keys (last_tool_*, gamma_generation_*)
    and formats the remainder as a structured note the LLM can reference
    without reading aloud.

    Returns empty string if no useful facts remain after filtering.
    """
    useful_facts = {
        k: v for k, v in facts.items()
        if k not in _EXCLUDE_FROM_CROSS_SESSION
    }
    if not useful_facts:
        return ""

    lines = ["[Prior session facts — do not read aloud, use for context only]"]
    for k, v in sorted(useful_facts.items()):
        v_display = v[:200] + "…" if len(v) > 200 else v
        lines.append(f"  {k}: {v_display}")
    return "\n".join(lines)


def format_search_results(results: List[Dict]) -> str:
    """Format search results for agent tool return value."""
    if not results:
        return "No matching prior session content found."

    lines = [f"Found {len(results)} matching excerpt(s) from prior sessions:\n"]
    for i, r in enumerate(results, 1):
        role = r.get("role", "unknown")
        content = str(r.get("content", ""))[:300]
        session = str(r.get("session_id", ""))[:20]
        ts = r.get("created_at", "")
        ts_str = str(ts)[:19] if ts else "unknown time"
        lines.append(f"{i}. [{role}] ({ts_str}) session={session}\n   {content}")

    return "\n".join(lines)
