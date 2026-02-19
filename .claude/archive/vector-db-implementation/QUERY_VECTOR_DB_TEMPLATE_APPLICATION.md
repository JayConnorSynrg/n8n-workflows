# Query Vector DB - Template Application Guide

**Template:** Gated Execution Pattern (Voice Tool: Send Gmail)
**Target Workflow:** Query Vector DB (new)
**Application Strategy:** Direct adaptation with vector-specific modifications

---

## 1. Node Mapping Reference

| Send Gmail Node | Query Vector DB Node | Adaptation |
|-----------------|----------------------|-----------|
| Webhook | Webhook | Identical - keep same config |
| Code: Generate ID | Code: Generate ID | Identical - reusable |
| Postgres: INSERT tool_call | Postgres: INSERT tool_call | Identical - shared schema |
| HTTP Request: Gate 1 | HTTP Request: Gate 1 | Modify message text only |
| IF: Check Cancel (Gate 1) | IF: Check Cancel (Gate 1) | Identical - logic reusable |
| Postgres: UPDATE CANCELLED | Postgres: UPDATE CANCELLED | Identical - shared schema |
| HTTP: Cancel Callback | HTTP: Cancel Callback | Identical - logic reusable |
| Respond: Cancelled | Respond: Cancelled | Identical - response reusable |
| HTTP Request: Gate 2 | HTTP Request: Gate 2 | Modify message for vector context |
| IF: Check Cancel (Gate 2) | IF: Check Cancel (Gate 2) | Identical - logic reusable |
| **Gmail: Send** | **Postgres: Query Vector DB** | **Core action change** |
| Code: Format Result | Code: Format Result | Modify to include vector results |
| Postgres: UPDATE COMPLETED | Postgres: UPDATE COMPLETED | Identical - stores results |
| HTTP Request: Gate 3 | HTTP Request: Gate 3 | Identical - completion pattern |
| Respond to Webhook | Respond to Webhook | Identical - response pattern |

---

## 2. Step-by-Step Node Configuration

### 2.1 Webhook Node
**Configuration:** Copy exactly from Send Gmail
```json
{
  "path": "query-vector-db",
  "httpMethod": "POST",
  "responseMode": "responseNode",
  "options": {}
}
```
**Change:** Update path to match new endpoint

---

### 2.2 Code: Generate ID
**Configuration:** Copy exactly from Send Gmail
```javascript
// Use intent_id as tool_call_id for predictable testing
// Falls back to generated ID if intent_id not provided
const body = $input.first().json.body || $input.first().json || {};
const timestamp = Date.now().toString(36);
const random = Math.random().toString(36).substr(2, 9);
return [{
  tool_call_id: body.intent_id || `tc_${timestamp}_${random}`,
  callback_url: body.callback_url || null,
  session_id: body.session_id || null,
  intent_id: body.intent_id || null,
  parameters: body.parameters || {}
}];
```
**No changes required**

---

### 2.3 Postgres: INSERT tool_call
**Configuration:** Copy exactly from Send Gmail
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
) VALUES ($1, $2, $3, 'query_vector_db', $4::jsonb, 'EXECUTING', $5, NOW())
RETURNING *;
```

**Query Replacement:**
```
{{ $json.tool_call_id }},
{{ $json.session_id }},
{{ $json.intent_id }},
{{ JSON.stringify($json.parameters) }},
{{ $json.callback_url }}
```

**Change:** Update function_name from 'send_email' to 'query_vector_db'

---

### 2.4 HTTP Request: Gate 1
**Configuration:** Copy from Send Gmail with message modification
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
    message: 'Preparing vector database query...'
  }) }}",
  "options": {"timeout": 10000}
}
```

**Changes:**
- Line "message": Change from "Preparing to send email..." to "Preparing vector database query..."
- All else identical

---

### 2.5 IF: Check Cancel (Gate 1)
**Configuration:** Copy exactly from Send Gmail - no changes
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

**Connection Pattern:**
- True branch: Postgres UPDATE CANCELLED
- False branch: HTTP Request Gate 2

---

### 2.6 Postgres: UPDATE CANCELLED
**Configuration:** Copy exactly from Send Gmail - no changes
```sql
UPDATE tool_calls
SET status = $1, completed_at = NOW()
WHERE tool_call_id = $2
RETURNING *;
```

**Query Replacement:**
```
{{ 'CANCELLED' }},
{{ $('Code: Generate ID').first().json.tool_call_id }}
```

**No changes required**

---

### 2.7 HTTP: Cancel Callback
**Configuration:** Copy exactly from Send Gmail with one message change
```json
{
  "method": "POST",
  "url": "={{ $('Code: Generate ID').first().json.callback_url }}",
  "sendHeaders": true,
  "headerParameters": {
    "parameters": [
      {"name": "Content-Type", "value": "application/json"}
    ]
  },
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({
    status: 'CANCELLED',
    gate: 0,
    tool_call_id: $('Code: Generate ID').first().json.tool_call_id,
    intent_id: $('Code: Generate ID').first().json.intent_id,
    voice_response: 'Vector database query cancelled by user.'
  }) }}",
  "options": {"timeout": 10000}
}
```

**Changes:**
- voice_response: Change "Email cancelled by user." to "Vector database query cancelled by user."

---

### 2.8 Respond: Cancelled
**Configuration:** Copy exactly from Send Gmail - no changes
```json
{
  "respondWith": "json",
  "options": {}
}
```

**No changes required**

---

### 2.9 HTTP Request: Gate 2
**Configuration:** Copy from Send Gmail with message modifications
```json
{
  "method": "POST",
  "url": "={{ $('Code: Generate ID').first().json.callback_url }}",
  "sendHeaders": true,
  "headerParameters": {
    "parameters": [
      {"name": "Content-Type", "value": "application/json"}
    ]
  },
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={{ JSON.stringify({
    status: 'READY_TO_QUERY',
    gate: 2,
    requires_confirmation: true,
    cancellable: true,
    tool_call_id: $('Code: Generate ID').first().json.tool_call_id,
    intent_id: $('Code: Generate ID').first().json.intent_id,
    message: 'Vector query is ready. Review results limit and embedding similarity threshold.'
  }) }}",
  "options": {"timeout": 35000}
}
```

**Changes:**
- status: 'READY_TO_SEND' → 'READY_TO_QUERY'
- message: Update to vector-specific text
- Keep timeout at 35000 (user review window)

---

### 2.10 IF: Check Cancel (Gate 2)
**Configuration:** Copy exactly from Send Gmail - no changes
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
        "id": "condition-1768345702969-g7cgtd6ew"
      }
    ]
  },
  "options": {}
}
```

**Connection Pattern:**
- True branch: Postgres UPDATE CANCELLED
- False branch: Postgres Query Vector DB (replaces Gmail: Send)

---

### 2.11 Core Action: Postgres Query Vector DB
**Node Type:** n8n-nodes-base.postgres v2.6
**Replaces:** Gmail: Send node

```json
{
  "operation": "executeQuery",
  "query": "SELECT id, content, embedding <-> $1::vector AS distance FROM documents WHERE embedding <-> $1::vector < $2 ORDER BY embedding <-> $1::vector LIMIT $3 RETURNING id, content, distance;",
  "options": {
    "queryReplacement": "='{{ JSON.stringify($('Code: Generate ID').first().json.parameters.embedding) }}', {{ $('Code: Generate ID').first().json.parameters.similarity_threshold || 0.8 }}, {{ $('Code: Generate ID').first().json.parameters.limit || 10 }}"
  }
}
```

**Expected Input Parameters (from Code: Generate ID):**
```json
{
  "embedding": [0.123, 0.456, ...],  // Vector array
  "similarity_threshold": 0.8,        // Cosine distance threshold
  "limit": 10                         // Results limit
}
```

**Query Details:**
- Uses pgvector `<->` operator for cosine distance
- Filters by similarity threshold
- Orders by distance (closest first)
- Limits results
- Returns: id, content, distance

---

### 2.12 Code: Format Result
**Replaces:** Code: Format Result from Send Gmail
```javascript
const genData = $('Code: Generate ID').first().json;
const queryResults = $('Postgres: Query Vector DB').first().json;

return [{
  status: 'COMPLETED',
  tool_call_id: genData.tool_call_id,
  intent_id: genData.intent_id,
  callback_url: genData.callback_url,
  result: {
    matches: queryResults.map(row => ({
      id: row.id,
      content: row.content,
      distance: row.distance
    })),
    total_results: queryResults.length,
    query_params: {
      limit: genData.parameters.limit,
      threshold: genData.parameters.similarity_threshold
    }
  },
  voice_response: `Vector query returned ${queryResults.length} documents matching your request.`,
  execution_time_ms: 0
}];
```

**Changes from Send Gmail:**
- Remove gmail-specific fields (messageId, threadId)
- Add vector-specific result format
- Include query parameters in result
- Update voice_response for vector context
- Transform query results into readable format

---

### 2.13 Postgres: UPDATE COMPLETED
**Configuration:** Copy exactly from Send Gmail - no changes
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

**Query Replacement:**
```
{{ JSON.stringify($json.result) }},
{{ $json.voice_response }},
{{ $json.tool_call_id }}
```

**No changes required - works with any result format**

---

### 2.14 HTTP Request: Gate 3
**Configuration:** Copy exactly from Send Gmail - no changes
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

**No changes required - works with any result payload**

---

### 2.15 Respond to Webhook
**Configuration:** Copy exactly from Send Gmail - no changes
```json
{
  "respondWith": "json",
  "options": {}
}
```

**No changes required**

---

## 3. Connection Topology (Query Vector DB)

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
[TRUE]                     IF: Check Cancel (Gate 2) ──→ [FALSE] → Postgres: Query Vector DB
  ↓                              ↓                            ↓
Postgres: UPDATE                [TRUE]                  Code: Format Result
CANCELLED                        ↓                            ↓
  ↓                     Postgres: UPDATE              Postgres: UPDATE
HTTP: Cancel                    CANCELLED               COMPLETED
Callback                        ↓                            ↓
  ↓                     HTTP: Cancel Callback      HTTP Request: Gate 3
Respond: Cancelled              ↓                            ↓
                        Respond: Cancelled         Respond to Webhook
```

---

## 4. Nodes to Copy vs. Modify vs. Create

### Copy Exactly (No Changes)
- Code: Generate ID
- Postgres: INSERT tool_call
- IF: Check Cancel (Gate 1)
- IF: Check Cancel (Gate 2)
- Postgres: UPDATE CANCELLED
- Respond: Cancelled
- Postgres: UPDATE COMPLETED
- HTTP Request: Gate 3
- Respond to Webhook
- Webhook (path change only)

### Copy & Modify (Text Changes Only)
- HTTP Request: Gate 1 (message text)
- HTTP: Cancel Callback (voice_response text)
- HTTP Request: Gate 2 (status, message text)

### Create New / Replace
- **Postgres: Query Vector DB** (replaces Gmail: Send)
  - New SQL query with pgvector operations
  - Input parameters from Code: Generate ID

- **Code: Format Result** (substantial modification)
  - Different output structure
  - Vector-specific formatting
  - Query parameters included

---

## 5. Critical Implementation Notes

### Database Schema Required
```sql
-- Existing table (shared with Send Gmail)
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

-- New table for vector operations
CREATE TABLE documents (
  id SERIAL PRIMARY KEY,
  content TEXT,
  embedding vector(1536),  -- For OpenAI embeddings
  created_at TIMESTAMP DEFAULT NOW()
);

-- pgvector extension required
CREATE EXTENSION IF NOT EXISTS vector;

-- Index for fast similarity search
CREATE INDEX ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### Input Request Format
```json
{
  "intent_id": "unique-id-for-testing",
  "callback_url": "https://your-callback-endpoint.com/notify",
  "session_id": "session-xyz",
  "parameters": {
    "embedding": [0.123, 0.456, ..., 1536 values total],
    "similarity_threshold": 0.8,
    "limit": 10
  }
}
```

### Output Response Format
```json
{
  "status": "COMPLETED",
  "tool_call_id": "tc_...",
  "intent_id": "...",
  "result": {
    "matches": [
      {
        "id": 1,
        "content": "Document text...",
        "distance": 0.15
      }
    ],
    "total_results": 10,
    "query_params": {
      "limit": 10,
      "threshold": 0.8
    }
  },
  "voice_response": "Vector query returned 10 documents matching your request."
}
```

---

## 6. Testing Checklist (Query Vector DB Specific)

- [ ] Documents table exists with embedding vectors
- [ ] Vector index created for performance
- [ ] Webhook accepts POST to `/query-vector-db`
- [ ] Input parameters include proper embedding array
- [ ] Gate 1 callback indicates "Preparing vector database query..."
- [ ] Gate 2 timeout allows user to review threshold/limit
- [ ] Postgres query executes successfully
- [ ] Results ordered by distance (closest first)
- [ ] Results limited to specified count
- [ ] Code: Format Result transforms results correctly
- [ ] voice_response reflects vector context
- [ ] Gate 3 includes full result set
- [ ] Cancel paths work at Gate 1 and Gate 2
- [ ] All retry logic functions
- [ ] Error handling degrades gracefully

---

## 7. Deployment Checklist

- [ ] All node typeVersions match template (postgres 2.6, httpRequest 4.3, etc.)
- [ ] Webhook path configured: `query-vector-db`
- [ ] Database credentials set for Postgres node
- [ ] tool_calls table exists with correct schema
- [ ] documents table exists with embedding column
- [ ] pgvector extension installed
- [ ] Callback URL in test request points to real endpoint
- [ ] Run workflow validation via n8n CLI
- [ ] Test with sample embedding vectors
- [ ] Monitor first few executions for performance
- [ ] Verify Gate 2 timeout is appropriate for your data size

---

## 8. Node Count Summary

**Total Nodes: 15 (same as Send Gmail)**

| Category | Count | Nodes |
|----------|-------|-------|
| Entry | 3 | Webhook, Code: Generate ID, Postgres INSERT |
| Gate 1 | 4 | HTTP Gate 1, IF Cancel 1, UPDATE CANCELLED, HTTP Cancel |
| Cancel Response | 1 | Respond Cancelled |
| Gate 2 | 2 | HTTP Gate 2, IF Cancel 2 |
| Core Action | 1 | Postgres Query Vector DB |
| Completion | 2 | Code Format Result, Postgres UPDATE COMPLETED |
| Gate 3 | 1 | HTTP Gate 3 |
| Final Response | 1 | Respond Success |

**Connection Count: 13 (same as Send Gmail)**
