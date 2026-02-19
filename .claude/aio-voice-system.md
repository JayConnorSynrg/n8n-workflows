# AIO Voice System - Full Architecture Reference

**On-demand document.** Loaded when working on AIO Voice System components.
For quick reference, see the AIO section in `.claude/CLAUDE.md`.

---

## Service Architecture

| Service | Location | Purpose | Key Files |
|---------|----------|---------|-----------|
| **Client (Web UI)** | `voice-agent-poc/client-v2/` | React app with LiveKit connection | `src/hooks/useLiveKitAgent.ts`, `src/lib/store.ts` |
| **LiveKit Agent** | `voice-agent-poc/livekit-voice-agent/` | Python voice agent | `src/agent.py`, `src/tools/` |
| **Async Worker** | (in agent) | Background tool execution | `src/utils/async_tool_worker.py` |
| **Database** | PostgreSQL on Railway | Tool call logging, session context | `database/schema.sql` |
| **n8n Workflows** | `jayconnorexe.app.n8n.cloud` | Tool backends (Drive, Email, DB) | MCP tools |
| **Recall.ai** | External | Meeting bot audio capture | - |
| **LLM** | Cerebras (see MEMORY.md for current models) | Function calling + reasoning | - |
| **STT** | Deepgram `nova-3` | Speech-to-text | - |
| **TTS** | Cartesia `sonic-3` | Text-to-speech | - |

## Data Flow Architecture

```
CLIENT (React)
  useLiveKitAgent.ts -> LiveKit Room -> Data Channel messages
  Message types: tool.call, tool.executing, tool.completed, tool.error
        |  ^
        |  | LiveKit WebRTC / Data Channel
        v  |
LIVEKIT AGENT (Python)
  agent.py -> LLM (Cerebras) -> Tool calls -> async_tool_worker.py
  Publishes results to data channel topic: "tool_result"
        |
        | HTTP webhooks
        v
N8N WORKFLOWS
  /execute-gmail, /drive-document-repo, /database-query, etc.
  Logs to PostgreSQL tool_calls table, returns voice_response for TTS
        |
        v
POSTGRESQL DATABASE
  Tables: tool_calls (gated execution), session_context, audit_trail
  tool_calls.status: EXECUTING -> COMPLETED/FAILED/CANCELLED
  tool_calls.voice_response: TTS text for agent announcement
```

## Key Database Schema (tool_calls)

```sql
CREATE TABLE tool_calls (
    tool_call_id VARCHAR(100) UNIQUE NOT NULL,  -- tc_xxx or lk_xxx format
    session_id VARCHAR(100) NOT NULL,
    function_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'EXECUTING',  -- EXECUTING, COMPLETED, FAILED, CANCELLED
    result JSONB,
    voice_response TEXT,  -- TTS text for agent to speak
    callback_url TEXT,    -- For gated execution (multi-turn)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

## AIO Ecosystem Analysis Protocol

When debugging or modifying ANY AIO Voice System component:
1. DO NOT ask the user about how components interact
2. Analyze the full ecosystem yourself by examining:
   - LiveKit agent code: `voice-agent-poc/livekit-voice-agent/`
   - Tool definitions: `voice-agent-poc/livekit-voice-agent/tools/`
   - AIO Tools Registry: `voice-agent-poc/livekit-voice-agent/docs/AIO-TOOLS-REGISTRY.md`
   - n8n workflow structures via MCP tools
3. The agent IS configured for multi-turn gate callbacks - this has been verified working

## Key Workflows

- `IamjzfFxjHviJvJg` - Google Drive Document Repository
- `gjYSN6xNjLw8qsA1` - Teams Voice Bot v3
- `ouWMjcKzbj6nrYXz` - Agent Context Access
- `kBuTRrXTJF1EEBEs` - Voice Tool: Send Gmail (multi-turn async gates)

## Known Issues

- Google Drive OAuth expiration (credential: `ylMLH2SMUpGQpUUr`)
- Gmail OAuth expiration (credential: `Wagsju9B8ofYq2Sl` - Jayconnor@synrgscaling.com)
- Cerebras model compatibility - see MEMORY.md for current production models
