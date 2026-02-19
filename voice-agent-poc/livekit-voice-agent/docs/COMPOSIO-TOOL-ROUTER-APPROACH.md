# Composio Tool Router — Architecture & Approach

**Created:** 2026-02-19
**Status:** Implementation in progress
**Problem:** Agent speaking function names/JSON aloud instead of natural language

---

## Problem Statement

The voice agent needs access to a plethora of Composio tools (Gmail, Google Drive, Slack, Teams, etc.) WITHOUT loading all individual tool schemas into the LLM context. Loading hundreds of schemas causes:
- Context pollution (200-400 tool schemas flood the LLM)
- Model confusion (agent speaks function names aloud instead of executing them)
- Token waste (large context = slower inference + higher cost)

## Solution: Composio Tool Router

Use Composio's Tool Router pattern to expose **3 filtered meta-tools** to the LLM instead of individual action schemas. The LLM discovers and executes specific tools on demand at runtime.

### How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│  WHAT THE LLM SEES (3 meta-tools, filtered via allowed_tools)      │
│                                                                     │
│  1. COMPOSIO_SEARCH_TOOLS       — Find relevant tools by query     │
│  2. COMPOSIO_MULTI_EXECUTE_TOOL — Execute discovered tools (50x)   │
│  3. COMPOSIO_MANAGE_CONNECTIONS — Handle OAuth/auth flows           │
│                                                                     │
│  Composio exposes ~25 meta-tools total. We filter to these 3 via   │
│  LiveKit MCPServerHTTP's allowed_tools parameter. The other 22      │
│  (planning, triggers, workbench, bash, etc.) never enter context.  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  WHAT'S AVAILABLE (configured via toolkits parameter)               │
│                                                                     │
│  gmail, googledrive, googlesheets, googlecalendar, slack,          │
│  microsoftteams, github, notion, linear, hubspot, ...              │
│  (hundreds of tools across all toolkits)                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Runtime Flow (per user query)

```
User: "Send an email to Jay about the meeting"
  │
  ▼
LLM calls: COMPOSIO_SEARCH_TOOLS("send email gmail")     ← ~300-500ms
  │
  ▼
Returns: [GMAIL_SEND_EMAIL] with schema + connection status
  │
  ▼
LLM calls: COMPOSIO_MULTI_EXECUTE_TOOL(                  ← ~400-1000ms
    tool="GMAIL_SEND_EMAIL",
    params={to: "jay@...", subject: "Meeting", body: "..."}
  )
  │
  ▼
Result: Email sent — only 1 tool schema ever entered context
```

### Key Insight

The `toolkits` parameter defines **what's searchable**, NOT what's loaded into context.
Whether you specify 1 toolkit or 100, the LLM context always contains only the 3 filtered meta-tools.

## Latency Considerations

| Step | Latency | Notes |
|------|---------|-------|
| COMPOSIO_SEARCH_TOOLS | 300-500ms | Full-text search across toolkits |
| COMPOSIO_MULTI_EXECUTE_TOOL | 400-1000ms | Actual API execution |
| **Total additional** | **700-1500ms** | Up to ~3s worst case |

### Mitigation: Filler Speech

The agent should use filler speech while tool discovery/execution runs:
- "Let me look into that..."
- "Checking on that for you..."
- "One moment while I handle that..."

This masks the latency since the user hears the agent "thinking" naturally.

## Configuration

### Environment Variables

```bash
# Composio Tool Router
COMPOSIO_API_KEY=ak_xxxxxxxxxxxxx
COMPOSIO_ROUTER_ENABLED=true
COMPOSIO_USER_ID=pg-test-pg-test-49ecc67f-362b-4475-b0cc-92804c604d1c
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

# ...
mcp_servers.append(mcp.MCPServerHTTP(
    url=composio_url,
    headers=composio_headers,
    timeout=15,
    allowed_tools=COMPOSIO_ALLOWED_TOOLS,  # Only 3 of ~25 enter context
))
```

## Production Viability

| Factor | Assessment |
|--------|-----------|
| Latency | 700-1500ms added per tool call — mitigated by filler speech |
| Context efficiency | 3 filtered meta-tools vs 200-400 schemas — massive improvement |
| Scalability | Add connected apps on Composio dashboard, no code/context changes |
| Error rate | Composio SDK GA (Dec 2025), stable |
| Known bugs | Toolkit scope leaking (GitHub #2011) — monitor |
| Rate limits | 20K-100K req/10min depending on plan |

## Relationship to Existing n8n Tools

The Composio Tool Router runs **alongside** the existing n8n webhook tools:

```
Agent Tools:
├── n8n webhook tools (ASYNC_TOOLS)     ← Direct, low-latency
│   ├── send_email (via /execute-gmail)
│   ├── search_drive (via /drive-document-repo)
│   ├── query_db (via /database-query)
│   ├── knowledge_base (via /vector-store)
│   ├── check_context (via /agent-context-access)
│   ├── add_contact (via /manage-contacts)
│   ├── recall, memory_status, recall_drive
│   └── ...
│
└── Composio Tool Router (MCP)          ← On-demand discovery
    ├── COMPOSIO_SEARCH_TOOLS
    ├── COMPOSIO_MULTI_EXECUTE_TOOL
    ├── COMPOSIO_MANAGE_CONNECTIONS
    ├── COMPOSIO_REMOTE_WORKBENCH
    └── COMPOSIO_REMOTE_BASH_TOOL
        └── Searches across: gmail, slack, teams, drive, sheets, github, ...
```

The n8n tools are the **fast path** (direct webhook, ~200ms). Composio is the **extended toolkit** for anything not covered by n8n tools.

## Files

| File | Purpose |
|------|---------|
| `src/tools/composio_router.py` | Creates MCP session with toolkits |
| `src/config.py` | Composio env var bindings |
| `src/agent.py` | Wires MCP session to LiveKit Agent |
| `.env.example` | Environment variable documentation |
| `requirements.txt` | composio>=0.11.0 dependency |
