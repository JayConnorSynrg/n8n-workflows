# Gated Execution Pattern - Voice Tool: Send Gmail

**Template Source:** Workflow ID `kBuTRrXTJF1EEBEs` (Voice Tool: Send Gmail)
**Pattern Complexity:** 3 gates with callback architecture
**Last Updated:** 2026-01-15

---

## 1. Node Structure & Flow

### A. Entry Phase
1. **Webhook** (n8n-nodes-base.webhook v2.1)
   - Path: `execute-gmail`
   - Method: POST
   - Response Mode: responseNode (allows async callback)

2. **Code: Generate ID** (n8n-nodes-base.code v2)
   - Generates unique `tool_call_id` (uses `intent_id` if provided for testability)
   - Extracts callback_url, session_id, parameters from request body
   - Enables state tracking across gates

3. **Postgres: INSERT tool_call** (n8n-nodes-base.postgres v2.6)
   - Initial record creation with status 'EXECUTING'

### B. Gating Architecture
The pattern uses 3 sequential gates, each with:
- Callback notification (HTTP POST with gate metadata)
- Cancel check (IF node)
- Status update (Postgres UPDATE)

```
Gate 1 (PREPARING)
    ↓
Cancel Check Gate 1 → [Cancel Path] or [Continue to Gate 2]
    ↓
Gate 2 (READY_TO_SEND)
    ↓
Cancel Check Gate 2 → [Cancel Path] or [Continue to Action]
    ↓
[Action: Gmail Send]
    ↓
Gate 3 (COMPLETED)
```

---

## 2. Gate Callback Implementation

### Gate 1: Preparation Phase
**Node:** HTTP Request: Gate 1 (n8n-nodes-base.httpRequest v4.3)

```json
{
  "method": "POST",
  "url": "={{ $json.callback_url }}",
  "sendHeaders": true,
  "headerParameters": {
    "parameters": [
      {"name": "Content-Type", "value": "application/json"}
    ]
  },
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({
    status: 'PREPARING',
    gate: 1,
    cancellable: true,
    tool_call_id: $('Code: Generate ID').first().json.tool_call_id,
    intent_id: $('Code: Generate ID').first().json.intent_id,
    message: 'Preparing to send email...'
  }) }}",
  "options": {"timeout": 10000}
}
```

**Key Patterns:**
- JSON body uses `JSON.stringify()` to ensure proper formatting
- References previous node data using `$('Code: Generate ID').first().json.tool_call_id`
- Includes gate number and cancellable flag
- Timeout: 10 seconds (user interaction window)
- Retry: 3 attempts with 1 second delay

### Gate 2: Confirmation Phase
**Node:** HTTP Request: Gate 2 (n8n-nodes-base.httpRequest v4.3)

```json
{
  "method": "POST",
  "url": "={{ $('Code: Generate ID').first().json.callback_url }}",
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({
    status: 'READY_TO_SEND',
    gate: 2,
    requires_confirmation: true,
    cancellable: true,
    tool_call_id: $('Code: Generate ID').first().json.tool_call_id,
    intent_id: $('Code: Generate ID').first().json.intent_id,
    message: 'Email is ready to send. Confirm to proceed.'
  }) }}",
  "options": {"timeout": 35000}
}
```

**Differences from Gate 1:**
- Longer timeout (35s) - waiting for user confirmation
- Additional field: `requires_confirmation: true`
- 2 retry attempts (vs 3 for Gate 1)
- 2 second wait between retries

### Gate 3: Completion Phase
**Node:** HTTP Request: Gate 3 (n8n-nodes-base.httpRequest v4.3)

```json
{
  "method": "POST",
  "url": "={{ $json.callback_url }}",
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({
    status: 'COMPLETED',
    gate: 3,
    tool_call_id: $json.tool_call_id,
    intent_id: $json.intent_id,
    result: $json.result,
    voice_response: $json.voice_response,
    execution_time_ms: $json.execution_time_ms
  }) }}",
  "options": {"timeout": 10000}
}
```

**Differences:**
- No user interaction expected
- Includes result data from the executed action
- Uses direct `$json` reference (comes from Code: Format Result)

---

## 3. IF Node Cancel Checking

### IF: Check Cancel (Gate 1)
**Node Type:** n8n-nodes-base.if v2.3

```json
{
  "conditions": {
    "options": {
      "version": 2,
      "leftValue": "",
      "caseSensitive": true,
      "typeValidation": "loose"
    },
    "combinator": "and",
    "conditions": [
      {
        "leftValue": "={{ $json.cancel }}",
        "operator": {
          "operation": "equals",
          "type": "boolean"
        },
        "rightValue": true,
        "id": "condition-1768345702969-j8bxvnnd2"
      }
    ]
  },
  "options": {}
}
```

**Outputs:**
- TRUE branch (index 0): Postgres UPDATE CANCELLED → HTTP Cancel Callback → Respond Cancelled
- FALSE branch (index 1): Continue to Gate 2

**Key Implementation Details:**
- Evaluates `$json.cancel` from HTTP response body
- Type: boolean equality check
- `onError: continueErrorOutput` - treats missing `cancel` field as false
- Branching uses array indices in connections

### IF: Check Cancel (Gate 2)
Identical structure to Gate 1, but:
- Receives response from Gate 2 callback
- Branches to either CANCELLED path or Gmail Send action

---

## 4. PostgreSQL Query Patterns

### INSERT Query (Initial State)
**Node:** Postgres: INSERT tool_call

```sql
INSERT INTO tool_calls (
  tool_call_id,
  session_id,
  intent_id,
  function_name,
  parameters,
  status,
  callback_url,
  created_at
) VALUES ($1, $2, $3, 'send_email', $4::jsonb, 'EXECUTING', $5, NOW())
RETURNING *;
```

**Query Replacement Pattern:**
```
{{ $json.tool_call_id }},
{{ $json.session_id }},
{{ $json.intent_id }},
{{ JSON.stringify($json.parameters) }},
{{ $json.callback_url }}
```

**Key Features:**
- `$1, $2, $3...` placeholders (parameterized)
- `NOW()` for server-side timestamps
- `$4::jsonb` - explicit JSON casting
- `JSON.stringify()` to convert object to string for JSONB column
- Hardcoded function_name for consistency

### UPDATE Query (Cancel)
**Node:** Postgres: UPDATE CANCELLED

```sql
UPDATE tool_calls
SET status = $1, completed_at = NOW()
WHERE tool_call_id = $2
RETURNING *;
```

**Query Replacement Pattern:**
```
{{ 'CANCELLED' }},
{{ $('Code: Generate ID').first().json.tool_call_id }}
```

**Key Features:**
- Hardcoded status string: `{{ 'CANCELLED' }}`
- Cross-node reference using node selector
- Single WHERE clause on tool_call_id

### UPDATE Query (Completion)
**Node:** Postgres: UPDATE COMPLETED

```sql
UPDATE tool_calls
SET
  status = 'COMPLETED',
  result = $1::jsonb,
  voice_response = $2,
  execution_time_ms = 0,
  completed_at = NOW()
WHERE tool_call_id = $3
RETURNING *;
```

**Query Replacement Pattern:**
```
{{ JSON.stringify($json.result) }},
{{ $json.voice_response }},
{{ $json.tool_call_id }}
```

**Key Features:**
- Multiple SET clauses
- Result object stored as JSONB with `JSON.stringify()`
- Hardcoded execution_time_ms: 0
- References data from Code: Format Result node

---

## 5. Connection Topology

```
Webhook
  ↓
Code: Generate ID
  ↓
Postgres: INSERT tool_call
  ↓
HTTP Request: Gate 1
  ↓
IF: Check Cancel (Gate 1) ──→ [FALSE] → HTTP Request: Gate 2
  ↓                              ↓
[TRUE]                     IF: Check Cancel (Gate 2) ──→ [FALSE] → Gmail: Send
  ↓                              ↓                            ↓
Postgres: UPDATE                [TRUE]                  Code: Format Result
CANCELLED                        ↓                            ↓
  ↓                     Postgres: UPDATE              Postgres: UPDATE
HTTP: Cancel                    CANCELLED               COMPLETED
Callback                        ↓                            ↓
  ↓                     HTTP: Cancel Callback      HTTP Request: Gate 3
Respond: Cancelled              ↓                            ↓
                        Respond: Cancelled         Respond to Webhook:
                                                    Success
```

---

## 6. Cross-Node Data References

### Node Selector Pattern
```javascript
$('Code: Generate ID').first().json.tool_call_id
$('Code: Generate ID').first().json.intent_id
$('Code: Generate ID').first().json.callback_url
$('Code: Generate ID').first().json.parameters
```

**When to Use:**
- Gate callbacks need to reference original request data
- Cancel queries need to reference tool_call_id from beginning
- Ensures data consistency across long execution chains

### Direct JSON Reference
```javascript
$json.cancel           // From HTTP response
$json.callback_url    // From Code: Format Result
$json.tool_call_id    // From Code: Format Result
```

**When to Use:**
- Current node's output data
- Recent transformations
- Simpler expressions with fewer hops

---

## 7. Error Handling

### Retry Configuration
- **Gate Callbacks:** `retryOnFail: true`, `maxTries: 3`, `waitBetweenTries: 1000`
- **Postgres Queries:** `retryOnFail: true` (uses n8n defaults)
- **Rationale:** HTTP callbacks may fail temporarily; database operations need resilience

### IF Node Error Handling
- **onError:** `continueErrorOutput`
- **Effect:** Missing or invalid `cancel` field defaults to FALSE (continue execution)
- **Benefit:** Graceful degradation if response is incomplete

---

## 8. Template Application for Query Vector DB

### Adaptation Points

**Gate 1: Query Initiation**
- Status: 'PREPARING_QUERY'
- Message: 'Preparing vector database query...'
- Timeout: 10s

**Gate 2: Query Confirmation**
- Status: 'READY_TO_QUERY'
- Message: 'Vector query is ready. Confirm to execute.'
- Timeout: 35s (user may review)

**Action: PostgreSQL Vector Query**
```sql
SELECT
  id,
  content,
  embedding <-> $1::vector AS distance
FROM documents
ORDER BY embedding <-> $1::vector
LIMIT 10;
```

**Gate 3: Results Delivered**
- Status: 'COMPLETED'
- Include: `results` array from query
- Include: `total_results` count

### Database Schema Assumptions
```sql
CREATE TABLE tool_calls (
  tool_call_id TEXT PRIMARY KEY,
  session_id TEXT,
  intent_id TEXT,
  function_name TEXT,
  parameters JSONB,
  status VARCHAR(50),
  callback_url TEXT,
  result JSONB,
  voice_response TEXT,
  execution_time_ms INTEGER,
  created_at TIMESTAMP,
  completed_at TIMESTAMP
);
```

---

## 9. Node Type Versions (Critical for Deployment)

| Node Type | Version | Critical | Notes |
|-----------|---------|----------|-------|
| webhook | 2.1 | Yes | Response mode required |
| code | 2 | Yes | JS execution context |
| postgres | 2.6 | Yes | Query execution v2.6+ |
| httpRequest | 4.3 | Yes | JSON body handling |
| if | 2.3 | Yes | Expression evaluation |
| gmail | 2.2 | Yes | Send operation |
| respondToWebhook | 1.5 | Yes | Async callback |

**Deployment Check:**
- All nodes must use versions listed above
- Verify with `mcp__n8n-mcp__get_node` before implementation
- Do not downgrade versions

---

## 10. Known Limitations & Workarounds

### Issue: Long-Running Queries Block Gate 2
**Problem:** If Query Vector DB takes >35s, Gate 2 timeout will fire
**Solution:** Increase timeout to 60s or use async query pattern

### Issue: Network Failures to Callback URL
**Problem:** If callback_url is unreachable, gates fail
**Solution:** Implement fallback polling from client side

### Issue: Multiple Cancellations
**Problem:** IF node branches may execute concurrently
**Solution:** Use Postgres constraint to prevent duplicate status updates

### Issue: Cross-Node References Break If Node Renamed
**Problem:** `$('Code: Generate ID')` fails if node renamed
**Solution:** Document node names as part of schema

---

## 11. Testing Checklist

- [ ] Webhook accepts POST to configured path
- [ ] tool_call_id generates consistently (use intent_id)
- [ ] Postgres INSERT succeeds with all fields
- [ ] Gate 1 callback POSTs to callback_url with correct payload
- [ ] IF node detects cancel: true correctly
- [ ] Cancel path completes with status update
- [ ] Continue path reaches Gate 2 callback
- [ ] Gate 2 timeout behaves correctly
- [ ] Action executes with parameters from original request
- [ ] Code: Format Result creates proper output object
- [ ] Postgres UPDATE COMPLETED stores results
- [ ] Gate 3 callback receives completion notification
- [ ] Webhook response returns final result
- [ ] All retry logic functions correctly
- [ ] Error handling degrades gracefully

---

## 12. Pattern Files

**Related Patterns:**
- `gated-execution-callbacks.md` - Detailed architecture documentation
- Pattern Implementation: Gated Execution with HTTP Callbacks
- Database: PostgreSQL integration for state management
- HTTP: Retry logic and timeout handling
