/**
 * WebSocket Relay Server
 * Bridges browser client to OpenAI Realtime API
 *
 * Why needed:
 * - Browser cannot securely store OpenAI API key
 * - Handles WebSocket protocol differences
 * - Provides message queuing during connection establishment
 */

import { WebSocketServer, WebSocket } from 'ws';
import dotenv from 'dotenv';

dotenv.config();

// ============================================================
// CONFIGURATION
// ============================================================

const PORT = process.env.PORT || 3000;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const OPENAI_REALTIME_URL = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17';

// Validate required environment variables
if (!OPENAI_API_KEY) {
  console.error('ERROR: OPENAI_API_KEY is required');
  console.error('Create a .env file with: OPENAI_API_KEY=sk-...');
  process.exit(1);
}

// ============================================================
// LOGGING UTILITIES
// ============================================================

const LOG_LEVELS = {
  DEBUG: 0,
  INFO: 1,
  WARN: 2,
  ERROR: 3
};

const currentLogLevel = LOG_LEVELS[process.env.LOG_LEVEL?.toUpperCase()] ?? LOG_LEVELS.INFO;

function log(level, ...args) {
  if (LOG_LEVELS[level] >= currentLogLevel) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${level}]`, ...args);
  }
}

// ============================================================
// CONNECTION TRACKING
// ============================================================

const connections = new Map();
let connectionIdCounter = 0;

function generateConnectionId() {
  return `conn_${++connectionIdCounter}_${Date.now()}`;
}

// ============================================================
// OPENAI CONNECTION
// ============================================================

async function connectToOpenAI(connectionId) {
  return new Promise((resolve, reject) => {
    log('INFO', `[${connectionId}] Connecting to OpenAI Realtime API...`);

    const openaiWs = new WebSocket(OPENAI_REALTIME_URL, {
      headers: {
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'OpenAI-Beta': 'realtime=v1'
      }
    });

    const timeout = setTimeout(() => {
      openaiWs.close();
      reject(new Error('OpenAI connection timeout'));
    }, 30000);

    openaiWs.on('open', () => {
      clearTimeout(timeout);
      log('INFO', `[${connectionId}] Connected to OpenAI`);
      resolve(openaiWs);
    });

    openaiWs.on('error', (error) => {
      clearTimeout(timeout);
      log('ERROR', `[${connectionId}] OpenAI connection error:`, error.message);
      reject(error);
    });
  });
}

// ============================================================
// WEBSOCKET SERVER
// ============================================================

const wss = new WebSocketServer({
  port: PORT,
  perMessageDeflate: false // Disable compression for lower latency
});

log('INFO', `WebSocket relay server starting on port ${PORT}...`);

wss.on('listening', () => {
  log('INFO', `Server listening on ws://0.0.0.0:${PORT}`);
  log('INFO', `Ready for browser connections`);
});

wss.on('connection', async (browserWs, req) => {
  const connectionId = generateConnectionId();
  const clientIp = req.socket.remoteAddress;

  log('INFO', `[${connectionId}] Browser connected from ${clientIp}`);

  // Validate connection path
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname !== '/' && url.pathname !== '') {
    log('WARN', `[${connectionId}] Invalid path: ${url.pathname}`);
    browserWs.close(1008, 'Invalid path');
    return;
  }

  // Connection state
  const state = {
    connectionId,
    openaiWs: null,
    messageQueue: [],
    isOpenAIConnected: false,
    isBrowserConnected: true
  };

  connections.set(connectionId, state);

  // Message handler for browser -> OpenAI
  const handleBrowserMessage = (data) => {
    try {
      const message = data.toString();
      const event = JSON.parse(message);

      // Log non-audio events
      if (!event.type?.includes('audio')) {
        log('DEBUG', `[${connectionId}] Browser -> OpenAI: ${event.type}`);
      }

      if (state.isOpenAIConnected && state.openaiWs?.readyState === WebSocket.OPEN) {
        state.openaiWs.send(message);
      } else {
        // Queue message until OpenAI is connected
        state.messageQueue.push(message);
        log('DEBUG', `[${connectionId}] Queued message (OpenAI not ready)`);
      }
    } catch (error) {
      log('ERROR', `[${connectionId}] Failed to parse browser message:`, error.message);
    }
  };

  // Message handler for OpenAI -> browser
  const handleOpenAIMessage = (data) => {
    try {
      const message = data.toString();
      const event = JSON.parse(message);

      // Log non-audio events
      if (!event.type?.includes('audio')) {
        log('DEBUG', `[${connectionId}] OpenAI -> Browser: ${event.type}`);
      }

      if (state.isBrowserConnected && browserWs.readyState === WebSocket.OPEN) {
        browserWs.send(message);
      }
    } catch (error) {
      log('ERROR', `[${connectionId}] Failed to relay OpenAI message:`, error.message);
    }
  };

  // Set up browser WebSocket handlers
  browserWs.on('message', handleBrowserMessage);

  browserWs.on('close', (code, reason) => {
    log('INFO', `[${connectionId}] Browser disconnected: ${code} ${reason}`);
    state.isBrowserConnected = false;

    // Close OpenAI connection
    if (state.openaiWs?.readyState === WebSocket.OPEN) {
      state.openaiWs.close(1000, 'Browser disconnected');
    }

    connections.delete(connectionId);
  });

  browserWs.on('error', (error) => {
    log('ERROR', `[${connectionId}] Browser WebSocket error:`, error.message);
  });

  // Send keepalive pings to browser
  const pingInterval = setInterval(() => {
    if (browserWs.readyState === WebSocket.OPEN) {
      browserWs.ping();
    } else {
      clearInterval(pingInterval);
    }
  }, 30000);

  browserWs.on('close', () => clearInterval(pingInterval));

  // Connect to OpenAI
  try {
    state.openaiWs = await connectToOpenAI(connectionId);

    // Set up OpenAI WebSocket handlers
    state.openaiWs.on('message', handleOpenAIMessage);

    state.openaiWs.on('close', (code, reason) => {
      log('INFO', `[${connectionId}] OpenAI disconnected: ${code} ${reason}`);
      state.isOpenAIConnected = false;

      // Close browser connection
      if (browserWs.readyState === WebSocket.OPEN) {
        browserWs.close(1011, 'OpenAI disconnected');
      }
    });

    state.openaiWs.on('error', (error) => {
      log('ERROR', `[${connectionId}] OpenAI WebSocket error:`, error.message);
    });

    state.isOpenAIConnected = true;

    // Process queued messages
    while (state.messageQueue.length > 0) {
      const queuedMessage = state.messageQueue.shift();
      state.openaiWs.send(queuedMessage);
      log('DEBUG', `[${connectionId}] Sent queued message`);
    }

    log('INFO', `[${connectionId}] Relay established: Browser <-> OpenAI`);

  } catch (error) {
    log('ERROR', `[${connectionId}] Failed to connect to OpenAI:`, error.message);
    browserWs.close(1011, `OpenAI connection failed: ${error.message}`);
    connections.delete(connectionId);
  }
});

// ============================================================
// HEALTH CHECK ENDPOINT (for monitoring)
// ============================================================

import http from 'http';

const healthServer = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      activeConnections: connections.size,
      uptime: process.uptime()
    }));
  } else if (req.url === '/stats') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      activeConnections: connections.size,
      connections: Array.from(connections.keys()),
      uptime: process.uptime(),
      memory: process.memoryUsage()
    }));
  } else {
    res.writeHead(404);
    res.end('Not found');
  }
});

const HEALTH_PORT = parseInt(process.env.HEALTH_PORT) || (PORT + 1);
healthServer.listen(HEALTH_PORT, () => {
  log('INFO', `Health check server listening on http://0.0.0.0:${HEALTH_PORT}/health`);
});

// ============================================================
// GRACEFUL SHUTDOWN
// ============================================================

process.on('SIGINT', () => {
  log('INFO', 'Shutting down...');

  // Close all connections
  for (const [connectionId, state] of connections) {
    log('INFO', `[${connectionId}] Closing connection...`);
    if (state.openaiWs?.readyState === WebSocket.OPEN) {
      state.openaiWs.close(1000, 'Server shutdown');
    }
  }

  wss.close(() => {
    log('INFO', 'WebSocket server closed');
    healthServer.close(() => {
      log('INFO', 'Health server closed');
      process.exit(0);
    });
  });
});

process.on('uncaughtException', (error) => {
  log('ERROR', 'Uncaught exception:', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  log('ERROR', 'Unhandled rejection at:', promise, 'reason:', reason);
});
