# Streaming Context Protocol - Cache Control Flags Reference

Quick reference for downstream nodes consuming Process Transcript output.

---

## Output Fields

| Field | Type | Description | Usage |
|-------|------|-------------|-------|
| `use_cached_context` | boolean | **Primary flag** - If true, use `cached_history` instead of DB query | Check this FIRST in downstream nodes |
| `cached_history` | array | Cached DB rows from previous load | Use when `use_cached_context === true` |
| `accumulated_transcript` | string | All chunks concatenated this session | For full context without DB query |
| `context_age_ms` | number | Milliseconds since cache was populated | Monitor cache freshness |
| `chunk_number` | number | Current chunk count (1-indexed) | Track streaming progress |
| `cache_invalidation_reason` | string | Why cache was invalidated (or 'cache_valid') | Debugging/monitoring |

---

## Cache Invalidation Reasons

| Reason | Meaning | Action Downstream |
|--------|---------|-------------------|
| `cache_valid` | Cache is fresh and usable | Use `cached_history` directly |
| `first_message` | New session started | Load from DB, populate cache |
| `cache_expired` | >30 seconds since last cache update | Load from DB, refresh cache |
| `route_changed_to_process` | User completed thought after waiting | Load from DB, refresh cache |

---

## Downstream Integration Pattern

### Pattern 1: Switch Before DB Load (Recommended)

```
Process Transcript
    ↓
    IF (use_cached_context)
    ├─ TRUE  → Build Agent Context (use cached_history)
    └─ FALSE → Load Bot State (DB) → Build Agent Context (populate cache)
```

**Implementation:**
- Add Switch/If node after Process Transcript
- Condition: `{{ $json.use_cached_context }}`
- True path: Skip DB, go to Build Agent Context
- False path: Execute DB load

### Pattern 2: Smart Code Node

Replace "Load Bot State" with:

```javascript
const pt = $input.first().json;

if (pt.use_cached_context && pt.cached_history.length > 0) {
  // Return cached data
  return pt.cached_history.map(row => ({ json: row }));
}

// Execute DB query
const db = await $executeWorkflow({
  workflowId: 'THIS_WORKFLOW_ID',
  nodeName: 'Load Bot State Original',
  data: [$input.item]
});

// Populate cache for next chunk
const staticData = $getWorkflowStaticData('global');
const botState = staticData.botTranscripts[pt.bot_id];
if (botState) {
  botState.cachedHistory = db.map(item => item.json);
  botState.cachedHistoryTime = Date.now();
  botState.contextValid = true;
}

return db;
```

---

## Cache Population (in Build Agent Context)

When fresh data IS loaded, update the cache:

```javascript
// After loading from DB
const staticData = $getWorkflowStaticData('global');
const processTranscript = $('Process Transcript').first().json;
const bot_id = processTranscript.bot_id;

if (staticData.botTranscripts && staticData.botTranscripts[bot_id]) {
  const botState = staticData.botTranscripts[bot_id];

  // Store fresh data in cache
  botState.cachedHistory = historyRows;        // DB query result
  botState.cachedHistoryTime = Date.now();     // Current timestamp
  botState.contextValid = true;                // Mark cache as valid
}
```

---

## Monitoring Cache Effectiveness

Add monitoring to track cache hit rate:

```javascript
// In Build Agent Context or monitoring node
const pt = $('Process Transcript').first().json;

console.log({
  chunk: pt.chunk_number,
  cache_hit: pt.use_cached_context,
  cache_age_ms: pt.context_age_ms,
  invalidation_reason: pt.cache_invalidation_reason
});
```

Expected output:
```
{ chunk: 1, cache_hit: false, cache_age_ms: 0, invalidation_reason: 'first_message' }
{ chunk: 2, cache_hit: true, cache_age_ms: 1234, invalidation_reason: 'cache_valid' }
{ chunk: 3, cache_hit: true, cache_age_ms: 2456, invalidation_reason: 'cache_valid' }
...
{ chunk: 10, cache_hit: false, cache_age_ms: 31000, invalidation_reason: 'cache_expired' }
```

---

## Cache Configuration

Current settings in Process Transcript:

```javascript
const CACHE_MAX_AGE_MS = 30000; // 30 seconds
```

**Tuning recommendations:**
- **Faster conversations:** Reduce to 15000ms (15s)
- **Slower conversations:** Increase to 60000ms (60s)
- **Balance:** 30000ms (current) works for most use cases

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Cache always false | Downstream not populating cache | Add cache population code to Build Agent Context |
| Cache never expires | System clock issue | Check `Date.now()` consistency |
| Stale context | Cache age too long | Reduce `CACHE_MAX_AGE_MS` |
| Too many DB queries | Cache age too short | Increase `CACHE_MAX_AGE_MS` |
| Cache invalidation spam | Route changes rapidly | Add debouncing to route detection |

---

## Performance Metrics to Track

1. **Cache hit rate:** `(cache_hits / total_chunks) × 100`
2. **Average cache age:** Mean of `context_age_ms` when cache hits
3. **DB query reduction:** `(1 - queries_after / queries_before) × 100`
4. **Latency improvement:** Compare avg chunk processing time

**Target metrics:**
- Cache hit rate: >70% (for multi-chunk conversations)
- DB query reduction: >75%
- Latency improvement: >60%

---

## Example Flow

### Conversation Timeline

```
Time  | Chunk | Route      | Cache Action
------|-------|------------|---------------------------
0.0s  | 1     | WAIT_LOG   | MISS - first_message → Load DB
1.2s  | 2     | WAIT_LOG   | HIT  - cache_valid (age: 1.2s)
2.5s  | 3     | PROCESS    | MISS - route_changed_to_process → Load DB
4.0s  | 4     | WAIT_LOG   | HIT  - cache_valid (age: 1.5s)
5.5s  | 5     | WAIT_LOG   | HIT  - cache_valid (age: 3.0s)
35.0s | 6     | PROCESS    | MISS - cache_expired (age: 31s) → Load DB
```

**Result:**
- 6 chunks processed
- 3 DB queries (chunks 1, 3, 6)
- 3 cache hits (chunks 2, 4, 5)
- Cache hit rate: 50%
- DB query reduction: 50%

---

## Related Files

- **Implementation doc:** `/Users/jelalconnor/CODING/N8N/Workflows/.reference/streaming-context-protocol-implementation.md`
- **Enhanced code:** `/tmp/process-transcript-enhanced.js`
- **Workflow ID:** `d3CxEaYk5mkC8sLo`
