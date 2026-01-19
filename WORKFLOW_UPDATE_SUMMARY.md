# Agent Context Access Workflow Update Summary

**Workflow ID:** `ouWMjcKzbj6nrYXz`
**Workflow Name:** Agent Context Access - Universal Query
**Updated:** 2026-01-18
**File:** `/Users/jelalconnor/CODING/N8N/Workflows/agent-context-access-updated.json`

---

## Summary of Changes

### CHANGE 1: Tool Calls Logging

**New Nodes Added (3):**
1. **Code: Generate Tool Call ID** (after webhook)
   - Generates unique ID: `tc_context_{timestamp}_{random}`
   - Preserves webhook data and adds `tool_call_id` and `created_at`

2. **Postgres: INSERT Tool Call** (after generate ID)
   - Logs to `tool_calls` table with status='EXECUTING'
   - Records: `tool_call_id`, `session_id`, `intent_id`, `function_name`, `parameters`

3. **HTTP: Confirmation Gate** (after INSERT)
   - POSTs to `callback_url` from request body
   - Sends confirmation request with all context

### CHANGE 2: Confirmation Gating

**New Nodes Added (3):**
1. **IF: Check Confirmation** (after HTTP gate)
   - Checks if `$json.continue === true`
   - TRUE path (output 0) → Cancel execution
   - FALSE path (output 1) → Continue to routing

2. **Postgres: UPDATE Cancelled** (TRUE path)
   - Updates tool_call with status='CANCELLED'
   - Sets error_message='User denied confirmation'

3. **Respond: Cancelled** (after UPDATE)
   - Returns cancellation message to webhook caller

### CHANGE 3: Custom Query Path with AI-Generated SQL

**New Switch Case:** `custom_query` (9th output of Switch node)

**New Nodes Added (4):**
1. **OpenAI: Generate SQL** (Switch → custom_query)
   - Model: gpt-4o (using ResourceLocator format)
   - System prompt: SQL generator for voice agent DB
   - Generates READ-ONLY SELECT queries
   - Temperature: 0.1 for consistency

2. **Code: Validate SQL** (after OpenAI)
   - Validates SQL is read-only (no INSERT/UPDATE/DELETE/etc.)
   - Checks for SELECT presence
   - Throws error if invalid
   - Returns: `{sql, validated, original_query}`

3. **Postgres: Execute Custom SQL** (after validation)
   - Executes validated SQL: `={{ $json.sql }}`
   - Uses same PostgreSQL credential

4. **Format: Custom Query Result** (after execute)
   - Formats results with metadata
   - Returns: `query_type`, `original_query`, `generated_sql`, `results_count`, `data`

### Tool Call Completion Logging

**New Nodes Added (10):**
One UPDATE node after each Format node:
- Postgres: UPDATE Success (Session)
- Postgres: UPDATE Success (History)
- Postgres: UPDATE Success (Schema)
- Postgres: UPDATE Success (Tables)
- Postgres: UPDATE Success (Global)
- Postgres: UPDATE Success (Archive)
- Postgres: UPDATE Success (Archive Result)
- Postgres: UPDATE Success (Search)
- Postgres: UPDATE Success (Default)
- Postgres: UPDATE Success (Custom)

**Each UPDATE node:**
- Sets status='SUCCESS'
- Sets result=JSON of formatted response
- Sets completed_at=NOW()
- Calculates execution_time_ms

---

## Node Count

- **Before:** 21 nodes
- **After:** 41 nodes
- **Added:** 20 nodes

---

## Credentials Used

| Service | Credential ID | Credential Name | Used By |
|---------|---------------|-----------------|---------|
| PostgreSQL | `NI3jbq1U8xPst3j3` | MICROSOFT TEAMS AGENT DATABASE | All Postgres nodes |
| OpenAI | `6BIzzQu5jAD5jKlH` | OpenAi account | OpenAI: Generate SQL |

---

## Execution Flow (New)

```
Webhook
  ↓
Code: Generate Tool Call ID
  ↓
Postgres: INSERT Tool Call (status=EXECUTING)
  ↓
HTTP: Confirmation Gate (POST to callback_url)
  ↓
IF: Check Confirmation ($json.continue === true)
  ├─ TRUE → Postgres: UPDATE Cancelled → Respond: Cancelled
  └─ FALSE → Route Query Type (Switch)
      ├─ session_context → Query → Format → UPDATE Success → Respond
      ├─ tool_history → Query → Format → UPDATE Success → Respond
      ├─ schema → Query → Format → UPDATE Success → Respond
      ├─ all_tables → Query → Format → UPDATE Success → Respond
      ├─ global_context → Query → Format → UPDATE Success → Respond
      ├─ session_archive → Query → Format → UPDATE Success → Respond
      ├─ archive_session → Query → Format → UPDATE Success → Respond
      ├─ search_history → Query → Format → UPDATE Success → Respond
      ├─ custom_query → OpenAI: Generate SQL → Validate → Execute → Format → UPDATE Success → Respond
      └─ default → Query → Format → UPDATE Success → Respond
```

---

## New Query Type: `custom_query`

**Request Format:**
```json
{
  "query_type": "custom_query",
  "search_query": "Show me all failed tool calls from the last hour",
  "callback_url": "https://your-callback-endpoint.com",
  "session_id": "optional_session_id",
  "intent_id": "optional_intent_id"
}
```

**Response Format:**
```json
{
  "query_type": "custom_query",
  "original_query": "Show me all failed tool calls from the last hour",
  "generated_sql": "SELECT * FROM tool_calls WHERE status = 'FAILED' AND created_at > NOW() - INTERVAL '1 hour' ORDER BY created_at DESC LIMIT 50",
  "results_count": 3,
  "data": [...]
}
```

---

## Safety Features

1. **SQL Injection Protection:**
   - OpenAI generates queries with system prompt restrictions
   - Code node validates: NO INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, GRANT, REVOKE
   - Only SELECT queries allowed

2. **Confirmation Gate:**
   - Every query now requires callback confirmation
   - Tool call logged BEFORE execution
   - Can be cancelled mid-flight

3. **Audit Trail:**
   - All executions logged to `tool_calls` table
   - Status progression: EXECUTING → SUCCESS/CANCELLED
   - Execution time tracked in milliseconds

---

## Available Tables (for custom queries)

As documented in OpenAI system prompt:

```
- tool_calls (id, tool_call_id, session_id, intent_id, function_name,
              parameters, status, result, voice_response, error_message,
              created_at, completed_at, execution_time_ms)

- session_context (id, session_id, key, value, created_at)

- agent_session_archive (id, session_id, session_summary, total_tool_calls,
                         session_started_at, session_ended_at, archived_at,
                         context_data)
```

---

## Node Version Compliance

All new nodes use latest typeVersions:
- **Code:** 2
- **HTTP Request:** 4.3
- **IF:** 2.3
- **OpenAI:** 2.1 (with ResourceLocator for modelId)
- **Postgres:** 2.6
- **Switch:** 3.4 (existing, now has 9 outputs + fallback)

---

## Testing Checklist

- [ ] Webhook receives POST with callback_url
- [ ] Tool call ID generated and logged
- [ ] Confirmation gate POSTs to callback_url
- [ ] Cancelled path works (sets status=CANCELLED)
- [ ] Continue path executes query
- [ ] All existing query types still work
- [ ] custom_query generates valid SQL
- [ ] Custom query validation blocks dangerous SQL
- [ ] Custom query executes and returns results
- [ ] UPDATE Success nodes log completion correctly
- [ ] execution_time_ms calculated accurately

---

## Deployment Instructions

### Option 1: Via n8n MCP Tool (Programmatic)
```javascript
mcp__n8n-mcp__n8n_update_full_workflow({
  id: "ouWMjcKzbj6nrYXz",
  nodes: [...], // from agent-context-access-updated.json
  connections: {...},
  settings: {...}
})
```

### Option 2: Via n8n UI (Manual)
1. Open n8n interface
2. Navigate to workflow "Agent Context Access - Universal Query"
3. Import JSON from `/Users/jelalconnor/CODING/N8N/Workflows/agent-context-access-updated.json`
4. Verify all credentials are mapped correctly
5. Save and activate

---

## Files Created

1. `/Users/jelalconnor/CODING/N8N/Workflows/agent-context-access-updated.json`
   - Complete workflow JSON with all changes

2. `/Users/jelalconnor/CODING/N8N/Workflows/WORKFLOW_UPDATE_SUMMARY.md`
   - This summary document

3. `/tmp/n8n-update.json`
   - Compact update payload for MCP tool

---

## Next Steps

1. **Apply the workflow update** (choose Option 1 or 2 above)
2. **Test the new functionality:**
   - Send a test request with `callback_url`
   - Verify confirmation gate behavior
   - Test custom_query with natural language
   - Verify logging in `tool_calls` table
3. **Update voice agent integration** to handle confirmation callbacks
4. **Document the new `custom_query` type** in voice agent instructions
