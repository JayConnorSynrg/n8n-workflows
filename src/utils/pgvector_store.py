"""
pgvector_store.py — AIO semantic memory via pgvector on Railway Postgres.

Provides async functions to store and search 384-dim embeddings using
pgvector's HNSW index. Gracefully degrades if Postgres is unavailable.

The pool is initialized once per worker process at agent startup via
init_pgvector_pool(). All public functions are no-ops when the pool is None.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import List, Optional, Tuple

import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _vec_to_pg(embedding: list) -> str:
    """Serialize float list to pgvector string format '[f1,f2,...]'."""
    return "[" + ",".join(f"{float(v):.8f}" for v in embedding) + "]"


# ─────────────────────────────────────────────────────────────────────────────
# Pool lifecycle
# ─────────────────────────────────────────────────────────────────────────────

async def init_pgvector_pool(postgres_url: str) -> bool:
    """
    Initialize asyncpg pool and ensure pgvector schema exists.
    Returns True if successful, False only if pool creation itself fails.
    Schema errors (concurrent race conditions) are logged but do not invalidate the pool.
    Idempotent — no-op if pool is already initialized (singleton across all sessions).
    """
    global _pool
    if _pool is not None:
        logger.debug("pgvector: pool already initialized, skipping re-init")
        return True
    try:
        _pool = await asyncpg.create_pool(postgres_url, min_size=1, max_size=3)
    except Exception as e:
        logger.warning("pgvector: pool creation failed (will use SQLite fallback): %s", e)
        _pool = None
        return False
    # Pool created — schema errors (e.g. concurrent worker race) do not invalidate the pool
    try:
        await _ensure_schema()
        logger.info("pgvector: pool initialized, schema ready")
    except Exception as e:
        logger.warning(
            "pgvector: schema init error (pool still active, schema may already exist): %s", e
        )
    return True


async def _ensure_schema() -> None:
    """Idempotent schema creation — safe for concurrent callers across worker processes."""
    async with _pool.acquire() as conn:
        # CREATE EXTENSION — IF NOT EXISTS is not concurrent-safe in PG; catch the race
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                pass  # Another worker created it simultaneously — this is fine
            else:
                raise

        # CREATE TABLE — concurrent-safe
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS aio_memories (
                    id          BIGSERIAL PRIMARY KEY,
                    user_id     TEXT        NOT NULL DEFAULT '_default',
                    session_id  TEXT,
                    content     TEXT        NOT NULL,
                    label       TEXT,
                    category    TEXT,
                    source      TEXT        NOT NULL DEFAULT 'capture',
                    importance  REAL        NOT NULL DEFAULT 0.5,
                    embedding   vector(384) NOT NULL,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    metadata    JSONB
                )
            """)
        except Exception as e:
            if "already exists" in str(e) or "duplicate" in str(e).lower():
                pass
            else:
                raise

        # CREATE INDEXES — each wrapped individually; concurrent workers may race on these too
        for idx_sql in [
            (
                "CREATE INDEX IF NOT EXISTS aio_memories_hnsw "
                "ON aio_memories USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            ),
            "CREATE INDEX IF NOT EXISTS aio_memories_user_idx ON aio_memories (user_id)",
            "CREATE INDEX IF NOT EXISTS aio_memories_user_source_idx ON aio_memories (user_id, source)",
            "CREATE INDEX IF NOT EXISTS aio_memories_created_idx ON aio_memories (created_at DESC)",
        ]:
            try:
                await conn.execute(idx_sql)
            except Exception as e:
                if "already exists" in str(e) or "duplicate" in str(e).lower():
                    pass
                else:
                    raise


def is_available() -> bool:
    """Check if pgvector pool is ready."""
    return _pool is not None


# ─────────────────────────────────────────────────────────────────────────────
# Write
# ─────────────────────────────────────────────────────────────────────────────

async def pgvector_save(
    content: str,
    embedding: list,
    user_id: str = "_default",
    session_id: Optional[str] = None,
    category: Optional[str] = None,
    label: Optional[str] = None,
    source: str = "capture",
    importance: float = 0.5,
    metadata: Optional[dict] = None,
) -> Optional[int]:
    """
    Save a memory embedding to pgvector. Fire-and-forget safe.
    Returns inserted row ID or None on failure.
    """
    if not _pool:
        return None
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO aio_memories
                    (user_id, session_id, content, label, category, source,
                     importance, embedding, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector, $9)
                RETURNING id
                """,
                user_id,
                session_id,
                content,
                label,
                category,
                source,
                importance,
                _vec_to_pg(embedding),
                json.dumps(metadata) if metadata else None,
            )
            return row["id"] if row else None
    except Exception as e:
        logger.warning("pgvector_save failed: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Search
# ─────────────────────────────────────────────────────────────────────────────

async def pgvector_search(
    query_embedding: list,
    user_id: str = "_default",
    top_k: int = 15,
    source_filter: Optional[str] = None,
) -> List[Tuple[str, str, float, str]]:
    """
    Semantic search using HNSW cosine similarity.
    Returns list of (content, category, similarity_score, source).
    similarity_score is in [0, 1] — higher = more similar.
    """
    if not _pool:
        return []
    try:
        vec_str = _vec_to_pg(query_embedding)
        if source_filter:
            rows = await _pool.fetch(
                """
                SELECT content, category, source,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM aio_memories
                WHERE user_id = $2 AND source = $3
                ORDER BY embedding <=> $1::vector
                LIMIT $4
                """,
                vec_str, user_id, source_filter, top_k,
            )
        else:
            rows = await _pool.fetch(
                """
                SELECT content, category, source,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM aio_memories
                WHERE user_id = $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                vec_str, user_id, top_k,
            )
        return [
            (r["content"], r["category"] or "general", float(r["similarity"]), r["source"])
            for r in rows
        ]
    except Exception as e:
        logger.warning("pgvector_search failed: %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostics
# ─────────────────────────────────────────────────────────────────────────────

async def pgvector_count(user_id: str = "_default") -> int:
    """Return total memory count for a user. Used for diagnostics."""
    if not _pool:
        return 0
    try:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS n FROM aio_memories WHERE user_id = $1",
                user_id,
            )
            return row["n"] if row else 0
    except Exception as e:
        logger.warning("pgvector_count failed: %s", e)
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# Teardown
# ─────────────────────────────────────────────────────────────────────────────

async def close_pgvector_pool() -> None:
    """Gracefully close pool at session end."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("pgvector: pool closed")
