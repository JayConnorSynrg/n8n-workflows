# Voice Agent Implementation Guide

Complete step-by-step guide to deploy the SYNRG Voice Agent with Recall.ai Output Media.

---

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Teams Meeting  │────▶│   Recall.ai     │────▶│  Voice Agent    │
│  (Audio I/O)    │     │   Output Media  │     │  Webpage        │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                        ┌────────────────────────────────┘
                        ▼
              ┌─────────────────┐     ┌─────────────────┐
              │  WebSocket      │────▶│  OpenAI         │
              │  Relay Server   │     │  Realtime API   │
              └─────────────────┘     └─────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  n8n Tool       │
              │  Webhooks       │
              └─────────────────┘
```

---

## Prerequisites

- Node.js 18+
- OpenAI API key with Realtime API access
- Recall.ai account with Output Media enabled
- n8n instance (cloud or self-hosted)
- Static hosting for voice agent webpage (Vercel, Netlify, etc.)

---

## Part 1: Deploy Relay Server

### 1.1 Local Development

```bash
cd relay-server

# Install dependencies
npm install

# Create environment file
cp .env.example .env

# Add your OpenAI API key to .env
# OPENAI_API_KEY=sk-...

# Start in development mode (verbose logging)
npm run dev
```

Server starts on:
- WebSocket: `ws://localhost:3000`
- Health check: `http://localhost:3001/health`

### 1.2 Production Deployment (Railway/Render)

**Railway:**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway add
railway variables set OPENAI_API_KEY=sk-...
railway up
```

**Render:**
1. Connect GitHub repository
2. Set environment variables in dashboard
3. Deploy as Web Service
4. Note the WebSocket URL: `wss://your-app.onrender.com`

### 1.3 Verify Deployment

```bash
# Health check
curl https://your-relay-server.com/health

# Expected response:
# {"status":"healthy","activeConnections":0,"uptime":123.45}
```

---

## Part 2: Deploy Voice Agent Webpage

### 2.1 Local Testing

```bash
cd client

# Serve locally (requires a local server)
npx serve .

# Or with Python
python -m http.server 8080
```

Open browser: `http://localhost:8080?wss=ws://localhost:3000`

### 2.2 Production Deployment (Vercel)

```bash
cd client

# Install Vercel CLI
npm install -g vercel

# Deploy
vercel

# Note the URL: https://your-voice-agent.vercel.app
```

### 2.3 URL Parameters

The voice agent webpage accepts these URL parameters:

| Parameter | Required | Description |
|-----------|----------|-------------|
| `wss` | Yes | WebSocket relay server URL |
| `calendar_webhook` | No | n8n calendar tools webhook base URL |
| `email_webhook` | No | n8n email tools webhook base URL |
| `crm_webhook` | No | n8n CRM tools webhook base URL |
| `knowledge_webhook` | No | n8n knowledge base webhook URL |
| `webhook_secret` | No | Shared secret for webhook auth |
| `debug` | No | Set to `true` to show debug panel |

**Example URL:**
```
https://your-voice-agent.vercel.app?wss=wss://your-relay.onrender.com&calendar_webhook=https://your-n8n.app.n8n.cloud/webhook/calendar&webhook_secret=abc123&debug=true
```

---

## Part 3: Configure Recall.ai Output Media

### 3.1 Create Bot with Output Media

```javascript
// Example: Creating a Recall.ai bot with Output Media
const response = await fetch('https://api.recall.ai/api/v1/bot', {
  method: 'POST',
  headers: {
    'Authorization': 'Token YOUR_RECALL_API_KEY',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    meeting_url: 'https://teams.microsoft.com/l/meetup-join/...',
    bot_name: 'SYNRG Assistant',

    // Output Media configuration
    output_media: {
      camera: {
        kind: 'webpage',
        config: {
          // URL with all parameters
          url: 'https://your-voice-agent.vercel.app?wss=wss://your-relay.onrender.com&calendar_webhook=https://...'
        }
      },
      microphone: {
        // Microphone comes from the same webpage
        kind: 'webpage'
      }
    },

    // Optional: Transcription for logging
    transcription_options: {
      provider: 'default'
    }
  })
});

const bot = await response.json();
console.log('Bot ID:', bot.id);
```

### 3.2 Bot Lifecycle

```javascript
// Check bot status
const status = await fetch(`https://api.recall.ai/api/v1/bot/${botId}`, {
  headers: { 'Authorization': 'Token YOUR_RECALL_API_KEY' }
});

// Remove bot from meeting
await fetch(`https://api.recall.ai/api/v1/bot/${botId}/leave_call`, {
  method: 'POST',
  headers: { 'Authorization': 'Token YOUR_RECALL_API_KEY' }
});
```

---

## Part 4: Create n8n Tool Workflows

### 4.1 Calendar Tools Workflow

Create a webhook workflow in n8n that handles calendar operations:

```
Webhook (POST /calendar/schedule)
  └─▶ Switch (by action)
        ├─▶ schedule ─▶ Google Calendar: Create Event ─▶ Respond
        ├─▶ availability ─▶ Google Calendar: Get Events ─▶ Respond
        └─▶ cancel ─▶ Google Calendar: Delete Event ─▶ Respond
```

**Webhook Configuration:**
- HTTP Method: POST
- Path: `calendar`
- Authentication: Header Auth (`X-Webhook-Secret`)
- Response Mode: Response Node

**Expected Request Format:**
```json
{
  "title": "Meeting Title",
  "attendees": ["email@example.com"],
  "datetime": "2025-01-15T10:00:00Z",
  "duration_minutes": 30,
  "description": "Meeting description"
}
```

**Expected Response Format:**
```json
{
  "success": true,
  "event_id": "abc123",
  "message": "Meeting scheduled for January 15 at 10:00 AM"
}
```

### 4.2 Email Tools Workflow

```
Webhook (POST /email/send)
  └─▶ Gmail: Send Email
        └─▶ Respond with status
```

**Expected Request:**
```json
{
  "to": ["recipient@example.com"],
  "subject": "Email Subject",
  "body": "Email body content",
  "cc": []
}
```

### 4.3 CRM Tools Workflow

```
Webhook (POST /crm/search)
  └─▶ HubSpot/Salesforce: Search Contacts
        └─▶ Format Results
              └─▶ Respond
```

### 4.4 Knowledge Base Workflow

```
Webhook (POST /knowledge/query)
  └─▶ OpenAI: Create Embedding
        └─▶ Pinecone/Supabase: Vector Search
              └─▶ Format Answer
                    └─▶ Respond
```

---

## Part 5: Testing

### 5.1 Component Testing

**Test Relay Server:**
```bash
# Install wscat
npm install -g wscat

# Connect to relay
wscat -c wss://your-relay.onrender.com

# You should see connection established
# (Will close after 30s if no OpenAI session configured)
```

**Test Voice Agent Webpage:**
1. Open with debug mode: `?wss=...&debug=true`
2. Check console for connection status
3. Verify "Connected" status shows green dot

**Test n8n Webhooks:**
```bash
curl -X POST https://your-n8n.app.n8n.cloud/webhook/calendar/schedule \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-secret" \
  -d '{"title":"Test Meeting","datetime":"2025-01-15T10:00:00Z"}'
```

### 5.2 End-to-End Testing

1. **Start a test Teams meeting** (or Zoom/Meet)
2. **Create Recall.ai bot** with Output Media pointing to your voice agent
3. **Verify bot joins** and shows "SYNRG" branding in camera
4. **Say "Hello"** - bot should respond with voice
5. **Test a tool:** "Schedule a meeting for tomorrow at 2pm"
6. **Verify n8n webhook** receives the request

### 5.3 Debugging

**Relay Server Logs:**
```bash
# Set LOG_LEVEL=DEBUG in .env
# Watch for:
# - Browser connections
# - OpenAI connections
# - Message relay events
```

**Voice Agent Debug Panel:**
- Enable with `?debug=true`
- Shows all events in real-time
- Displays connection state changes

**Common Issues:**

| Issue | Solution |
|-------|----------|
| "No server configured" | Add `?wss=...` parameter to URL |
| WebSocket connection fails | Check CORS, verify relay server is running |
| No audio output | Check browser microphone permissions |
| Tools not working | Verify n8n webhook URLs and secret |

---

## Part 6: Latency Optimization

### Expected Latencies

| Component | Latency |
|-----------|---------|
| Audio capture → Relay | ~10-20ms |
| Relay → OpenAI | ~50-100ms |
| OpenAI VAD + STT + LLM | ~200-500ms |
| OpenAI TTS → Relay | ~50-100ms |
| Relay → Browser playback | ~10-20ms |
| **Total (voice only)** | **~320-740ms** |

### Optimization Tips

1. **Deploy relay server close to OpenAI** (US regions)
2. **Use server-side VAD** (already configured)
3. **Keep tool webhooks fast** (<500ms response)
4. **Use streaming responses** for long tool operations

---

## Part 7: Production Checklist

- [ ] Relay server deployed with HTTPS/WSS
- [ ] Voice agent webpage deployed with HTTPS
- [ ] OpenAI API key stored securely (environment variable)
- [ ] Recall.ai API key stored securely
- [ ] n8n webhooks configured with authentication
- [ ] Health monitoring set up for relay server
- [ ] Error alerting configured
- [ ] Rate limiting considered for webhooks
- [ ] Backup/fallback plan for service outages

---

## Quick Reference

**URLs to Configure:**

```
Relay Server:     wss://your-relay.onrender.com
Voice Agent:      https://your-voice-agent.vercel.app
n8n Calendar:     https://your-n8n.app.n8n.cloud/webhook/calendar
n8n Email:        https://your-n8n.app.n8n.cloud/webhook/email
n8n CRM:          https://your-n8n.app.n8n.cloud/webhook/crm
n8n Knowledge:    https://your-n8n.app.n8n.cloud/webhook/knowledge
```

**Full Voice Agent URL:**
```
https://your-voice-agent.vercel.app?wss=wss://your-relay.onrender.com&calendar_webhook=https://your-n8n.app.n8n.cloud/webhook/calendar&email_webhook=https://your-n8n.app.n8n.cloud/webhook/email&webhook_secret=YOUR_SECRET
```
