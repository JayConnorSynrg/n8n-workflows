# Architecture: Teams Voice Bot with Recall.ai

## System Overview

```
Teams Meeting
     |
     v
[Recall.ai Bot] <-- Joins meeting, captures audio
     |
     | WebSocket (real-time transcripts)
     v
[n8n Webhook] POST /transcript
     |
     v
[Filter Code Node] -- Filters for final, non-bot transcripts
     |
     v
[Set Node] -- Extracts: transcript, speaker, bot_id, timestamp
     |
     v
[AI Agent] -- GPT-4o-mini with conversation memory
     |
     v
[Code Node] -- Prepares audio response payload
     |
     v
[Respond to Webhook] -- Returns status to Recall.ai
     |
     | (External Service handles actual audio)
     v
[XTTS-v2 WebSocket] -- Text-to-speech synthesis
     |
     v
[Recall.ai Send Audio] -- Injects audio into meeting
```

## Component Details

### 1. Recall.ai ($0.70/hr)
- **Real-time Endpoint**: WebSocket connection for bi-directional audio
- **Transcription**: Automatic speech-to-text with speaker identification
- **Audio Injection**: Send synthesized speech back to meeting

### 2. n8n Workflow
- **Webhook Trigger**: Receives transcript events from Recall.ai
- **Filter Node**: Only processes final transcripts from non-bot speakers
- **AI Agent**: Generates contextual responses using GPT-4o-mini
- **Memory**: Buffer window memory for conversation continuity

### 3. External Voice Service (Required)
The n8n workflow cannot maintain persistent WebSocket connections. An external service is required:

```javascript
// External service responsibilities:
// 1. Connect to XTTS-v2 WebSocket
// 2. Receive text from n8n response
// 3. Stream audio to Recall.ai
```

See `../scripts/external-voice-service.js` for implementation template.

### 4. XTTS-v2 (Docker + GPU)
- **Container**: `ghcr.io/coqui-ai/xtts-streaming-server:latest`
- **Endpoint**: `ws://localhost:8000/stream`
- **Latency**: <200ms for first audio chunk

## Data Flow

### Incoming (Transcript Event)
```json
{
  "event": "transcript.data",
  "bot_id": "abc123",
  "data": {
    "is_final": true,
    "speaker_name": "John Doe",
    "words": [
      {"text": "Hello", "start_time": 0.0, "end_time": 0.5},
      {"text": "everyone", "start_time": 0.5, "end_time": 1.0}
    ]
  }
}
```

### Outgoing (Response)
```json
{
  "success": true,
  "action": "audio_queued",
  "responseText": "Hello John! How can I help you today?",
  "timestamp": "2025-12-13T22:15:00.000Z"
}
```

## Latency Budget

| Stage | Target | Actual |
|-------|--------|--------|
| Webhook receive | <100ms | TBD |
| Filter + Extract | <50ms | TBD |
| AI Response | <2000ms | TBD |
| TTS Synthesis | <500ms | TBD |
| Audio Injection | <300ms | TBD |
| **Total** | **<3000ms** | TBD |

## Deployment Checklist

- [ ] n8n workflow activated
- [ ] OpenAI API key configured in n8n
- [ ] Recall.ai API key obtained
- [ ] Real-time endpoint created in Recall.ai
- [ ] XTTS-v2 Docker container running with GPU
- [ ] External voice service deployed
- [ ] Test with sample transcript payload
