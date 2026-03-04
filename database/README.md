# AIO Voice System — Database Migrations

Railway PostgreSQL credential: `NI3jbq1U8xPst3j3`

---

## Naming Convention

```
YYYYMMDD_<snake_case_description>.sql
```

- Date prefix guarantees chronological ordering.
- All migrations must be **idempotent** — safe to replay on a live database without side effects.
- Use `IF NOT EXISTS`, `DO $$ BEGIN IF NOT EXISTS ... END $$`, and `ON CONFLICT` guards throughout.

---

## How to Apply a Migration

### Option 1 — psql via POSTGRES_URL (recommended)

```bash
psql "$POSTGRES_URL" -f database/20260304_fix_conversation_log_user_id.sql
```

Set `POSTGRES_URL` from Railway dashboard: **livekit-voice-agent** service → Variables → `POSTGRES_URL`.

### Option 2 — Railway CLI interactive session

```bash
railway connect --service postgresql
# Once in psql, paste the file contents or use \i
\i /path/to/migration.sql
```

### Option 3 — Apply all pending migrations in order

```bash
for f in database/*.sql; do
  echo "Applying $f ..."
  psql "$POSTGRES_URL" -f "$f"
done
```

---

## Migration Registry

### Critical Migrations (apply immediately on schema drift)

| File | Priority | Description |
|------|----------|-------------|
| `20260304_fix_conversation_log_user_id.sql` | **CRITICAL** | Adds missing `user_id` column to `conversation_log` + 3 performance indexes. Without this, `pg_logger.py` write failures and full table scans on per-user queries. |
| `20260304_fix_session_facts_log_unique.sql` | **CRITICAL** | Adds `UNIQUE(session_id, key)` constraint to `session_facts_log`. Without this, `flush_facts_to_db()` ON CONFLICT upsert raises an error on every session end — Gamma URLs and cross-session facts are never persisted. |

### Optional / Infrastructure Migrations

| File | Priority | Description |
|------|----------|-------------|
| `20260304_maintenance_cron_jobs.sql` | **OPTIONAL** | Registers 5 pg_cron scheduled jobs for session expiry, tool call timeout, and 90-day log pruning. Degrades gracefully if pg_cron is unavailable on Railway managed PG. |

### Foundation Migrations (applied at initial setup)

| File | Priority | Description |
|------|----------|-------------|
| `tool_calls_migration.sql` | Foundation | Creates `tool_calls` audit table (`id BIGSERIAL`, `tool_call_id`, `session_id`, `user_id`, `function_name`, `parameters JSONB`, `status`, `callback_url`, `result JSONB`, `voice_response`, `success`, `error_message`, `execution_time_ms`, `created_at`, `completed_at`). |
| `session_context_migration.sql` | Foundation | Creates `session_context(context_key PK, context_value, expires_at, created_at)`. Used by the n8n Launcher dedup workflow (`kUcUSyPgz4Z9mYBt`) to enforce 3-hour TTL guards against duplicate session starts. |
| `conversation_log_migration.sql` | Foundation | Creates `conversation_log` base schema. NOTE: `user_id` column is absent from this file — apply `20260304_fix_conversation_log_user_id.sql` immediately after. |
| `session_facts_log_migration.sql` | Foundation | Creates `session_facts_log(id, session_id, user_id DEFAULT '_default', key, value, created_at)`. NOTE: UNIQUE constraint may be missing — apply `20260304_fix_session_facts_log_unique.sql` after. |
| `sessions_migration.sql` | Foundation | Creates `sessions(id, session_id UNIQUE, user_id, room_name, started_at, ended_at, message_count, tool_call_count, summary, metadata, created_at)`. Written by `pg_logger.log_session_start` / `log_session_end`. |
| `composio_tool_log_migration.sql` | Foundation | Creates `composio_tool_log` for Composio direct call audit trail (~25 rows total as of 2026-03-04). Separate from `tool_calls`. |
| `perplexity_searches_migration.sql` | Foundation | Creates `perplexity_searches` table for Perplexity search result caching/audit. |
| `pgvector_migration.sql` | Foundation | Creates `aio_memories` table with `embedding vector(384)` column and HNSW index (cosine, m=16, ef=64). Targets the pgvector-memory Railway service (`postgresql://aio:...@pgvector-memory.railway.internal:5432/aio_vectors`), NOT the main Railway PostgreSQL instance. |

---

## Schema Quick Reference

```sql
-- Key tables on Railway PostgreSQL (NI3jbq1U8xPst3j3)
tool_calls             -- Tool execution audit (function_name/parameters, NOT tool_name/input_json)
session_context        -- n8n Launcher dedup guard (3-hour TTL rows)
conversation_log       -- Async conversation log via pg_logger.py (~750 rows/day)
session_facts_log      -- Cross-session key-value facts (Gamma URLs, generation IDs)
sessions               -- Session lifecycle metadata (start/end/counts)
composio_tool_log      -- Composio direct call audit
perplexity_searches    -- Perplexity search cache/audit

-- Separate pgvector service (pgvector-memory.railway.internal:5432 / db: aio_vectors)
aio_memories           -- 384-dim embeddings (HNSW), dual-write from SQLite FTS5
```

---

## Notes

- **Never drop columns** on live tables — use nullable additions only.
- **Schema drift check**: Compare `information_schema.columns` against migration files when debugging silent write failures.
- **pg_cron availability**: Railway managed PostgreSQL does not always support pg_cron. The `20260304_maintenance_cron_jobs.sql` migration handles this gracefully via a NOTICE.
- **pgvector migrations** (`pgvector_migration.sql`) target the separate `pgvector-memory` service — do not apply to the main Railway PostgreSQL instance.
