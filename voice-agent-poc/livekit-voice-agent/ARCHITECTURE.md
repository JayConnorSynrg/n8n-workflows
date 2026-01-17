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

## Provider Alternation Guide

This section documents how to swap STT, LLM, and TTS providers. The modular architecture allows easy provider substitution.

### STT (Speech-to-Text) Providers

**Current: Deepgram Nova-3** (~150ms latency, $0.0044/min)

| Provider | Plugin | Latency | Cost/min | Notes |
|----------|--------|---------|----------|-------|
| Deepgram Nova-3 | `livekit.plugins.deepgram` | ~150ms | $0.0044 | Best quality, interim results |
| Deepgram Nova-2 | `livekit.plugins.deepgram` | ~120ms | $0.0036 | Faster, slightly lower quality |
| AssemblyAI | `livekit.plugins.assemblyai` | ~200ms | $0.006 | Good accuracy, no streaming |
| Google Cloud STT | `livekit.plugins.google` | ~180ms | $0.006 | Good multilingual support |
| Azure Speech | `livekit.plugins.azure` | ~150ms | $0.01 | Enterprise compliance |
| Whisper (local) | `livekit.plugins.openai` | ~500ms+ | Free | Offline, higher latency |

**To switch STT:**

```python
# In src/agent.py - replace the STT initialization

# Option 1: Deepgram Nova-2 (faster, cheaper)
from livekit.plugins import deepgram
stt = deepgram.STT(model="nova-2", language="en")

# Option 2: AssemblyAI
from livekit.plugins import assemblyai
stt = assemblyai.STT(api_key=settings.assemblyai_api_key)

# Option 3: Google Cloud STT
from livekit.plugins import google
stt = google.STT(credentials_info=settings.google_credentials)

# Option 4: Azure Speech
from livekit.plugins import azure
stt = azure.STT(
    speech_key=settings.azure_speech_key,
    speech_region=settings.azure_speech_region
)
```

**Environment variables to add:**
```bash
# For AssemblyAI
ASSEMBLYAI_API_KEY=xxxxxxxx

# For Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# For Azure
AZURE_SPEECH_KEY=xxxxxxxx
AZURE_SPEECH_REGION=eastus
```

---

### LLM (Language Model) Providers

**Current: Groq LLaMA 3.1 8B** (~200ms latency, $0.0002/min)

| Provider | Plugin | Latency | Cost/1K tokens | Notes |
|----------|--------|---------|----------------|-------|
| Groq LLaMA 3.1 8B | `livekit.plugins.groq` | ~200ms | $0.00005 | Fastest inference |
| Groq LLaMA 3.1 70B | `livekit.plugins.groq` | ~350ms | $0.0006 | Better quality |
| OpenAI GPT-4o-mini | `livekit.plugins.openai` | ~400ms | $0.0015 | Good balance |
| OpenAI GPT-4o | `livekit.plugins.openai` | ~600ms | $0.03 | Best quality |
| Anthropic Claude 3 Haiku | `livekit.plugins.anthropic` | ~350ms | $0.0025 | Fast, safe |
| Anthropic Claude 3.5 Sonnet | `livekit.plugins.anthropic` | ~500ms | $0.015 | Better reasoning |
| Together AI | `livekit.plugins.together` | ~250ms | Varies | Open models |

**To switch LLM:**

```python
# In src/agent.py - replace the LLM initialization

# Option 1: OpenAI GPT-4o-mini (good balance)
from livekit.plugins import openai
llm_instance = openai.LLM(
    model="gpt-4o-mini",
    api_key=settings.openai_api_key,
    temperature=0.7
)

# Option 2: OpenAI GPT-4o (highest quality)
from livekit.plugins import openai
llm_instance = openai.LLM(
    model="gpt-4o",
    api_key=settings.openai_api_key,
    temperature=0.7
)

# Option 3: Anthropic Claude 3 Haiku (fast, safe)
from livekit.plugins import anthropic
llm_instance = anthropic.LLM(
    model="claude-3-haiku-20240307",
    api_key=settings.anthropic_api_key
)

# Option 4: Anthropic Claude 3.5 Sonnet (better reasoning)
from livekit.plugins import anthropic
llm_instance = anthropic.LLM(
    model="claude-3-5-sonnet-20241022",
    api_key=settings.anthropic_api_key
)

# Option 5: Groq LLaMA 3.1 70B (higher quality Groq)
from livekit.plugins import groq
llm_instance = groq.LLM(
    model="llama-3.1-70b-versatile",
    api_key=settings.groq_api_key
)
```

**Environment variables to add:**
```bash
# For OpenAI
OPENAI_API_KEY=sk-xxxxxxxx

# For Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxx

# For Together AI
TOGETHER_API_KEY=xxxxxxxx
```

---

### TTS (Text-to-Speech) Providers

**Current: Cartesia Sonic-3** (~80ms latency, $0.0067/min)

| Provider | Plugin | Latency | Cost/1K chars | Notes |
|----------|--------|---------|---------------|-------|
| Cartesia Sonic-3 | `livekit.plugins.cartesia` | ~80ms | $0.01 | Lowest latency, natural |
| Cartesia Sonic-2 | `livekit.plugins.cartesia` | ~100ms | $0.007 | Good quality, cheaper |
| ElevenLabs | `livekit.plugins.elevenlabs` | ~150ms | $0.018 | Most natural, expensive |
| OpenAI TTS | `livekit.plugins.openai` | ~200ms | $0.015 | HD quality option |
| Azure TTS | `livekit.plugins.azure` | ~120ms | $0.016 | Enterprise, many voices |
| Google Cloud TTS | `livekit.plugins.google` | ~150ms | $0.016 | WaveNet voices |

**To switch TTS:**

```python
# In src/agent.py - replace the TTS initialization

# Option 1: ElevenLabs (most natural, higher latency)
from livekit.plugins import elevenlabs
tts = elevenlabs.TTS(
    api_key=settings.elevenlabs_api_key,
    voice="Rachel",  # or voice ID
    model_id="eleven_turbo_v2"  # faster model
)

# Option 2: OpenAI TTS
from livekit.plugins import openai
tts = openai.TTS(
    api_key=settings.openai_api_key,
    voice="nova",  # alloy, echo, fable, onyx, nova, shimmer
    model="tts-1"  # or tts-1-hd for higher quality
)

# Option 3: Azure TTS
from livekit.plugins import azure
tts = azure.TTS(
    speech_key=settings.azure_speech_key,
    speech_region=settings.azure_speech_region,
    voice="en-US-JennyNeural"
)

# Option 4: Google Cloud TTS
from livekit.plugins import google
tts = google.TTS(
    credentials_info=settings.google_credentials,
    voice_name="en-US-Neural2-C"
)
```

**Environment variables to add:**
```bash
# For ElevenLabs
ELEVENLABS_API_KEY=xxxxxxxx

# For OpenAI TTS
OPENAI_API_KEY=sk-xxxxxxxx  # Same key as LLM

# For Azure TTS
AZURE_SPEECH_KEY=xxxxxxxx
AZURE_SPEECH_REGION=eastus

# For Google Cloud TTS
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

---

### Recommended Provider Combinations

| Use Case | STT | LLM | TTS | Total Latency | Cost/min |
|----------|-----|-----|-----|---------------|----------|
| **Budget (Current)** | Deepgram Nova-3 | Groq LLaMA 3.1 8B | Cartesia Sonic-3 | ~450ms | ~$0.012 |
| **Quality Focused** | Deepgram Nova-3 | GPT-4o | ElevenLabs | ~950ms | ~$0.05 |
| **Enterprise** | Azure Speech | Claude 3.5 Sonnet | Azure TTS | ~770ms | ~$0.04 |
| **Ultra Low Latency** | Deepgram Nova-2 | Groq LLaMA 3.1 8B | Cartesia Sonic-3 | ~400ms | ~$0.011 |
| **Offline/Private** | Whisper (local) | Ollama (local) | Piper (local) | ~1500ms | Free |

---

### Sample Rate Considerations

When switching providers, ensure sample rates are compatible:

| Component | Expected Sample Rate | Notes |
|-----------|---------------------|-------|
| VAD (Silero) | 16000 Hz | Required - no flexibility |
| STT Input | 16000 Hz | Most STT providers accept this |
| TTS Output | 24000 Hz (default) | Some providers output 22050 or 44100 |

**If TTS outputs different sample rate:**
```python
# LiveKit handles resampling automatically, but you can specify:
tts = cartesia.TTS(
    model="sonic-3",
    voice=settings.cartesia_voice,
    sample_rate=24000  # Explicitly set to 24kHz
)

# For room output (matches TTS):
room_options=room_io.RoomOptions(
    audio_output=room_io.AudioOutputOptions(
        sample_rate=24000,  # Match TTS output
        num_channels=1,
    ),
)
```

---

## Future Enhancements

1. **Full callback server**: Implement proper callback handling in Railway for real-time gate control
2. **Session context**: Use session_context table for cross-tool data sharing
3. **Multiple voices**: Support for different Cartesia voices per context
4. **Observability**: OpenTelemetry integration for latency tracking
5. **Provider fallback**: Automatic fallback to backup providers on failure
6. **A/B testing**: Compare provider quality metrics in production
