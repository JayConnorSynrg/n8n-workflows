# Error Handling Patterns
Category from agents-evolution.md | 14 entries | Workflows: AQjMRh9pqK5PebFq, Ge33EW4K3WVHT4oG, IamjzfFxjHviJvJg, MMaJkr8abEjnCM2h
---

### Anti-Pattern: Missing Error Handling on Teams Message Fetch
**What Happened:** The "Get chat message" node had no error handling. When Microsoft Teams triggers fire for ephemeral events (deleted messages, typing indicators, system notifications), the message may not exist by the time the GET request fires (even after 300ms wait). This crashed the entire workflow with "The message you are trying to get doesn't exist".

**Impact:**
- Workflow execution #5383 failed completely
- No error feedback sent to user in Teams chat
- Silent failure — user sees no response at all

**Why It Failed:** Error handling was only applied to the AI Agent node downstream, not to upstream Teams API nodes that are equally susceptible to transient failures. Teams change notifications can fire for events that don't produce retrievable messages.

### Positive Pattern: Dual Error Routing on Teams Message Fetch
**Solution:** Added `onError: "continueErrorOutput"` to the "Get chat message" node with error output routed to the existing Error Message node.

**Implementation:**
1. Set `onError: "continueErrorOutput"` on "Get chat message" node
2. Connected error output (main[1]) to "Error Message" node
3. User receives "Error database unavailable." feedback instead of silence

**Result:**
- Workflow no longer crashes on phantom/deleted Teams messages
- User always gets feedback (either AI response or error message)
- Normal flow (main[0] → Exclude AI Bot) unchanged

**Reusable Pattern:**
Apply `onError: "continueErrorOutput"` to ALL Microsoft Teams API nodes (Get chat message, Get Chat Details, Create chat message) — not just downstream processing nodes. Teams webhook triggers can fire for events that produce non-retrievable messages. Always route error outputs to a user-facing error message node so users are never left without feedback.

---

### Positive Pattern: Immediate feedback message before long-running AI operations
**Solution:** Add a "Searching Message" Teams node before the AI Agent that immediately sends "Searching applicant database now..." to give users instant feedback while the AI processes.

**Implementation:**
1. Insert Microsoft Teams "Create chat message" node before AI Agent
2. Message: "Searching applicant database now..." (contentType: "text")
3. Same chatId expression as reply node: `={{ $('Get IDs').item.json.chatId }}`

**Result:**
- Users see immediate response instead of silence during 3-5 second AI processing
- Improved perceived responsiveness without actual speed change

**Reusable Pattern:** For any AI Agent workflow with >2 second processing time, insert a feedback message node before the agent. Use contentType "text" (not html) for simple status messages.

---

### Positive Pattern: Error handler with user-friendly fallback message
**Solution:** Configure AI Agent with `onError: "continueErrorOutput"` and route error output to a Teams message node that sends "Error database unavailable."

**Implementation:**
1. Set AI Agent `onError: "continueErrorOutput"` (dual output: success[0] + error[1])
2. Add "Error Message" Teams node connected to error output (index 1)
3. Message: "Error database unavailable." (contentType: "text")

**Result:**
- Vector search failures produce user-friendly error instead of silent failure
- Success path unaffected — Format Enforcer → Create chat message continues normally

**Reusable Pattern:** For user-facing AI Agent workflows, always configure `onError: "continueErrorOutput"` with a human-readable error message on the error path. Never let errors silently fail in chat interfaces.

---

### Anti-Pattern: Using Respond to Webhook Node with Form Trigger
**What Happened:** When building the SYNRG Invoice Generator workflow with a Form Trigger node (`responseMode: "lastNode"`), I used a "Respond to Webhook" node at the end to return JSON response after processing. The workflow deployed successfully but failed on first execution with:

```
The "Respond to Webhook" node is not supported in workflows initiated by the "n8n Form Trigger"
```

The Form Trigger node with `responseMode: "lastNode"` is incompatible with the "Respond to Webhook" node type entirely.

**Impact:**
- Workflow execution failed immediately on form submission
- Required n8n AI assistant intervention to diagnose and fix
- User could not generate invoices until workflow was corrected
- Had to remove Respond to Webhook node and replace with n8n Form node

**Why It Failed:**
- Form Trigger and Webhook Trigger have fundamentally different response mechanisms
- Form Trigger with `responseMode: "lastNode"` expects to display a form completion page, NOT return raw JSON
- "Respond to Webhook" node is designed for HTTP webhook responses, not form submissions
- The node types are incompatible - n8n enforces this at runtime
- Validation passed (structure was valid) but runtime rejected the configuration

### Positive Pattern: Use n8n Form Node as Form Ending for Form Trigger Workflows
**Solution:** Replace "Respond to Webhook" node with "n8n Form" node configured as a Form Ending page.

**Implementation:**
1. **Remove** the incompatible "Respond to Webhook" node
2. **Add** an "n8n Form" node (`n8n-nodes-base.form`) with:
   ```json
   {
     "type": "n8n-nodes-base.form",
     "typeVersion": 1,
     "parameters": {
       "operation": "completion",
       "title": "Invoice Created Successfully",
       "subtitle": "={{ $('Generate Invoice ID').item.json.invoice_id }}",
       "description": "Your invoice for {{ $('Generate Invoice ID').item.json.client_name }} totaling {{ $('Generate Invoice ID').item.json.total_due_formatted }} has been created.",
       "buttonLabel": "Create Another Invoice",
       "redirectUrl": "[form-url]"
     }
   }
   ```
3. **Connect** the Form node to the end of workflow (replacing webhook node)
4. Form Trigger's `responseMode: "lastNode"` now correctly displays the Form completion page

**Result:**
- Workflow now correctly displays success page to user after invoice generation
- User sees invoice ID, client name, and total amount on completion page
- "Create Another Invoice" button allows immediate re-use
- No runtime errors - Form Trigger and Form completion node are compatible

**Reusable Pattern:**

**Form Trigger Response Node Compatibility Matrix:**

| Response Mode | Respond to Webhook | n8n Form (completion) | None (just end) |
|--------------|-------------------|----------------------|-----------------|
| `onReceived` | ❌ Incompatible | ❌ Not needed | ✅ Works (immediate) |
| `responseNode` | ✅ Works | ❌ Not needed | ❌ No response |
| `lastNode` | ❌ **INCOMPATIBLE** | ✅ **REQUIRED** | ❌ No display |

**Decision Flow:**
```
Using Form Trigger?
├─ YES: Need to return data after processing?
│   ├─ YES: Display in web page?
│   │   ├─ YES: Use responseMode="lastNode" + n8n Form (completion)
│   │   └─ NO: Consider if form is appropriate (forms are for UI, not API)
│   └─ NO: Use responseMode="onReceived" for immediate confirmation
└─ NO (using Webhook Trigger): Use Respond to Webhook node freely
```

**Key Learnings:**
- **Form Trigger ≠ Webhook Trigger** - Different response mechanisms, different node compatibility
- **Respond to Webhook is for HTTP responses** - Not for form submission workflows
- **n8n Form (completion) is for form workflows** - Shows completion page to user
- **Validation passes but runtime fails** - This node incompatibility isn't caught in structural validation
- **Check trigger type first** - Before choosing response node, verify trigger type compatibility

---

### Anti-Pattern: IF Node Conditions Missing Required Fields in Options
**What Happened:** When deploying the SYNRG Invoice Generator workflow, the n8n API rejected the workflow with validation error:

```
Node "Check Email Provided" (index 9): Missing required field "conditions.options.leftValue". Expected value: ""
```

The IF node conditions were structured without `leftValue` in the `options` object, and the operator was missing the `name` field:

```json
// WRONG - Missing conditions.options.leftValue and operator.name
{
  "conditions": {
    "options": {
      "version": 2,
      "caseSensitive": true,
      "typeValidation": "strict"
    },
    "conditions": [{
      "operator": {
        "type": "string",
        "operation": "notEmpty"
      },
      "leftValue": "={{ $json.field }}"
    }]
  }
}
```

**Impact:**
- Workflow creation failed via MCP API
- Required researching n8n templates to discover correct structure
- Delayed deployment while fixing IF node configuration

**Why It Failed:**
- n8n IF node typeVersion 2.2 requires specific structure in `conditions.options`
- `leftValue: ""` must be present in options object (even if empty)
- `operator.name` field is required (e.g., `"filter.operator.notEmpty"`)
- The MCP validation tool's error message was accurate but non-obvious

### Positive Pattern: Complete IF Node Conditions Structure for TypeVersion 2.2
**Solution:** Use the complete conditions structure with all required fields:

**Implementation:**
```json
// CORRECT - Complete structure for IF node typeVersion 2.2
{
  "type": "n8n-nodes-base.if",
  "typeVersion": 2.2,
  "parameters": {
    "options": {},  // ← options at parameter level (empty object OK)
    "conditions": {
      "options": {
        "version": 2,
        "leftValue": "",        // ← REQUIRED even if empty
        "caseSensitive": true,
        "typeValidation": "strict"
      },
      "combinator": "and",
      "conditions": [
        {
          "id": "unique-condition-id",
          "operator": {
            "name": "filter.operator.notEmpty",  // ← REQUIRED - full operator name
            "type": "string",
            "operation": "notEmpty"
          },
          "leftValue": "={{ $json.fieldToCheck }}",
          "rightValue": ""
        }
      ]
    }
  }
}
```

**Key Fields That Must Be Present:**
1. `parameters.options` - Empty object `{}` at parameter level
2. `conditions.options.leftValue` - Empty string `""` (required by schema)
3. `conditions.options.version` - Set to `2` for typeVersion 2.2
4. `operator.name` - Full operator name like `"filter.operator.notEmpty"` or `"filter.operator.equals"`

**Result:**
- Workflow deployed successfully after correcting IF node structure
- No validation errors from n8n API
- Pattern documented for future IF node implementations

**Reusable Pattern:**

**IF Node Operator Name Reference:**

| Operation | Operator Name |
|-----------|---------------|
| Not Empty | `filter.operator.notEmpty` |
| Equals | `filter.operator.equals` |
| Not Equals | `filter.operator.notEquals` |
| Contains | `filter.operator.contains` |
| Starts With | `filter.operator.startsWith` |
| Ends With | `filter.operator.endsWith` |
| Greater Than | `filter.operator.gt` |
| Less Than | `filter.operator.lt` |
| Is True | `filter.operator.true` |
| Is False | `filter.operator.false` |

**IF Node Validation Checklist:**
- [ ] `parameters.options` exists (can be empty `{}`)
- [ ] `conditions.options.leftValue` exists (can be empty `""`)
- [ ] `conditions.options.version` is `2` for typeVersion 2.2
- [ ] Each condition has `operator.name` field with full operator path
- [ ] Each condition has unique `id` field

**Key Learnings:**
- **Schema validation is strict** - n8n API requires ALL fields even if semantically empty
- **Research templates for correct structure** - Fetch working templates via MCP to see exact field requirements
- **Operator requires full name** - Not just `operation` but also `name` with `filter.operator.` prefix
- **TypeVersion 2.2 structure differs from older versions** - Don't assume same structure across versions

---

### Anti-Pattern: Building Workflows Without Error Handling Properties
**What Happened:** When validating the Google Drive Document Repository workflow after fixing a missing `operation: "search"` parameter, n8n's validator returned 35 warnings about missing error handling on nodes:
- All Google Drive nodes (7 nodes) lacked `onError` property
- All PostgreSQL nodes (14 nodes) lacked `onError` and `retryOnFail` properties
- OpenAI Vision nodes (2 nodes) lacked `onError` and retry configuration
- Switch/Route nodes (2 nodes) had error output connections but no `onError: "continueErrorOutput"` to enable them

**Impact:**
- When Google Drive has auth issues, voice agent gets no response or timeout instead of structured error
- Database logging failures block critical path instead of gracefully continuing
- OpenAI rate limits (429) immediately fail instead of retrying
- Switch nodes with error branches don't route errors correctly

**Why It Failed:**
- Error handling properties are not required for workflow validation to pass
- Building focused on "making it work" rather than "making it resilient"
- No established pattern for which nodes need what type of error handling
- Error handling added as afterthought instead of built-in from start

### Positive Pattern: Error Handling by Node Category (Build Correct from Start)
**Solution:** Apply error handling properties during initial workflow creation based on node category:

**Implementation - Error Handling Matrix:**

| Node Category | Error Property | Retry Config | Use Case |
|--------------|----------------|--------------|----------|
| **Switch/Route nodes** | `onError: "continueErrorOutput"` | N/A | Routes errors to connected error branches |
| **External API (OpenAI, etc.)** | `onError: "continueRegularOutput"` | `retryOnFail: true, maxTries: 2, waitBetweenTries: 3000` | Handles rate limits and transient failures |
| **Google Drive/OAuth APIs** | `onError: "continueRegularOutput"` | Optional retry | Auth failures should return gracefully |
| **Critical Path DB (Search, Get)** | `onError: "continueRegularOutput"` | `retryOnFail: true, maxTries: 2` | Results needed by caller |
| **Logging/Observability DB** | `onError: "continueRegularOutput"` | None | Don't block workflow if logging fails |
| **Code nodes** | N/A (usually) | N/A | Input validation should prevent errors |

**Node Configuration Templates:**

```json
// Switch/Route nodes with error branches
{
  "onError": "continueErrorOutput"
}

// External API nodes (OpenAI, etc.)
{
  "onError": "continueRegularOutput",
  "retryOnFail": true,
  "maxTries": 2,
  "waitBetweenTries": 3000
}

// OAuth-based external services (Google Drive, etc.)
{
  "onError": "continueRegularOutput"
}

// Critical path database operations
{
  "onError": "continueRegularOutput",
  "retryOnFail": true,
  "maxTries": 2
}

// Logging/observability database operations
{
  "onError": "continueRegularOutput"
}
```

**Result:**
- Workflow warnings reduced from 35 to 9 (74% reduction)
- Remaining 9 warnings are informational Code node notices
- Voice agent will now receive structured errors instead of timeouts
- Database logging won't block critical operations
- OpenAI nodes will retry once before failing gracefully

**Reusable Pattern:**

**Build Resilience From Start - Error Handling Checklist:**

Before completing ANY workflow build:
1. [ ] Identify all Switch/Route nodes with error branches → add `onError: "continueErrorOutput"`
2. [ ] Identify all external API nodes (OpenAI, HTTP Request) → add retry + graceful failure
3. [ ] Identify all OAuth-based services (Google, Microsoft) → add graceful failure handling
4. [ ] Categorize database operations: Critical path → retry, Logging → continue on error
5. [ ] Validate workflow → confirm warning count is minimal (expect only Code node notices)

**Key Learnings:**
- **Build resilient from the start** - Adding error handling after the fact is inefficient
- **Categorize nodes by risk** - Different nodes need different error handling strategies
- **Logging should never block** - Observability is important but not critical path
- **External APIs need retries** - Rate limits and transient failures are common
- **Switch nodes need explicit error routing** - Having error connections isn't enough

---

### Anti-Pattern: Using `onError: continueRegularOutput` Without Downstream Error Detection
**What Happened:** After adding `onError: "continueRegularOutput"` to Google Drive nodes, we realized downstream Code nodes (Format List Response, Prepare DB Insert) would receive error objects instead of expected file data. Without modification, these nodes would:
- Try to map non-existent file properties
- Return empty arrays/malformed data
- Log "SUCCESS" status for failed operations
- Send confusing responses back to voice agent

**Impact:**
- Error handling that doesn't communicate errors is worse than no handling
- Voice agent would receive empty results without understanding why
- Database would have incorrect "SUCCESS" entries for failed operations

**Why It Failed:**
- `onError: "continueRegularOutput"` passes error data through the normal output
- Downstream nodes must be modified to detect and handle error data
- Error handling is a chain - every node in the flow must participate

### Positive Pattern: Symbiotic Error Handling (Error Detection in Downstream Nodes)
**Solution:** When using `onError: "continueRegularOutput"`, ALL downstream processing nodes must include error detection at the start of their logic.

**Implementation - Error Detection Template:**

```javascript
// At the START of any Code node downstream of an error-handled node:
const input = $input.first()?.json || {};

// Detect error response (from onError: continueRegularOutput)
if (input.error || (!input.expectedField && !input.otherExpectedField)) {
  const errorMsg = input.error?.message || input.message || 'Operation failed';
  return [{ json: { error: true, message: errorMsg, /* graceful defaults */ } }];
}

// Normal success path continues below...
```

**Updated Format List Response:**
```javascript
// Handle both success and error cases
const input = $input.all();

// Check if this is an error response
if (input.length === 0 || (input[0].json && input[0].json.error)) {
  const errorMsg = input[0]?.json?.error?.message || 'Drive temporarily unavailable';
  return [{ json: { error: true, message: errorMsg, files: [], count: 0 } }];
}

// Normal success path
const files = input.map(item => ({
  id: item.json.id,
  name: item.json.name,
  // ...
}));
return [{ json: { files, count: files.length } }];
```

**Updated Prepare DB Insert:**
```javascript
const downloadNodeData = $input.first()?.json || {};

// Check if this is an error response
if (downloadNodeData.error || (!downloadNodeData.id && !downloadNodeData.text)) {
  const errorMsg = downloadNodeData.error?.message || 'Extraction failed';
  return [{
    json: {
      drive_file_id: 'error',
      extraction_status: 'FAILED',  // Mark as failed, not success
      extracted_text: errorMsg,
      // ... other fields with safe defaults
    }
  }];
}

// Normal success path continues...
```

**Result:**
- Voice agent receives clear error messages when Drive is unavailable
- Database correctly logs FAILED status for failed operations
- Error handling flows through entire chain symbiotically
- No silent failures or confusing empty results

**Reusable Pattern:**

**Symbiotic Error Handling Checklist:**

When adding `onError: "continueRegularOutput"` to any node:
1. [ ] Identify ALL downstream Code nodes in the flow
2. [ ] Add error detection logic at START of each Code node
3. [ ] Return graceful error response with clear message
4. [ ] Mark status fields as "FAILED" not "SUCCESS"
5. [ ] Test full flow with simulated errors

**Error Detection Indicators:**
- `input.error` exists (explicit error object)
- Expected data fields are missing
- Input is empty or null
- `input.message` contains error text

**Key Learnings:**
- **Error handling is a chain** - One node's error becomes the next node's input
- **Graceful degradation requires coordination** - All nodes must participate
- **Voice agents need clear messages** - "Drive temporarily unavailable" > empty results
- **Database must reflect reality** - Never log SUCCESS for failed operations
- **Test the error path** - Simulated failures reveal gaps in error handling

---

### Anti-Pattern 3: IF node with strict type validation on JS expression
**What Happened:** Resume Quality Check IF node used `typeValidation: "strict"` with condition `{{ $json.resumeText && $json.resumeText.length > 50 && $json.resumeText !== 'Resume text not available' }}`. With strict validation, the JS expression returns the last truthy value (a string), not boolean `true`. String !== true evaluates to FALSE, routing valid resumes to the error path.

**Impact:**
- Valid candidates with proper resume data were routed to the error/skip path
- Workflow appeared to work but produced no AI analysis

**Why It Failed:** Knowledge Gap — n8n IF node with `typeValidation: "strict"` requires the expression to evaluate to exactly boolean `true`, not just a truthy value. JavaScript `&&` chains return the last truthy operand (a string), which fails strict boolean comparison.

### Positive Pattern 3: Evaluate necessity of validation nodes; use boolean casting for strict IF conditions
**Solution:** Removed the Resume Quality Check node entirely — it was redundant because the AI Agent and VDC already handle all quality scenarios (missing resume, incomplete data, error paths). When IF nodes with strict validation ARE needed, cast to boolean: `{{ Boolean($json.field && $json.field.length > 50) }}`.

**Implementation:**
1. Before adding validation IF nodes, check if downstream nodes already handle the scenarios
2. If strict type validation is required, wrap expression in `Boolean()`
3. Prefer `continueRegularOutput` error handling over gating IF nodes

**Reusable Pattern:**
n8n IF node `typeValidation: "strict"` requires explicit boolean values. JS expressions like `a && b && c` return the last truthy value (a string/number), NOT `true`. Always wrap in `Boolean()` for strict mode. Better yet: evaluate whether the IF node is needed at all — defensive downstream handling often makes validation gates redundant.

---
