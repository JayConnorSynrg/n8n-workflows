# AIO Database Architecture

**Generated:** 2026-03-04 | **Authoritative source:** actual source code, not documentation
**Purpose:** Enable future Claude sessions to instantly understand the full database layer without file investigation.

---

## 1. Overview

Four databases serve distinct roles. Understand which layer owns what before writing any code that touches storage.

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                          AIO VOICE SYSTEM — DATA FLOW                          ║
╚══════════════════════════════════════════════════════════════════════════════════╝

USER SPEAKS
    │
    ▼
on_conversation_item_added (agent.py)
    │
    ├──► [capture.py] detect_and_queue()
    │         → queue in-memory (flushed at session end)
    │         → flush_to_store() → memory_store.store()
    │                   │
    │                   ├──► SQLite: memories table INSERT        (sync, blocking)
    │                   └──► pgvector: pgvector_save()           (asyncio.ensure_future, fire-and-forget)
    │
    └──► [pg_logger.py] log_turn("user", ...)
              └──► Railway PG: conversation_log INSERT           (asyncio.create_task, fire-and-forget)

AGENT RESPONDS
    │
    └──► [pg_logger.py] log_turn("assistant", ...)
              └──► Railway PG: conversation_log INSERT           (asyncio.create_task, fire-and-forget)

deepStore TOOL CALLED
    │
    └──► [memory_store.py] deep_store_save()
              │
              ├──► SQLite: deep_store table INSERT               (sync, under threading.Lock)
              └──► pgvector: pgvector_save(source="deep_store")  (asyncio.ensure_future, fire-and-forget)

SESSION STARTS (room join)
    │
    ├──► [pg_logger.py] log_session_start()
    │         └──► Railway PG: sessions INSERT (ON CONFLICT DO NOTHING)  (create_task)
    │
    └──► WebSocket connection from relay-server
              └──► Supabase: bot_state SELECT                    (blocking fetch, up to 5s timeout)

SESSION ENDS (room disconnect)
    │
    ├──► [session_facts.py] flush_facts_to_db()
    │         └──► Railway PG: session_facts_log UPSERT          (awaited, raw asyncpg connection)
    │
    ├──► [pg_logger.py] log_session_end()
    │         └──► Railway PG: sessions UPSERT                   (awaited)
    │
    └──► [memory_store.py] flush_session() → MEMORY.md append   (filesystem write)

AGENT CALLS recall()
    │
    └──► [memory_store.py] search()
              │
              ├── 1. pgvector HNSW search (if _pgvector.is_available())
              │         └── if empty → fall back to SQLite brute-force
              └── 2. SQLite FTS5 BM25 search
                        └── merge: 0.7 × vector_score + 0.3 × bm25_score
```

---

## 2. Railway PostgreSQL (Primary Operational DB)

### Connection

| Field | Value |
|---|---|
| n8n Credential ID | `NI3jbq1U8xPst3j3` |
| Env var | `POSTGRES_URL` |
| Config field | `settings.postgres_url` (src/config.py line 59) |
| Pool impl | asyncpg pool in `src/utils/pg_logger.py` |
| Pool config | `min_size=1, max_size=3, command_timeout=5, ssl='require'` |
| Pool per worker | max 3 connections; 5 Gunicorn workers = max 15 total Railway PG connections |
| Raw connection | `src/utils/session_facts.py` — one-shot `asyncpg.connect()` at session end only |

Pool initialized once per worker in `prewarm()` via `await pg_logger.init_pool(settings.postgres_url)`. Idempotent — no-op if pool already exists.

### Tables

#### conversation_log

**Base DDL** (`database/conversation_log_migration.sql`):
```sql
CREATE TABLE IF NOT EXISTS conversation_log (
    id          BIGSERIAL PRIMARY KEY,
    session_id  TEXT        NOT NULL,
    role        TEXT        NOT NULL CHECK (role IN ('user', 'assistant', 'tool', 'system')),
    content     TEXT        NOT NULL,
    tool_name   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Amended by** `database/20260304_fix_conversation_log_user_id.sql` (2026-03-04):
- `user_id TEXT` column added via `ALTER TABLE` (nullable, no default — existing rows stay NULL)

**Full column set after migration:**
| Column | Type | Nullable | Notes |
|---|---|---|---|
| id | BIGSERIAL PK | NO | auto-increment |
| session_id | TEXT | NO | LiveKit room session identifier |
| role | TEXT | NO | CHECK: 'user', 'assistant', 'tool', 'system' |
| content | TEXT | NO | Capped at 4000 chars in pg_logger.py line 68 |
| tool_name | TEXT | YES | Populated for role='tool' rows only |
| user_id | TEXT | YES | Added via ALTER TABLE — pre-migration rows are NULL |
| created_at | TIMESTAMPTZ | NO | DEFAULT NOW() |

**Indexes:**
```sql
idx_conv_log_session          ON conversation_log(session_id)
idx_conv_log_created          ON conversation_log(created_at DESC)
idx_conv_log_user             ON conversation_log(user_id)            -- from 20260304 fix
idx_conv_log_session_created  ON conversation_log(session_id, created_at DESC)  -- from 20260304 fix
```

**Writes from:** `src/utils/pg_logger.py` — `log_turn()` only. Fire-and-forget via `asyncio.create_task`.
**Reads from:** n8n workflow `ouWMjcKzbj6nrYXz` (agent context webhook). Never read directly by agent code during a session.
**Gotcha:** The base migration omitted `user_id`. If `20260304_fix_conversation_log_user_id.sql` has not been applied, writes that pass `user_id=...` will crash silently. Always apply in order.
**Retention:** 90 days (cron job `prune-conversation-log` at 03:00 UTC daily).

---

#### sessions

**DDL** (`database/sessions_migration.sql`):
```sql
CREATE TABLE IF NOT EXISTS sessions (
    id              BIGSERIAL   PRIMARY KEY,
    session_id      TEXT        NOT NULL UNIQUE,
    user_id         TEXT,
    room_name       TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    message_count   INTEGER     NOT NULL DEFAULT 0,
    tool_call_count INTEGER     NOT NULL DEFAULT 0,
    summary         TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Indexes:**
```sql
idx_sessions_session_id  ON sessions(session_id)
idx_sessions_user_id     ON sessions(user_id)
idx_sessions_started_at  ON sessions(started_at DESC)
```

**Writes from:** `src/utils/pg_logger.py`:
- `log_session_start()` — `INSERT ... ON CONFLICT (session_id) DO NOTHING` at room join
- `log_session_end()` — `INSERT ... ON CONFLICT (session_id) DO UPDATE SET ended_at, summary, message_count, tool_call_count` at disconnect

Neither n8n nor relay-server writes to this table.
**Reads from:** Not queried by agent code. Available for analytics and monitoring.
**Retention:** 90 days (cron job `prune-old-sessions` at 03:30 UTC daily).
**Orphan cleanup:** `close-orphaned-sessions` cron (03:15 UTC) sets `ended_at = started_at + 4 hours` for sessions open more than 4 hours (Railway crash recovery).

---

#### session_facts_log

**DDL** (`database/session_facts_log_migration.sql`):
```sql
CREATE TABLE IF NOT EXISTS session_facts_log (
    id          BIGSERIAL   PRIMARY KEY,
    session_id  TEXT        NOT NULL,
    user_id     TEXT        NOT NULL DEFAULT '_default',
    key         TEXT        NOT NULL,
    value       TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**UNIQUE constraint** (`database/20260304_fix_session_facts_log_unique.sql`):
```sql
ALTER TABLE session_facts_log
    ADD CONSTRAINT uniq_session_facts_session_key UNIQUE (session_id, key);
```

CRITICAL: Without this constraint, `flush_facts_to_db()` raises:
`ERROR: there is no unique or exclusion constraint matching the ON CONFLICT specification`
Every session fact flush silently fails — Gamma URLs, generation IDs, and all cross-session facts are never persisted.

**Indexes:**
```sql
idx_session_facts_user_key   ON session_facts_log(user_id, key, created_at DESC)
idx_session_facts_session    ON session_facts_log(session_id)
idx_session_facts_session_key ON session_facts_log(session_id, key)  -- from 20260304 fix
```

**Writes from:** `src/utils/session_facts.py` — `flush_facts_to_db()` at session end only. Uses raw `asyncpg.connect()` (not the pg_logger pool) — single-use connection, awaited before session teardown completes.
**Reads from:** n8n workflow `ouWMjcKzbj6nrYXz` (agent context webhook), agent's `checkContext` tool via webhook.
**Retention:** 90 days (combined with `prune-old-sessions` cron at 03:30 UTC).

---

#### session_context

**DDL** (`database/session_context_migration.sql`):
```sql
CREATE TABLE IF NOT EXISTS session_context (
    id            BIGSERIAL PRIMARY KEY,
    session_id    TEXT NOT NULL,
    context_key   TEXT NOT NULL,
    context_value TEXT,
    expires_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (session_id, context_key)
);
```

**Indexes:**
```sql
idx_session_context_session_id  ON session_context(session_id)
idx_session_context_expires_at  ON session_context(expires_at)
```

**Writes from:**
- `voice-agent-poc/relay-server/index-enhanced.js` — `SessionCache.setContext()` (write-through pattern)
- n8n Launcher workflow `kUcUSyPgz4Z9mYBt` — session dedup guard (`launcher_meeting_` + session_id, 3-hour TTL)

**Reads from:** `relay-server/index-enhanced.js` — `SessionCache.getContext()` (read-through: memory → PG)
**TTL expiry:** Cron job `expire-session-context` every 6 hours: `DELETE FROM session_context WHERE expires_at < NOW()`
**Gotcha:** Rows without `expires_at` never expire. n8n launcher sets 3-hour TTL explicitly.

---

#### tool_calls

**DDL** (`database/tool_calls_migration.sql`):
```sql
CREATE TABLE IF NOT EXISTS tool_calls (
    id                  BIGSERIAL PRIMARY KEY,
    tool_call_id        TEXT UNIQUE,           -- NULL for Composio-sourced rows
    session_id          TEXT,
    user_id             TEXT,
    intent_id           TEXT,                  -- correlation ID from voice agent
    source              TEXT NOT NULL DEFAULT 'n8n',  -- 'n8n' | 'composio'
    function_name       TEXT NOT NULL,
    parameters          JSONB,
    status              TEXT NOT NULL DEFAULT 'EXECUTING',
    callback_url        TEXT,
    result              JSONB,
    voice_response      TEXT,
    success             BOOLEAN,
    error_message       TEXT,
    execution_time_ms   INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    CONSTRAINT valid_status CHECK (status IN ('EXECUTING', 'COMPLETED', 'FAILED', 'CANCELLED'))
);
```

**Indexes:**
```sql
idx_tool_calls_tool_call_id  ON tool_calls(tool_call_id)
idx_tool_calls_session       ON tool_calls(session_id)
idx_tool_calls_source        ON tool_calls(source)
idx_tool_calls_created       ON tool_calls(created_at DESC)
idx_tool_calls_status        ON tool_calls(status)
idx_tool_calls_function      ON tool_calls(function_name)
```

**Writes from:** n8n workflow `z02K1a54akYXMkyj` (vector DB workflow); also backfilled from `composio_tool_log` via migration.
**Reads from:** `relay-server/index-enhanced.js` — `SessionCache.getRecentTools()` queries `tool_calls WHERE session_id = $1 AND status IN ('COMPLETED', 'FAILED', 'CANCELLED') ORDER BY created_at DESC LIMIT 20`
**Stalled row cleanup:** Cron `timeout-stalled-tool-calls` every hour: sets `status='FAILED', error_message='Timed out'` for `status='EXECUTING' AND created_at < NOW() - INTERVAL '15 minutes'`

---

#### composio_tool_log (legacy — superseded by tool_calls)

**DDL** (`database/composio_tool_log_migration.sql`):
```sql
CREATE TABLE IF NOT EXISTS composio_tool_log (
    id            BIGSERIAL   PRIMARY KEY,
    user_id       TEXT,
    source        TEXT        NOT NULL DEFAULT 'composio',
    slug          TEXT        NOT NULL,
    arguments     JSONB,
    result_data   JSONB,
    voice_result  TEXT,
    success       BOOLEAN     NOT NULL,
    error_message TEXT,
    duration_ms   INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Wrote 25 rows as of 2026-03-04 audit. Fully migrated into `tool_calls` via `tool_calls_migration.sql` Section 3. New code should write to `tool_calls`, not this table. Retained for historical queries only.

---

### Writing to Railway PG

Two patterns are used. The choice is determined by whether the write is on the hot path:

**Pattern 1 — Fire-and-forget (hot path writes):**
```python
# pg_logger.py — never blocks the agent event loop
asyncio.create_task(
    pg_logger.log_turn(session_id, "user", text, user_id=user_id)
)
asyncio.create_task(
    pg_logger.log_session_start(session_id, user_id=user_id, room_name=room_name)
)
```

**Pattern 2 — Awaited at teardown (session-end writes that must complete):**
```python
# At session disconnect — blocking, must complete before worker cleanup
await session_facts.flush_facts_to_db(
    session_id=session_id,
    postgres_url=settings.postgres_url,
    user_id=user_id,
)
await pg_logger.log_session_end(
    session_id=session_id,
    user_id=user_id,
    summary=summary,
    message_count=message_count,
    tool_call_count=tool_call_count,
)
```

**Exact function signatures from pg_logger.py:**
```python
async def init_pool(postgres_url: str) -> None: ...
async def log_turn(
    session_id: str,
    role: str,
    content: str,
    tool_name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None: ...
async def log_session_start(
    session_id: str,
    user_id: Optional[str] = None,
    room_name: Optional[str] = None,
) -> None: ...
async def log_session_end(
    session_id: str,
    user_id: Optional[str] = None,
    summary: Optional[str] = None,
    message_count: int = 0,
    tool_call_count: int = 0,
) -> None: ...
async def close_pool() -> None: ...
```

**session_facts.py flush signature:**
```python
async def flush_facts_to_db(
    session_id: str,
    postgres_url: Optional[str],
    user_id: str = "_default",
) -> None: ...
```

### Reading from Railway PG

The agent does NOT query Railway PG directly during conversations. All reads are mediated by the n8n Agent Context workflow.

**Pattern:** `agent_context_tool.py` fires an HTTP POST to `ouWMjcKzbj6nrYXz` webhook:
```
POST {N8N_WEBHOOK_BASE_URL}/agent-context
Body: { "session_id": "...", "intent_id": "..." }
```
The n8n workflow uses the `NI3jbq1U8xPst3j3` credential to query `conversation_log` and returns the last N turns as JSON. The `checkContext` tool in the agent calls this webhook and surfaces results to the LLM.

---

## 3. SQLite Per-User Memory Store

### Connection

| Field | Value |
|---|---|
| Path pattern | `{AIO_MEMORY_DIR}/users/{user_id}/aio-voice-memory.sqlite` |
| Env var | `AIO_MEMORY_DIR` (default: `/app/data/memory`) |
| Config field | `settings.memory_dir` (src/config.py line 72) |
| Enabled flag | `AIO_MEMORY_ENABLED` (default: `True`) |
| Module | `src/memory/memory_store.py` |
| Connection model | Per-call `sqlite3.connect(db_path)` — no persistent connection |
| Threading | Module-level `threading.Lock()` (`_lock`) for all write operations |
| WAL mode | Enabled on schema creation: `PRAGMA journal_mode=WAL` |

The singleton is reinitialized per user via `memory_store.reinit_for_user(user_id)` at session start, which resolves the per-user path and calls `_create_schema()`.

### Actual Schema (verified from `_create_schema()`, memory_store.py lines 155-316)

#### memories table

```sql
CREATE TABLE IF NOT EXISTS memories (
    id          TEXT PRIMARY KEY,           -- UUID4 string
    text        TEXT NOT NULL,              -- raw text (NOT "content" — never confuse these)
    text_safe   TEXT NOT NULL,              -- html.escape(text, quote=True) — safe for LLM injection
    category    TEXT NOT NULL DEFAULT 'general',
    importance  REAL NOT NULL DEFAULT 0.5,
    source      TEXT NOT NULL DEFAULT 'auto',
    embedding   TEXT,                       -- JSON-serialized float list OR NULL
    created_at  INTEGER NOT NULL            -- Unix epoch timestamp (int(time.time()))
    -- user_id TEXT  ← added via ALTER TABLE with PRAGMA guard
    -- session_id TEXT  ← added via ALTER TABLE with PRAGMA guard
)
```

CRITICAL column naming: the text column is `text`, not `content`. The column `text_safe` holds the HTML-escaped version injected into agent context. Both are always stored; search returns `text_safe`.

`user_id` and `session_id` are NOT in the CREATE TABLE DDL. They are added via `ALTER TABLE` during `_create_schema()` with a `PRAGMA table_info` guard to prevent "duplicate column" races on multi-worker startup.

`created_at` is `INTEGER` Unix epoch — NOT `TEXT`, NOT `TIMESTAMPTZ`. When surfaced to callers, it is an integer seconds-since-epoch.

`embedding` is always JSON (a serialized `list[float]`) or NULL when embedder unavailable. It is NOT used for search — it is stored for deduplication checks only (last 100 rows scanned by `_is_near_duplicate()`).

**Runtime indexes (created after ALTER TABLE confirmation):**
```sql
idx_memories_user_id   ON memories(user_id)
idx_memories_session_id ON memories(session_id)
```

**Important:** Per-user isolation is at FILE LEVEL — each user has a separate `.sqlite` file at `users/{user_id}/aio-voice-memory.sqlite`. The `user_id` column in rows should match the file path but is NOT enforced or filtered on during searches. `search()` does not pass `user_id` into the SQL `WHERE` clause — the file-level partition is sufficient.

#### memories_fts (virtual FTS5 table)

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    text,
    id          UNINDEXED,
    category    UNINDEXED,
    content     = 'memories',
    content_rowid = 'rowid'
)
```

Content table backed by `memories`. Three triggers (`memories_ai`, `memories_ad`, `memories_au`) keep FTS in sync with INSERT/DELETE/UPDATE on `memories`. Tokenizer is FTS5 default (`unicode61`).

#### deep_store table

```sql
CREATE TABLE IF NOT EXISTS deep_store (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL DEFAULT '_default',
    label      TEXT,
    content    TEXT NOT NULL,             -- no size limit
    session_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))   -- ISO 8601 string, NOT Unix epoch
    -- embedding TEXT  ← added via ALTER TABLE with PRAGMA guard; always NULL
)
```

Note `created_at` is `TEXT` ISO 8601 (SQLite `datetime('now')`) — different from `memories.created_at` which is `INTEGER` Unix epoch. The `embedding` column is always NULL — deep_store vectors live only in pgvector (`source='deep_store'`).

**Runtime indexes:**
```sql
idx_deep_store_user_id   ON deep_store(user_id)
idx_deep_store_created_at ON deep_store(created_at)
```

#### session_summaries table

This table is fully implemented but not documented anywhere in the skill files.

```sql
CREATE TABLE IF NOT EXISTS session_summaries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL UNIQUE,
    user_id       TEXT NOT NULL DEFAULT '_default',
    summary       TEXT NOT NULL,
    topics        TEXT NOT NULL DEFAULT '[]',   -- JSON list of topic strings
    message_count INTEGER NOT NULL DEFAULT 0,
    embedding     TEXT,                         -- JSON float list or NULL
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
)
```

**Index:**
```sql
idx_ss_user_created ON session_summaries(user_id, created_at DESC)
```

Written by `memory_store.py` → `store_session_summary()` (line ~993). Queried by `search_session_summaries()` (line ~1010) and loaded into the system prompt via `load_memory_context()` as the last 2 session summaries. Budget-capped at 500 tokens.

### Writing to SQLite

**`store()` signature** (memory_store.py lines 337-410):
```python
def store(
    text: str,
    category: str = "general",
    importance: float = 0.5,
    source: str = "auto",
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[str]:
    """Returns entry UUID on success, None on rejection or failure."""
```

Rejection conditions (returns None without writing):
1. `_looks_like_injection(text)` — matches prompt injection patterns
2. Near-duplicate: cosine similarity > 0.95 with any of the last 100 stored embeddings
3. Embedder unavailable AND dedup check cannot run (allowed through in this case)

Text is truncated to 1000 chars before storage (`MAX_MEMORY_TEXT_LEN = 1000`).

Dual-write sequence:
1. SQLite `INSERT INTO memories` — synchronous, under `_lock`
2. `asyncio.ensure_future(_pgvector.pgvector_save(...))` — fire-and-forget, runs in background
3. Embedding is generated ONCE before the lock: `embedding = embedder.embed(text)`, passed to both writes

**`deep_store_save()` signature** (memory_store.py lines 819-877):
```python
def deep_store_save(
    content: str,
    label: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: str = "_default",
) -> int:
    """Returns row id (AUTOINCREMENT integer) on success, 0 on failure."""
```

No size limit on content. No deduplication check. Importance hardcoded to 0.9 in pgvector write.

### Reading from SQLite

**`search()` signature** (memory_store.py lines 460-522):
```python
def search(
    query: str,
    top_k: int = DEFAULT_TOP_K,   # DEFAULT_TOP_K = 3
    category: Optional[str] = None,
    user_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Returns list of dicts: {id, text_safe, category, score, created_at}
    text_safe is HTML-entity escaped — safe to inject into agent context.
    created_at is Unix epoch INTEGER.
    """
```

Search routing logic (memory_store.py lines 484-522):
1. If `_pgvector.is_available()` → call `_search_via_pgvector()` (HNSW + FTS5 hybrid merge)
2. If pgvector unavailable OR returns empty → SQLite brute-force: `_vector_search()` + `_bm25_search()`
3. Merge scores: `final = 0.7 * vector_score + 0.3 * bm25_score`
4. Apply temporal decay: `score × e^(-ln(2)/halfLife × age_days)` (half-life in `TEMPORAL_HALF_LIFE_DAYS`)
5. Filter: `final < MIN_SCORE (0.25)` → excluded

**`deep_store_search()` signature** (memory_store.py lines 880-935):
```python
def deep_store_search(
    query: str,
    label: Optional[str] = None,
    limit: int = 10,
    user_id: str = "_default",
) -> list[dict[str, Any]]:
    """
    Returns: [{id, label, content, session_id, created_at}, ...]
    content is NOT escaped — raw text. Full content returned, no truncation.
    Search is LIKE-based (not vector/BM25) — simple substring match.
    """
```

Deep store search is `content LIKE %query%` OR `label LIKE %query%`. There is no semantic search for deep_store results; pgvector is write-only for deep_store (source='deep_store') and the vectors are not yet queried back by `deep_store_search()`.

---

## 4. pgvector Semantic Memory

### Connection

| Field | Value |
|---|---|
| Host | `pgvector-memory.railway.internal:5432` (Railway internal VPC — no public TCP) |
| DB | `aio_vectors` |
| User | `aio` |
| Env var | `PGVECTOR_URL` |
| Config field | `settings.pgvector_url` (src/config.py line 63) — `Optional[str]`, defaults `None` |
| Pool impl | asyncpg pool in `src/utils/pgvector_store.py` |
| Pool config | `min_size=1, max_size=3` (no `command_timeout` — different from pg_logger pool) |
| Singleton | Module-level `_pool` — initialized once at worker boot |

Pool is initialized in a daemon thread during `prewarm()` in `agent.py`:
```python
asyncio.ensure_future(pgvector_store.init_pgvector_pool(settings.pgvector_url))
```

If `PGVECTOR_URL` is not set, `pgvector_store.is_available()` returns `False` and all calls are no-ops. SQLite brute-force search activates transparently as fallback.

### Actual Schema (from `_ensure_schema()`, pgvector_store.py lines 65-117)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS aio_memories (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT        NOT NULL DEFAULT '_default',
    session_id  TEXT,
    content     TEXT        NOT NULL,
    label       TEXT,
    category    TEXT,
    source      TEXT        NOT NULL DEFAULT 'capture',
    importance  REAL        NOT NULL DEFAULT 0.5,    -- NOT 1.0 — confirmed 0.5
    embedding   vector(384) NOT NULL,                -- fastembed all-MiniLM-L6-v2
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata    JSONB
);
```

Note: `importance DEFAULT 0.5` — not 1.0. `deep_store_save()` overrides to 0.9 explicitly.

**Indexes:**
```sql
-- HNSW ANN index: cosine distance, m=16 links/node, ef_construction=64
CREATE INDEX IF NOT EXISTS aio_memories_hnsw
ON aio_memories USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Scalar filter indexes
CREATE INDEX IF NOT EXISTS aio_memories_user_idx     ON aio_memories (user_id);
CREATE INDEX IF NOT EXISTS aio_memories_user_source_idx ON aio_memories (user_id, source);
CREATE INDEX IF NOT EXISTS aio_memories_created_idx  ON aio_memories (created_at DESC);
```

`ef_search` is NOT set at query time — relies on the server's `hnsw.ef_search` default (~40). Higher `ef_search` improves recall at cost of latency; can be set per-session with `SET hnsw.ef_search = 100` if needed.

Schema creation is idempotent and concurrent-safe: each DDL statement is individually wrapped in try/except catching `"already exists"` / `"duplicate"`. Concurrent workers racing during startup converge safely.

### Writing to pgvector

**`pgvector_save()` signature** (pgvector_store.py lines 129-169):
```python
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
    """Returns inserted row id (BIGINT) or None on failure."""
```

Dual-write pattern from `memory_store.store()`:
```python
# Embedding generated ONCE before SQLite write
embedding = embedder.embed(text)

# 1. SQLite write — synchronous under threading.Lock
conn.execute("INSERT INTO memories ...", (entry_id, text, text_safe, ..., embedding_json, ...))
conn.commit()

# 2. pgvector write — fire-and-forget in background
# Note: second near-duplicate check here. First check was before SQLite INSERT.
# The second check catches the case where the just-inserted SQLite row would
# itself be a near-duplicate — intentional extra guard.
if not _is_near_duplicate(embedding):
    asyncio.ensure_future(
        _pgvector.pgvector_save(
            content=text,
            embedding=embedding if isinstance(embedding, list) else list(embedding),
            user_id=user_id or "_default",
            session_id=session_id,
            category=category,
            source="capture",
            importance=importance,
        )
    )
```

The embedding vector is serialized to pgvector format via `_vec_to_pg()`:
```python
def _vec_to_pg(embedding: list) -> str:
    return "[" + ",".join(f"{float(v):.8f}" for v in embedding) + "]"
```

### Reading from pgvector

**`pgvector_search()` signature** (pgvector_store.py lines 176-222):
```python
async def pgvector_search(
    query_embedding: list,
    user_id: str = "_default",
    top_k: int = 15,
    source_filter: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Tuple[str, str, float, str, object]]:
    """
    Returns: [(content, category, similarity_score, source, created_at), ...]
    similarity_score: float in [0,1] — 1 - (embedding <=> query_vec)
    created_at: datetime object (TIMESTAMPTZ from Postgres), NOT Unix epoch
    """
```

The `WHERE` clause is built dynamically. With `user_id` and `category` both set:
```sql
SELECT content, category, source, created_at,
       1 - (embedding <=> $1::vector) AS similarity
FROM aio_memories
WHERE user_id = $2 AND category = $3
ORDER BY embedding <=> $1::vector
LIMIT $4
```

The `_search_via_pgvector()` function in memory_store.py calls pgvector from a sync context by bridging into asyncio via `ThreadPoolExecutor` (when loop is running) or `loop.run_until_complete()` (when called from non-async context). It requests `top_k * 3` results from pgvector, then merges with FTS5 BM25 scores.

**3-tier search routing summary** (memory_store.py `search()` function):
```
Tier 1 (pgvector path):
  pgvector.is_available() AND query_embedding is not None
  → _search_via_pgvector()
      → pgvector HNSW cosine (top_k * 3 candidates)
      → SQLite FTS5 BM25 (top_k * 4 candidates)
      → merge by content string: 0.7 * v_score + 0.3 * t_score
      → if pgvector returns EMPTY → fall through to Tier 2

Tier 2 (SQLite brute-force cosine):
  query_embedding is not None
  → _vector_search(): scan embeddings column (all rows, O(n))
  → results: {id: cosine_similarity}

Tier 3 (FTS5 BM25):
  always runs alongside Tier 2
  → _bm25_search(): FTS5 match(), rank column (BM25)
  → results: {id: bm25_score}

Final merge:
  0.7 * vector_score + 0.3 * bm25_score
  → _apply_temporal_decay() per candidate
  → MIN_SCORE = 0.25 cutoff
  → sort descending, return top_k
```

### Important Nuances

- pgvector is **internal-only** — no TCP proxy configured, no public URL. Cannot `psql` from dev machine. Cannot use `railway connect` (only works for Railway managed databases, not custom Docker services).
- Verify connectivity via Railway logs: `"pgvector: pool initialized, schema ready"`
- `created_at` in pgvector search results is a `datetime` object from asyncpg, NOT Unix epoch integer. `_search_via_pgvector()` converts it: `int(raw_created_at.timestamp())` with a fallback to `0` on error.
- Category filter works correctly in pgvector path (fixed 2026-03-04). Prior to fix, category was silently dropped.
- Near-duplicate check for pgvector: `store()` runs `_is_near_duplicate()` twice — once before SQLite INSERT, once before the `ensure_future`. The second check is intentional: it prevents duplicate pgvector rows when two concurrent sessions store similar content.

---

## 5. Relay Supabase (bot_state — read-only)

### Connection

| Field | Value |
|---|---|
| Env vars | `SUPABASE_URL`, `SUPABASE_ANON_KEY` |
| Used in | `voice-agent-poc/relay-server/index-enhanced.js` |
| Access method | `fetch()` to Supabase REST API (not `@supabase/supabase-js` SDK) |
| Auth headers | `'apikey': SUPABASE_ANON_KEY`, `'Authorization': 'Bearer {SUPABASE_ANON_KEY}'` |
| Timeout | 5 second `AbortSignal.timeout(5000)` on every request |

### Schema (inferred from relay query patterns)

The relay server never creates or alters this table. Schema is inferred from SELECT column lists and filter patterns:

| Column | Type (inferred) | Notes |
|---|---|---|
| bot_id | TEXT | Written by n8n launcher workflow `kUcUSyPgz4Z9mYBt` |
| bot_name | TEXT | Bot name / interrupt trigger word |
| session_id | TEXT | LiveKit session identifier |
| meeting_url | TEXT | Teams/Zoom meeting URL for Recall.ai |
| status | TEXT | Values: 'active', 'joining', 'created', and terminal states |
| created_at | TIMESTAMPTZ | Used for ordering (most recent first) |

n8n launcher workflow `kUcUSyPgz4Z9mYBt` is the ONLY writer for this table.

### Access Patterns

Three distinct patterns are used with different filter columns:

**Pattern 1 — `getBotStateFromSupabase(sessionId)`** (relay-server, line 907):
```
GET /rest/v1/bot_state?session_id=eq.{sessionId}&select=bot_id,bot_name,meeting_url,status,created_at&order=created_at.desc&limit=1
```
Filters by `session_id`. Called when the relay has a valid client-provided `sessionId`.

**Pattern 2 — `getLatestActiveBotFromSupabase()`** (relay-server, line 951):
```
GET /rest/v1/bot_state?status=in.(active,joining,created)&select=bot_id,bot_name,session_id,meeting_url,status,created_at&order=created_at.desc&limit=1
```
Filters by `status IN ('active', 'joining', 'created')`. Used as fallback when session_id lookup returns nothing.

**Pattern 3 — `SessionCache.getBotState()`** (relay-server, line 334):
```javascript
// Extracts bot_id from session_id (strips "_session" suffix)
const botId = this.sessionId.replace('_session', '');
// GET /rest/v1/bot_state?bot_id=eq.{botId}&limit=1
```
Filters by `bot_id`. Used by the in-process cache miss path.

All three patterns return `data[0]` and cache it in `SessionCache.botStateCache` with 2-hour TTL.

### Important Nuances

- Relay is **READ-ONLY** to Supabase — it never INSERTs or UPDATEs. n8n launcher workflow `kUcUSyPgz4Z9mYBt` owns all writes.
- Supabase lookups are on the **blocking connection path** — `getBotStateFromSupabase()` and `getLatestActiveBotFromSupabase()` are called during WebSocket connection setup (relay-server lines 1833-1842) with 5-second timeout. A Supabase outage or slow response adds up to 10 seconds to session start latency.
- No stale row cleanup exists — expired rows with `status='active'` will be returned by Pattern 2 as "latest active bot" even after the session ended. This can cause incorrect bot_state association.
- Three patterns use different filter columns (`session_id` vs `status` vs `bot_id`). A schema change to any of these columns breaks the corresponding pattern independently.
- Future refactor tracked: `bot_state` should migrate to Railway PG (`session_context` table) to eliminate Supabase dependency on the hot path.

---

## 6. Cross-Database Data Flow

### Session Lifecycle (complete write sequence)

```
T=0ms   Room join detected
        → asyncio.create_task(pg_logger.log_session_start(session_id, user_id, room_name))
          Railway PG: INSERT INTO sessions (ON CONFLICT DO NOTHING)

T=0ms   WebSocket connection from relay-server browser client
        → relay: getBotStateFromSupabase(sessionId) [BLOCKING, up to 5s]
          Supabase: SELECT FROM bot_state WHERE session_id = $1

T=0ms   capture.reset_session()      — clear pending facts queue
        capture.set_user_id(user_id) — bind user to capture context

T=Ns    User speaks (on_conversation_item_added fires)
        → capture.detect_and_queue(text) — regex pattern match, queue if triggered
        → asyncio.create_task(pg_logger.log_turn(session_id, "user", text, user_id=user_id))
          Railway PG: INSERT INTO conversation_log (fire-and-forget)

T=Ns    Agent processes, responds
        → asyncio.create_task(pg_logger.log_turn(session_id, "assistant", text, user_id=user_id))
          Railway PG: INSERT INTO conversation_log (fire-and-forget)

T=Ns    deepStore tool called
        → asyncio.to_thread(memory_store.deep_store_save, content, label, session_id, user_id)
          SQLite: INSERT INTO deep_store (sync, under threading.Lock)
          asyncio.ensure_future(pgvector_save(content, embedding, source="deep_store", importance=0.9))
          pgvector: INSERT INTO aio_memories (fire-and-forget)

T=Ns    session_facts.store_fact(session_id, key, value)
        → in-memory dict only (no DB write mid-session)

T=end   Room disconnecting
        → await session_facts.flush_facts_to_db(session_id, postgres_url, user_id)
          Railway PG: UPSERT INTO session_facts_log (ON CONFLICT(session_id,key) DO UPDATE)
          [AWAITED — must complete]

        → capture.flush_to_store(memory_store)
          SQLite: INSERT INTO memories for each queued capture fact
          pgvector: pgvector_save() for each (asyncio.ensure_future)

        → await pg_logger.log_session_end(session_id, user_id, summary, msg_count, tool_count)
          Railway PG: UPSERT INTO sessions
          [AWAITED — must complete]

        → memory_store.flush_session() → _append_to_memory_md()
          Filesystem: append to {user_dir}/MEMORY.md
```

### Memory Search Path

When the agent calls `recall(query)` → `memory_store.search(query_text, top_k=5, category=..., user_id=...)`:

```
search() called
│
├── Step 1: query_embedding = embedder.embed(query_text)
│   (fastembed ONNX all-MiniLM-L6-v2 → 384-dim float list)
│
├── Step 2: Route decision
│   if _pgvector.is_available() and query_embedding is not None:
│       → _search_via_pgvector()
│           │
│           ├── [Thread pool] asyncio.run(pgvector_search(
│           │       query_embedding, user_id, top_k*3, category))
│           │   Returns: [(content, category, similarity, source, created_at), ...]
│           │
│           ├── if pg_rows is EMPTY:
│           │   → fall through to SQLite brute-force (same as no-pgvector path)
│           │
│           └── SQLite FTS5 BM25: _bm25_search(query, top_k*4, category)
│               Returns: {sqlite_id: bm25_score, ...}
│               [Fetch content text for BM25 hits to enable content-string join]
│
│           Merge by content string:
│           final = 0.7 * pg_similarity + 0.3 * bm25_score
│           → filter MIN_SCORE=0.25
│           → sort descending
│           → return top_k as [{id, text_safe, category, score, created_at}, ...]
│
└── else (no pgvector):
    ├── _vector_search(query_embedding, top_k*4, category)
    │   Scans ALL embeddings in SQLite (O(n) cosine), returns {id: similarity}
    │
    ├── _bm25_search(query, top_k*4, category)
    │   FTS5 match(), returns {id: bm25_score}
    │
    ├── Merge: final = 0.7 * v_score + 0.3 * t_score
    ├── _apply_temporal_decay(final, created_at) per candidate
    ├── filter MIN_SCORE=0.25
    └── return top_k sorted results
```

---

## 7. Efficient Access Patterns

### Add a conversation log entry

```python
# Never blocks agent event loop
asyncio.create_task(
    pg_logger.log_turn(
        session_id,
        "user",          # or "assistant", "tool", "system"
        text,
        tool_name=None,  # populate for role="tool" rows
        user_id=user_id,
    )
)
```

### Search memory

```python
# Returns top-k results, handles pgvector/SQLite routing automatically
results = memory_store.search(
    query_text,
    top_k=5,
    category="preference",  # optional — one of: preference, decision, fact, general
    user_id=user_id         # scopes to user's .sqlite file (file-level partition)
)
# Each result dict:
# {
#   "id": str,                  # UUID (SQLite) or "pgv:{hash}" (pgvector path)
#   "text_safe": str,           # HTML-entity escaped — safe for LLM injection
#   "category": str,
#   "score": float,             # 0.0–1.0 final weighted score
#   "created_at": int           # Unix epoch integer
# }
```

### Store a memory fact

```python
# Dual-writes to SQLite + pgvector automatically
# Embedding generated once, passed to both
entry_id = memory_store.store(
    text=fact_text,
    category="preference",   # preference, decision, fact, general
    importance=0.8,
    source="auto",           # "auto" for auto-capture, "explicit" for user-commanded stores
    user_id=user_id,
    session_id=session_id,
)
# Returns UUID str on success, None if rejected (duplicate/injection/error)
```

### Deep store content

```python
# Called via asyncio.to_thread() from deep_store_async tool (no size limit)
row_id = memory_store.deep_store_save(
    content=large_content,
    label="descriptive label",
    session_id=session_id,
    user_id=user_id,
)
# Returns int row id on success, 0 on failure
```

### Flush session facts to DB

```python
# At session end ONLY — opens raw asyncpg connection (not from pg_logger pool)
await session_facts.flush_facts_to_db(
    session_id=session_id,
    postgres_url=settings.postgres_url,
    user_id=user_id,          # DEFAULT '_default' — must pass actual user_id
)
```

### Store a session fact (in-memory, mid-session)

```python
# In-process only — no DB write until flush_facts_to_db() at session end
session_facts.store_fact(session_id, "gammaUrl", "https://...")
session_facts.store_fact(session_id, "gammaGenerationId", "gen_abc123")
value = session_facts.get_fact(session_id, "gammaUrl")  # Returns str or None
```

### Query Railway PG directly (n8n workflow pattern)

n8n `HTTP Request` node POSTs to webhook `ouWMjcKzbj6nrYXz`. The workflow uses credential `NI3jbq1U8xPst3j3` to query `conversation_log`:

```
POST https://jayconnorexe.app.n8n.cloud/webhook/agent-context
Body: { "session_id": "lk_...", "intent_id": "..." }
→ n8n queries: SELECT * FROM conversation_log WHERE session_id = $1 ORDER BY created_at DESC LIMIT 20
→ Returns: { turns: [...], facts: [...], session: {...} }
```

Agent code calls this via `agent_context_tool.py` (the `checkContext` LLM tool).

### Access pgvector from agent code

```python
# pgvector has NO public URL. Never call from dev machine.
# Only callable from within Railway worker code:
from src.utils import pgvector_store as _pgvector

# Check availability before calling
if _pgvector.is_available():
    results = await _pgvector.pgvector_search(
        query_embedding=embedding_list,
        user_id=user_id,
        top_k=15,
        category="preference",     # optional
        source_filter="capture",   # optional
    )
    # Results: [(content, category, similarity, source, created_at_datetime), ...]

    # Diagnostics
    count = await _pgvector.pgvector_count(user_id=user_id)
```

### Access Railway PG from dev machine

```bash
# Retrieve connection string from Railway environment
railway variables --service livekit-voice-agent | grep POSTGRES_URL

# Connect directly
psql "postgresql://user:pass@host/db?sslmode=require"

# Useful diagnostic queries:
SELECT role, COUNT(*) FROM conversation_log GROUP BY role;
SELECT * FROM sessions ORDER BY started_at DESC LIMIT 10;
SELECT * FROM session_facts_log WHERE session_id = 'lk_xxx';
```

### pgvector diagnostics (Railway logs only — no psql access)

```bash
# Verify pool init at worker startup — look for:
# [INFO] pgvector: pool initialized, schema ready
# [INFO] pgvector: pool already initialized, skipping re-init  (subsequent workers)
railway logs --service pgvector-memory

# Within agent code:
count = await pgvector_store.pgvector_count(user_id="_default")
```

---

## 8. Maintenance Procedures

### Required cron jobs (as of 2026-03-04)

These are defined in `database/20260304_maintenance_cron_jobs.sql` for `pg_cron`. Railway managed PostgreSQL may not support `pg_cron` — if not available, implement as n8n Schedule trigger workflows using credential `NI3jbq1U8xPst3j3`.

| Job Name | Schedule | SQL | Purpose |
|---|---|---|---|
| `expire-session-context` | `0 */6 * * *` (every 6h) | `DELETE FROM session_context WHERE expires_at < NOW()` | Purge TTL-expired dedup rows from n8n launcher |
| `timeout-stalled-tool-calls` | `0 * * * *` (every 1h) | `UPDATE tool_calls SET status='FAILED', error_message='Timed out', completed_at=NOW() WHERE status='EXECUTING' AND created_at < NOW() - INTERVAL '15 minutes'` | Mark ghost EXECUTING rows as FAILED |
| `prune-conversation-log` | `0 3 * * *` (daily 03:00 UTC) | `DELETE FROM conversation_log WHERE created_at < NOW() - INTERVAL '90 days'` | 90-day retention on ~750 rows/day |
| `close-orphaned-sessions` | `15 3 * * *` (daily 03:15 UTC) | `UPDATE sessions SET ended_at = started_at + INTERVAL '4 hours' WHERE ended_at IS NULL AND started_at < NOW() - INTERVAL '4 hours'` | Mark crashed-session rows as ended |
| `prune-old-sessions` | `30 3 * * *` (daily 03:30 UTC) | `DELETE FROM sessions WHERE created_at < NOW() - INTERVAL '90 days'; DELETE FROM session_facts_log WHERE created_at < NOW() - INTERVAL '90 days'` | 90-day retention for sessions + facts |

### SQLite maintenance

Run when db file exceeds ~50MB (check at session start via `os.path.getsize`):

```python
import sqlite3
with sqlite3.connect(db_path) as conn:
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # Flush WAL to main file
    conn.execute("VACUUM")                            # Defragment and shrink
    # VACUUM rebuilds entire DB — do not run during active writes
```

### pgvector maintenance

Weekly `VACUUM ANALYZE` on `aio_memories` reduces table bloat and updates planner statistics. Cannot run from dev machine (no public TCP). Options:

1. Via `pg_cron` on the pgvector-memory Railway service (if available):
   ```sql
   SELECT cron.schedule('weekly-vacuum-aio', '0 4 * * 0',
     'VACUUM ANALYZE aio_memories');
   ```
2. Via Railway worker code at session start (run at most once per week, tracked in SQLite):
   ```python
   await conn.execute("VACUUM ANALYZE aio_memories")
   ```

### HNSW index rebuild (if recall degrades over time)

```sql
-- Rebuild HNSW index after large bulk inserts to restore search quality
REINDEX INDEX aio_memories_hnsw;
```

---

## 9. Known Issues and Fixes (2026-03-04)

Issues identified during the 2026-03-04 database audit session, with status:

| # | Severity | Issue | Status |
|---|---|---|---|
| 1 | CRITICAL | `conversation_log` missing `user_id` column — pg_logger writes `user_id` but original DDL omitted it | FIXED — `20260304_fix_conversation_log_user_id.sql` |
| 2 | CRITICAL | `session_facts_log` missing `UNIQUE(session_id, key)` constraint — every `flush_facts_to_db()` call raises `ON CONFLICT` error, all session facts silently never persisted | FIXED — `20260304_fix_session_facts_log_unique.sql` |
| 3 | HIGH | pgvector `_search_via_pgvector()` hardcoded `created_at=0` — all pgvector search results returned with epoch 0 instead of actual timestamp | FIXED — 2026-03-04 (memory_store.py `int(raw_created_at.timestamp())` conversion) |
| 4 | HIGH | pgvector `pgvector_search()` silently dropped `category` filter — `category` kwarg was not wired into the WHERE clause builder | FIXED — 2026-03-04 (pgvector_store.py `category` condition added to dynamic WHERE) |
| 5 | HIGH | Near-duplicate check NOT applied to pgvector writes — `store()` ran dedup before SQLite but did not re-check before `ensure_future` → duplicate embeddings in pgvector | FIXED — 2026-03-04 (second `_is_near_duplicate()` check added before `ensure_future`) |
| 6 | HIGH | 5 Railway PG maintenance cron jobs absent — orphaned sessions, stalled tool_calls, unbounded table growth all unmanaged | FIXED — `20260304_maintenance_cron_jobs.sql` created (pending application if `pg_cron` available; else implement as n8n schedules) |
| 7 | HIGH | WebSocket connections to relay-server lack auth — `SESSION_SECRET` env var references a non-existent token; any client can connect without credentials | OPEN — pending auth middleware implementation |
| 8 | HIGH | `session_context` never cleaned up without cron job — `expire-session-context` cron not yet applied to Railway | OPEN — pending `pg_cron` availability or n8n schedule implementation |
| 9 | MEDIUM | `tool_calls` stalled EXECUTING rows accumulate — `timeout-stalled-tool-calls` cron not yet applied | OPEN — same as above |
| 10 | MEDIUM | Supabase `bot_state` has no stale row cleanup — expired `status='active'` rows returned as latest active bot indefinitely | OPEN — requires n8n launcher to update status to terminal value on session end |
| 11 | MEDIUM | `deep_store_search()` uses LIKE-based search only — no semantic/vector recall for deep_store items despite vectors being written to pgvector | OPEN — pgvector vectors for `source='deep_store'` are written but never queried back by `deep_store_search()` |
| 12 | LOW | `session_summaries` SQLite table is fully implemented but undocumented in all skill files — `store_session_summary()` and `search_session_summaries()` are called but not surfaced in any tool or system prompt documentation | OPEN — document and surface in agent tool registry |

---

## Appendix: Environment Variables Reference

All database-related env vars resolved via `src/config.py` (pydantic Settings):

| Env Var | Config Field | Default | Purpose |
|---|---|---|---|
| `POSTGRES_URL` | `settings.postgres_url` | `""` | Railway PG — conversation_log, sessions, session_facts_log, session_context, tool_calls |
| `PGVECTOR_URL` | `settings.pgvector_url` | `None` | pgvector-memory Railway service — aio_memories |
| `AIO_MEMORY_DIR` | `settings.memory_dir` | `/app/data/memory` | SQLite base directory — per-user files at `{dir}/users/{user_id}/aio-voice-memory.sqlite` |
| `AIO_MEMORY_ENABLED` | `settings.memory_enabled` | `True` | Master switch for SQLite memory layer |
| `AIO_MODELS_DIR` | `settings.models_dir` | `/app/models` | fastembed ONNX model cache — `FASTEMBED_CACHE_PATH` should match this |
| `SUPABASE_URL` | (relay-server only) | `null` | Supabase project URL for bot_state reads |
| `SUPABASE_ANON_KEY` | (relay-server only) | `null` | Supabase anon key for REST API auth |
| `DATABASE_URL` | (relay-server only) | required | Railway PG URL for relay-server `pg.Pool` (separate pool from agent's asyncpg pool) |
