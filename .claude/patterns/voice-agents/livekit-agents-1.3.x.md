# LiveKit Agents 1.3.x Integration Patterns

**Pattern ID**: `voice-agents/livekit-agents-1.3.x`
**Category**: Voice Agent Architecture
**Severity**: CRITICAL
**Created**: 2026-01-17
**Source**: Voice Agent POC debugging session

---

## Overview

LiveKit Agents 1.3.x introduces significant API changes from earlier versions. This pattern documents the correct integration approach learned through extensive debugging.

---

## CRITICAL: Use Official Plugins, Not Custom Implementations

### Anti-Pattern: Custom LLM Implementations

**DO NOT** create custom LLM classes that inherit from `llm.LLM` and `llm.LLMStream`.

```python
# ANTI-PATTERN - DO NOT DO THIS
class GroqLLM(llm.LLM):
    def chat(self, *, chat_ctx, tools, ...):
        return GroqLLMStream(...)

class GroqLLMStream(llm.LLMStream):
    async def __aenter__(self):
        # Custom streaming implementation
        pass
```

**Why This Fails:**
1. LiveKit 1.3.x `llm.LLMStream` requires implementing `_run` abstract method
2. The `chat()` method MUST be synchronous (not `async def`)
3. Return type must be an async context manager that handles streaming internally
4. The base class API changes frequently between minor versions

### Correct Pattern: Official Plugins

```python
# CORRECT - Use official livekit-plugins-groq
from livekit.plugins import groq

llm_instance = groq.LLM(
    model="llama-3.1-8b-instant",
    api_key=settings.groq_api_key,
    temperature=0.7,
)
```

**Requirements.txt:**
```
livekit-plugins-groq>=1.0.0,<2.0.0
```

---

## LLM.chat() API Contract

### Critical Understanding

In LiveKit Agents 1.3.x, the LLM `chat()` method:
1. **MUST be synchronous** (regular `def`, not `async def`)
2. **Returns an async context manager** that handles the API call in `__aenter__`
3. **Is used as**: `async with llm.chat(...) as stream:`

### Debugging Signature

If you see this error:
```
'coroutine' object does not support the asynchronous context manager protocol
```

The `chat()` method is incorrectly defined as `async def`.

If you see this error:
```
TypeError: Can't instantiate abstract class GroqLLMStream with abstract method _run
```

You're trying to subclass `llm.LLMStream` directly - use the official plugin instead.

---

## Event Handler Pattern

### Critical: Synchronous Callbacks with Async Task Dispatch

LiveKit Agents 1.3.x requires **synchronous** event handlers. Async work must be dispatched via `asyncio.create_task()`.

```python
# CORRECT PATTERN
@session.on("user_input_transcribed")
def on_user_input_transcribed(ev):  # Regular def, not async def
    """Called when user speech is transcribed."""
    text = ev.transcript if hasattr(ev, 'transcript') else str(ev)
    logger.info(f"User said: {text}")

    # Dispatch async work via create_task
    asyncio.create_task(safe_publish_data(
        json.dumps({"type": "transcript.user", "text": text}).encode()
    ))

# ANTI-PATTERN - DO NOT DO THIS
@session.on("user_input_transcribed")
async def on_user_input_transcribed(ev):  # WRONG - async def
    await publish_data(...)  # Won't work correctly
```

---

## Session Configuration Best Practices

### Recommended Session Kwargs

```python
session_kwargs = {
    "vad": vad,                           # Pre-warmed VAD instance
    "stt": stt,
    "llm": llm_instance,                  # Official plugin instance
    "tts": tts,
    "preemptive_generation": True,        # Start LLM before turn ends
    "resume_false_interruption": True,    # Handle background noise
    "false_interruption_timeout": 1.0,    # Grace period for noise
}

# Optional: Add turn detection if available
if HAS_TURN_DETECTOR:
    try:
        session_kwargs["turn_detection"] = MultilingualModel()
    except RuntimeError:
        pass  # Graceful fallback to VAD-only
```

### RoomOptions for Audio

```python
await session.start(
    agent=agent,
    room=ctx.room,
    room_options=room_io.RoomOptions(
        audio_output=room_io.AudioOutputOptions(
            sample_rate=24000,  # TTS output rate
            num_channels=1,
        ),
        audio_input=room_io.AudioInputOptions(
            sample_rate=16000,  # VAD requires 16kHz
            num_channels=1,
        ),
        participant_identity=participant_identity,  # Link to specific participant
        participant_kinds=[
            rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD,
            rtc.ParticipantKind.PARTICIPANT_KIND_SIP,
            rtc.ParticipantKind.PARTICIPANT_KIND_INGRESS,
            rtc.ParticipantKind.PARTICIPANT_KIND_EGRESS,
        ],
    ),
)
```

---

## Prewarm Pattern

### Optimize Cold Start Latency

```python
def prewarm(proc: JobProcess):
    """Prewarm VAD model during server initialization."""
    logger.info("Prewarming VAD model...")
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.05,
        min_silence_duration=0.55,
        prefix_padding_duration=0.5,
        activation_threshold=0.05,
        sample_rate=16000,
        force_cpu=True,
    )

# In entrypoint
async def entrypoint(ctx: JobContext):
    if "vad" in ctx.proc.userdata:
        vad = ctx.proc.userdata["vad"]
    else:
        vad = silero.VAD.load(...)  # Fallback
```

---

## Dependencies Reference

### Minimal Production Requirements

```
# Core LiveKit
livekit>=1.0.0,<2.0.0
livekit-api>=1.0.0,<2.0.0
livekit-agents>=1.0.0,<2.0.0

# Plugins (use official versions)
livekit-plugins-silero>=1.0.0,<2.0.0
livekit-plugins-deepgram>=1.0.0,<2.0.0
livekit-plugins-cartesia>=1.0.0,<2.0.0
livekit-plugins-groq>=1.0.0,<2.0.0
livekit-plugins-turn-detector>=1.0.0,<2.0.0
```

---

## Commit History Reference

These commits document the debugging journey:

| Commit | Issue | Resolution |
|--------|-------|------------|
| `8d2f7e2` | Missing tool_choice parameter | Added to custom chat() |
| `85fefba` | Missing conn_options parameter | Added to custom chat() |
| `b893746` | Async context manager missing | Added __aenter__/__aexit__ |
| `1af6283` | chat() was async def | Changed to sync def |
| `d1e2a93` | Abstract method _run required | Switched to official plugin |

**Key Learning**: The official plugin handles all API complexity. Custom implementations require maintaining parity with frequently-changing internal APIs.

---

## Version Compatibility Matrix

| LiveKit Agents | Plugin Pattern | Notes |
|----------------|----------------|-------|
| 1.0.x | Basic plugins | Limited features |
| 1.2.x | Enhanced plugins | Turn detection added |
| 1.3.x | **Current** | chat() must be sync, _run abstract |

---

## Anti-Memory Flag

**This pattern requires fresh reading before implementation.**

Do not rely on memory for:
- LLM class inheritance patterns
- Event handler signatures
- Session configuration options

Always verify against latest LiveKit Agents documentation.
