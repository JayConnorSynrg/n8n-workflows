-- AIO pgvector semantic memory — Railway Postgres migration
-- Run once against Railway Postgres NI3jbq1U8xPst3j3
-- Requires Postgres 16+ (Railway default) with pgvector extension available
--
-- pgvector is available on Railway Postgres by default on Postgres 16.
-- Embeddings are 384-dim float32 from fastembed all-MiniLM-L6-v2 model.
-- HNSW index provides sub-linear ANN search (vs brute-force cosine on SQLite).

-- Step 1: Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Create aio_memories table
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
);

-- Step 3: HNSW index for fast cosine similarity (ANN search)
-- m=16: num bidirectional links per node (higher = better recall, more memory)
-- ef_construction=64: size of dynamic candidate list during build
-- vector_cosine_ops: cosine distance operator (<=>)
CREATE INDEX IF NOT EXISTS aio_memories_hnsw
ON aio_memories USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Step 4: Filter indexes for per-user queries and source-type filtering
CREATE INDEX IF NOT EXISTS aio_memories_user_idx
ON aio_memories (user_id);

CREATE INDEX IF NOT EXISTS aio_memories_user_source_idx
ON aio_memories (user_id, source);

CREATE INDEX IF NOT EXISTS aio_memories_created_idx
ON aio_memories (created_at DESC);

-- Verify
SELECT 'aio_memories table ready' AS status,
       COUNT(*) AS existing_rows
FROM aio_memories;
