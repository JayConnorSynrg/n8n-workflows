# LiveKit TTS - Extracted Code Snippets

## 1. Sentence Tokenization (NLTK)

**File**: `livekit-plugins-nltk/sentence_tokenizer.py`

```python
from nltk.tokenize import sent_tokenize

class SentenceTokenizer:
    def __init__(self, language="english", min_sentence_len=20, stream_context_len=10):
        self.language = language
        self.min_sentence_len = min_sentence_len
        self.stream_context_len = stream_context_len

    def tokenize(self, text: str) -> list[str]:
        # Step 1: Use NLTK punkt tokenizer (language-aware)
        sentences = sent_tokenize(text, self.language)

        # Step 2: Concatenate small sentences
        new_sentences = []
        buff = ""
        for sentence in sentences:
            buff += sentence + " "
            if len(buff) - 1 >= self.min_sentence_len:
                new_sentences.append(buff.rstrip())
                buff = ""

        # Step 3: Append remainder
        if buff:
            new_sentences.append(buff.rstrip())

        return new_sentences
```

---

## 2. Stream Pacing Algorithm

**File**: `livekit/agents/tts/stream_pacer.py`

```python
import asyncio
import time
from dataclasses import dataclass

@dataclass
class StreamPacerOptions:
    min_remaining_audio: float = 5.0
    max_text_length: int = 300

class SentenceStreamPacer:
    def __init__(self, *, min_remaining_audio=5.0, max_text_length=300):
        self._options = StreamPacerOptions(
            min_remaining_audio=min_remaining_audio,
            max_text_length=max_text_length
        )
        self._sentences = []
        self._wakeup_event = asyncio.Event()
        self._input_ended = False
        self._closing = False

    async def _send_task(self):
        """Main pacing loop - sends batches to TTS based on remaining audio"""
        audio_start_time = 0.0
        first_sentence = True

        while not self._closing:
            await self._wakeup_event.wait()
            self._wakeup_event.clear()

            if self._closing or (self._input_ended and not self._sentences):
                break

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

            # Decision logic: send batch if conditions met
            send_batch = (
                first_sentence or
                remaining_audio <= self._options.min_remaining_audio
            )

            if send_batch:
                batch = []
                while self._sentences:
                    batch.append(self._sentences.pop(0))

                    # First sentence: send immediately
                    # Others: accumulate until max_text_length
                    if (first_sentence or
                        sum(len(s) for s in batch) >= self._options.max_text_length):
                        break

                if batch:
                    text = " ".join(batch)
                    self._event_ch.send_nowait(TokenData(token=text))
                    first_sentence = False
```

---

## 3. Audio Frame Chunking

**File**: `livekit/agents/tts/tts.py`

```python
class AudioEmitter:
    def start(self, *, request_id, sample_rate, num_channels, mime_type,
              frame_size_ms=200, stream=False):
        """
        Args:
            sample_rate: e.g., 24000 (Hz)
            num_channels: e.g., 1 (mono) or 2 (stereo)
            frame_size_ms: e.g., 200 (milliseconds)
            mime_type: e.g., "audio/pcm" or "audio/mp3"
        """
        self._frame_size_ms = frame_size_ms
        self._sample_rate = sample_rate
        self._num_channels = num_channels

        # Calculate samples per frame
        samples_per_channel = int(
            sample_rate // 1000 * frame_size_ms
        )
        # Example: 24000 // 1000 * 200 = 4800 samples per frame

        # Create byte stream for frame emission
        audio_byte_stream = AudioByteStream(
            sample_rate=sample_rate,
            num_channels=num_channels,
            samples_per_channel=samples_per_channel
        )

        self._is_raw_pcm = (
            mime_type.lower().startswith("audio/pcm") or
            mime_type.lower().startswith("audio/raw")
        )
```

---

## 4. Buffered Token Stream

**File**: `livekit/agents/tokenize/token_stream.py`

```python
class BufferedTokenStream:
    """
    Buffers tokens until minimum length reached, respecting context window
    """
    def __init__(self, *, tokenize_fnc, min_token_len=20, min_ctx_len=10,
                 retain_format=False):
        self._tokenize_fnc = tokenize_fnc  # e.g., nltk.tokenize.sent_tokenize
        self._min_token_len = min_token_len
        self._min_ctx_len = min_ctx_len
        self._in_buf = ""
        self._out_buf = ""

    def push_text(self, text: str):
        self._in_buf += text

        # Wait for minimum context before tokenizing
        if len(self._in_buf) < self._min_ctx_len:
            return

        while True:
            tokens = self._tokenize_fnc(self._in_buf)
            if len(tokens) <= 1:
                break  # Not enough to tokenize

            tok = tokens.pop(0)
            tok_text = tok[0] if isinstance(tok, tuple) else tok

            self._out_buf += tok_text
            if len(self._out_buf) >= self._min_token_len:
                # Emit when minimum length reached
                emit_token(self._out_buf)
                self._out_buf = ""

            # Update input buffer (remove processed token)
            if isinstance(tok, tuple):
                self._in_buf = self._in_buf[tok[2]:]  # tok = (text, start, end)
            else:
                tok_i = max(self._in_buf.find(tok), 0)
                self._in_buf = self._in_buf[tok_i + len(tok):].lstrip()

    def flush(self):
        """Final flush when stream ends"""
        if self._in_buf or self._out_buf:
            tokens = self._tokenize_fnc(self._in_buf)
            if tokens:
                if self._out_buf:
                    self._out_buf += " "
                if isinstance(tokens[0], tuple):
                    self._out_buf += " ".join([tok[0] for tok in tokens])
                else:
                    self._out_buf += " ".join(tokens)

            if self._out_buf:
                emit_token(self._out_buf)
```

---

## 5. Segment Boundary Management

**File**: `livekit/agents/tts/tts.py`

```python
class AudioEmitter:
    @dataclass
    class _StartSegment:
        """Mark start of text segment"""
        pass

    @dataclass
    class _EndSegment:
        """Mark end of text segment"""
        pass

    @dataclass
    class _FlushSegment:
        """Flush buffered bytes without closing segment"""
        pass

# Usage in audio pipeline
async for data in self._write_ch:
    if isinstance(data, bytes):
        # Raw audio data
        for f in audio_byte_stream.push(data):
            _emit_frame(f)

    elif isinstance(data, AudioEmitter._FlushSegment):
        # Flush without segment boundary
        for f in audio_byte_stream.flush():
            _emit_frame(f)
        _flush_frame()

    elif isinstance(data, AudioEmitter._EndSegment):
        # End segment and flush
        for f in audio_byte_stream.flush():
            _emit_frame(f)
        # Send final frame and reset segment tracking
```

---

## 6. Duration Tracking (No Speed Adjustment)

**File**: `livekit/agents/tts/tts.py`

```python
class AudioEmitter:
    def __init__(self):
        self._audio_duration = 0.0  # Milliseconds of audio pushed

    def pushed_duration(self) -> float:
        """Returns total milliseconds of audio data pushed to stream"""
        return self._audio_duration

    def _emit_frame(self, frame_data):
        """Emit frame without speed adjustment"""
        # Duration calculation (not used for tempo)
        duration_ms = (len(frame_data) /
                      (self._sample_rate // 1000 * self._num_channels * 2))
        self._audio_duration += duration_ms

        # Create SynthesizedAudio without tempo info
        synthesized = SynthesizedAudio(
            request_id=self._request_id,
            segment_id=self._segment_id,
            data=frame_data,
            sample_rate=self._sample_rate,
            num_channels=self._num_channels
        )
        self._event_ch.send_nowait(synthesized)
```

---

## 7. Complete Integration Example

```python
"""
Complete TTS pipeline using LiveKit patterns
"""
from livekit.plugins.nltk import SentenceTokenizer
from livekit.agents.tts import SentenceStreamPacer, AudioEmitter

# 1. Setup tokenizer
tokenizer = SentenceTokenizer(
    language="english",
    min_sentence_len=20,
    stream_context_len=10
)

# 2. Setup pacer
pacer = SentenceStreamPacer(
    min_remaining_audio=5.0,   # seconds
    max_text_length=300         # characters
)

# 3. Setup TTS emitter
emitter = AudioEmitter(label="main")
emitter.start(
    request_id="req-123",
    sample_rate=24000,
    num_channels=1,
    mime_type="audio/pcm",
    frame_size_ms=200,
    stream=True
)

# 4. Stream text
text = "The quick brown fox jumps over the lazy dog."
for word in text.split():
    tokenizer_stream.push_text(word + " ")

tokenizer_stream.flush()
tokenizer_stream.end_input()

# 5. Consume frames
frame_count = 0
async for frame in emitter.aiter_frames():
    frame_count += 1
    # Each frame is ~200ms at 24kHz
    print(f"Frame {frame_count}: {len(frame.data)} bytes, "
          f"{frame.sample_rate} Hz, {frame.num_channels} channel(s)")
```

---

## 8. Configuration Presets

**Aggressive (Low Latency)**:
```python
SentenceStreamPacer(
    min_remaining_audio=2.0,   # Trigger earlier
    max_text_length=150        # Smaller batches
)
```

**Balanced (Default)**:
```python
SentenceStreamPacer(
    min_remaining_audio=5.0,   # Default
    max_text_length=300        # Default
)
```

**Conservative (High Context)**:
```python
SentenceStreamPacer(
    min_remaining_audio=10.0,  # Wait longer
    max_text_length=500        # Larger batches
)
```

---

## 9. Raw PCM vs Encoded Detection

```python
def detect_format(mime_type: str) -> str:
    """Determine if audio is raw PCM or encoded"""
    mt = mime_type.lower().strip()

    if mt.startswith("audio/pcm") or mt.startswith("audio/raw"):
        return "raw_pcm"  # Skip decoding
    elif mt.startswith("audio/mp3"):
        return "mp3"      # Requires decoding
    elif mt.startswith("audio/ogg"):
        return "ogg"      # Requires decoding
    else:
        return "unknown"

# Usage
if detect_format(mime_type) == "raw_pcm":
    # Direct streaming
    for f in audio_byte_stream.push(raw_bytes):
        emit_frame(f)
else:
    # Decode first
    async for decoded_frame in decoder.aiter_frames(encoded_stream):
        for f in audio_byte_stream.push(decoded_frame.data):
            emit_frame(f)
```

---

## Key Constants

```python
# Defaults
DEFAULT_FRAME_SIZE_MS = 200
DEFAULT_MIN_REMAINING_AUDIO = 5.0
DEFAULT_MAX_TEXT_LENGTH = 300
DEFAULT_MIN_SENTENCE_LEN = 20
DEFAULT_STREAM_CONTEXT_LEN = 10

# Common sample rates
SAMPLE_RATE_16K = 16000   # Older TTS engines
SAMPLE_RATE_24K = 24000   # Modern TTS (Cartesia, etc.)
SAMPLE_RATE_48K = 48000   # High quality

# Samples per frame at different rates
# 200ms @ 16kHz = 3200 samples
# 200ms @ 24kHz = 4800 samples
# 200ms @ 48kHz = 9600 samples
```
