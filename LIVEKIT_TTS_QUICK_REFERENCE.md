# LiveKit TTS Patterns - Quick Reference

## Sentence Segmentation

**Method**: NLTK punkt tokenizer (NOT regex)
```python
import nltk
sentences = nltk.tokenize.sent_tokenize(text, language="english")
# Concatenate until min_sentence_len (default: 20 chars)
```

**Supported languages**: 50+ including English, French, Spanish, German, etc.

---

## Audio Chunk Sizing

**Default frame size**: 200ms
**Calculation**: `samples_per_frame = sample_rate // 1000 * frame_size_ms`
**Example**: 24kHz sample rate → 4800 samples/frame → ~9600 bytes (stereo 16-bit)

---

## Stream Pacing Algorithm

**Trigger**: Send next batch when `remaining_audio <= min_remaining_audio`

```
remaining_audio = (audio_start_time + pushed_duration - current_time)
```

**Default thresholds**:
- `min_remaining_audio`: 5.0 seconds
- `max_text_length`: 300 characters
- `check_interval`: 0.1 seconds

**Logic**:
1. First sentence: send immediately (minimize latency)
2. Subsequent batches: accumulate until 300+ chars OR remaining audio drops below 5 sec

---

## Buffer Management

**Architecture**: Channel-based async queues
- Input: Text tokens + flush/end signals
- Processing: Tokenize → Batch → TTS → Decode → Frame → Emit
- Output: 200ms audio frames

**Segment boundaries**: `_StartSegment`, `_EndSegment`, `_FlushSegment` control flow

---

## Speed/Tempo

**Status**: NOT implemented in framework
- Delegated to TTS provider (Cartesia, OpenAI, ElevenLabs)
- Duration tracking exists but not used for speed adjustment
- Frame timing determined by provider output rate

---

## Code File Locations (GitHub)

| File | Purpose |
|------|---------|
| `livekit/agents/tts/tts.py` | Core AudioEmitter, frame handling |
| `livekit/agents/tts/stream_pacer.py` | Pacing algorithm & batching |
| `livekit/agents/tokenize/token_stream.py` | Buffered tokenization |
| `livekit-plugins-nltk/sentence_tokenizer.py` | NLTK integration |
| `examples/voice_agents/tts_text_pacing.py` | Working example |

---

## Integration Pattern

```python
# 1. Tokenize with min length enforcement
tokenizer = SentenceTokenizer(min_sentence_len=20)
sentences = tokenizer.tokenize(text)

# 2. Pace with remaining audio threshold
pacer = SentenceStreamPacer(
    min_remaining_audio=5.0,
    max_text_length=300
)

# 3. Stream to TTS with frame size
tts.start(
    request_id="...",
    sample_rate=24000,
    num_channels=1,
    frame_size_ms=200
)

# 4. Consume 200ms audio frames
async for frame in tts_stream:
    emit(frame)  # ~4800 samples at 24kHz
```

---

## Performance Targets

| Metric | Value |
|--------|-------|
| Latency to first audio | 50-200ms |
| Frame duration | 200ms (configurable) |
| Min sentence chunk | 20 chars |
| Max batch text | 300 chars |
| Polling interval | 100ms |

---

## Limitations

- No Chinese/Japanese (tokenizer uses whitespace)
- No frame-level speed adjustment
- No sub-200ms frame size recommended
- Stream format determined by provider
