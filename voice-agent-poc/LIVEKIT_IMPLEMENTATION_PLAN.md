# LiveKit Voice Pipeline Implementation Plan

**Objective:** Migrate from OpenAI Realtime API to disaggregated pipeline for sub-500ms latency

**Constraint:** Fully cloud-hosted - no local deployment allowed

**Last Updated:** January 2026

---

## RECOMMENDED ARCHITECTURE: Option A - LiveKit Cloud + API Services

After evaluating self-hosted options, this architecture is recommended for production deployment:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    PRODUCTION VOICE AGENT ARCHITECTURE                            │
│                    (Fully Cloud-Hosted - No Local Dependencies)                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ INFRASTRUCTURE LAYER                                                        │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                             │  │
│  │  LiveKit Cloud (FREE tier)           Railway ($5/mo)                        │  │
│  │  ├── WebRTC transport               ├── LiveKit Agent process               │  │
│  │  ├── Media routing                  ├── Plugin orchestration                │  │
│  │  ├── 100 concurrent participants    └── Tool execution                      │  │
│  │  └── Built-in TURN servers                                                  │  │
│  │                                                                             │  │
│  │  Vercel (FREE)                       n8n Cloud (existing)                   │  │
│  │  └── Frontend hosting               └── Workflow automation                 │  │
│  │                                                                             │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ API SERVICES LAYER                                                          │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                             │  │
│  │  Deepgram Nova-3 (STT)      Groq LLaMA 3.1 8B (LLM)     Chatterbox (TTS)   │  │
│  │  ├── $0.0035/min            ├── $0.05/1M tokens          ├── ~$0.004/min   │  │
│  │  ├── ~150ms P50 latency     ├── ~200ms TTFT              ├── ~200ms stream │  │
│  │  └── Streaming WebSocket    └── Streaming API            └── Streaming PCM │  │
│  │                                                                             │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ DATA FLOW                                                                   │  │
│  ├────────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                             │  │
│  │  Teams Meeting                                                              │  │
│  │       │                                                                     │  │
│  │       ▼                                                                     │  │
│  │  Recall.ai Bot (output_media: webpage)                                      │  │
│  │       │                                                                     │  │
│  │       ▼                                                                     │  │
│  │  Client (Vercel) ──WebRTC──► LiveKit Cloud ──WebSocket──► Railway Agent     │  │
│  │                                    │                            │           │  │
│  │                                    │                            ▼           │  │
│  │                              Audio Stream            ┌──────────────────┐   │  │
│  │                                                      │ Pipeline:        │   │  │
│  │                                                      │ Silero VAD       │   │  │
│  │                                                      │ Deepgram STT     │   │  │
│  │                                                      │ Groq LLM         │   │  │
│  │                                                      │ Chatterbox TTS   │   │  │
│  │                                                      └──────────────────┘   │  │
│  │                                                             │               │  │
│  │                                                             ▼               │  │
│  │                                                      n8n Webhooks           │  │
│  │                                                      (Tool execution)       │  │
│  │                                                                             │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Decision Record

### Why Not Self-Hosted LiveKit?

| Issue | Impact |
|-------|--------|
| **Railway lacks host networking** | LiveKit server requires direct UDP port exposure |
| **Container isolation** | WebRTC STUN/TURN relay adds 50-100ms latency |
| **No GPU support on Railway** | Cannot run local LLM inference |
| **Operational complexity** | Self-hosting WebRTC requires significant DevOps |

**Recommendation:** Use LiveKit Cloud free tier (100 concurrent participants) - handles all WebRTC complexity.

### Why Not Self-Hosted LLM?

| Option | Latency | Cost/hr | Issue |
|--------|---------|---------|-------|
| vLLM on Modal | 300-400ms | ~$2.50 | +100-200ms vs Groq |
| vLLM on RunPod | 300-400ms | ~$0.40 | Cold starts, no auto-scale |
| Together.ai | 250-350ms | ~$0.20/1M | Slightly slower than Groq |
| **Groq** | **~200ms** | **~$0.05/1M** | **Fastest, cheapest** |

**Recommendation:** Groq runs open-source models (LLaMA 3.1) on proprietary LPU hardware. The ~200ms TTFT cannot be matched by self-hosted vLLM without significant GPU investment.

### Cost Analysis

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| LiveKit Cloud | **FREE** | 100 concurrent participants |
| Railway | **$5** | LiveKit Agent process |
| Vercel | **FREE** | Frontend hosting |
| Deepgram | ~$0.0035/min | Pay-per-use |
| Groq | ~$0.05/1M tokens | Pay-per-use |
| Chatterbox | ~$0.004/min | Pay-per-use |

**Per-minute voice cost:** ~$0.01/min
**Fixed monthly:** ~$5

---

## Target Architecture (Latency Breakdown)

```
User Audio ──► LiveKit VAD ──► Deepgram STT ──► Groq LLaMA 3.1 ──► Chatterbox TTS
                (~20ms)         (~150ms)         (~200ms)           (~200ms)
                                                                    ─────────
                                                           TOTAL: ~400-600ms
```

---

## Phase 1: Cloud Infrastructure Setup (Day 1)

### 1.1 LiveKit Cloud Account (FREE Tier)

```
┌────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Sign up at https://cloud.livekit.io                                │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  1. Create account (GitHub/Google OAuth)                                   │
│  2. Create new project: "voice-agent-production"                           │
│  3. Select region: us-west (closest to Railway)                            │
│  4. Copy credentials from Settings → API Keys:                             │
│                                                                            │
│     LIVEKIT_URL=wss://voice-agent-production.livekit.cloud                 │
│     LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxxx                                    │
│     LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx                   │
│                                                                            │
│  FREE TIER LIMITS:                                                         │
│  - 100 concurrent participants                                             │
│  - 5,000 participant-minutes/month                                         │
│  - Sufficient for development + moderate production                        │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 API Services Setup

| Service | Sign Up URL | Environment Variable | Free Tier |
|---------|-------------|---------------------|-----------|
| **LiveKit** | cloud.livekit.io | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | 5,000 min/mo |
| **Deepgram** | console.deepgram.com | `DEEPGRAM_API_KEY` | $200 credit |
| **Groq** | console.groq.com | `GROQ_API_KEY` | Free tier available |
| **Chatterbox** | chatterboxtts.com | `CHATTERBOX_API_KEY` | Varies |

**Alternative TTS Options (if Chatterbox unavailable):**
- ElevenLabs: `ELEVENLABS_API_KEY` - ~250ms latency, high quality
- Cartesia: `CARTESIA_API_KEY` - ~150ms latency, built-in LiveKit plugin
- PlayHT: `PLAYHT_API_KEY` - ~200ms latency, good voices

### 1.3 Railway Deployment (LiveKit Agent)

```bash
# Clone or create new project
mkdir livekit-voice-agent && cd livekit-voice-agent

# Initialize Railway project
railway init

# Link to existing project or create new
railway link

# Set ALL environment variables (Railway Dashboard → Variables)
railway variables set \
  LIVEKIT_URL="wss://voice-agent-production.livekit.cloud" \
  LIVEKIT_API_KEY="APIxxxxxxxxxxxxxxxx" \
  LIVEKIT_API_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  DEEPGRAM_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  GROQ_API_KEY="gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  CHATTERBOX_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  N8N_WEBHOOK_BASE_URL="https://jayconnorexe.app.n8n.cloud/webhook"

# Deploy
railway up
```

**Railway Configuration (railway.json):**
```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "numReplicas": 1,
    "sleepApplication": false,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 1.4 Vercel Frontend Deployment

```bash
# Navigate to client
cd voice-agent-poc/client-v2

# Deploy to Vercel
vercel --prod

# Set environment variables in Vercel Dashboard:
# NEXT_PUBLIC_LIVEKIT_URL=wss://voice-agent-production.livekit.cloud
```

---

## Phase 2: LiveKit Agent Server (Day 1-2)

### 2.1 Project Structure
```
livekit-voice-agent/
├── agent.py                 # Main agent entry point
├── plugins/
│   ├── __init__.py
│   ├── chatterbox_tts.py   # Custom Chatterbox TTS plugin
│   └── groq_llm.py         # Groq LLM wrapper
├── tools/
│   ├── __init__.py
│   ├── email_tool.py       # n8n email integration
│   └── database_tool.py    # n8n vector DB integration
├── requirements.txt
├── Dockerfile
└── railway.json
```

### 2.2 requirements.txt
```
livekit-agents[silero,deepgram]~=1.0
aiohttp>=3.9.0
python-dotenv>=1.0.0
groq>=0.9.0
```

### 2.3 Main Agent (agent.py)
```python
import asyncio
from livekit.agents import Agent, AgentSession, JobContext, cli
from livekit.plugins import silero, deepgram

from plugins.groq_llm import GroqLLM
from plugins.chatterbox_tts import ChatterboxTTS
from tools.email_tool import send_email_tool
from tools.database_tool import query_database_tool

SYSTEM_PROMPT = """You are a professional voice assistant for enterprise meetings.

CORE BEHAVIORS:
- Be concise and direct
- Confirm actions before executing
- Announce completion of tasks

AVAILABLE TOOLS:
- send_email: Send emails via Gmail
- query_database: Search the knowledge base

RESPONSE STYLE:
- Keep responses under 2 sentences when possible
- Use natural conversation pacing
"""

async def entrypoint(ctx: JobContext):
    # Initialize pipeline components
    session = AgentSession(
        vad=silero.VAD.load(
            min_speech_duration=0.1,
            min_silence_duration=0.3,
            activation_threshold=0.5
        ),
        stt=deepgram.STT(
            model="nova-3",
            language="en",
            smart_format=True,
            interim_results=True  # For faster response
        ),
        llm=GroqLLM(
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=256  # Keep responses short for voice
        ),
        tts=ChatterboxTTS(
            model="turbo",
            voice="professional"
        )
    )

    # Define agent with tools
    agent = Agent(
        instructions=SYSTEM_PROMPT,
        tools=[send_email_tool, query_database_tool]
    )

    # Connect to room and start
    await ctx.connect(auto_subscribe=True)
    await session.start(agent=agent, room=ctx.room)

    # Handle events
    @session.on("agent_speech_started")
    def on_speaking():
        # Notify webpage for animation
        ctx.room.local_participant.publish_data(
            '{"type":"agent.state","state":"speaking"}'
        )

    @session.on("agent_speech_finished")
    def on_idle():
        ctx.room.local_participant.publish_data(
            '{"type":"agent.state","state":"idle"}'
        )

    @session.on("user_speech_started")
    def on_listening():
        ctx.room.local_participant.publish_data(
            '{"type":"agent.state","state":"listening"}'
        )

if __name__ == "__main__":
    cli.run_app(entrypoint)
```

### 2.4 Custom Groq LLM Plugin (plugins/groq_llm.py)
```python
from typing import AsyncIterator, Optional
from livekit.agents import LLM, LLMMessage
from groq import AsyncGroq
import os

class GroqLLM(LLM):
    def __init__(
        self,
        model: str = "llama-3.1-8b-instant",
        temperature: float = 0.7,
        max_tokens: int = 256
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: Optional[list] = None
    ) -> AsyncIterator[str]:
        # Convert to Groq format
        groq_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        # Stream response
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=groq_messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
            tools=tools if tools else None
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

            # Handle tool calls
            if chunk.choices[0].delta.tool_calls:
                for tool_call in chunk.choices[0].delta.tool_calls:
                    yield {"tool_call": tool_call}
```

### 2.5 Custom Chatterbox TTS Plugin (plugins/chatterbox_tts.py)
```python
from typing import AsyncIterator
from livekit.agents import TTS, AudioFrame
import aiohttp
import os

class ChatterboxTTS(TTS):
    def __init__(
        self,
        model: str = "turbo",
        voice: str = "professional",
        api_url: str = "https://api.chatterboxtts.com/v1"
    ):
        self.model = model
        self.voice = voice
        self.api_url = api_url
        self.api_key = os.environ.get("CHATTERBOX_API_KEY")

    async def synthesize(self, text: str) -> AsyncIterator[AudioFrame]:
        """Stream audio from Chatterbox TTS API"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_url}/audio/speech",
                json={
                    "input": text,
                    "model": self.model,
                    "voice": self.voice,
                    "response_format": "pcm",  # Raw 24kHz PCM
                    "stream": True
                },
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    raise Exception(f"Chatterbox API error: {error}")

                async for chunk in resp.content.iter_chunked(4096):
                    yield AudioFrame(
                        data=chunk,
                        sample_rate=24000,
                        channels=1,
                        samples_per_channel=len(chunk) // 2  # 16-bit audio
                    )
```

### 2.6 Tool Integration (tools/email_tool.py)
```python
import aiohttp
from livekit.agents import function_tool

N8N_WEBHOOK_URL = "https://jayconnorexe.app.n8n.cloud/webhook/voice-tools"

@function_tool(
    name="send_email",
    description="Send an email to a recipient. Requires to, subject, and body.",
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string", "description": "Email subject line"},
            "body": {"type": "string", "description": "Email body content"}
        },
        "required": ["to", "subject", "body"]
    }
)
async def send_email_tool(to: str, subject: str, body: str, ctx) -> str:
    """Execute email send via n8n workflow"""

    # Get session context
    session_id = ctx.room.name  # Room name is session ID

    async with aiohttp.ClientSession() as session:
        # Call n8n webhook
        async with session.post(
            f"{N8N_WEBHOOK_URL}/execute-gmail",
            json={
                "session_id": session_id,
                "to": to,
                "subject": subject,
                "body": body
            }
        ) as resp:
            result = await resp.json()

            if result.get("status") == "COMPLETED":
                return f"Email sent successfully to {to}"
            else:
                return f"Failed to send email: {result.get('error', 'Unknown error')}"
```

---

## Phase 3: Client Updates (Day 2)

### 3.1 Update Client to Use LiveKit SDK
```bash
cd voice-agent-poc/client-v2
npm install livekit-client@^2.0.0
```

### 3.2 New Hook: useLiveKitVoice.ts
```typescript
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Room,
  RoomEvent,
  Track,
  TrackPublication,
  RemoteParticipant,
  DataPacket_Kind
} from 'livekit-client'
import { useStore } from '../lib/store'

interface UseLiveKitVoiceOptions {
  url: string
  token: string
  onConnect?: () => void
  onDisconnect?: () => void
}

export function useLiveKitVoice(options: UseLiveKitVoiceOptions) {
  const [isConnected, setIsConnected] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const roomRef = useRef<Room | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)

  const {
    setAgentState,
    setInputVolume,
    setOutputVolume,
    addMessage
  } = useStore()

  const connect = useCallback(async () => {
    if (roomRef.current?.state === 'connected') return

    setIsConnecting(true)
    setError(null)

    try {
      const room = new Room({
        adaptiveStream: true,
        dynacast: true,
        audioCaptureDefaults: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })

      roomRef.current = room

      // Handle data messages from agent
      room.on(RoomEvent.DataReceived, (payload, participant) => {
        try {
          const data = JSON.parse(new TextDecoder().decode(payload))

          switch (data.type) {
            case 'agent.state':
              setAgentState(data.state)
              break
            case 'transcript.user':
              addMessage({ role: 'user', content: data.text })
              break
            case 'transcript.assistant':
              addMessage({ role: 'assistant', content: data.text })
              break
          }
        } catch (e) {
          console.error('Failed to parse data message:', e)
        }
      })

      // Handle agent audio for volume visualization
      room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
        if (track.kind === Track.Kind.Audio && participant.isAgent) {
          setupOutputVolumeAnalyzer(track.mediaStream!)
        }
      })

      // Connect to room
      await room.connect(options.url, options.token)

      // Publish microphone
      await room.localParticipant.setMicrophoneEnabled(true)

      // Setup input volume analyzer
      const localAudioTrack = room.localParticipant.getTrack(Track.Source.Microphone)
      if (localAudioTrack?.track?.mediaStream) {
        setupInputVolumeAnalyzer(localAudioTrack.track.mediaStream)
      }

      setIsConnecting(false)
      setIsConnected(true)
      options.onConnect?.()

    } catch (err) {
      setIsConnecting(false)
      const message = err instanceof Error ? err.message : 'Connection failed'
      setError(message)
    }
  }, [options, setAgentState, addMessage])

  const disconnect = useCallback(() => {
    if (roomRef.current) {
      roomRef.current.disconnect()
      roomRef.current = null
    }
    setIsConnected(false)
  }, [])

  const setupInputVolumeAnalyzer = (stream: MediaStream) => {
    const audioContext = new AudioContext()
    audioContextRef.current = audioContext

    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 256

    const source = audioContext.createMediaStreamSource(stream)
    source.connect(analyser)

    const dataArray = new Uint8Array(analyser.frequencyBinCount)

    const updateVolume = () => {
      analyser.getByteFrequencyData(dataArray)
      const average = dataArray.reduce((a, b) => a + b) / dataArray.length
      setInputVolume(Math.min(1, average / 128))
      requestAnimationFrame(updateVolume)
    }
    updateVolume()
  }

  const setupOutputVolumeAnalyzer = (stream: MediaStream) => {
    const audioContext = audioContextRef.current || new AudioContext()

    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 256

    const source = audioContext.createMediaStreamSource(stream)
    source.connect(analyser)

    const dataArray = new Uint8Array(analyser.frequencyBinCount)

    const updateVolume = () => {
      analyser.getByteFrequencyData(dataArray)
      const average = dataArray.reduce((a, b) => a + b) / dataArray.length
      setOutputVolume(Math.min(1, average / 128))
      requestAnimationFrame(updateVolume)
    }
    updateVolume()
  }

  useEffect(() => {
    return () => disconnect()
  }, [disconnect])

  return {
    connect,
    disconnect,
    isConnected,
    isConnecting,
    error
  }
}
```

### 3.3 Update App.tsx for LiveKit
```typescript
// Add LiveKit token fetching
const params = new URLSearchParams(window.location.search)
const livekitUrl = params.get('livekit_url')
const roomName = params.get('room') || params.get('session_id')

// Fetch token from your backend
useEffect(() => {
  if (livekitUrl && roomName) {
    fetch(`/api/livekit-token?room=${roomName}`)
      .then(res => res.json())
      .then(data => {
        setLivekitToken(data.token)
      })
  }
}, [livekitUrl, roomName])

// Use LiveKit hook instead of WebSocket hook
const { connect, disconnect, isConnected, isConnecting, error } = useLiveKitVoice({
  url: livekitUrl,
  token: livekitToken
})
```

---

## Phase 4: Update n8n Launcher Workflow (Day 2)

### 4.1 Modify Recall.ai Bot Output Media URL
```javascript
// In teams-voice-bot-launcher.json
// Update the output_media.camera URL to include LiveKit params

"output_media": {
  "camera": {
    "kind": "webpage",
    "config": {
      "url": `https://jayconnorsynrg.github.io/synrg-voice-agent-client
        ?livekit_url=wss://your-project.livekit.cloud
        &room=meeting_${session_id}
        &token=${livekit_token}`
    }
  },
  "microphone": {
    "kind": "webpage"
  }
}
```

### 4.2 Add LiveKit Token Generation Node
```javascript
// New Code node before Create Bot
const { AccessToken } = require('livekit-server-sdk')

const apiKey = process.env.LIVEKIT_API_KEY
const apiSecret = process.env.LIVEKIT_API_SECRET

const at = new AccessToken(apiKey, apiSecret, {
  identity: `bot_${$json.session_id}`,
  ttl: '24h'
})

at.addGrant({
  roomJoin: true,
  room: `meeting_${$json.session_id}`,
  canPublish: true,
  canSubscribe: true
})

return [{
  json: {
    ...$input.first().json,
    livekit_token: at.toJwt()
  }
}]
```

---

## Phase 5: Testing & Optimization (Day 3)

### 5.1 Latency Testing Checklist
- [ ] Measure VAD detection time (target: <30ms)
- [ ] Measure STT first word (target: <150ms)
- [ ] Measure LLM TTFT (target: <200ms)
- [ ] Measure TTS first audio (target: <200ms)
- [ ] Measure total round-trip (target: <600ms)

### 5.2 Optimization Techniques
```python
# 1. Pre-warm connections on room join
async def on_room_join():
    # Pre-warm Groq connection
    await groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": "Hi"}],
        max_tokens=1
    )
    # Pre-warm Chatterbox connection
    await chatterbox_client.synthesize(".")

# 2. Parallel processing for tool calls
async def handle_tool_call(tool_call):
    # Start TTS for filler while executing tool
    filler_task = asyncio.create_task(
        tts.synthesize("One moment...")
    )
    result_task = asyncio.create_task(
        execute_tool(tool_call)
    )

    # Stream filler, then result
    async for chunk in filler_task:
        yield chunk

    result = await result_task
    async for chunk in tts.synthesize(result):
        yield chunk

# 3. Speculative execution for common patterns
COMMON_RESPONSES = {
    "yes": "Got it, proceeding now.",
    "no": "Okay, I'll cancel that.",
    "cancel": "Cancelled."
}
```

### 5.3 Monitoring Setup
```python
# Add latency tracking
import time

class LatencyTracker:
    def __init__(self):
        self.stages = {}

    def start(self, stage: str):
        self.stages[stage] = time.perf_counter()

    def end(self, stage: str) -> float:
        elapsed = (time.perf_counter() - self.stages[stage]) * 1000
        print(f"[LATENCY] {stage}: {elapsed:.1f}ms")
        return elapsed

# Usage in agent
tracker = LatencyTracker()

@session.on("user_speech_started")
def on_speech():
    tracker.start("total")
    tracker.start("vad")

@session.on("transcription_received")
def on_transcript(text):
    tracker.end("vad")
    tracker.start("stt")

# ... etc
```

---

## Rollback Plan

If LiveKit pipeline doesn't meet latency targets:

1. **Keep existing relay server** running in parallel
2. **Feature flag** in client to switch between:
   - `?mode=livekit` - New LiveKit pipeline
   - `?mode=openai` - Existing OpenAI Realtime
3. **Gradual migration** - Test with internal users first

---

## Cost Comparison (per minute of voice)

| Service | Current (OpenAI) | Proposed |
|---------|-----------------|----------|
| STT | ~$0.006/min (included) | ~$0.0035/min (Deepgram) |
| LLM | ~$0.01/min | ~$0.001/min (Groq) |
| TTS | ~$0.015/min (included) | ~$0.004/min (Chatterbox) |
| Transport | ~$0.005/min (OpenAI) | ~$0.003/min (LiveKit) |
| **TOTAL** | **~$0.036/min** | **~$0.011/min** |

**Savings: ~70% cost reduction**

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Total latency | <600ms | End-to-end voice round-trip |
| VAD accuracy | >95% | No premature cutoffs |
| STT accuracy | >90% | Word error rate |
| TTS quality | MOS >4.0 | User perception |
| Uptime | >99.5% | Service availability |

---

## NEXT STEPS: Implementation Checklist

### Immediate Actions (Do First)

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ STEP 0: Account Setup (30 min)                                                 │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│ [ ] 1. Sign up for LiveKit Cloud: https://cloud.livekit.io                     │
│        - Create project "voice-agent-production"                               │
│        - Copy LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET                │
│                                                                                │
│ [ ] 2. Sign up for Deepgram: https://console.deepgram.com                      │
│        - Get $200 free credit                                                  │
│        - Copy DEEPGRAM_API_KEY                                                 │
│                                                                                │
│ [ ] 3. Sign up for Groq: https://console.groq.com                              │
│        - Copy GROQ_API_KEY                                                     │
│                                                                                │
│ [ ] 4. TTS Provider (choose one):                                              │
│        - Chatterbox: https://chatterboxtts.com                                 │
│        - OR ElevenLabs: https://elevenlabs.io                                  │
│        - OR Cartesia: https://cartesia.ai (built-in LiveKit plugin)            │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Day 1: Infrastructure + Agent Server

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Create LiveKit Agent Project (2 hours)                                 │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│ [ ] Create project directory:                                                  │
│     mkdir livekit-voice-agent && cd livekit-voice-agent                        │
│                                                                                │
│ [ ] Create files from Phase 2 of this document:                                │
│     - agent.py (main entry point)                                              │
│     - plugins/groq_llm.py (Groq wrapper)                                       │
│     - plugins/chatterbox_tts.py (TTS wrapper)                                  │
│     - tools/email_tool.py (n8n integration)                                    │
│     - requirements.txt                                                         │
│     - Dockerfile                                                               │
│     - railway.json                                                             │
│                                                                                │
│ [ ] Test locally:                                                              │
│     pip install -r requirements.txt                                            │
│     python agent.py dev                                                        │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Deploy to Railway (30 min)                                             │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│ [ ] Initialize Railway project:                                                │
│     railway init                                                               │
│                                                                                │
│ [ ] Set environment variables in Railway Dashboard:                            │
│     LIVEKIT_URL=wss://voice-agent-production.livekit.cloud                     │
│     LIVEKIT_API_KEY=xxx                                                        │
│     LIVEKIT_API_SECRET=xxx                                                     │
│     DEEPGRAM_API_KEY=xxx                                                       │
│     GROQ_API_KEY=xxx                                                           │
│     CHATTERBOX_API_KEY=xxx                                                     │
│     N8N_WEBHOOK_BASE_URL=https://jayconnorexe.app.n8n.cloud/webhook            │
│                                                                                │
│ [ ] Deploy:                                                                    │
│     railway up                                                                 │
│                                                                                │
│ [ ] Verify deployment:                                                         │
│     railway logs                                                               │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Day 2: Client + n8n Updates

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Update Client for LiveKit (2 hours)                                    │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│ [ ] Install LiveKit SDK:                                                       │
│     cd voice-agent-poc/client-v2                                               │
│     npm install livekit-client@^2.0.0                                          │
│                                                                                │
│ [ ] Create new hook:                                                           │
│     - src/hooks/useLiveKitVoice.ts (from Phase 3.2)                            │
│                                                                                │
│ [ ] Update App.tsx:                                                            │
│     - Add LiveKit token fetching                                               │
│     - Switch from useVoice to useLiveKitVoice                                  │
│     - Keep existing code for fallback                                          │
│                                                                                │
│ [ ] Add feature flag:                                                          │
│     - ?mode=livekit → New pipeline                                             │
│     - ?mode=openai → Existing OpenAI Realtime (fallback)                       │
│                                                                                │
│ [ ] Deploy to Vercel:                                                          │
│     vercel --prod                                                              │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ STEP 4: Update n8n Launcher Workflow (1 hour)                                  │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│ [ ] Add LiveKit credentials to n8n environment:                                │
│     - LIVEKIT_API_KEY                                                          │
│     - LIVEKIT_API_SECRET                                                       │
│                                                                                │
│ [ ] Add Code node for token generation (Phase 4.2)                             │
│                                                                                │
│ [ ] Update output_media URL in Recall.ai bot creation:                         │
│     - Add livekit_url param                                                    │
│     - Add room param                                                           │
│     - Add token param                                                          │
│                                                                                │
│ [ ] Test workflow with new parameters                                          │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### Day 3: Testing + Optimization

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ STEP 5: Latency Testing (2 hours)                                              │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│ [ ] Test VAD latency (target: <30ms)                                           │
│ [ ] Test STT latency (target: <150ms)                                          │
│ [ ] Test LLM TTFT (target: <200ms)                                             │
│ [ ] Test TTS latency (target: <200ms)                                          │
│ [ ] Test total round-trip (target: <600ms)                                     │
│                                                                                │
│ [ ] If latency targets not met:                                                │
│     - Check Groq model (try llama-3.1-8b-instant)                              │
│     - Check TTS streaming config                                               │
│     - Consider Cartesia TTS (lower latency)                                    │
│     - Add pre-warming for connections                                          │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────────┐
│ STEP 6: Integration Testing (1 hour)                                           │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│ [ ] Test with Recall.ai in Teams meeting                                       │
│ [ ] Test tool execution (email via n8n)                                        │
│ [ ] Test cancellation flow                                                     │
│ [ ] Test error recovery                                                        │
│ [ ] Verify voice quality acceptable                                            │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure Reference

```
voice-agent-poc/
├── client-v2/                       # Frontend (Vercel)
│   ├── src/
│   │   ├── hooks/
│   │   │   ├── useVoice.ts         # Existing OpenAI hook (keep for fallback)
│   │   │   └── useLiveKitVoice.ts  # NEW: LiveKit hook
│   │   └── App.tsx                 # Updated with mode switching
│   └── package.json                # Add livekit-client
│
├── livekit-voice-agent/             # NEW: LiveKit Agent (Railway)
│   ├── agent.py                    # Main entry point
│   ├── plugins/
│   │   ├── __init__.py
│   │   ├── groq_llm.py            # Groq LLM wrapper
│   │   └── chatterbox_tts.py      # TTS wrapper
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── email_tool.py          # n8n email integration
│   │   └── database_tool.py       # n8n vector DB integration
│   ├── requirements.txt
│   ├── Dockerfile
│   └── railway.json
│
├── n8n-workflows/                   # n8n (existing, update launcher)
│   └── teams-voice-bot-launcher.json
│
├── relay-server/                    # Existing OpenAI Relay (keep for fallback)
│
└── LIVEKIT_IMPLEMENTATION_PLAN.md  # This document
```

---

## Environment Variables Summary

| Location | Variable | Purpose |
|----------|----------|---------|
| **Railway (Agent)** | `LIVEKIT_URL` | LiveKit Cloud WebSocket URL |
| | `LIVEKIT_API_KEY` | LiveKit authentication |
| | `LIVEKIT_API_SECRET` | LiveKit authentication |
| | `DEEPGRAM_API_KEY` | STT service |
| | `GROQ_API_KEY` | LLM service |
| | `CHATTERBOX_API_KEY` | TTS service |
| | `N8N_WEBHOOK_BASE_URL` | n8n webhook endpoint |
| **Vercel (Client)** | `NEXT_PUBLIC_LIVEKIT_URL` | LiveKit Cloud URL for client |
| **n8n Cloud** | `LIVEKIT_API_KEY` | Token generation |
| | `LIVEKIT_API_SECRET` | Token generation |

---

## Quick Reference: Key URLs

| Service | URL | Purpose |
|---------|-----|---------|
| LiveKit Cloud Dashboard | https://cloud.livekit.io | Manage project, API keys |
| Deepgram Console | https://console.deepgram.com | Usage, API keys |
| Groq Console | https://console.groq.com | Usage, API keys |
| Railway Dashboard | https://railway.app | Deploy, logs, env vars |
| Vercel Dashboard | https://vercel.com | Frontend deployment |
| n8n Cloud | https://jayconnorexe.app.n8n.cloud | Workflow management |

---

## Document History

| Date | Change |
|------|--------|
| Jan 2026 | Added cloud-hosted architecture decision |
| Jan 2026 | Documented why self-hosted rejected |
| Jan 2026 | Added comprehensive implementation checklist |
| Jan 2026 | Initial implementation plan created |
