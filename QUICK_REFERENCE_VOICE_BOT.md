# Quick Reference: Voice Bot Patterns from Recall.ai

---

## 1-MINUTE SETUP

### Environment
```bash
# .env file
OPENAI_API_KEY=sk-proj-xxxxxx
PORT=3000
```

### Start Relay Server
```bash
# Node.js
cd node-server && npm install && npm run dev

# Python
cd python-server && pip install -r requirements.txt && python server.py
```

### Expose Public URL
```bash
ngrok http 3000
# Output: Forwarding wss://abc123.ngrok.io -> http://localhost:3000
```

### Create Teams Bot
```bash
curl -X POST https://us-east-1.recall.ai/api/v1/bot/ \
  -H "Authorization: Bearer RECALL_TOKEN" \
  -d '{
    "meeting_url": "TEAMS_MEETING_URL",
    "bot_name": "Voice Assistant",
    "output_media": {
      "camera": {
        "kind": "webpage",
        "config": {
          "url": "https://your-frontend.com?wss=wss://abc123.ngrok.io"
        }
      }
    },
    "variant": { "microsoft_teams": "web_4_core" }
  }'
```

---

## CRITICAL CODE PATTERNS

### Pattern 1: WebSocket Relay (Node.js)
```javascript
const wss = new WebSocketServer({ port: 3000 });

wss.on("connection", async (ws) => {
  const client = new RealtimeClient({ apiKey: OPENAI_API_KEY });
  const queue = [];

  // OpenAI → Browser
  client.realtime.on("server.*", (event) => {
    ws.send(JSON.stringify(event));
  });

  // Browser → OpenAI (with queuing)
  ws.on("message", (data) => {
    if (!client.isConnected()) {
      queue.push(data);
    } else {
      client.realtime.send(JSON.parse(data).type, JSON.parse(data));
    }
  });

  await client.connect();
  while (queue.length) {
    const data = queue.shift();
    client.realtime.send(JSON.parse(data).type, JSON.parse(data));
  }
});
```

### Pattern 2: Client Audio Setup
```typescript
const client = new RealtimeClient({ url: RELAY_SERVER_URL });
const wavRecorder = new WavRecorder({ sampleRate: 24000 });
const wavStreamPlayer = new WavStreamPlayer({ sampleRate: 24000 });

// Connect everything
await wavRecorder.begin();
await wavStreamPlayer.connect();
await client.connect();

// Enable server-side VAD (CRITICAL for latency)
client.updateSession({
  turn_detection: { type: "server_vad" }
});

// Stream audio
await wavRecorder.record((data) =>
  client.appendInputAudio(data.mono)
);

// Play responses
client.on("conversation.updated", ({ delta }) => {
  if (delta?.audio) {
    wavStreamPlayer.add16BitPCM(delta.audio, item.id);
  }
});
```

### Pattern 3: System Prompt
```typescript
client.updateSession({
  instructions: `You are a Teams meeting voice assistant.
- Respond via audio
- Keep responses under 30 seconds
- Be professional and helpful
- Speak naturally and engage genuinely`
});
```

### Pattern 4: Interruption Handling
```typescript
client.on("conversation.interrupted", async () => {
  const { trackId, offset } = await wavStreamPlayer.interrupt();
  await client.cancelResponse(trackId, offset);
});
```

### Pattern 5: Error Recovery
```typescript
client.on("error", (event) => {
  console.error(event);
  // Attempt reconnect
  setTimeout(connectConversation, 1000);
});

client.on("disconnected", () => {
  isConnectedRef.current = false;
  // Clean up and allow reconnect
});
```

---

## AUDIO FORMATS (MUST MATCH)

```
Input:  PCM16, 24kHz, mono
Output: PCM16, 24kHz, mono
Transport: Raw PCM (no MP3/AAC)
```

All mismatches = distorted audio or failure.

---

## LATENCY OPTIMIZATION CHECKLIST

**Most Important:**
- [ ] Server-side VAD: `turn_detection: { type: "server_vad" }`
- [ ] Direct PCM (24kHz, not encoded)
- [ ] Continuous audio (not batched)

**Important:**
- [ ] Message queuing during connection
- [ ] Interrupt handling implemented
- [ ] WebSocket keepalive (ping every 20s)

**Nice-to-have:**
- [ ] Voice choice optimized (alloy = fastest)
- [ ] Minimal system prompt (fewer tokens)

---

## RELAY SERVER COMPARISON

### Node.js
```javascript
// PROS: Fast, familiar, JS ecosystem
// CONS: Single-threaded, message handling overhead

// Handle many connections: PM2 clustering
// Handle slow clients: Built-in backpressure
```

### Python
```python
# PROS: Concurrency via asyncio, cleaner code
# CONS: GIL considerations at scale

# Handle many connections: Asyncio handles 1000+ easily
# Handle slow clients: Built-in buffering
```

**Recommendation:** Use Python for production (better concurrency).

---

## WEBSOCKET PROTOCOL DETAILS

### Connection
```
GET / HTTP/1.1
Host: localhost:3000
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: xxx
Sec-WebSocket-Version: 13
```

### Subprotocol
```
Sec-WebSocket-Protocol: realtime
```

### Keepalive
```
Ping: server → client every 20s
Pong: client → server response
Timeout: 20s
```

---

## OPENAI REALTIME API EVENTS

### Client Must Handle
```javascript
client.on("error", (event) => {});
client.on("disconnected", () => {});
client.on("conversation.interrupted", async () => {});
client.on("conversation.updated", async ({ item, delta }) => {});
```

### Session Configuration Events
```javascript
client.updateSession({
  input_audio_format: "pcm16",
  output_audio_format: "pcm16",
  modalities: ["text", "audio"],
  voice: "alloy",  // or: echo, shimmer
  turn_detection: { type: "server_vad" },
  instructions: "Your system prompt"
});
```

### Message Flow
```
1. Client: session.update
2. Server: session.created
3. Client: user message or audio
4. Server: response.created
5. Server: response.delta (audio chunks)
6. Server: response.done
7. Repeat from step 3
```

---

## DEPLOYMENT CHECKLIST

### Pre-deployment
- [ ] OpenAI account has credits (minimum $5)
- [ ] Relay server tested locally with ngrok
- [ ] Client connects with correct WSS URL
- [ ] Audio input/output working
- [ ] System prompt configured
- [ ] Error handling implemented

### During deployment
- [ ] Use WSS (secure WebSocket) in production
- [ ] Environment variables not hardcoded
- [ ] Logging enabled for debugging
- [ ] Health check endpoint available
- [ ] Rate limiting if needed
- [ ] CORS configured if needed

### Post-deployment
- [ ] Monitor connection latency
- [ ] Track error rates
- [ ] Monitor memory usage per connection
- [ ] Set up alerting for disconnects
- [ ] Test interruption scenarios
- [ ] Verify audio quality with real voices

---

## COMMON ISSUES & FIXES

| Issue | Fix |
|-------|-----|
| Bot connects but silent | Add OpenAI credits |
| Audio distorted | Verify PCM16, 24kHz format |
| High latency (>500ms) | Enable server-side VAD |
| Frequent disconnects | Add ping keepalive every 20s |
| Messages lost | Implement message queue |
| Can't hear bot response | Check WebSocket connection in browser DevTools |
| Microphone not working | Check browser permissions, verify WavRecorder initialization |

---

## FILE STRUCTURE

```
/your-project
├── node-server/
│   ├── index.js                  # WebSocket relay server
│   ├── package.json
│   └── .env                      # OPENAI_API_KEY
├── python-server/
│   ├── server.py                 # Python WebSocket relay
│   ├── requirements.txt
│   └── .env                      # OPENAI_API_KEY
└── client/
    ├── src/
    │   ├── App.tsx               # Main React component
    │   ├── conversation_config.ts # System prompt
    │   ├── lib/wavtools/         # Audio library
    │   ├── main.tsx
    │   └── index.css
    └── package.json
```

---

## PRODUCTION SCALING

### 100 Concurrent Connections
```
Memory: ~100MB (1MB per connection)
CPU: ~2 cores (20% per core)
Network: ~10Mbps (100Kbps per connection)
Cost: $5-10/month on AWS Lambda or similar
```

### 1000 Concurrent Connections
```
Memory: ~1GB
CPU: ~8 cores
Network: ~100Mbps
Cost: $50-100/month
→ Use load balancer (sticky sessions for WebSocket)
→ Use managed cloud service (AWS API Gateway + Lambda)
```

### Bottleneck Analysis
1. OpenAI API rate limits (depends on account tier)
2. Bandwidth (more of an issue than CPU)
3. Database for storing conversations
4. Webhook processing (if using Recall.ai events)

---

## MONITORING METRICS

```javascript
// Track these in production:

1. Connection latency
   - Time from client WebSocket open to OpenAI connection
   - Target: < 1 second

2. Message latency
   - Time from client sending audio to response starting
   - Target: < 500ms

3. Audio quality
   - Check for dropouts, distortion, echo
   - Sample random conversations

4. Error rate
   - Connection errors per 1000 attempts
   - Target: < 1%

5. Memory per connection
   - Should be ~1-2MB
   - Monitor for leaks

6. WebSocket disconnects
   - Track reason: normal close, timeout, error
   - Set up alerts for > 5% rate
```

---

## API KEYS & SECURITY

### OpenAI API Key
```
- Keep in .env file
- Never commit to git
- Rotate quarterly
- Monitor usage on https://platform.openai.com/account/billing/overview
- Set rate limits if needed
```

### Recall.ai API Key
```
- Used only for bot creation (not in relay server)
- Keep in .env or secrets manager
- Required to POST /api/v1/bot/
```

### Ngrok Token
```
ngrok config add-authtoken YOUR_TOKEN
# Allows persistent domains
```

---

## TESTING CHECKLIST

### Local Testing
```bash
1. Start relay server: npm run dev
2. Expose with ngrok: ngrok http 3000
3. Start client: npm run dev (in client dir)
4. Visit: http://localhost:5173?wss=wss://YOUR_NGROK_URL
5. Speak into microphone
6. Listen for bot response
7. Check browser console for errors
8. Check server logs for relay messages
```

### Integration Testing
```bash
1. Create actual Teams meeting
2. Create bot via Recall.ai API with your relay URL
3. Join meeting
4. Bot should appear as participant
5. Speak naturally
6. Bot should respond
7. Monitor latency and audio quality
```

### Load Testing
```bash
# Simulate multiple concurrent connections
ab -n 100 -c 10 http://localhost:3000

# Or use websocket load testing tool
npm install -g wsdump.py
```

---

## FURTHER OPTIMIZATION

### For Lower Latency
- Use regional servers (AWS regions closer to users)
- Optimize system prompt (fewer tokens)
- Consider voice choice (alloy is faster than shimmer)
- Implement client-side prediction/caching

### For Better Quality
- Use higher quality voices (shimmer for premium feel)
- Add conversation context from previous turns
- Implement tool use for complex tasks
- Add follow-up prompt to generate summaries

### For Better Reliability
- Implement exponential backoff on reconnect
- Add health checks every 30 seconds
- Store conversation history
- Implement graceful degradation

---

## RESOURCES

- **Recall.ai Docs:** https://docs.recall.ai
- **OpenAI Realtime API:** https://platform.openai.com/docs/guides/realtime
- **GitHub Demo:** https://github.com/recallai/voice-agent-demo
- **WebSocket Spec:** https://tools.ietf.org/html/rfc6455
- **PCM Audio Format:** https://en.wikipedia.org/wiki/Pulse-code_modulation
