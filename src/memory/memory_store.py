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
import math
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
TEMPORAL_HALF_LIFE_DAYS = 30.0  # Memories score 50% less after 30 days

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
        print(f"[Memory] Store initialized at {_db_path}", flush=True)
        return True

    except Exception as exc:
        _init_failed = True
        logger.error("[Memory] Store init failed: %s", exc)
        print(f"[Memory] Store init FAILED: {exc}", flush=True)
        return False


def reinit_for_user(user_mem_dir: str) -> bool:
    """Re-initialize the memory store for a specific user's directory.

    Called at session start to switch the singleton to the user's SQLite db.
    Idempotent: no-op if already initialized for the same path.

    Args:
        user_mem_dir: Per-user memory directory (e.g., /app/data/memory/users/jay)

    Returns:
        True if initialized successfully, False otherwise.
    """
    global _initialized, _init_failed, _db_path

    target_db = os.path.join(user_mem_dir, "aio-voice-memory.sqlite")

    # Already on the right database — skip reinit
    if _initialized and _db_path == target_db:
        logger.info("[Memory] Already initialized for: %s", target_db)
        return True

    # Reset singleton state so init() will run fresh for this user
    _initialized = False
    _init_failed = False
    logger.info("[Memory] Switching memory store to user dir: %s", user_mem_dir)
    return init(user_mem_dir)


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
        # Schema evolution: add user_id and session_id to memories if missing
        for col_def in [
            ("user_id", "TEXT"),
            ("session_id", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {col_def[0]} {col_def[1]}")
            except Exception:
                pass  # Column already exists
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_session_id ON memories(session_id)")
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deep_store (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    TEXT NOT NULL DEFAULT '_default',
                label      TEXT,
                content    TEXT NOT NULL,
                session_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # Schema evolution: add embedding column and indexes to deep_store if missing
        try:
            conn.execute("ALTER TABLE deep_store ADD COLUMN embedding TEXT")
        except Exception:
            pass  # Column already exists
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deep_store_user_id ON deep_store(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deep_store_created_at ON deep_store(created_at)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_summaries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id    TEXT NOT NULL UNIQUE,
                user_id       TEXT NOT NULL DEFAULT '_default',
                summary       TEXT NOT NULL,
                topics        TEXT NOT NULL DEFAULT '[]',
                message_count INTEGER NOT NULL DEFAULT 0,
                embedding     TEXT,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ss_user_created
                ON session_summaries(user_id, created_at DESC)
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
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
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
                    INSERT INTO memories (id, text, text_safe, category, importance, source, embedding, created_at, user_id, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (entry_id, text, text_safe, category, importance, source, embedding_json, now, user_id or None, session_id or None),
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


def _get_creation_times(ids: list[str]) -> dict[str, int]:
    """Fetch created_at timestamps for a list of memory IDs."""
    if not ids or _db_path is None:
        return {}
    try:
        placeholders = ",".join("?" for _ in ids)
        with sqlite3.connect(_db_path) as conn:
            rows = conn.execute(
                f"SELECT id, created_at FROM memories WHERE id IN ({placeholders})",  # nosec B608
                ids,
            ).fetchall()
        return {row_id: created_at for row_id, created_at in rows}
    except Exception:
        return {}


def _apply_temporal_decay(score: float, created_at: int) -> float:
    """Apply exponential half-life decay: score × e^(-ln(2)/halfLife × age_days)."""
    age_days = (time.time() - created_at) / 86400
    if age_days <= 0:
        return score
    decay = math.exp(-math.log(2) / TEMPORAL_HALF_LIFE_DAYS * age_days)
    return score * decay


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
        creation_times = _get_creation_times(list(all_ids))
        scored: list[dict[str, Any]] = []

        for cand_id in all_ids:
            v_score = vector_results.get(cand_id, 0.0)
            t_score = text_results.get(cand_id, 0.0)
            final = VECTOR_WEIGHT * v_score + TEXT_WEIGHT * t_score
            # Apply temporal decay — older memories score progressively lower
            if cand_id in creation_times:
                final = _apply_temporal_decay(final, creation_times[cand_id])
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


# ────────────────────────────────────────────────────────────────────────────────
# Deep Store — unlimited persistent archive (no size cap, no dedup, no expiry)
# ────────────────────────────────────────────────────────────────────────────────

def deep_store_save(
    content: str,
    label: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: str = "_default",
) -> int:
    """
    Insert content into the deep_store table.

    Args:
        content:    The content to archive (no size limit).
        label:      Short descriptive label for later recall.
        session_id: Session identifier (optional).
        user_id:    Per-user partition key (defaults to '_default').

    Returns:
        The row id of the inserted entry on success, 0 on failure.
    """
    if not _initialized or _init_failed or _db_path is None:
        logger.warning("[DeepStore] Store not initialized — cannot save")
        return 0

    with _lock:
        try:
            with sqlite3.connect(_db_path) as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO deep_store (user_id, label, content, session_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, label or None, content, session_id or None),
                )
                conn.commit()
                row_id = cursor.lastrowid or 0
            logger.debug("[DeepStore] Saved id=%d label=%r", row_id, label)
            return row_id
        except Exception as exc:
            logger.error("[DeepStore] Save error: %s", exc)
            return 0


def deep_store_search(
    query: str,
    label: Optional[str] = None,
    limit: int = 10,
    user_id: str = "_default",
) -> list[dict[str, Any]]:
    """
    Search the deep_store table by label or content substring.

    Matches rows WHERE content LIKE %query% OR label LIKE %query%.
    If label is provided it is AND-ed as an additional filter (label LIKE %label%).
    Results are ordered by created_at DESC.

    Args:
        query:   Text to search in content and label columns.
        label:   Optional label filter — narrows results to matching labels.
        limit:   Maximum number of rows to return.
        user_id: Per-user partition key.

    Returns:
        List of dicts with keys: id, label, content, session_id, created_at.
    """
    if not _initialized or _init_failed or _db_path is None:
        return []

    try:
        pattern = f"%{query}%" if query else "%"
        if label:
            label_pattern = f"%{label}%"
            with sqlite3.connect(_db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT id, label, content, session_id, created_at
                    FROM deep_store
                    WHERE user_id = ?
                      AND label LIKE ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, label_pattern, limit),
                ).fetchall()
        elif query:
            with sqlite3.connect(_db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT id, label, content, session_id, created_at
                    FROM deep_store
                    WHERE user_id = ?
                      AND (content LIKE ? OR label LIKE ?)
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, pattern, pattern, limit),
                ).fetchall()
        else:
            # No query, no label — return most recent entries
            with sqlite3.connect(_db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT id, label, content, session_id, created_at
                    FROM deep_store
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                ).fetchall()

        return [
            {
                "id": row[0],
                "label": row[1] or "",
                "content": row[2],
                "session_id": row[3] or "",
                "created_at": row[4] or "",
            }
            for row in rows
        ]

    except Exception as exc:
        logger.error("[DeepStore] Search error: %s", exc)
        return []


# ────────────────────────────────────────────────────────────────────────────────
# Session Summaries — cross-session semantic recall over distilled session text
# ────────────────────────────────────────────────────────────────────────────────

def save_session_summary(
    session_id: str,
    summary: str,
    topics: Optional[list] = None,
    message_count: int = 0,
    user_id: str = "_default",
) -> bool:
    """Store a distilled session summary with fastembed embedding.

    Uses INSERT OR REPLACE to handle re-saves of the same session_id.
    Returns True on success, False on failure.
    """
    if not _initialized or _init_failed or _db_path is None:
        logger.warning("[SessionSummary] Store not initialized — cannot save")
        return False

    topics_json = json.dumps(topics or [])
    embedding = embedder.embed(summary)
    embedding_json = json.dumps(embedding) if embedding is not None else None

    with _lock:
        try:
            with sqlite3.connect(_db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO session_summaries
                        (session_id, user_id, summary, topics, message_count, embedding)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, user_id, summary, topics_json, message_count, embedding_json),
                )
                conn.commit()
            logger.info(
                "[SessionSummary] Saved session_id=%r user=%r msgs=%d",
                session_id, user_id, message_count,
            )
            return True
        except Exception as exc:
            logger.error("[SessionSummary] Save error: %s", exc)
            return False


def search_session_summaries(
    query: str,
    user_id: str = "_default",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Semantic search over session summaries for a user.

    Returns list of dicts: {session_id, summary, topics, message_count, score, created_at}
    sorted by cosine similarity descending.
    Falls back to recency order if no embeddings are stored.
    """
    if not _initialized or _init_failed or _db_path is None:
        return []

    try:
        with sqlite3.connect(_db_path) as conn:
            rows = conn.execute(
                """
                SELECT session_id, summary, topics, message_count, embedding, created_at
                FROM session_summaries
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()

        if not rows:
            return []

        query_embedding = embedder.embed(query)

        scored: list[tuple[float, tuple]] = []
        for row in rows:
            row_session_id, row_summary, row_topics_json, row_msg_count, row_emb_json, row_created = row
            if query_embedding is not None and row_emb_json:
                try:
                    row_vec = json.loads(row_emb_json)
                    score = embedder.cosine_similarity(query_embedding, row_vec)
                except Exception:
                    score = 0.0
            else:
                # No embedding available — use recency score (already ordered DESC)
                score = 0.0
            scored.append((score, row))

        # Sort by score descending; ties preserve recency order (stable sort)
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        results = []
        for score, row in top:
            row_session_id, row_summary, row_topics_json, row_msg_count, _, row_created = row
            try:
                topics_list = json.loads(row_topics_json) if row_topics_json else []
            except Exception:
                topics_list = []
            results.append({
                "session_id": row_session_id,
                "summary": row_summary,
                "topics": topics_list,
                "message_count": row_msg_count,
                "score": round(score, 4),
                "created_at": row_created or "",
            })

        return results

    except Exception as exc:
        logger.error("[SessionSummary] Search error: %s", exc)
        return []


def get_session_summary(session_id: str) -> Optional[dict[str, Any]]:
    """Get a specific session summary by session_id. Returns None if not found."""
    if not _initialized or _init_failed or _db_path is None:
        return None

    try:
        with sqlite3.connect(_db_path) as conn:
            row = conn.execute(
                """
                SELECT session_id, summary, topics, message_count, created_at
                FROM session_summaries
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            return None

        row_session_id, row_summary, row_topics_json, row_msg_count, row_created = row
        try:
            topics_list = json.loads(row_topics_json) if row_topics_json else []
        except Exception:
            topics_list = []

        return {
            "session_id": row_session_id,
            "summary": row_summary,
            "topics": topics_list,
            "message_count": row_msg_count,
            "created_at": row_created or "",
        }

    except Exception as exc:
        logger.error("[SessionSummary] Get error: %s", exc)
        return None
