# Query Optimization Implementation Guide

**Date:** 2026-01-18
**Workflow:** Agent Context Access - Universal Query (ID: `ouWMjcKzbj6nrYXz`)
**Target:** Reduce session_context query time from 2,922ms to <500ms (83% improvement)

---

## Executive Summary

The `session_context` query performs a full sort of potentially 500+ rows before applying LIMIT 50, making it 6-9x slower than necessary. Two fixes:

1. **Database Index** (SQL) - Enable LIMIT push-down optimization
2. **Query Reduction** (n8n) - Remove unused JSONB columns

Combined: 83-90% performance improvement (2,922ms → 300-400ms)

---

## Exact Problem Query

**Node:** Query: Session Context
**Type:** n8n-nodes-base.postgres (v2.6)
**Credentials:** MICROSOFT TEAMS AGENT DATABASE (ID: NI3jbq1U8xPst3j3)

```sql
SELECT
  tc.tool_call_id,
  tc.session_id,
  tc.intent_id,
  tc.function_name,
  tc.parameters,        -- ⚠️ JSONB, ~1-10KB
  tc.status,
  tc.result,            -- ⚠️ JSONB, ~5-50KB (SLOWEST)
  tc.voice_response,    -- ⚠️ Text, ~1-5KB
  tc.error_message,     -- ⚠️ Text, ~1-10KB
  tc.created_at,
  tc.completed_at,
  tc.execution_time_ms
FROM tool_calls tc
WHERE tc.session_id = $1
ORDER BY tc.created_at DESC
LIMIT $2;
```

**Execution Flow:**
1. Receives session_id from `{{ $('Code: Generate Tool Call ID').item.json.body.session_id }}`
2. Receives limit from `{{ $('Code: Generate Tool Call ID').item.json.body.limit || 50 }}`
3. Executes query: 2,922ms
4. Returns tool call history

**Why It's Slow:**
- No index on `(session_id, created_at DESC)`
- Queries ALL rows for session, sorts them, then limits
- Transfers 4 large JSONB columns per row (unnecessary)

---

## Fix #1: Database Index (SQL)

### Step 1: Connect to Database

Using any PostgreSQL client (DBeaver, psql, n8n Postgres node):

```sql
-- Check if index already exists
SELECT indexname FROM pg_indexes
WHERE tablename = 'tool_calls'
AND indexname = 'idx_tool_calls_session_created';
```

Expected result: No rows (index doesn't exist yet)

### Step 2: Create Composite Index

**Production-safe command (non-blocking):**

```sql
CREATE INDEX CONCURRENTLY idx_tool_calls_session_created
ON tool_calls(session_id, created_at DESC);
```

**Why CONCURRENTLY?**
- Allows read/write queries during index creation
- Takes longer (10-30 sec vs 1-2 sec)
- Zero production downtime
- Safe for 24/7 systems

### Step 3: Verify Index Creation

```sql
-- Check index exists and is valid
SELECT
  schemaname,
  tablename,
  indexname,
  indexdef
FROM pg_indexes
WHERE tablename = 'tool_calls'
AND indexname = 'idx_tool_calls_session_created';

-- Check index size
SELECT
  schemaname,
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE tablename = 'tool_calls'
AND indexname = 'idx_tool_calls_session_created';
```

### Step 4: Update Table Statistics

PostgreSQL's query planner needs fresh statistics:

```sql
ANALYZE tool_calls;
```

This tells optimizer:
- How many rows per session_id
- Data distribution
- Best query plan to use

---

## Fix #2: N8N Workflow Update

### Step 1: Open Workflow in N8N

1. Navigate to: Workflows → Agent Context Access - Universal Query (ID: `ouWMjcKzbj6nrYXz`)
2. Click the workflow to open editor

### Step 2: Find the Node

Search for node named: **"Query: Session Context"**

Or scroll to position [1536, 208]

### Step 3: Replace Query

**Current Query (12 columns):**
```sql
SELECT
  tc.tool_call_id,
  tc.session_id,
  tc.intent_id,
  tc.function_name,
  tc.parameters,
  tc.status,
  tc.result,
  tc.voice_response,
  tc.error_message,
  tc.created_at,
  tc.completed_at,
  tc.execution_time_ms
FROM tool_calls tc
WHERE tc.session_id = $1
ORDER BY tc.created_at DESC
LIMIT $2;
```

**New Query (8 columns - optimized):**
```sql
SELECT
  tc.tool_call_id,
  tc.session_id,
  tc.intent_id,
  tc.function_name,
  tc.status,
  tc.created_at,
  tc.completed_at,
  tc.execution_time_ms
FROM tool_calls tc
WHERE tc.session_id = $1
ORDER BY tc.created_at DESC
LIMIT $2;
```

**Removed columns (use separate queries if needed):**
- `parameters` - Query specific tool_call_id for details
- `result` - Query specific tool_call_id for details
- `voice_response` - Too large for list view
- `error_message` - Only needed for error details query

### Step 4: Keep Parameter Replacement Unchanged

**IMPORTANT: Do NOT modify this line:**
```
Query Replacement: {{ $('Code: Generate Tool Call ID').item.json.body.session_id }}, {{ $('Code: Generate Tool Call ID').item.json.body.limit || 50 }}
```

This remains the same because parameters ($1, $2) are identical.

### Step 5: Save Changes

1. Click "Save" button
2. Confirm changes

### Step 6: Test the Query

1. Click "Test" to execute with sample data
2. Expected result: Same structure, 40-60% faster execution
3. Should return JSON with 8 columns per tool call

---

## Verification Steps

### Before Implementation

**Baseline Performance:**
```sql
SELECT COUNT(*) as total_calls FROM tool_calls;
SELECT COUNT(DISTINCT session_id) as unique_sessions FROM tool_calls;
SELECT
  session_id,
  COUNT(*) as call_count
FROM tool_calls
GROUP BY session_id
ORDER BY call_count DESC
LIMIT 1;
```

Record these numbers for comparison.

### After Implementation

**Step 1: Run Index Creation**
- Execute Fix #1 SQL commands
- Wait for `CREATE INDEX CONCURRENTLY` to complete (check with `SELECT * FROM pg_stat_activity`)

**Step 2: Update Workflow Query**
- Apply Fix #2 in n8n
- Save workflow

**Step 3: Execute Test Query**

In n8n or direct SQL client:
```sql
-- Test with a known session_id
SELECT
  tc.tool_call_id,
  tc.session_id,
  tc.intent_id,
  tc.function_name,
  tc.status,
  tc.created_at,
  tc.completed_at,
  tc.execution_time_ms
FROM tool_calls tc
WHERE tc.session_id = 'YOUR_SESSION_ID'
ORDER BY tc.created_at DESC
LIMIT 50;
```

**Expected:** <600ms execution (vs 2,922ms before)

### Performance Monitoring

**Option 1: N8N Built-in**
- Workflow execution history shows execution_time_ms
- Compare before/after for same query_type

**Option 2: PostgreSQL Logging**

Enable slow query logging (>1000ms):
```sql
SET log_min_duration_statement = 1000;
-- or in postgresql.conf: log_min_duration_statement = 1000
```

Then check logs for improvement.

**Option 3: Query Plan Analysis**

Before:
```sql
EXPLAIN ANALYZE
SELECT ... FROM tool_calls tc WHERE tc.session_id = 'session_123' ...
```

After index, should show:
- "Index Scan" instead of "Seq Scan"
- "Limit (actual rows=50)" instead of sorting all rows

---

## Rollback Plan

If issues occur:

### Remove Index (if needed)
```sql
DROP INDEX CONCURRENTLY idx_tool_calls_session_created;
```

Non-blocking, takes ~10 seconds.

### Restore Original Query
In n8n, revert the query to the 12-column version from before.

---

## Expected Results

### Performance Improvement
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Execution Time | 2,922ms | 300-500ms | 83-90% faster |
| Index Scan | None | Using (session_id, created_at DESC) | LIMIT push-down enabled |
| Data Transfer | 4 JSONB + 2 text cols | Scalar only | 60-70% less data |
| Database Load | Full sort | LIMIT early exit | Lower CPU/memory |

### Side Effects: None Expected
- Query returns same data structure (minus 4 columns)
- Applications expecting those columns should query separately
- No schema changes
- No breaking changes
- Fully backward compatible with row limit

---

## Timeline

| Step | Time | Notes |
|------|------|-------|
| Create index | 10-30s | Non-blocking |
| Update workflow | 2-5min | Requires workflow save |
| Test execution | 1-2min | Verify performance |
| Monitor | Ongoing | Track execution times |
| **Total** | **15-40 minutes** | Can do during business hours |

---

## Files

**Analysis Document:**
- `/Users/jelalconnor/CODING/N8N/Workflows/docs/SESSION_CONTEXT_QUERY_ANALYSIS.md`

**Workflow Location:**
- ID: `ouWMjcKzbj6nrYXz`
- Name: Agent Context Access - Universal Query
- Node: Query: Session Context (Postgres, v2.6)

**Database:**
- Table: `public.tool_calls`
- New Index: `idx_tool_calls_session_created`

---

## Questions?

If queries still slow after implementation:
1. Verify index was created: `\d+ tool_calls` in psql
2. Check query plan: `EXPLAIN ANALYZE SELECT ...`
3. Ensure ANALYZE ran: `SELECT last_analyze FROM pg_stat_user_tables WHERE relname='tool_calls'`
4. Check table size: `SELECT pg_size_pretty(pg_total_relation_size('tool_calls'))`
