# N8N Voice Agent Supporting Workflows

## Get Session Context

**File**: `voice-tool-get-session-context.json`

**Status**: ✓ Valid - All validations passed

### Workflow Configuration

| Property | Value |
|----------|-------|
| Name | Get Session Context |
| Trigger | Webhook (GET) |
| Webhook Path | `get-session-context` |
| HTTP Method | GET |
| Response Mode | Response Node |

### Flow Structure

```
Webhook (GET /get-session-context)
  ↓
Postgres: SELECT (Query session_context table)
  ↓
IF: Check Found (Check if result exists)
  ├── TRUE (Result found) → Respond: Success
  └── FALSE (No result) → Respond: Not Found
```

### Node Configuration Details

**1. Webhook (typeVersion: 2.1)**
- Path: `get-session-context`
- Method: GET
- Response Mode: Response Node
- Error Handling: Continue on regular output
- Query Parameters: Receives `session_id` and `context_key` from query string

**2. Postgres: SELECT (typeVersion: 2.6)**
- Operation: Execute Query
- Query:
  ```sql
  SELECT context_value 
  FROM session_context 
  WHERE session_id = $1 
    AND context_key = $2 
    AND expires_at > NOW() 
  LIMIT 1;
  ```
- Query Parameters: `{{ $json.query.session_id }},{{ $json.query.context_key }}`
- Retry on Fail: Enabled (3 attempts)

**3. IF: Check Found (typeVersion: 2.3)**
- Condition: `{{ $json.length }} > 0`
- Type Validation: Strict
- Outputs:
  - **TRUE** → Route to "Respond: Success"
  - **FALSE** → Route to "Respond: Not Found"

**4. Respond: Success (typeVersion: 1.5)**
- Response Body:
  ```json
  {
    "success": true,
    "context": "[context_value from database]"
  }
  ```

**5. Respond: Not Found (typeVersion: 1.5)**
- Response Body:
  ```json
  {
    "success": false,
    "error": "Context not found or expired"
  }
  ```

### API Usage Example

**Request**:
```bash
GET /webhook/get-session-context?session_id=user123&context_key=settings
```

**Response (Success)**:
```json
{
  "success": true,
  "context": "{\"theme\": \"dark\", \"language\": \"en\"}"
}
```

**Response (Not Found/Expired)**:
```json
{
  "success": false,
  "error": "Context not found or expired"
}
```

### Database Requirements

Table: `session_context`

| Column | Type | Description |
|--------|------|-------------|
| session_id | VARCHAR | Unique session identifier |
| context_key | VARCHAR | Context key name |
| context_value | TEXT | Context value (JSON or plain text) |
| expires_at | TIMESTAMP | Expiration timestamp |

### Validation Results

✓ All 5 nodes valid
✓ All 4 connections valid
✓ All 5 expressions valid
✓ No errors
⚠ 2 minor warnings (expected and handled):
  - Webhook: Standard informational warning about error responses
  - Postgres: Retry attempts configured (default 3)

### Integration Points

This workflow is a supporting service for:
- **AI Voice Agent** - Retrieves conversation context for multi-turn dialogues
- **Session Management** - Accesses stored session state and preferences
- **Memory Service** - Fetches agent memory/context by session

### Deployment Notes

1. Configure PostgreSQL credentials in n8n UI
2. Webhook will be available at: `https://[n8n-instance]/webhook/get-session-context`
3. Query parameters: `session_id` and `context_key` (required)
4. Ensure database table exists with proper schema
5. Monitor retry behavior for database connection issues
