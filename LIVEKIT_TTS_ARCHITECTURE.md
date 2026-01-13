# LiveKit TTS Architecture & Pattern Relationships

## Audio Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM/Agent Output                             │
│                    (Streaming Text)                             │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  Buffered Token     │  Context window: 10 chars
        │  Stream             │  Min length: 20 chars
        │                     │
        │  push_text()        │
        │  flush()            │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  Sentence Stream    │  NLTK punkt tokenizer
        │  Pacer              │  (Language-aware)
        │                     │
        │  Batching logic:    │
        │  • 1st sentence:    │
        │    immediate send   │
        │  • Subsequent:      │
        │    max 300 chars    │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  TTS Provider API   │  Cartesia, OpenAI,
        │  (synthesize)       │  ElevenLabs, etc.
        │                     │
        │  Trigger:          │
        │  remaining_audio   │
        │  <= 5.0 sec        │
        └──────────┬──────────┘
                   │
        ┌──────────┴─────────────┐
        │                        │
        ▼                        ▼
    (Raw PCM)            (Compressed: MP3)
        │                        │
        │                        ▼
        │                 ┌──────────────┐
        │                 │  Audio Stream│
        │                 │  Decoder     │
        │                 └──────┬───────┘
        │                        │
        └────────────┬───────────┘
                     │
                     ▼
        ┌──────────────────────────┐
        │  Audio Byte Stream       │  Frame size: 200ms
        │  (Frame accumulator)     │  At 24kHz: 4800 samples
        │                          │
        │  Resampling/buffering    │
        │  Emit @ frame_size_ms    │
        └──────────┬───────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │  Synthesized Audio       │  SynthesizedAudio frames
        │  Frame Emission          │  with metadata
        │                          │
        │  _emit_frame()           │
        │  Add request_id,         │
        │  segment_id, timing      │
        └──────────┬───────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │  Client Audio Output     │  Stream to WebRTC
        │  (Publication)           │  or local speaker
        └──────────────────────────┘
```

---

## Concurrency Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ SentenceStreamPacer (Main Orchestrator)                  │ │
│  │                                                          │ │
│  │  ┌────────────────────────┐  ┌──────────────────────┐  │ │
│  │  │ _recv_task()           │  │ _send_task()         │  │ │
│  │  │                        │  │                      │  │ │
│  │  │ Pull sentences from    │  │ Monitor audio        │  │ │
│  │  │ upstream stream        │  │ duration             │  │ │
│  │  │                        │  │ Dispatch to TTS      │  │ │
│  │  │ Store in buffer        │  │ when threshold       │  │ │
│  │  │ Signal wakeup event    │  │ reached              │  │ │
│  │  └────────┬───────────────┘  └──────────┬───────────┘  │ │
│  │           │                             │              │ │
│  │  (async)  │                    (async)  │              │ │
│  │           ▼                             ▼              │ │
│  │    ┌─────────────────┐        ┌────────────────┐      │ │
│  │    │ self._sentences │        │ Wakeup Event   │      │ │
│  │    │ (list buffer)   │        │ (asyncio)      │      │ │
│  │    └─────────────────┘        └────────────────┘      │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Timings:                                                      │
│  • Audio check: every 100ms                                   │
│  • Generate cycle: responsive (< 200ms)                       │
│  • Idle cycle: waits up to (remaining - threshold) seconds    │ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Buffer State Transitions

```
Initial State:
┌──────────────────────────────────┐
│ remaining_audio = 0              │
│ sentences buffer = []            │
│ first_sentence = true            │
│ generation_started = false       │
└──────────────────────────────────┘
              │
              │ Text arrives
              ▼
┌──────────────────────────────────┐
│ _sentences = ["The", "quick"]    │
│ Wakeup event triggered           │
└──────────────────────────────────┘
              │
              │ _send_task checks
              ▼
┌──────────────────────────────────┐
│ first_sentence=true              │
│ Send immediately:                │
│ "The quick" → TTS                │
│ first_sentence = false           │
└──────────────────────────────────┘
              │
              │ More text
              │ arrives (TTS still generating)
              ▼
┌──────────────────────────────────┐
│ _sentences = ["brown", "fox"]    │
│ remaining_audio = 3.2s           │
│ < 5.0s threshold?                │
│ NO - wait                        │
└──────────────────────────────────┘
              │
              │ 1 second passes
              │ TTS audio reaches us
              ▼
┌──────────────────────────────────┐
│ remaining_audio = 2.1s           │
│ < 5.0s threshold?                │
│ YES - send next batch            │
│ Send "brown fox" → TTS           │
└──────────────────────────────────┘
```

---

## Pacing Decision Tree

```
                    ┌─────────────────────┐
                    │  Text Available?    │
                    └────────┬────────────┘
                             │
                 ┌───────────┼───────────┐
                 │                       │
                 NO                      YES
                 │                       │
                 │                       ▼
                 │           ┌──────────────────────┐
                 │           │  first_sentence?     │
                 │           └──────┬─────────────┬──┘
                 │                  │             │
                 │                  YES          NO
                 │                  │             │
                 │    ┌─────────────┘             │
                 │    │ SEND                      │
                 │    │ IMMEDIATELY               ▼
                 │    │         ┌─────────────────────────┐
                 │    │         │ remaining_audio         │
                 │    │         │ <= min_remaining_audio? │
                 │    │         │ (5.0 sec default)       │
                 │    │         └──────┬─────────┬────────┘
                 │    │                │         │
                 │    │               YES       NO
                 │    │                │         │
                 │    │    ┌───────────┘         │
                 │    │    │ SEND                │ WAIT
                 │    │    │ BATCH               │ For more
                 │    │    │                     │ text or timeout
                 │    │    │                     │
                 └────┼────┴─────────────────────┴───────────
                      │
                      ▼
              ┌──────────────────────┐
              │  Aggregate text:     │
              │  up to 300 chars     │
              │  or single sentence  │
              │                      │
              │  Join with spaces    │
              │  Push to TTS         │
              └──────────────────────┘
```

---

## Data Structure: Segment Boundaries

```
┌─────────────────────────────────────────────────────┐
│ Text Segment 1: "Hello there"                       │
├─────────────────────────────────────────────────────┤
│ _StartSegment                                       │
│  ├─ Push "Hello there" → TTS                        │
│  └─ generate frame 0, 1, 2, ...                     │
├─────────────────────────────────────────────────────┤
│ SynthesizedAudio frames with metadata:              │
│  {                                                  │
│    request_id: "req-123",                           │
│    segment_id: "seg-001",                           │
│    data: b'...',  # 4800 samples                    │
│    sample_rate: 24000,                              │
│    num_channels: 1,                                 │
│    is_final: false                                  │
│  }                                                  │
├─────────────────────────────────────────────────────┤
│ _EndSegment                                         │
│  ├─ Flush remaining bytes                           │
│  ├─ Send final frame with is_final=true             │
│  └─ Reset segment_id                                │
├─────────────────────────────────────────────────────┤
│ Text Segment 2: "How are you?"                      │
│  ... (repeat for next segment)                      │
└─────────────────────────────────────────────────────┘
```

---

## Duration Calculation

```python
# Method: Track cumulative audio pushed, compare with wall time

┌────────────────────────────────────────────┐
│ Timeline:                                  │
│                                            │
│ T=0.0  ┌─────────────────────┐            │
│        │ Start TTS           │            │
│        │ 200ms of audio      │            │
│        │ audio_start_time=0  │            │
│        │ pushed_duration=200 │            │
│        └─────────────────────┘            │
│                                            │
│ T=0.1  │ Check remaining                  │
│        │ audio_duration=200ms             │
│        │ remaining=200-100=100ms          │
│        │ Start checking every 100ms       │
│                                            │
│ T=0.2  │ Second TTS batch arrives         │
│        │ audio_duration=400ms             │
│        │ remaining=400-200=200ms          │
│        │ generation_started=true          │
│                                            │
│ T=0.6  │ TTS finishes generating          │
│        │ audio_duration=5000ms (5 sec)    │
│        │ remaining=5000-600=4400ms        │
│        │ > 5000ms threshold, don't send   │
│                                            │
│ T=3.0  │ Audio consumed by playback       │
│        │ remaining=5000-3000=2000ms       │
│        │ < 5000ms threshold               │
│        │ TRIGGER: send next batch         │
│        └─────────────────────┘            │
└────────────────────────────────────────────┘

Remaining Audio Formula:
remaining = (audio_start_time + pushed_duration - current_time) * 1000
          = (0 + 5000 - 3000) ms
          = 2000 ms
```

---

## Performance Characteristics Graph

```
Text Input Volume (chars)
      │
 1000 │                                    ┌─── Max text length (300 chars)
      │                                   /│
  300 │                          ┌────────┤│
      │                         /│        ││
  150 │              ┌─────────┤ │        ││
      │             /│         ││        ││
    0 │────────────┤ │─────────┴┴────────┴┴─────► Time (seconds)
      │            ││
      │            │└─ Aggressive config (150 char batch)
      │            │
      │            └─ Default config (300 char batch)
      │
      │
Remaining Audio Threshold
      │
 10s  │ ┌──────┐
      │ │      │ Conservative (10s threshold)
  5s  │ │      │ ┌──────┐
      │ │      │ │      │ Default (5s threshold)
  3s  │ │      │ │      │ ┌──────┐
      │ │      │ │      │ │      │ Aggressive (3s threshold)
  0s  └─┴──────┴─┴──────┴─┴──────┴─────────────►
      0  1  2  3  4  5  6  7  8  9 10  Time (seconds)

      Dispatch happens when remaining_audio ≤ threshold
      (Except first sentence which triggers immediately)
```

---

## Language Support Matrix (NLTK)

```
Fully Supported (Punkt Tokenizer):
┌──────────────────────────────────────────┐
│ English, French, German, Spanish,        │
│ Portuguese, Dutch, Italian, Danish,      │
│ Swedish, Finnish, Polish, Czech,         │
│ Slovak, Turkish, Hungarian, Romanian,    │
│ Bulgarian, Russian, Estonian, Slovene    │
│ ... 50+ languages total                  │
└──────────────────────────────────────────┘

Partially Supported (Whitespace fallback):
┌──────────────────────────────────────────┐
│ Languages with spaces between words but  │
│ complex sentence boundaries               │
│ May produce suboptimal chunking           │
└──────────────────────────────────────────┘

Not Supported:
┌──────────────────────────────────────────┐
│ • Chinese (mandarin, cantonese)          │
│ • Japanese                               │
│ • Korean                                 │
│ • Thai                                   │
│ ... (languages without space-separated   │
│      words)                              │
└──────────────────────────────────────────┘
```

---

## Resource Usage Estimates

```
Per-Stream Resources:
┌─────────────────────────────────┐
│ Memory (runtime):               │
│ • Sentence buffer: ~50-100 KB   │
│ • Audio frames: ~200 KB         │
│ • Streaming state: ~10 KB       │
│ ────────────────────────────    │
│ Total per stream: ~260 KB       │
│                                 │
│ CPU (per stream):               │
│ • Tokenization: <1%             │
│ • Pacing logic: <1%             │
│ • Frame emission: <1%           │
│ • I/O: varies by provider       │
│ ────────────────────────────    │
│ Total CPU: negligible (< 5%)    │
│                                 │
│ Bandwidth:                      │
│ • Audio @ 24kHz mono: ~48 kbps  │
│ • Text (TTS input): ~1-2 kbps   │
│ ────────────────────────────    │
│ Total: ~50 kbps per stream      │
└─────────────────────────────────┘
```

---

## Integration Checklist

- [ ] Implement or integrate NLTK punkt tokenizer
- [ ] Implement BufferedTokenStream with min_token_len constraint
- [ ] Create SentenceStreamPacer with configurable thresholds
- [ ] Implement AudioByteStream frame chunking (200ms default)
- [ ] Create AudioEmitter with segment boundary signals
- [ ] Integrate TTS provider (Cartesia, OpenAI, etc.)
- [ ] Implement duration tracking without speed adjustment
- [ ] Add configuration presets (aggressive/balanced/conservative)
- [ ] Test with multiple languages (English, French, German minimum)
- [ ] Validate frame synchronization with WebRTC playback
- [ ] Implement error handling for stream interruptions
- [ ] Monitor latency: first frame < 200ms target
