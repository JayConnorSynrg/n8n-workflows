# LiveKit Voice Agent Architecture

## System Overview

This document explains how tool calls operate with the LiveKit + n8n architecture.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE VOICE AGENT ARCHITECTURE                            │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  USER (Voice)                                                                     │
│       │                                                                           │
│       │  WebRTC Audio                                                             │
│       ▼                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                    LIVEKIT CLOUD                                          │    │
│  │                    wss://synrg-voice-agent-gqv10vbf.livekit.cloud         │    │
│  │                                                                           │    │
│  │  • WebRTC transport (sub-100ms latency)                                   │    │
│  │  • Room management                                                        │    │
│  │  • Audio streaming                                                        │    │
│  └───────────────────────────┬──────────────────────────────────────────────┘    │
│                              │                                                    │
│                              │  LiveKit Agent Protocol                            │
│                              ▼                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                    LIVEKIT VOICE AGENT (Railway)                          │    │
│  │                    python -m src.agent start                              │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                           │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │    │
│  │  │ Silero VAD  │→ │Deepgram STT │→ │  Groq LLM   │→ │Cartesia TTS │      │    │
│  │  │   ~20ms     │  │  ~150ms     │  │  ~200ms     │  │  ~80ms      │      │    │
│  │  └─────────────┘  └─────────────┘  └──────┬──────┘  └─────────────┘      │    │
│  │                                           │                               │    │
│  │                                           │ Tool Calls                    │    │
│  │                                           ▼                               │    │
│  │  ┌──────────────────────────────────────────────────────────────────┐    │    │
│  │  │                    FUNCTION TOOLS                                 │    │    │
│  │  │  send_email_tool ──────────────────────────────────────┐         │    │    │
│  │  │  query_database_tool ────────────────────────────┐     │         │    │    │
│  │  └──────────────────────────────────────────────────│─────│─────────┘    │    │
│  │                                                     │     │               │    │
│  └─────────────────────────────────────────────────────│─────│──────────────┘    │
│                                                        │     │                    │
│                                                        │     │  HTTP POST         │
│                                                        ▼     ▼                    │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │                    N8N CLOUD                                              │    │
│  │                    https://jayconnorexe.app.n8n.cloud                     │    │
│  ├──────────────────────────────────────────────────────────────────────────┤    │
│  │                                                                           │    │
│  │  POST /webhook/execute-gmail ──────→ Voice Tool: Send Gmail              │    │
│  │  POST /webhook/query-vector-db ────→ Voice Tool: Query Vector DB         │    │
│  │  POST /webhook/callback-noop ──────→ Callback No-Op (gate handler)       │    │
│  │                                                                           │    │
│  │  Each workflow implements:                                                │    │
│  │  • Gated execution with progress callbacks                                │    │
│  │  • PostgreSQL logging (tool_calls table)                                  │    │
│  │  • Voice-optimized response formatting                                    │    │
│  │                                                                           │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Voice Pipeline Data Flow

### Latency Budget (Target: <500ms end-to-end)

| Stage | Component | Target Latency | Actual |
|-------|-----------|----------------|--------|
| 1 | Silero VAD | <30ms | ~20ms |
| 2 | Deepgram STT (Nova-3) | <200ms | ~150ms |
| 3 | Groq LLM (LLaMA 3.1 8B) | <250ms | ~200ms |
| 4 | Cartesia TTS (Sonic-3) | <100ms | ~80ms |
| **Total** | **End-to-end** | **<500ms** | **~450ms** |

### Pipeline Sequence

```
User Speech → [VAD detects speech end]
           → [STT transcribes audio to text]
           → [LLM processes text + decides on tool call]
           → [If tool call needed: execute via n8n webhook]
           → [LLM generates response with tool result]
           → [TTS synthesizes speech]
           → Agent Speech
```

---

## Tool Call Architecture

### How Tool Calls Work

1. **LLM Function Detection**: The Groq LLM (LLaMA 3.1 8B) is configured with function definitions for available tools. When a user request matches a tool's purpose, the LLM generates a function call.

2. **Pre-Confirmation**: The system prompt instructs the agent to ALWAYS confirm with the user before executing tools:
   ```
   Agent: "I'll send an email to john@example.com about the meeting. Is that correct?"
   User: "Yes, send it"
   Agent: [Now executes tool]
   ```

3. **Tool Execution**: The LiveKit agent's `@llm.function_tool` decorator defines async functions that make HTTP POST requests to n8n webhooks.

4. **n8n Workflow Processing**: Each n8n workflow implements:
   - Parameter validation
   - PostgreSQL logging
   - Gated execution with progress callbacks
   - Voice-optimized response generation

5. **Response Handling**: The tool returns a string response that the LLM uses to generate a natural voice announcement.

### Tool Definitions

#### send_email Tool
```python
@llm.function_tool(
    name="send_email",
    description="Send an email to a recipient. ALWAYS confirm first."
)
async def send_email_tool(to: str, subject: str, body: str) -> str:
    # POST to /webhook/execute-gmail
    # Returns voice_response like "Email sent to X successfully"
```

#### query_database Tool
```python
@llm.function_tool(
    name="query_database",
    description="Search the knowledge base for information."
)
async def query_database_tool(query: str) -> str:
    # POST to /webhook/query-vector-db
    # Returns formatted search results for voice output
```

---

## N8N Workflow Architecture

### Gated Execution Pattern

The n8n workflows implement a gated execution pattern for interruptible tool calls:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    GATED EXECUTION FLOW                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Webhook receives request                                                    │
│       ↓                                                                      │
│  Generate tool_call_id + INSERT to PostgreSQL (EXECUTING)                    │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 1: Progress callback (cancellable)                             │    │
│  │ POST callback_url: { status: "PREPARING", cancellable: true }       │    │
│  │ Wait for response: { continue: true } or { cancel: true }           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 2: Final confirmation checkpoint                               │    │
│  │ POST callback_url: { status: "READY_TO_SEND" }                      │    │
│  │ Wait for response: { continue: true } or { cancel: true }           │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  Execute actual tool (Gmail send / Vector query)                             │
│       ↓                                                                      │
│  UPDATE PostgreSQL (COMPLETED) + voice_response                              │
│       ↓                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ GATE 3: Completion callback                                         │    │
│  │ POST callback_url: { status: "COMPLETED", voice_response }          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       ↓                                                                      │
│  Respond to webhook with final result                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Callback No-Op Workflow

For the initial LiveKit deployment, a simple "Callback No-Op" workflow handles gate callbacks by always returning `{ continue: true }`. This allows the gated workflows to proceed without a full callback server implementation.

**Workflow ID**: `Y6CuLuSu87qKQzK1`
**Path**: `/webhook/callback-noop`

---

## Deployment Architecture

### Railway Deployment

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RAILWAY DEPLOYMENT                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Docker Container (python:3.11-slim)                                         │
│       │                                                                      │
│       │  Entry: python -m src.agent start                                    │
│       │                                                                      │
│       ├── src/agent.py (main entry point)                                    │
│       ├── src/config.py (environment validation)                             │
│       ├── src/plugins/groq_llm.py (LLM integration)                          │
│       ├── src/tools/email_tool.py (n8n webhook)                              │
│       └── src/tools/database_tool.py (n8n webhook)                           │
│                                                                              │
│  Environment Variables:                                                      │
│       LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET                       │
│       DEEPGRAM_API_KEY, DEEPGRAM_MODEL                                       │
│       GROQ_API_KEY, GROQ_MODEL                                               │
│       CARTESIA_API_KEY, CARTESIA_VOICE                                       │
│       N8N_WEBHOOK_BASE_URL                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### LiveKit Agent Worker

The agent runs as a LiveKit Worker that:
1. Connects to LiveKit Cloud via WebSocket
2. Registers as available for room dispatch
3. Joins rooms when users connect
4. Processes audio in real-time through the voice pipeline

---

## Database Schema

### PostgreSQL: tool_calls table

```sql
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
```

---

## Quick Start

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (or use .env file)
export LIVEKIT_URL=wss://synrg-voice-agent-gqv10vbf.livekit.cloud
# ... (see .env.example)

# Run tests
python tests/test_pipeline.py

# Start agent
python -m src.agent start
```

### Railway Deployment

```bash
# Login to Railway
railway login

# Link to project
railway link

# Deploy
./scripts/deploy.sh
```

---

## Active Workflows

| Workflow | ID | Purpose |
|----------|----|---------|
| Voice Tool: Send Gmail | `kBuTRrXTJF1EEBEs` | Send emails via Gmail API |
| Voice Tool: Query Vector DB | `uuf3Qaba5O8YsKaI` | Search knowledge base |
| Callback No-Op | `Y6CuLuSu87qKQzK1` | Handle gate callbacks |

---

## Cost Estimate

~$0.012/min voice (65% cheaper than OpenAI Realtime API)

| Component | Cost per minute |
|-----------|----------------|
| Deepgram Nova-3 | $0.0044 |
| Groq LLaMA 3.1 | $0.0002 |
| Cartesia Sonic-3 | $0.0067 |
| LiveKit Cloud | Free tier |
| **Total** | **~$0.012** |

---

## Future Enhancements

1. **Full callback server**: Implement proper callback handling in Railway for real-time gate control
2. **Session context**: Use session_context table for cross-tool data sharing
3. **Multiple voices**: Support for different Cartesia voices per context
4. **Observability**: OpenTelemetry integration for latency tracking
