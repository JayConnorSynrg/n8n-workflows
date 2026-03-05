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


async def init_pool(postgres_url: str) -> None:
    """Initialize asyncpg connection pool. Call once in prewarm()."""
    global _pool, _pg_available
    if _pool is not None:
        return
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
            ssl='require',
        )
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
    user_id: Optional[str] = None,
) -> None:
    """Log a single conversation turn. Fire-and-forget — errors are suppressed."""
    if not _pg_available or _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_log (session_id, role, content, tool_name, user_id)
                VALUES ($1, $2, $3, $4, $5)
                """,
                session_id,
                role,
                content[:4000],  # Cap at 4KB per turn
                tool_name,
                user_id,
            )
    except Exception as e:
        logger.debug(f"[PgLogger] Turn log failed (non-critical): {e}")


async def log_session_start(
    session_id: str,
    user_id: Optional[str] = None,
    room_name: Optional[str] = None,
) -> None:
    if not _pg_available or _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (session_id, user_id, room_name, started_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (session_id) DO NOTHING
                """,
                session_id, user_id, room_name,
            )
    except Exception as e:
        logger.debug(f"log_session_start error: {e}")


async def log_session_end(
    session_id: str,
    user_id: Optional[str] = None,
    summary: Optional[str] = None,
    message_count: int = 0,
    tool_call_count: int = 0,
) -> None:
    if not _pg_available or _pool is None:
        return
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (session_id, user_id, ended_at, summary, message_count, tool_call_count)
                VALUES ($1, $2, NOW(), $3, $4, $5)
                ON CONFLICT (session_id) DO UPDATE SET
                    ended_at = NOW(),
                    summary = EXCLUDED.summary,
                    message_count = EXCLUDED.message_count,
                    tool_call_count = EXCLUDED.tool_call_count,
                    user_id = COALESCE(sessions.user_id, EXCLUDED.user_id)
                """,
                session_id, user_id, summary, message_count, tool_call_count,
            )
    except Exception as e:
        logger.debug(f"log_session_end error: {e}")


async def log_tool_error(
    *,
    slug: str,
    resolved_slug: Optional[str] = None,
    service: Optional[str] = None,
    error_type: str,           # TIMEOUT, AUTH_401, PERMISSION_403, RATE_LIMIT, SLUG_NOT_FOUND, CB_TRIPPED, PARAM_ERROR, NETWORK, SERVER_5XX, META_TOOL, UNKNOWN
    tier_resolved: Optional[int] = None,
    retry_count: int = 0,
    cb_state: Optional[str] = None,  # OPEN, CLOSED, HALF_OPEN
    worker_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
    raw_error: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Fire-and-forget: log a structured tool error to tool_error_log table."""
    if not _pg_available or _pool is None:
        return
    try:
        async with _pool.acquire(timeout=5) as conn:
            await conn.execute(
                """
                INSERT INTO tool_error_log
                    (slug, resolved_slug, service, error_type, tier_resolved, retry_count,
                     cb_state, worker_id, duration_ms, raw_error, session_id, user_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                slug,
                resolved_slug,
                service,
                error_type,
                tier_resolved,
                retry_count,
                cb_state,
                worker_id,
                duration_ms,
                raw_error,
                session_id,
                user_id,
            )
    except Exception as e:
        logger.debug(f"[PgLogger] tool_error_log insert failed (non-critical): {e}")


async def _get_pool():
    """Return the active asyncpg pool, or None if not initialized."""
    return _pool if _pg_available else None


async def close_pool() -> None:
    """Close the connection pool. Call once on worker shutdown."""
    global _pool, _pg_available
    if _pool:
        await _pool.close()
        _pool = None
        _pg_available = False
        logger.info("[PgLogger] Connection pool closed")
