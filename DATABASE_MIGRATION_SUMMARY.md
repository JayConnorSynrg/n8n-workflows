# Database Schema Migration - Agent Context Enhancement

## Summary

Two n8n workflows have been created to execute PostgreSQL DDL statements for the Agent Context Schema Enhancement on the Microsoft Teams Agent Database (Credential ID: `NI3jbq1U8xPst3j3`).

---

## Workflows Created

### 1. Webhook Version (Production)
- **Workflow ID:** `zcU1EwEaVKvWXxOu`
- **Name:** Database Schema Migration - Agent Context Enhancement
- **Status:** Active (webhook endpoint requires manual UI activation)
- **Trigger:** POST webhook at path `migrate-agent-context-schema`
- **Webhook URL:** `https://[your-n8n-instance]/webhook/migrate-agent-context-schema`

**To activate webhook:**
1. Open workflow in n8n UI
2. Click "Active" toggle in top-right
3. Webhook endpoint will be registered automatically

### 2. Manual Execution Version (Testing)
- **Workflow ID:** `h9saXEbuhHyxMp4X`
- **Name:** MANUAL - Database Schema Migration - Agent Context Enhancement
- **Status:** Ready for manual execution
- **Trigger:** Manual trigger (click "Test Workflow" in n8n UI)

**To execute:**
1. Open workflow in n8n UI
2. Click "Test Workflow" button
3. Monitor execution progress
4. Review results in final "Build Migration Summary" node

---

## Schema Components

The migration creates the following database objects in sequence:

### 1. Tables

#### `agent_session_context`
- Stores active session context data
- Keys: session_id, context_key (unique constraint)
- Supports TTL via `expires_at` column
- Indexes: composite (session_id, context_key), expires_at filter

#### `agent_global_knowledge`
- Cross-session accessible knowledge base
- Tracks source (session, tool call) and confidence
- Supports access counting and last access tracking
- Indexes: knowledge_key (unique), source_session_id

#### `agent_session_archive`
- Closed session history (globally accessible)
- Stores complete session snapshots
- Full-text search support via `searchable_content`
- Indexes: session_id (unique), date (DESC), GIN text search

### 2. Table Alterations

#### `tool_calls` (existing table)
- Added `parent_tool_call_id` column (for tool call chaining)
- Added `promote_to_global` boolean flag
- Added partial index on parent_tool_call_id

### 3. Views

#### `v_agent_full_context`
Unified agent access point providing:
- Current tool call data
- Session context (non-expired)
- Previous session calls (last 10 completed)

#### `v_agent_global_context`
Global knowledge access with:
- Knowledge entries sorted by confidence and access count
- Source session summary (from archive)

### 4. Functions

#### `archive_session(p_session_id varchar(100)) RETURNS jsonb`
Archives completed session and promotes flagged tool calls to global knowledge.

**Returns:**
```json
{
  "success": true,
  "session_id": "...",
  "archived_tool_calls": 15,
  "promoted_to_global": 3
}
```

#### `search_session_history(p_search_query text, p_limit integer DEFAULT 10)`
Full-text search across archived sessions.

**Returns:** Table with columns:
- session_id
- session_summary
- relevance (ranking score)
- session_ended_at

---

## Workflow Architecture

### Node Flow
1. **Webhook/Manual Trigger** - Initiates execution
2. **Create Session Context Table** - DDL step 1
3. **Create Global Knowledge Table** - DDL step 2
4. **Create Session Archive Table** - DDL step 3
5. **Alter Tool Calls Table** - DDL step 4
6. **Create Unified Context View** - DDL step 5
7. **Create Global Knowledge View** - DDL step 6
8. **Create Archive Session Function** - DDL step 7
9. **Create Search Function** - DDL step 8
10. **Build Migration Summary** - Aggregates results

### Error Handling
- All Postgres nodes have `onError: "continueRegularOutput"`
- Retry on fail enabled (max 2 attempts)
- Errors are captured in final summary
- Migration continues even if individual steps fail

### Response Format
```json
{
  "migration_status": "SUCCESS" | "PARTIAL_FAILURE",
  "total_steps": 8,
  "successful_steps": 8,
  "failed_steps": 0,
  "timestamp": "2026-01-17T22:48:44.897Z",
  "results": [
    {
      "node": "Create Session Context Table",
      "success": true,
      "rowCount": 0
    }
  ],
  "errors": [],
  "schema_components_created": [
    "agent_session_context table",
    "agent_global_knowledge table",
    "agent_session_archive table",
    "tool_calls table alterations",
    "v_agent_full_context view",
    "v_agent_global_context view",
    "archive_session() function",
    "search_session_history() function"
  ]
}
```

---

## Files Created

- `/Users/jelalconnor/CODING/N8N/Workflows/workflow-zcU1EwEaVKvWXxOu-migration-agent-context.json`
  - Webhook version workflow JSON

- `/Users/jelalconnor/CODING/N8N/Workflows/DATABASE_MIGRATION_SUMMARY.md`
  - This documentation file

---

## Execution Instructions

### Option 1: Manual Execution (Recommended for Testing)
1. Open n8n UI
2. Navigate to workflow `h9saXEbuhHyxMp4X` (MANUAL version)
3. Click "Test Workflow"
4. Review execution results in "Build Migration Summary" node

### Option 2: Webhook Execution (Production)
1. Open n8n UI
2. Navigate to workflow `zcU1EwEaVKvWXxOu`
3. Activate workflow (toggle in top-right)
4. Send POST request to webhook:
   ```bash
   curl -X POST https://[your-n8n-instance]/webhook/migrate-agent-context-schema
   ```

---

## Validation

### Pre-Migration Checks
- Credential `NI3jbq1U8xPst3j3` has CREATE TABLE, CREATE INDEX, CREATE FUNCTION privileges
- Database has `tool_calls` table (required for ALTER statements)
- PostgreSQL version supports JSONB and full-text search (9.4+)

### Post-Migration Verification
Run these queries to verify migration success:

```sql
-- Verify tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('agent_session_context', 'agent_global_knowledge', 'agent_session_archive');

-- Verify views exist
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public'
  AND table_name IN ('v_agent_full_context', 'v_agent_global_context');

-- Verify functions exist
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name IN ('archive_session', 'search_session_history');

-- Verify tool_calls columns added
SELECT column_name FROM information_schema.columns
WHERE table_name = 'tool_calls'
  AND column_name IN ('parent_tool_call_id', 'promote_to_global');
```

---

## Rollback Plan

To rollback this migration:

```sql
-- Drop functions
DROP FUNCTION IF EXISTS search_session_history(text, integer);
DROP FUNCTION IF EXISTS archive_session(varchar(100));

-- Drop views
DROP VIEW IF EXISTS v_agent_global_context;
DROP VIEW IF EXISTS v_agent_full_context;

-- Drop indexes (will cascade with tables)
-- Remove columns from tool_calls
ALTER TABLE tool_calls DROP COLUMN IF EXISTS promote_to_global;
ALTER TABLE tool_calls DROP COLUMN IF EXISTS parent_tool_call_id;

-- Drop tables
DROP TABLE IF EXISTS agent_session_archive;
DROP TABLE IF EXISTS agent_global_knowledge;
DROP TABLE IF EXISTS agent_session_context;
```

---

## Notes

- All DDL statements use `IF NOT EXISTS` / `CREATE OR REPLACE` for idempotency
- Migration can be run multiple times safely
- Workflow validation shows 0 critical errors
- Error handling configured for production resilience
- Execution saved to n8n history (saveDataSuccessExecution: all)

---

## Next Steps

1. Execute manual workflow to verify migration
2. Review execution results
3. Run post-migration verification queries
4. Update application code to use new schema
5. Activate webhook version for production use
6. Archive or delete manual test workflow after successful migration
