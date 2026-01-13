# Voice Agent n8n Workflows

Enterprise voice agent workflows implementing gated execution with pre-confirmation pattern.

## Workflows

| File | Webhook | Purpose |
|------|---------|---------|
| `voice-tool-send-gmail.json` | `POST /execute-gmail` | Gated email with pre-send checkpoint |
| `voice-tool-query-vector-db.json` | `POST /query-vector-db` | Gated query + context storage |
| `voice-tool-get-session-context.json` | `GET /get-session-context` | Fetch stored context for email drafting |

## Architecture

```
Relay Server (pre-confirmation) → n8n Workflows (gated execution) → PostgreSQL (state)
```

### Flow Pattern

1. **Pre-confirmation** (Relay): Agent confirms parameters before calling n8n
2. **Gate 1** (n8n): Creates EXECUTING record, sends callback, checks for cancel
3. **Gate 2** (n8n): Final confirmation checkpoint (READY_TO_SEND)
4. **Execution** (n8n): Performs actual operation (Gmail send, DB query)
5. **Gate 3** (n8n): Completion callback with voice_response

## Database Requirements

Requires PostgreSQL tables from `../database/schema.sql`:

- `tool_calls` - Gated execution tracking
- `session_context` - Cross-tool data sharing (1-hour TTL)

## Import to n8n

1. Open n8n web interface
2. Go to Workflows → Import from File
3. Select JSON file
4. Configure credentials:
   - PostgreSQL connection
   - Gmail OAuth2 (for send_gmail)

## Callback Payload Examples

### Gate 1 (PREPARING)
```json
{
  "status": "PREPARING",
  "gate": 1,
  "cancellable": true,
  "tool_call_id": "tc_xxx"
}
```

### Gate 2 (READY_TO_SEND)
```json
{
  "status": "READY_TO_SEND",
  "gate": 2,
  "requires_confirmation": true,
  "tool_call_id": "tc_xxx"
}
```

### Gate 3 (COMPLETED)
```json
{
  "status": "COMPLETED",
  "gate": 3,
  "tool_call_id": "tc_xxx",
  "result": {...},
  "voice_response": "Email sent successfully..."
}
```

### Query DB Completion
```json
{
  "status": "COMPLETED",
  "context_available": true,
  "context_key": "last_query_results",
  "tool_call_id": "tc_xxx",
  "voice_response": "Found Q3 sales data. $4.2M total..."
}
```

## Relay Response Format

Relay must respond to callbacks with:

```json
// Continue execution
{ "continue": true }

// Cancel execution
{ "cancel": true, "reason": "User requested" }
```

## Node TypeVersions

All nodes use latest stable versions (2026-01-12):

| Node | Version |
|------|---------|
| Webhook | 2.1 |
| Respond to Webhook | 1.5 |
| Code | 2 |
| Postgres | 2.6 |
| HTTP Request | 4.3 |
| IF | 2.3 |
| Gmail | 2.2 |
