# LiveKit Agents TTS & Sentence Chunking Patterns

## Repository Analysis
**Source**: livekit/agents (Python Framework)
**Key Files Analyzed**:
- `livekit-agents/livekit/agents/tts/` - Core TTS pipeline
- `livekit-agents/livekit/agents/tokenize/` - Tokenization
- `livekit-plugins/livekit-plugins-nltk/` - NLTK sentence tokenizer
- Examples: `examples/other/text-to-speech/`, `examples/voice_agents/tts_text_pacing.py`

---

## 1. Sentence Segmentation & Tokenization

### Approach: NLTK Punkt Tokenizer (NOT Regex-Based)

```python
# From: livekit-plugins-nltk/sentence_tokenizer.py
import nltk

class SentenceTokenizer(agents.tokenize.SentenceTokenizer):
    def __init__(self, *, language: str = "english", min_sentence_len: int = 20):
        self.language = language
        self.min_sentence_len = min_sentence_len  # Default: 20 chars

    def tokenize(self, text: str) -> list[str]:
        # 1. Use NLTK's punkt tokenizer (language-aware)
        sentences = nltk.tokenize.sent_tokenize(text, self.language)

        # 2. Concatenate small sentences until reaching min_sentence_len
        new_sentences = []
        buff = ""
        for sentence in sentences:
            buff += sentence + " "
            if len(buff) - 1 >= self.min_sentence_len:
                new_sentences.append(buff.rstrip())
                buff = ""

        # 3. Append remainder
        if buff:
            new_sentences.append(buff.rstrip())

        return new_sentences
```

**Key Details**:
- **No regex patterns** - Uses NLTK's built-in punkt tokenizer
- **Language support**: English and 50+ languages via NLTK
- **Min sentence length**: 20 chars (configurable)
- **Concatenation strategy**: Space-separated, left-associative
- **Limitation**: Chinese/Japanese not supported (whitespace-based concatenation)

### Stream Processing

```python
# BufferedTokenStream for streaming tokenization
class BufferedTokenStream:
    def __init__(self, *, tokenize_fnc: Callable, min_token_len: int = 20, min_ctx_len: int = 10):
        self._min_token_len = min_token_len  # Minimum output chunk size
        self._min_ctx_len = min_ctx_len      # Context window before tokenizing
        self._in_buf = ""                     # Input buffer
        self._out_buf = ""                    # Output buffer

    def push_text(self, text: str):
        self._in_buf += text
        if len(self._in_buf) < self._min_ctx_len:
            return  # Wait for more context

        while True:
            tokens = self._tokenize_fnc(self._in_buf)
            if len(tokens) <= 1:
                break

            tok = tokens.pop(0)
            self._out_buf += tok

            if len(self._out_buf) >= self._min_token_len:
                # Emit token when minimum length reached
                send_token(self._out_buf)
                self._out_buf = ""
```

---

## 2. TTS Audio Chunk Sizing & Streaming

### Default Frame Size: 200ms

```python
# From: livekit/agents/tts/tts.py
class AudioEmitter:
    def start(self, *, request_id: str, sample_rate: int, num_channels: int,
              mime_type: str, frame_size_ms: int = 200):
        self._frame_size_ms = frame_size_ms  # Default: 200ms chunks
        self._sample_rate = sample_rate      # e.g., 24000 Hz
        self._num_channels = num_channels    # e.g., 1 (mono)

        # Calculate samples per frame
        samples_per_channel = int(sample_rate // 1000 * frame_size_ms)
        # Example: 24000 // 1000 * 200 = 4800 samples per frame
```

**Key Values**:
- **Default frame size**: 200ms
- **Typical sample rate**: 24000 Hz (24 kHz)
- **Samples per frame**: 4800 samples at 24kHz with 200ms
- **Bytes per frame**: 9600 bytes (2 bytes per sample, mono)

### Audio Byte Stream Implementation

```python
# Buffers raw bytes and emits frames at specified intervals
audio_byte_stream = audio.AudioByteStream(
    sample_rate=24000,
    num_channels=1,
    samples_per_channel=4800  # 200ms at 24kHz
)

# Push compressed audio (decoded first)
for f in audio_byte_stream.push(decoded_audio_bytes):
    emit_frame(f)  # Emits when buffer reaches samples_per_channel

# Flush remaining bytes
for f in audio_byte_stream.flush():
    emit_frame(f)
```

---

## 3. Stream Pacing & Buffer Management

### SentenceStreamPacer Architecture

```python
# From: livekit/agents/tts/stream_pacer.py
class SentenceStreamPacer:
    def __init__(self, *, min_remaining_audio: float = 5.0, max_text_length: int = 300):
        self._min_remaining_audio = min_remaining_audio  # Threshold in seconds
        self._max_text_length = max_text_length          # Chars to accumulate
        self._sentences: list[str] = []                  # Buffer
```

### Pacing Algorithm

```python
async def _send_task(self):
    audio_start_time = 0.0
    first_sentence = True
    generation_started = False

    while not self._closing:
        await self._wakeup_event.wait()

        # Calculate remaining audio duration
        audio_duration = self._audio_emitter.pushed_duration()
        curr_time = time.time()

        if audio_duration > 0.0 and audio_start_time == 0.0:
            audio_start_time = curr_time

        remaining_audio = (
            audio_start_time + audio_duration - curr_time
            if audio_start_time > 0.0
            else 0.0
        )

        # Dispatch logic: send when conditions met
        if first_sentence or remaining_audio <= self._min_remaining_audio:
            batch = []
            while self._sentences:
                batch.append(self._sentences.pop(0))

                # First sentence: no waiting
                # Subsequent: accumulate until max_text_length
                if (first_sentence or
                    sum(len(s) for s in batch) >= self._max_text_length):
                    break

            if batch:
                text = " ".join(batch)
                send_to_tts(text)
                first_sentence = False
```

### Pacing Parameters (Defaults)

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `min_remaining_audio` | 5.0 sec | Threshold to trigger next batch |
| `max_text_length` | 300 chars | Max chars per TTS call |
| `frame_size_ms` | 200 ms | Audio frame duration |
| `check_interval` | 0.1 sec | Audio duration check frequency |

**Timing Logic**:
- **During generation**: Check every 0.1 seconds for responsiveness
- **Idle**: Wait up to `remaining_audio - min_remaining_audio` seconds
- **Dispatch trigger**: `remaining_audio <= min_remaining_audio`

---

## 4. Channel-Based Buffering Architecture

### Multi-Stage Pipeline

```python
class AudioEmitter:
    def __init__(self):
        # Input channel: receives text or flush signals
        self._input_ch = aio.Chan()

        # Output channel: emits SynthesizedAudio frames
        self._event_ch = aio.Chan()

        # Internal write channel: coordinates audio data
        self._write_ch = aio.Chan()

# Data flows through stages:
# 1. Text → SentenceStreamPacer
# 2. Batched text → TTS provider
# 3. Compressed audio → AudioStreamDecoder
# 4. Raw audio → AudioByteStream
# 5. Frames → SynthesizedAudio objects
# 6. Client iteration
```

### Segment Boundary Signals

```python
class AudioEmitter:
    class _StartSegment:
        pass

    class _EndSegment:
        pass

    class _FlushSegment:
        pass

# Usage in pipeline
if isinstance(data, AudioEmitter._FlushSegment):
    # Flush any buffered bytes
    for f in audio_byte_stream.flush():
        emit_frame(f)
elif isinstance(data, AudioEmitter._EndSegment):
    # End current segment, prepare for next
    for f in audio_byte_stream.flush():
        emit_frame(f)
```

---

## 5. Speed/Tempo Adjustment

### Current Implementation: NONE

**Key Finding**: LiveKit agents framework does NOT implement tempo/speed adjustment.

**What IS tracked**:
```python
# Duration metrics exist but aren't used for tempo
audio_duration = self._audio_emitter.pushed_duration()  # Total audio pushed (ms)
pushed_duration()  # Returns milliseconds of audio buffered
```

**Tempo control responsibility**: Delegated to TTS provider
- Cartesia: Supports speed parameter in API
- OpenAI: No speed control
- ElevenLabs: Supports stability/similarity tradeoffs (indirect tempo effect)

**No frame-level speed adjustment** - timing determined by:
1. TTS provider's output rate
2. Audio decoder's processing rate
3. Frame chunking at `frame_size_ms` intervals

---

## 6. Practical Examples

### Example 1: Two-Word Streaming Pattern

```python
# From: examples/voice_agents/tts_text_pacing.py
# Simulates LLM streaming with 2-word chunks

tts_stream = tts_provider.push_text("The quick")
await tts_stream.push_text("brown fox")
await tts_stream.push_text("jumps over")
# ... continue chunking ...
await tts_stream.flush()
await tts_stream.end_input()

# Playback task continuously pulls frames
async for frame in tts_stream:
    audio_source.emit(frame)
```

### Example 2: Custom Pacer Configuration

```python
from livekit.agents.tts import SentenceStreamPacer

# Aggressive pacing: emit quickly with less context
pacer_aggressive = SentenceStreamPacer(
    min_remaining_audio=3.0,   # Trigger at 3 sec remaining
    max_text_length=150        # Smaller batches
)

# Conservative pacing: accumulate more context
pacer_conservative = SentenceStreamPacer(
    min_remaining_audio=10.0,  # Wait until 10 sec remaining
    max_text_length=500        # Larger batches, better context
)
```

### Example 3: Cartesia TTS Streaming

```python
import livekit.plugins.cartesia as cartesia

tts = cartesia.TTS()
stream = tts.synthesize(
    tts.Voice.ENGLISH_FEMALE,
    speech_model="sonic-2"
)

# Push text incrementally
stream.push_text("Hello, ")
stream.push_text("this is a test.")
stream.flush()

# Consume frames
async for frame in stream:
    # Process 200ms chunks
    print(f"Audio frame: {frame.sample_rate} Hz, {len(frame.data)} bytes")
```

---

## 7. Key Integration Points

### Sentence Tokenizer Configuration

```python
from livekit.plugins.nltk import SentenceTokenizer

tokenizer = SentenceTokenizer(
    language="english",           # Or: "french", "spanish", etc.
    min_sentence_len=20,          # Minimum output chunk (chars)
    stream_context_len=10         # Context before emitting
)

# Use in session
session = AgentSession(
    stt="...",
    llm="...",
    tts="...",
    # Optional: customize sentence handling
    sentence_tokenizer=tokenizer
)
```

### TTS Stream Integration

```python
from livekit.agents.tts import SentenceStreamPacer

session = AgentSession(
    # ... other config ...
    text_pacing=SentenceStreamPacer(
        min_remaining_audio=5.0,
        max_text_length=300
    )
)
```

---

## 8. Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Min sentence length | 20 chars | Default; configurable |
| Default frame size | 200 ms | At 24kHz = 4800 samples |
| Stream context window | 10 chars | Before first tokenization |
| Max text batch | 300 chars | Typical config |
| Remaining audio threshold | 5 sec | Triggers next dispatch |
| Check interval | 100 ms | Audio duration polling |
| Latency (first frame) | ~50-200 ms | Depends on TTS provider |

---

## 9. Unsupported Features

1. **No regex patterns** - NLTK punkt used exclusively
2. **No speed/tempo adjustment** - Delegated to TTS providers
3. **No Chinese/Japanese support** - Whitespace tokenization limitation
4. **No sub-frame chunking** - Minimum 200ms (configurable)
5. **No adaptive bitrate** - Fixed output format per provider

---

## 10. Stream Formats & Codecs

### Supported Formats (via providers)

| Provider | Codec | Quality | Speed |
|----------|-------|---------|-------|
| Cartesia | MP3, WAV, PCM | High | Real-time |
| OpenAI TTS | MP3, PCM | Good | Non-streaming |
| ElevenLabs | MP3, PCM | High | Real-time |
| DeepGram | MP3, PCM | Good | Real-time |

### Raw PCM Detection

```python
# Automatic format detection
is_raw_pcm = (mime_type.startswith("audio/pcm") or
              mime_type.startswith("audio/raw"))

if is_raw_pcm:
    # Skip decoding, push directly to AudioByteStream
    for f in audio_byte_stream.push(raw_bytes):
        emit_frame(f)
else:
    # Decompress first (MP3, etc.)
    async for frame in AudioStreamDecoder(stream):
        for f in audio_byte_stream.push(frame.data):
            emit_frame(f)
```

---

## Recommendation for Integration

For n8n TTS nodes, implement:

1. **Sentence tokenization**: Integrate NLTK punkt or use simple regex + min-length buffering
2. **Stream pacing**: Implement `min_remaining_audio` and `max_text_length` thresholds
3. **Frame chunking**: Default 200ms at provider's sample rate
4. **Buffering**: Use channel-based async queues with overflow handling
5. **Provider abstraction**: Allow swapping TTS providers without refactor

**Reference implementations**: See `livekit-agents/tts/` directory for battle-tested patterns.
