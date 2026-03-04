"""
pgvector_migration.py — One-time migration of existing SQLite memories to pgvector.

Reads all rows from SQLite tables (memories, deep_store, session_summaries)
and bulk-inserts them into the pgvector aio_memories table.

Idempotent: uses a sentinel row in aio_memories (source='_migration_complete')
to detect if migration has already run. Safe to call on every startup.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


async def migrate_sqlite_to_pgvector(
    sqlite_path: str,
    pgvector_pool,  # asyncpg Pool
) -> int:
    """
    Migrate all SQLite memory tables to pgvector.
    Returns number of rows migrated (0 if already done or nothing to migrate).
    Idempotent — safe to call on every startup.
    """
    if not os.path.exists(sqlite_path):
        logger.info("pgvector migration: SQLite file not found at %s, skipping", sqlite_path)
        return 0

    # Check sentinel — if already run, skip immediately
    async with pgvector_pool.acquire() as conn:
        sentinel = await conn.fetchrow(
            "SELECT id FROM aio_memories WHERE source = '_migration_complete' LIMIT 1"
        )
        if sentinel:
            logger.debug("pgvector migration: already completed, skipping")
            return 0

    logger.info("pgvector migration: starting from %s", sqlite_path)
    total = 0

    try:
        db = sqlite3.connect(sqlite_path)
        db.row_factory = sqlite3.Row

        # ── 1. memories table ────────────────────────────────────────────────
        # Column mapping: text -> content, category, importance, source,
        # embedding (JSON TEXT), user_id, session_id, created_at (INTEGER epoch)
        try:
            rows = db.execute(
                "SELECT text, category, importance, source, embedding, "
                "user_id, session_id, created_at FROM memories WHERE embedding IS NOT NULL"
            ).fetchall()
            batch = []
            for r in rows:
                emb = r["embedding"]
                if not emb:
                    continue
                try:
                    vec = json.loads(emb) if isinstance(emb, str) else emb
                    if not isinstance(vec, list) or len(vec) != 384:
                        continue
                except Exception:
                    continue
                batch.append({
                    "content": r["text"],
                    "category": r["category"],
                    "importance": float(r["importance"] or 0.5),
                    "source": r["source"] or "capture",
                    "embedding": vec,
                    "user_id": r["user_id"] or "_default",
                    "session_id": r["session_id"],
                    "label": None,
                })
            n = await _bulk_insert(pgvector_pool, batch)
            total += n
            logger.info("pgvector migration: memories -> %d rows inserted", n)
        except sqlite3.OperationalError as e:
            logger.warning("pgvector migration: memories table error: %s", e)

        # ── 2. deep_store table ──────────────────────────────────────────────
        # Columns: content, label, user_id, session_id, embedding (TEXT JSON),
        # created_at (TEXT ISO datetime)
        try:
            rows = db.execute(
                "SELECT content, label, user_id, session_id, embedding, created_at "
                "FROM deep_store WHERE embedding IS NOT NULL"
            ).fetchall()
            batch = []
            for r in rows:
                emb = r["embedding"]
                if not emb:
                    continue
                try:
                    vec = json.loads(emb) if isinstance(emb, str) else emb
                    if not isinstance(vec, list) or len(vec) != 384:
                        continue
                except Exception:
                    continue
                batch.append({
                    "content": r["content"],
                    "label": r["label"],
                    "source": "deep_store",
                    "importance": 0.9,
                    "embedding": vec,
                    "user_id": r["user_id"] or "_default",
                    "session_id": r["session_id"],
                    "category": None,
                })
            n = await _bulk_insert(pgvector_pool, batch)
            total += n
            logger.info("pgvector migration: deep_store -> %d rows inserted", n)
        except sqlite3.OperationalError as e:
            logger.warning("pgvector migration: deep_store table error: %s", e)

        # ── 3. session_summaries table ───────────────────────────────────────
        # Columns: summary, user_id, session_id, embedding (TEXT JSON),
        # created_at (TEXT ISO datetime)
        try:
            rows = db.execute(
                "SELECT summary, user_id, session_id, embedding, created_at "
                "FROM session_summaries WHERE embedding IS NOT NULL"
            ).fetchall()
            batch = []
            for r in rows:
                emb = r["embedding"]
                if not emb:
                    continue
                try:
                    vec = json.loads(emb) if isinstance(emb, str) else emb
                    if not isinstance(vec, list) or len(vec) != 384:
                        continue
                except Exception:
                    continue
                batch.append({
                    "content": r["summary"],
                    "source": "session_summary",
                    "importance": 0.7,
                    "embedding": vec,
                    "user_id": r["user_id"] or "_default",
                    "session_id": r["session_id"],
                    "label": None,
                    "category": None,
                })
            n = await _bulk_insert(pgvector_pool, batch)
            total += n
            logger.info("pgvector migration: session_summaries -> %d rows inserted", n)
        except sqlite3.OperationalError as e:
            logger.warning("pgvector migration: session_summaries table error: %s", e)

        db.close()

    except Exception as e:
        logger.error("pgvector migration: unexpected error: %s", e)
        return total

    # Write sentinel — always write after first attempt so we never re-scan
    # a SQLite with no embeddings either (avoids repeated empty-scan on startup)
    try:
        dummy_vec = "[" + ",".join(["0.0"] * 384) + "]"
        async with pgvector_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO aio_memories (user_id, content, embedding, source) "
                "VALUES ('_system', '_migration_complete', $1::vector, '_migration_complete')",
                dummy_vec,
            )
    except Exception as e:
        logger.warning("pgvector migration: sentinel write failed: %s", e)

    logger.info("pgvector migration: complete — %d rows migrated to pgvector", total)
    return total


async def backfill_conversation_log(
    postgres_url: str,
    pgvector_pool,
    batch_size: int = 50,
    rows_per_run: int = 300,
) -> int:
    """
    Incrementally backfill conversation_log into pgvector.
    Uses a progress marker (source='_backfill_progress') so each
    worker resumes from where the last one stopped.
    Sentinel (source='_conv_backfill_complete') written when all rows done.
    Returns count of rows inserted this run.
    """
    import asyncpg as _asyncpg

    # Already done?
    async with pgvector_pool.acquire() as conn:
        if await conn.fetchrow(
            "SELECT id FROM aio_memories WHERE source = '_conv_backfill_complete' LIMIT 1"
        ):
            logger.debug("pgvector backfill: already complete, skipping")
            return 0

    # Read progress marker
    last_id = 0
    async with pgvector_pool.acquire() as conn:
        progress = await conn.fetchrow(
            "SELECT content FROM aio_memories WHERE source = '_backfill_progress' LIMIT 1"
        )
        if progress:
            try:
                last_id = int(progress["content"].split("last_id=")[1])
            except Exception:
                last_id = 0

    logger.info(f"pgvector backfill: resuming from conversation_log id > {last_id}")

    # Fetch next slice from conversation_log
    conv_pool = await _asyncpg.create_pool(postgres_url, min_size=1, max_size=2)
    try:
        rows = await conv_pool.fetch(
            """
            SELECT id, session_id, role, content, user_id
            FROM conversation_log
            WHERE role IN ('user', 'assistant')
              AND LENGTH(content) > 20
              AND id > $1
            ORDER BY id ASC
            LIMIT $2
            """,
            last_id, rows_per_run,
        )
    finally:
        await conv_pool.close()

    if not rows:
        # All rows processed — write sentinel
        logger.info("pgvector backfill: all conversation turns embedded — writing sentinel")
        dummy = "[" + ",".join(["0.0"] * 384) + "]"
        async with pgvector_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO aio_memories (user_id, content, embedding, source) "
                "VALUES ('_system', '_conv_backfill_complete', $1::vector, '_conv_backfill_complete') "
                "ON CONFLICT DO NOTHING",
                dummy,
            )
        return 0

    logger.info(f"pgvector backfill: embedding {len(rows)} turns (id {rows[0]['id']}–{rows[-1]['id']})")

    # Import embedder — lazy singleton, loads fastembed ONNX model on first call
    from ..memory.embedder import embed as _embed

    total = 0
    new_last_id = last_id
    for i in range(0, len(rows), batch_size):
        chunk = rows[i : i + batch_size]
        records = []
        for r in chunk:
            try:
                emb = _embed(r["content"])
                if emb is None or len(emb) != 384:
                    continue
                records.append({
                    "content": r["content"],
                    "label": None,
                    "source": "conversation_backfill",
                    "importance": 0.6 if r["role"] == "user" else 0.5,
                    "embedding": emb,
                    "user_id": r["user_id"] or "_default",
                    "session_id": r["session_id"],
                    "category": "conversation",
                })
                new_last_id = max(new_last_id, r["id"])
            except Exception as _e:
                logger.debug(f"pgvector backfill embed error: {_e}")

        inserted = await _bulk_insert(pgvector_pool, records)
        total += inserted

    # Upsert progress marker: delete old, insert new
    async with pgvector_pool.acquire() as conn:
        await conn.execute("DELETE FROM aio_memories WHERE source = '_backfill_progress'")
        await conn.execute(
            "INSERT INTO aio_memories (user_id, content, embedding, source) "
            "VALUES ('_system', $1, $2::vector, '_backfill_progress')",
            f"last_id={new_last_id}",
            "[" + ",".join(["0.0"] * 384) + "]",
        )

    logger.info(f"pgvector backfill: {total} turns embedded this run, progress saved at id={new_last_id}")
    return total


async def _bulk_insert(pool, rows: list) -> int:
    """Batch-insert rows into aio_memories. Returns count of rows attempted (not verified)."""
    if not rows:
        return 0
    inserted = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        try:
            async with pool.acquire() as conn:
                await conn.executemany(
                    """
                    INSERT INTO aio_memories
                        (user_id, session_id, content, label, category,
                         source, importance, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
                    ON CONFLICT DO NOTHING
                    """,
                    [
                        (
                            r.get("user_id", "_default"),
                            r.get("session_id"),
                            r["content"],
                            r.get("label"),
                            r.get("category"),
                            r.get("source", "capture"),
                            float(r.get("importance", 0.5)),
                            "[" + ",".join(f"{float(v):.8f}" for v in r["embedding"]) + "]",
                        )
                        for r in batch
                    ],
                )
                inserted += len(batch)
        except Exception as e:
            logger.warning("pgvector migration: batch insert error (batch %d): %s", i // BATCH_SIZE, e)
    return inserted
