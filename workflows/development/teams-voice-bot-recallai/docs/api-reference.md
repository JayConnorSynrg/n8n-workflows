# Recall.ai API Reference

## API Base URL

```
https://us-west-2.recall.ai/api/v1/
```

## Authentication

All requests require an Authorization header:
```
Authorization: Token YOUR_RECALL_API_KEY
```

---

## 1. Create Bot

**Endpoint:** `POST /api/v1/bot/`

Creates a bot that joins a meeting and starts real-time transcription.

### Request Body

```json
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
    "realtime_endpoints": [
      {
        "type": "webhook",
        "url": "https://your-n8n-instance.com/webhook/transcript",
        "events": ["transcript.data", "transcript.partial_data"]
      }
    ]
  },
  "automatic_audio_output": {
    "in_call_recording": {
      "data": {
        "kind": "mp3",
        "b64_data": "SILENT_MP3_PLACEHOLDER_BASE64"
      }
    }
  }
}
```

### Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `meeting_url` | string | Full meeting URL (Teams, Zoom, Meet, Webex) |
| `bot_name` | string | Display name for the bot in the meeting |
| `recording_config.transcript.provider` | object | Transcription provider config |
| `recording_config.realtime_endpoints` | array | Webhook/WebSocket endpoints for events |
| `automatic_audio_output` | object | **Required** to use output_audio endpoint |

### Transcription Modes

| Mode | Latency | Use Case |
|------|---------|----------|
| `prioritize_low_latency` | 1-3 seconds | Real-time voice assistants |
| `prioritize_accuracy` | 3-10 minutes | Post-call transcription |

### Response

```json
{
  "id": "bot_abc123",
  "status_changes": [...],
  "meeting_url": "...",
  "bot_name": "AI Voice Assistant"
}
```

---

## 2. Output Audio

**Endpoint:** `POST /api/v1/bot/{bot_id}/output_audio/`

Sends audio to the meeting through the bot's microphone.

### Prerequisites

- Bot must have `automatic_audio_output` configured in Create Bot request
- Audio must be MP3 format, base64 encoded

### Request Body

```json
{
  "kind": "mp3",
  "b64_data": "//uQxAAAAAANIAAAAAExBTUUzLjEwMFVVVVVV..."
}
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `kind` | string | Audio format (only `"mp3"` supported) |
| `b64_data` | string | Base64-encoded MP3 audio (RFC 4648 Section 4) |

### Response

```json
{
  "success": true
}
```

### Converting Audio to Base64

```bash
# Using ffmpeg + base64
ffmpeg -i input.wav -acodec libmp3lame output.mp3
base64 -i output.mp3 -o output.b64

# In n8n (from binary data)
{{ $binary.data.toString('base64') }}
```

---

## 3. Real-Time Webhook Events

### transcript.data Event

Sent when a final transcript segment is available.

```json
{
  "event": "transcript.data",
  "bot_id": "bot_abc123",
  "data": {
    "is_final": true,
    "speaker_name": "John Doe",
    "words": [
      {"text": "Hello", "start_time": 0.0, "end_time": 0.3},
      {"text": "everyone", "start_time": 0.3, "end_time": 0.7}
    ],
    "confidence": 0.95
  }
}
```

### transcript.partial_data Event

Sent for intermediate (not-yet-final) transcription results.

```json
{
  "event": "transcript.partial_data",
  "bot_id": "bot_abc123",
  "data": {
    "is_final": false,
    "speaker_name": "Jane Smith",
    "words": [
      {"text": "I", "start_time": 0.0, "end_time": 0.1},
      {"text": "think", "start_time": 0.1, "end_time": 0.3}
    ]
  }
}
```

### Participant Events

```
participant_events.join
participant_events.leave
participant_events.speech_on
participant_events.speech_off
```

---

## 4. Webhook Security

### Cryptographic Signature

Add a secret to your Recall.ai workspace to receive signed headers:

```
X-Recall-Signature: sha256=abc123...
```

### Query Parameter Token

Include token in webhook URL:
```
https://your-app.com/webhook?token=secret123
```

---

## Pricing

| Feature | Cost |
|---------|------|
| Bot hours | $0.70/hour |
| Recall.ai Transcription | $0.15/hour |

---

## Platform Support

| Platform | Supported |
|----------|-----------|
| Microsoft Teams | Yes |
| Zoom | Yes |
| Google Meet | Yes |
| Cisco Webex | Yes |
| Slack Huddles | No |

---

## Sources

- [Bot Real-time Transcription](https://docs.recall.ai/docs/bot-real-time-transcription)
- [Real-Time Webhook Endpoints](https://docs.recall.ai/docs/real-time-webhook-endpoints)
- [Send AI Agents to Meetings](https://docs.recall.ai/docs/stream-media)
- [Output Audio in Meetings](https://docs.recall.ai/docs/output-audio-in-meetings)
