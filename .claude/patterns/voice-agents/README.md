# Voice Agents Pattern Library

**Created**: 2026-01-17
**Source**: Voice Agent POC for Recall.ai Output Media Integration
**Status**: PRODUCTION-VALIDATED

---

## Overview

This pattern library documents the successful integration of a LiveKit voice agent with Recall.ai Output Media for enterprise meeting voice interactions. The patterns were derived from extensive debugging and represent production-ready configurations.

---

## Architecture Summary

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Recall.ai Bot  │────>│  LiveKit Room   │<────│  Voice Agent    │
│  (Meeting Audio)│     │  (Real-time)    │     │  (Python)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  VOICE AGENT PIPELINE                                           │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   │
│  │ Silero │─>│Deepgram│─>│  Groq  │─>│Cartesia│─>│ Audio  │   │
│  │  VAD   │  │  STT   │  │  LLM   │  │  TTS   │  │ Output │   │
│  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘   │
│  (16kHz)      (nova-3)   (llama-3.1)  (sonic-3)   (24kHz)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Pattern Index

| Pattern ID | Title | Severity | Summary |
|------------|-------|----------|---------|
| `livekit-agents-1.3.x` | LiveKit Agents 1.3.x Integration | CRITICAL | Official plugin usage, API contracts |
| `vad-tuning-recall-ai` | VAD Tuning for Recall.ai | HIGH | Threshold optimization for processed audio |
| `participant-detection` | Participant Detection | HIGH | Client detection, audio subscription |
| `groq-llm-plugin` | Groq LLM Plugin | CRITICAL | Official plugin, avoid custom implementations |

---

## Quick Reference

### Must-Use Official Plugins

```python
from livekit.plugins import silero, deepgram, cartesia, groq

# Initialize with official plugins
vad = silero.VAD.load(activation_threshold=0.05, ...)
stt = deepgram.STT(model="nova-3", ...)
llm_instance = groq.LLM(model="llama-3.1-8b-instant", ...)
tts = cartesia.TTS(model="sonic-3", ...)
```

### Critical VAD Settings

```python
silero.VAD.load(
    activation_threshold=0.05,     # LOW for processed audio
    min_speech_duration=0.05,      # Fast speech detection
    min_silence_duration=0.55,     # Natural turn-taking
    sample_rate=16000,             # MUST be 16kHz for Silero
    force_cpu=True,                # Consistent latency
)
```

### Event Handler Pattern

```python
@session.on("user_input_transcribed")
def on_user_input_transcribed(ev):  # Sync def, NOT async
    text = ev.transcript
    asyncio.create_task(handle_async_work())  # Dispatch async
```

---

## Anti-Memory Patterns

These patterns MUST be read fresh before implementation:

1. **`livekit-agents-1.3.x`** - LLM API contracts change frequently
2. **`groq-llm-plugin`** - Custom implementations always fail

---

## Key Lessons Learned

### 1. Official Plugins Over Custom Code

Custom LLM implementations fail because:
- Abstract method `_run` required in `llm.LLMStream`
- `chat()` must be sync (not async def)
- Parameters change between minor versions

### 2. VAD Threshold Critical for Processed Audio

Default Silero threshold (0.5) fails with Recall.ai audio.
Working threshold: **0.05** (10x more sensitive)

### 3. Participant Detection Requires Audio Track Verification

Don't just detect participant connection. Verify:
- Audio track is published
- Audio track is subscribed
- Correct participant is linked to session

### 4. Sample Rate Alignment

```
VAD Input:  16kHz (Silero requirement)
STT Input:  16kHz (from VAD)
TTS Output: 24kHz (Cartesia default)
```

---

## Production Checklist

Before deploying a voice agent:

- [ ] Using official `livekit-plugins-*` packages
- [ ] VAD threshold tuned for audio source
- [ ] Audio sample rates aligned (16kHz in, 24kHz out)
- [ ] Event handlers are synchronous (dispatch async via create_task)
- [ ] Participant detection waits for audio track
- [ ] Session linked to correct participant identity
- [ ] Keep-alive loop prevents agent disconnect
- [ ] Audio level monitoring enabled
- [ ] Graceful error handling for LLM failures

---

## Commit History Reference

Key fixes that led to working implementation:

```
d1e2a93 fix(llm): switch to official livekit-plugins-groq package
1af6283 fix(groq_llm): make chat() synchronous for LiveKit Agents 1.3.x
3f09f10 fix(agent): lower VAD threshold to 0.05 for Recall.ai audio
0eb432c fix(audio-input): comprehensive audio subscription verification
48c7878 fix(audio-input): wait for client AUDIO TRACK before session
```

---

## Related Projects

- **Voice Agent POC**: `voice-agent-poc/livekit-voice-agent/`
- **Client V2**: `voice-agent-poc/client-v2/` (React + LiveKit SDK)
- **N8N Workflows**: `voice-agent-poc/n8n-workflows/` (Tool execution)

---

## Evolution Notes

This pattern library was created from a debugging session that resolved multiple integration issues. The patterns represent hard-won knowledge that should prevent future engineers from repeating the same mistakes.

When LiveKit Agents releases new major versions, these patterns should be re-validated.
