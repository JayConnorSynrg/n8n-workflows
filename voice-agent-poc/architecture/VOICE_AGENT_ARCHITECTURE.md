# Enterprise Voice Agent - Architecture Evaluation

**Objective:** Production-grade voice assistant with **maximum observability** - each tool as its own sub-workflow for independent monitoring, versioning, and debugging.

---

## Architecture Comparison: MCP Trigger vs Webhook Dispatcher

### Option A: MCP Server Trigger + Call n8n Sub-Workflow Tool (NEW)

**Based on:** [n8n MCP Server Trigger docs](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-langchain.mcptrigger/), [Template #3770](https://n8n.io/workflows/3770-build-your-own-n8n-workflows-mcp-server/)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MCP TRIGGER ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Voice Agent (Relay Server) ──── MCP Client Connection (SSE/HTTP) ────┐     │
│                                                                        │     │
│  ┌─────────────────────────────────────────────────────────────────────▼──┐ │
│  │                    MCP SERVER TRIGGER WORKFLOW                         │ │
│  │                    (Exposes tools to MCP clients)                      │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  MCP Server Trigger (path: /voice-agent-tools)                         │ │
│  │       │                                                                │ │
│  │       ├──→ Call n8n Sub-Workflow Tool: schedule_meeting                │ │
│  │       ├──→ Call n8n Sub-Workflow Tool: send_email                      │ │
│  │       ├──→ Call n8n Sub-Workflow Tool: search_contacts                 │ │
│  │       ├──→ Call n8n Sub-Workflow Tool: get_calendar_availability       │ │
│  │       ├──→ Call n8n Sub-Workflow Tool: create_task                     │ │
│  │       ├──→ Call n8n Sub-Workflow Tool: search_documentation            │ │
│  │       ├──→ Call n8n Sub-Workflow Tool: get_training_progress           │ │
│  │       └──→ Call n8n Sub-Workflow Tool: knowledge_check                 │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Each Sub-Workflow (8 total):                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  Execute Workflow Trigger (receives parameters from tool)              │ │
│  │       ↓                                                                │ │
│  │  Tool Implementation (Code/Gmail/HTTP)                                 │ │
│  │       ↓                                                                │ │
│  │  Return Result (auto-returned to MCP client)                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**MCP Trigger Advantages:**
| Feature | Benefit |
|---------|---------|
| **Native tool discovery** | MCP clients auto-discover available tools |
| **Schema inference** | Input schemas from sub-workflow triggers |
| **Persistent connection** | SSE keeps connection alive (no repeated handshakes) |
| **Protocol standard** | Uses Model Context Protocol (Anthropic standard) |
| **Simpler routing** | No webhook path parsing, no Switch nodes |

**MCP Trigger Disadvantages:**
| Issue | Impact |
|-------|--------|
| **Known bug with JS Code nodes** | [Issue #19902](https://github.com/n8n-io/n8n/issues/19902) - hangs with JavaScript code nodes |
| **Queue mode limitation** | All MCP requests must route to single replica |
| **SSE complexity** | Requires proper proxy configuration |
| **Less control over state** | No built-in pending/confirm pattern |
| **Relay server changes** | Must implement MCP client protocol |

---

### Option B: Webhook Dispatcher + State Manager (Current Plan)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WEBHOOK DISPATCHER ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Voice Agent (Relay Server) ──── HTTP POST/PATCH/DELETE ────────────┐       │
│                                                                      │       │
│  ┌───────────────────────────────────────────────────────────────────▼────┐ │
│  │                    TOOL STATE MANAGER WORKFLOW                         │ │
│  │                    (Multiple webhook endpoints)                        │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │  POST   /voice-tools/pending     → Create PENDING tool call            │ │
│  │  POST   /voice-tools/confirm/:id → Execute tool, return result         │ │
│  │  PATCH  /voice-tools/modify/:id  → Update parameters                   │ │
│  │  DELETE /voice-tools/cancel/:id  → Cancel pending call                 │ │
│  │  GET    /voice-tools/context/:s  → Get agent context                   │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Webhook Advantages:**
| Feature | Benefit |
|---------|---------|
| **Full state control** | PENDING/CONFIRM/MODIFY/CANCEL states |
| **Agent context** | Query tool history, reference past calls |
| **Parameter modification** | User can correct inputs before execution |
| **Cancellation** | Halt tool calls before execution |
| **No known bugs** | Stable webhook/execute workflow pattern |
| **Simpler relay changes** | Standard REST calls |

**Webhook Disadvantages:**
| Issue | Impact |
|-------|--------|
| **Manual routing** | Must implement endpoint parsing |
| **No auto-discovery** | Tools hardcoded in relay server |
| **More n8n nodes** | ~15-20 nodes vs ~10 for MCP |

---

## Evaluation Matrix

| Criteria | MCP Trigger | Webhook Dispatcher | Winner |
|----------|-------------|-------------------|--------|
| **Observability** | Sub-workflow execution history | Sub-workflow + state table | Tie |
| **Tool discovery** | Automatic via MCP | Manual in relay server | MCP |
| **State management** | None built-in | Full PENDING/CONFIRM/CANCEL | Webhook |
| **Agent context** | No history access | Full history via /context | Webhook |
| **Relay complexity** | MCP client impl required | REST calls | Webhook |
| **Known bugs** | JS Code node hang | None | Webhook |
| **Parameter modification** | Not supported | Supported | Webhook |
| **Cancellation** | Not supported | Supported | Webhook |
| **Stability** | Newer, less tested | Mature pattern | Webhook |

---

## RECOMMENDATION

**For your use case (interruptible execution + agent context), Webhook Dispatcher is recommended.**

The MCP Trigger pattern is elegant for simple tool exposure, but:
1. **Does not support the pending/confirm/cancel flow** you requested
2. **Has a known bug with JavaScript Code nodes** (most of your tools use Code nodes)
3. **Cannot provide agent context** (history of tool calls)
4. **Cannot modify parameters** before execution

**However**, if you want the **best of both worlds**, we could implement:

### Hybrid Option C: MCP Trigger + State Layer (Detailed Analysis)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID MCP + STATE ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Voice Agent (Relay Server)                                                      │
│       │                                                                          │
│       │  MCP Client Connection (SSE persistent)                                  │
│       ▼                                                                          │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    MCP SERVER TRIGGER WORKFLOW                             │  │
│  │                    (Tool Discovery + State Routing)                        │  │
│  ├───────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                            │  │
│  │  MCP Server Trigger (path: /voice-agent)                                   │  │
│  │       │                                                                    │  │
│  │       ├──→ Tool: request_tool (creates PENDING, returns tool_call_id)      │  │
│  │       ├──→ Tool: confirm_tool (executes tool, returns result)              │  │
│  │       ├──→ Tool: modify_tool (updates parameters)                          │  │
│  │       ├──→ Tool: cancel_tool (cancels pending)                             │  │
│  │       └──→ Tool: get_context (returns tool history)                        │  │
│  │                                                                            │  │
│  │  Each tool is a Call n8n Sub-Workflow Tool pointing to:                    │  │
│  │                                                                            │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  Sub-Workflows:                                                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────────┐ │
│  │ request_tool_wf     │  │ confirm_tool_wf     │  │ Tool: send_email        │ │
│  │ (creates PENDING)   │  │ (routes to tool)    │──│ Tool: schedule_meeting  │ │
│  └─────────────────────┘  └─────────────────────┘  │ Tool: search_contacts   │ │
│                                                     │ ...etc                  │ │
│                                                     └─────────────────────────┘ │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Speed Analysis: Option C vs Option B

| Metric | Option B (Webhook) | Option C (Hybrid MCP) | Winner |
|--------|-------------------|----------------------|--------|
| **Connection Setup** | New TCP/TLS per request | Persistent SSE connection | **MCP (+50-100ms saved)** |
| **First Request** | ~100-200ms (TLS handshake) | ~500ms (SSE setup) | Webhook |
| **Subsequent Requests** | ~100-200ms each | ~20-50ms each | **MCP (5-10x faster)** |
| **Confirm Flow** | 2 HTTP calls (pending + confirm) | 2 MCP calls (same connection) | **MCP (faster)** |
| **Relay Overhead** | Simple HTTP client | MCP client library | Webhook (simpler) |

**Speed Verdict:** Option C is **faster for sustained conversations** due to SSE persistent connection. Option B is faster for single isolated calls.

#### Robustness Analysis: Option C vs Option B

| Metric | Option B (Webhook) | Option C (Hybrid MCP) | Winner |
|--------|-------------------|----------------------|--------|
| **Connection Stability** | Stateless (always works) | SSE can drop | **Webhook** |
| **Proxy Compatibility** | Universal | Requires SSE config | **Webhook** |
| **Error Recovery** | Simple retry | Must reconnect SSE | **Webhook** |
| **Known Bugs** | None | JS Code node hang ([#19902](https://github.com/n8n-io/n8n/issues/19902)) | **Webhook** |
| **Queue Mode** | Works with replicas | Single replica required | **Webhook** |
| **Debugging** | Standard HTTP logs | MCP protocol logs | **Webhook** |
| **Maturity** | Years of production use | Newer (2025) | **Webhook** |

**Robustness Verdict:** Option B is **more robust** due to simpler failure modes and no known bugs.

#### Complexity Analysis

| Component | Option B | Option C | Difference |
|-----------|----------|----------|------------|
| **n8n Workflows** | 9 (1 state manager + 8 tools) | 14 (1 MCP trigger + 5 state tools + 8 tools) | +5 workflows |
| **Relay Server** | REST client (simple) | MCP client library (complex) | +significant |
| **PostgreSQL** | tool_calls table | Same | Same |
| **Testing** | curl commands | MCP client test harness | +complexity |

#### The JS Code Node Bug (Critical)

From [GitHub Issue #19902](https://github.com/n8n-io/n8n/issues/19902):
> "When building a workflow with an MCP server trigger that uses call-n8n-workflow as a tool, which calls a sub-workflow containing a JavaScript code node... it hangs and executes forever."

**This affects 7 of your 8 tools** (all except Gmail send_email use Code nodes).

**Workaround options:**
1. Use Python code nodes instead (not affected)
2. Wait for n8n to fix the bug
3. Use Option B (Webhook) which doesn't have this issue

---

## Updated Recommendation

Given your requirements for **speed** and **robustness**:

| Requirement | Best Option |
|-------------|-------------|
| Interruptible execution | B or C (both support) |
| Agent context | B or C (both support) |
| Fastest sustained calls | **C (MCP)** |
| Most robust | **B (Webhook)** |
| Avoids known bugs | **B (Webhook)** |
| Simpler relay changes | **B (Webhook)** |

**My recommendation: Start with Option B (Webhook Dispatcher)**

Reasons:
1. The JS Code node bug in MCP is a blocker for 7/8 of your tools
2. Robustness > Speed for a production voice agent (dropped connections = bad UX)
3. Can migrate to Option C later when MCP matures and bug is fixed
4. ~100ms difference per call is negligible vs. conversation latency

**Alternative: If you really want MCP speed**, we could:
1. Implement Option C
2. Convert all Code nodes to Python (avoids the bug)
3. Accept the robustness tradeoffs

---

## SELECTED: Option C - Hybrid MCP + State Layer (Python Nodes)

**User Choice:** Option C with Python code nodes to avoid JS Code bug

**Key Implementation Notes:**
- All Code nodes will use **Python** instead of JavaScript
- MCP Server Trigger + Call n8n Sub-Workflow Tool pattern
- Full state management (PENDING/CONFIRM/MODIFY/CANCEL)
- Agent context via get_context tool

---

## NEW: Agent Context & Interruptible Tool Execution

### User Requirements (Added)
1. **Agent must have context of tool calls** - can reference what's pending
2. **Real-time progress updates** - agent knows when tool is executing
3. **Cancellation capability** - user can say "stop" or "cancel that"
4. **Input modification** - user can correct parameters before execution
5. **Tool call history** - agent can reference previous calls with specifics

### Architecture Enhancement: Pending State Pattern

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    INTERRUPTIBLE TOOL EXECUTION FLOW                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  User: "Send an email to john@example.com"                                       │
│       ↓                                                                          │
│  n8n: Create tool_call record (status: PENDING)                                  │
│       ↓                                                                          │
│  Callback → Voice Agent: "I'll send an email to john@example.com. Proceed?"      │
│       ↓                                                                          │
│  User: "Wait, make that john.smith@example.com"                                  │
│       ↓                                                                          │
│  n8n: UPDATE tool_call parameters (still PENDING)                                │
│       ↓                                                                          │
│  Callback → Voice Agent: "Updated to john.smith@example.com. Proceed?"           │
│       ↓                                                                          │
│  User: "Yes, send it"                                                            │
│       ↓                                                                          │
│  n8n: status → EXECUTING, execute sub-workflow                                   │
│       ↓                                                                          │
│  n8n: status → COMPLETED, log result                                             │
│       ↓                                                                          │
│  Callback → Voice Agent: "Email sent to john.smith@example.com"                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Tool Call States (State Machine)

| State | Description | Transitions |
|-------|-------------|-------------|
| `PENDING` | Tool call registered, awaiting confirmation | → EXECUTING, MODIFIED, CANCELLED |
| `MODIFIED` | Parameters updated by user | → PENDING (auto), CANCELLED |
| `EXECUTING` | Tool running in sub-workflow | → COMPLETED, FAILED |
| `COMPLETED` | Tool finished successfully | (terminal) |
| `FAILED` | Tool execution error | (terminal) |
| `CANCELLED` | User cancelled before execution | (terminal) |

### Database Schema (Enhanced)

```sql
-- tool_calls table (replaces tool_executions)
CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_call_id VARCHAR(100) UNIQUE,  -- Client-provided ID for correlation
    session_id VARCHAR(100) NOT NULL,
    connection_id VARCHAR(100),

    -- Tool details
    function_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL,
    parameters_history JSONB DEFAULT '[]',  -- Track modifications

    -- State tracking
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    status_history JSONB DEFAULT '[]',  -- Full audit trail

    -- Execution details
    workflow_id VARCHAR(100),
    result JSONB,
    error_message TEXT,
    voice_response TEXT,

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    execution_time_ms INTEGER,

    -- Indexes for agent queries
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'MODIFIED', 'EXECUTING', 'COMPLETED', 'FAILED', 'CANCELLED'))
);

-- Indexes for agent context queries
CREATE INDEX idx_tool_calls_session ON tool_calls(session_id, created_at DESC);
CREATE INDEX idx_tool_calls_status ON tool_calls(session_id, status);
CREATE INDEX idx_tool_calls_pending ON tool_calls(session_id) WHERE status = 'PENDING';
```

### Agent Context Query Examples

```sql
-- Get all pending tool calls for agent context
SELECT tool_call_id, function_name, parameters, created_at
FROM tool_calls
WHERE session_id = $1 AND status = 'PENDING'
ORDER BY created_at DESC;

-- Get tool call history for agent reference
SELECT function_name, parameters, result, status, voice_response, created_at
FROM tool_calls
WHERE session_id = $1 AND status IN ('COMPLETED', 'FAILED')
ORDER BY created_at DESC
LIMIT 10;

-- Get specific tool call for modification
SELECT * FROM tool_calls WHERE tool_call_id = $1;
```

### New Endpoints Required

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice-tools/pending` | POST | Create pending tool call, return tool_call_id |
| `/voice-tools/confirm/{id}` | POST | Confirm and execute pending tool |
| `/voice-tools/modify/{id}` | PATCH | Update parameters before execution |
| `/voice-tools/cancel/{id}` | DELETE | Cancel pending tool call |
| `/voice-tools/status/{id}` | GET | Get current status of tool call |
| `/voice-tools/context/{session}` | GET | Get all tool calls for agent context |

### Callback to Voice Agent (Status Updates)

```json
{
  "type": "tool_status",
  "tool_call_id": "tc_12345",
  "function_name": "send_email",
  "status": "PENDING",
  "parameters": {
    "to": "john.smith@example.com",
    "subject": "Meeting Tomorrow"
  },
  "message": "Ready to send email to john.smith@example.com. Say 'confirm' to proceed or 'cancel' to stop.",
  "actions_available": ["confirm", "modify", "cancel"]
}
```

---

## Research Summary (January 2026)

### Templates Analyzed
| Template ID | Name | Pattern | Relevance |
|------------|------|---------|-----------|
| 6247 | Fan-Out/Fan-In | **Execute Workflow + Static Data** | Direct match |
| 4508 | Multi-Platform AI Sales Agent | Modular sub-workflows | High |
| 4045 | Demo Call Center | Switch → Execute Workflow | High |
| 4150 | Route User Requests | LLM Router → Sub-workflows | Medium |
| 4046 | Taxi Service | Tool Workflow pattern | Medium |

### Key Findings
1. **Execute Workflow pattern provides best observability** - each tool has independent execution history
2. **Static Data** enables cross-workflow status tracking
3. **Per-workflow logging** allows tool-specific metrics (duration, success rate, errors)
4. **Independent versioning** - update one tool without touching others

---

## Architecture Overview (With Interruptible Execution)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE VOICE AGENT SYSTEM                                  │
│              Execute Workflow Dispatcher + Interruptible Execution                │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  Voice Agent (Relay Server)                                                       │
│       │                                                                           │
│       │  1. Tool request (function + args)                                        │
│       ▼                                                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐      │
│  │                    TOOL STATE MANAGER WORKFLOW                          │      │
│  │                    (Controls pending/confirm/cancel)                    │      │
│  ├────────────────────────────────────────────────────────────────────────┤      │
│  │                                                                         │      │
│  │  Webhook /voice-tools/pending (POST)                                    │      │
│  │       ↓                                                                 │      │
│  │  Generate tool_call_id + Insert PENDING → PostgreSQL                    │      │
│  │       ↓                                                                 │      │
│  │  Return {tool_call_id, status: "PENDING", confirmation_message}         │      │
│  │                                                                         │      │
│  │  ────────────────────────────────────────────────                      │      │
│  │                                                                         │      │
│  │  Webhook /voice-tools/confirm/{id} (POST)                               │      │
│  │       ↓                                                                 │      │
│  │  Update status → EXECUTING                                              │      │
│  │       ↓                                                                 │      │
│  │  Execute Sub-Workflow (DYNAMIC by function_name)                        │      │
│  │       │                                                                 │      │
│  │       ├──→ Voice Tool: schedule_meeting                                 │      │
│  │       ├──→ Voice Tool: send_email (Gmail REAL)                          │      │
│  │       ├──→ Voice Tool: search_contacts                                  │      │
│  │       ├──→ Voice Tool: get_calendar_availability                        │      │
│  │       ├──→ Voice Tool: create_task                                      │      │
│  │       ├──→ Voice Tool: search_documentation                             │      │
│  │       ├──→ Voice Tool: get_training_progress                            │      │
│  │       └──→ Voice Tool: knowledge_check                                  │      │
│  │       ↓                                                                 │      │
│  │  Update status → COMPLETED + log result                                 │      │
│  │       ↓                                                                 │      │
│  │  Return {status: "COMPLETED", result, voice_response}                   │      │
│  │                                                                         │      │
│  │  ────────────────────────────────────────────────                      │      │
│  │                                                                         │      │
│  │  Webhook /voice-tools/modify/{id} (PATCH)                               │      │
│  │       ↓                                                                 │      │
│  │  Update parameters + append to parameters_history                       │      │
│  │       ↓                                                                 │      │
│  │  Return {status: "PENDING", updated_parameters}                         │      │
│  │                                                                         │      │
│  │  ────────────────────────────────────────────────                      │      │
│  │                                                                         │      │
│  │  Webhook /voice-tools/cancel/{id} (DELETE)                              │      │
│  │       ↓                                                                 │      │
│  │  Update status → CANCELLED                                              │      │
│  │       ↓                                                                 │      │
│  │  Return {status: "CANCELLED"}                                           │      │
│  │                                                                         │      │
│  │  ────────────────────────────────────────────────                      │      │
│  │                                                                         │      │
│  │  Webhook /voice-tools/context/{session} (GET)                           │      │
│  │       ↓                                                                 │      │
│  │  Query tool_calls for session (pending + recent history)                │      │
│  │       ↓                                                                 │      │
│  │  Return {pending: [...], recent: [...]}                                 │      │
│  │                                                                         │      │
│  └────────────────────────────────────────────────────────────────────────┘      │
│                                                                                   │
│  Each Sub-Workflow (8 total):                                                     │
│  ┌────────────────────────────────────────────────────────────────────────┐      │
│  │  Execute Workflow Trigger (receives tool_call_id + parameters)          │      │
│  │       ↓                                                                 │      │
│  │  Tool Implementation (Code/Gmail/HTTP/etc.)                             │      │
│  │       ↓                                                                 │      │
│  │  Format Voice Response                                                  │      │
│  │       ↓                                                                 │      │
│  │  Return {result, voice_response}                                        │      │
│  └────────────────────────────────────────────────────────────────────────┘      │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Workflow Separation

| Workflow | Purpose | Trigger |
|----------|---------|---------|
| **Tool State Manager** | Handle pending/confirm/modify/cancel/context | Multiple webhooks |
| **Voice Tool: send_email** | Execute Gmail send | Execute Workflow Trigger |
| **Voice Tool: schedule_meeting** | Execute calendar booking | Execute Workflow Trigger |
| **...6 more tools** | Execute specific tool logic | Execute Workflow Trigger |

---

## Observability Benefits

| Metric | Single Code Node | Execute Workflow Dispatcher |
|--------|-----------------|----------------------------|
| **Per-tool execution history** | None | Full history per workflow |
| **Tool-specific error logs** | Mixed in one log | Isolated per workflow |
| **Execution duration tracking** | Combined | Individual per tool |
| **Independent versioning** | All-or-nothing | Update one tool at a time |
| **A/B testing** | Impossible | Enable/disable individual tools |
| **Debugging** | Parse entire code | Drill into specific workflow |
| **Success rate by tool** | Manual calculation | Built-in n8n metrics |

---

## Workflow Structure

### Main Dispatcher Workflow
**Name:** `Voice Tools Dispatcher`
**ID:** To be created (replaces `xkjMMQkor7oxoAmu`)

```
Nodes (4 total):
1. Webhook (/voice-tools)
2. Set (extract function name)
3. Execute Workflow (dynamic ID lookup)
4. Respond to Webhook
```

**Execute Workflow Node Configuration:**
```javascript
// Dynamic workflow selection by tool name
{
  "source": "expression",
  "workflowId": "={{ $json.toolWorkflows[$json.body.function] }}",
  "mode": "wait"  // Wait for sub-workflow to complete
}
```

**Tool Workflow Mapping:**
```json
{
  "toolWorkflows": {
    "schedule_meeting": "WORKFLOW_ID_1",
    "send_email": "WORKFLOW_ID_2",
    "search_contacts": "WORKFLOW_ID_3",
    "get_calendar_availability": "WORKFLOW_ID_4",
    "create_task": "WORKFLOW_ID_5",
    "search_documentation": "WORKFLOW_ID_6",
    "get_training_progress": "WORKFLOW_ID_7",
    "knowledge_check": "WORKFLOW_ID_8"
  }
}
```

---

### Sub-Workflow Template (for each tool)

**Structure (5 nodes):**
```
1. Execute Workflow Trigger
       ↓
2. Tool Implementation (Code/Gmail/HTTP/etc.)
       ↓
3. Format Response (Code - add voice_response)
       ↓
4. Log to PostgreSQL (tool_executions table)
       ↓
5. Return Result (to parent workflow)
```

---

## Implementation Plan (Revised)

### Phase 1: Database Schema (Create First)

```sql
-- Run in PostgreSQL before creating workflows
CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_call_id VARCHAR(100) UNIQUE,
    session_id VARCHAR(100) NOT NULL,
    connection_id VARCHAR(100),
    function_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL,
    parameters_history JSONB DEFAULT '[]',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    status_history JSONB DEFAULT '[]',
    workflow_id VARCHAR(100),
    result JSONB,
    error_message TEXT,
    voice_response TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    execution_time_ms INTEGER,
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'MODIFIED', 'EXECUTING', 'COMPLETED', 'FAILED', 'CANCELLED'))
);

CREATE INDEX idx_tool_calls_session ON tool_calls(session_id, created_at DESC);
CREATE INDEX idx_tool_calls_status ON tool_calls(session_id, status);
CREATE INDEX idx_tool_calls_pending ON tool_calls(session_id) WHERE status = 'PENDING';
```

### Phase 2: Create Tool State Manager Workflow (1 workflow, 5 webhook paths)

**Name:** `Tool State Manager`

This single workflow handles ALL state transitions with multiple webhook entry points.

**Nodes (approx 15-20):**

```
Webhook: /voice-tools/pending ─────────────────────────────────────────┐
    ↓                                                                   │
    Code: Generate tool_call_id (tc_uuid)                               │
    ↓                                                                   │
    PostgreSQL: INSERT tool_calls (PENDING)                             │
    ↓                                                                   │
    Code: Build confirmation message                                    │
    ↓                                                                   │
    Respond: {tool_call_id, status, message}                            │
                                                                        │
────────────────────────────────────────────────────────────────────────│
                                                                        │
Webhook: /voice-tools/confirm/:id ──────────────────────────────────────┤
    ↓                                                                   │
    PostgreSQL: SELECT tool_call WHERE tool_call_id = :id               │
    ↓                                                                   │
    IF: status == 'PENDING'?                                            │
        ↓ YES                                                           │
        PostgreSQL: UPDATE status = 'EXECUTING'                         │
        ↓                                                               │
        Set: Build workflow mapping                                     │
        ↓                                                               │
        Execute Workflow: $toolWorkflows[function_name]                 │
            ├──→ Voice Tool: schedule_meeting                           │
            ├──→ Voice Tool: send_email                                 │
            ├──→ Voice Tool: search_contacts                            │
            ├──→ Voice Tool: get_calendar_availability                  │
            ├──→ Voice Tool: create_task                                │
            ├──→ Voice Tool: search_documentation                       │
            ├──→ Voice Tool: get_training_progress                      │
            └──→ Voice Tool: knowledge_check                            │
        ↓                                                               │
        PostgreSQL: UPDATE status = 'COMPLETED', result, voice_response │
        ↓                                                               │
        Respond: {status, result, voice_response}                       │
        ↓ NO (status != PENDING)                                        │
        Respond: {error: "Cannot confirm non-pending tool call"}        │
                                                                        │
────────────────────────────────────────────────────────────────────────│
                                                                        │
Webhook: /voice-tools/modify/:id ───────────────────────────────────────┤
    ↓                                                                   │
    PostgreSQL: SELECT tool_call WHERE tool_call_id = :id               │
    ↓                                                                   │
    IF: status == 'PENDING'?                                            │
        ↓ YES                                                           │
        Code: Merge parameters, append to history                       │
        ↓                                                               │
        PostgreSQL: UPDATE parameters, parameters_history               │
        ↓                                                               │
        Respond: {status: "PENDING", updated_parameters}                │
        ↓ NO                                                            │
        Respond: {error: "Cannot modify non-pending tool call"}         │
                                                                        │
────────────────────────────────────────────────────────────────────────│
                                                                        │
Webhook: /voice-tools/cancel/:id ───────────────────────────────────────┤
    ↓                                                                   │
    PostgreSQL: UPDATE status = 'CANCELLED' WHERE id = :id              │
    ↓                                                                   │
    Respond: {status: "CANCELLED"}                                      │
                                                                        │
────────────────────────────────────────────────────────────────────────│
                                                                        │
Webhook: /voice-tools/context/:session ─────────────────────────────────┘
    ↓
    PostgreSQL: SELECT pending FROM tool_calls WHERE session_id = :session AND status = 'PENDING'
    ↓
    PostgreSQL: SELECT recent FROM tool_calls WHERE session_id = :session AND status IN ('COMPLETED', 'FAILED') LIMIT 10
    ↓
    Code: Combine into context object
    ↓
    Respond: {pending: [...], recent: [...]}
```

### Phase 3: Create Sub-Workflows (8 workflows)

| # | Workflow Name | Node Type | Purpose |
|---|--------------|-----------|---------|
| 1 | Voice Tool: schedule_meeting | Code | Mock calendar |
| 2 | Voice Tool: send_email | Gmail | **REAL** email |
| 3 | Voice Tool: search_contacts | Code | Mock CRM |
| 4 | Voice Tool: get_calendar_availability | Code | Mock calendar |
| 5 | Voice Tool: create_task | Code | Mock task manager |
| 6 | Voice Tool: search_documentation | Code | Mock knowledge base |
| 7 | Voice Tool: get_training_progress | Code | Mock training |
| 8 | Voice Tool: knowledge_check | Code | Mock assessment |

**Each sub-workflow is SIMPLE (3-4 nodes):**
```
Execute Workflow Trigger
    ↓
Tool Implementation (Code/Gmail/HTTP)
    ↓
Format Voice Response (Code)
    ↓
Return Result
```

**Note:** PostgreSQL logging moved to Tool State Manager (after Execute Workflow returns).
This keeps sub-workflows focused on tool logic only.

### Phase 4: Relay Server Updates (Railway)

The relay server needs to be updated to use the new pending/confirm flow:

**Current Flow (synchronous):**
```
User says "send email" → relay calls /voice-tools → waits → returns result
```

**New Flow (interruptible):**
```
User says "send email"
    ↓
Relay calls POST /voice-tools/pending
    ↓
n8n returns: {tool_call_id: "tc_123", status: "PENDING", message: "..."}
    ↓
Voice agent says: "I'll send an email to X. Say 'confirm' to proceed."
    ↓
User says "yes" or "confirm"
    ↓
Relay calls POST /voice-tools/confirm/tc_123
    ↓
n8n executes tool, returns result
    ↓
Voice agent announces result
```

**Modification scenarios:**
```
Voice agent: "I'll send an email to john@example.com. Confirm?"
User: "Wait, use john.smith@example.com instead"
    ↓
Relay calls PATCH /voice-tools/modify/tc_123 {parameters: {to: "john.smith@..."}}
    ↓
n8n returns updated parameters
    ↓
Voice agent: "Updated to john.smith@example.com. Confirm?"
```

**Cancellation:**
```
Voice agent: "I'll schedule a meeting for tomorrow at 3pm. Confirm?"
User: "Cancel that" or "Nevermind"
    ↓
Relay calls DELETE /voice-tools/cancel/tc_123
    ↓
n8n returns: {status: "CANCELLED"}
    ↓
Voice agent: "Cancelled."
```

**Context for agent decisions:**
```
When voice agent needs to reference history:
    ↓
Relay calls GET /voice-tools/context/{session_id}
    ↓
n8n returns: {
  pending: [{tool_call_id, function_name, parameters, created_at}],
  recent: [{function_name, result, voice_response, status, created_at}]
}
    ↓
Agent can say: "I previously scheduled a meeting for 3pm and sent an email to john@..."
```

---

## Verification Steps

### 1. Database Schema
```bash
# Verify table exists in PostgreSQL
psql -c "SELECT * FROM tool_calls LIMIT 1;"
```

### 2. Create All Sub-Workflows (8 total)
```bash
# For each tool, create workflow via MCP
mcp__n8n-mcp__n8n_create_workflow({
  name: "Voice Tool: {tool_name}",
  nodes: [executeWorkflowTrigger, implementation, formatResponse],
  connections: {...}
})

# Record workflow IDs for state manager mapping
```

### 3. Create Tool State Manager
```bash
mcp__n8n-mcp__n8n_create_workflow({
  name: "Tool State Manager",
  nodes: [webhooks, postgres, code, executeWorkflow, respond],
  connections: {...}
})
```

### 4. Test Pending Flow
```bash
# 1. Create pending tool call
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/voice-tools/pending \
  -H "Content-Type: application/json" \
  -d '{"session_id":"test_123","function":"send_email","parameters":{"to":"test@example.com","subject":"Test"}}'

# Expected response:
# {"tool_call_id":"tc_abc123","status":"PENDING","message":"Ready to send email to test@example.com. Confirm to proceed."}

# 2. Verify in PostgreSQL
psql -c "SELECT * FROM tool_calls WHERE session_id='test_123';"
# Should show status='PENDING'
```

### 5. Test Modify Flow
```bash
# Update parameters before confirmation
curl -X PATCH https://jayconnorexe.app.n8n.cloud/webhook/voice-tools/modify/tc_abc123 \
  -H "Content-Type: application/json" \
  -d '{"parameters":{"to":"updated@example.com"}}'

# Expected: {"status":"PENDING","updated_parameters":{...}}

# Verify history tracked
psql -c "SELECT parameters, parameters_history FROM tool_calls WHERE tool_call_id='tc_abc123';"
```

### 6. Test Cancel Flow
```bash
# Cancel a pending tool call
curl -X DELETE https://jayconnorexe.app.n8n.cloud/webhook/voice-tools/cancel/tc_abc123

# Expected: {"status":"CANCELLED"}

# Verify in database
psql -c "SELECT status FROM tool_calls WHERE tool_call_id='tc_abc123';"
# Should show 'CANCELLED'
```

### 7. Test Confirm + Execute Flow
```bash
# Create new pending call
curl -X POST .../voice-tools/pending -d '{"session_id":"test_456","function":"send_email",...}'
# Returns: {"tool_call_id":"tc_def456","status":"PENDING",...}

# Confirm and execute
curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/voice-tools/confirm/tc_def456

# Expected: {"status":"COMPLETED","result":{...},"voice_response":"Email sent successfully."}

# Verify:
# 1. n8n shows Tool State Manager execution
# 2. n8n shows Voice Tool: send_email sub-workflow execution
# 3. PostgreSQL shows status='COMPLETED' with result
```

### 8. Test Context Endpoint
```bash
# Get agent context for a session
curl -X GET https://jayconnorexe.app.n8n.cloud/webhook/voice-tools/context/test_456

# Expected:
# {
#   "pending": [],
#   "recent": [{"function_name":"send_email","status":"COMPLETED","voice_response":"..."}]
# }
```

### 9. Verify Full Observability
- **n8n Dashboard**: Separate execution counts for Tool State Manager + each sub-workflow
- **PostgreSQL**: Complete audit trail with status_history, parameters_history
- **Error Isolation**: Fail one tool, verify others unaffected
- **Timing**: execution_time_ms tracked per tool call

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| PostgreSQL | CREATE | `tool_calls` table with state machine |
| n8n cloud | CREATE | 1 Tool State Manager + 8 sub-workflows (9 total) |
| Relay Server | UPDATE | Add pending/confirm/modify/cancel flow |
| Existing workflow | DEACTIVATE | `xkjMMQkor7oxoAmu` after validation |

---

## Success Criteria

### Core Functionality
- [ ] All 8 sub-workflows created and active
- [ ] Tool State Manager routes correctly to sub-workflows
- [ ] Each tool has independent execution history in n8n
- [ ] Gmail sends real emails via sub-workflow
- [ ] Mock tools return realistic data

### Interruptible Execution (NEW)
- [ ] `POST /pending` creates PENDING record, returns tool_call_id
- [ ] `PATCH /modify/{id}` updates parameters, tracks history
- [ ] `DELETE /cancel/{id}` sets status to CANCELLED
- [ ] `POST /confirm/{id}` executes tool, returns result
- [ ] `GET /context/{session}` returns pending + recent tool calls

### Agent Context (NEW)
- [ ] Agent can query pending tool calls for current session
- [ ] Agent can reference specific tool call by tool_call_id
- [ ] Agent can see parameter modification history
- [ ] Agent can access recent tool call results with voice_response

### Observability
- [ ] PostgreSQL: Full audit trail (status_history, parameters_history)
- [ ] n8n: Separate execution counts per tool
- [ ] Error isolation: One tool failure doesn't affect others
- [ ] Timing: execution_time_ms tracked per tool call

---

## Node TypeVersions (Latest)

| Node | typeVersion | Notes |
|------|-------------|-------|
| webhook | 2.1 | Path without leading `/` |
| set | 3.4 | Use `setValue` operation |
| executeWorkflow | 1.2 | Dynamic ID via expression |
| respondToWebhook | 1.5 | JSON response |
| code | 2 | Return array `[{...}]` |
| postgres | 2.6 | Use `mappingMode: "defineBelow"` |
| gmail | 2.2 | OAuth2 credentials |
| executeWorkflowTrigger | 1.1 | Entry for sub-workflows |
| if | 2.2 | Status checks |

---

## Execution Order

### Phase 1: Database (5 min)
1. Create `tool_calls` table in PostgreSQL
2. Verify indexes created

### Phase 2: Sub-Workflows (20 min)
3. Create 8 sub-workflows via MCP (can be parallel)
4. Record all workflow IDs

### Phase 3: Tool State Manager (15 min)
5. Create Tool State Manager with 5 webhook paths
6. Add workflow ID mapping for all 8 tools
7. Activate workflow

### Phase 4: Testing (15 min)
8. Test pending flow
9. Test modify flow
10. Test cancel flow
11. Test confirm + execute flow
12. Test context endpoint

### Phase 5: Cleanup
13. Verify all observability criteria met
14. Deactivate old workflow `xkjMMQkor7oxoAmu`

**Estimated time:** ~55 minutes (increased due to new endpoints)

---

## DATA FLOW ANALYSIS: Option C - Hybrid MCP + State Layer

### Complete Process Map: "Updating Email" Use Case

This section traces the exact data flow for the scenario where a user requests an email, provides the wrong email address, then corrects it before execution.

---

### Scenario: User Says Wrong Email, Then Corrects It

**Voice Conversation:**
```
User: "Send an email to john@gmail.com about the meeting tomorrow"
Agent: "I'll send an email to john@gmail.com about the meeting. Confirm?"
User: "Wait, that should be john.smith@gmail.com"
Agent: "Updated to john.smith@gmail.com. Confirm?"
User: "Yes, send it"
Agent: "Email sent to john.smith@gmail.com successfully."
```

---

### STEP 1: Initial Tool Request (Wrong Email)

**Time: T+0ms**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ RELAY SERVER (Railway)                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OpenAI Realtime API → function_call detected                                │
│       │                                                                      │
│       │  Function: send_email                                                │
│       │  Arguments: {                                                        │
│       │    "to": "john@gmail.com",                                           │
│       │    "subject": "Meeting Tomorrow",                                    │
│       │    "body": "Let's discuss the project..."                            │
│       │  }                                                                   │
│       ▼                                                                      │
│  MCP Client Library                                                          │
│       │                                                                      │
│       │  SSE Connection (persistent, already established)                    │
│       │  Tool Call: request_tool                                             │
│       │  Payload: {                                                          │
│       │    "session_id": "sess_abc123",                                      │
│       │    "function_name": "send_email",                                    │
│       │    "parameters": {                                                   │
│       │      "to": "john@gmail.com",                                         │
│       │      "subject": "Meeting Tomorrow",                                  │
│       │      "body": "Let's discuss the project..."                          │
│       │    }                                                                 │
│       │  }                                                                   │
│       ▼                                                                      │
│  SSE POST to n8n MCP Server Trigger                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Time: T+20ms** (SSE is fast - no TLS handshake)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ N8N: MCP SERVER TRIGGER WORKFLOW                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MCP Server Trigger (path: /voice-agent)                                     │
│       │                                                                      │
│       │  Receives: { tool: "request_tool", input: {...} }                    │
│       │  Routes to: Call n8n Sub-Workflow Tool (request_tool_wf)             │
│       ▼                                                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Time: T+30ms**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ N8N: REQUEST_TOOL SUB-WORKFLOW                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Execute Workflow Trigger                                                    │
│       │  Input: { session_id, function_name, parameters }                    │
│       ▼                                                                      │
│  Code Node (Python): Generate tool_call_id                                   │
│       │                                                                      │
│       │  import uuid                                                         │
│       │  tool_call_id = f"tc_{uuid.uuid4().hex[:12]}"                        │
│       │  # Result: "tc_a1b2c3d4e5f6"                                         │
│       ▼                                                                      │
│  PostgreSQL: INSERT INTO tool_calls                                          │
│       │                                                                      │
│       │  INSERT INTO tool_calls (                                            │
│       │    tool_call_id, session_id, function_name,                          │
│       │    parameters, status, created_at                                    │
│       │  ) VALUES (                                                          │
│       │    'tc_a1b2c3d4e5f6',                                                │
│       │    'sess_abc123',                                                    │
│       │    'send_email',                                                     │
│       │    '{"to":"john@gmail.com","subject":"Meeting Tomorrow",...}',       │
│       │    'PENDING',                                                        │
│       │    NOW()                                                             │
│       │  );                                                                  │
│       ▼                                                                      │
│  Code Node (Python): Build confirmation message                              │
│       │                                                                      │
│       │  params = items[0].json["parameters"]                                │
│       │  message = f"I'll send an email to {params['to']} "                  │
│       │          + f"about '{params['subject']}'. Confirm to proceed."       │
│       ▼                                                                      │
│  Return Result                                                               │
│       │                                                                      │
│       │  {                                                                   │
│       │    "tool_call_id": "tc_a1b2c3d4e5f6",                                │
│       │    "status": "PENDING",                                              │
│       │    "function_name": "send_email",                                    │
│       │    "parameters": {                                                   │
│       │      "to": "john@gmail.com",                                         │
│       │      "subject": "Meeting Tomorrow",                                  │
│       │      "body": "Let's discuss the project..."                          │
│       │    },                                                                │
│       │    "message": "I'll send an email to john@gmail.com about            │
│       │               'Meeting Tomorrow'. Confirm to proceed.",              │
│       │    "actions_available": ["confirm", "modify", "cancel"]              │
│       │  }                                                                   │
│       ▼                                                                      │
│  → MCP Server Trigger returns to client                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Time: T+80ms** (Total: request → PENDING response)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ RELAY SERVER                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MCP Response received                                                       │
│       │                                                                      │
│       │  Store: pending_tool_calls["tc_a1b2c3d4e5f6"] = response             │
│       │                                                                      │
│       ▼                                                                      │
│  OpenAI Realtime API: Add to conversation                                    │
│       │                                                                      │
│       │  function_call_output: {                                             │
│       │    status: "pending_confirmation",                                   │
│       │    message: "I'll send an email to john@gmail.com..."                │
│       │  }                                                                   │
│       ▼                                                                      │
│  TTS Output: "I'll send an email to john@gmail.com about                     │
│               Meeting Tomorrow. Confirm to proceed."                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**DATABASE STATE AFTER STEP 1:**
```sql
SELECT * FROM tool_calls WHERE tool_call_id = 'tc_a1b2c3d4e5f6';

┌─────────────────┬──────────────┬──────────────┬─────────────────────────────┬─────────┐
│ tool_call_id    │ session_id   │ function     │ parameters                  │ status  │
├─────────────────┼──────────────┼──────────────┼─────────────────────────────┼─────────┤
│ tc_a1b2c3d4e5f6 │ sess_abc123  │ send_email   │ {"to":"john@gmail.com",...} │ PENDING │
└─────────────────┴──────────────┴──────────────┴─────────────────────────────┴─────────┘
```

---

### STEP 2: User Corrects Email Address

**Time: T+3000ms** (User speaks correction)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ RELAY SERVER                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OpenAI Realtime API → Transcription                                         │
│       │                                                                      │
│       │  User: "Wait, that should be john.smith@gmail.com"                   │
│       │                                                                      │
│       ▼                                                                      │
│  Intent Detection (OpenAI decides this is a modification)                    │
│       │                                                                      │
│       │  Function: modify_tool                                               │
│       │  Arguments: {                                                        │
│       │    "tool_call_id": "tc_a1b2c3d4e5f6",                                │
│       │    "parameters": {                                                   │
│       │      "to": "john.smith@gmail.com"                                    │
│       │    }                                                                 │
│       │  }                                                                   │
│       ▼                                                                      │
│  MCP Client: Tool Call to modify_tool                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Time: T+3020ms**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ N8N: MODIFY_TOOL SUB-WORKFLOW                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Execute Workflow Trigger                                                    │
│       │  Input: { tool_call_id, parameters (partial update) }                │
│       ▼                                                                      │
│  PostgreSQL: SELECT current state                                            │
│       │                                                                      │
│       │  SELECT * FROM tool_calls                                            │
│       │  WHERE tool_call_id = 'tc_a1b2c3d4e5f6';                             │
│       │                                                                      │
│       │  Result: status = 'PENDING', parameters = {...}                      │
│       ▼                                                                      │
│  IF Node: status == 'PENDING'?                                               │
│       │                                                                      │
│       │  YES → Continue                                                      │
│       ▼                                                                      │
│  Code Node (Python): Merge parameters + append history                       │
│       │                                                                      │
│       │  # Get existing data                                                 │
│       │  existing = items[0].json                                            │
│       │  old_params = existing["parameters"]                                 │
│       │  new_params = input["parameters"]                                    │
│       │                                                                      │
│       │  # Merge (new overwrites old)                                        │
│       │  merged = {**old_params, **new_params}                               │
│       │  # Result: {"to":"john.smith@gmail.com",                             │
│       │  #          "subject":"Meeting Tomorrow",                            │
│       │  #          "body":"Let's discuss..."}                               │
│       │                                                                      │
│       │  # Build history entry                                               │
│       │  history_entry = {                                                   │
│       │    "timestamp": datetime.utcnow().isoformat(),                       │
│       │    "old_value": old_params["to"],                                    │
│       │    "new_value": new_params["to"],                                    │
│       │    "field": "to"                                                     │
│       │  }                                                                   │
│       ▼                                                                      │
│  PostgreSQL: UPDATE tool_calls                                               │
│       │                                                                      │
│       │  UPDATE tool_calls SET                                               │
│       │    parameters = '{"to":"john.smith@gmail.com",...}',                 │
│       │    parameters_history = parameters_history || '[{                    │
│       │      "timestamp": "2026-01-12T15:30:03Z",                            │
│       │      "old_value": "john@gmail.com",                                  │
│       │      "new_value": "john.smith@gmail.com",                            │
│       │      "field": "to"                                                   │
│       │    }]'::jsonb,                                                       │
│       │    status_history = status_history || '[{                            │
│       │      "status": "MODIFIED",                                           │
│       │      "timestamp": "2026-01-12T15:30:03Z"                             │
│       │    }]'::jsonb                                                        │
│       │  WHERE tool_call_id = 'tc_a1b2c3d4e5f6';                             │
│       ▼                                                                      │
│  Code Node (Python): Build updated confirmation                              │
│       │                                                                      │
│       │  message = f"Updated recipient to {merged['to']}. Confirm?"          │
│       ▼                                                                      │
│  Return Result                                                               │
│       │                                                                      │
│       │  {                                                                   │
│       │    "tool_call_id": "tc_a1b2c3d4e5f6",                                │
│       │    "status": "PENDING",                                              │
│       │    "updated_parameters": {                                           │
│       │      "to": "john.smith@gmail.com",                                   │
│       │      "subject": "Meeting Tomorrow",                                  │
│       │      "body": "Let's discuss the project..."                          │
│       │    },                                                                │
│       │    "message": "Updated recipient to john.smith@gmail.com. Confirm?", │
│       │    "modification_applied": {                                         │
│       │      "field": "to",                                                  │
│       │      "old": "john@gmail.com",                                        │
│       │      "new": "john.smith@gmail.com"                                   │
│       │    }                                                                 │
│       │  }                                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Time: T+3070ms**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ RELAY SERVER                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MCP Response: modification confirmed                                        │
│       │                                                                      │
│       │  Update local cache:                                                 │
│       │  pending_tool_calls["tc_a1b2c3d4e5f6"].parameters = updated          │
│       ▼                                                                      │
│  OpenAI Realtime API: function_call_output                                   │
│       │                                                                      │
│       │  {                                                                   │
│       │    status: "pending_confirmation",                                   │
│       │    message: "Updated to john.smith@gmail.com",                       │
│       │    modification: "Changed 'to' from john@... to john.smith@..."      │
│       │  }                                                                   │
│       ▼                                                                      │
│  TTS Output: "Updated recipient to john.smith@gmail.com. Confirm?"           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**DATABASE STATE AFTER STEP 2:**
```sql
SELECT tool_call_id, parameters, parameters_history, status
FROM tool_calls WHERE tool_call_id = 'tc_a1b2c3d4e5f6';

┌─────────────────┬───────────────────────────────┬────────────────────────────────────────────┬─────────┐
│ tool_call_id    │ parameters                    │ parameters_history                         │ status  │
├─────────────────┼───────────────────────────────┼────────────────────────────────────────────┼─────────┤
│ tc_a1b2c3d4e5f6 │ {"to":"john.smith@gmail.com", │ [{"timestamp":"2026-01-12T15:30:03Z",      │ PENDING │
│                 │  "subject":"Meeting Tomorrow",│   "old_value":"john@gmail.com",            │         │
│                 │  "body":"Let's discuss..."}   │   "new_value":"john.smith@gmail.com",      │         │
│                 │                               │   "field":"to"}]                           │         │
└─────────────────┴───────────────────────────────┴────────────────────────────────────────────┴─────────┘
```

---

### STEP 3: User Confirms Execution

**Time: T+5000ms** (User says "Yes, send it")

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ RELAY SERVER                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  OpenAI Realtime API → Transcription                                         │
│       │                                                                      │
│       │  User: "Yes, send it"                                                │
│       │                                                                      │
│       ▼                                                                      │
│  Intent Detection (OpenAI decides this is a confirmation)                    │
│       │                                                                      │
│       │  Function: confirm_tool                                              │
│       │  Arguments: {                                                        │
│       │    "tool_call_id": "tc_a1b2c3d4e5f6"                                 │
│       │  }                                                                   │
│       ▼                                                                      │
│  MCP Client: Tool Call to confirm_tool                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Time: T+5020ms**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ N8N: CONFIRM_TOOL SUB-WORKFLOW                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Execute Workflow Trigger                                                    │
│       │  Input: { tool_call_id }                                             │
│       ▼                                                                      │
│  PostgreSQL: SELECT + validate status                                        │
│       │                                                                      │
│       │  SELECT * FROM tool_calls                                            │
│       │  WHERE tool_call_id = 'tc_a1b2c3d4e5f6';                             │
│       │                                                                      │
│       │  Result: status = 'PENDING', function_name = 'send_email',           │
│       │          parameters = {"to":"john.smith@gmail.com",...}              │
│       ▼                                                                      │
│  IF Node: status == 'PENDING'?                                               │
│       │                                                                      │
│       │  YES → Continue to execution                                         │
│       ▼                                                                      │
│  PostgreSQL: UPDATE status = 'EXECUTING'                                     │
│       │                                                                      │
│       │  UPDATE tool_calls SET                                               │
│       │    status = 'EXECUTING',                                             │
│       │    confirmed_at = NOW(),                                             │
│       │    executed_at = NOW(),                                              │
│       │    status_history = status_history || '[{                            │
│       │      "status": "EXECUTING",                                          │
│       │      "timestamp": "2026-01-12T15:30:05Z"                             │
│       │    }]'::jsonb                                                        │
│       │  WHERE tool_call_id = 'tc_a1b2c3d4e5f6';                             │
│       ▼                                                                      │
│  Set Node: Build workflow mapping                                            │
│       │                                                                      │
│       │  toolWorkflows = {                                                   │
│       │    "send_email": "WF_SEND_EMAIL_ID",                                 │
│       │    "schedule_meeting": "WF_SCHEDULE_MEETING_ID",                     │
│       │    ...                                                               │
│       │  }                                                                   │
│       │                                                                      │
│       │  targetWorkflowId = toolWorkflows["send_email"]                      │
│       ▼                                                                      │
│  Execute Workflow Node: Call sub-workflow                                    │
│       │                                                                      │
│       │  workflowId: "WF_SEND_EMAIL_ID"                                      │
│       │  mode: "wait" (synchronous)                                          │
│       │  data: {                                                             │
│       │    tool_call_id: "tc_a1b2c3d4e5f6",                                  │
│       │    parameters: {                                                     │
│       │      "to": "john.smith@gmail.com",                                   │
│       │      "subject": "Meeting Tomorrow",                                  │
│       │      "body": "Let's discuss the project..."                          │
│       │    }                                                                 │
│       │  }                                                                   │
│       ▼                                                                      │
│  ───────────────────────────────────────────────────────────────────────    │
│  │                                                                     │    │
│  │  SUB-WORKFLOW: Voice Tool: send_email (separate execution history)  │    │
│  │                                                                     │    │
│  │  Execute Workflow Trigger                                           │    │
│  │       │                                                             │    │
│  │       ▼                                                             │    │
│  │  Gmail Node (typeVersion: 2.2)                                      │    │
│  │       │                                                             │    │
│  │       │  operation: "send"                                          │    │
│  │       │  sendTo: "john.smith@gmail.com"                             │    │
│  │       │  subject: "Meeting Tomorrow"                                │    │
│  │       │  message: "Let's discuss the project..."                    │    │
│  │       │  credentials: "Gmail OAuth2"                                │    │
│  │       │                                                             │    │
│  │       │  ACTUAL EMAIL SENT via Gmail API                            │    │
│  │       │                                                             │    │
│  │       ▼                                                             │    │
│  │  Code Node (Python): Format voice response                          │    │
│  │       │                                                             │    │
│  │       │  result = items[0].json  # Gmail response                   │    │
│  │       │  return [{                                                  │    │
│  │       │    "success": True,                                         │    │
│  │       │    "message_id": result.get("id"),                          │    │
│  │       │    "thread_id": result.get("threadId"),                     │    │
│  │       │    "voice_response": f"Email sent successfully to "         │    │
│  │       │                    + f"{params['to']}."                     │    │
│  │       │  }]                                                         │    │
│  │       ▼                                                             │    │
│  │  Return to parent workflow                                          │    │
│  │                                                                     │    │
│  ───────────────────────────────────────────────────────────────────────    │
│       │                                                                      │
│       │  Sub-workflow result: {                                              │
│       │    success: true,                                                    │
│       │    message_id: "msg_xyz789",                                         │
│       │    voice_response: "Email sent successfully to john.smith@gmail.com" │
│       │  }                                                                   │
│       ▼                                                                      │
│  PostgreSQL: UPDATE status = 'COMPLETED'                                     │
│       │                                                                      │
│       │  UPDATE tool_calls SET                                               │
│       │    status = 'COMPLETED',                                             │
│       │    completed_at = NOW(),                                             │
│       │    execution_time_ms = EXTRACT(EPOCH FROM (NOW() - executed_at))     │
│       │                        * 1000,                                       │
│       │    result = '{"success":true,"message_id":"msg_xyz789",...}',        │
│       │    voice_response = 'Email sent successfully to john.smith@gmail.com'│
│       │    status_history = status_history || '[{                            │
│       │      "status": "COMPLETED",                                          │
│       │      "timestamp": "2026-01-12T15:30:07Z"                             │
│       │    }]'::jsonb                                                        │
│       │  WHERE tool_call_id = 'tc_a1b2c3d4e5f6';                             │
│       ▼                                                                      │
│  Return Result to MCP Server Trigger                                         │
│       │                                                                      │
│       │  {                                                                   │
│       │    "tool_call_id": "tc_a1b2c3d4e5f6",                                │
│       │    "status": "COMPLETED",                                            │
│       │    "result": {                                                       │
│       │      "success": true,                                                │
│       │      "message_id": "msg_xyz789",                                     │
│       │      "thread_id": "thread_abc"                                       │
│       │    },                                                                │
│       │    "voice_response": "Email sent successfully to john.smith@gmail.com",│
│       │    "execution_time_ms": 1850                                         │
│       │  }                                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Time: T+6900ms** (Total: confirmation → completion)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ RELAY SERVER                                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MCP Response: execution completed                                           │
│       │                                                                      │
│       │  Remove from pending:                                                │
│       │  delete pending_tool_calls["tc_a1b2c3d4e5f6"]                        │
│       ▼                                                                      │
│  OpenAI Realtime API: function_call_output                                   │
│       │                                                                      │
│       │  {                                                                   │
│       │    status: "completed",                                              │
│       │    result: { success: true, message_id: "msg_xyz789" },              │
│       │    voice_response: "Email sent successfully to john.smith@gmail.com" │
│       │  }                                                                   │
│       ▼                                                                      │
│  TTS Output: "Email sent successfully to john.smith@gmail.com."              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**FINAL DATABASE STATE:**
```sql
SELECT * FROM tool_calls WHERE tool_call_id = 'tc_a1b2c3d4e5f6';

┌─────────────────┬───────────────────────────────┬─────────────────────────────────┬───────────┐
│ tool_call_id    │ parameters                    │ status_history                  │ status    │
├─────────────────┼───────────────────────────────┼─────────────────────────────────┼───────────┤
│ tc_a1b2c3d4e5f6 │ {"to":"john.smith@gmail.com", │ [                               │ COMPLETED │
│                 │  "subject":"Meeting Tomorrow",│   {"status":"PENDING",...},     │           │
│                 │  "body":"Let's discuss..."}   │   {"status":"MODIFIED",...},    │           │
│                 │                               │   {"status":"EXECUTING",...},   │           │
│                 │                               │   {"status":"COMPLETED",...}    │           │
│                 │                               │ ]                               │           │
├─────────────────┼───────────────────────────────┼─────────────────────────────────┼───────────┤
│ parameters_     │ [{"field":"to",               │ execution_time_ms: 1850         │           │
│ history         │   "old":"john@gmail.com",     │ voice_response: "Email sent..." │           │
│                 │   "new":"john.smith@..."}]    │ result: {success:true,...}      │           │
└─────────────────┴───────────────────────────────┴─────────────────────────────────┴───────────┘
```

---

### TIMING SUMMARY: Option C (Hybrid MCP)

| Step | Operation | Latency | Cumulative |
|------|-----------|---------|------------|
| 1a | User speaks → STT | ~300ms | T+300ms |
| 1b | OpenAI → function_call | ~200ms | T+500ms |
| 1c | MCP tool call (SSE) | ~20ms | T+520ms |
| 1d | request_tool workflow | ~60ms | T+580ms |
| 1e | Response → TTS | ~300ms | T+880ms |
| **Step 1 Total** | **Initial request** | **~880ms** | |
| | | | |
| 2a | User correction → STT | ~300ms | +300ms |
| 2b | OpenAI → modify intent | ~200ms | +500ms |
| 2c | MCP tool call (SSE) | ~20ms | +520ms |
| 2d | modify_tool workflow | ~50ms | +570ms |
| 2e | Response → TTS | ~300ms | +870ms |
| **Step 2 Total** | **Modification** | **~870ms** | |
| | | | |
| 3a | User confirm → STT | ~300ms | +300ms |
| 3b | OpenAI → confirm intent | ~100ms | +400ms |
| 3c | MCP tool call (SSE) | ~20ms | +420ms |
| 3d | confirm_tool + Gmail | ~1800ms | +2220ms |
| 3e | Response → TTS | ~300ms | +2520ms |
| **Step 3 Total** | **Execution** | **~2520ms** | |

**Total conversation time: ~4.3 seconds** (from first request to completion announcement)

---

### COMPARISON: Option B (Webhook) vs Option C (MCP) for Same Scenario

| Metric | Option B (Webhook) | Option C (MCP) | Difference |
|--------|-------------------|----------------|------------|
| **Step 1 (request)** | ~980ms | ~880ms | **-100ms** |
| **Step 2 (modify)** | ~970ms | ~870ms | **-100ms** |
| **Step 3 (confirm)** | ~2620ms | ~2520ms | **-100ms** |
| **Total** | ~4.6s | ~4.3s | **-300ms** |

**Why MCP is faster:**
- No TLS handshake per request (~100ms saved each call)
- SSE persistent connection reused
- 3 MCP calls × 100ms = 300ms saved total

---

### OBSERVABILITY: What's Logged Where

| Location | What's Captured | Purpose |
|----------|-----------------|---------|
| **n8n: MCP Trigger** | Trigger execution, tool routing | Entry point metrics |
| **n8n: request_tool** | PENDING creation, initial params | Request logging |
| **n8n: modify_tool** | Parameter changes, history | Modification audit |
| **n8n: confirm_tool** | Execution routing | Confirmation tracking |
| **n8n: send_email** | Gmail API call, response | **Independent tool metrics** |
| **PostgreSQL: tool_calls** | Full state machine, history | Complete audit trail |
| **Relay Server** | MCP timing, pending cache | Client-side observability |

---

### AGENT CONTEXT QUERY (Anytime)

The agent can query context to reference previous tool calls:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ MCP Tool Call: get_context                                                   │
│ Input: { session_id: "sess_abc123" }                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  N8N: GET_CONTEXT SUB-WORKFLOW                                               │
│       │                                                                      │
│       ▼                                                                      │
│  PostgreSQL: Query pending + recent                                          │
│       │                                                                      │
│       │  -- Pending tool calls                                               │
│       │  SELECT tool_call_id, function_name, parameters, created_at          │
│       │  FROM tool_calls                                                     │
│       │  WHERE session_id = 'sess_abc123' AND status = 'PENDING';            │
│       │                                                                      │
│       │  -- Recent completed/failed                                          │
│       │  SELECT function_name, parameters, result, status,                   │
│       │         voice_response, created_at                                   │
│       │  FROM tool_calls                                                     │
│       │  WHERE session_id = 'sess_abc123'                                    │
│       │    AND status IN ('COMPLETED', 'FAILED')                             │
│       │  ORDER BY created_at DESC LIMIT 10;                                  │
│       ▼                                                                      │
│  Return:                                                                     │
│  {                                                                           │
│    "pending": [],                                                            │
│    "recent": [                                                               │
│      {                                                                       │
│        "function_name": "send_email",                                        │
│        "parameters": {"to":"john.smith@gmail.com",...},                      │
│        "result": {"success":true,"message_id":"msg_xyz789"},                 │
│        "status": "COMPLETED",                                                │
│        "voice_response": "Email sent successfully...",                       │
│        "created_at": "2026-01-12T15:30:00Z"                                  │
│      }                                                                       │
│    ]                                                                         │
│  }                                                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Agent can now say:**
> "I sent an email to john.smith@gmail.com about 'Meeting Tomorrow' a few minutes ago. Would you like me to send another one?"

---

## REVISED ARCHITECTURE: Pre-Confirmation + Gated Execution

### User Requirement Clarification

The user wants:
1. **AI confirms BEFORE any n8n call** - Agent asks user to confirm parameters FIRST
2. **User can modify before execution** - Handled entirely in relay/OpenAI
3. **Gated execution with checkpoints** - Workflow sends progress, can be cancelled mid-execution
4. **Completion notification** - Agent always announces successful completion

### Key Insight: Two Layers of Control

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: PRE-CALL CONFIRMATION (Relay Server - No n8n involved)             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "Send email to john@gmail.com"                                        │
│       ↓                                                                      │
│  OpenAI: Detects intent, extracts parameters                                 │
│       ↓                                                                      │
│  Relay: Stores params locally, does NOT call n8n yet                         │
│       ↓                                                                      │
│  Agent: "I'll send an email to john@gmail.com. Is that correct?"             │
│       ↓                                                                      │
│  User: "No, use john.smith@gmail.com"                                        │
│       ↓                                                                      │
│  Relay: Updates local params (still no n8n call)                             │
│       ↓                                                                      │
│  Agent: "Updated to john.smith@gmail.com. Confirm to send?"                  │
│       ↓                                                                      │
│  User: "Yes, send it"                                                        │
│       ↓                                                                      │
│  ══════════════════ NOW ENTERS LAYER 2 ══════════════════                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: GATED EXECUTION (n8n with checkpoints + callbacks)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Relay: Calls n8n /execute-tool with confirmed parameters                    │
│       ↓                                                                      │
│  n8n: Creates record (EXECUTING), starts workflow                            │
│       ↓                                                                      │
│  n8n: GATE 1 - Callback to relay: "Starting email send..."                   │
│       ↓                                                                      │
│  Agent: "Sending email now..."                                               │
│       ↓                                                                      │
│  [User can say "Stop!" here]                                                 │
│       ↓                                                                      │
│  n8n: GATE 2 - Check for cancellation signal                                 │
│       ↓                                                                      │
│  [If cancelled] → Abort, callback: "Cancelled"                               │
│  [If continue]  → Execute Gmail API call                                     │
│       ↓                                                                      │
│  n8n: GATE 3 - Callback: "Email sent successfully!"                          │
│       ↓                                                                      │
│  Agent: "Email sent to john.smith@gmail.com successfully!"                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Revised Flow: "Updating Email" Scenario

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: INTENT DETECTION + PRE-CONFIRMATION (No n8n)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  T+0ms: User speaks                                                          │
│  "Send an email to john@gmail.com about the meeting tomorrow"                │
│       ↓                                                                      │
│  T+300ms: OpenAI Realtime STT → text                                         │
│       ↓                                                                      │
│  T+500ms: OpenAI detects tool intent                                         │
│       │                                                                      │
│       │  Function: send_email                                                │
│       │  Arguments: {                                                        │
│       │    "to": "john@gmail.com",                                           │
│       │    "subject": "Meeting Tomorrow",                                    │
│       │    "body": "Let's discuss..."                                        │
│       │  }                                                                   │
│       │  requires_confirmation: true  ← KEY FLAG                             │
│       ▼                                                                      │
│  T+510ms: Relay stores pending intent locally                                │
│       │                                                                      │
│       │  pendingIntents["intent_123"] = {                                    │
│       │    function: "send_email",                                           │
│       │    params: {...},                                                    │
│       │    confirmed: false                                                  │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+520ms: Relay returns to OpenAI (NOT a tool result)                        │
│       │                                                                      │
│       │  {                                                                   │
│       │    type: "confirmation_required",                                    │
│       │    intent_id: "intent_123",                                          │
│       │    summary: "Send email to john@gmail.com about 'Meeting Tomorrow'"  │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+800ms: Agent speaks (TTS)                                                 │
│       │                                                                      │
│       │  "I'll send an email to john@gmail.com about the meeting             │
│       │   tomorrow. Is that correct?"                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: USER CORRECTION (Still no n8n)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  T+3000ms: User speaks correction                                            │
│  "Wait, that should be john.smith@gmail.com"                                 │
│       ↓                                                                      │
│  T+3300ms: OpenAI Realtime STT → text                                        │
│       ↓                                                                      │
│  T+3500ms: OpenAI detects modification intent                                │
│       │                                                                      │
│       │  Function: modify_pending_intent                                     │
│       │  Arguments: {                                                        │
│       │    "intent_id": "intent_123",                                        │
│       │    "field": "to",                                                    │
│       │    "new_value": "john.smith@gmail.com"                               │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+3510ms: Relay updates local pending intent                                │
│       │                                                                      │
│       │  pendingIntents["intent_123"].params.to = "john.smith@gmail.com"     │
│       │  pendingIntents["intent_123"].modifications.push({                   │
│       │    field: "to",                                                      │
│       │    old: "john@gmail.com",                                            │
│       │    new: "john.smith@gmail.com",                                      │
│       │    timestamp: Date.now()                                             │
│       │  })                                                                  │
│       ▼                                                                      │
│  T+3520ms: Relay returns to OpenAI                                           │
│       │                                                                      │
│       │  {                                                                   │
│       │    type: "intent_modified",                                          │
│       │    intent_id: "intent_123",                                          │
│       │    updated_summary: "Send email to john.smith@gmail.com..."          │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+3800ms: Agent speaks                                                      │
│       │                                                                      │
│       │  "Updated to john.smith@gmail.com. Confirm to send?"                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: USER CONFIRMS → EXECUTION BEGINS (n8n enters)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  T+5000ms: User confirms                                                     │
│  "Yes, send it"                                                              │
│       ↓                                                                      │
│  T+5300ms: OpenAI Realtime STT → text                                        │
│       ↓                                                                      │
│  T+5500ms: OpenAI detects confirmation                                       │
│       │                                                                      │
│       │  Function: confirm_intent                                            │
│       │  Arguments: { "intent_id": "intent_123" }                            │
│       ▼                                                                      │
│  T+5510ms: Relay executes confirmed intent                                   │
│       │                                                                      │
│       │  // Mark as confirmed                                                │
│       │  pendingIntents["intent_123"].confirmed = true                       │
│       │                                                                      │
│       │  // NOW call n8n                                                     │
│       │  MCP Tool Call: execute_tool                                         │
│       │  Payload: {                                                          │
│       │    "session_id": "sess_abc123",                                      │
│       │    "function_name": "send_email",                                    │
│       │    "parameters": {                                                   │
│       │      "to": "john.smith@gmail.com",                                   │
│       │      "subject": "Meeting Tomorrow",                                  │
│       │      "body": "Let's discuss..."                                      │
│       │    },                                                                │
│       │    "callback_url": "https://relay.railway.app/tool-progress",        │
│       │    "intent_id": "intent_123"                                         │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+5530ms: n8n receives execution request                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: GATED EXECUTION IN N8N (With progress callbacks)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  N8N: EXECUTE_TOOL SUB-WORKFLOW                                              │
│                                                                              │
│  T+5530ms: Execute Workflow Trigger receives request                         │
│       ↓                                                                      │
│  T+5540ms: Code Node - Generate tool_call_id, create DB record               │
│       │                                                                      │
│       │  INSERT INTO tool_calls (                                            │
│       │    tool_call_id, session_id, function_name,                          │
│       │    parameters, status, intent_id                                     │
│       │  ) VALUES (                                                          │
│       │    'tc_xyz789', 'sess_abc123', 'send_email',                         │
│       │    {...}, 'EXECUTING', 'intent_123'                                  │
│       │  );                                                                  │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 1: Progress Callback - "Starting"                              │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │  T+5550ms: HTTP Request Node → Callback to relay                    │    │
│  │       │                                                             │    │
│  │       │  POST https://relay.railway.app/tool-progress               │    │
│  │       │  {                                                          │    │
│  │       │    "tool_call_id": "tc_xyz789",                             │    │
│  │       │    "intent_id": "intent_123",                               │    │
│  │       │    "status": "EXECUTING",                                   │    │
│  │       │    "progress": "Starting email send...",                    │    │
│  │       │    "gate": 1,                                               │    │
│  │       │    "cancellable": true                                      │    │
│  │       │  }                                                          │    │
│  │       ▼                                                             │    │
│  │  T+5600ms: Relay receives callback                                  │    │
│  │       │                                                             │    │
│  │       │  // Update OpenAI conversation                              │    │
│  │       │  // Agent can now say "Sending email now..."                │    │
│  │       ▼                                                             │    │
│  │  T+5650ms: Check for cancellation signal                            │    │
│  │       │                                                             │    │
│  │       │  // Relay checks: has user said "stop"?                     │    │
│  │       │  // If yes, respond with {cancel: true}                     │    │
│  │       │  // If no, respond with {continue: true}                    │    │
│  │       ▼                                                             │    │
│  │  T+5660ms: n8n receives response                                    │    │
│  │       │                                                             │    │
│  │       │  IF response.cancel === true:                               │    │
│  │       │    → Jump to CANCELLATION branch                            │    │
│  │       │  ELSE:                                                      │    │
│  │       │    → Continue to next gate                                  │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 2: Execute Tool (Gmail API call)                               │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │  T+5700ms: Set Node - Route to correct tool workflow                │    │
│  │       ↓                                                             │    │
│  │  T+5710ms: Execute Workflow - Voice Tool: send_email                │    │
│  │       │                                                             │    │
│  │       │  ┌─────────────────────────────────────────────────────┐   │    │
│  │       │  │ SUB-WORKFLOW: send_email                            │   │    │
│  │       │  │                                                     │   │    │
│  │       │  │ Gmail Node (typeVersion 2.2)                        │   │    │
│  │       │  │   operation: "send"                                 │   │    │
│  │       │  │   sendTo: "john.smith@gmail.com"                    │   │    │
│  │       │  │   subject: "Meeting Tomorrow"                       │   │    │
│  │       │  │   message: "Let's discuss..."                       │   │    │
│  │       │  │                                                     │   │    │
│  │       │  │ *** GMAIL API CALL EXECUTES ***                     │   │    │
│  │       │  │                                                     │   │    │
│  │       │  │ Returns: { id: "msg_xyz", threadId: "thread_abc" }  │   │    │
│  │       │  └─────────────────────────────────────────────────────┘   │    │
│  │       ↓                                                             │    │
│  │  T+7500ms: Gmail response received (~1.8s for API call)             │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 3: Completion Callback                                         │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │  T+7510ms: Code Node - Format result + voice response               │    │
│  │       │                                                             │    │
│  │       │  result = {                                                 │    │
│  │       │    success: True,                                           │    │
│  │       │    message_id: "msg_xyz",                                   │    │
│  │       │    voice_response: "Email sent to john.smith@gmail.com      │    │
│  │       │                     successfully!"                          │    │
│  │       │  }                                                          │    │
│  │       ▼                                                             │    │
│  │  T+7520ms: PostgreSQL - Update status to COMPLETED                  │    │
│  │       │                                                             │    │
│  │       │  UPDATE tool_calls SET                                      │    │
│  │       │    status = 'COMPLETED',                                    │    │
│  │       │    completed_at = NOW(),                                    │    │
│  │       │    execution_time_ms = 1970,                                │    │
│  │       │    result = {...},                                          │    │
│  │       │    voice_response = 'Email sent...'                         │    │
│  │       │  WHERE tool_call_id = 'tc_xyz789';                          │    │
│  │       ▼                                                             │    │
│  │  T+7530ms: HTTP Request - Final callback to relay                   │    │
│  │       │                                                             │    │
│  │       │  POST https://relay.railway.app/tool-progress               │    │
│  │       │  {                                                          │    │
│  │       │    "tool_call_id": "tc_xyz789",                             │    │
│  │       │    "intent_id": "intent_123",                               │    │
│  │       │    "status": "COMPLETED",                                   │    │
│  │       │    "result": {...},                                         │    │
│  │       │    "voice_response": "Email sent to john.smith@gmail.com    │    │
│  │       │                       successfully!",                       │    │
│  │       │    "execution_time_ms": 1970                                │    │
│  │       │  }                                                          │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  T+7540ms: Return to MCP (workflow complete)                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: COMPLETION ANNOUNCEMENT                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  T+7550ms: Relay receives completion callback                                │
│       │                                                                      │
│       │  // Clean up pending intent                                          │
│       │  delete pendingIntents["intent_123"]                                 │
│       │                                                                      │
│       │  // Notify OpenAI of completion                                      │
│       │  function_call_output: {                                             │
│       │    status: "completed",                                              │
│       │    result: {...},                                                    │
│       │    voice_response: "Email sent to john.smith@gmail.com..."           │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+7850ms: Agent speaks (TTS)                                                │
│       │                                                                      │
│       │  "Email sent to john.smith@gmail.com successfully!"                  │
│                                                                              │
│  TOTAL TIME: ~7.85 seconds (including user confirmation delays)              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### CANCELLATION FLOW (User says "Stop!" during execution)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CANCELLATION SCENARIO                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  During GATE 1 callback wait:                                                │
│                                                                              │
│  T+5600ms: Relay receives progress callback from n8n                         │
│       │    { status: "EXECUTING", gate: 1, cancellable: true }               │
│       │                                                                      │
│  T+5610ms: Agent says "Sending email now..."                                 │
│       │                                                                      │
│  T+5700ms: User interrupts: "Stop! Don't send that!"                         │
│       │                                                                      │
│       │  Relay sets: cancelRequests["intent_123"] = true                     │
│       │                                                                      │
│  T+5750ms: n8n polling for cancellation signal                               │
│       │                                                                      │
│       │  Response to n8n: { cancel: true, reason: "User requested" }         │
│       ▼                                                                      │
│  T+5760ms: n8n receives cancel signal                                        │
│       │                                                                      │
│       │  IF Node: cancel === true?                                           │
│       │    → YES: Jump to cancellation branch                                │
│       ▼                                                                      │
│  T+5770ms: PostgreSQL - Update status to CANCELLED                           │
│       │                                                                      │
│       │  UPDATE tool_calls SET                                               │
│       │    status = 'CANCELLED',                                             │
│       │    completed_at = NOW(),                                             │
│       │    error_message = 'User cancelled'                                  │
│       │  WHERE tool_call_id = 'tc_xyz789';                                   │
│       ▼                                                                      │
│  T+5780ms: HTTP Request - Cancellation callback to relay                     │
│       │                                                                      │
│       │  POST https://relay.railway.app/tool-progress                        │
│       │  {                                                                   │
│       │    "tool_call_id": "tc_xyz789",                                      │
│       │    "status": "CANCELLED",                                            │
│       │    "voice_response": "Email cancelled. The email was not sent."      │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+5900ms: Relay receives cancellation confirmation                          │
│       │                                                                      │
│       │  // Clean up                                                         │
│       │  delete pendingIntents["intent_123"]                                 │
│       │  delete cancelRequests["intent_123"]                                 │
│       ▼                                                                      │
│  T+6200ms: Agent speaks                                                      │
│       │                                                                      │
│       │  "Cancelled. The email was not sent."                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Revised Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    REVISED ENTERPRISE VOICE AGENT SYSTEM                          │
│              Pre-Confirmation (Relay) + Gated Execution (n8n)                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │ RELAY SERVER (Railway) - Handles pre-confirmation                        │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                          │    │
│  │  OpenAI Realtime API ←→ Voice conversation                               │    │
│  │       │                                                                  │    │
│  │       ├── Intent Detection → pendingIntents map (local)                  │    │
│  │       ├── Modification → Update pendingIntents (no n8n)                  │    │
│  │       ├── Confirmation → MCP call to n8n                                 │    │
│  │       ├── Progress callbacks ← n8n gated execution                       │    │
│  │       ├── Cancel requests → cancelRequests map                           │    │
│  │       └── Completion → Announce to user                                  │    │
│  │                                                                          │    │
│  │  Callback Endpoint: POST /tool-progress                                  │    │
│  │       │                                                                  │    │
│  │       ├── Receives: { status, progress, gate, cancellable }              │    │
│  │       ├── Checks: cancelRequests[intent_id]                              │    │
│  │       └── Returns: { continue: true } or { cancel: true }                │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│       │                                                                           │
│       │  MCP Tool Call: execute_tool (only after user confirms)                   │
│       ▼                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │ N8N: MCP SERVER TRIGGER + GATED EXECUTOR                                 │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                          │    │
│  │  MCP Server Trigger (path: /voice-agent)                                 │    │
│  │       │                                                                  │    │
│  │       └──→ Tool: execute_tool                                            │    │
│  │             │                                                            │    │
│  │             ▼                                                            │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │    │
│  │  │ EXECUTE_TOOL SUB-WORKFLOW (Gated)                                │   │    │
│  │  ├──────────────────────────────────────────────────────────────────┤   │    │
│  │  │                                                                  │   │    │
│  │  │  1. Execute Workflow Trigger                                     │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  2. Code: Generate tool_call_id, INSERT EXECUTING                │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │   │    │
│  │  │  │ GATE 1: HTTP callback → relay (cancellable: true)         │ │   │    │
│  │  │  │         Wait for response: continue or cancel             │ │   │    │
│  │  │  └────────────────────────────────────────────────────────────┘ │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  3. IF: cancelled? → CANCEL branch                               │   │    │
│  │  │       ↓ (continue)                                               │   │    │
│  │  │  4. Set: Route to tool workflow                                  │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  5. Execute Workflow: Voice Tool: {function_name}                │   │    │
│  │  │       │                                                          │   │    │
│  │  │       ├──→ Voice Tool: send_email (Gmail)                        │   │    │
│  │  │       ├──→ Voice Tool: schedule_meeting                          │   │    │
│  │  │       ├──→ Voice Tool: search_contacts                           │   │    │
│  │  │       └──→ ... (8 total)                                         │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  6. Code: Format result + voice_response                         │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  7. PostgreSQL: UPDATE COMPLETED                                 │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │   │    │
│  │  │  │ GATE 3: HTTP callback → relay (status: COMPLETED)         │ │   │    │
│  │  │  │         Final result + voice_response                     │ │   │    │
│  │  │  └────────────────────────────────────────────────────────────┘ │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  8. Return result to MCP                                         │   │    │
│  │  │                                                                  │   │    │
│  │  │  ─────────────────────────────────────────────────────────────   │   │    │
│  │  │                                                                  │   │    │
│  │  │  CANCEL BRANCH:                                                  │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  PostgreSQL: UPDATE CANCELLED                                    │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  HTTP callback → relay (status: CANCELLED)                       │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  Return cancellation to MCP                                      │   │    │
│  │  │                                                                  │   │    │
│  │  └──────────────────────────────────────────────────────────────────┘   │    │
│  │                                                                          │    │
│  │  Tool: get_context (query tool history)                                  │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  Sub-Workflows (8 total - Independent execution history):                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  Voice Tool: send_email        │  Voice Tool: schedule_meeting           │    │
│  │  Voice Tool: search_contacts   │  Voice Tool: get_calendar_availability  │    │
│  │  Voice Tool: create_task       │  Voice Tool: search_documentation       │    │
│  │  Voice Tool: get_training_progress │ Voice Tool: knowledge_check         │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

### Key Differences from Previous Design

| Aspect | Previous Design | Revised Design |
|--------|-----------------|----------------|
| **Pre-confirmation** | n8n creates PENDING record | Relay handles locally, no n8n |
| **Modification** | MCP call to modify_tool | Relay updates local state |
| **When n8n is called** | On first tool request | Only after user confirms |
| **Execution state** | PENDING → CONFIRM → EXECUTE | Direct EXECUTE (already confirmed) |
| **Progress updates** | None | Gated callbacks at checkpoints |
| **Cancellation** | Update DB record | HTTP callback with cancel signal |
| **MCP tools needed** | request, modify, confirm, cancel, context | execute, context |

---

### MCP Tools (Simplified)

| Tool | Purpose |
|------|---------|
| **execute_tool** | Execute confirmed tool, includes callback_url for progress |
| **get_context** | Query tool history for agent reference |

The **5 state management tools become 2** because:
- `request_tool` → Relay handles locally
- `modify_tool` → Relay handles locally
- `confirm_tool` → Merged into `execute_tool`
- `cancel_tool` → HTTP callback response `{cancel: true}`
- `get_context` → Stays the same

---

### Relay Server Requirements

The relay server needs to implement:

```typescript
// Local state management
interface PendingIntent {
  function_name: string;
  parameters: Record<string, any>;
  confirmed: boolean;
  modifications: Array<{
    field: string;
    old: any;
    new: any;
    timestamp: number;
  }>;
}

const pendingIntents: Map<string, PendingIntent> = new Map();
const cancelRequests: Set<string> = new Set();

// Callback endpoint for n8n progress updates
app.post('/tool-progress', (req, res) => {
  const { intent_id, status, progress, gate, cancellable } = req.body;

  // Check if user requested cancellation
  if (cancellable && cancelRequests.has(intent_id)) {
    cancelRequests.delete(intent_id);
    return res.json({ cancel: true, reason: 'User requested' });
  }

  // Forward progress to OpenAI conversation
  notifyProgress(intent_id, { status, progress });

  // Continue execution
  return res.json({ continue: true });
});
```

---

### Success Criteria (Updated)

**Pre-Confirmation (Relay):**
- [ ] Agent asks for confirmation BEFORE any n8n call
- [ ] User can modify parameters without n8n involvement
- [ ] Local state tracks pending intents and modifications

**Gated Execution (n8n):**
- [ ] Gate 1 callback sends progress, checks for cancellation
- [ ] User can say "stop" and execution halts
- [ ] Gate 3 callback sends completion with voice_response
- [ ] Each tool sub-workflow has independent execution history

**Completion:**
- [ ] Agent always announces successful completion
- [ ] Agent announces cancellation if stopped
- [ ] Full audit trail in PostgreSQL

---

## FINAL ARCHITECTURE: Async Execution + Database as Source of Truth

### User Requirement Clarification (Final)

1. **Async tool calls** - n8n returns immediately, execution runs in background
2. **Database is single source of truth** - All state in PostgreSQL, not relay memory
3. **Agent queries database for context** - Via `get_context` MCP tool
4. **Pre-confirmation flow** - Agent confirms before execution starts
5. **Cancellation during execution** - Update database, workflow checks

---

### Database-Centric State Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATABASE AS SOURCE OF TRUTH                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PostgreSQL: tool_calls table                                                │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ All state transitions happen HERE:                                  │    │
│  │                                                                     │    │
│  │  PENDING → MODIFIED → EXECUTING → COMPLETED                         │    │
│  │     ↓         ↓          ↓           │                              │    │
│  │  CANCELLED  CANCELLED  CANCELLED     ↓                              │    │
│  │                                    FAILED                           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Relay Server: STATELESS                                                     │
│  - Does NOT store pending intents locally                                    │
│  - All queries go through n8n MCP → PostgreSQL                               │
│  - Receives async completion callbacks from n8n                              │
│                                                                              │
│  Agent Context: Always from database                                         │
│  - get_context queries PostgreSQL                                            │
│  - Returns pending + recent tool calls                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Async Execution Pattern

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ASYNC TOOL EXECUTION                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Relay calls: execute_tool (MCP)                                          │
│       │                                                                      │
│       │  {                                                                   │
│       │    function_name: "send_email",                                      │
│       │    parameters: {...},                                                │
│       │    callback_url: "https://relay/tool-complete",                      │
│       │    async: true                                                       │
│       │  }                                                                   │
│       ▼                                                                      │
│  2. n8n: INSERT record (EXECUTING), RETURN IMMEDIATELY                       │
│       │                                                                      │
│       │  Returns: { tool_call_id: "tc_xyz", status: "EXECUTING" }            │
│       │                                                                      │
│       │  *** RELAY IS NOW UNBLOCKED ***                                      │
│       ▼                                                                      │
│  3. n8n: ASYNC - Triggers sub-workflow execution                             │
│       │                                                                      │
│       │  Execute Workflow (mode: "queue" or webhook-triggered)               │
│       │  Background execution of tool logic                                  │
│       ▼                                                                      │
│  4. n8n: Tool executes (Gmail send, etc.)                                    │
│       │                                                                      │
│       │  Meanwhile: Agent can query status via get_context                   │
│       │  Meanwhile: User can request cancellation                            │
│       ▼                                                                      │
│  5. n8n: UPDATE database (COMPLETED)                                         │
│       │                                                                      │
│       │  UPDATE tool_calls SET status='COMPLETED', result={...}              │
│       ▼                                                                      │
│  6. n8n: POST callback to relay                                              │
│       │                                                                      │
│       │  POST https://relay/tool-complete                                    │
│       │  { tool_call_id, status, result, voice_response }                    │
│       ▼                                                                      │
│  7. Relay: Notifies OpenAI → Agent speaks result                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Revised Flow: "Updating Email" with Async + DB Truth

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: User requests email (creates PENDING in database)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "Send an email to john@gmail.com about the meeting"                   │
│       ↓                                                                      │
│  OpenAI: Detects send_email intent                                           │
│       ↓                                                                      │
│  Relay: MCP call → n8n request_tool                                          │
│       │                                                                      │
│       │  {                                                                   │
│       │    session_id: "sess_123",                                           │
│       │    function_name: "send_email",                                      │
│       │    parameters: { to: "john@gmail.com", subject: "Meeting" }          │
│       │  }                                                                   │
│       ▼                                                                      │
│  n8n: INSERT INTO tool_calls (status: PENDING)                               │
│       │                                                                      │
│       │  Returns: {                                                          │
│       │    tool_call_id: "tc_abc",                                           │
│       │    status: "PENDING",                                                │
│       │    confirmation_message: "I'll send email to john@gmail.com..."      │
│       │  }                                                                   │
│       ▼                                                                      │
│  Agent: "I'll send an email to john@gmail.com about the meeting.             │
│          Is that correct?"                                                   │
│                                                                              │
│  DATABASE STATE: { tc_abc: PENDING, params: {to: "john@gmail.com"} }         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: User corrects email (updates database)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "Wait, that should be john.smith@gmail.com"                           │
│       ↓                                                                      │
│  OpenAI: Detects modification intent                                         │
│       ↓                                                                      │
│  Relay: MCP call → n8n modify_tool                                           │
│       │                                                                      │
│       │  {                                                                   │
│       │    tool_call_id: "tc_abc",                                           │
│       │    parameters: { to: "john.smith@gmail.com" }                        │
│       │  }                                                                   │
│       ▼                                                                      │
│  n8n: UPDATE tool_calls SET parameters = merged, history = appended          │
│       │                                                                      │
│       │  Returns: {                                                          │
│       │    status: "PENDING",                                                │
│       │    updated_parameters: { to: "john.smith@gmail.com", ... }           │
│       │  }                                                                   │
│       ▼                                                                      │
│  Agent: "Updated to john.smith@gmail.com. Confirm to send?"                  │
│                                                                              │
│  DATABASE STATE: { tc_abc: PENDING, params: {to: "john.smith@gmail.com"},    │
│                    parameters_history: [{old: "john@...", new: "john.smith@"}] }
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: User confirms → ASYNC execution begins                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "Yes, send it"                                                        │
│       ↓                                                                      │
│  OpenAI: Detects confirmation                                                │
│       ↓                                                                      │
│  Relay: MCP call → n8n confirm_tool                                          │
│       │                                                                      │
│       │  {                                                                   │
│       │    tool_call_id: "tc_abc",                                           │
│       │    callback_url: "https://relay.railway.app/tool-complete"           │
│       │  }                                                                   │
│       ▼                                                                      │
│  n8n: UPDATE status = 'EXECUTING', RETURN IMMEDIATELY                        │
│       │                                                                      │
│       │  Returns: {                                                          │
│       │    tool_call_id: "tc_abc",                                           │
│       │    status: "EXECUTING",                                              │
│       │    message: "Sending email now..."                                   │
│       │  }                                                                   │
│       │                                                                      │
│       │  *** ASYNC: Triggers background workflow ***                         │
│       ▼                                                                      │
│  Agent: "Sending email now..."                                               │
│                                                                              │
│  DATABASE STATE: { tc_abc: EXECUTING }                                       │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│  RELAY IS NOW FREE - Can handle other requests while email sends             │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Background execution + Completion callback                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  n8n (ASYNC - Background):                                                   │
│       │                                                                      │
│       │  1. Fetch tool_call from DB (tc_abc)                                 │
│       │  2. Check if status still EXECUTING (not cancelled)                  │
│       │  3. Execute sub-workflow: Voice Tool: send_email                     │
│       │       │                                                              │
│       │       │  Gmail Node: Send email                                      │
│       │       │  Returns: { id: "msg_xyz", threadId: "..." }                 │
│       │       ↓                                                              │
│       │  4. UPDATE tool_calls SET status='COMPLETED',                        │
│       │     result={...}, voice_response="Email sent successfully"           │
│       │  5. POST callback to relay                                           │
│       ▼                                                                      │
│  Relay: Receives callback                                                    │
│       │                                                                      │
│       │  POST /tool-complete                                                 │
│       │  {                                                                   │
│       │    tool_call_id: "tc_abc",                                           │
│       │    status: "COMPLETED",                                              │
│       │    result: { message_id: "msg_xyz" },                                │
│       │    voice_response: "Email sent to john.smith@gmail.com successfully" │
│       │  }                                                                   │
│       ▼                                                                      │
│  Agent: "Email sent to john.smith@gmail.com successfully!"                   │
│                                                                              │
│  DATABASE STATE: { tc_abc: COMPLETED, result: {...} }                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Cancellation During Async Execution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CANCELLATION SCENARIO                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  After confirm_tool returns EXECUTING:                                       │
│                                                                              │
│  Agent: "Sending email now..."                                               │
│       │                                                                      │
│  User: "Stop! Don't send that!"                                              │
│       ↓                                                                      │
│  OpenAI: Detects cancellation intent                                         │
│       ↓                                                                      │
│  Relay: MCP call → n8n cancel_tool                                           │
│       │                                                                      │
│       │  { tool_call_id: "tc_abc" }                                          │
│       ▼                                                                      │
│  n8n: UPDATE tool_calls SET status='CANCELLED' WHERE id='tc_abc'             │
│       │  AND status='EXECUTING'  -- Only if still executing                  │
│       │                                                                      │
│       │  Returns: { status: "CANCELLED" } or { error: "Already completed" }  │
│       ▼                                                                      │
│  Agent: "Cancelled. The email was not sent."                                 │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│  Background workflow checks DB before executing:                             │
│                                                                              │
│  n8n (Background):                                                           │
│       │                                                                      │
│       │  1. Check status: SELECT status FROM tool_calls WHERE id='tc_abc'    │
│       │  2. If status='CANCELLED' → Skip execution, exit workflow            │
│       │  3. If status='EXECUTING' → Proceed with tool                        │
│                                                                              │
│  This creates a race condition window, but database is truth:                │
│  - If cancel happens before tool executes → Tool skipped                     │
│  - If cancel happens after tool executes → Tool ran, marked cancelled anyway │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### n8n Workflow Structure (Async Pattern)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ MCP SERVER TRIGGER WORKFLOW                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  MCP Server Trigger (path: /voice-agent)                                     │
│       │                                                                      │
│       ├──→ Tool: request_tool                                                │
│       │         │                                                            │
│       │         ▼                                                            │
│       │    ┌─────────────────────────────────────────────────────────────┐  │
│       │    │ REQUEST_TOOL_WF (Synchronous - returns immediately)        │  │
│       │    │                                                             │  │
│       │    │ 1. Generate tool_call_id                                    │  │
│       │    │ 2. INSERT INTO tool_calls (PENDING)                         │  │
│       │    │ 3. Return { tool_call_id, status, confirmation_message }    │  │
│       │    └─────────────────────────────────────────────────────────────┘  │
│       │                                                                      │
│       ├──→ Tool: modify_tool                                                 │
│       │         │                                                            │
│       │         ▼                                                            │
│       │    ┌─────────────────────────────────────────────────────────────┐  │
│       │    │ MODIFY_TOOL_WF (Synchronous)                                │  │
│       │    │                                                             │  │
│       │    │ 1. SELECT tool_call WHERE id=:id AND status='PENDING'       │  │
│       │    │ 2. Merge parameters, append to history                      │  │
│       │    │ 3. UPDATE tool_calls                                        │  │
│       │    │ 4. Return { status, updated_parameters }                    │  │
│       │    └─────────────────────────────────────────────────────────────┘  │
│       │                                                                      │
│       ├──→ Tool: confirm_tool                                                │
│       │         │                                                            │
│       │         ▼                                                            │
│       │    ┌─────────────────────────────────────────────────────────────┐  │
│       │    │ CONFIRM_TOOL_WF (Returns immediately, triggers async)       │  │
│       │    │                                                             │  │
│       │    │ 1. SELECT tool_call WHERE id=:id AND status='PENDING'       │  │
│       │    │ 2. UPDATE status='EXECUTING', confirmed_at=NOW()            │  │
│       │    │ 3. HTTP Request: Trigger async executor (fire-and-forget)   │  │
│       │    │    POST /webhook/async-executor                             │  │
│       │    │    { tool_call_id, callback_url }                           │  │
│       │    │ 4. Return { tool_call_id, status: "EXECUTING" }             │  │
│       │    └─────────────────────────────────────────────────────────────┘  │
│       │                                                                      │
│       ├──→ Tool: cancel_tool                                                 │
│       │         │                                                            │
│       │         ▼                                                            │
│       │    ┌─────────────────────────────────────────────────────────────┐  │
│       │    │ CANCEL_TOOL_WF (Synchronous)                                │  │
│       │    │                                                             │  │
│       │    │ 1. UPDATE tool_calls SET status='CANCELLED'                 │  │
│       │    │    WHERE id=:id AND status IN ('PENDING', 'EXECUTING')      │  │
│       │    │ 2. Return { status: "CANCELLED" } or { error: "..." }       │  │
│       │    └─────────────────────────────────────────────────────────────┘  │
│       │                                                                      │
│       └──→ Tool: get_context                                                 │
│                 │                                                            │
│                 ▼                                                            │
│            ┌─────────────────────────────────────────────────────────────┐  │
│            │ GET_CONTEXT_WF (Synchronous - query database)               │  │
│            │                                                             │  │
│            │ 1. SELECT pending FROM tool_calls WHERE session=:s          │  │
│            │    AND status IN ('PENDING', 'EXECUTING')                   │  │
│            │ 2. SELECT recent FROM tool_calls WHERE session=:s           │  │
│            │    AND status IN ('COMPLETED', 'FAILED', 'CANCELLED')       │  │
│            │    LIMIT 10                                                 │  │
│            │ 3. Return { pending: [...], recent: [...] }                 │  │
│            └─────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ ASYNC EXECUTOR WORKFLOW (Separate, triggered by webhook)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Webhook: /async-executor (receives tool_call_id, callback_url)              │
│       │                                                                      │
│       ▼                                                                      │
│  PostgreSQL: SELECT * FROM tool_calls WHERE id=:tool_call_id                 │
│       │                                                                      │
│       ▼                                                                      │
│  IF: status == 'CANCELLED'?                                                  │
│       │                                                                      │
│       ├── YES → Exit (do nothing)                                            │
│       │                                                                      │
│       └── NO → Continue                                                      │
│             │                                                                │
│             ▼                                                                │
│  Set: Route to tool workflow based on function_name                          │
│       │                                                                      │
│       ▼                                                                      │
│  Execute Workflow: Voice Tool: {function_name}                               │
│       │                                                                      │
│       ├──→ Voice Tool: send_email (Gmail)                                    │
│       ├──→ Voice Tool: schedule_meeting                                      │
│       └──→ ... (8 total)                                                     │
│       │                                                                      │
│       ▼                                                                      │
│  Code: Format result + voice_response                                        │
│       │                                                                      │
│       ▼                                                                      │
│  PostgreSQL: UPDATE status='COMPLETED', result={...}, voice_response=...     │
│       │                                                                      │
│       ▼                                                                      │
│  HTTP Request: POST callback_url                                             │
│       │                                                                      │
│       │  {                                                                   │
│       │    tool_call_id: "tc_abc",                                           │
│       │    status: "COMPLETED",                                              │
│       │    result: {...},                                                    │
│       │    voice_response: "Email sent successfully..."                      │
│       │  }                                                                   │
│       ▼                                                                      │
│  End                                                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### MCP Tools (Final)

| Tool | Purpose | Returns |
|------|---------|---------|
| **request_tool** | Create PENDING tool call | { tool_call_id, status, confirmation_message } |
| **modify_tool** | Update parameters of PENDING call | { status, updated_parameters } |
| **confirm_tool** | Start ASYNC execution | { tool_call_id, status: "EXECUTING" } |
| **cancel_tool** | Cancel PENDING or EXECUTING call | { status: "CANCELLED" } |
| **get_context** | Query tool history from DB | { pending: [...], recent: [...] } |

---

### Relay Server (Session Cache + DB Truth)

**Cache Strategy:**
- **Database = Source of Truth** - All writes go to database
- **Session Cache = Read Optimization** - Cache pending tool calls per session
- **Cache Invalidation** - Update cache when database changes (via MCP response or callback)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CACHING PATTERN                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Database (PostgreSQL)          Session Cache (Relay Memory)                 │
│  ══════════════════════         ════════════════════════════                 │
│  Source of truth                Read-through cache                           │
│  All writes go here             Avoids repeated DB queries                   │
│  Survives relay restart         Cleared on session end                       │
│                                                                              │
│  Flow:                                                                       │
│                                                                              │
│  1. request_tool → n8n → INSERT DB → response → UPDATE CACHE                │
│  2. modify_tool  → n8n → UPDATE DB → response → UPDATE CACHE                │
│  3. confirm_tool → n8n → UPDATE DB → response → UPDATE CACHE                │
│  4. callback     → relay receives → UPDATE CACHE                            │
│  5. get_context  → CHECK CACHE FIRST → if stale → query DB                  │
│                                                                              │
│  Latency Savings:                                                            │
│  - Cache hit: ~1-5ms (local memory)                                          │
│  - Cache miss: ~50-100ms (MCP → n8n → PostgreSQL)                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```typescript
// Session cache for reduced latency
interface SessionCache {
  session_id: string;
  pending_tool_calls: Map<string, ToolCall>;  // tool_call_id → ToolCall
  recent_tool_calls: ToolCall[];              // Last 10 completed
  last_synced: number;                        // Timestamp for staleness check
}

const sessionCaches: Map<string, SessionCache> = new Map();

// Cache configuration
const CACHE_TTL_MS = 30000;  // 30 seconds before checking DB for updates
const MAX_RECENT_CACHED = 10;

// Update cache when MCP returns
function updateCacheFromMCPResponse(session_id: string, response: MCPResponse) {
  const cache = sessionCaches.get(session_id) || createEmptyCache(session_id);

  if (response.tool_call_id) {
    if (response.status === 'PENDING' || response.status === 'EXECUTING') {
      cache.pending_tool_calls.set(response.tool_call_id, response);
    } else {
      // Move from pending to recent
      cache.pending_tool_calls.delete(response.tool_call_id);
      cache.recent_tool_calls.unshift(response);
      cache.recent_tool_calls = cache.recent_tool_calls.slice(0, MAX_RECENT_CACHED);
    }
  }

  cache.last_synced = Date.now();
  sessionCaches.set(session_id, cache);
}

// Callback endpoint - updates cache + notifies agent
app.post('/tool-complete', async (req, res) => {
  const { tool_call_id, session_id, status, result, voice_response } = req.body;

  // Update cache
  const cache = sessionCaches.get(session_id);
  if (cache) {
    const toolCall = cache.pending_tool_calls.get(tool_call_id);
    if (toolCall) {
      toolCall.status = status;
      toolCall.result = result;
      toolCall.voice_response = voice_response;

      // Move from pending to recent
      cache.pending_tool_calls.delete(tool_call_id);
      cache.recent_tool_calls.unshift(toolCall);
      cache.recent_tool_calls = cache.recent_tool_calls.slice(0, MAX_RECENT_CACHED);
    }
  }

  // Notify OpenAI of completion
  await notifyCompletion(tool_call_id, { status, result, voice_response });

  res.json({ received: true });
});

// Fast context lookup - cache first, DB fallback
async function getSessionContext(session_id: string): Promise<Context> {
  const cache = sessionCaches.get(session_id);

  // If cache exists and fresh, return immediately
  if (cache && (Date.now() - cache.last_synced) < CACHE_TTL_MS) {
    return {
      pending: Array.from(cache.pending_tool_calls.values()),
      recent: cache.recent_tool_calls
    };
  }

  // Cache miss or stale - query database via MCP
  const dbContext = await mcpCall('get_context', { session_id });

  // Update cache with fresh data
  updateCacheFromDBResponse(session_id, dbContext);

  return dbContext;
}
```

**Latency Comparison:**

| Operation | Without Cache | With Cache |
|-----------|--------------|------------|
| Get pending tool calls | ~80ms (MCP → DB) | ~2ms (memory) |
| Check if tool_call_id exists | ~80ms | ~1ms |
| Get recent history | ~100ms | ~3ms |
| Agent context query | ~150ms | ~5ms |

**Cache Behavior:**
- **On MCP response** - Cache is UPDATED (not invalidated) with new data
- **On callback** - Cache is UPDATED with completion status
- **Session end** - Cache cleared when voice session disconnects

**Note:** TTL (Time To Live) means "how long data stays valid before expiring." We're NOT using TTL expiration here - cache persists for the entire session. The cache is only updated, never invalidated mid-session.

---

## CHECKPOINT PATTERN: Wait for Confirmation Before Execution

### Current Approach: Human-in-the-Loop Style

The workflow pauses RIGHT BEFORE executing the actual tool (Gmail send, etc.) and waits for the agent to confirm one final time.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CHECKPOINT FLOW: "Email is prepared, waiting for final confirmation"         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ASYNC EXECUTOR WORKFLOW (with checkpoint)                                   │
│                                                                              │
│  Webhook: /async-executor                                                    │
│       │                                                                      │
│       ▼                                                                      │
│  PostgreSQL: Fetch tool_call (tc_abc)                                        │
│       │                                                                      │
│       ▼                                                                      │
│  IF: status == 'CANCELLED'? → Exit                                           │
│       │                                                                      │
│       ▼ (status == 'EXECUTING')                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ CHECKPOINT: Preparation Complete - Request Final Confirmation       │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │  Code Node: Build preparation summary                               │    │
│  │       │                                                             │    │
│  │       │  {                                                          │    │
│  │       │    tool_call_id: "tc_abc",                                  │    │
│  │       │    function_name: "send_email",                             │    │
│  │       │    prepared_action: "Email to john.smith@gmail.com",        │    │
│  │       │    subject: "Meeting Tomorrow",                             │    │
│  │       │    status: "PREPARED",                                      │    │
│  │       │    message: "Email is ready to send. Confirm to proceed."   │    │
│  │       │  }                                                          │    │
│  │       ▼                                                             │    │
│  │  PostgreSQL: UPDATE status = 'PREPARED'                             │    │
│  │       │                                                             │    │
│  │       │  UPDATE tool_calls SET                                      │    │
│  │       │    status = 'PREPARED',                                     │    │
│  │       │    prepared_at = NOW()                                      │    │
│  │       │  WHERE tool_call_id = 'tc_abc';                             │    │
│  │       ▼                                                             │    │
│  │  HTTP Request: POST callback to relay (checkpoint notification)     │    │
│  │       │                                                             │    │
│  │       │  POST https://relay.railway.app/tool-checkpoint             │    │
│  │       │  {                                                          │    │
│  │       │    tool_call_id: "tc_abc",                                  │    │
│  │       │    status: "PREPARED",                                      │    │
│  │       │    checkpoint: "ready_to_execute",                          │    │
│  │       │    message: "Email to john.smith@gmail.com is ready.        │    │
│  │       │              Say 'send it' to proceed or 'cancel'.",        │    │
│  │       │    resume_webhook: "/webhook/resume-execution/tc_abc"       │    │
│  │       │  }                                                          │    │
│  │       ▼                                                             │    │
│  │  *** WORKFLOW ENDS HERE - Waits for resume webhook ***              │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│  Agent speaks: "Email to john.smith@gmail.com is ready. Send it?"            │
│  User: "Yes, send it"                                                        │
│  Relay: POST /webhook/resume-execution/tc_abc { action: "proceed" }          │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ RESUME EXECUTION WORKFLOW (triggered when user confirms)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Webhook: /resume-execution/:tool_call_id                                    │
│       │                                                                      │
│       │  Receives: { action: "proceed" } or { action: "cancel" }             │
│       ▼                                                                      │
│  PostgreSQL: Fetch tool_call, verify status = 'PREPARED'                     │
│       │                                                                      │
│       ▼                                                                      │
│  IF: action == 'cancel'?                                                     │
│       │                                                                      │
│       ├── YES → UPDATE status='CANCELLED', callback, exit                    │
│       │                                                                      │
│       └── NO (action == 'proceed')                                           │
│             │                                                                │
│             ▼                                                                │
│  PostgreSQL: UPDATE status = 'EXECUTING'                                     │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ ACTUAL TOOL EXECUTION                                               │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │  Execute Workflow: Voice Tool: send_email                           │    │
│  │       │                                                             │    │
│  │       │  Gmail Node: ACTUALLY SENDS THE EMAIL                       │    │
│  │       │  Returns: { id: "msg_xyz", threadId: "..." }                │    │
│  │       ▼                                                             │    │
│  │  Code: Format result + voice_response                               │    │
│  │       ▼                                                             │    │
│  │  PostgreSQL: UPDATE status='COMPLETED', result={...}                │    │
│  │       ▼                                                             │    │
│  │  HTTP Request: POST completion callback to relay                    │    │
│  │       │                                                             │    │
│  │       │  { tool_call_id, status: "COMPLETED", voice_response }      │    │
│  │       ▼                                                             │    │
│  │  End                                                                │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Updated State Machine (with PREPARED state)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TOOL CALL STATE MACHINE                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                    ┌──────────────┐                                          │
│                    │   PENDING    │ ← User requests tool                     │
│                    └──────┬───────┘                                          │
│                           │                                                  │
│              ┌────────────┼────────────┐                                     │
│              │            │            │                                     │
│              ▼            ▼            ▼                                     │
│        ┌──────────┐ ┌──────────┐ ┌──────────┐                               │
│        │ MODIFIED │ │EXECUTING │ │CANCELLED │                               │
│        └────┬─────┘ └────┬─────┘ └──────────┘                               │
│             │            │                                                   │
│             └──► PENDING │ (auto-return after modify)                       │
│                          │                                                   │
│                          ▼                                                   │
│                    ┌──────────┐                                              │
│                    │ PREPARED │ ← Checkpoint: ready to execute               │
│                    └────┬─────┘                                              │
│                         │                                                    │
│              ┌──────────┼──────────┐                                         │
│              │                     │                                         │
│              ▼                     ▼                                         │
│        ┌──────────┐          ┌──────────┐                                   │
│        │EXECUTING │          │CANCELLED │                                   │
│        │ (actual) │          └──────────┘                                   │
│        └────┬─────┘                                                          │
│             │                                                                │
│      ┌──────┴──────┐                                                         │
│      │             │                                                         │
│      ▼             ▼                                                         │
│ ┌──────────┐ ┌──────────┐                                                   │
│ │COMPLETED │ │  FAILED  │                                                   │
│ └──────────┘ └──────────┘                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

State Transitions:
- PENDING → MODIFIED (user corrects params) → PENDING
- PENDING → EXECUTING (user says "confirm")
- PENDING → CANCELLED (user says "cancel")
- EXECUTING → PREPARED (checkpoint reached, waiting for final confirm)
- PREPARED → EXECUTING (actual) (user says "send it")
- PREPARED → CANCELLED (user says "cancel" at checkpoint)
- EXECUTING (actual) → COMPLETED (tool succeeded)
- EXECUTING (actual) → FAILED (tool error)
```

---

### Checkpoint vs Initial Confirmation

| Stage | When | What Happens |
|-------|------|--------------|
| **Initial Confirmation** | After `request_tool` | Agent: "I'll send email to X. Is that correct?" |
| **User Confirms** | `confirm_tool` called | Status → EXECUTING, async workflow starts |
| **Checkpoint** | Before actual execution | Agent: "Email is ready to send. Send it?" |
| **Final Confirm** | `resume-execution` webhook | Status → EXECUTING (actual), tool runs |
| **Completion** | After tool finishes | Agent: "Email sent successfully!" |

---

### Full Flow with Checkpoint: "Updating Email"

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ COMPLETE FLOW WITH CHECKPOINT                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. User: "Send email to john@gmail.com"                                     │
│     → request_tool → INSERT PENDING                                          │
│     → Agent: "I'll send email to john@gmail.com. Is that correct?"           │
│                                                                              │
│  2. User: "Use john.smith@gmail.com instead"                                 │
│     → modify_tool → UPDATE parameters                                        │
│     → Agent: "Updated to john.smith@gmail.com. Confirm?"                     │
│                                                                              │
│  3. User: "Yes, confirm"                                                     │
│     → confirm_tool → UPDATE EXECUTING, trigger async workflow                │
│     → Agent: "Processing..."                                                 │
│                                                                              │
│  4. Async workflow reaches checkpoint                                        │
│     → UPDATE PREPARED, POST to /tool-checkpoint                              │
│     → Agent: "Email to john.smith@gmail.com is ready. Send it?"              │
│                                                                              │
│  5. User: "Yes, send it"                                                     │
│     → POST /resume-execution/tc_abc { action: "proceed" }                    │
│     → UPDATE EXECUTING (actual), Gmail sends email                           │
│                                                                              │
│  6. Tool completes                                                           │
│     → UPDATE COMPLETED, POST to /tool-complete                               │
│     → Agent: "Email sent to john.smith@gmail.com successfully!"              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Relay Endpoints (Updated)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/tool-checkpoint` | POST | Receives checkpoint notification, agent asks for final confirm |
| `/tool-complete` | POST | Receives completion notification, agent announces result |

```typescript
// Checkpoint callback - agent asks for final confirmation
app.post('/tool-checkpoint', async (req, res) => {
  const { tool_call_id, status, checkpoint, message, resume_webhook } = req.body;

  // Update cache
  updateCache(session_id, { tool_call_id, status: 'PREPARED' });

  // Store resume webhook for when user confirms
  pendingCheckpoints.set(tool_call_id, resume_webhook);

  // Notify OpenAI - agent will ask user for final confirmation
  await notifyCheckpoint(tool_call_id, { status, message });

  res.json({ received: true });
});

// When user says "send it" at checkpoint
async function handleFinalConfirmation(tool_call_id: string, action: 'proceed' | 'cancel') {
  const resume_webhook = pendingCheckpoints.get(tool_call_id);

  // Call n8n resume webhook
  await fetch(resume_webhook, {
    method: 'POST',
    body: JSON.stringify({ action })
  });

  pendingCheckpoints.delete(tool_call_id);
}
```

---

### n8n Workflows (Updated Count)

| Workflow | Purpose |
|----------|---------|
| **MCP Server Trigger** | Exposes 5 MCP tools |
| **Async Executor** | Handles first phase → checkpoint |
| **Resume Execution** | Handles checkpoint → actual execution |
| **Voice Tool: send_email** | Gmail send |
| **Voice Tool: schedule_meeting** | Calendar booking |
| **Voice Tool: search_contacts** | CRM lookup |
| **Voice Tool: get_calendar_availability** | Calendar query |
| **Voice Tool: create_task** | Task creation |
| **Voice Tool: search_documentation** | Knowledge base |
| **Voice Tool: get_training_progress** | Training data |
| **Voice Tool: knowledge_check** | Assessment |

**Total: 11 workflows** (3 orchestration + 8 tool sub-workflows)

---

### Success Criteria (Final)

**Database as Source of Truth:**
- [ ] All state in PostgreSQL tool_calls table (including PREPARED state)
- [ ] Session cache in relay for fast reads (updated, never invalidated)
- [ ] Agent queries context via get_context MCP tool

**Async Execution with Checkpoint:**
- [ ] confirm_tool returns immediately with EXECUTING
- [ ] Async workflow reaches PREPARED state (checkpoint)
- [ ] Callback to relay: "Email is ready. Send it?"
- [ ] User confirms → resume-execution webhook triggers actual execution
- [ ] Callback notifies relay of completion
- [ ] Agent announces success

**Full Tool Flow:**
- [ ] request_tool creates PENDING record
- [ ] modify_tool updates parameters in database
- [ ] confirm_tool triggers async execution
- [ ] cancel_tool sets status to CANCELLED (checked by executor)
- [ ] get_context returns pending + recent from database

**Observability:**
- [ ] Each tool sub-workflow has independent execution history
- [ ] Full audit trail: parameters_history, status_history
- [ ] execution_time_ms tracked per tool call

---

## REVISED ARCHITECTURE: Pre-Confirmation + Gated Execution

### User Requirement Clarification

The user wants:
1. **AI confirms BEFORE any n8n call** - Agent asks user to confirm parameters FIRST
2. **User can modify before execution** - Handled entirely in relay/OpenAI
3. **Gated execution with checkpoints** - Workflow sends progress, can be cancelled mid-execution
4. **Completion notification** - Agent always announces successful completion

### Key Insight: Two Layers of Control

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: PRE-CALL CONFIRMATION (Relay Server - No n8n involved)             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "Send email to john@gmail.com"                                        │
│       ↓                                                                      │
│  OpenAI: Detects intent, extracts parameters                                 │
│       ↓                                                                      │
│  Relay: Stores params locally, does NOT call n8n yet                         │
│       ↓                                                                      │
│  Agent: "I'll send an email to john@gmail.com. Is that correct?"             │
│       ↓                                                                      │
│  User: "No, use john.smith@gmail.com instead"                                │
│       ↓                                                                      │
│  Relay: Updates local params (still no n8n call)                             │
│       ↓                                                                      │
│  Agent: "Updated to john.smith@gmail.com. Confirm to send?"                  │
│       ↓                                                                      │
│  User: "Yes, send it"                                                        │
│       ↓                                                                      │
│  ══════════════════ NOW ENTERS LAYER 2 ══════════════════                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: GATED EXECUTION (n8n with checkpoints + callbacks)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Relay: Calls n8n /execute-tool with confirmed parameters                    │
│       ↓                                                                      │
│  n8n: Creates record (EXECUTING), starts workflow                            │
│       ↓                                                                      │
│  n8n: GATE 1 - Callback to relay: "Starting email send..."                   │
│       ↓                                                                      │
│  Agent: "Sending email now..."                                               │
│       ↓                                                                      │
│  [User can say "Stop!" here]                                                 │
│       ↓                                                                      │
│  n8n: GATE 2 - Check for cancellation signal                                 │
│       ↓                                                                      │
│  [If cancelled] → Abort, callback: "Cancelled"                               │
│  [If continue]  → Execute Gmail API call                                     │
│       ↓                                                                      │
│  n8n: GATE 3 - Callback: "Email sent successfully!"                          │
│       ↓                                                                      │
│  Agent: "Email sent to john.smith@gmail.com successfully!"                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Revised Flow: "Updating Email" Scenario

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: INTENT DETECTION + PRE-CONFIRMATION (No n8n)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  T+0ms: User speaks                                                          │
│  "Send an email to john@gmail.com about the meeting tomorrow"                │
│       ↓                                                                      │
│  T+300ms: OpenAI Realtime STT → text                                         │
│       ↓                                                                      │
│  T+500ms: OpenAI detects tool intent                                         │
│       │                                                                      │
│       │  Function: send_email                                                │
│       │  Arguments: {                                                        │
│       │    "to": "john@gmail.com",                                           │
│       │    "subject": "Meeting Tomorrow",                                    │
│       │    "body": "Let's discuss..."                                        │
│       │  }                                                                   │
│       │  requires_confirmation: true  ← KEY FLAG                             │
│       ▼                                                                      │
│  T+510ms: Relay stores pending intent locally                                │
│       │                                                                      │
│       │  pendingIntents["intent_123"] = {                                    │
│       │    function: "send_email",                                           │
│       │    params: {...},                                                    │
│       │    confirmed: false                                                  │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+520ms: Relay returns to OpenAI (NOT a tool result)                        │
│       │                                                                      │
│       │  {                                                                   │
│       │    type: "confirmation_required",                                    │
│       │    intent_id: "intent_123",                                          │
│       │    summary: "Send email to john@gmail.com about 'Meeting Tomorrow'"  │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+800ms: Agent speaks (TTS)                                                 │
│       │                                                                      │
│       │  "I'll send an email to john@gmail.com about the meeting             │
│       │   tomorrow. Is that correct?"                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: USER CORRECTION (Still no n8n)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  T+3000ms: User speaks correction                                            │
│  "Wait, that should be john.smith@gmail.com"                                 │
│       ↓                                                                      │
│  T+3300ms: OpenAI Realtime STT → text                                        │
│       ↓                                                                      │
│  T+3500ms: OpenAI detects modification intent                                │
│       │                                                                      │
│       │  Function: modify_pending_intent                                     │
│       │  Arguments: {                                                        │
│       │    "intent_id": "intent_123",                                        │
│       │    "field": "to",                                                    │
│       │    "new_value": "john.smith@gmail.com"                               │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+3510ms: Relay updates local pending intent                                │
│       │                                                                      │
│       │  pendingIntents["intent_123"].params.to = "john.smith@gmail.com"     │
│       │  pendingIntents["intent_123"].modifications.push({                   │
│       │    field: "to",                                                      │
│       │    old: "john@gmail.com",                                            │
│       │    new: "john.smith@gmail.com",                                      │
│       │    timestamp: Date.now()                                             │
│       │  })                                                                  │
│       ▼                                                                      │
│  T+3520ms: Relay returns to OpenAI                                           │
│       │                                                                      │
│       │  {                                                                   │
│       │    type: "intent_modified",                                          │
│       │    intent_id: "intent_123",                                          │
│       │    updated_summary: "Send email to john.smith@gmail.com..."          │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+3800ms: Agent speaks                                                      │
│       │                                                                      │
│       │  "Updated to john.smith@gmail.com. Confirm to send?"                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: USER CONFIRMS → EXECUTION BEGINS (n8n enters)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  T+5000ms: User confirms                                                     │
│  "Yes, send it"                                                              │
│       ↓                                                                      │
│  T+5300ms: OpenAI Realtime STT → text                                        │
│       ↓                                                                      │
│  T+5500ms: OpenAI detects confirmation                                       │
│       │                                                                      │
│       │  Function: confirm_intent                                            │
│       │  Arguments: { "intent_id": "intent_123" }                            │
│       ▼                                                                      │
│  T+5510ms: Relay executes confirmed intent                                   │
│       │                                                                      │
│       │  // Mark as confirmed                                                │
│       │  pendingIntents["intent_123"].confirmed = true                       │
│       │                                                                      │
│       │  // NOW call n8n                                                     │
│       │  MCP Tool Call: execute_tool                                         │
│       │  Payload: {                                                          │
│       │    "session_id": "sess_abc123",                                      │
│       │    "function_name": "send_email",                                    │
│       │    "parameters": {                                                   │
│       │      "to": "john.smith@gmail.com",                                   │
│       │      "subject": "Meeting Tomorrow",                                  │
│       │      "body": "Let's discuss..."                                      │
│       │    },                                                                │
│       │    "callback_url": "https://relay.railway.app/tool-progress",        │
│       │    "intent_id": "intent_123"                                         │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+5530ms: n8n receives execution request                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: GATED EXECUTION IN N8N (With progress callbacks)                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  N8N: EXECUTE_TOOL SUB-WORKFLOW                                              │
│                                                                              │
│  T+5530ms: Execute Workflow Trigger receives request                         │
│       ↓                                                                      │
│  T+5540ms: Code Node - Generate tool_call_id, create DB record               │
│       │                                                                      │
│       │  INSERT INTO tool_calls (                                            │
│       │    tool_call_id, session_id, function_name,                          │
│       │    parameters, status, intent_id                                     │
│       │  ) VALUES (                                                          │
│       │    'tc_xyz789', 'sess_abc123', 'send_email',                         │
│       │    {...}, 'EXECUTING', 'intent_123'                                  │
│       │  );                                                                  │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 1: Progress Callback - "Starting"                              │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │  T+5550ms: HTTP Request Node → Callback to relay                    │    │
│  │       │                                                             │    │
│  │       │  POST https://relay.railway.app/tool-progress               │    │
│  │       │  {                                                          │    │
│  │       │    "tool_call_id": "tc_xyz789",                             │    │
│  │       │    "intent_id": "intent_123",                               │    │
│  │       │    "status": "EXECUTING",                                   │    │
│  │       │    "progress": "Starting email send...",                    │    │
│  │       │    "gate": 1,                                               │    │
│  │       │    "cancellable": true                                      │    │
│  │       │  }                                                          │    │
│  │       ▼                                                             │    │
│  │  T+5600ms: Relay receives callback                                  │    │
│  │       │                                                             │    │
│  │       │  // Update OpenAI conversation                              │    │
│  │       │  // Agent can now say "Sending email now..."                │    │
│  │       ▼                                                             │    │
│  │  T+5650ms: Check for cancellation signal                            │    │
│  │       │                                                             │    │
│  │       │  // Relay checks: has user said "stop"?                     │    │
│  │       │  // If yes, respond with {cancel: true}                     │    │
│  │       │  // If no, respond with {continue: true}                    │    │
│  │       ▼                                                             │    │
│  │  T+5660ms: n8n receives response                                    │    │
│  │       │                                                             │    │
│  │       │  IF response.cancel === true:                               │    │
│  │       │    → Jump to CANCELLATION branch                            │    │
│  │       │  ELSE:                                                      │    │
│  │       │    → Continue to next gate                                  │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 2: Execute Tool (Gmail API call)                               │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │  T+5700ms: Set Node - Route to correct tool workflow                │    │
│  │       ↓                                                             │    │
│  │  T+5710ms: Execute Workflow - Voice Tool: send_email                │    │
│  │       │                                                             │    │
│  │       │  ┌─────────────────────────────────────────────────────┐   │    │
│  │       │  │ SUB-WORKFLOW: send_email                            │   │    │
│  │       │  │                                                     │   │    │
│  │       │  │ Gmail Node (typeVersion 2.2)                        │   │    │
│  │       │  │   operation: "send"                                 │   │    │
│  │       │  │   sendTo: "john.smith@gmail.com"                    │   │    │
│  │       │  │   subject: "Meeting Tomorrow"                       │   │    │
│  │       │  │   message: "Let's discuss..."                       │   │    │
│  │       │  │                                                     │   │    │
│  │       │  │ *** GMAIL API CALL EXECUTES ***                     │   │    │
│  │       │  │                                                     │   │    │
│  │       │  │ Returns: { id: "msg_xyz", threadId: "thread_abc" }  │   │    │
│  │       │  └─────────────────────────────────────────────────────┘   │    │
│  │       ↓                                                             │    │
│  │  T+7500ms: Gmail response received (~1.8s for API call)             │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 3: Completion Callback                                         │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │  T+7510ms: Code Node - Format result + voice response               │    │
│  │       │                                                             │    │
│  │       │  result = {                                                 │    │
│  │       │    success: True,                                           │    │
│  │       │    message_id: "msg_xyz",                                   │    │
│  │       │    voice_response: "Email sent to john.smith@gmail.com      │    │
│  │       │                     successfully!"                          │    │
│  │       │  }                                                          │    │
│  │       ▼                                                             │    │
│  │  T+7520ms: PostgreSQL - Update status to COMPLETED                  │    │
│  │       │                                                             │    │
│  │       │  UPDATE tool_calls SET                                      │    │
│  │       │    status = 'COMPLETED',                                    │    │
│  │       │    completed_at = NOW(),                                    │    │
│  │       │    execution_time_ms = 1970,                                │    │
│  │       │    result = {...},                                          │    │
│  │       │    voice_response = 'Email sent...'                         │    │
│  │       │  WHERE tool_call_id = 'tc_xyz789';                          │    │
│  │       ▼                                                             │    │
│  │  T+7530ms: HTTP Request - Final callback to relay                   │    │
│  │       │                                                             │    │
│  │       │  POST https://relay.railway.app/tool-progress               │    │
│  │       │  {                                                          │    │
│  │       │    "tool_call_id": "tc_xyz789",                             │    │
│  │       │    "intent_id": "intent_123",                               │    │
│  │       │    "status": "COMPLETED",                                   │    │
│  │       │    "result": {...},                                         │    │
│  │       │    "voice_response": "Email sent to john.smith@gmail.com    │    │
│  │       │                       successfully!",                       │    │
│  │       │    "execution_time_ms": 1970                                │    │
│  │       │  }                                                          │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  T+7540ms: Return to MCP (workflow complete)                                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: COMPLETION ANNOUNCEMENT                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  T+7550ms: Relay receives completion callback                                │
│       │                                                                      │
│       │  // Clean up pending intent                                          │
│       │  delete pendingIntents["intent_123"]                                 │
│       │                                                                      │
│       │  // Notify OpenAI of completion                                      │
│       │  function_call_output: {                                             │
│       │    status: "completed",                                              │
│       │    result: {...},                                                    │
│       │    voice_response: "Email sent to john.smith@gmail.com..."           │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+7850ms: Agent speaks (TTS)                                                │
│       │                                                                      │
│       │  "Email sent to john.smith@gmail.com successfully!"                  │
│                                                                              │
│  TOTAL TIME: ~7.85 seconds (including user confirmation delays)              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### CANCELLATION FLOW (User says "Stop!" during execution)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ CANCELLATION SCENARIO                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  During GATE 1 callback wait:                                                │
│                                                                              │
│  T+5600ms: Relay receives progress callback from n8n                         │
│       │    { status: "EXECUTING", gate: 1, cancellable: true }               │
│       │                                                                      │
│  T+5610ms: Agent says "Sending email now..."                                 │
│       │                                                                      │
│  T+5700ms: User interrupts: "Stop! Don't send that!"                         │
│       │                                                                      │
│       │  Relay sets: cancelRequests["intent_123"] = true                     │
│       │                                                                      │
│  T+5750ms: n8n polling for cancellation signal                               │
│       │                                                                      │
│       │  Response to n8n: { cancel: true, reason: "User requested" }         │
│       ▼                                                                      │
│  T+5760ms: n8n receives cancel signal                                        │
│       │                                                                      │
│       │  IF Node: cancel === true?                                           │
│       │    → YES: Jump to cancellation branch                                │
│       ▼                                                                      │
│  T+5770ms: PostgreSQL - Update status to CANCELLED                           │
│       │                                                                      │
│       │  UPDATE tool_calls SET                                               │
│       │    status = 'CANCELLED',                                             │
│       │    completed_at = NOW(),                                             │
│       │    error_message = 'User cancelled'                                  │
│       │  WHERE tool_call_id = 'tc_xyz789';                                   │
│       ▼                                                                      │
│  T+5780ms: HTTP Request - Cancellation callback to relay                     │
│       │                                                                      │
│       │  POST https://relay.railway.app/tool-progress                        │
│       │  {                                                                   │
│       │    "tool_call_id": "tc_xyz789",                                      │
│       │    "status": "CANCELLED",                                            │
│       │    "voice_response": "Email cancelled. The email was not sent."      │
│       │  }                                                                   │
│       ▼                                                                      │
│  T+5900ms: Relay receives cancellation confirmation                          │
│       │                                                                      │
│       │  // Clean up                                                         │
│       │  delete pendingIntents["intent_123"]                                 │
│       │  delete cancelRequests["intent_123"]                                 │
│       ▼                                                                      │
│  T+6200ms: Agent speaks                                                      │
│       │                                                                      │
│       │  "Cancelled. The email was not sent."                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Revised Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    REVISED ENTERPRISE VOICE AGENT SYSTEM                          │
│              Pre-Confirmation (Relay) + Gated Execution (n8n)                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │ RELAY SERVER (Railway) - Handles pre-confirmation                        │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                          │    │
│  │  OpenAI Realtime API ←→ Voice conversation                               │    │
│  │       │                                                                  │    │
│  │       ├── Intent Detection → pendingIntents map (local)                  │    │
│  │       ├── Modification → Update pendingIntents (no n8n)                  │    │
│  │       ├── Confirmation → MCP call to n8n                                 │    │
│  │       ├── Progress callbacks ← n8n gated execution                       │    │
│  │       ├── Cancel requests → cancelRequests map                           │    │
│  │       └── Completion → Announce to user                                  │    │
│  │                                                                          │    │
│  │  Callback Endpoint: POST /tool-progress                                  │    │
│  │       │                                                                  │    │
│  │       ├── Receives: { status, progress, gate, cancellable }              │    │
│  │       ├── Checks: cancelRequests[intent_id]                              │    │
│  │       └── Returns: { continue: true } or { cancel: true }                │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│       │                                                                           │
│       │  MCP Tool Call: execute_tool (only after user confirms)                   │
│       ▼                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │ N8N: MCP SERVER TRIGGER + GATED EXECUTOR                                 │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                          │    │
│  │  MCP Server Trigger (path: /voice-agent)                                 │    │
│  │       │                                                                  │    │
│  │       └──→ Tool: execute_tool                                            │    │
│  │             │                                                            │    │
│  │             ▼                                                            │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │    │
│  │  │ EXECUTE_TOOL SUB-WORKFLOW (Gated)                                │   │    │
│  │  ├──────────────────────────────────────────────────────────────────┤   │    │
│  │  │                                                                  │   │    │
│  │  │  1. Execute Workflow Trigger                                     │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  2. Code: Generate tool_call_id, INSERT EXECUTING                │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │   │    │
│  │  │  │ GATE 1: HTTP callback → relay (cancellable: true)         │ │   │    │
│  │  │  │         Wait for response: continue or cancel             │ │   │    │
│  │  │  └────────────────────────────────────────────────────────────┘ │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  3. IF: cancelled? → CANCEL branch                               │   │    │
│  │  │       ↓ (continue)                                               │   │    │
│  │  │  4. Set: Route to tool workflow                                  │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  5. Execute Workflow: Voice Tool: {function_name}                │   │    │
│  │  │       │                                                          │   │    │
│  │  │       ├──→ Voice Tool: send_email (Gmail)                        │   │    │
│  │  │       ├──→ Voice Tool: schedule_meeting                          │   │    │
│  │  │       ├──→ Voice Tool: search_contacts                           │   │    │
│  │  │       └──→ ... (8 total)                                         │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  6. Code: Format result + voice_response                         │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  7. PostgreSQL: UPDATE COMPLETED                                 │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  ┌────────────────────────────────────────────────────────────┐ │   │    │
│  │  │  │ GATE 3: HTTP callback → relay (status: COMPLETED)         │ │   │    │
│  │  │  │         Final result + voice_response                     │ │   │    │
│  │  │  └────────────────────────────────────────────────────────────┘ │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  8. Return result to MCP                                         │   │    │
│  │  │                                                                  │   │    │
│  │  │  ─────────────────────────────────────────────────────────────   │   │    │
│  │  │                                                                  │   │    │
│  │  │  CANCEL BRANCH:                                                  │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  PostgreSQL: UPDATE CANCELLED                                    │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  HTTP callback → relay (status: CANCELLED)                       │   │    │
│  │  │       ↓                                                          │   │    │
│  │  │  Return cancellation to MCP                                      │   │    │
│  │  │                                                                  │   │    │
│  │  └──────────────────────────────────────────────────────────────────┘   │    │
│  │                                                                          │    │
│  │  Tool: get_context (query tool history)                                  │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
│  Sub-Workflows (8 total - Independent execution history):                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  Voice Tool: send_email        │  Voice Tool: schedule_meeting           │    │
│  │  Voice Tool: search_contacts   │  Voice Tool: get_calendar_availability  │    │
│  │  Voice Tool: create_task       │  Voice Tool: search_documentation       │    │
│  │  Voice Tool: get_training_progress │ Voice Tool: knowledge_check         │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

### Key Differences from Previous Design

| Aspect | Previous Design | Revised Design |
|--------|-----------------|----------------|
| **Pre-confirmation** | n8n creates PENDING record | Relay handles locally, no n8n |
| **Modification** | MCP call to modify_tool | Relay updates local state |
| **When n8n is called** | On first tool request | Only after user confirms |
| **Execution state** | PENDING → CONFIRM → EXECUTE | Direct EXECUTE (already confirmed) |
| **Progress updates** | None | Gated callbacks at checkpoints |
| **Cancellation** | Update DB record | HTTP callback with cancel signal |
| **MCP tools needed** | request, modify, confirm, cancel, context | execute, context |

---

### MCP Tools (Simplified)

| Tool | Purpose |
|------|---------|
| **execute_tool** | Execute confirmed tool, includes callback_url for progress |
| **get_context** | Query tool history for agent reference |

The **5 state management tools become 2** because:
- `request_tool` → Relay handles locally
- `modify_tool` → Relay handles locally
- `confirm_tool` → Merged into `execute_tool`
- `cancel_tool` → HTTP callback response `{cancel: true}`
- `get_context` → Stays the same

---

### Relay Server Requirements

The relay server needs to implement:

```typescript
// Local state management
interface PendingIntent {
  function_name: string;
  parameters: Record<string, any>;
  confirmed: boolean;
  modifications: Array<{
    field: string;
    old: any;
    new: any;
    timestamp: number;
  }>;
}

const pendingIntents: Map<string, PendingIntent> = new Map();
const cancelRequests: Set<string> = new Set();

// Callback endpoint for n8n progress updates
app.post('/tool-progress', (req, res) => {
  const { intent_id, status, progress, gate, cancellable } = req.body;

  // Check if user requested cancellation
  if (cancellable && cancelRequests.has(intent_id)) {
    cancelRequests.delete(intent_id);
    return res.json({ cancel: true, reason: 'User requested' });
  }

  // Forward progress to OpenAI conversation
  notifyProgress(intent_id, { status, progress });

  // Continue execution
  return res.json({ continue: true });
});
```

---

### Success Criteria (Updated)

**Pre-Confirmation (Relay):**
- [ ] Agent asks for confirmation BEFORE any n8n call
- [ ] User can modify parameters without n8n involvement
- [ ] Local state tracks pending intents and modifications

**Gated Execution (n8n):**
- [ ] Gate 1 callback sends progress, checks for cancellation
- [ ] User can say "stop" and execution halts
- [ ] Gate 3 callback sends completion with voice_response
- [ ] Each tool sub-workflow has independent execution history

**Completion:**
- [ ] Agent always announces successful completion
- [ ] Agent announces cancellation if stopped
- [ ] Full audit trail in PostgreSQL

---

## FINAL IMPLEMENTATION: Two Workflow Architecture

### Overview

Based on user requirements, the system has exactly **2 tool workflows** (plus 1 supporting workflow):

| Workflow | Purpose | Key Feature |
|----------|---------|-------------|
| **Send Gmail** | Send emails via Gmail API | Gated execution with pre-send checkpoint |
| **Query Vector Database** | Retrieve information for agent context | Agent writes structured query, results available for emails |
| **Get Session Context** | Supporting: fetch stored context | Fallback when relay cache expires |

---

## Workflow 1: Send Gmail (Gated Execution)

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEND GMAIL WORKFLOW - GATED EXECUTION                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PHASE 1: PRE-CONFIRMATION (Relay - No n8n)                             │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  User: "Send an email to john@example.com about the project"           │ │
│  │       ↓                                                                │ │
│  │  OpenAI: Extracts intent + parameters                                  │ │
│  │       ↓                                                                │ │
│  │  Relay: Stores in pendingIntents["intent_123"]                         │ │
│  │       │  {                                                             │ │
│  │       │    function_name: "send_gmail",                                │ │
│  │       │    parameters: { to, subject, body },                          │ │
│  │       │    confirmed: false                                            │ │
│  │       │  }                                                             │ │
│  │       ↓                                                                │ │
│  │  Agent: "I'll send an email to john@example.com. Correct?"             │ │
│  │       ↓                                                                │ │
│  │  [User: CONFIRM / MODIFY / CANCEL]                                     │ │
│  │       ↓                                                                │ │
│  │  User confirms → pendingIntents.confirmed = true → Call n8n            │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PHASE 2: GATED EXECUTION (n8n Workflow)                                │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Webhook: POST /execute-gmail                                          │ │
│  │       │  Payload: { intent_id, session_id, to, subject, body,          │ │
│  │       │             callback_url }                                     │ │
│  │       ▼                                                                │ │
│  │  GATE 1: Insert Record + Progress Callback                             │ │
│  │       Code: Generate tool_call_id                                      │ │
│  │       PostgreSQL: INSERT (EXECUTING)                                   │ │
│  │       HTTP: POST callback { status: "PREPARING", cancellable: true }   │ │
│  │       [Wait for: {continue} or {cancel}]                               │ │
│  │       ↓                                                                │ │
│  │  GATE 2: Pre-Send Checkpoint (Human-in-the-Loop)                       │ │
│  │       HTTP: POST callback { status: "READY_TO_SEND",                   │ │
│  │                             requires_confirmation: true }              │ │
│  │       Agent: "Email to X is ready. Send it?"                           │ │
│  │       [Wait for: {continue} or {cancel}]                               │ │
│  │       ↓                                                                │ │
│  │  GATE 3: Execute Gmail Send                                            │ │
│  │       Gmail Node (typeVersion: 2.2): Send email                        │ │
│  │       Code: Format result { message_id, thread_id }                    │ │
│  │       ↓                                                                │ │
│  │  GATE 4: Completion Callback                                           │ │
│  │       PostgreSQL: UPDATE status = 'COMPLETED'                          │ │
│  │       HTTP: POST callback { status: "COMPLETED", voice_response }      │ │
│  │       Respond: { success: true }                                       │ │
│  │                                                                        │ │
│  │  CANCEL BRANCH: PostgreSQL UPDATE → callback → respond                 │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PHASE 3: COMPLETION (Relay)                                            │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │  Relay receives callback → Clean up pendingIntents                     │ │
│  │  Agent (TTS): "Email sent to john@example.com successfully!"           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Send Gmail Node Summary

| Node | Type | Purpose |
|------|------|---------|
| Webhook | webhook | Entry: POST /execute-gmail |
| Generate Tool Call ID | code | Create tc_xxx identifier |
| Insert Tool Call | postgres | Record in tool_calls table |
| Gate 1: Progress Callback | httpRequest | Notify relay + check cancel |
| Check Cancel Gate 1 | if | Branch on cancel response |
| Gate 2: Pre-Send Checkpoint | httpRequest | Final confirm before send |
| Check Cancel Gate 2 | if | Branch on cancel response |
| Gmail: Send Email | gmail | Execute email send (typeVersion: 2.2) |
| Format Result | code | Build response with message_id |
| Update Status: Completed | postgres | Mark COMPLETED |
| Completion Callback | httpRequest | Notify relay of success |
| Respond: Success | respondToWebhook | Return to caller |
| Update Status: Cancelled | postgres | Mark CANCELLED (cancel branch) |
| Cancel Callback | httpRequest | Notify cancellation |
| Respond: Cancelled | respondToWebhook | Return cancelled |

---

## Workflow 2: Query Vector Database

### Purpose

This workflow enables the agent to:
1. Take a user's natural language query
2. Have the agent write a structured database query (done in relay)
3. Confirm the query before execution
4. Execute against the vector database
5. Store results in session context
6. Notify agent that data is available for email writing

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    QUERY VECTOR DATABASE - GATED EXECUTION                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PHASE 1: AGENT QUERY FORMULATION (Relay)                               │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  User: "Look up the Q3 sales data for the northwest region"            │ │
│  │       ↓                                                                │ │
│  │  OpenAI: Extracts intent { function: "query_vector_db" }               │ │
│  │       ↓                                                                │ │
│  │  Agent: Writes structured query, confirms with user                    │ │
│  │       "I'll search for Q3 2024 sales in Northwest (WA, OR, ID, MT)     │ │
│  │        filtering July-September. Is this correct?"                     │ │
│  │       ↓                                                                │ │
│  │  Relay: Stores structured_query in pendingIntents                      │ │
│  │       {                                                                │ │
│  │         function_name: "query_vector_db",                              │ │
│  │         parameters: {                                                  │ │
│  │           user_query: "Q3 sales data northwest",                       │ │
│  │           structured_query: {                                          │ │
│  │             filters: { date_start, date_end, region[] },               │ │
│  │             semantic_query: "quarterly sales northwest"                │ │
│  │           }                                                            │ │
│  │         }                                                              │ │
│  │       }                                                                │ │
│  │       ↓                                                                │ │
│  │  User: "Yes" → confirmed = true → Call n8n                             │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PHASE 2: GATED EXECUTION (n8n Workflow)                                │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Webhook: POST /query-vector-db                                        │ │
│  │       ↓                                                                │ │
│  │  GATE 1: Insert Record + Progress                                      │ │
│  │       Code: Generate tool_call_id                                      │ │
│  │       PostgreSQL: INSERT (EXECUTING)                                   │ │
│  │       HTTP: POST callback { status: "QUERYING", cancellable: true }    │ │
│  │       [Wait for continue/cancel]                                       │ │
│  │       ↓                                                                │ │
│  │  GATE 2: Execute Vector Query                                          │ │
│  │       Embeddings: Generate query embedding                             │ │
│  │       HTTP: Query Pinecone/Supabase with filters                       │ │
│  │       Code: Format results { summary, metrics, documents }             │ │
│  │       ↓                                                                │ │
│  │  GATE 3: Store in Session Context                                      │ │
│  │       PostgreSQL: UPSERT session_context                               │ │
│  │         context_key: "last_query_results"                              │ │
│  │         expires_at: NOW() + 1 hour                                     │ │
│  │       ↓                                                                │ │
│  │  GATE 4: Completion Callback                                           │ │
│  │       PostgreSQL: UPDATE (COMPLETED)                                   │ │
│  │       HTTP: POST callback {                                            │ │
│  │         status: "COMPLETED",                                           │ │
│  │         context_available: true,  ← KEY FLAG                           │ │
│  │         context_key: "last_query_results",                             │ │
│  │         voice_response: "Found Q3 data. $4.2M total sales..."          │ │
│  │       }                                                                │ │
│  │       Respond: { success: true }                                       │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ PHASE 3: DATA AVAILABLE (Relay)                                        │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                        │ │
│  │  Relay receives callback with context_available: true                  │ │
│  │  Relay caches: sessionContexts["sess_abc"]["last_query_results"]       │ │
│  │  Agent: "I found Q3 sales data. $4.2M total. This is available         │ │
│  │          if you want to reference it in an email."                     │ │
│  │                                                                        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Availability: Reference Query Results in Email

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA REFERENCE FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  User: "Now send an email to the regional manager with these numbers"        │
│       ↓                                                                      │
│  OpenAI: Detects email + reference to previous query                         │
│       Args: { to, subject, body: <DRAFTED FROM CONTEXT>,                     │
│               reference_context: "last_query_results" }                      │
│       ↓                                                                      │
│  Relay: Fetch context from cache or GET /get-session-context                 │
│       ↓                                                                      │
│  Agent drafts email body using the query results:                            │
│       "Total Sales: $4.2M, Units Sold: 12,450..."                            │
│       ↓                                                                      │
│  Agent: "I'll send an email to the regional manager with the Q3              │
│          sales data. Send it?"                                               │
│       ↓                                                                      │
│  [Normal gated email flow continues...]                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow 3: Get Session Context (Supporting)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GET SESSION CONTEXT WORKFLOW                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Webhook: GET /get-session-context?session_id=X&context_key=Y                │
│       ↓                                                                      │
│  PostgreSQL: SELECT context_value FROM session_context                       │
│       WHERE session_id = :session_id AND context_key = :context_key          │
│       AND expires_at > NOW()                                                 │
│       ↓                                                                      │
│  IF found → Respond: { context: context_value }                              │
│  ELSE     → Respond: { error: "Not found or expired" }                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema (Complete)

```sql
-- Tool calls audit table
CREATE TABLE tool_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_call_id VARCHAR(100) UNIQUE NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    intent_id VARCHAR(100),
    function_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'EXECUTING',
    result JSONB,
    error_message TEXT,
    voice_response TEXT,
    callback_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    execution_time_ms INTEGER,
    CONSTRAINT valid_status CHECK (
        status IN ('EXECUTING', 'COMPLETED', 'FAILED', 'CANCELLED')
    )
);

CREATE INDEX idx_tool_calls_session ON tool_calls(session_id, created_at DESC);

-- Session context for cross-tool data sharing
CREATE TABLE session_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    context_key VARCHAR(100) NOT NULL,
    context_value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(session_id, context_key)
);

CREATE INDEX idx_session_context_lookup
ON session_context(session_id, context_key)
WHERE expires_at > NOW();
```

---

## Complete System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE TWO-WORKFLOW VOICE AGENT                              │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │ RELAY SERVER (Railway)                                                    │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                          │    │
│  │  OpenAI Realtime API                                                     │    │
│  │       ├── Intent: send_gmail → Pre-confirm → POST /execute-gmail         │    │
│  │       ├── Intent: query_vector_db → Agent writes query → Pre-confirm     │    │
│  │       │                            → POST /query-vector-db               │    │
│  │       └── Reference context → Cache or GET /get-session-context          │    │
│  │                                                                          │    │
│  │  Callback: POST /tool-progress ← Gate callbacks from n8n                 │    │
│  │                                                                          │    │
│  │  State:                                                                  │    │
│  │       pendingIntents: Map<intent_id, PendingIntent>                      │    │
│  │       cancelRequests: Set<intent_id>                                     │    │
│  │       sessionContexts: Map<session_id, Map<key, value>>                  │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│       │                                                                           │
│       ▼                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │ N8N WORKFLOWS (3 total)                                                   │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                          │    │
│  │  1. Voice Tool: Send Gmail (POST /execute-gmail)                         │    │
│  │     Gates: PREPARING → READY_TO_SEND → EXECUTE → COMPLETED               │    │
│  │                                                                          │    │
│  │  2. Voice Tool: Query Vector DB (POST /query-vector-db)                  │    │
│  │     Gates: QUERYING → EXECUTE → STORE_CONTEXT → COMPLETED                │    │
│  │                                                                          │    │
│  │  3. Get Session Context (GET /get-session-context)                       │    │
│  │     Returns: context value or error                                      │    │
│  │                                                                          │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│       │                                                                           │
│       ▼                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │ POSTGRESQL                                                                │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │  tool_calls: Audit trail for all executions                              │    │
│  │  session_context: Cross-tool data sharing (1-hour expiry)                │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Workflow Summary Table

| # | Workflow | Webhook | Purpose |
|---|----------|---------|---------|
| 1 | Voice Tool: Send Gmail | POST /execute-gmail | Gated email with pre-send checkpoint |
| 2 | Voice Tool: Query Vector DB | POST /query-vector-db | Gated query + context storage |
| 3 | Get Session Context | GET /get-session-context | Fetch context for email drafting |

---

## Final Implementation Success Criteria

**Two-Workflow Architecture:**
- [ ] Send Gmail: 4 gates (PREPARING → READY_TO_SEND → EXECUTE → COMPLETED)
- [ ] Query Vector DB: 4 gates (QUERYING → EXECUTE → STORE → COMPLETED)
- [ ] Get Session Context: Simple query/response

**Pre-Confirmation (Relay):**
- [ ] Agent confirms before any n8n call
- [ ] Agent writes structured query for vector DB
- [ ] User can modify/cancel before execution

**Gated Execution (n8n):**
- [ ] Each gate sends HTTP callback to relay
- [ ] Relay responds {continue: true} or {cancel: true}
- [ ] Gate 2 (READY_TO_SEND) has requires_confirmation: true

**Data Availability:**
- [ ] Vector results stored with context_key "last_query_results"
- [ ] Results available via reference_context in email requests
- [ ] Session cache + DB fallback
- [ ] Agent drafts email body using context data

**Completion:**
- [ ] Agent announces with voice_response
- [ ] context_available: true signals data ready
- [ ] Full audit in tool_calls table
