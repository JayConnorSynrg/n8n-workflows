# Composio Tool Router — Architecture & Approach

**Created:** 2026-02-19
**Updated:** 2026-02-19
**Status:** Deployed (Railway)
**Problem:** Agent speaking function names/JSON aloud instead of natural language

---

## Problem Statement

The voice agent needs access to a plethora of Composio tools (Gmail, Google Drive, Slack, Teams, etc.) WITHOUT loading all individual tool schemas into the LLM context. Loading hundreds of schemas causes:
- Context pollution (200-400 tool schemas flood the LLM)
- Model confusion (agent speaks function names aloud instead of executing them)
- Token waste (large context = slower inference + higher cost)

## Solution: Composio Tool Router

Hybrid MCP + Python SDK approach: MCP for discovery/planning, Python SDK for execution.
The LLM discovers tools via MCP, plans execution order, then executes via Python wrappers
that dispatch to AsyncToolWorker for non-blocking background execution.

### How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│  WHAT THE LLM SEES                                                  │
│                                                                     │
│  VIA MCP (discovery + auth + planning):                             │
│  1. COMPOSIO_SEARCH_TOOLS        — Find tools by use case          │
│  2. COMPOSIO_MANAGE_CONNECTIONS  — Handle OAuth/auth flows          │
│  3. COMPOSIO_GET_TOOL_SCHEMAS    — Load full schema (if schemaRef) │
│  4. COMPOSIO_WAIT_FOR_CONNECTION — Wait for user auth completion    │
│  5. COMPOSIO_CREATE_PLAN         — Build ordered execution plan     │
│                                                                     │
│  VIA PYTHON TOOLS (execution):                                      │
│  6. composioBatchExecute  — DEFAULT: parallel bg, step ordering     │
│  7. composioExecute       — SYNC: single reads when LLM needs data │
│                                                                     │
│  Composio exposes ~12 MCP tools. We filter to 5 via allowed_tools. │
│  Execution bypasses MCP entirely — goes direct via Composio SDK.   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  WHAT'S AVAILABLE (configured via connected accounts on dashboard)  │
│                                                                     │
│  gmail, googledrive, googlesheets, googlecalendar, slack,          │
│  microsoftteams, github, notion, linear, hubspot, ...              │
│  (hundreds of tools across all connected apps)                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Runtime Flow (per user query)

```
User: "Send an email to Jay about the meeting"
  │
  ▼
LLM calls: COMPOSIO_SEARCH_TOOLS(use_case="send email",      ← ~300-500ms
            session={generate_id: true},
            known_fields="recipient: Jay")
  │
  ▼
Returns: [GMAIL_SEND_EMAIL] with schema + connection status + plan
  │
  ▼  (If schemaRef returned instead of full schema)
  │  LLM calls: COMPOSIO_GET_TOOL_SCHEMAS(slugs=["GMAIL_SEND_EMAIL"])
  │
  ▼
LLM calls: composioBatchExecute(                              ← Python tool
    tools_json='[{"tool_slug":"GMAIL_SEND_EMAIL","arguments":{...}}]'
  )
  │
  ▼
Agent speaks: "Sending that email now"                         ← No silence gap
  │                                          │
  │  (LLM free to continue)                │ AsyncToolWorker
  │                                          │ calls Composio SDK
  │                                          │ ~400-1000ms
  │                                          ▼
  │                              session.say("Email sent")
```

### Dependency-Aware Execution

```
User: "Send a Teams message and check my OneDrive files"
  │
  ▼
LLM calls: COMPOSIO_SEARCH_TOOLS(
  queries=[
    {use_case: "send teams message", known_fields: "channel: general"},
    {use_case: "list onedrive files"}
  ])
  │
  ▼
Returns: [TEAMS_SEND_MESSAGE, ONEDRIVE_LIST_FILES] — INDEPENDENT tools
  │
  ▼
LLM calls: composioBatchExecute(tools_json='[          ← Both in parallel
  {"tool_slug":"TEAMS_SEND_MESSAGE","arguments":{...}},
  {"tool_slug":"ONEDRIVE_LIST_FILES","arguments":{...}}
]')
  │
  ▼
Both execute in parallel via asyncio.gather — latency ≈ max(single), not sum
```

```
User: "Look up issue 123 and add a comment saying it's done"
  │
  ▼
LLM calls: COMPOSIO_SEARCH_TOOLS → discovers GET_ISSUE, ADD_COMMENT
  │
  ▼  LLM recognizes: ADD_COMMENT doesn't need GET_ISSUE output
  │  (issue_id=123 is already known)
  │
  ▼
LLM calls: composioBatchExecute(tools_json='[          ← Step ordering
  {"tool_slug":"GET_ISSUE","arguments":{"id":123},"step":1},
  {"tool_slug":"ADD_COMMENT","arguments":{"id":123,"text":"done"},"step":2}
]')
  │
  ▼
Step 1 runs first, step 2 waits, all in background
```

```
User: "Search candidates and email the top one"
  │
  ▼
LLM recognizes: email needs data FROM search results (name, email)
  │
  ▼
LLM calls: composioExecute(                               ← SYNC: needs data
  tool_slug="DB_SEARCH", arguments_json='{"query":"candidates"}'
)
  │
  ▼
Returns: "Found 3 candidates: Jay Connor jay@..., ..."     ← LLM sees results
  │
  ▼
LLM calls: composioBatchExecute(tools_json='[              ← Background
  {"tool_slug":"GMAIL_SEND_EMAIL","arguments":{"to":"jay@...","body":"..."}}
]')
```

### Key Insight

The `toolkits` parameter defines **what's searchable**, NOT what's loaded into context.
Whether you specify 1 toolkit or 100, the LLM context always contains only the 7 filtered tools
(5 MCP + 2 Python wrappers).

## Latency Considerations

| Step | Latency | Notes |
|------|---------|-------|
| COMPOSIO_SEARCH_TOOLS | 300-500ms | Full-text search across apps |
| COMPOSIO_GET_TOOL_SCHEMAS | 100-300ms | Only if schemaRef returned |
| COMPOSIO_CREATE_PLAN | 200-500ms | Only for complex workflows |
| composioBatchExecute | 400-1000ms | Actual API execution (background) |
| composioExecute (sync) | 400-1000ms | Blocks until result |
| **Total (simple)** | **700-1500ms** | Search + execute |
| **Total (complex)** | **1000-2500ms** | Search + schema + plan + execute |

### Mitigation: Live Narration

The agent uses **live narration** while tool discovery/execution runs.
It narrates each step as it happens:
- "Looking up that candidate now"
- "Got it now sending that over"
- "Checking your OneDrive and sending that Teams message at the same time"

Background execution via AsyncToolWorker means the agent keeps talking —
no dead air while tools run.

### Context Retention

The agent tracks all specifics mentioned in conversation (emails, names, data, results).
If the user provides an email address in one turn, the agent never re-asks for it.
The `known_fields` parameter in `COMPOSIO_SEARCH_TOOLS` carries forward known context.

## Configuration

### Environment Variables

```bash
# Composio Tool Router
COMPOSIO_API_KEY=ak_xxxxxxxxxxxxx
COMPOSIO_ROUTER_ENABLED=true
COMPOSIO_USER_ID=pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c
```

### Toolkits (defined in composio_router.py)

Two Composio meta-toolkits are passed to `composio.create()`:
- `"composio"` — provides execute + manage_connections meta-tools
- `"composio_search"` — provides the search meta-tool

These are NOT individual services. External services (gmail, drive, slack,
teams, etc.) are controlled by **connected accounts** on the Composio
dashboard. The search tool discovers tools across all connected apps.

```python
COMPOSIO_TOOLKITS = ["composio", "composio_search"]

session = composio.create(
    user_id=user_id,
    toolkits=COMPOSIO_TOOLKITS,
)
```

### MCP Integration (agent.py)

The session's MCP endpoint is passed to LiveKit's MCPServerHTTP:

```python
from .tools.composio_router import get_composio_mcp_url, COMPOSIO_ALLOWED_TOOLS

# COMPOSIO_ALLOWED_TOOLS = 5 meta-tools (of ~12 available)
mcp_servers.append(mcp.MCPServerHTTP(
    url=composio_url,
    headers=composio_headers,
    timeout=15,
    allowed_tools=COMPOSIO_ALLOWED_TOOLS,
))
```

## Production Viability

| Factor | Assessment |
|--------|-----------|
| Latency | 700-1500ms added per tool call — masked by background execution + narration |
| Context efficiency | 7 tools (5 MCP + 2 Python) vs 200-400 schemas — massive improvement |
| Dependency safety | Step-based ordering prevents incorrect concurrent execution |
| Scalability | Add connected apps on Composio dashboard, no code/context changes |
| Error rate | Composio SDK GA (Dec 2025), stable |
| Rate limits | 20K-100K req/10min depending on plan |

## Relationship to Existing n8n Tools

The Composio Tool Router runs **alongside** the existing n8n webhook tools:

```
Agent Tools:
├── n8n webhook tools (ASYNC_TOOLS)       ← Direct, low-latency (~200ms)
│   ├── sendEmail (via /execute-gmail)
│   ├── searchDrive (via /drive-document-repo)
│   ├── queryDatabase (via /database-query)
│   ├── knowledgeBase (via /vector-store)
│   ├── checkContext (via /agent-context-access)
│   ├── addContact, getContact, searchContacts
│   ├── recall, memoryStatus, recallDrive
│   └── ...
│
├── Composio Python Tools (execution)     ← Background via AsyncToolWorker
│   ├── composioBatchExecute (DEFAULT)    ← Parallel, step-ordered, background
│   └── composioExecute (SYNC READS)     ← Single tool, LLM needs data
│
└── Composio MCP (discovery + planning)   ← 5 filtered meta-tools
    ├── COMPOSIO_SEARCH_TOOLS             ← Discover tools by use case
    ├── COMPOSIO_MANAGE_CONNECTIONS       ← Handle OAuth/auth
    ├── COMPOSIO_GET_TOOL_SCHEMAS         ← Load full schema (schemaRef)
    ├── COMPOSIO_WAIT_FOR_CONNECTION      ← Wait for auth completion
    └── COMPOSIO_CREATE_PLAN              ← Ordered execution plan
        └── Searches across: gmail, slack, teams, drive, sheets, github, ...
```

The n8n tools are the **fast path** (direct webhook, ~200ms). Composio is the **extended toolkit** for anything not covered by n8n tools.

## System Prompt Requirements

The LLM **must** be explicitly instructed on the Composio workflow:

1. **Search first**: Always call `COMPOSIO_SEARCH_TOOLS` before executing
2. **Load schemas**: If search returns `schemaRef`, call `COMPOSIO_GET_TOOL_SCHEMAS`
3. **Plan complex workflows**: For 3+ tools, call `COMPOSIO_CREATE_PLAN`
4. **Fill arguments**: Use the discovered schema — never leave arguments empty
5. **Batch independent**: Use `composioBatchExecute` for independent tools
6. **Sequence dependent**: Use `composioExecute` when next tool needs prior results
7. **Step ordering**: Use `step` field when tools must run in order but don't share data
8. **Live narration**: Narrate what's happening while background tools execute

### Dependency Decision Tree

```
Does tool B need specific output DATA from tool A?
  ├── YES → Sequential: composioExecute(A) → composioBatchExecute([B])
  │         LLM must see A's results to build B's arguments
  │
  └── NO → Does tool B need to wait for tool A to complete?
           ├── YES → Step ordering: composioBatchExecute([{A, step:1}, {B, step:2}])
           │         Both run in background, B waits for A
           │
           └── NO → Parallel: composioBatchExecute([A, B])
                    Both run at the same time, fastest execution
```

### Root Cause History

**Empty Arguments Bug (2026-02-19):**
LLM called `COMPOSIO_MULTI_EXECUTE_TOOL` with `arguments: {}` because system prompt
referenced a fictional tool and had no search-first workflow instructions.
**Fix**: Replaced with explicit discover → schema → execute workflow.

**Schema Loading Gap (2026-02-19):**
Search sometimes returns `schemaRef` instead of full `input_schema`. Without
`COMPOSIO_GET_TOOL_SCHEMAS`, the LLM can't fill in arguments correctly.
**Fix**: Added `COMPOSIO_GET_TOOL_SCHEMAS` to MCP allowed tools + system prompt step 1b.

## Files

| File | Purpose |
|------|---------|
| `src/tools/composio_router.py` | MCP session + SDK execution + batch parallel |
| `src/tools/async_wrappers.py` | composioBatchExecute + composioExecute Python tools |
| `src/config.py` | Composio env var bindings |
| `src/agent.py` | Wires MCP session to LiveKit Agent + system prompt |
| `.env.example` | Environment variable documentation |
| `requirements.txt` | composio>=0.11.0 dependency |
| `docs/COMPOSIO-TOOL-ROUTER-APPROACH.md` | This file |
