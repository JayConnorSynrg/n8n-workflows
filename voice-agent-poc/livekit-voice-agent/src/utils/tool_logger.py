"""
Fire-and-forget tool call logging to PostgreSQL.

Zero latency impact: all writes are asyncio.create_task() — never awaited.
Reuses the asyncpg pool from pg_logger; does NOT create a second connection pool.

Tables written:
  composio_tool_log  — every Composio + native tool call
  perplexity_searches — Perplexity calls with richer structured data
"""
import asyncio
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_pool():
    """Return the shared asyncpg pool from pg_logger, or None if unavailable.

    Imported lazily to avoid circular imports at module load time.
    pg_logger._pool is None until init_pool() has been called (prewarm phase),
    so this will silently no-op before the pool is ready.
    """
    try:
        from src.utils.pg_logger import _pool, _pg_available  # type: ignore[import]
        return _pool if _pg_available else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Internal async writers — called only via asyncio.create_task()
# ---------------------------------------------------------------------------

async def _write_composio_log(
    user_id: Optional[str],
    source: str,
    slug: str,
    arguments: Optional[dict],
    result_data: Any,
    voice_result: Optional[str],
    success: bool,
    error_message: Optional[str],
    duration_ms: int,
) -> None:
    pool = _get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO composio_tool_log
                    (user_id, source, slug, arguments, result_data, voice_result,
                     success, error_message, duration_ms)
                VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6, $7, $8, $9)
                """,
                user_id,
                source,
                slug,
                json.dumps(arguments) if arguments is not None else None,
                json.dumps(result_data) if result_data is not None else None,
                voice_result[:2000] if voice_result else None,
                success,
                error_message[:1000] if error_message else None,
                duration_ms,
            )
    except Exception as exc:
        logger.debug("[tool_logger] composio_tool_log write failed: %s", exc)


async def _write_perplexity_log(
    user_id: Optional[str],
    query: str,
    model: str,
    response_content: Optional[str],
    search_results: Any,
    usage: Any,
    duration_ms: int,
    success: bool,
    error_message: Optional[str],
) -> None:
    pool = _get_pool()
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO perplexity_searches
                    (user_id, query, model, response_content, search_results, usage,
                     duration_ms, success, error_message)
                VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7, $8, $9)
                """,
                user_id,
                query[:2000] if query else "",
                model,
                response_content[:8000] if response_content else None,
                json.dumps(search_results) if search_results is not None else None,
                json.dumps(usage) if usage is not None else None,
                duration_ms,
                success,
                error_message[:1000] if error_message else None,
            )
    except Exception as exc:
        logger.debug("[tool_logger] perplexity_searches write failed: %s", exc)


# ---------------------------------------------------------------------------
# Public fire-and-forget API
# ---------------------------------------------------------------------------

def log_composio_call(
    user_id: Optional[str],
    slug: str,
    arguments: Optional[dict],
    result_data: Any,
    voice_result: str,
    success: bool,
    error_message: Optional[str],
    duration_ms: int,
    source: str = "composio",
) -> None:
    """Schedule a composio_tool_log row write.  Never blocks the caller."""
    try:
        asyncio.create_task(
            _write_composio_log(
                user_id, source, slug, arguments,
                result_data, voice_result, success, error_message, duration_ms,
            )
        )
    except RuntimeError:
        # No running event loop (e.g. during unit tests) — skip silently.
        pass


def log_perplexity_search(
    user_id: Optional[str],
    arguments: dict,
    result_data: Any,
    duration_ms: int,
    success: bool,
    error_message: Optional[str] = None,
) -> None:
    """Schedule a perplexity_searches row write with full structured fields.

    Extracts query / model / response_content / search_results / usage from
    the raw Composio result["data"] dict so callers don't have to parse it.
    Never blocks the caller.
    """
    query = arguments.get("userContent", "") if arguments else ""
    model = arguments.get("model", "sonar") if arguments else "sonar"

    response_content: Optional[str] = None
    search_results: Any = None
    usage: Any = None

    if result_data and isinstance(result_data, dict):
        choices = result_data.get("choices", [])
        if choices:
            response_content = choices[0].get("message", {}).get("content")
        search_results = result_data.get("search_results")
        usage = result_data.get("usage")

    try:
        asyncio.create_task(
            _write_perplexity_log(
                user_id, query, model, response_content,
                search_results, usage, duration_ms, success, error_message,
            )
        )
    except RuntimeError:
        pass
