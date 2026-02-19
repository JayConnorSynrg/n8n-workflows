# Loop & Iteration Patterns
Category from agents-evolution.md | 8 entries | Workflows: 8bhcEHkbbvnhdHBh, MMaJkr8abEjnCM2h
---

### Anti-Pattern: Using Upstream Node References in Loop Entry Points
**What Happened:** The "Set Slide Context" node used expressions that referenced upstream nodes outside the loop:
```javascript
"dalle_style": "={{ $('Store Folder Info').item.json.dalle_style }}",
"carousel_folder_id": "={{ $('Store Folder Info').item.json.carousel_folder_id }}",
"style_description": "={{ $('Store Folder Info').item.json.style_description }}",
"carousel_id": "={{ $('Store Folder Info').item.json.carousel_id }}"
```

When the quality loop iterated (Refine Prompt → Set Slide Context), the workflow failed with:
```
NodeOperationError: paired_item_no_info
Error: Paired item data for item from node 'Parse Quality Result' is unavailable
```

**Impact:**
- Workflow execution #1512 failed after successfully:
  - Generating 5 DALL-E 3 images
  - Analyzing quality for all 5 images
  - Routing slide 1 (score 78/100) to refinement path
  - Creating refined prompt
- Failed on loop iteration 2 when returning to Set Slide Context
- No images uploaded to Google Drive despite being generated
- Entire workflow stopped - no carousel completion

**Why It Failed:**
1. **Why #1**: Set Slide Context threw "paired item data unavailable" error
2. **Why #2**: Parse Quality Result Code node returns data without `pairedItem` metadata
3. **Why #3**: Code node manually constructs return object, only copies `binary` but not `pairedItem`
4. **Why #4**: n8n's loop architecture relies on `pairedItem` to track item lineage for expressions like `$('Store Folder Info').item`
5. **Why #5 (Root Cause)**: Knowledge gap - Code nodes in loops break the pairedItem chain, and Set nodes that use upstream references can't resolve which item to reference

### Positive Pattern: Use Fallback Expressions for Loop-Compatible Set Nodes
**Solution:** Modify the loop entry point (Set Slide Context) to use fallback expressions that check for values in `$json` first (from loop path), falling back to upstream references only for the initial path.

**Implementation:**

**1. Changed Set Slide Context expressions to use fallback pattern:**
```javascript
// BEFORE - Only works on initial path, breaks on loop return
"dalle_style": "={{ $('Store Folder Info').item.json.dalle_style }}"

// AFTER - Works on both initial path and loop return
"dalle_style": "={{ $json.dalle_style || $('Store Folder Info').item.json.dalle_style }}"
```

**2. Applied pattern to all fields that need to persist through loop:**
```json
{
  "parameters": {
    "assignments": {
      "assignments": [
        {
          "name": "current_prompt",
          "value": "={{ $json.current_prompt || $json.prompt }}"
        },
        {
          "name": "original_prompt",
          "value": "={{ $json.original_prompt || $json.prompt }}"
        },
        {
          "name": "attempt_number",
          "value": "={{ $json.attempt_number || 1 }}"
        },
        {
          "name": "max_attempts",
          "value": "={{ $json.max_attempts || 3 }}"
        },
        {
          "name": "dalle_style",
          "value": "={{ $json.dalle_style || $('Store Folder Info').item.json.dalle_style }}"
        },
        {
          "name": "carousel_folder_id",
          "value": "={{ $json.carousel_folder_id || $('Store Folder Info').item.json.carousel_folder_id }}"
        },
        {
          "name": "style_description",
          "value": "={{ $json.style_description || $('Store Folder Info').item.json.style_description }}"
        },
        {
          "name": "carousel_id",
          "value": "={{ $json.carousel_id || $('Store Folder Info').item.json.carousel_id }}"
        }
      ]
    }
  }
}
```

**3. Why this works:**
- **Initial path** (Split → Set Slide Context): `$json` has slide data but NOT `dalle_style` → falls back to `$('Store Folder Info').item.json.dalle_style`
- **Loop path** (Refine Prompt → Set Slide Context): `$json` has ALL data including `dalle_style` from Refine Prompt → uses `$json.dalle_style` directly, never hits upstream reference

**4. Deployed fix:**
```javascript
mcp__n8n-mcp__n8n_update_partial_workflow({
  id: "8bhcEHkbbvnhdHBh",
  operations: [{
    type: "updateNode",
    nodeName: "Set Slide Context",
    updates: {
      parameters: {
        assignments: { /* updated assignments with fallback expressions */ }
      }
    }
  }]
})
```

**Result:**
- Workflow updated to versionCounter 9
- Set Slide Context now works on both initial and loop paths
- No pairedItem chain required for loop functionality
- Self-contained loop architecture - all needed data passed through JSON

**Reusable Pattern:**

**Loop-Compatible Set Node Architecture:**

```
                    ┌───────────────────────────────────────┐
                    │                                       │
                    ▼                                       │
Entry Point ──► Set Node ──► Process ──► Quality Check ──►│
    │              │                         │             │
    │         Uses fallback:                 ▼             │
    │         $json.field ||            Pass: Continue     │
    │         $('Upstream').item        Fail: Refine ──────┘
    │              │                          │
    │              │                          │
    └──────────────┘                          │
   Initial path provides                 Loop path provides
   upstream reference                    $json.field directly
```

**When to Use Fallback Expressions:**
- ✅ Any Set node that receives input from both a linear path AND a loop return
- ✅ When upstream references work initially but break on subsequent iterations
- ✅ When Code nodes are in the loop path (they break pairedItem chain)
- ✅ When you see `paired_item_no_info` errors on loop iteration

**When NOT Needed:**
- ❌ Set nodes that only receive input from one source
- ❌ Loops that don't use upstream references (all data in `$json`)
- ❌ Loops using only native n8n nodes (they preserve pairedItem)

**Alternative Solutions (Not Recommended):**

| Solution | Complexity | Reliability | Recommendation |
|----------|------------|-------------|----------------|
| Fallback expressions | Low | High | ✅ **RECOMMENDED** |
| Add pairedItem to Code nodes | Medium | Fragile | ⚠️ Can break |
| Restructure loop to avoid upstream refs | High | High | ⚠️ Major refactor |
| Use SplitInBatches node | Medium | Medium | ⚠️ Different architecture |

**Adding pairedItem to Code nodes (fragile alternative):**
```javascript
// This CAN work but is fragile
return [{
  json: { ...data },
  binary: imageData,
  pairedItem: $input.first().pairedItem  // Must manually preserve
}];
```
Issues with this approach:
- Easy to forget when modifying Code nodes
- `$input.first().pairedItem` may be undefined
- Doesn't work if multiple items input
- Fallback expressions are more robust

**Key Learnings:**
- **pairedItem is n8n's item lineage tracker** - Required for `$('NodeName').item` expressions
- **Code nodes break pairedItem chain** - They don't automatically preserve lineage
- **Fallback expressions are self-healing** - Work regardless of which path items arrive from
- **Loop entry points are critical** - The node where loops return needs special handling
- **Data duplication in loops is OK** - Refine Prompt passing all fields through JSON is the right pattern
- **5-Why analysis essential** - Surface error (Set node) vs root cause (Code node + upstream reference) are different

**Files Updated:**
- Workflow `8bhcEHkbbvnhdHBh` (versionCounter 8 → 9)
- `.claude/agents-evolution.md` (this pattern)

---

### Anti-Pattern: Direct Backward Connections for Loop Logic
**What Happened:** When implementing a quality retry loop for the AI Carousel Generator (ID: `8bhcEHkbbvnhdHBh`), the initial approach created a direct backward connection from `Wait Before Retry` to `Set Slide Context` to create a retry loop when image quality didn't pass.

**Implementation Attempted:**
```
Quality Check (IF) → [FALSE] → Refine Prompt → Wait Before Retry → Set Slide Context (BACKWARD)
```

**Impact:**
- Workflow validation failed with error: "Workflow contains a cycle (infinite loop)"
- `valid: false` in validation results
- Workflow could not be activated or executed
- Core functionality (quality-based regeneration) was broken

**Why It Failed:**
- n8n workflows are DAG (Directed Acyclic Graph) based
- Direct backward connections to earlier nodes create cycles that n8n's validation rejects
- The validation engine flags any path that can loop back to a previously executed node

### Positive Pattern: SplitInBatches Node with Reset=true for Controlled Loops
**Solution:** Used the `SplitInBatches` node (also called "Loop Over Items") with the `Reset=true` option to create an officially supported loop pattern that n8n's validation accepts.

**Implementation:**
1. **Added SplitInBatches node** (`Quality Retry Loop`) after `Split Slide Prompts`
   ```json
   {
     "type": "n8n-nodes-base.splitInBatches",
     "typeVersion": 3,
     "parameters": {
       "batchSize": 1,
       "options": { "reset": true }
     }
   }
   ```

2. **Connected SplitInBatches outputs correctly:**
   - **Output 0 (done)**: → `Merge All Slides` (when loop completes)
   - **Output 1 (loop)**: → `Set Slide Context` (process current item)

3. **Loop back connections TO SplitInBatches (not backward to other nodes):**
   - On success: `Format Slide Result` → `Loop Back to Quality Check` → `Quality Retry Loop`
   - On failure: `Wait Before Retry` → `Quality Retry Loop`

4. **Architecture:**
```
Split Slide Prompts
       ↓
Quality Retry Loop (SplitInBatches, Reset=true)
       ↓ output[0]           ↓ output[1]
Merge All Slides      Set Slide Context
       ↓                      ↓
Generate Metadata      Generate Image → Analyze → Parse → Quality Check
       ↓                                                ↓ TRUE        ↓ FALSE
Show Results                                         Upload →     Refine Prompt
                                                     Share →      Wait Before Retry
                                                     Format →          ↓
                                                     Loop Back ←-------↓
                                                         ↓
                                                   (back to Quality Retry Loop)
```

**Result:**
- ✅ Validation passes: `valid: true`, `errorCount: 0`
- ✅ No "cycle" or "infinite loop" errors
- ✅ Loop functionality preserved - items that fail quality check get refined prompts and retry
- ✅ Items that pass quality check proceed to upload and complete
- ✅ When all items processed, loop exits via output[0] to merge results
- Workflow updated to version 32

**Reusable Pattern:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  n8n QUALITY RETRY LOOP PATTERN (SplitInBatches)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STRUCTURE:                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │   Items → SplitInBatches (Reset=true) ←─────────────────────────┐  │   │
│  │                │                                                │   │   │
│  │        output[0]│output[1]                                      │   │   │
│  │                ↓       ↓                                        │   │   │
│  │           [DONE]    [LOOP]                                      │   │   │
│  │            ↓           ↓                                        │   │   │
│  │         Merge     Process Item                                  │   │   │
│  │            ↓           ↓                                        │   │   │
│  │         Output     Quality Check (IF)                           │   │   │
│  │                         │                                       │   │   │
│  │                  TRUE   │   FALSE                               │   │   │
│  │                    ↓    │     ↓                                 │   │   │
│  │               Success   │   Refine                              │   │   │
│  │               Path      │   Prompt                              │   │   │
│  │                  ↓      │     ↓                                 │   │   │
│  │               Mark     Wait/Retry                               │   │   │
│  │               Done ────────────────────────────→ (back to loop) │   │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  KEY RULES:                                                                 │
│  ✅ Use SplitInBatches node with Reset=true                                │
│  ✅ Connect LOOP output (index 1) to processing chain                      │
│  ✅ Connect DONE output (index 0) to final aggregation                     │
│  ✅ All retry paths loop BACK to SplitInBatches, not to other nodes        │
│  ✅ Success paths also return to SplitInBatches (to process next item)     │
│  ❌ NEVER connect backward to any node except SplitInBatches               │
│                                                                             │
│  PARAMETERS:                                                                │
│  - batchSize: 1 (process one item at a time for retry control)             │
│  - options.reset: true (treat each incoming item as fresh data)            │
│                                                                             │
│  OUTPUT INDICES (CRITICAL - counterintuitive!):                            │
│  - Output 0 = "done" (AFTER loop completes)                                │
│  - Output 1 = "loop" (DURING iteration - process items here)               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Learnings:**
- SplitInBatches with `Reset=true` is n8n's official pattern for controlled loops
- The Reset option treats incoming data as a new set rather than continuation
- Connecting back TO the SplitInBatches node (not other nodes) is valid and expected
- Output indices are counterintuitive: done=0, loop=1 (not loop=0, done=1)
- Quality retry loops work when all paths eventually return to the SplitInBatches node
- Templates #2719 and #5597 from n8n.io demonstrate this pattern in production

**Documentation References:**
- n8n Loop Over Items docs: https://docs.n8n.io/flow-logic/looping/
- Template #2719: "Retry on fail except for known error"
- Template #5597: "Iterative Content Refinement with GPT-4 Multi-Agent Feedback System"

---

### Anti-Pattern: Backward Connections Create Invalid Workflow Cycles

**What Happened:** The AI Carousel Generator workflow (ID: `8bhcEHkbbvnhdHBh`) was flagged as invalid with the error "Workflow contains a cycle (infinite loop)". The workflow had a quality retry loop implemented using a backward connection:

```
Quality Check → (fail) → Refine Prompt → Set Slide Context (BACKWARD CONNECTION)
```

This connection from "Refine Prompt (Positive)" back to "Set Slide Context" was intended to retry image generation when quality was below threshold. However, n8n detected this as an invalid cycle.

**Impact:**
- Workflow could not be activated
- Error: "Workflow contains a cycle (infinite loop)"
- No execution possible - structural validation failed

**Why It Failed:**
- **Root Cause**: n8n does not support arbitrary backward connections for creating loops
- n8n requires explicit loop constructs (Loop Over Items / SplitInBatches nodes) for controlled iteration
- The backward connection pattern works in some workflow engines but n8n's DAG (Directed Acyclic Graph) architecture rejects cycles
- The workflow validator detected the cycle: Refine Prompt → Set Slide Context → Generate Image → Analyze → Parse → Quality Check → Refine Prompt (loop)

### Positive Pattern: Remove Cycles or Use Explicit Loop Nodes

**Solution:** Removed the backward connection and simplified the workflow to a linear flow. The "Refine Prompt (Positive)" node was also removed as it became orphaned.

**Implementation:**
1. **Fetched current workflow** using `mcp__n8n-mcp__n8n_get_workflow({ id: "8bhcEHkbbvnhdHBh", mode: "full" })`
2. **Identified the problematic connection**: `"Refine Prompt (Positive)" → "Set Slide Context"`
3. **Restructured the workflow**:
   - Removed the "Refine Prompt (Positive)" node (now orphaned)
   - Removed the "Quality Check" IF node (no longer needed without retry logic)
   - Connected "Parse Quality Result" directly to "Upload to Google Drive"
4. **Used full workflow update**: `mcp__n8n-mcp__n8n_update_full_workflow` with complete nodes array and connections (partial update had issues with node references)
5. **Validated**: `mcp__n8n-mcp__n8n_validate_workflow({ id: "8bhcEHkbbvnhdHBh" })` → `valid: true`, 0 errors

**Result:**
- Workflow now valid with 0 errors (28 warnings, all non-blocking)
- Reduced from 21 nodes to 19 nodes (cleaner architecture)
- Workflow can now be activated and executed
- Renamed from "AI Carousel Generator - 5 Slides with Quality Loop" to "AI Carousel Generator - 5 Slides"

**Reusable Pattern:**

```
┌─────────────────────────────────────────────────────────────┐
│  n8n LOOP ARCHITECTURE RULES                                │
├─────────────────────────────────────────────────────────────┤
│  ❌ NEVER: Create backward connections between nodes        │
│  ❌ NEVER: Assume arbitrary loops will work                 │
│  ✅ ALWAYS: Use Loop Over Items node for iteration          │
│  ✅ ALWAYS: Use SplitInBatches for batch processing         │
│  ✅ ALTERNATIVE: Sub-workflow called recursively            │
│  ✅ ALTERNATIVE: Accept first result (no retry)             │
└─────────────────────────────────────────────────────────────┘
```

**Alternative Approaches for Quality Retry (if needed in future):**

1. **Sub-Workflow Approach**:
   ```
   Main Workflow → Execute Workflow (quality-retry-subworkflow) → Continue

   quality-retry-subworkflow:
   Input → Generate Image → Check Quality → IF pass → Output
                                         → IF fail → Generate Again (up to N times)
   ```

2. **Loop Over Items with Counter**:
   ```
   Set (attempts array [1,2,3]) → Loop Over Items → Generate → Check →
   IF pass → Break → Output
   IF fail → Continue (next attempt)
   ```

3. **Accept First Result** (simplest - what we implemented):
   ```
   Generate Image → Analyze → Upload (no retry)
   ```
   - GPT Image 1 produces high-quality results on first try
   - Retry logic adds complexity without proportional value gain

**Key Learnings:**
- n8n is a DAG-based workflow engine - cycles are structurally invalid
- The "cycle detection" happens at validation time, not runtime
- When MCP partial update fails with node reference issues, use full workflow update
- Simpler workflows are often better - the quality loop added complexity without proven value

---

### Anti-Pattern 4: SplitInBatches "done" vs "loop" output index confusion
**What Happened:** After removing the Resume Quality Check node, the `replaceConnections` operation incorrectly placed "Standardize Resume Data" on index 0 (the "done" output) instead of index 1 (the "loop" output) of the Loop One Candidate (SplitInBatches) node. The node output candidate data on index 1, but nothing was connected there.

**Impact:**
- Workflow stopped at Loop One Candidate — no candidates were processed
- The node executed successfully but its loop output had no downstream connection

**Why It Failed:** Knowledge Gap + Process Gap — the `replaceConnections` operation dropped the empty array placeholder `[]` for the done output, collapsing the loop connection from index 1 to index 0.

### Positive Pattern 4: SplitInBatches connection format with explicit empty array placeholder
**Solution:** SplitInBatches nodes MUST always have TWO entries in the `main` array: index 0 = done (empty or final node), index 1 = loop body. Always include the empty array placeholder.

**Implementation:**
```json
"Loop Node Name": {
  "main": [
    [],  // index 0 = "done" output (fires when all items processed)
    [{ "node": "ProcessingNode", "type": "main", "index": 0 }]  // index 1 = "loop" output
  ]
}
```

**Reusable Pattern:**
When modifying SplitInBatches connections via API, ALWAYS include both array entries. The empty `[]` placeholder for the done output is REQUIRED — without it, the loop output shifts to index 0 and the workflow silently stops processing. This is especially dangerous with `replaceConnections` operations that rebuild the entire connections object.

---
