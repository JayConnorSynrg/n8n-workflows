"""Async PostgreSQL conversation logger for full session context storage.

Logs all conversation turns (user + assistant + tool) to the conversation_log
table. Uses asyncpg for non-blocking writes, gracefully disabled if POSTGRES_URL
is not configured.

Load assessment:
- ~150 rows per 30-min session (50 turns × 3 roles avg)
- ~5 sessions/day → ~750 rows/day
- PostgreSQL handles 10,000s writes/sec — this load is trivially manageable
- Recommended retention: 90 days (see migration SQL comment)
- Existing Railway PostgreSQL (NI3jbq1U8xPst3j3) is sufficient; no alternative needed
"""
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_pool = None
_pg_available = False

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS conversation_log (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT        NOT NULL,
    role        TEXT        NOT NULL CHECK (role IN ('user', 'assistant', 'tool', 'system')),
    content     TEXT        NOT NULL,
    tool_name   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conv_log_session ON conversation_log(session_id);
CREATE INDEX IF NOT EXISTS idx_conv_log_created ON conversation_log(created_at DESC);
"""


async def init_pool(postgres_url: str) -> None:
    """Initialize asyncpg connection pool and ensure conversation_log table exists."""
    global _pool, _pg_available
    if not postgres_url:
        logger.info("[PgLogger] POSTGRES_URL not set — conversation logging disabled")
        return
    try:
        import asyncpg  # type: ignore
        _pool = await asyncpg.create_pool(
            postgres_url,
            min_size=1,
            max_size=3,
            command_timeout=5,
        )
        # Auto-create conversation_log if it doesn't exist (idempotent)
        async with _pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE_SQL)
        _pg_available = True
        logger.info("[PgLogger] Connection pool initialized — conversation logging active")
    except ImportError:
        logger.warning("[PgLogger] asyncpg not installed — conversation logging disabled")
    except Exception as e:
        logger.warning(f"[PgLogger] Pool init failed: {e} — conversation logging disabled")


async def log_turn(
    session_id: str,
    role: str,
    content: str,
    tool_name: Optional[str] = None,
) -> None:
    """Log a single conversation turn. Fire-and-forget — errors are suppressed."""
    if not _pg_available or _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_log (session_id, role, content, tool_name)
                VALUES ($1, $2, $3, $4)
                """,
                session_id,
                role,
                content[:4000],  # Cap at 4KB per turn
                tool_name,
            )
    except Exception as e:
        logger.debug(f"[PgLogger] Turn log failed (non-critical): {e}")


async def read_session_history(
    session_id: str,
    limit: int = 50,
) -> list:
    """Read conversation turns for a session directly from conversation_log.

    Returns empty list if pool unavailable or session has no logged turns.
    Primary read path for checkContext — bypasses n8n webhook entirely.
    """
    if not _pg_available or _pool is None:
        return []
    try:
        async with _pool.acquire() as conn:
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
            return [dict(row) for row in rows]
    except Exception as e:
        logger.debug(f"[PgLogger] read_session_history failed: {e}")
        return []


async def save_session_summary(session_id: str, summary: str) -> None:
    """Save a session-level summary to conversation_log at session end.

    Written as a 'system' role entry with tool_name='session_summary'.
    Enables fast recall of what happened in a session without scanning all turns.
    """
    if not _pg_available or _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_log (session_id, role, content, tool_name)
                VALUES ($1, 'system', $2, 'session_summary')
                """,
                session_id,
                summary[:4000],
            )
        logger.info("[PgLogger] Session summary saved for %s", session_id)
    except Exception as e:
        logger.debug(f"[PgLogger] save_session_summary failed (non-critical): {e}")


async def close_pool() -> None:
    """Close the connection pool. Call once on worker shutdown."""
    global _pool, _pg_available
    if _pool:
        await _pool.close()
        _pool = None
        _pg_available = False
        logger.info("[PgLogger] Connection pool closed")
