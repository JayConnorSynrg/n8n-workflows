# pgvector Session Store — Future Implementation

**Status:** Planned (not implemented)
**Priority:** Medium — required before department-scale deployment
**Estimated scope:** 3-4 days implementation, 1 day migration

---

## Architecture Context: Two-Layer Memory

The AIO Voice System uses two distinct memory layers with different purposes. This doc covers only the second layer.

| Layer | Storage | Purpose | Scope |
|-------|---------|---------|-------|
| **Agent Learning Memory** | SQLite (`aio-voice-memory.sqlite`) | OpenClaw approach — agent learns the user. Stores preferences, behavioral patterns, SOUL.md, USER.md, extracted facts. Personal assistant memory. | Per-user, per-worker (intentionally local) |
| **Session Store** *(this doc)* | pgvector on Railway PostgreSQL | Full session data — conversation transcripts, tool call logs, semantic search across historical sessions. Enterprise audit + cross-session recall. | Shared, all workers |

These are not alternatives — they serve different functions. SQLite remains the agent learning layer. pgvector is additive.

---

## Problem Being Solved

### What SQLite Cannot Do at Scale

SQLite is the right tool for the OpenClaw agent learning layer because it is:
- Fast, local, zero-latency reads
- Appropriate for small per-user fact stores
- Simple to operate for a single-worker setup

But it cannot:
- Share data across Railway replicas (each container has its own volume)
- Survive redeployments without an explicitly configured persistent volume
- Support semantic search across all users' sessions
- Enable cross-department query (e.g., "what issues has the team raised this week")

### What pgvector Adds

A shared Postgres table with a `vector(384)` column enables:
- Semantic search across all historical sessions for a given user
- Cross-session recall without the per-worker isolation problem
- Full audit trail surviving redeployments
- Department-level analytics and reporting

---

## Target Architecture

```
LiveKit Worker 1  ─────┐
LiveKit Worker 2  ─────┼──── pgvector (Railway Postgres) ──── Shared session store
LiveKit Worker N  ─────┘
                              │
                         SQLite (per-worker)
                         Agent learning memory (unchanged)
```

Each worker continues to write OpenClaw learning data to its local SQLite. Additionally, each worker writes session turns + embeddings to the shared pgvector store.

---

## Schema Design

### Enable Extension
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Railway PostgreSQL almost certainly supports it. Verify with:
```sql
SELECT * FROM pg_available_extensions WHERE name = 'vector';
```

### Core Tables

```sql
-- Full session transcript with semantic embeddings
CREATE TABLE session_turns (
    id              BIGSERIAL PRIMARY KEY,
    user_id         TEXT        NOT NULL,
    session_id      TEXT        NOT NULL,
    role            TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT        NOT NULL,
    embedding       vector(384),          -- all-MiniLM-L6-v2 or API equivalent
    tool_calls      JSONB,                -- tool calls made on this turn (if role=assistant)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Session-level metadata
CREATE TABLE session_metadata (
    session_id      TEXT        PRIMARY KEY,
    user_id         TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    turn_count      INTEGER     DEFAULT 0,
    tool_call_count INTEGER     DEFAULT 0,
    summary         TEXT,                 -- LLM-generated summary on session end
    summary_vector  vector(384)
);

-- Indexes
CREATE INDEX ON session_turns (user_id, created_at DESC);
CREATE INDEX ON session_turns USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON session_metadata (user_id, started_at DESC);
CREATE INDEX ON session_metadata USING hnsw (summary_vector vector_cosine_ops);
```

### Why HNSW over IVFFlat
HNSW (Hierarchical Navigable Small World) builds incrementally — no need to know the dataset size upfront. IVFFlat requires a training pass with representative data. For a growing department store, HNSW is the correct choice.

---

## Embedding Strategy

### Option A: Keep Local Model (Current)
Use the same `all-MiniLM-L6-v2` already loaded for the SQLite layer. Zero additional API calls. Works while the model is loaded.

**Problem:** The embedder is now unloaded at session end. Writing embeddings requires the model to be loaded, which means it stays loaded until the write completes. Adds complexity to the shutdown flow.

### Option B: Fireworks Embedding API (Recommended)
Fireworks already has an active API key in the system. They offer `nomic-ai/nomic-embed-text-v1.5` at `$0.008/1M tokens` — negligible cost for voice sessions.

```python
# Rough implementation
response = fireworks_client.embeddings.create(
    model="nomic-ai/nomic-embed-text-v1.5",
    input=text
)
embedding = response.data[0].embedding  # 768 dims — requires schema adjustment
```

**Note:** Nomic embed is 768 dims, not 384. Schema would need `vector(768)` if using this. Alternatively Fireworks offers smaller models.

### Option C: OpenAI `text-embedding-3-small`
OpenAI API key already in the system. `text-embedding-3-small` is 1536 dims by default, reducible to 384 via the `dimensions` parameter.

```python
response = openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=text,
    dimensions=384  # matches current SQLite schema
)
```

**Recommendation:** Option C for schema compatibility, Option B for cost.

---

## Query Patterns

### Semantic Recall (Cross-Session)
```sql
-- "What did we discuss about the Q3 report?"
SELECT content, role, created_at, session_id
FROM session_turns
WHERE user_id = $1
  AND created_at > NOW() - INTERVAL '90 days'
ORDER BY embedding <-> $2  -- $2 is the query embedding
LIMIT 10;
```

### Recent Session Summary
```sql
SELECT summary, started_at, turn_count
FROM session_metadata
WHERE user_id = $1
ORDER BY started_at DESC
LIMIT 5;
```

### Department-Level (No user filter)
```sql
-- "What issues has the team raised this week?"
SELECT user_id, content, created_at
FROM session_turns
WHERE created_at > NOW() - INTERVAL '7 days'
  AND role = 'user'
ORDER BY embedding <-> $1
LIMIT 20;
```

---

## Integration Points in Current Codebase

### Write Path (per turn)
Location: `src/utils/pg_logger.py` (already exists, currently logs to `conversation_log`)

Extend `pg_logger.py` to also write to `session_turns` with embedding. Embed asynchronously — do not block the voice response.

```python
# Non-blocking fire-and-forget
asyncio.create_task(_write_turn_with_embedding(session_id, user_id, role, content))
```

### Read Path (cross-session recall)
New function in `pg_logger.py` or a dedicated `session_store.py`:
```python
async def semantic_search(user_id: str, query: str, limit: int = 10) -> list[dict]:
    ...
```

Called from a new agent tool: `crossSessionRecall` — distinct from the existing `recall` tool (which reads SQLite).

### Session End Summary
At session end (currently in agent.py finally block), generate a summary via Fireworks and write to `session_metadata.summary` + `summary_vector`. This enables semantic search at session granularity (faster, cheaper than turn-level for broad queries).

---

## Implementation Steps

1. **Verify pgvector available** on Railway Postgres — `SELECT * FROM pg_available_extensions WHERE name = 'vector'`
2. **Run migration SQL** — create tables + indexes (add to `database/` folder)
3. **Choose embedding strategy** — recommend OpenAI `text-embedding-3-small` with `dimensions=384` for schema compatibility
4. **Extend `pg_logger.py`** — add async `write_turn()` with embedding, fire-and-forget pattern
5. **Add `crossSessionRecall` tool** — query semantic search, register in `ASYNC_TOOLS`
6. **Add session summary on end** — generate + store in `session_metadata` at finally block
7. **Update system prompt** — instruct agent when to use `crossSessionRecall` vs `recall` (SQLite)

---

## What Does NOT Change

- SQLite agent learning layer — OpenClaw SOUL.md, USER.md, extracted facts, preference tracking — unchanged
- `memory_store.py`, `embedder.py`, `session_writer.py` — unchanged
- Per-user directory structure at `/app/data/memory/users/{user_id}/` — unchanged
- The `recall` tool — still reads from SQLite (fast, low-latency, personal)
- The `deepStore` / `deepRecall` tools — still SQLite

The SQLite and pgvector layers are **additive**, not a migration.

---

## Deployment Considerations

- **Railway Postgres** (`NI3jbq1U8xPst3j3`) is already shared across all workers — no new infrastructure required
- **pgvector extension**: Enable once via psql or Railway dashboard
- **Volume risk**: The existing Docker volume at `/app/data/memory` is per-replica. The pgvector store removes the dependency on it for session data. SQLite will still need a sticky-session strategy or acceptance of per-worker learning divergence at scale.
- **Sticky sessions**: If 1 user always hits the same Railway replica, the SQLite learning layer works fine. Railway does not guarantee this without explicit sticky routing. For a small department (< 20 users, 2-3 replicas), the probability of hitting the same replica is high enough to be acceptable in practice.

---

## Scale Estimate After Implementation

| Users | SQLite only | + pgvector session store |
|-------|-------------|--------------------------|
| 1-5 | Works | Works |
| 10-20 concurrent | Inconsistent cross-session recall | Consistent recall, shared data |
| 50 (department) | Memory fragmented across replicas | Full shared history, audit trail |
| 200+ | Not viable | Needs table partitioning by `user_id` hash |

---

**Last updated:** 2026-02-24
**Author:** AIO Voice System dev session
**Related docs:** `AIO-TOOLS-REGISTRY.md`, `../database/conversation_log_migration.sql`
