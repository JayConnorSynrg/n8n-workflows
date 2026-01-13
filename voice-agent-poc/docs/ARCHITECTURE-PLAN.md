# Voice Agent Architecture Plan
## n8n + Recall.ai Output Media + OpenAI Realtime API

**Date:** 2026-01-10
**Status:** Implementation Ready

---

## Executive Summary

This architecture replaces the current webhook-based Teams Voice Bot (~11s latency) with a **bidirectional streaming architecture** using Recall.ai's Output Media API (<500ms latency).

**Key Innovation:** n8n shifts from being the voice pipeline to being the **tool executor** that the voice agent calls for actions (calendar, email, CRM, etc.).

---

## Current vs Proposed Architecture

### Current Architecture (Webhook-Based) - ~11s Latency

```
Teams Meeting
     │
     ▼
Recall.ai Bot (webhook transcription)
     │ HTTP POST (1-10 sec batches)
     ▼
n8n Workflow (d3CxEaYk5mkC8sLo)
├── Pre-Router (routing logic)
├── Intent Classification
├── Orchestrator Agent
└── Response via Recall.ai API
     │
     ▼ (Response delay: 3-11 seconds)
Teams Meeting
```

**Problems:**
- Webhook batching adds 1-10 seconds
- HTTP request/response cycle adds latency
- No real-time interruption handling
- Duplicate detection complexity

---

### Proposed Architecture (Output Media) - <500ms Latency

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TEAMS MEETING                                 │
│  ┌─────────────┐                              ┌─────────────┐       │
│  │ Participant │ ◄──── Audio ────►            │ Recall Bot  │       │
│  │   (User)    │                              │  (Camera)   │       │
│  └─────────────┘                              └──────┬──────┘       │
└─────────────────────────────────────────────────────│───────────────┘
                                                      │
                            Recall.ai Output Media API│
                            (Webpage rendered as camera)
                                                      │
┌─────────────────────────────────────────────────────▼───────────────┐
│                     VOICE AGENT WEBPAGE                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                                                               │  │
│  │  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐ │  │
│  │  │ WavRecorder │───►│ WebSocket    │───►│ OpenAI Realtime │ │  │
│  │  │ (Mic Input) │    │ Client       │    │ API             │ │  │
│  │  └─────────────┘    └──────────────┘    └────────┬────────┘ │  │
│  │                                                   │          │  │
│  │  ┌─────────────┐    ┌──────────────┐             │          │  │
│  │  │ WavPlayer   │◄───│ Audio Delta  │◄────────────┘          │  │
│  │  │ (Speaker)   │    │ Handler      │                        │  │
│  │  └─────────────┘    └──────────────┘                        │  │
│  │                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────┐│  │
│  │  │ Tool Executor (Calls n8n for actions)                   ││  │
│  │  │ • Calendar operations    → n8n webhook                  ││  │
│  │  │ • Email operations       → n8n webhook                  ││  │
│  │  │ • CRM operations         → n8n webhook                  ││  │
│  │  │ • Knowledge base queries → n8n webhook                  ││  │
│  │  └─────────────────────────────────────────────────────────┘│  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Tool calls only (not voice)
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         N8N WORKFLOWS                                │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │ Calendar Tools │  │ Email Tools    │  │ CRM Tools      │        │
│  │ Webhook        │  │ Webhook        │  │ Webhook        │        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │
│  │ Knowledge Base │  │ Meeting Notes  │  │ Action Items   │        │
│  │ Webhook        │  │ Webhook        │  │ Webhook        │        │
│  └────────────────┘  └────────────────┘  └────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Voice Agent Webpage (New - PoC)

**Purpose:** Real-time voice interface rendered inside Recall.ai bot's camera

**Technology Stack:**
- React/Vanilla JS
- WebSocket client for OpenAI Realtime API
- WavTools library for audio capture/playback
- Function calling for n8n tool integration

**Key Features:**
- Server-side VAD (Voice Activity Detection)
- Continuous audio streaming (no batching)
- Interruption handling
- Visual connection status indicator

**Latency Targets:**
| Metric | Target | How Achieved |
|--------|--------|--------------|
| Speech-to-first-response | <500ms | Server-side VAD |
| Audio frame size | 200ms | LiveKit pattern |
| Interruption response | <100ms | Cancel in-flight responses |

---

### 2. WebSocket Relay Server (New)

**Purpose:** Bridge between webpage and OpenAI Realtime API (handles API key security)

**Why Needed:**
- Browser can't securely store OpenAI API key
- Relay handles authentication server-side
- Enables message queuing during connection establishment

**Deployment Options:**
1. **Node.js on Railway/Render** (Recommended for PoC)
2. AWS Lambda + API Gateway WebSocket
3. Cloudflare Workers (Durable Objects)

---

### 3. n8n Tool Workflows (Modified Role)

**Old Role:** Voice pipeline processor (routing, intent, response generation)
**New Role:** Tool executor for specific actions

**n8n Workflow Changes:**

| Workflow | Old Purpose | New Purpose |
|----------|-------------|-------------|
| Teams Voice Bot v3.0 | Full voice pipeline | **Archive/Deprecate** |
| Calendar Tools | N/A | **NEW:** Book, cancel, reschedule meetings |
| Email Tools | N/A | **NEW:** Send, read, summarize emails |
| CRM Tools | N/A | **NEW:** Update contacts, log interactions |
| Knowledge Base | N/A | **NEW:** RAG queries for company data |

**n8n Webhook Pattern for Tools:**

```javascript
// OpenAI Realtime API tool definition
{
  type: "function",
  name: "schedule_meeting",
  description: "Schedule a meeting on the user's calendar",
  parameters: {
    type: "object",
    properties: {
      title: { type: "string" },
      attendees: { type: "array", items: { type: "string" } },
      datetime: { type: "string", format: "date-time" },
      duration_minutes: { type: "integer" }
    },
    required: ["title", "datetime"]
  }
}

// When tool is called, webpage POSTs to n8n:
fetch("https://n8n.example.com/webhook/calendar/schedule", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    title: "Project Review",
    attendees: ["bob@example.com"],
    datetime: "2026-01-15T14:00:00Z",
    duration_minutes: 30
  })
});
```

---

## Data Flow Diagram

```
User speaks in Teams meeting
          │
          │ Audio captured by Recall.ai
          ▼
┌─────────────────────────────────────────────────────────────┐
│ Recall.ai Output Media                                       │
│ • Captures room audio                                        │
│ • Feeds to bot's microphone input                           │
│ • Bot's camera shows webpage                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │ Audio stream (PCM16, 24kHz)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ Voice Agent Webpage                                          │
│                                                              │
│ 1. WavRecorder captures audio                               │
│ 2. Streams to WebSocket relay                               │
│ 3. Relay forwards to OpenAI Realtime API                    │
│ 4. OpenAI server-side VAD detects speech end                │
│ 5. OpenAI generates response (text + audio)                 │
│ 6. Audio deltas streamed back                               │
│ 7. WavStreamPlayer outputs audio                            │
│                                                              │
│ If tool call needed:                                         │
│ 8. OpenAI emits function_call event                         │
│ 9. Webpage calls n8n webhook                                │
│ 10. n8n executes action, returns result                     │
│ 11. Webpage sends tool_result to OpenAI                     │
│ 12. OpenAI continues with result context                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Latency Comparison

| Stage | Current (Webhook) | Proposed (Output Media) |
|-------|-------------------|-------------------------|
| Audio capture | ~100ms | ~20ms |
| Transcription batching | 1-10s | 0ms (streaming) |
| Network to AI | ~100ms | ~50ms |
| AI processing | ~500ms | ~300ms |
| Response generation | ~200ms | ~100ms (streaming) |
| Audio playback | ~100ms | ~50ms |
| **Total** | **3-11 seconds** | **300-500ms** |

---

## Implementation Phases

### Phase 1: Core Voice Agent (Week 1)

**Deliverables:**
1. ✅ Architecture plan (this document)
2. Voice agent webpage (React)
3. WebSocket relay server (Node.js)
4. Recall.ai bot creation script

**Success Criteria:**
- Bot joins meeting
- User speaks, bot responds via voice
- Latency < 1 second
- Interruption handling works

### Phase 2: n8n Tool Integration (Week 2)

**Deliverables:**
1. Calendar tools workflow
2. Email tools workflow
3. Tool definitions in OpenAI session
4. Tool result handling in webpage

**Success Criteria:**
- "Schedule a meeting" triggers n8n workflow
- Meeting actually created in calendar
- Bot confirms action vocally

### Phase 3: Production Hardening (Week 3)

**Deliverables:**
1. Error recovery and reconnection
2. Conversation memory/context
3. Multi-participant handling
4. Logging and monitoring

**Success Criteria:**
- 99% uptime during meetings
- Graceful degradation on errors
- Full conversation transcripts saved

---

## n8n Tool Workflow Templates

### Calendar Tools Workflow

```
Webhook Trigger (/webhook/calendar/{action})
     │
     ├── action = "schedule"
     │   └── Google Calendar: Create Event
     │
     ├── action = "cancel"
     │   └── Google Calendar: Delete Event
     │
     ├── action = "reschedule"
     │   └── Google Calendar: Update Event
     │
     └── action = "check_availability"
         └── Google Calendar: Get Free/Busy
     │
     ▼
Respond to Webhook (JSON result)
```

### Email Tools Workflow

```
Webhook Trigger (/webhook/email/{action})
     │
     ├── action = "send"
     │   └── Gmail: Send Email
     │
     ├── action = "read_recent"
     │   └── Gmail: Get Messages
     │
     └── action = "summarize"
         └── Gmail: Get Message → OpenAI: Summarize
     │
     ▼
Respond to Webhook (JSON result)
```

---

## Security Considerations

### API Key Management

| Key | Where Stored | Access |
|-----|--------------|--------|
| OpenAI API Key | Relay server env | Server-side only |
| Recall.ai Token | n8n credentials | n8n workflows only |
| n8n Webhook URLs | Webpage config | Public (but authenticated) |

### Webhook Authentication

```javascript
// n8n webhook with header authentication
{
  "authentication": "headerAuth",
  "headerAuth": {
    "name": "X-Webhook-Secret",
    "value": "{{$env.WEBHOOK_SECRET}}"
  }
}

// Webpage includes secret in tool calls
fetch(webhookUrl, {
  headers: {
    "X-Webhook-Secret": WEBHOOK_SECRET
  }
});
```

---

## Files to Create

```
voice-agent-poc/
├── client/
│   ├── index.html          # Main webpage
│   ├── app.js              # Voice agent logic
│   ├── lib/
│   │   └── wavtools.js     # Audio utilities
│   └── styles.css          # UI styling
├── relay-server/
│   ├── index.js            # Node.js relay
│   ├── package.json        # Dependencies
│   └── .env.example        # Environment template
├── n8n-workflows/
│   ├── calendar-tools.json # Calendar workflow export
│   └── email-tools.json    # Email workflow export
└── docs/
    ├── ARCHITECTURE-PLAN.md (this file)
    ├── DEPLOYMENT-GUIDE.md
    └── RECALL-BOT-SETUP.md
```

---

## Next Steps

1. **Build voice agent webpage** (index.html + app.js)
2. **Build WebSocket relay server** (Node.js)
3. **Test locally** with ngrok
4. **Create Recall.ai bot** pointing to deployed webpage
5. **Create n8n tool workflows** (calendar, email)
6. **End-to-end test** in Teams meeting

---

## References

- [Recall.ai Output Media API](https://docs.recall.ai/docs/output-media)
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- [LiveKit Agents TTS Patterns](./LIVEKIT_TTS_PATTERNS.md)
- [Teams Voice Bot v3.0 Architecture](./workflows/teams-voice-bot/ARCHITECTURE-PLAN.md)
