# Teams Voice Bot with Recall.ai

**Workflow ID:** `gjYSN6xNjLw8qsA1`
**n8n URL:** https://jayconnorexe.app.n8n.cloud/workflow/gjYSN6xNjLw8qsA1
**Created:** 2025-12-13
**Updated:** 2025-12-13
**Status:** Ready for Testing (0 errors, 8 advisory warnings)

## Purpose

Real-time conversational voice bot for Microsoft Teams meetings using:
- **Recall.ai** - Meeting bot API ($0.70/hr) with real-time webhook transcription
- **n8n AI Agent** - Conversational LLM (GPT-4o-mini) with buffer memory
- **XTTS-v2** - Text-to-speech via HTTP endpoint (returns MP3)

## Architecture

```
Recall.ai Bot → Webhook → Filter → Extract → AI Agent → TTS → output_audio → Respond
                                              ↑    ↑
                                         GPT-4o   Memory
```

See [docs/architecture.md](./docs/architecture.md) for detailed flow.

## Workflow Nodes (11 total)

| Node | Type | Purpose |
|------|------|---------|
| Receive Transcript | Webhook | POST /transcript endpoint |
| Filter Final Transcripts | Code | Only is_final=true, non-bot speakers |
| Extract Transcript Data | Set | Parse transcript, speaker, bot_id |
| AI Voice Assistant | AI Agent | Generate conversational response |
| OpenAI GPT-4 | LM Chat | GPT-4o-mini with temp 0.7 |
| Conversation Memory | Buffer | 10-message context window |
| Generate TTS Audio | HTTP Request | POST to XTTS-v2, returns MP3 |
| Send Audio to Recall.ai | HTTP Request | POST /output_audio with MP3 base64 |
| Respond OK | Respond | Returns {status: "received"} |

## API Integration

### Recall.ai Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/bot/` | POST | Create bot (external - before workflow) |
| `/api/v1/bot/{id}/output_audio/` | POST | Send MP3 audio to meeting |

See [docs/api-reference.md](./docs/api-reference.md) for full API documentation.

### Key Discovery: Audio Format

Recall.ai's `output_audio` endpoint requires **MP3 format** (base64-encoded), not raw PCM or WebSocket streaming. The workflow uses XTTS-v2 HTTP endpoint that returns MP3 files.

## Environment Variables Required

```env
RECALL_API_KEY=Token your_recall_api_key
OPENAI_API_KEY=sk-...
```

## Pre-Requisites

1. **Recall.ai Account** with API access
2. **XTTS-v2 Docker** running with HTTP endpoint:
   ```bash
   docker run --gpus all -p 8000:8000 ghcr.io/coqui-ai/xtts-streaming-server:latest
   ```
3. **OpenAI API Key** configured in n8n

## Bot Creation (Before Workflow)

Create a Recall.ai bot with this configuration:

```json
POST https://us-west-2.recall.ai/api/v1/bot/
{
  "meeting_url": "https://teams.microsoft.com/l/meetup-join/...",
  "bot_name": "AI Voice Assistant",
  "recording_config": {
    "transcript": {
      "provider": {
        "recallai_streaming": {
          "mode": "prioritize_low_latency"
        }
      }
    },
    "realtime_endpoints": [{
      "type": "webhook",
      "url": "https://jayconnorexe.app.n8n.cloud/webhook/transcript",
      "events": ["transcript.data"]
    }]
  },
  "automatic_audio_output": {
    "in_call_recording": {
      "data": {
        "kind": "mp3",
        "b64_data": "SILENT_MP3_BASE64_PLACEHOLDER"
      }
    }
  }
}
```

## Testing

See [docs/testing.md](./docs/testing.md) for test payloads and procedures.

## Latency Budget

| Stage | Target |
|-------|--------|
| Webhook receive | <100ms |
| Filter + Extract | <50ms |
| AI Response | <2000ms |
| TTS Synthesis | <500ms |
| Audio POST | <300ms |
| **Total** | **<3000ms** |

## Sources

- [Recall.ai Bot Real-time Transcription](https://docs.recall.ai/docs/bot-real-time-transcription)
- [Recall.ai Output Audio](https://docs.recall.ai/docs/output-audio-in-meetings)
- [Recall.ai Send AI Agents to Meetings](https://docs.recall.ai/docs/stream-media)
