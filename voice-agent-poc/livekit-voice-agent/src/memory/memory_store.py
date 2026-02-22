"""
AIO Voice System — SQLite Memory Store

Persistent cross-session memory with:
- Hybrid search: 0.7 * vector_score + 0.3 * bm25_score
- Deduplication: skip store if similarity > 0.95 with existing entry
- Prompt injection protection: HTML-entity escape on all stored text
- Thread-safe writes via threading.Lock
- WAL mode for concurrent reads

Schema:
  memories       — discrete facts (auto-captured or explicit)
  memories_fts   — FTS5 virtual table for BM25 keyword search

Gracefully disabled: if SQLite init fails, all operations are no-ops.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

from . import embedder

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────────────────

VECTOR_WEIGHT = 0.7
TEXT_WEIGHT = 0.3
DEFAULT_TOP_K = 3
MIN_SCORE = 0.25           # Minimum final score to include in results
DEDUP_THRESHOLD = 0.95     # Cosine similarity above which we skip storage
MAX_MEMORY_TEXT_LEN = 1000 # Characters — truncate longer entries at store time

# Patterns that suggest prompt injection attempts
_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(previous|all|above)\s+instructions?|"
    r"system\s*:\s*you\s+are|"
    r"<\s*/?system\s*>|"
    r"assistant\s*:\s*|"
    r"human\s*:\s*|"
    r"\[INST\]|\[/INST\]|"
    r"###\s*(instruction|system|prompt))",
    re.IGNORECASE,
)

# ────────────────────────────────────────────────────────────────────────────────
# Singleton state
# ────────────────────────────────────────────────────────────────────────────────

_db_path: Optional[str] = None
_lock = threading.Lock()
_initialized = False
_init_failed = False


# ────────────────────────────────────────────────────────────────────────────────
# Initialization
# ────────────────────────────────────────────────────────────────────────────────

def init(memory_dir: Optional[str] = None) -> bool:
    """
    Initialize the SQLite memory store. Idempotent — safe to call multiple times.

    Args:
        memory_dir: Directory for memory files. Defaults to AIO_MEMORY_DIR env var
                    or /app/data/memory.

    Returns:
        True if initialized successfully, False if memory is unavailable.
    """
    global _db_path, _initialized, _init_failed

    if _initialized:
        return True
    if _init_failed:
        return False

    base_dir = memory_dir or os.environ.get("AIO_MEMORY_DIR", "/app/data/memory")

    try:
        os.makedirs(base_dir, exist_ok=True)
        sessions_dir = os.path.join(base_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)

        _db_path = os.path.join(base_dir, "aio-voice-memory.sqlite")
        _create_schema(_db_path)
        _initialized = True

        # Update package-level flag
        import sys
        module = sys.modules[__name__.rsplit(".", 1)[0]]  # parent package
        module.MEMORY_AVAILABLE = True  # type: ignore[attr-defined]

        logger.info("[Memory] Store initialized at %s", _db_path)
        return True

    except Exception as exc:
        _init_failed = True
        logger.error("[Memory] Store init failed: %s", exc)
        return False


def _create_schema(db_path: str) -> None:
    """Create tables if they don't exist. Idempotent."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id          TEXT PRIMARY KEY,
                text        TEXT NOT NULL,
                text_safe   TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                importance  REAL NOT NULL DEFAULT 0.5,
                source      TEXT NOT NULL DEFAULT 'auto',
                embedding   TEXT,
                created_at  INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                text,
                id          UNINDEXED,
                category    UNINDEXED,
                content     = 'memories',
                content_rowid = 'rowid'
            )
        """)
        # Keep FTS in sync with memories table
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai
            AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, text, id, category)
                VALUES (new.rowid, new.text, new.id, new.category);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad
            AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, text, id, category)
                VALUES ('delete', old.rowid, old.text, old.id, old.category);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au
            AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, text, id, category)
                VALUES ('delete', old.rowid, old.text, old.id, old.category);
                INSERT INTO memories_fts(rowid, text, id, category)
                VALUES (new.rowid, new.text, new.id, new.category);
            END
        """)
        conn.commit()


# ────────────────────────────────────────────────────────────────────────────────
# Security helpers
# ────────────────────────────────────────────────────────────────────────────────

def _looks_like_injection(text: str) -> bool:
    """Return True if text contains prompt injection patterns."""
    return bool(_INJECTION_PATTERNS.search(text))


def _escape_for_prompt(text: str) -> str:
    """HTML-entity escape text before injecting into agent context."""
    return html.escape(text, quote=True)


# ────────────────────────────────────────────────────────────────────────────────
# Write operations
# ────────────────────────────────────────────────────────────────────────────────

def store(
    text: str,
    category: str = "general",
    importance: float = 0.5,
    source: str = "auto",
) -> Optional[str]:
    """
    Store a memory entry.

    Returns the entry id on success, None on failure or if rejected.
    Rejects entries that:
    - Look like prompt injection
    - Are too long (truncated instead)
    - Are near-duplicates of existing entries (cosine similarity > 0.95)
    """
    if not _initialized or _init_failed:
        return None

    if _looks_like_injection(text):
        logger.warning("[Memory] Rejected injection attempt: %.80s...", text)
        return None

    # Truncate long entries
    if len(text) > MAX_MEMORY_TEXT_LEN:
        text = text[:MAX_MEMORY_TEXT_LEN] + "…"

    text_safe = _escape_for_prompt(text)
    embedding = embedder.embed(text)

    # Deduplication check
    if embedding is not None and _is_near_duplicate(embedding):
        logger.debug("[Memory] Skipping near-duplicate entry: %.60s...", text)
        return None

    entry_id = str(uuid.uuid4())
    embedding_json = json.dumps(embedding) if embedding is not None else None
    now = int(time.time())

    with _lock:
        try:
            with sqlite3.connect(_db_path) as conn:  # type: ignore[arg-type]
                conn.execute(
                    """
                    INSERT INTO memories (id, text, text_safe, category, importance, source, embedding, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entry_id, text, text_safe, category, importance, source, embedding_json, now),
                )
                conn.commit()
            logger.debug("[Memory] Stored: [%s] %.60s...", category, text)
            return entry_id
        except Exception as exc:
            logger.error("[Memory] Store error: %s", exc)
            return None


def _is_near_duplicate(query_embedding: list[float]) -> bool:
    """Check if a very similar entry already exists (cosine similarity > 0.95)."""
    try:
        with sqlite3.connect(_db_path) as conn:  # type: ignore[arg-type]
            rows = conn.execute(
                "SELECT embedding FROM memories WHERE embedding IS NOT NULL ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
        for (emb_json,) in rows:
            if emb_json:
                existing = json.loads(emb_json)
                sim = embedder.cosine_similarity(query_embedding, existing)
                if sim >= DEDUP_THRESHOLD:
                    return True
        return False
    except Exception:
        return False  # On error, allow storage


# ────────────────────────────────────────────────────────────────────────────────
# Search operations
# ────────────────────────────────────────────────────────────────────────────────

def search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Hybrid search over memories.

    Returns list of {id, text_safe, category, score, created_at} dicts,
    sorted by descending final score.

    text_safe is HTML-entity escaped — safe to inject into agent context.
    """
    if not _initialized or _init_failed:
        return []

    try:
        query_embedding = embedder.embed(query)
        vector_results = _vector_search(query_embedding, top_k * 4, category) if query_embedding else {}
        text_results = _bm25_search(query, top_k * 4, category)

        # Merge candidates
        all_ids: set[str] = set(vector_results) | set(text_results)
        scored: list[dict[str, Any]] = []

        for cand_id in all_ids:
            v_score = vector_results.get(cand_id, 0.0)
            t_score = text_results.get(cand_id, 0.0)
            final = VECTOR_WEIGHT * v_score + TEXT_WEIGHT * t_score
            if final < MIN_SCORE:
                continue
            scored.append({"_id": cand_id, "score": final})

        scored.sort(key=lambda x: x["score"], reverse=True)
        top_ids = [r["_id"] for r in scored[:top_k]]

        if not top_ids:
            return []

        return _fetch_by_ids(top_ids, scored[:top_k])

    except Exception as exc:
        logger.error("[Memory] Search error: %s", exc)
        return []


def _vector_search(
    query_embedding: list[float],
    limit: int,
    category: Optional[str],
) -> dict[str, float]:
    """Pure Python cosine similarity over all stored embeddings."""
    results: dict[str, float] = {}
    try:
        with sqlite3.connect(_db_path) as conn:  # type: ignore[arg-type]
            if category:
                rows = conn.execute(
                    "SELECT id, embedding FROM memories WHERE embedding IS NOT NULL AND category = ?",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, embedding FROM memories WHERE embedding IS NOT NULL"
                ).fetchall()

        for entry_id, emb_json in rows:
            if not emb_json:
                continue
            vec = json.loads(emb_json)
            sim = embedder.cosine_similarity(query_embedding, vec)
            results[entry_id] = max(0.0, sim)  # clamp to [0, 1]

        # Return top `limit` by score
        top = sorted(results.items(), key=lambda x: x[1], reverse=True)[:limit]
        return dict(top)

    except Exception as exc:
        logger.error("[Memory] Vector search error: %s", exc)
        return {}


def _bm25_search(
    query: str,
    limit: int,
    category: Optional[str],
) -> dict[str, float]:
    """FTS5 BM25 full-text search. BM25 ranks are negative in SQLite (more negative = better)."""
    results: dict[str, float] = {}
    try:
        with sqlite3.connect(_db_path) as conn:  # type: ignore[arg-type]
            if category:
                rows = conn.execute(
                    """
                    SELECT m.id, bm25(memories_fts) as rank
                    FROM memories_fts
                    JOIN memories m ON memories_fts.id = m.id
                    WHERE memories_fts MATCH ? AND m.category = ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, bm25(memories_fts) as rank
                    FROM memories_fts
                    WHERE memories_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()

        for entry_id, rank in rows:
            # Normalize: rank is negative, larger magnitude = better match
            # 1 / (1 + |rank|) maps to [0, 1]
            score = 1.0 / (1.0 + max(0.0, abs(rank)))
            results[entry_id] = score

        return results

    except Exception as exc:
        logger.error("[Memory] BM25 search error: %s", exc)
        return {}


def _fetch_by_ids(
    ids: list[str],
    scored: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Fetch full memory entries by id list, preserving score order."""
    score_map = {r["_id"]: r["score"] for r in scored}
    try:
        placeholders = ",".join("?" for _ in ids)
        with sqlite3.connect(_db_path) as conn:  # type: ignore[arg-type]
            rows = conn.execute(
                f"SELECT id, text_safe, category, created_at FROM memories WHERE id IN ({placeholders})",  # nosec B608 — placeholders are all '?', ids passed as params
                ids,
            ).fetchall()

        result = []
        for row_id, text_safe, category, created_at in rows:
            result.append(
                {
                    "id": row_id,
                    "text_safe": text_safe,
                    "category": category,
                    "score": score_map.get(row_id, 0.0),
                    "created_at": created_at,
                }
            )
        result.sort(key=lambda x: x["score"], reverse=True)
        return result

    except Exception as exc:
        logger.error("[Memory] Fetch error: %s", exc)
        return []


# ────────────────────────────────────────────────────────────────────────────────
# Utility
# ────────────────────────────────────────────────────────────────────────────────

def get_stats() -> dict[str, Any]:
    """Return basic stats about the memory store."""
    if not _initialized or _init_failed:
        return {"available": False}
    try:
        with sqlite3.connect(_db_path) as conn:  # type: ignore[arg-type]
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            by_cat = conn.execute(
                "SELECT category, COUNT(*) FROM memories GROUP BY category"
            ).fetchall()
        return {
            "available": True,
            "total_entries": total,
            "by_category": dict(by_cat),
            "db_path": _db_path,
        }
    except Exception as exc:
        return {"available": True, "error": str(exc)}
