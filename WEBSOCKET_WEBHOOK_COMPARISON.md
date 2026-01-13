# WebSocket vs Webhook Architecture for Voice Bots

Based on Recall.ai voice-agent-demo implementation and Teams integration requirements.

---

## EXECUTIVE SUMMARY

| Aspect | WebSocket | Webhook |
|--------|-----------|---------|
| **Use Case** | Real-time voice streaming | Asynchronous event notifications |
| **Connection Model** | Persistent bidirectional | Request/response HTTP |
| **Latency** | 50-200ms | 500-2000ms |
| **Voice Streaming** | ✓ Supported | ✗ Not suitable |
| **Message Ordering** | Guaranteed | Best-effort |
| **Scalability** | Per-connection cost | Per-request cost |
| **Implementation** | WebSocket library | HTTP server |
| **Recall.ai Usage** | ✓ For realtime API | ✓ For event callbacks |

**Bottom Line:** Recall.ai uses **WebSocket exclusively** for real-time voice because webhooks are too slow and incompatible with continuous audio streaming.

---

## 1. WEBSOCKET ARCHITECTURE (Implemented in Recall.ai Demo)

### Connection Model
```
[Browser Client]
      ↓ (WebSocket open)
[Relay Server] ← Single persistent connection
      ↓ (WebSocket open)
[OpenAI Realtime API]
```

### Why WebSocket for Voice

**1. Bidirectional Streaming**
```javascript
// Browser → Server (microphone audio)
client.appendInputAudio(data.mono);

// Server → Browser (response audio)
wavStreamPlayer.add16BitPCM(delta.audio, item.id);

// Same connection, no request/response cycle
```

**2. Low Latency**
- Network RTT: ~50-100ms
- No HTTP header overhead
- No connection establishment per message
- **Total latency: 200-400ms voice-to-response**

**3. Continuous Streaming**
```javascript
// 50-100 small messages per second (one per audio frame)
// With HTTP, would be 50-100 separate requests/responses = impractical

// With WebSocket: single open pipe
client.appendInputAudio(audioFrame);  // Send immediately
client.appendInputAudio(nextFrame);   // Send immediately
```

**4. Server Push Capability**
```javascript
// Server can push audio chunks the moment they're ready
// No need to wait for client to poll

client.realtime.on("server.*", (event) => {
  // Server pushes ALL events, including audio deltas
  ws.send(JSON.stringify(event));
});
```

### Implementation Pattern (From Recall.ai)

**Node.js:**
```javascript
const wss = new WebSocketServer({ port: 3000 });

wss.on("connection", async (ws) => {
  const client = new RealtimeClient({ apiKey: OPENAI_API_KEY });

  // Bidirectional relay
  client.realtime.on("server.*", (event) => {
    ws.send(JSON.stringify(event));  // OpenAI → Browser
  });

  ws.on("message", (data) => {
    client.realtime.send(JSON.parse(data).type, event);  // Browser → OpenAI
  });

  await client.connect();
});
```

**Python:**
```python
async def handle_browser_connection(websocket, path):
  openai_ws, session = await connect_to_openai()

  async def relay_browser_to_openai():
    async for message in websocket:
      await openai_ws.send(message)

  async def relay_openai_to_browser():
    async for message in openai_ws:
      await websocket.send(message)

  # Run both simultaneously
  await asyncio.gather(
    relay_browser_to_openai(),
    relay_openai_to_browser()
  )
```

### Connection Lifecycle
```
1. Client opens WebSocket to Relay
2. Relay opens WebSocket to OpenAI
3. OpenAI sends session.created
4. Relay forwards to Client
5. Client sends session.update
6. Relay forwards to OpenAI
7. Client sends audio chunks continuously
8. Relay forwards each chunk to OpenAI
9. OpenAI sends audio deltas continuously
10. Relay forwards each delta to Client
11. [Repeat 7-10 until conversation ends]
12. Client closes WebSocket
13. Relay closes OpenAI connection
```

### Reliability & Recovery
```javascript
// Message queue during connection setup
const messageQueue = [];

ws.on("message", (data) => {
  if (!client.isConnected()) {
    messageQueue.push(data);  // Don't lose early messages
  } else {
    client.realtime.send(JSON.parse(data).type, data);
  }
});

// Process queue once connected
while (messageQueue.length) {
  messageHandler(messageQueue.shift());
}
```

### Keepalive & Heartbeat
```python
# Python: Prevent idle timeouts
async with serve(
    handler,
    "0.0.0.0",
    PORT,
    ping_interval=20,      # Send ping every 20 seconds
    ping_timeout=20,       # Expect pong within 20 seconds
):
    pass
```

---

## 2. WEBHOOK ARCHITECTURE (NOT Used for Voice)

### Connection Model
```
[Event Happens] → [Recall.ai]
                      ↓ (HTTP POST)
                [Your Server]
                      ↓ (HTTP Response)
                  [Done]
```

### Why NOT Webhooks for Real-Time Voice

**Problem 1: Audio Can't Stream**
```
// Webhook limitation: Each request → Response
Request 1:  [Send 20ms audio chunk 1]
Response 1: [Received]

Request 2:  [Send 20ms audio chunk 2]
Response 2: [Received]

// With 100 frames/second = 100 HTTP requests/second
// Each request = 200-500ms overhead
// IMPOSSIBLE for real-time voice
```

**Problem 2: Server Can't Push Data**
```
// Webhooks are one-way: service → your server
// Can't send audio from server back to meeting

// Would need second mechanism (polling)
// GET /audio/next → [Return audio chunk]
// GET /audio/next → [Return next chunk]
// = 200 requests/second = impractical
```

**Problem 3: Latency Unbearable**
```
User speaks at t=0
→ Audio frames received by Recall.ai
→ HTTP POST to your server (50-100ms)
→ Your server processes, calls OpenAI (50-100ms)
→ OpenAI returns response (100-300ms)
→ Your server HTTP POSTs back to Recall.ai (50-100ms)
→ Recall.ai plays audio (10-20ms)
= Total: 300-600ms minimum per turn
= User perceives delay as awkward silence
```

**Problem 4: Message Ordering**
- Webhooks can arrive out of order
- Critical for audio frame sequencing

---

## 3. HYBRID APPROACH: WebSocket + Webhook

**Recommended for Teams Bot:**

```
┌─────────────────────────────────────────┐
│         Teams Meeting                    │
│  (Recall.ai bot with video feed)        │
└─────────────────────────────────────────┘
              ↓ (Meeting audio)
      ┌───────────────────────┐
      │   Recall.ai Bot       │
      │   (Managed service)   │
      └───────────────────────┘
         ↓ (WebSocket for audio)
      ┌───────────────────────┐
      │   Client Browser      │
      │   (Displays status)   │
      └───────────────────────┘
         ↓ (WebSocket relay)
      ┌───────────────────────┐
      │   Relay Server        │
      │   (Node.js/Python)    │
      └───────────────────────┘
         ↓ (WebSocket audio)
      ┌───────────────────────┐
      │   OpenAI Realtime     │
      │   API                 │
      └───────────────────────┘

Additionally:

Bot Events → [HTTP Webhook] → Your backend
- "bot_joined" event
- "bot_left" event
- "meeting_ended" event
→ Store in database
→ Generate summary
→ Send email notification
```

### WebSocket: Real-time Audio
```javascript
// This MUST be WebSocket for voice
const relayServer = new WebSocketServer({ port: 3000 });
relayServer.on("connection", async (ws) => {
  const openai = new RealtimeClient({ apiKey: OPENAI_API_KEY });
  // Relay audio streams...
});
```

### Webhook: Async Events
```python
# This can be webhook for non-real-time events
@app.post("/webhook/recall-events")
async def handle_recall_event(event: dict):
    if event["type"] == "bot.ended":
        # Generate summary
        summary = await openai.generate_summary(event["transcript"])
        # Store in database
        db.save_meeting(event["meeting_id"], summary)
        # Send notification
        send_email_notification(event["user_email"], summary)
    return {"status": "received"}
```

---

## 4. DETAILED COMPARISON TABLE

### Performance Metrics

| Metric | WebSocket | Webhook |
|--------|-----------|---------|
| Connection Overhead | ~50ms (one-time) | ~50-100ms per request |
| Latency per Message | 20-50ms | 200-500ms |
| Messages/Second | 100+ sustainable | 10 max (realistically) |
| Voice Quality @ 24kHz | Excellent | Impossible |
| Two-way Communication | Native | Requires polling |
| Server Push Capability | Native | None (polling required) |
| Scaling (1000 connections) | ~50MB RAM | Would need 10,000 HTTP connections |
| Typical RTT | 50-100ms | 200-500ms |

### Operational Characteristics

| Aspect | WebSocket | Webhook |
|--------|-----------|---------|
| Protocol | TCP/WebSocket | HTTP/HTTPS |
| Default Port | 80 (WS) / 443 (WSS) | 443 (HTTPS) |
| Firewall Friendly | ✓ (passes through proxies) | ✓ (standard HTTPS) |
| Load Balancing | Sticky sessions required | Stateless (easy) |
| Authentication | Custom header | Basic/Bearer token |
| Monitoring | netstat, tcpdump | HTTP logs |
| Debugging | Browser DevTools | HTTP proxy tools |
| Recovery | Auto-reconnect on disconnect | Retry logic needed |
| Ordering Guarantee | ✓ In-order delivery | ✗ Best-effort |

---

## 5. RECALL.AI SPECIFIC PATTERNS

### How Recall.ai Captures Audio
```
Teams Meeting → Recall.ai SDK
                     ↓
            (Captures room audio)
                     ↓
            (Sends to browser page)
                     ↓
         (Browser accesses microphone stream)
                     ↓
         client.appendInputAudio(stream)
                     ↓
         (Relay sends to OpenAI)
```

### How Recall.ai Outputs Audio
```
OpenAI Response Audio
      ↓
 (Relay receives)
      ↓
 (Browser client plays)
      ↓
 (Played through bot's speakers)
      ↓
(Visible in Teams meeting)
```

### Webhook Events (If Using Recall.ai Callbacks)
```json
{
  "type": "bot.joined",
  "event_id": "evt_xxx",
  "bot_id": "bot_xxx",
  "meeting_id": "meet_xxx",
  "meeting_url": "https://teams.microsoft.com/...",
  "timestamp": "2025-01-10T10:00:00Z"
}
```

```json
{
  "type": "bot.left",
  "event_id": "evt_xxx",
  "bot_id": "bot_xxx",
  "reason": "meeting_ended",
  "transcript": "...",
  "metadata": {...}
}
```

**Webhook Handler (Only for events, NOT for audio):**
```python
@app.post("/webhook/recall")
async def handle_recall_webhook(event: dict):
    if event["type"] == "bot.joined":
        logger.info(f"Bot joined: {event['meeting_id']}")
        # Start tracking
        db.create_session(event["bot_id"], event["meeting_id"])

    elif event["type"] == "bot.left":
        # Store results
        db.save_meeting_data(
            event["bot_id"],
            transcript=event.get("transcript"),
            duration=event.get("duration")
        )
        # Generate summary
        summary = await summarize_transcript(event.get("transcript"))
        # Send notification
        notify_user(summary)

    return {"status": "ok"}
```

---

## 6. IMPLEMENTATION DECISION FLOWCHART

```
┌─────────────────────────────────────────────────┐
│ Do you need real-time voice streaming?          │
└─────────────────────────────────────────────────┘
                        ↓
                   YES / NO
                   /       \
                  /         \
               YES            NO
                ↓              ↓
          ┌─────────┐    ┌──────────┐
          │WebSocket│    │Webhook   │
          │Required │    │OK        │
          └─────────┘    └──────────┘
```

---

## 7. PRODUCTION SETUP COMPARISON

### WebSocket Setup (Relay Server)
```bash
# 1. Deploy relay server
docker run -e OPENAI_API_KEY=sk-... relay-server

# 2. Expose via ngrok or cloud service
ngrok http 3000
→ wss://relay.example.com

# 3. Client connects to relay
# https://frontend.com?wss=wss://relay.example.com

# 4. Relay bridges to OpenAI
# wss://api.openai.com/v1/realtime?model=gpt-4o-realtime
```

### Webhook Setup (Event Handler)
```bash
# 1. Create HTTP endpoint in your backend
@app.post("/webhook/recall")
async def handle_event(event: dict):
    # Process event
    return {"status": "ok"}

# 2. Register with Recall.ai
curl https://recall.ai/api/webhooks \
  -H "Authorization: Bearer $RECALL_TOKEN" \
  -d '{
    "url": "https://yourserver.com/webhook/recall",
    "events": ["bot.joined", "bot.left", "meeting_ended"]
  }'

# 3. Recall.ai will POST events to your endpoint
```

---

## 8. ARCHITECTURE DIAGRAMS

### Option A: Pure WebSocket (Voice + Events)
```
┌──────────────────────────────────────────────────┐
│           Teams Meeting                          │
│  ┌────────────────────────────────────────────┐  │
│  │  Recall.ai Bot (Screen Share)              │  │
│  │  - Captures room audio                     │  │
│  │  - Displays webpage                        │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
                      ↓
         ┌────────────────────────┐
         │  Client (React)        │
         │  - Status indicator    │
         │  - Audio playback      │
         └────────────────────────┘
                      ↓ (WebSocket)
         ┌────────────────────────┐
         │  Relay Server          │
         │  - Bridges to OpenAI   │
         │  - Queues messages     │
         │  - Handles reconnects  │
         └────────────────────────┘
                      ↓ (WebSocket)
         ┌────────────────────────┐
         │  OpenAI Realtime API   │
         │  - Processes voice     │
         │  - Generates response  │
         └────────────────────────┘

PROS:
+ Single connection
+ Real-time everything
+ No polling

CONS:
- Stateful relay server
- Scaling requires sticky sessions
```

### Option B: WebSocket + Webhook (Recommended)
```
┌──────────────────────────────────────────────────┐
│           Teams Meeting                          │
│  ┌────────────────────────────────────────────┐  │
│  │  Recall.ai Bot                             │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
        ↓                           ↓
   (WebSocket)            (HTTP Webhook)
        ↓                           ↓
    ┌───────────┐          ┌──────────────┐
    │ Relay     │          │Event Handler │
    │Server     │          │(Backend API) │
    └───────────┘          └──────────────┘
        ↓                           ↓
    ┌───────────┐          ┌──────────────┐
    │OpenAI     │          │Database      │
    │Realtime   │          │Notifications │
    └───────────┘          └──────────────┘

PROS:
+ WebSocket for low-latency voice
+ Webhook for async events
+ Easier scaling (stateless events)
+ Better separation of concerns

CONS:
- Two different protocols
- Slightly more complex setup
```

### Option C: Polling (NOT Recommended)
```
┌──────────────────────────────────────────────────┐
│           Teams Meeting                          │
│  ┌────────────────────────────────────────────┐  │
│  │  Recall.ai Bot                             │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
        ↓ (HTTP polling every 100ms)
    ┌──────────────┐
    │Your Server   │
    │- Polls for   │
    │  audio       │
    │- Sends back  │
    │  audio       │
    └──────────────┘
        ↓ (HTTP polling)
    ┌──────────────┐
    │OpenAI API    │
    │(Not realtime)│
    └──────────────┘

CONS:
- 10+ HTTP requests/second
- High latency (hundreds of ms)
- Wasted bandwidth
- Server never pushes data to client
- NOT SUITABLE FOR VOICE

DON'T USE THIS ✗
```

---

## 9. MIGRATION PATH

### Phase 1: Development (Pure WebSocket)
```javascript
// Start with relay server + client only
const relay = new WebSocketServer({ port: 3000 });
// Test voice locally
```

### Phase 2: Testing (Add Events)
```javascript
// Keep WebSocket for voice
// Add webhook endpoint for events
app.post("/webhook/recall", handleRecallEvents);
```

### Phase 3: Production (Full Hybrid)
```
WebSocket Relay: Load balanced (multiple instances)
Webhook Handler: Stateless API servers
Database: Persistent event storage
Monitoring: Connection health, latency metrics
```

---

## 10. DECISION SUMMARY

**FOR TEAMS VOICE BOT: Use WebSocket (Recall.ai approach)**

```
✓ MUST USE WebSocket:
  - Real-time voice streaming (audio input/output)
  - Continuous PCM16 audio flow
  - Low-latency conversation (< 500ms)

✓ CAN ALSO USE Webhook:
  - Bot joined/left events
  - Meeting ended notifications
  - Transcript summaries
  - Analytics callbacks

✗ DO NOT USE Webhook:
  - For voice streaming
  - For any real-time component
  - For audio frames
```

---

## REFERENCES

- [Recall.ai Implementation](https://github.com/recallai/voice-agent-demo)
- [OpenAI Realtime API (WebSocket)](https://platform.openai.com/docs/guides/realtime)
- [RFC 6455: WebSocket Protocol](https://tools.ietf.org/html/rfc6455)
- [HTTP vs WebSocket](https://stackoverflow.com/questions/14703627/websockets-protocol-vs-http)
