# Teams Voice Bot Implementation Guide
## Based on Recall.ai Voice Agent Architecture

---

## QUICK START: Core Components

### 1. WebSocket Relay Server (Node.js)

**File:** `/node-server/index.js`

```javascript
import { WebSocketServer } from "ws";
import { RealtimeClient } from "@openai/realtime-api-beta";
import dotenv from "dotenv";

dotenv.config();

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const PORT = process.env.PORT || 3000;

if (!OPENAI_API_KEY) {
  console.error("OPENAI_API_KEY is required in .env file");
  process.exit(1);
}

const wss = new WebSocketServer({ port: PORT });

wss.on("connection", async (ws, req) => {
  // Validate connection
  if (!req.url || new URL(req.url, `https://${req.headers.host}`).pathname !== "/") {
    console.log("Invalid connection, closing");
    ws.close();
    return;
  }

  // Create OpenAI realtime client
  const client = new RealtimeClient({ apiKey: OPENAI_API_KEY });

  // Message queue for early arrivals
  const messageQueue = [];

  // Relay OpenAI → Browser (bidirectional)
  client.realtime.on("server.*", (event) => {
    console.log(`[OpenAI → Browser] ${event.type}`);
    ws.send(JSON.stringify(event));
  });

  // Handle OpenAI disconnection
  client.realtime.on("close", () => {
    console.log("OpenAI disconnected");
    ws.close();
  });

  // Relay Browser → OpenAI (with queuing)
  const messageHandler = (data) => {
    try {
      const event = JSON.parse(data);
      console.log(`[Browser → OpenAI] ${event.type}`);
      client.realtime.send(event.type, event);
    } catch (e) {
      console.error(`JSON parse error: ${e.message}`);
    }
  };

  ws.on("message", (data) => {
    if (!client.isConnected()) {
      messageQueue.push(data);
      console.log("Queued message (awaiting OpenAI connection)");
    } else {
      messageHandler(data);
    }
  });

  ws.on("close", () => {
    client.disconnect();
    console.log("Browser disconnected");
  });

  // Connect to OpenAI
  try {
    console.log("Connecting to OpenAI Realtime API...");
    await client.connect();
    console.log("✓ Connected to OpenAI");

    // Process queued messages
    while (messageQueue.length) {
      messageHandler(messageQueue.shift());
    }
  } catch (e) {
    console.error(`OpenAI connection failed: ${e.message}`);
    ws.close(1011, e.message);
  }
});

console.log(`WebSocket relay server listening on port ${PORT}`);
```

**Dependencies (`package.json`):**
```json
{
  "dependencies": {
    "@openai/realtime-api-beta": "github:openai/openai-realtime-api-beta",
    "dotenv": "^16.4.5",
    "ws": "^8.18.0"
  },
  "devDependencies": {
    "nodemon": "^3.0.2"
  },
  "scripts": {
    "dev": "nodemon index.js",
    "start": "node index.js"
  }
}
```

---

### 2. Python WebSocket Relay Server (Alternative)

**File:** `/python-server/server.py`

```python
import asyncio
import json
import logging
import os
from dotenv import load_dotenv
import websockets
from websockets.legacy.server import WebSocketServerProtocol, serve
from websockets.legacy.client import connect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()
PORT = int(os.getenv("PORT", 3000))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set in .env file")


async def connect_to_openai():
    """Establish connection to OpenAI Realtime API"""
    uri = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"

    try:
        ws = await connect(
            uri,
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "realtime=v1",
            },
            subprotocols=["realtime"],
        )
        logger.info("✓ Connected to OpenAI Realtime API")

        # Receive session.created event
        response = await ws.recv()
        event = json.loads(response)

        if event.get("type") != "session.created":
            raise Exception(f"Expected session.created, got {event.get('type')}")

        logger.info(f"✓ Session created: {event['session']['id']}")

        # Configure session
        update_session = {
            "type": "session.update",
            "session": {
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "modalities": ["text", "audio"],
                "voice": "alloy",
            },
        }
        await ws.send(json.dumps(update_session))
        logger.info("✓ Session configured")

        return ws, event

    except Exception as e:
        logger.error(f"OpenAI connection failed: {str(e)}")
        raise


class WebSocketRelay:
    def __init__(self):
        self.connections = {}
        self.message_queues = {}

    async def handle_browser_connection(
        self, websocket: WebSocketServerProtocol, path: str
    ):
        """Handle incoming browser connection"""
        base_path = path.split("?")[0]
        if base_path != "/":
            logger.warning(f"Invalid path: {path}")
            await websocket.close(1008, "Invalid path")
            return

        logger.info(f"✓ Browser connected: {websocket.remote_address}")
        self.message_queues[websocket] = []
        openai_ws = None

        try:
            # Connect to OpenAI
            openai_ws, session_created = await connect_to_openai()
            self.connections[websocket] = openai_ws

            # Send session info to browser
            await websocket.send(json.dumps(session_created))
            logger.info("✓ Session info forwarded to browser")

            # Process queued messages
            while self.message_queues[websocket]:
                message = self.message_queues[websocket].pop(0)
                try:
                    event = json.loads(message)
                    logger.info(f"[Queue] Relaying {event.get('type')} to OpenAI")
                    await openai_ws.send(message)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {message}")

            # Define bidirectional message handlers
            async def relay_browser_to_openai():
                """Stream messages from browser to OpenAI"""
                try:
                    while True:
                        message = await websocket.recv()
                        try:
                            event = json.loads(message)
                            logger.info(f"[Browser → OpenAI] {event.get('type')}")
                            await openai_ws.send(message)
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON from browser: {message}")
                except websockets.exceptions.ConnectionClosed:
                    logger.info("Browser connection closed")
                    raise

            async def relay_openai_to_browser():
                """Stream messages from OpenAI to browser"""
                try:
                    while True:
                        message = await openai_ws.recv()
                        try:
                            event = json.loads(message)
                            logger.info(f"[OpenAI → Browser] {event.get('type')}")
                            await websocket.send(message)
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON from OpenAI: {message}")
                except websockets.exceptions.ConnectionClosed:
                    logger.info("OpenAI connection closed")
                    raise

            # Run both directions concurrently
            await asyncio.gather(
                relay_browser_to_openai(),
                relay_openai_to_browser()
            )

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            if not websocket.closed:
                await websocket.close(1011, str(e))

        finally:
            # Cleanup
            if websocket in self.connections:
                if openai_ws and not openai_ws.closed:
                    await openai_ws.close(1000, "Normal closure")
                del self.connections[websocket]
            if websocket in self.message_queues:
                del self.message_queues[websocket]
            if not websocket.closed:
                await websocket.close(1000, "Normal closure")
            logger.info(f"Cleaned up connection from {websocket.remote_address}")

    async def serve(self):
        """Start WebSocket relay server"""
        async with serve(
            self.handle_browser_connection,
            "0.0.0.0",
            PORT,
            ping_interval=20,      # Ping every 20 seconds
            ping_timeout=20,       # Expect pong within 20 seconds
            subprotocols=["realtime"],
        ):
            logger.info(f"✓ WebSocket relay server running on ws://0.0.0.0:{PORT}")
            await asyncio.Future()  # Run forever


async def main():
    relay = WebSocketRelay()
    try:
        await relay.serve()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")


if __name__ == "__main__":
    asyncio.run(main())
```

**Dependencies (`requirements.txt`):**
```
websockets==12.0
python-dotenv==1.0.1
```

---

### 3. Client-Side Audio Capture & Realtime API Integration

**File:** `client/src/App.tsx`

```typescript
import { useState, useEffect, useRef, useCallback } from "react";
import { RealtimeClient } from "@openai/realtime-api-beta";
import { WavRecorder, WavStreamPlayer } from "./lib/wavtools/index.js";
import { instructions } from "./conversation_config.js";
import "./App.css";

const clientRef = { current: null as RealtimeClient | null };
const wavRecorderRef = { current: null as WavRecorder | null };
const wavStreamPlayerRef = { current: null as WavStreamPlayer | null };

export function App() {
  // Get relay server URL from query parameter
  const params = new URLSearchParams(window.location.search);
  const RELAY_SERVER_URL = params.get("wss");

  const [connectionStatus, setConnectionStatus] = useState<
    "disconnected" | "connecting" | "connected"
  >("disconnected");

  // Initialize clients (once per component lifecycle)
  if (!clientRef.current) {
    clientRef.current = new RealtimeClient({
      url: RELAY_SERVER_URL || undefined,
    });
  }
  if (!wavRecorderRef.current) {
    wavRecorderRef.current = new WavRecorder({ sampleRate: 24000 });
  }
  if (!wavStreamPlayerRef.current) {
    wavStreamPlayerRef.current = new WavStreamPlayer({ sampleRate: 24000 });
  }

  const isConnectedRef = useRef(false);

  // Main connection function
  const connectConversation = useCallback(async () => {
    if (isConnectedRef.current) return;
    isConnectedRef.current = true;
    setConnectionStatus("connecting");

    const client = clientRef.current;
    const wavRecorder = wavRecorderRef.current;
    const wavStreamPlayer = wavStreamPlayerRef.current;

    if (!client || !wavRecorder || !wavStreamPlayer) return;

    try {
      // Initialize audio capture
      await wavRecorder.begin();

      // Initialize audio output
      await wavStreamPlayer.connect();

      // Connect to relay server (which bridges to OpenAI)
      await client.connect();

      setConnectionStatus("connected");
      console.log("✓ Connected to OpenAI Realtime API");

      // Error handling
      client.on("error", (event: any) => {
        console.error("Client error:", event);
        setConnectionStatus("disconnected");
      });

      client.on("disconnected", () => {
        console.log("Disconnected from OpenAI");
        setConnectionStatus("disconnected");
      });

      // Send initial greeting
      client.sendUserMessageContent([
        {
          type: "input_text",
          text: "Hello! Please respond with audio.",
        },
      ]);

      // Configure server-side Voice Activity Detection (critical for latency)
      client.updateSession({
        turn_detection: { type: "server_vad" },
      });

      // Start recording microphone input
      await wavRecorder.record((data: { mono: Float32Array }) =>
        client.appendInputAudio(data.mono)
      );

    } catch (error) {
      console.error("Connection error:", error);
      setConnectionStatus("disconnected");
      isConnectedRef.current = false;
    }
  }, []);

  // Validate relay server URL
  const errorMessage = !RELAY_SERVER_URL
    ? 'Missing "wss" parameter in URL'
    : (() => {
        try {
          new URL(RELAY_SERVER_URL);
          return null;
        } catch {
          return 'Invalid URL format for "wss" parameter';
        }
      })();

  // Setup realtime client and event handlers
  useEffect(() => {
    if (!errorMessage) {
      connectConversation();

      const wavStreamPlayer = wavStreamPlayerRef.current;
      const client = clientRef.current;

      if (!client || !wavStreamPlayer) return;

      // Set system instructions
      client.updateSession({
        instructions: instructions,
      });

      // Handle interruptions
      client.on("conversation.interrupted", async () => {
        const trackSampleOffset = await wavStreamPlayer.interrupt();
        if (trackSampleOffset?.trackId) {
          const { trackId, offset } = trackSampleOffset;
          await client.cancelResponse(trackId, offset);
        }
      });

      // Handle audio updates from OpenAI
      client.on("conversation.updated", async ({ item, delta }: any) => {
        if (delta?.audio) {
          // Queue audio for playback
          wavStreamPlayer.add16BitPCM(delta.audio, item.id);
        }
        if (item.status === "completed" && item.formatted.audio?.length) {
          // Optionally save completed audio
          const wavFile = await WavRecorder.decode(
            item.formatted.audio,
            24000,
            24000
          );
          item.formatted.file = wavFile;
        }
      });

      return () => {
        client.reset();
      };
    }
  }, [errorMessage]);

  return (
    <div className="app-container">
      <div className="status-indicator">
        <div
          className={`status-dot ${
            errorMessage ? "error" : connectionStatus
          }`}
        />
        <div className="status-text">
          <div className="status-label">
            {errorMessage
              ? "Error:"
              : connectionStatus === "connecting"
              ? "Connecting..."
              : connectionStatus === "connected"
              ? "Connected to:"
              : "Disconnected"}
          </div>
          <div className="status-url">{errorMessage || RELAY_SERVER_URL}</div>
        </div>
      </div>
    </div>
  );
}

export default App;
```

---

### 4. System Prompt Configuration

**File:** `client/src/conversation_config.ts`

```typescript
export const instructions = `System settings:
Tool use: enabled.

You are a Teams meeting voice assistant. Your role is to:
1. Listen to meeting participants
2. Provide helpful real-time responses
3. Answer questions about the meeting
4. Maintain conversation flow
5. Be concise and clear

Instructions:
- Respond via audio whenever possible
- Keep responses under 30 seconds
- Ask clarifying questions if needed
- Be professional and helpful
- Do not interrupt other speakers
- If you miss something, ask for clarification

Personality:
- Be engaging and attentive
- Show genuine interest in the discussion
- Speak at a natural pace
- Use natural speech patterns
- Avoid robotic tone
`;
```

---

## ENVIRONMENT CONFIGURATION

### `.env` File (Both Node.js and Python servers)

```env
# Required: Your OpenAI API key
# Get it from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxx

# Optional: Server port (defaults to 3000)
PORT=3000

# Optional: Logging level
LOG_LEVEL=INFO
```

**CRITICAL:** Before testing, add credits to your OpenAI account:
- Visit: https://platform.openai.com/account/billing/overview
- Add credits (at least $5 recommended)
- Without credits, bot connects but won't respond

---

## DEPLOYMENT: Exposing Relay Server

### Option 1: Ngrok (Development)

```bash
# Install ngrok
brew install ngrok

# Authenticate (get token from https://dashboard.ngrok.com)
ngrok config add-authtoken YOUR_TOKEN

# Expose local server
ngrok http 3000
```

**Output:**
```
Forwarding                    https://xxxx-xx-xxx-xxx.ngrok.io -> http://localhost:3000
```

**Use in client URL:**
```
https://your-frontend.com?wss=wss://xxxx-xx-xxx-xxx.ngrok.io
```

### Option 2: AWS Lambda + API Gateway

```python
# Serverless WebSocket implementation with AWS
from mangum import Mangum
from server import WebSocketRelay

# Wrap relay for Lambda
relay = WebSocketRelay()
handler = Mangum(relay.serve)
```

**CloudFormation:**
```yaml
Resources:
  WebSocketAPI:
    Type: AWS::ApiGatewayV2::Api
    Properties:
      ProtocolType: WEBSOCKET
      RouteSelectionExpression: $request.body.action

  RelayFunction:
    Type: AWS::Lambda::Function
    Properties:
      Runtime: python3.11
      Handler: handler.handler
      Code:
        S3Bucket: your-bucket
        S3Key: relay-server.zip
```

### Option 3: Docker + Cloud Run / ECS

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY python-server/ .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
```

**Deploy to Cloud Run:**
```bash
docker build -t voice-relay .
docker tag voice-relay gcr.io/your-project/voice-relay
docker push gcr.io/your-project/voice-relay

gcloud run deploy voice-relay \
  --image gcr.io/your-project/voice-relay \
  --allow-unauthenticated
```

---

## TEAMS BOT CREATION

### Create Bot via Recall.ai API

```bash
curl --request POST \
  --url https://us-east-1.recall.ai/api/v1/bot/ \
  --header 'Authorization: Bearer YOUR_RECALL_TOKEN' \
  --header 'accept: application/json' \
  --header 'content-type: application/json' \
  --data '{
    "meeting_url": "https://teams.microsoft.com/l/meetup-join/...",
    "bot_name": "Teams Voice Assistant",
    "output_media": {
      "camera": {
        "kind": "webpage",
        "config": {
          "url": "https://your-frontend.com?wss=wss://your-relay-server.com"
        }
      }
    },
    "variant": {
      "zoom": "web_4_core",
      "google_meet": "web_4_core",
      "microsoft_teams": "web_4_core"
    }
  }'
```

**Response:**
```json
{
  "id": "bot_xxxxx",
  "meeting_url": "https://teams.microsoft.com/...",
  "status": "connecting",
  "output_media": {
    "camera": {
      "kind": "webpage",
      "config": {
        "url": "https://your-frontend.com?wss=wss://your-relay-server.com"
      }
    }
  }
}
```

---

## LATENCY OPTIMIZATION CHECKLIST

- [ ] **Server-Side VAD Enabled**
  ```javascript
  client.updateSession({ turn_detection: { type: "server_vad" } });
  ```
  Expected: ~200-300ms reduction in response latency

- [ ] **Audio Format Correct**
  - Input: PCM16, 24kHz
  - Output: PCM16, 24kHz
  - Avoid compression (MP3, AAC)

- [ ] **Message Queuing During Connection**
  ```javascript
  if (!client.isConnected()) {
    messageQueue.push(data);  // Don't drop messages
  }
  ```

- [ ] **Continuous Audio Streaming**
  ```javascript
  await wavRecorder.record((data) =>
    client.appendInputAudio(data.mono)  // Not batched
  );
  ```

- [ ] **WebSocket Keepalive Enabled**
  ```python
  ping_interval=20,   # Send ping every 20s
  ping_timeout=20,    # Expect pong in 20s
  ```

- [ ] **Interrupt Handling Implemented**
  ```javascript
  client.on("conversation.interrupted", async () => {
    const { trackId, offset } = await wavStreamPlayer.interrupt();
    await client.cancelResponse(trackId, offset);
  });
  ```

- [ ] **Proper Error Recovery**
  - Auto-reconnect on connection loss
  - Don't drop messages during reconnection

---

## TESTING & DEBUGGING

### Test WebSocket Connection

```bash
# Test relay server is listening
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: SGVsbG8sIHdvcmxkIQ==" \
  http://localhost:3000
```

### Monitor WebSocket Traffic

```bash
# Python: See what messages are flowing
LOG_LEVEL=DEBUG python server.py
```

### Test OpenAI Connection

```bash
# Verify OpenAI API key is valid
curl https://api.openai.com/v1/models/gpt-4o-realtime-preview-2024-12-17 \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Local Testing Flow

1. Start relay server: `npm run dev` (Node) or `python server.py` (Python)
2. Expose with ngrok: `ngrok http 3000`
3. Start client dev server: `npm run dev` (in client directory)
4. Visit: `http://localhost:5173?wss=wss://YOUR_NGROK_URL`
5. Check browser console for connection status
6. Speak into microphone, hear bot respond

---

## PERFORMANCE METRICS

Track these metrics in production:

```javascript
// Track connection time
const connectionStart = Date.now();
await client.connect();
const connectionTime = Date.now() - connectionStart;
console.log(`Connection time: ${connectionTime}ms`);

// Track message latency
const messageStart = Date.now();
client.sendUserMessageContent([{ type: "input_text", text: "Hello" }]);
client.on("conversation.updated", () => {
  const latency = Date.now() - messageStart;
  console.log(`Latency: ${latency}ms`);
});

// Track audio quality
client.on("conversation.updated", ({ item }) => {
  if (item.formatted.audio) {
    const audioSize = item.formatted.audio.length;
    console.log(`Audio chunk: ${audioSize} bytes`);
  }
});
```

---

## COMMON ISSUES & SOLUTIONS

| Issue | Cause | Solution |
|-------|-------|----------|
| Bot connects but doesn't respond | No OpenAI credits | Add credits to account |
| Audio distortion | Format mismatch | Verify PCM16, 24kHz everywhere |
| High latency | Client-side VAD | Use `turn_detection: { type: "server_vad" }` |
| Frequent disconnects | Firewall timeout | Add ping keepalive every 20s |
| Messages lost | Connection establishing | Implement message queue |
| Audio interrupts fail | Track ID missing | Call `wavStreamPlayer.interrupt()` correctly |

---

## NEXT STEPS

1. **Deploy relay server** to cloud infrastructure
2. **Set up monitoring** for connection health
3. **Implement conversation memory** for context across turns
4. **Add Teams-specific features** (participant detection, meeting context)
5. **Optimize prompt** for your specific use case
6. **Add logging & analytics** for production visibility

---

## References

- [Recall.ai Documentation](https://docs.recall.ai)
- [OpenAI Realtime API](https://platform.openai.com/docs/guides/realtime)
- [WebSocket Protocol](https://tools.ietf.org/html/rfc6455)
- [PCM Audio Format](https://en.wikipedia.org/wiki/Pulse-code_modulation)
