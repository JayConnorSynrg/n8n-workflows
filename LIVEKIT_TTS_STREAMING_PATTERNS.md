# LiveKit Agents TTS Streaming Implementation Patterns

**Source Repository:** https://github.com/livekit/agents
**Analysis Date:** 2026-01-10
**Purpose:** Extract actionable patterns for building OpenAI Realtime API alternative for voice agents

---

## 1. Sentence Chunking Logic

### Core Implementation
**File:** `/livekit-agents/livekit/agents/tokenize/_basic_sent.py`

#### Regex-Based Sentence Splitter
```python
def split_sentences(text: str, min_sentence_len: int = 20, retain_format: bool = False):
    """
    Rule-based segmentation - works surprisingly well
    Based on: https://stackoverflow.com/a/31505798
    """

    # Pattern definitions
    alphabets = r"([A-Za-z])"
    prefixes = r"(Mr|St|Mrs|Ms|Dr)[.]"
    suffixes = r"(Inc|Ltd|Jr|Sr|Co)"
    starters = r"(Mr|Mrs|Ms|Dr|Prof|Capt|Cpt|Lt|He\s|She\s|...)"
    acronyms = r"([A-Z][.][A-Z][.](?:[A-Z][.])?)"
    websites = r"[.](com|net|org|io|gov|edu|me)"
    digits = r"([0-9])"

    # Mark end of sentence punctuations with <stop>
    text = re.sub(r"([.!?。！？])([\""])", "\\1\\2<stop>", text)
    text = re.sub(r"([.!?。！？])(?![\""])", "\\1<stop>", text)

    # Buffer sentences until min_sentence_len reached
    buff = ""
    for match in text.split("<stop>"):
        sentence = match.strip()
        buff += " " + sentence
        if len(buff) > min_sentence_len:
            sentences.append(buff)
            buff = ""
```

#### Key Parameters
- **`min_sentence_len`**: Default `20` characters
- **`min_ctx_len`**: Default `10` characters (minimum context before tokenizing)
- **Pattern**: Buffers partial sentences until minimum length reached

**Actionable Pattern:**
```javascript
// n8n node implementation
const MIN_SENTENCE_LENGTH = 20;
const MIN_CONTEXT_LENGTH = 10;

function chunkTextForTTS(text) {
    let buffer = "";
    let chunks = [];

    // Split on sentence boundaries
    const sentences = text.split(/([.!?。！？][""]?)\s*/);

    for (const sentence of sentences) {
        buffer += sentence;
        if (buffer.length >= MIN_SENTENCE_LENGTH) {
            chunks.push(buffer.trim());
            buffer = "";
        }
    }

    if (buffer) chunks.push(buffer.trim());
    return chunks;
}
```

---

## 2. Audio Streaming Architecture

### AudioByteStream Buffer Pattern
**File:** `/livekit-agents/livekit/agents/utils/audio.py`

```python
class AudioByteStream:
    """
    Buffer and chunk audio byte data into fixed-size frames.
    Default: 100ms frames (sample_rate // 10)
    """

    def __init__(self, sample_rate: int, num_channels: int,
                 samples_per_channel: int | None = None):
        if samples_per_channel is None:
            samples_per_channel = sample_rate // 10  # 100ms default

        self._bytes_per_sample = num_channels * ctypes.sizeof(ctypes.c_int16)
        self._bytes_per_frame = samples_per_channel * self._bytes_per_sample
        self._buf = bytearray()

    def push(self, data: bytes) -> list[rtc.AudioFrame]:
        """Buffer incoming audio and emit fixed-size frames"""
        self._buf.extend(data)

        frames = []
        while len(self._buf) >= self._bytes_per_frame:
            frame_data = self._buf[:self._bytes_per_frame]
            del self._buf[:self._bytes_per_frame]
            frames.append(create_audio_frame(frame_data))

        return frames
```

#### Audio Frame Configuration
- **Default frame duration:** 100ms (`sample_rate // 10`)
- **Default sample rate:** 24,000 Hz (OpenAI), 48,000 Hz (general)
- **Channels:** Mono (1 channel)
- **Format:** PCM 16-bit signed little-endian

**File:** `/livekit-agents/livekit/agents/tts/tts.py:660`
```python
output_emitter.initialize(
    request_id=request_id,
    sample_rate=sample_rate,
    num_channels=num_channels,
    mime_type="audio/pcm",
    frame_size_ms=200  # 200ms default for TTS output
)
```

**Actionable Pattern:**
```javascript
// n8n voice bot workflow
const AUDIO_FRAME_SIZE_MS = 200; // 200ms chunks for TTS
const SAMPLE_RATE = 24000;
const NUM_CHANNELS = 1;

function bufferAudioChunks(audioData) {
    const samplesPerFrame = (SAMPLE_RATE / 1000) * AUDIO_FRAME_SIZE_MS;
    const bytesPerFrame = samplesPerFrame * NUM_CHANNELS * 2; // 16-bit = 2 bytes

    // Queue frames for streaming
    const frames = [];
    for (let i = 0; i < audioData.length; i += bytesPerFrame) {
        frames.push(audioData.slice(i, i + bytesPerFrame));
    }
    return frames;
}
```

---

## 3. Stream Pacing & Latency Optimization

### SentenceStreamPacer
**File:** `/livekit-agents/livekit/agents/tts/stream_pacer.py`

```python
class SentenceStreamPacer:
    def __init__(self, min_remaining_audio: float = 5.0, max_text_length: int = 300):
        """
        Controls pacing of text sent to TTS based on remaining audio duration.

        Args:
            min_remaining_audio: Minimum remaining audio (seconds) before sending next batch
            max_text_length: Maximum text length sent to TTS at once
        """
```

#### Intelligent Batching Logic
```python
async def _send_task(self):
    audio_duration = self._audio_emitter.pushed_duration()
    remaining_audio = audio_start_time + audio_duration - current_time

    # Send when:
    # 1. First sentence (immediate)
    # 2. Generation stopped AND remaining_audio <= min_remaining_audio
    if first_sentence or (generation_stopped and remaining_audio <= 5.0):
        # Send batch up to max_text_length (300 chars)
        batch = []
        while sentences and sum(len(s) for s in batch) < 300:
            batch.append(sentences.pop(0))

        send_to_tts(" ".join(batch))
```

**Key Insights:**
- **First sentence sent immediately** (minimize TTFB)
- **Subsequent batches wait** until ~5 seconds of audio remain
- **Max batch size:** 300 characters
- **Tracks generation state:** Detects when audio generation stops

**Actionable Pattern:**
```javascript
// n8n implementation
const MIN_REMAINING_AUDIO_SEC = 5.0;
const MAX_TEXT_BATCH_LENGTH = 300;

class TTSStreamPacer {
    constructor() {
        this.sentenceQueue = [];
        this.audioStartTime = null;
        this.audioDuration = 0;
        this.firstSentence = true;
    }

    shouldSendNextBatch() {
        if (this.firstSentence) return true;

        const remainingAudio = this.audioStartTime
            ? (this.audioStartTime + this.audioDuration - Date.now() / 1000)
            : 0;

        return remainingAudio <= MIN_REMAINING_AUDIO_SEC;
    }

    buildBatch() {
        const batch = [];
        let length = 0;

        while (this.sentenceQueue.length > 0 && length < MAX_TEXT_BATCH_LENGTH) {
            const sentence = this.sentenceQueue.shift();
            batch.push(sentence);
            length += sentence.length;
            if (this.firstSentence) break; // Send first sentence alone
        }

        this.firstSentence = false;
        return batch.join(" ");
    }
}
```

---

## 4. Connection Pooling for WebSockets

### ConnectionPool Pattern
**File:** `/livekit-agents/livekit/agents/utils/connection_pool.py`

```python
class ConnectionPool:
    """
    Manages persistent WebSocket connections with automatic reconnection.

    Features:
    - Connection reuse
    - Automatic expiration after max_session_duration (default: 300s)
    - Prewarming support
    """

    def __init__(self, max_session_duration: float = 300):
        self._connections = {}  # conn -> connected_at timestamp
        self._available = set()

    async def get(self, timeout: float) -> WebSocket:
        """Reuse available connection or create new one"""
        if self._available:
            conn = self._available.pop()
            if time.time() - self._connections[conn] <= self.max_session_duration:
                return conn
        return await self._connect(timeout)

    def prewarm(self):
        """Initiate connection in background without blocking"""
        asyncio.create_task(self._create_connection())
```

**Implementation Example (Cartesia TTS):**
**File:** `/livekit-plugins/livekit-plugins-cartesia/livekit/plugins/cartesia/tts.py:164-169`

```python
self._pool = ConnectionPool[aiohttp.ClientWebSocketResponse](
    connect_cb=self._connect_ws,
    close_cb=self._close_ws,
    max_session_duration=300,      # 5 minutes
    mark_refreshed_on_get=True     # Reset timer on reuse
)
```

**Actionable Pattern:**
```javascript
// n8n WebSocket connection pooling
class WebSocketPool {
    constructor(maxSessionDuration = 300000) { // 5 minutes
        this.connections = new Map();
        this.available = new Set();
        this.maxSessionDuration = maxSessionDuration;
    }

    async getConnection(url) {
        // Try reusing available connection
        for (const ws of this.available) {
            const connectedAt = this.connections.get(ws);
            if (Date.now() - connectedAt <= this.maxSessionDuration) {
                this.available.delete(ws);
                return ws;
            }
        }

        // Create new connection
        const ws = await this.connect(url);
        this.connections.set(ws, Date.now());
        return ws;
    }

    release(ws) {
        this.available.add(ws);
    }

    prewarm(url) {
        // Non-blocking connection creation
        this.connect(url).then(ws => {
            this.connections.set(ws, Date.now());
            this.available.add(ws);
        });
    }
}
```

---

## 5. Preemptive Generation Pattern

### Intelligent Prefetching
**File:** `/livekit-agents/livekit/agents/voice/agent_activity.py:88-96`

```python
@dataclass
class _PreemptiveGeneration:
    """
    Start generating LLM response before user finishes speaking.
    Triggered when STT detects high-confidence partial transcript.
    """
    speech_handle: SpeechHandle
    user_message: llm.ChatMessage
    info: _PreemptiveGenerationInfo
    chat_ctx: llm.ChatContext
    created_at: float

def on_preemptive_generation(self, info: _PreemptiveGenerationInfo):
    """
    Called when STT has high confidence partial transcript.
    Starts LLM generation early to reduce response latency.
    """
    if not self._session.options.preemptive_generation:
        return

    # Cancel any existing preemptive generation
    self._cancel_preemptive_generation()

    # Start new generation with partial transcript
    self._preemptive_generation = _PreemptiveGeneration(
        user_message=llm.ChatMessage(role="user", content=info.new_transcript),
        info=info,
        created_at=time.time()
    )
```

**Key Conditions for Preemptive Start:**
- STT confidence > threshold (typically 0.8)
- Transcript length > minimum (e.g., 10 words)
- User pause detected by VAD
- No current speech playing

**Actionable Pattern:**
```javascript
// n8n preemptive generation trigger
const PREEMPTIVE_CONFIDENCE_THRESHOLD = 0.8;
const PREEMPTIVE_MIN_WORDS = 10;

function shouldTriggerPreemptiveGeneration(sttResult) {
    return (
        sttResult.confidence >= PREEMPTIVE_CONFIDENCE_THRESHOLD &&
        sttResult.text.split(' ').length >= PREEMPTIVE_MIN_WORDS &&
        sttResult.isFinal === false && // Still streaming
        sttResult.pauseDetected === true
    );
}

async function handleSTTStream(sttResult) {
    if (shouldTriggerPreemptiveGeneration(sttResult)) {
        // Start LLM generation with partial transcript
        // Can be cancelled if user continues speaking
        const preemptiveResponse = await startLLMGeneration({
            text: sttResult.text,
            cancellable: true
        });

        // Store for potential reuse or cancellation
        this.preemptiveCache = preemptiveResponse;
    }
}
```

---

## 6. Speed Manipulation Pattern

### Audio Time-Stretching
**File:** `/examples/voice_agents/speedup_output_audio.py`

```python
import librosa
import numpy as np

class MyAgent(Agent):
    def __init__(self, speed_factor: float = 1.2):
        self.speed_factor = speed_factor

    def _process_audio(self, frame: rtc.AudioFrame) -> rtc.AudioFrame:
        """Time-stretch audio without pitch change"""
        audio_data = np.frombuffer(frame.data, dtype=np.int16)

        # Convert to float32 for processing
        audio_float = audio_data.astype(np.float32) / np.iinfo(np.int16).max

        # Time-stretch using librosa (preserves pitch)
        stretched = librosa.effects.time_stretch(
            audio_float,
            rate=self.speed_factor  # 1.2 = 20% faster
        )

        # Convert back to int16
        audio_int16 = (stretched * np.iinfo(np.int16).max).astype(np.int16)

        return rtc.AudioFrame(
            data=audio_int16.tobytes(),
            sample_rate=frame.sample_rate,
            num_channels=frame.num_channels,
            samples_per_channel=audio_int16.shape[-1]
        )
```

**Configuration via TTS Parameters:**
```python
# OpenAI TTS
tts = openai.TTS(speed=1.2)  # 0.25 to 4.0 range

# Cartesia TTS (Sonic-3)
tts = cartesia.TTS(speed=1.5)  # 0.6 to 2.0 range
```

**Actionable Pattern:**
```javascript
// n8n implementation options:

// Option 1: TTS provider native speed control
{
    tts_provider: "openai",
    speed: 1.2  // Direct API parameter
}

// Option 2: Post-processing (requires audio processing library)
// Use Web Audio API or external service for time-stretching
async function timeStretchAudio(audioBuffer, speedFactor) {
    const audioContext = new AudioContext();
    const source = audioContext.createBufferSource();
    source.playbackRate.value = speedFactor; // Simple approach
    // Note: This changes pitch. For pitch-preserving, need phase vocoder
    return processedAudio;
}

// Option 3: Delegate to Python subprocess
// Call librosa.effects.time_stretch via Execute Command node
```

---

## 7. Complete Voice Bot Workflow Pattern

### Recommended n8n Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Voice Bot Workflow                                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 1. WebSocket Trigger (LiveKit/Twilio/WebRTC)               │
│    ↓                                                         │
│ 2. Audio Input Buffer                                       │
│    → VAD (Voice Activity Detection)                         │
│    → 100ms frames, 48kHz, Mono                              │
│    ↓                                                         │
│ 3. STT Node (Streaming)                                     │
│    → Partial transcripts                                    │
│    → Confidence scoring                                     │
│    → Trigger preemptive generation at 0.8 confidence        │
│    ↓                                                         │
│ 4. Sentence Chunker                                         │
│    → min_sentence_len = 20                                  │
│    → min_ctx_len = 10                                       │
│    ↓                                                         │
│ 5. LLM Node (Streaming)                                     │
│    → OpenAI GPT-4 / Claude                                  │
│    → Stream tokens as available                             │
│    ↓                                                         │
│ 6. TTS Stream Pacer                                         │
│    → First sentence: immediate                              │
│    → Subsequent: when 5s audio remains                      │
│    → Max batch: 300 chars                                   │
│    ↓                                                         │
│ 7. TTS Node (WebSocket)                                     │
│    → OpenAI TTS / ElevenLabs / Cartesia                     │
│    → Connection pooling (300s lifetime)                     │
│    → Prewarm on workflow start                              │
│    ↓                                                         │
│ 8. Audio Frame Buffer                                       │
│    → 200ms chunks                                           │
│    → PCM 16-bit, 24kHz                                      │
│    ↓                                                         │
│ 9. WebSocket Output                                         │
│    → Stream to client                                       │
│    → Handle interruptions                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Key Implementation Constants

```javascript
// Timing & Buffering
const AUDIO_FRAME_SIZE_MS = 200;           // TTS output chunks
const AUDIO_INPUT_FRAME_MS = 100;          // STT input chunks
const SAMPLE_RATE_TTS = 24000;             // OpenAI standard
const SAMPLE_RATE_INPUT = 48000;           // General input
const NUM_CHANNELS = 1;                     // Mono

// Sentence Chunking
const MIN_SENTENCE_LENGTH = 20;            // Characters
const MIN_CONTEXT_LENGTH = 10;             // Before tokenizing
const MAX_TEXT_BATCH_LENGTH = 300;         // Per TTS request

// Stream Pacing
const MIN_REMAINING_AUDIO_SEC = 5.0;       // Before sending next batch
const FIRST_SENTENCE_IMMEDIATE = true;     // No delay for TTFB

// Connection Management
const WS_MAX_SESSION_DURATION = 300000;    // 5 minutes (ms)
const WS_PREWARM_ENABLED = true;           // Background connection

// Preemptive Generation
const PREEMPTIVE_CONFIDENCE_THRESHOLD = 0.8;
const PREEMPTIVE_MIN_WORDS = 10;
const PREEMPTIVE_ENABLED = true;

// Speed Control
const TTS_SPEED_DEFAULT = 1.0;
const TTS_SPEED_FAST = 1.2;                // 20% faster
const TTS_SPEED_RANGE = [0.6, 2.0];        // Cartesia Sonic-3
```

---

## 9. Critical Insights for n8n Implementation

### Latency Optimization Priorities
1. **Send first sentence immediately** (TTFB < 500ms)
2. **Use WebSocket connection pooling** (avoid handshake overhead)
3. **Prewarm connections** on workflow activation
4. **Enable preemptive generation** with high-confidence STT
5. **Buffer intelligently** (200ms TTS frames, not 1s+)

### Audio Quality Best Practices
- **PCM 16-bit preferred** over compressed formats (lower latency)
- **24kHz sample rate** sufficient for voice (OpenAI standard)
- **Mono channel** adequate for speech
- **Fixed frame sizes** prevent jitter (100ms input, 200ms output)

### Error Handling
- **Implement retry logic** with exponential backoff
- **Connection pool invalidation** on errors
- **Graceful degradation** (fallback TTS if streaming fails)
- **Cancel preemptive generations** if user continues speaking

### Cost Optimization
- **Batch sentences** up to 300 chars (reduce API calls)
- **Reuse WebSocket connections** (avoid per-request overhead)
- **Cache common phrases** if applicable
- **Monitor audio duration metrics** (track API usage)

---

## 10. Reference Files for Deep Dive

| Component | File Path | Purpose |
|-----------|-----------|---------|
| Sentence tokenization | `tokenize/_basic_sent.py` | Regex patterns for sentence splitting |
| Audio buffering | `utils/audio.py` | Fixed-size frame chunking |
| Stream pacing | `tts/stream_pacer.py` | Intelligent batch timing |
| Connection pooling | `utils/connection_pool.py` | WebSocket reuse pattern |
| TTS base classes | `tts/tts.py` | AudioEmitter, ChunkedStream, SynthesizeStream |
| OpenAI TTS | `plugins/openai/tts.py` | Non-streaming implementation |
| Cartesia TTS | `plugins/cartesia/tts.py` | Streaming WebSocket implementation |
| Preemptive generation | `voice/agent_activity.py` | Early LLM triggering |
| Speed manipulation | `examples/speedup_output_audio.py` | Librosa time-stretching |

---

## Implementation Checklist for n8n Voice Bot

- [ ] Implement sentence chunker with min_length=20, min_context=10
- [ ] Create audio frame buffer (200ms chunks, 24kHz, PCM16)
- [ ] Build WebSocket connection pool with 300s lifetime
- [ ] Add prewarm capability on workflow start
- [ ] Implement stream pacer (first immediate, then 5s remaining audio)
- [ ] Enable preemptive LLM generation (confidence ≥ 0.8)
- [ ] Configure TTS speed parameter (1.0-1.2 range)
- [ ] Add retry logic with exponential backoff
- [ ] Implement interruption handling (cancel ongoing TTS)
- [ ] Add metrics collection (TTFB, latency, duration)

---

**Generated by:** Claude Sonnet 4.5
**For:** n8n Workflow Voice Bot Development
**License:** Analysis of Apache 2.0 licensed code (LiveKit Agents)
