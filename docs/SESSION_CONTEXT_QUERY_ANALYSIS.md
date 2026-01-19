# Session Context Query Performance Analysis

**Workflow:** Agent Context Access - Universal Query (ID: `ouWMjcKzbj6nrYXz`)
**Issue:** session_context query takes 2,922ms vs 341-809ms for other queries
**Root Cause:** Missing index + excessive JSONB column selection

---

## The Slow Query (2,922ms)

**Node:** Query: Session Context

```sql
SELECT
  tc.tool_call_id,
  tc.session_id,
  tc.intent_id,
  tc.function_name,
  tc.parameters,              -- ⚠️ JSONB - expensive
  tc.status,
  tc.result,                  -- ⚠️ JSONB - expensive
  tc.voice_response,          -- ⚠️ Large text
  tc.error_message,           -- ⚠️ Large text
  tc.created_at,
  tc.completed_at,
  tc.execution_time_ms
FROM tool_calls tc
WHERE tc.session_id = $1
ORDER BY tc.created_at DESC
LIMIT $2;
```

**Parameters:**
- `$1`: session_id (from request body)
- `$2`: limit (default: 50)

**Workflow Integration:**
- Located in n8n workflow as "Query: Session Context" Postgres node
- Triggers when query_type = 'session_context'
- Returns tool call history for a specific session

---

## Performance Comparison

| Query | Type | Columns | Exec Time | Index? |
|-------|------|---------|-----------|--------|
| Session Context | SELECT | 12 (4 JSONB) | **2,922ms** | ❌ Missing |
| Tool History | SELECT | 9 (fewer JSONB) | 341-809ms | ✓ Likely using |
| Default Activity | SELECT | 2 (uses json_agg) | ~500ms | ✓ LIMIT 10 |

---

## Root Cause Analysis

### Problem 1: Missing Composite Index ⚠️ PRIMARY

The query filters by `session_id` then sorts by `created_at DESC`. PostgreSQL needs:

**Current behavior (without index):**
1. Full table scan OR inefficient session_id-only scan
2. Collect ALL matching rows in memory
3. Sort entire result set by created_at DESC
4. Apply LIMIT 50 (after sort - too late!)

**With proper index:**
1. Use `(session_id, created_at DESC)` index
2. Retrieve rows already sorted
3. Apply LIMIT 50 (stops after 50 rows!)
4. Return immediately

**Evidence:** 2,922ms execution time indicates full sort of large dataset.

### Problem 2: Excessive JSONB Column Selection ⚠️ HIGH IMPACT

Selecting 4 JSONB columns plus large text fields:

- `parameters` - Stores webhook body JSON (could be 1-10KB)
- `result` - Stores AI model response JSON (could be 5-50KB)
- `voice_response` - Large audio transcription text
- `error_message` - Error stack traces

**Why this matters:**
- JSONB columns require deserialization on fetch
- Transferring large objects over network
- 4x memory usage vs scalar columns

**Comparison:**
- Tool History query excludes: parameters, error_message (faster)
- Default query uses `json_agg()` at DB layer (aggregates at source)

### Problem 3: No Query Statistics

PostgreSQL optimizer may lack:
- Row count distribution by session_id
- Average result set size
- Column cardinality

Result: Suboptimal query plan selection

### Problem 4: Missing LIMIT Optimization

Without the index, query executes:
```
SORT (all 500+ rows for session)
├─ FILTER by session_id
└─ LIMIT 50 (applied AFTER sort)
```

Instead of:
```
LIMIT 50
└─ INDEX SCAN (session_id, created_at DESC)
```

---

## Solutions

### ✅ Solution 1: Create Composite Index (HIGH PRIORITY)

```sql
CREATE INDEX CONCURRENTLY idx_tool_calls_session_created
ON tool_calls(session_id, created_at DESC);
```

**Why this fixes it:**
- Allows LIMIT push-down (PostgreSQL stops at 50 rows)
- Rows already sorted by created_at
- No full sort required
- Expected speedup: 60-80% (2,922ms → 600-1,200ms)

**Note:** `CONCURRENTLY` allows production queries to continue during index creation

### ✅ Solution 2: Reduce Column Selection (HIGH PRIORITY)

Update the n8n node query to:

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

**Removed columns:**
- `parameters` - Store separately or query by specific tool_call_id
- `result` - Store separately or query by specific tool_call_id
- `voice_response` - Not needed for context list
- `error_message` - Only useful for error queries

**Expected savings:** 50-70% network transfer, 40-50% execution time

**Client impact:** If applications need these fields, they can:
1. Query specific tool_call_id for full details
2. Or call a separate "get_tool_call_details" query

### ✅ Solution 3: Update Table Statistics (MEDIUM PRIORITY)

```sql
ANALYZE tool_calls;
```

Ensures query planner has current statistics. Run after:
- Large data loads
- Index creation
- After 10%+ table change

### ✅ Solution 4: Verify Session Distribution (DIAGNOSTIC)

Before implementing fixes, confirm data distribution:

```sql
SELECT
  session_id,
  COUNT(*) as call_count,
  AVG(OCTET_LENGTH(parameters::text)) as avg_params_size,
  AVG(OCTET_LENGTH(result::text)) as avg_result_size,
  MAX(created_at) as latest_call
FROM tool_calls
GROUP BY session_id
ORDER BY call_count DESC
LIMIT 20;
```

This shows:
- How many calls per session (determines index benefit)
- JSONB column sizes (determines benefit of column reduction)

---

## Expected Performance Improvements

### With Index Only
```
Before: 2,922ms
After:  600-1,200ms (60-65% faster)
Reason: LIMIT push-down, no full sort
```

### With Column Reduction Only
```
Before: 2,922ms
After:  1,200-1,800ms (40-55% faster)
Reason: Less data to transfer/deserialize
```

### With Both Index + Column Reduction
```
Before: 2,922ms
After:  300-500ms (83-90% faster)
Reason: LIMIT push-down + reduced data size
```

---

## Implementation Steps

### Step 1: Create Index (Production - No Downtime)
```bash
# From n8n Postgres node or direct SQL client
CREATE INDEX CONCURRENTLY idx_tool_calls_session_created
ON tool_calls(session_id, created_at DESC);
```

### Step 2: Update Workflow Node
Edit "Query: Session Context" node in n8n workflow:
- Update SQL query (remove 4 columns listed above)
- Test with sample session_id
- Verify execution time < 1 second

### Step 3: Analyze & Monitor
```sql
ANALYZE tool_calls;
```

Monitor subsequent executions - should see 60-90% speedup.

### Step 4: Optional - Archive Old Sessions
If tool_calls table is very large (>10M rows), consider:
- Archive sessions older than 30 days to separate table
- Partition tool_calls by created_at month
- See "Session Archive" query in workflow for reference

---

## Files Affected

**N8N Workflow:**
- `/Users/jelalconnor/CODING/N8N/Workflows/[workflow-export].json`
- Node: "Query: Session Context" (Postgres operation)

**Database:**
- Table: `public.tool_calls`
- Columns: session_id, created_at (index), parameters, result, voice_response, error_message

---

## Monitoring

After implementation, track in n8n:
- Workflow execution times per query type
- Database connection pool utilization
- Slow query log (queries > 1000ms)

The workflow already captures execution_time_ms for each tool call - use this metric to verify improvement.
