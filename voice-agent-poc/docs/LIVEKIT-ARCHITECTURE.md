# LiveKit Voice Agent Architecture

## Open-Source Alternative to OpenAI Realtime API

This document describes the LiveKit Agents-based voice pipeline, an open-source alternative that maintains the same three-layer architecture while using modular, swappable components.

---

## Architecture Comparison

### OpenAI Realtime API (Original)
```
Browser ←→ WebSocket Relay ←→ OpenAI Realtime API
                                  ├─ Voice (built-in)
                                  ├─ LLM (GPT-4o)
                                  └─ TTS (built-in)
```

### LiveKit Voice Agent (Open Source)
```
Browser ←→ WebSocket Server ←→ Voice Pipeline
                                  ├─ STT (Whisper/Deepgram)
                                  ├─ LLM (GPT-4/Claude/Ollama)
                                  └─ TTS (OpenAI/ElevenLabs/Cartesia)
```

---

## Three-Layer Architecture (Preserved)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  THE THREE-LAYER ARCHITECTURE (LiveKit Version)                             │
│                                                                             │
│  LAYER 1: VOICE (Hot Path - ~200-500ms)                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐
│  │  Browser Audio ←→ Voice Agent Pipeline                                  │
│  │                                                                         │
│  │  STT: Deepgram Nova-2 (~150ms) or Whisper (~500ms)                     │
│  │  LLM: GPT-4o/Claude/Llama (~200-800ms)                                 │
│  │  TTS: OpenAI/ElevenLabs/Cartesia (~100-300ms)                          │
│  │                                                                         │
│  │  • Sentence chunking for streaming TTS (from LiveKit patterns)          │
│  │  • Stream pacing: First sentence immediate, then batch                  │
│  │  • Full conversation context maintained in Python                       │
│  └─────────────────────────────────────────────────────────────────────────┘
│                              │                                              │
│                              ▼ (tool calls with context)                    │
│  LAYER 2: TOOLS (Action Path - <500ms)                                      │
│  ┌─────────────────────────────────────────────────────────────────────────┐
│  │  n8n "Voice Agent Tools" Workflow (UNCHANGED!)                          │
│  │                                                                         │
│  │  • Same webhook interface                                               │
│  │  • Same tool definitions                                                │
│  │  • Same conversation context format                                     │
│  │  • 100% compatible with OpenAI version                                  │
│  └─────────────────────────────────────────────────────────────────────────┘
│                              │                                              │
│                              ▼ (async, non-blocking)                        │
│  LAYER 3: ANALYSIS (Background - Async)                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐
│  │  Existing Logging Agent Sub-Workflow (UNCHANGED!)                       │
│  │                                                                         │
│  │  • Same logging format                                                  │
│  │  • Same context enrichment                                              │
│  │  • Same PostgreSQL logging                                              │
│  └─────────────────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Voice Agent Pipeline (`livekit-agent/`)

```
livekit-agent/
├── server.py              # WebSocket server (entry point)
├── voice_agent.py         # VoiceAgentSession class (main pipeline)
├── config.py              # Configuration with LiveKit patterns
├── sentence_chunker.py    # Sentence splitting (from LiveKit patterns)
├── conversation_context.py # Context tracking (ported from JS)
├── n8n_integration.py     # n8n webhook integration
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container build
└── .env.example          # Environment template
```

### Provider Architecture

```python
# Abstract interfaces allow swapping providers
class STTProvider(ABC):
    async def transcribe_stream(audio_stream) -> AsyncGenerator[transcript]

class LLMProvider(ABC):
    async def generate_stream(messages, tools) -> AsyncGenerator[response]

class TTSProvider(ABC):
    async def synthesize_stream(text) -> AsyncGenerator[audio]

# Default implementations
- OpenAISTT (Whisper)
- OpenAILLM (GPT-4o with function calling)
- OpenAITTS (alloy voice)

# Alternative providers (plug-and-play)
- DeepgramSTT (faster streaming)
- AnthropicLLM (Claude)
- OllamaLLM (local models)
- ElevenLabsTTS (better quality)
- CartesiaTTS (low latency streaming)
```

---

## Key Patterns from LiveKit Agents

### 1. Sentence Chunking (`sentence_chunker.py`)

From `livekit-agents/tokenize/_basic_sent.py`:

```python
# Buffers text until minimum length reached
MIN_SENTENCE_LENGTH = 20  # Characters
MIN_CONTEXT_LENGTH = 10   # Before tokenizing

# Handles abbreviations (Mr., Dr., etc.)
# Protects decimal numbers, URLs, acronyms
# Splits on .!? with proper quote handling
```

### 2. Stream Pacing

From `livekit-agents/tts/stream_pacer.py`:

```python
# First sentence: Send immediately (minimize TTFB)
# Subsequent: Wait until 5 seconds of audio remain
# Max batch: 300 characters per TTS request
```

### 3. Audio Frame Configuration

From `livekit-agents/utils/audio.py`:

```python
TTS_FRAME_SIZE_MS = 200   # 200ms chunks for output
STT_FRAME_SIZE_MS = 100   # 100ms chunks for input
TTS_SAMPLE_RATE = 24000   # OpenAI TTS standard
STT_SAMPLE_RATE = 48000   # General input
NUM_CHANNELS = 1          # Mono
BITS_PER_SAMPLE = 16      # PCM16
```

---

## Latency Comparison

| Component | OpenAI Realtime | LiveKit Agent |
|-----------|-----------------|---------------|
| **Voice Input** | <50ms | ~150-500ms |
| **STT** | Built-in | 150ms (Deepgram) / 500ms (Whisper) |
| **LLM** | Built-in | 200-800ms (GPT-4o) |
| **TTS** | Built-in | 100-300ms |
| **First Response** | ~200ms | ~500-1000ms |
| **Streaming** | Native | Sentence-chunked |

### Trade-offs

**OpenAI Realtime API**:
- ✅ Lowest latency (<200ms end-to-end)
- ✅ Native streaming (no chunking needed)
- ✅ Single API (simpler integration)
- ❌ OpenAI lock-in
- ❌ Higher cost (audio + LLM)
- ❌ No local/offline option

**LiveKit Voice Agent**:
- ✅ Provider flexibility (swap STT/LLM/TTS)
- ✅ Cost optimization (mix providers)
- ✅ Local LLM option (Ollama)
- ✅ Open source
- ❌ Higher latency (~500-1000ms)
- ❌ More complex setup
- ❌ More components to manage

---

## Configuration

### Environment Variables

```env
# Provider Selection
STT_PROVIDER=deepgram    # openai, deepgram
LLM_PROVIDER=openai      # openai, anthropic, ollama
TTS_PROVIDER=openai      # openai, elevenlabs, cartesia

# API Keys
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...

# n8n Integration (same as OpenAI version)
N8N_TOOLS_WEBHOOK=https://your-n8n.cloud/webhook/voice-tools
N8N_LOGGING_WEBHOOK=https://your-n8n.cloud/webhook/voice-logging
```

### Provider Combinations

**Lowest Cost (Local)**:
```env
STT_PROVIDER=openai      # Whisper (included in OpenAI)
LLM_PROVIDER=ollama      # Llama 3.1 local
TTS_PROVIDER=openai      # OpenAI TTS
```

**Best Quality**:
```env
STT_PROVIDER=deepgram    # Nova-2
LLM_PROVIDER=openai      # GPT-4o
TTS_PROVIDER=elevenlabs  # Eleven Multilingual v2
```

**Fastest**:
```env
STT_PROVIDER=deepgram    # Nova-2 (150ms)
LLM_PROVIDER=openai      # GPT-4o-mini (fast)
TTS_PROVIDER=cartesia    # Sonic (streaming)
```

---

## Deployment

### Docker (Development)

```bash
# LiveKit version
docker-compose -f docker-compose.livekit.yml up

# OpenAI version (original)
docker-compose up
```

### Docker (Production with SSL)

```bash
# LiveKit version with Traefik
docker-compose -f docker-compose.livekit.yml -f docker-compose.prod.yml up
```

### Local Development

```bash
cd livekit-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python server.py
```

---

## n8n Integration

The n8n workflows work with **both** backends:

### Voice Agent Tools Workflow
- Same webhook URL
- Same request format:
  ```json
  {
    "function": "schedule_meeting",
    "args": { "title": "...", "datetime": "..." },
    "connection_id": "session_xxx",
    "context": { /* conversation history */ }
  }
  ```
- Same response format

### Logging Agent Workflow
- Same logging format
- Same context enrichment
- No changes needed

---

## Migration Guide

### From OpenAI Realtime to LiveKit

1. **Deploy LiveKit agent** alongside OpenAI relay
2. **Test with same n8n workflows** (no changes needed)
3. **Update client WebSocket URL** to point to LiveKit agent
4. **Decommission OpenAI relay** when satisfied

### Client Changes

The browser client works with both backends with minimal changes:

```javascript
// OpenAI version
const WS_URL = 'wss://relay.yourdomain.com';

// LiveKit version
const WS_URL = 'wss://livekit.yourdomain.com';

// Same audio handling, same message format
```

---

## Future Enhancements

1. **Preemptive Generation**
   - Start LLM when STT confidence > 0.8
   - Cancel if user continues speaking

2. **Connection Pooling**
   - WebSocket connection reuse for TTS providers
   - 300s session lifetime

3. **Speed Manipulation**
   - TTS speed parameter (0.6-2.0)
   - Post-processing with librosa if needed

4. **VAD Integration**
   - Silero VAD for accurate speech detection
   - Reduce false positive transcriptions

---

## Summary

The LiveKit Voice Agent provides:

1. **Same three-layer architecture** as OpenAI version
2. **100% n8n compatibility** (tools + logging)
3. **Provider flexibility** (swap STT/LLM/TTS)
4. **Open source** (no vendor lock-in)
5. **Trade-off**: Higher latency for flexibility

Choose based on your priorities:
- **Latency critical** → OpenAI Realtime API
- **Flexibility/cost** → LiveKit Voice Agent
- **Hybrid** → Run both, route based on use case
