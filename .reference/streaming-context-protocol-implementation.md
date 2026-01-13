# Streaming Context Protocol Implementation

**Date:** 2026-01-09
**Workflow:** Teams Voice Bot v3.0 - Agent Orchestrator (d3CxEaYk5mkC8sLo)
**Node Updated:** Process Transcript (process-transcript)

---

## Problem Solved

**Before:** Every chunk triggered a database query to "Load Bot State" node (4 rows), causing 200-500ms latency per chunk even for mid-conversation chunks that didn't need fresh context.

**After:** Process Transcript now manages a session cache and signals downstream nodes whether to use cached context or load fresh from database.

---

## Implementation Details

### New Session State Fields

Added to `staticData.botTranscripts[bot_id]`:

```javascript
{
  // Existing fields (unchanged)
  lastProcessedTranscript: '',
  lastProcessedTime: 0,
  processingCount: 0,
  sessionStartTime: now,
  lastOrchestratorCues: '',
  pendingActions: [],

  // NEW: Streaming Context Protocol fields
  cachedHistory: [],              // Cached DB rows (populated by downstream)
  cachedHistoryTime: 0,           // When cache was populated
  accumulatedTranscript: '',      // All chunks this session
  chunkNumber: 0,                 // Current chunk count
  lastRouteDecision: '',          // Track route changes
  contextValid: false             // Whether cache is usable
}
```

### New Output Fields

Added to Process Transcript output:

```javascript
{
  // ... existing fields ...

  // NEW: Streaming Context Protocol output fields
  use_cached_context: boolean,         // True = use cache, False = load from DB
  cached_history: array,               // Cached DB rows (if available)
  accumulated_transcript: string,      // All chunks accumulated this session
  context_age_ms: number,              // How old the cached context is
  chunk_number: number,                // Which chunk this is
  cache_invalidation_reason: string    // Why cache was invalidated (if applicable)
}
```

### Cache Invalidation Rules

Cache is invalidated (triggers DB load) when ANY of these conditions are met:

1. **First message in session** - `isFirstMessage === true`
2. **Cache too old** - Context age > 30 seconds (30000ms)
3. **Route changed to PROCESS** - User completed thought, need fresh context

```javascript
const CACHE_MAX_AGE_MS = 30000; // 30 seconds
const cacheIsTooOld = contextAge > CACHE_MAX_AGE_MS;
const routeChangedToProcess = route === 'PROCESS' && botState.lastRouteDecision !== 'PROCESS';
const shouldInvalidateCache = isFirstMessage || cacheIsTooOld || routeChangedToProcess;
```

### Cache Logic Flow

```
┌─────────────────────────────────────────────┐
│ Process Transcript (Enhanced)               │
├─────────────────────────────────────────────┤
│ 1. Parse transcript chunk                   │
│ 2. Increment chunk_number                   │
│ 3. Accumulate transcript in session state   │
│ 4. Check cache invalidation conditions      │
│ 5. Determine if cache is valid and fresh    │
│                                             │
│ IF cache valid and fresh:                   │
│   ✓ use_cached_context = true              │
│   ✓ cached_history = botState.cachedHistory│
│   ✓ Skip DB load downstream                │
│                                             │
│ ELSE (cache invalid/stale):                 │
│   ✗ use_cached_context = false             │
│   ✗ cached_history = []                    │
│   ✗ Trigger DB load downstream             │
└─────────────────────────────────────────────┘
```

---

## Next Steps (Downstream Integration)

### 1. Update "Load Bot State" Node

The downstream "Load Bot State" Postgres node should check `use_cached_context` flag:

**Option A: Conditional execution** (recommended)
- Add a Switch/If node before "Load Bot State"
- Route to "Load Bot State" only if `use_cached_context === false`
- Route directly to "Build Agent Context" if `use_cached_context === true`

**Option B: Code node wrapper**
- Replace "Load Bot State" with a Code node that:
  - Checks `use_cached_context` flag
  - Returns cached data if true
  - Executes DB query if false

### 2. Update "Build Agent Context" Node

Modify to accept cached history:

```javascript
// Load conversation history
let historyRows = [];
const processTranscript = $('Process Transcript').first().json;

if (processTranscript.use_cached_context && processTranscript.cached_history.length > 0) {
  // Use cached history
  historyRows = processTranscript.cached_history;
} else {
  // Load from DB query result
  try {
    historyRows = $('Load Bot State').all().map(item => item.json);

    // UPDATE CACHE for next chunk
    const staticData = $getWorkflowStaticData('global');
    const bot_id = processTranscript.bot_id;
    if (staticData.botTranscripts && staticData.botTranscripts[bot_id]) {
      staticData.botTranscripts[bot_id].cachedHistory = historyRows;
      staticData.botTranscripts[bot_id].cachedHistoryTime = Date.now();
      staticData.botTranscripts[bot_id].contextValid = true;
    }
  } catch (e) {
    historyRows = [];
  }
}
```

### 3. Cache Population Strategy

When fresh data IS loaded from DB:
1. "Build Agent Context" stores it in `botState.cachedHistory`
2. Sets `botState.cachedHistoryTime = Date.now()`
3. Sets `botState.contextValid = true`

This ensures subsequent chunks can use the cache.

---

## Expected Performance Improvement

### Before (Current State)
- Every chunk: 200-500ms DB query latency
- 10 chunks = 2000-5000ms total latency
- Database load: 10 queries × 4 rows = 40 row reads

### After (With Cache Active)
- First chunk: 200-500ms DB query (cache population)
- Chunks 2-10: ~0ms DB latency (cache hit)
- 10 chunks = ~500ms total latency
- Database load: 1 query × 4 rows = 4 row reads

**Reduction:** ~80% fewer DB queries, ~75-90% latency reduction

---

## Testing Checklist

- [ ] First message triggers DB load (cache invalidation: first_message)
- [ ] Subsequent chunks within 30s use cache
- [ ] Cache expires after 30s of inactivity
- [ ] Route change from WAIT to PROCESS invalidates cache
- [ ] Session reset (>5 min inactive) clears cache
- [ ] `chunk_number` increments correctly
- [ ] `accumulated_transcript` builds across chunks
- [ ] `context_age_ms` updates accurately
- [ ] Downstream nodes receive correct `use_cached_context` flag

---

## Rollback Plan

If issues arise, revert to v3 code:

```javascript
// Remove lines 61-67 (NEW fields)
// Remove lines 75-77 (chunk number increment)
// Remove lines 87-92 (cache reset in session reset)
// Remove lines 185-246 (entire Streaming Context Protocol section)
// Remove new output fields (lines 233-245)
```

Use `mcp__n8n-mcp__n8n_update_partial_workflow` with original code.

---

## Version History

- **v3:** Deduplication + First message detection + Phonetic bot names
- **v4 (this update):** Streaming Context Protocol with session cache

---

## Code Location

**Enhanced code file:** `/tmp/process-transcript-enhanced.js`
**Workflow ID:** `d3CxEaYk5mkC8sLo`
**Node ID:** `process-transcript`
**Node Name:** `Process Transcript`
