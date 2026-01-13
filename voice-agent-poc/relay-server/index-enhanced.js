/**
 * Enhanced WebSocket Relay Server with Tool Execution
 *
 * REVOLUTIONARY ARCHITECTURE:
 * - Bridges browser client to OpenAI Realtime API (unchanged)
 * - Handles OpenAI function calls by delegating to n8n webhooks
 * - Sends transcript chunks to n8n Logging Agent asynchronously
 *
 * This is the "simple system within the system" - OpenAI handles conversation,
 * n8n handles tools and logging. The relay is just a smart bridge.
 */

import { WebSocketServer, WebSocket } from 'ws';
import http from 'http';
import dotenv from 'dotenv';
import pg from 'pg';

dotenv.config();

// ============================================================
// CONFIGURATION
// ============================================================

const PORT = process.env.PORT || 3000;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const OPENAI_REALTIME_URL = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17';

// n8n Integration URLs (for tool execution and logging)
const N8N_BASE_URL = process.env.N8N_BASE_URL || 'https://jayconnorexe.app.n8n.cloud';
const N8N_TOOLS_WEBHOOK = process.env.N8N_TOOLS_WEBHOOK || null; // Fallback dispatcher
const N8N_LOGGING_WEBHOOK = process.env.N8N_LOGGING_WEBHOOK || null;
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || null;

// Per-tool webhook mapping - REAL TOOLS ONLY (no mocks)
const TOOL_WEBHOOKS = {
  send_email: `${N8N_BASE_URL}/webhook/execute-gmail`,
  get_session_context: `${N8N_BASE_URL}/webhook/get-session-context`,
  query_vector_db: `${N8N_BASE_URL}/webhook/query-vector-db`
};

// Recall.ai Integration (for meeting audio injection)
const RECALL_API_KEY = process.env.RECALL_API_KEY || null;
const RECALL_BOT_ID = process.env.RECALL_BOT_ID || null; // Can be dynamic per session

// Supabase Integration (for bot_state lookup - source of truth from launcher workflow)
const SUPABASE_URL = process.env.SUPABASE_URL || null;
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY || null;

// Error Handling Configuration
const MAX_RETRIES = parseInt(process.env.MAX_RETRIES) || 5;
const RETRY_BASE_DELAY_MS = parseInt(process.env.RETRY_BASE_DELAY_MS) || 1000;
const CIRCUIT_BREAKER_COOLDOWN_MS = parseInt(process.env.CIRCUIT_BREAKER_COOLDOWN_MS) || 30000;

// Audio Monitoring Configuration
const AUDIO_LOSS_THRESHOLD = parseFloat(process.env.AUDIO_LOSS_THRESHOLD) || 0.05; // 5%

// ============================================================
// CALLBACK CONFIGURATION (for gated workflow execution)
// ============================================================

const CALLBACK_BASE_URL = process.env.CALLBACK_BASE_URL || null;

// ============================================================
// MANDATORY DATABASE CONFIGURATION
// ============================================================

const DATABASE_URL = process.env.DATABASE_URL;

// Validate required environment variables
if (!OPENAI_API_KEY) {
  console.error('ERROR: OPENAI_API_KEY is required');
  console.error('Create a .env file with: OPENAI_API_KEY=sk-...');
  process.exit(1);
}

// MANDATORY: Database is required for logging - fail fast if not configured
if (!DATABASE_URL) {
  console.error('CRITICAL ERROR: DATABASE_URL is required for mandatory logging');
  console.error('The relay server cannot start without database connectivity.');
  console.error('Add to .env file: DATABASE_URL=postgres://user:pass@host:5432/voice_agent');
  process.exit(1);
}

// Initialize PostgreSQL connection pool
const dbPool = new pg.Pool({
  connectionString: DATABASE_URL,
  max: 10, // Maximum connections in pool
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000
});

// Pending logs queue for retry on failure (in-memory buffer)
const pendingLogs = [];
const MAX_PENDING_LOGS = 1000;

// ============================================================
// SESSION CACHE - Enterprise In-Memory + PostgreSQL Write-Through
// ============================================================
// Pattern: In-memory Map for hot cache, PostgreSQL for persistence
// Latency: Memory ~1-5ms, PostgreSQL ~30-50ms (fallback only)
//
// Write-Through: Write to DB first (persistent), then update memory
// Read-Through: Check memory first, on miss query DB and warm cache

const CACHE_TTL = {
  session_context: 3600,      // 1 hour - session data
  pending_tool: 300,          // 5 minutes - pending tool calls
  recent_tools: 1800,         // 30 minutes - completed tool calls
  bot_state: 7200,            // 2 hours - bot configuration
  query_results: 900          // 15 minutes - vector query results
};

/**
 * SessionCache - Enterprise-grade in-memory + PostgreSQL caching layer
 *
 * Write-through pattern:
 * 1. Write to PostgreSQL (persistent source of truth)
 * 2. Update in-memory cache with TTL
 *
 * Read-through pattern:
 * 1. Check in-memory cache (hot path ~1-5ms)
 * 2. On miss → Query PostgreSQL → Warm in-memory cache
 *
 * Memory Management:
 * - Per-session cache maps with TTL expiry checking
 * - Automatic cleanup on session end
 * - Graceful degradation to DB-only on memory pressure
 */
class SessionCache {
  constructor(sessionId) {
    this.sessionId = sessionId;

    // In-memory cache stores: { value: any, expiresAt: number }
    this.contextCache = new Map();
    this.pendingToolCache = new Map();
    this.recentToolsCache = null;  // { value: array, expiresAt: number }
    this.botStateCache = null;     // { value: object, expiresAt: number }
  }

  // ==================== CACHE UTILITIES ====================

  _isExpired(cacheEntry) {
    if (!cacheEntry) return true;
    return Date.now() > cacheEntry.expiresAt;
  }

  _wrapWithTTL(value, ttlSeconds) {
    return {
      value,
      expiresAt: Date.now() + (ttlSeconds * 1000)
    };
  }

  // ==================== SESSION CONTEXT ====================

  /**
   * Get session context (e.g., vector query results, user preferences)
   * Read-through: Memory → PostgreSQL
   */
  async getContext(contextKey) {
    // Check in-memory cache (hot path)
    const cached = this.contextCache.get(contextKey);
    if (cached && !this._isExpired(cached)) {
      log('DEBUG', `Cache HIT (memory): ${contextKey}`);
      return cached.value;
    }

    // Memory miss or expired - query PostgreSQL
    try {
      const result = await dbPool.query(
        `SELECT context_value FROM session_context
         WHERE session_id = $1 AND context_key = $2
         AND (expires_at IS NULL OR expires_at > NOW())`,
        [this.sessionId, contextKey]
      );

      if (result.rows.length > 0) {
        const value = result.rows[0].context_value;
        // Warm the in-memory cache
        this.contextCache.set(contextKey, this._wrapWithTTL(value, CACHE_TTL.session_context));
        log('DEBUG', `Cache MISS → DB HIT: ${contextKey}`);
        return value;
      }
    } catch (err) {
      log('ERROR', `DB query failed for context ${contextKey}: ${err.message}`);
    }

    log('DEBUG', `Cache MISS (both): ${contextKey}`);
    return null;
  }

  /**
   * Set session context (write-through: PostgreSQL + Memory)
   */
  async setContext(contextKey, value, ttlSeconds = CACHE_TTL.session_context) {
    const expiresAt = new Date(Date.now() + ttlSeconds * 1000);

    // Write to PostgreSQL FIRST (persistent source of truth)
    try {
      await dbPool.query(
        `INSERT INTO session_context (session_id, context_key, context_value, expires_at)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT (session_id, context_key)
         DO UPDATE SET context_value = $3, expires_at = $4`,
        [this.sessionId, contextKey, JSON.stringify(value), expiresAt]
      );
    } catch (err) {
      log('ERROR', `DB write failed for context ${contextKey}: ${err.message}`);
      // Still update memory cache for resilience
    }

    // Update in-memory cache
    this.contextCache.set(contextKey, this._wrapWithTTL(value, ttlSeconds));
    log('DEBUG', `Context SET: ${contextKey} (TTL: ${ttlSeconds}s)`);
    return true;
  }

  // ==================== PENDING TOOL CALLS ====================

  /**
   * Store pending tool call (pre-confirmation state)
   * Memory-only with TTL (no DB persistence for pending calls)
   */
  async setPendingTool(intentId, toolData) {
    this.pendingToolCache.set(intentId, this._wrapWithTTL(toolData, CACHE_TTL.pending_tool));
    log('DEBUG', `Pending tool SET: ${intentId}`);
    return true;
  }

  async getPendingTool(intentId) {
    const cached = this.pendingToolCache.get(intentId);
    if (cached && !this._isExpired(cached)) {
      return cached.value;
    }
    // Expired or not found
    if (cached) this.pendingToolCache.delete(intentId);
    return null;
  }

  async deletePendingTool(intentId) {
    this.pendingToolCache.delete(intentId);
    log('DEBUG', `Pending tool DELETED: ${intentId}`);
    return true;
  }

  async getAllPendingTools() {
    const pending = [];
    for (const [intentId, cached] of this.pendingToolCache.entries()) {
      if (!this._isExpired(cached)) {
        pending.push({ intent_id: intentId, ...cached.value });
      } else {
        this.pendingToolCache.delete(intentId);
      }
    }
    return pending;
  }

  // ==================== RECENT TOOL CALLS ====================

  /**
   * Get recent completed tool calls for agent context
   */
  async getRecentTools(limit = 10) {
    // Check in-memory cache
    if (this.recentToolsCache && !this._isExpired(this.recentToolsCache)) {
      return this.recentToolsCache.value.slice(0, limit);
    }

    // Memory miss - query PostgreSQL
    try {
      const result = await dbPool.query(
        `SELECT tool_call_id, function_name, parameters, result, status,
                voice_response, created_at, execution_time_ms
         FROM tool_calls
         WHERE session_id = $1 AND status IN ('COMPLETED', 'FAILED', 'CANCELLED')
         ORDER BY created_at DESC LIMIT $2`,
        [this.sessionId, 20]  // Fetch more for future requests
      );

      if (result.rows.length > 0) {
        this.recentToolsCache = this._wrapWithTTL(result.rows, CACHE_TTL.recent_tools);
        return result.rows.slice(0, limit);
      }
    } catch (err) {
      log('ERROR', `DB query failed for recent tools: ${err.message}`);
    }

    return [];
  }

  /**
   * Add completed tool to recent list (called after tool execution)
   */
  async addCompletedTool(toolCall) {
    // Get existing list
    let recentTools = this.recentToolsCache && !this._isExpired(this.recentToolsCache)
      ? [...this.recentToolsCache.value]
      : await this.getRecentTools(20);

    // Prepend new tool and limit to 20
    recentTools = [toolCall, ...recentTools].slice(0, 20);

    // Update in-memory cache
    this.recentToolsCache = this._wrapWithTTL(recentTools, CACHE_TTL.recent_tools);

    return true;
  }

  // ==================== VECTOR QUERY RESULTS ====================

  /**
   * Store vector query results for email reference
   */
  async setQueryResults(queryId, results) {
    // Store in context with special key
    await this.setContext(`query_results:${queryId}`, results, CACHE_TTL.query_results);
    // Also store as "last_query_results" for easy access
    await this.setContext('last_query_results', results, CACHE_TTL.query_results);
    return true;
  }

  async getQueryResults(queryId = null) {
    if (queryId) {
      return this.getContext(`query_results:${queryId}`);
    }
    return this.getContext('last_query_results');
  }

  // ==================== BOT STATE ====================

  /**
   * Get bot state from Supabase (cached)
   */
  async getBotState() {
    // Check in-memory cache
    if (this.botStateCache && !this._isExpired(this.botStateCache)) {
      return this.botStateCache.value;
    }

    // Fallback to Supabase (external API)
    if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return null;

    try {
      // Extract bot_id from session_id (format: botid_session)
      const botId = this.sessionId.replace('_session', '');

      const response = await fetch(
        `${SUPABASE_URL}/rest/v1/bot_state?bot_id=eq.${botId}&limit=1`,
        {
          headers: {
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        if (data.length > 0) {
          this.botStateCache = this._wrapWithTTL(data[0], CACHE_TTL.bot_state);
          return data[0];
        }
      }
    } catch (err) {
      log('ERROR', `Supabase query failed for bot_state: ${err.message}`);
    }

    return null;
  }

  // ==================== FULL CONTEXT FOR AGENT ====================

  /**
   * Get complete context for OpenAI agent
   * Returns: { pending: [...], recent: [...], queryResults: {...}, botState: {...} }
   */
  async getAgentContext() {
    const [pendingTools, recentTools, queryResults, botState] = await Promise.all([
      this.getAllPendingTools(),
      this.getRecentTools(5),
      this.getQueryResults(),
      this.getBotState()
    ]);

    return {
      session_id: this.sessionId,
      pending_tool_calls: pendingTools,
      recent_tool_calls: recentTools,
      last_query_results: queryResults,
      bot_state: botState,
      cached_at: new Date().toISOString()
    };
  }

  // ==================== CLEANUP ====================

  /**
   * Clear all in-memory caches for this session
   */
  clearCache() {
    this.contextCache.clear();
    this.pendingToolCache.clear();
    this.recentToolsCache = null;
    this.botStateCache = null;
    log('DEBUG', `Session cache cleared: ${this.sessionId}`);
  }
}

// Session cache instances (per connection)
const sessionCaches = new Map();

function getSessionCache(sessionId) {
  if (!sessionCaches.has(sessionId)) {
    sessionCaches.set(sessionId, new SessionCache(sessionId));
  }
  return sessionCaches.get(sessionId);
}

// Cleanup session cache when session ends
function clearSessionCache(sessionId) {
  const cache = sessionCaches.get(sessionId);
  if (cache) {
    cache.clearCache();
    sessionCaches.delete(sessionId);
    log('INFO', `Session cache removed: ${sessionId}`);
  }
}

// ============================================================
// TOOL DEFINITIONS (sent to OpenAI for function calling)
// REAL TOOLS ONLY - Connected to n8n workflows
// ============================================================

const VOICE_TOOLS = [
  {
    type: "function",
    name: "send_email",
    description: "Send an email via Gmail. Use when the user asks to send, compose, or email someone. Requires confirmation before sending.",
    parameters: {
      type: "object",
      properties: {
        to: {
          type: "string",
          description: "Recipient email address"
        },
        subject: {
          type: "string",
          description: "Email subject line"
        },
        body: {
          type: "string",
          description: "Email body content"
        },
        cc: {
          type: "array",
          items: { type: "string" },
          description: "CC recipients (optional)"
        }
      },
      required: ["to", "subject", "body"]
    }
  },
  {
    type: "function",
    name: "get_session_context",
    description: "Retrieve stored context from current or previous sessions. Use to access query results, meeting notes, or any data stored during the conversation.",
    parameters: {
      type: "object",
      properties: {
        session_id: {
          type: "string",
          description: "Session ID to query (optional, defaults to current session)"
        },
        context_key: {
          type: "string",
          description: "Key for the context data (e.g., 'last_query_results', 'meeting_notes')"
        }
      },
      required: ["context_key"]
    }
  },
  {
    type: "function",
    name: "query_vector_db",
    description: "Search the vector database for relevant information. Use when the user asks to look up, find, or search for data, documents, or past information.",
    parameters: {
      type: "object",
      properties: {
        user_query: {
          type: "string",
          description: "The user's natural language search query"
        },
        filters: {
          type: "object",
          description: "Optional filters (date_start, date_end, category, etc.)",
          properties: {
            date_start: { type: "string", description: "Start date filter (ISO format)" },
            date_end: { type: "string", description: "End date filter (ISO format)" },
            category: { type: "string", description: "Category to filter by" }
          }
        },
        limit: {
          type: "number",
          description: "Maximum results to return (default: 10)"
        }
      },
      required: ["user_query"]
    }
  }
];

// ============================================================
// SESSION INSTRUCTIONS (sent to OpenAI on connection)
// Dynamic system prompt with bot_name interrupt support
// ============================================================

/**
 * Generate dynamic session config with bot_name for interrupt trigger
 * @param {string} botName - The bot name from launcher (interrupt trigger word)
 * @returns {Object} Session configuration for OpenAI Realtime API
 */
function getSessionConfig(botName = 'Assistant') {
  const interruptInstruction = botName && botName !== 'Assistant'
    ? `
INTERRUPT TRIGGER - "${botName}":
If the user says "${botName}" (your name) at any point, IMMEDIATELY:
1. Stop whatever you're saying mid-sentence
2. Briefly apologize: "Sorry about that."
3. Say: "Yes?"
4. Wait for the user's next instruction
This is a HARD STOP - prioritize this over completing any thought.`
    : '';

  return {
    modalities: ["text", "audio"],
    instructions: `You are ${botName}, an AI voice assistant participating in a Microsoft Teams meeting via Recall.ai.

CONTEXT:
- You joined this Teams meeting as a voice bot via Recall.ai
- You can hear all meeting participants through real-time transcription
- Your responses are converted to speech and played in the meeting
- The user who started this session can interact with you directly

CAPABILITIES (REAL TOOLS ONLY):
- Send emails via Gmail (send_email) - Always confirm before sending
- Search the vector database (query_vector_db) - Find documents, data, information
- Get session context (get_session_context) - Retrieve previously stored data
${interruptInstruction}

EMAIL WORKFLOW:
When asked to send an email:
1. Confirm the recipient, subject, and key points with the user
2. Draft the email content
3. Read back the draft and ask for confirmation
4. Only call send_email after explicit user confirmation
5. Report success/failure after sending

DATA LOOKUP WORKFLOW:
When asked to find or look up information:
1. Use query_vector_db with the user's query
2. Summarize results clearly
3. Store results in context for email reference if needed

CONVERSATION STYLE:
- Be concise - this is a voice interface in a live meeting
- Confirm actions before executing (especially emails)
- After tool execution, summarize the result naturally
- If a request is ambiguous, ask ONE clarifying question

CRITICAL RULES:
- NEVER simulate or pretend to complete actions - always use actual tools
- NEVER send emails without explicit user confirmation
- NEVER say "I can help you with that" without using the tool
- You have full context of all previous tool calls in this conversation
- When referencing data from query_vector_db, be specific about what you found`,
    voice: "alloy",
    input_audio_format: "pcm16",
    output_audio_format: "pcm16",
    input_audio_transcription: {
      model: "whisper-1"
    },
    turn_detection: {
      type: "server_vad",
      threshold: 0.5,
      prefix_padding_ms: 300,
      silence_duration_ms: 500
    },
    tools: VOICE_TOOLS,
    tool_choice: "auto"
  };
}

// Default config for backward compatibility (when bot_name not available)
const SESSION_CONFIG = getSessionConfig();

// ============================================================
// CONVERSATION CONTEXT MANAGEMENT
// ============================================================

/**
 * ConversationContext maintains full conversation history including tool calls.
 * OpenAI Realtime API maintains context automatically, but we track it for:
 * 1. Logging to n8n
 * 2. Tool execution context (n8n needs to know conversation history)
 * 3. Session recovery if needed
 */
class ConversationContext {
  constructor(connectionId) {
    this.connectionId = connectionId;
    this.items = []; // Full conversation history
    this.toolCalls = []; // Just tool calls for quick reference
    this.startTime = new Date().toISOString();
    this.lastActivity = new Date().toISOString();
  }

  addUserMessage(transcript) {
    this.lastActivity = new Date().toISOString();
    this.items.push({
      type: 'user_message',
      content: transcript,
      timestamp: this.lastActivity
    });
  }

  addAssistantMessage(transcript) {
    this.lastActivity = new Date().toISOString();
    this.items.push({
      type: 'assistant_message',
      content: transcript,
      timestamp: this.lastActivity
    });
  }

  addToolCall(name, args, callId) {
    this.lastActivity = new Date().toISOString();
    const toolCall = {
      type: 'tool_call',
      name,
      args,
      callId,
      timestamp: this.lastActivity,
      result: null // Will be set when result comes back
    };
    this.items.push(toolCall);
    this.toolCalls.push(toolCall);
    return toolCall;
  }

  setToolResult(callId, result) {
    this.lastActivity = new Date().toISOString();
    const toolCall = this.toolCalls.find(tc => tc.callId === callId);
    if (toolCall) {
      toolCall.result = result;
      toolCall.completedAt = this.lastActivity;
    }
    this.items.push({
      type: 'tool_result',
      callId,
      result,
      timestamp: this.lastActivity
    });
  }

  /**
   * Get context summary for n8n tool execution
   * This gives n8n the conversation history so tools can be context-aware
   */
  getToolExecutionContext() {
    return {
      connectionId: this.connectionId,
      sessionStart: this.startTime,
      lastActivity: this.lastActivity,
      recentMessages: this.items.slice(-10), // Last 10 items for context
      previousToolCalls: this.toolCalls.map(tc => ({
        name: tc.name,
        args: tc.args,
        result: tc.result,
        timestamp: tc.timestamp
      })),
      messageCount: this.items.length,
      toolCallCount: this.toolCalls.length
    };
  }

  /**
   * Get full transcript for logging
   */
  getFullTranscript() {
    return this.items.map(item => {
      switch (item.type) {
        case 'user_message':
          return `[USER ${item.timestamp}]: ${item.content}`;
        case 'assistant_message':
          return `[ASSISTANT ${item.timestamp}]: ${item.content}`;
        case 'tool_call':
          return `[TOOL_CALL ${item.timestamp}]: ${item.name}(${JSON.stringify(item.args)})`;
        case 'tool_result':
          return `[TOOL_RESULT ${item.timestamp}]: ${JSON.stringify(item.result)}`;
        default:
          return `[UNKNOWN ${item.timestamp}]: ${JSON.stringify(item)}`;
      }
    }).join('\n');
  }

  /**
   * Get summary for final logging
   */
  getSummary() {
    const userMessages = this.items.filter(i => i.type === 'user_message').length;
    const assistantMessages = this.items.filter(i => i.type === 'assistant_message').length;
    const toolCalls = this.toolCalls.length;
    const successfulTools = this.toolCalls.filter(tc => tc.result?.success).length;

    return {
      connectionId: this.connectionId,
      startTime: this.startTime,
      endTime: new Date().toISOString(),
      durationMs: Date.now() - new Date(this.startTime).getTime(),
      userMessages,
      assistantMessages,
      toolCalls,
      successfulTools,
      failedTools: toolCalls - successfulTools,
      toolsUsed: [...new Set(this.toolCalls.map(tc => tc.name))]
    };
  }
}

// ============================================================
// CONNECTION MANAGER WITH CIRCUIT BREAKER
// ============================================================

/**
 * Manages OpenAI WebSocket connections with exponential backoff and circuit breaker
 */
class ConnectionManager {
  constructor() {
    this.consecutiveFailures = 0;
    this.circuitBreakerOpen = false;
    this.lastFailureTime = null;
  }

  async connectWithRetry(connectionId) {
    // Circuit breaker check
    if (this.circuitBreakerOpen) {
      const cooldown = Date.now() - this.lastFailureTime;
      if (cooldown < CIRCUIT_BREAKER_COOLDOWN_MS) {
        throw new Error(`Circuit breaker open - cooling down (${Math.ceil((CIRCUIT_BREAKER_COOLDOWN_MS - cooldown) / 1000)}s remaining)`);
      }
      // Reset circuit breaker after cooldown
      this.circuitBreakerOpen = false;
      this.consecutiveFailures = 0;
      log('INFO', `[${connectionId}] Circuit breaker reset after cooldown`);
    }

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const ws = await this._attemptConnection(connectionId);
        this.consecutiveFailures = 0;
        return ws;
      } catch (error) {
        this.consecutiveFailures++;
        this.lastFailureTime = Date.now();

        if (attempt === MAX_RETRIES - 1) {
          this.circuitBreakerOpen = true;
          log('ERROR', `[${connectionId}] All ${MAX_RETRIES} connection attempts failed - circuit breaker opened`);
          throw error;
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s
        const delayMs = RETRY_BASE_DELAY_MS * Math.pow(2, attempt);
        log('WARN', `[${connectionId}] Connection attempt ${attempt + 1}/${MAX_RETRIES} failed, retrying in ${delayMs}ms`);
        await new Promise(r => setTimeout(r, delayMs));
      }
    }
  }

  async _attemptConnection(connectionId) {
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
        reject(new Error('OpenAI connection timeout after 30s'));
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

  getStatus() {
    return {
      consecutiveFailures: this.consecutiveFailures,
      circuitBreakerOpen: this.circuitBreakerOpen,
      lastFailureTime: this.lastFailureTime
    };
  }
}

// Global connection manager instance
const connectionManager = new ConnectionManager();

// ============================================================
// AUDIO TRANSMISSION MONITOR
// ============================================================

/**
 * Monitors audio packet transmission quality
 */
class AudioTransmissionMonitor {
  constructor(connectionId) {
    this.connectionId = connectionId;
    this.packetsSent = 0;
    this.packetsReceived = 0;
    this.audioGaps = [];
    this.lastPacketTime = Date.now();
  }

  trackPacket(type) {
    const now = Date.now();

    if (type === 'sent') {
      this.packetsSent++;
    }
    if (type === 'received') {
      this.packetsReceived++;

      // Check for audio gaps (>500ms between packets)
      const gap = now - this.lastPacketTime;
      if (gap > 500) {
        this.audioGaps.push({
          timestamp: now,
          gapDurationMs: gap
        });

        if (gap > 2000) {
          log('WARN', `[${this.connectionId}] Significant audio gap detected: ${gap}ms`);
        }
      }
    }

    this.lastPacketTime = now;
  }

  getPacketLossRate() {
    if (this.packetsSent === 0) return 0;
    return 1 - (this.packetsReceived / this.packetsSent);
  }

  checkHealth() {
    const lossRate = this.getPacketLossRate();
    const isHealthy = lossRate < AUDIO_LOSS_THRESHOLD;

    if (!isHealthy) {
      log('WARN', `[${this.connectionId}] Audio transmission unhealthy: ${(lossRate * 100).toFixed(1)}% packet loss`);
    }

    return {
      packetLossRate: lossRate,
      isHealthy,
      packetsSent: this.packetsSent,
      packetsReceived: this.packetsReceived,
      totalGaps: this.audioGaps.length,
      largestGapMs: this.audioGaps.length > 0
        ? Math.max(...this.audioGaps.map(g => g.gapDurationMs))
        : 0
    };
  }

  reset() {
    this.packetsSent = 0;
    this.packetsReceived = 0;
    this.audioGaps = [];
    this.lastPacketTime = Date.now();
  }
}

// ============================================================
// SUPABASE BOT STATE LOOKUP
// ============================================================

/**
 * Query Supabase bot_state table to get bot_id for a session
 * The launcher workflow (kUcUSyPgz4Z9mYBt) writes bot_id here when creating bots
 *
 * @param {string} sessionId - The session ID to look up
 * @returns {Promise<{bot_id: string, meeting_url: string, status: string}|null>}
 */
async function getBotStateFromSupabase(sessionId) {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    log('DEBUG', `Supabase not configured, cannot look up bot_state`);
    return null;
  }

  try {
    // Query bot_state table for this session (includes bot_name for interrupt trigger)
    const response = await fetch(
      `${SUPABASE_URL}/rest/v1/bot_state?session_id=eq.${encodeURIComponent(sessionId)}&select=bot_id,bot_name,meeting_url,status,created_at&order=created_at.desc&limit=1`,
      {
        headers: {
          'apikey': SUPABASE_ANON_KEY,
          'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
          'Accept': 'application/json'
        },
        signal: AbortSignal.timeout(5000) // 5 second timeout
      }
    );

    if (!response.ok) {
      throw new Error(`Supabase API error: ${response.status} ${response.statusText}`);
    }

    const results = await response.json();

    if (results && results.length > 0) {
      log('INFO', `Found bot_state for session ${sessionId}: bot_id=${results[0].bot_id}`);
      return results[0];
    }

    log('DEBUG', `No bot_state found for session ${sessionId}`);
    return null;

  } catch (error) {
    log('ERROR', `Failed to query Supabase bot_state: ${error.message}`);
    return null;
  }
}

/**
 * Query Supabase for the most recent active bot (fallback when session ID not matched)
 * @returns {Promise<{bot_id: string, session_id: string, meeting_url: string}|null>}
 */
async function getLatestActiveBotFromSupabase() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    return null;
  }

  try {
    // Get the most recently created bot that's in 'active' or 'joining' status
    const response = await fetch(
      `${SUPABASE_URL}/rest/v1/bot_state?status=in.(active,joining,created)&select=bot_id,bot_name,session_id,meeting_url,status,created_at&order=created_at.desc&limit=1`,
      {
        headers: {
          'apikey': SUPABASE_ANON_KEY,
          'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
          'Accept': 'application/json'
        },
        signal: AbortSignal.timeout(5000)
      }
    );

    if (!response.ok) {
      throw new Error(`Supabase API error: ${response.status}`);
    }

    const results = await response.json();

    if (results && results.length > 0) {
      log('INFO', `Found latest active bot: bot_id=${results[0].bot_id}, session=${results[0].session_id}`);
      return results[0];
    }

    return null;

  } catch (error) {
    log('ERROR', `Failed to query latest active bot: ${error.message}`);
    return null;
  }
}

// ============================================================
// RECALL.AI AUDIO OUTPUT
// ============================================================

/**
 * Send audio to Recall.ai meeting bot
 * Generates TTS audio and injects it into the meeting
 */
async function sendAudioToRecallBot(botId, text, connectionId) {
  if (!RECALL_API_KEY) {
    log('DEBUG', `[${connectionId}] Recall.ai not configured, skipping audio output`);
    return false;
  }

  const effectiveBotId = botId || RECALL_BOT_ID;
  if (!effectiveBotId) {
    log('WARN', `[${connectionId}] No Recall.ai bot ID available, skipping audio output`);
    return false;
  }

  try {
    log('INFO', `[${connectionId}] Generating TTS audio for Recall.ai...`);

    // Step 1: Generate TTS audio from OpenAI
    const audioResponse = await fetch('https://api.openai.com/v1/audio/speech', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${OPENAI_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'tts-1',
        input: text,
        voice: 'alloy',
        response_format: 'mp3'
      }),
      signal: AbortSignal.timeout(15000) // 15 second timeout for TTS
    });

    if (!audioResponse.ok) {
      throw new Error(`OpenAI TTS failed: ${audioResponse.status} ${audioResponse.statusText}`);
    }

    const audioBuffer = await audioResponse.arrayBuffer();
    const audioBase64 = Buffer.from(audioBuffer).toString('base64');

    log('INFO', `[${connectionId}] Sending audio to Recall.ai bot ${effectiveBotId}...`);

    // Step 2: Send to Recall.ai
    const recallResponse = await fetch(
      `https://us-west-2.recall.ai/api/v1/bot/${effectiveBotId}/output_audio/`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Token ${RECALL_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          kind: 'mp3',
          b64_data: audioBase64
        }),
        signal: AbortSignal.timeout(10000) // 10 second timeout for Recall.ai
      }
    );

    if (!recallResponse.ok) {
      const errorText = await recallResponse.text().catch(() => 'Unknown error');
      throw new Error(`Recall.ai API failed: ${recallResponse.status} ${errorText}`);
    }

    log('INFO', `[${connectionId}] Audio successfully injected into meeting`);
    return true;

  } catch (error) {
    log('ERROR', `[${connectionId}] Failed to send audio to Recall.ai: ${error.message}`);
    return false;
  }
}

// ============================================================
// LOGGING UTILITIES
// ============================================================

const LOG_LEVELS = { DEBUG: 0, INFO: 1, WARN: 2, ERROR: 3 };
const currentLogLevel = LOG_LEVELS[process.env.LOG_LEVEL?.toUpperCase()] ?? LOG_LEVELS.INFO;

function log(level, ...args) {
  if (LOG_LEVELS[level] >= currentLogLevel) {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${level}]`, ...args);
  }
}

// ============================================================
// MANDATORY DATABASE LOGGING
// ============================================================

/**
 * Log to database - MANDATORY, never optional
 * This is the core logging function that writes directly to PostgreSQL
 */
async function logToDatabase(tableName, data) {
  try {
    switch (tableName) {
      case 'tool_executions':
        await dbPool.query(
          `INSERT INTO tool_executions
           (session_id, connection_id, function_name, args, result, voice_response, status, execution_time_ms, retry_attempts)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
          [
            data.session_id,
            data.connection_id,
            data.function_name,
            JSON.stringify(data.args || {}),
            JSON.stringify(data.result || {}),
            data.voice_response || null,
            data.status || 'success',
            data.execution_time_ms || 0,
            data.retry_attempts || 0
          ]
        );
        break;

      case 'audit_trail':
        await dbPool.query(
          `INSERT INTO audit_trail
           (session_id, connection_id, event_type, event_source, severity, event_data, user_email, meeting_id, latency_ms, event_timestamp)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())`,
          [
            data.session_id,
            data.connection_id,
            data.event_type,
            data.event_source || 'relay_server',
            data.severity || 'INFO',
            JSON.stringify(data.event_data || {}),
            data.user_email || null,
            data.meeting_id || null,
            data.latency_ms || null
          ]
        );
        break;

      case 'user_session_analytics':
        await dbPool.query(
          `INSERT INTO user_session_analytics
           (user_email, session_id, bot_id, session_duration_seconds, total_interactions,
            tools_called, tools_successful, training_interactions, documentation_queries,
            audio_quality_score, packet_loss_rate, started_at, ended_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
          [
            data.user_email || 'anonymous',
            data.session_id,
            data.bot_id || null,
            data.session_duration_seconds || 0,
            data.total_interactions || 0,
            data.tools_called || 0,
            data.tools_successful || 0,
            data.training_interactions || 0,
            data.documentation_queries || 0,
            data.audio_quality_score || null,
            data.packet_loss_rate || null,
            data.started_at,
            data.ended_at
          ]
        );
        break;

      case 'training_metrics':
        await dbPool.query(
          `INSERT INTO training_metrics
           (user_email, session_id, topic, event_type, question_asked, user_response, is_correct, confidence_score, knowledge_gap, time_spent_seconds)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
          [
            data.user_email || 'anonymous',
            data.session_id,
            data.topic || null,
            data.event_type || null,
            data.question_asked || null,
            data.user_response || null,
            data.is_correct ?? null,
            data.confidence_score || null,
            data.knowledge_gap || null,
            data.time_spent_seconds || null
          ]
        );
        break;

      default:
        log('WARN', `Unknown table for logging: ${tableName}`);
    }

    log('DEBUG', `Logged to ${tableName} successfully`);

  } catch (error) {
    // Log failure but DON'T throw - logging failure shouldn't crash conversation
    log('ERROR', `Database logging failed for ${tableName}: ${error.message}`);

    // Queue for retry if buffer not full
    if (pendingLogs.length < MAX_PENDING_LOGS) {
      pendingLogs.push({
        tableName,
        data,
        error: error.message,
        timestamp: Date.now(),
        retryCount: 0
      });
    } else {
      log('ERROR', 'Pending logs buffer full - dropping log entry');
    }
  }
}

/**
 * Process pending logs (retry failed writes)
 * Called periodically to flush the queue
 */
async function processPendingLogs() {
  if (pendingLogs.length === 0) return;

  log('INFO', `Processing ${pendingLogs.length} pending log entries...`);

  const toProcess = pendingLogs.splice(0, 50); // Process in batches of 50

  for (const entry of toProcess) {
    if (entry.retryCount < 3) {
      try {
        await logToDatabase(entry.tableName, entry.data);
      } catch (error) {
        entry.retryCount++;
        if (entry.retryCount < 3) {
          pendingLogs.push(entry); // Re-queue for retry
        } else {
          log('ERROR', `Giving up on log entry after 3 retries: ${entry.tableName}`);
        }
      }
    }
  }
}

// Process pending logs every 30 seconds
setInterval(processPendingLogs, 30000);

// ============================================================
// DATABASE QUERY HANDLERS
// ============================================================

/**
 * Query conversation history from database
 * Used by query_conversation_history tool
 */
async function queryConversationHistory({ query_type, limit = 10, function_filter, since_hours = 24 }, connectionId) {
  const sinceTime = new Date(Date.now() - since_hours * 60 * 60 * 1000).toISOString();

  try {
    let query, params, voiceResponse;

    switch (query_type) {
      case 'recent_tools':
        if (function_filter) {
          query = `SELECT function_name, args, result, voice_response, status, created_at
                   FROM tool_executions
                   WHERE created_at > $1 AND function_name = $2
                   ORDER BY created_at DESC LIMIT $3`;
          params = [sinceTime, function_filter, limit];
        } else {
          query = `SELECT function_name, args, result, voice_response, status, created_at
                   FROM tool_executions
                   WHERE created_at > $1
                   ORDER BY created_at DESC LIMIT $2`;
          params = [sinceTime, limit];
        }
        break;

      case 'past_conversations':
        query = `SELECT session_id, user_email, total_interactions, tools_called, started_at, ended_at
                 FROM user_session_analytics
                 WHERE started_at > $1
                 ORDER BY started_at DESC LIMIT $2`;
        params = [sinceTime, limit];
        break;

      case 'training_history':
        query = `SELECT topic, event_type, question_asked, user_response, is_correct, confidence_score, created_at
                 FROM training_metrics
                 WHERE created_at > $1
                 ORDER BY created_at DESC LIMIT $2`;
        params = [sinceTime, limit];
        break;

      case 'audit_events':
        query = `SELECT event_type, event_source, severity, event_data, event_timestamp
                 FROM audit_trail
                 WHERE event_timestamp > $1
                 ORDER BY event_timestamp DESC LIMIT $2`;
        params = [sinceTime, limit];
        break;

      default:
        return {
          success: false,
          error: `Unknown query type: ${query_type}`,
          voice_response: `I don't recognize the query type "${query_type}". Please try recent_tools, past_conversations, training_history, or audit_events.`
        };
    }

    const result = await dbPool.query(query, params);

    // Format voice-friendly response
    voiceResponse = formatQueryResultsForVoice(result.rows, query_type, function_filter);

    return {
      success: true,
      data: result.rows,
      count: result.rows.length,
      query_type,
      since_hours,
      voice_response: voiceResponse
    };

  } catch (error) {
    log('ERROR', `[${connectionId}] Query failed: ${error.message}`);
    return {
      success: false,
      error: error.message,
      voice_response: "I had trouble retrieving that information from the database. Please try again."
    };
  }
}

/**
 * Query user analytics from database
 * Used by query_user_analytics tool
 */
async function queryUserAnalytics({ metric_type, time_range = 'week' }, connectionId) {
  try {
    // Calculate time range
    let intervalClause;
    switch (time_range) {
      case 'today': intervalClause = "NOW() - INTERVAL '1 day'"; break;
      case 'week': intervalClause = "NOW() - INTERVAL '7 days'"; break;
      case 'month': intervalClause = "NOW() - INTERVAL '30 days'"; break;
      case 'all_time': intervalClause = "'1970-01-01'::timestamp"; break;
      default: intervalClause = "NOW() - INTERVAL '7 days'";
    }

    let query, voiceResponse;

    switch (metric_type) {
      case 'session_summary':
        query = `SELECT
                   COUNT(DISTINCT session_id) as total_sessions,
                   COALESCE(SUM(total_interactions), 0) as total_interactions,
                   COALESCE(AVG(session_duration_seconds), 0)::int as avg_duration_seconds,
                   COALESCE(SUM(tools_called), 0) as total_tools_called
                 FROM user_session_analytics
                 WHERE started_at > ${intervalClause}`;
        break;

      case 'tool_usage':
        query = `SELECT function_name, COUNT(*) as call_count,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
                   ROUND(100.0 * SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 1) as success_rate
                 FROM tool_executions
                 WHERE created_at > ${intervalClause}
                 GROUP BY function_name
                 ORDER BY call_count DESC`;
        break;

      case 'training_progress':
        query = `SELECT topic,
                   COUNT(*) as total_attempts,
                   SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct,
                   ROUND(100.0 * SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as accuracy_pct,
                   ROUND(AVG(confidence_score)::numeric, 2) as avg_confidence
                 FROM training_metrics
                 WHERE created_at > ${intervalClause} AND is_correct IS NOT NULL
                 GROUP BY topic
                 ORDER BY accuracy_pct DESC`;
        break;

      case 'engagement_score':
        query = `SELECT
                   COUNT(DISTINCT session_id) as sessions,
                   COALESCE(SUM(total_interactions), 0) as interactions,
                   COALESCE(SUM(tools_called), 0) as tools,
                   COALESCE(SUM(training_interactions), 0) as training_activities,
                   COALESCE(SUM(documentation_queries), 0) as doc_queries,
                   ROUND(AVG(audio_quality_score)::numeric, 2) as avg_audio_quality
                 FROM user_session_analytics
                 WHERE started_at > ${intervalClause}`;
        break;

      default:
        return {
          success: false,
          error: `Unknown metric type: ${metric_type}`,
          voice_response: `I don't recognize the metric type "${metric_type}". Please try session_summary, tool_usage, training_progress, or engagement_score.`
        };
    }

    const result = await dbPool.query(query);

    // Format voice-friendly response
    voiceResponse = formatAnalyticsForVoice(result.rows, metric_type, time_range);

    return {
      success: true,
      data: result.rows,
      metric_type,
      time_range,
      voice_response: voiceResponse
    };

  } catch (error) {
    log('ERROR', `[${connectionId}] Analytics query failed: ${error.message}`);
    return {
      success: false,
      error: error.message,
      voice_response: "I had trouble retrieving your analytics. Please try again."
    };
  }
}

/**
 * Format query results for voice output
 */
function formatQueryResultsForVoice(rows, queryType, functionFilter) {
  if (!rows || rows.length === 0) {
    return `I didn't find any ${queryType.replace(/_/g, ' ')} in the specified time range.`;
  }

  switch (queryType) {
    case 'recent_tools':
      if (functionFilter) {
        return `I found ${rows.length} ${functionFilter.replace(/_/g, ' ')} actions. ${
          rows.slice(0, 3).map(r => r.voice_response || `${r.function_name} was ${r.status}`).join('. ')
        }`;
      }
      const toolCounts = rows.reduce((acc, r) => {
        acc[r.function_name] = (acc[r.function_name] || 0) + 1;
        return acc;
      }, {});
      const toolSummary = Object.entries(toolCounts)
        .map(([name, count]) => `${count} ${name.replace(/_/g, ' ')} action${count > 1 ? 's' : ''}`)
        .join(', ');
      return `In the recent history, you have ${toolSummary}.`;

    case 'past_conversations':
      return `You've had ${rows.length} conversation session${rows.length > 1 ? 's' : ''} recently, with a total of ${
        rows.reduce((sum, r) => sum + (r.total_interactions || 0), 0)
      } interactions.`;

    case 'training_history':
      const correctCount = rows.filter(r => r.is_correct).length;
      const topics = [...new Set(rows.map(r => r.topic).filter(Boolean))];
      return `You've completed ${rows.length} training activities${
        topics.length > 0 ? ` on topics including ${topics.slice(0, 3).join(', ')}` : ''
      }, with ${correctCount} correct answers.`;

    case 'audit_events':
      const severityCounts = rows.reduce((acc, r) => {
        acc[r.severity] = (acc[r.severity] || 0) + 1;
        return acc;
      }, {});
      return `I found ${rows.length} audit events: ${
        Object.entries(severityCounts).map(([sev, count]) => `${count} ${sev}`).join(', ')
      }.`;

    default:
      return `Found ${rows.length} results.`;
  }
}

/**
 * Format analytics for voice output
 */
function formatAnalyticsForVoice(rows, metricType, timeRange) {
  if (!rows || rows.length === 0) {
    return `I don't have any ${metricType.replace(/_/g, ' ')} data for the ${timeRange.replace(/_/g, ' ')} period.`;
  }

  const row = rows[0]; // Most analytics queries return a single aggregated row
  const timeLabel = timeRange === 'today' ? 'today' :
                    timeRange === 'week' ? 'this week' :
                    timeRange === 'month' ? 'this month' : 'overall';

  switch (metricType) {
    case 'session_summary':
      return `${timeLabel.charAt(0).toUpperCase() + timeLabel.slice(1)}, you've had ${row.total_sessions || 0} session${(row.total_sessions || 0) !== 1 ? 's' : ''} with ${row.total_interactions || 0} total interactions and ${row.total_tools_called || 0} tool calls. Your average session lasted about ${Math.round((row.avg_duration_seconds || 0) / 60)} minutes.`;

    case 'tool_usage':
      if (rows.length === 0) return `No tools have been used ${timeLabel}.`;
      const topTools = rows.slice(0, 3);
      return `${timeLabel.charAt(0).toUpperCase() + timeLabel.slice(1)}, your most used tools are: ${
        topTools.map(r => `${r.function_name.replace(/_/g, ' ')} with ${r.call_count} calls and ${r.success_rate}% success rate`).join('; ')
      }.`;

    case 'training_progress':
      if (rows.length === 0) return `No training activities recorded ${timeLabel}.`;
      const topTopics = rows.slice(0, 3);
      return `Your training progress ${timeLabel}: ${
        topTopics.map(r => `${r.topic || 'general'} at ${r.accuracy_pct}% accuracy`).join(', ')
      }.`;

    case 'engagement_score':
      return `Your engagement ${timeLabel}: ${row.sessions || 0} sessions, ${row.interactions || 0} interactions, ${row.tools || 0} tool uses, ${row.training_activities || 0} training activities, and ${row.doc_queries || 0} documentation queries.`;

    default:
      return `Analytics retrieved for ${metricType}.`;
  }
}

// ============================================================
// N8N INTEGRATION
// ============================================================

/**
 * Execute a tool via n8n webhook
 * This is where the "tool execution layer" happens
 *
 * Uses per-tool webhook mapping (TOOL_WEBHOOKS) for direct workflow calls.
 * Each tool has its own dedicated n8n workflow endpoint.
 *
 * IMPORTANT: Includes conversation context so n8n can make context-aware decisions
 */
async function executeToolViaN8n(functionName, args, connectionId, conversationContext) {
  const sessionId = conversationContext?.connectionId || connectionId;
  const cache = getSessionCache(sessionId);

  // ==================== CACHE-FIRST FOR GET_SESSION_CONTEXT ====================
  // Try to serve from cache before hitting n8n (latency optimization)
  if (functionName === 'get_session_context' && args.context_key) {
    const cachedContext = await cache.getContext(args.context_key);
    if (cachedContext) {
      log('INFO', `[${connectionId}] get_session_context served from cache: ${args.context_key}`);
      return {
        success: true,
        cached: true,
        context_key: args.context_key,
        context_value: cachedContext,
        message: `Retrieved ${args.context_key} from session cache`
      };
    }
  }

  // Look up the per-tool webhook URL
  const toolWebhookUrl = TOOL_WEBHOOKS[functionName];

  // Fall back to dispatcher if tool-specific URL not found
  const webhookUrl = toolWebhookUrl || N8N_TOOLS_WEBHOOK;

  if (!webhookUrl) {
    log('ERROR', `[${connectionId}] No webhook configured for tool: ${functionName}`);
    return {
      success: false,
      error: 'NO_WEBHOOK_CONFIGURED',
      message: `Tool ${functionName} is not configured. Available tools: ${Object.keys(TOOL_WEBHOOKS).join(', ')}`
    };
  }

  try {
    log('INFO', `[${connectionId}] Executing tool via n8n: ${functionName} → ${webhookUrl}`);

    const headers = {
      'Content-Type': 'application/json'
    };

    if (WEBHOOK_SECRET) {
      headers['X-Webhook-Secret'] = WEBHOOK_SECRET;
    }

    // Include conversation context so n8n can make context-aware decisions
    const toolContext = conversationContext ? conversationContext.getToolExecutionContext() : null;

    // Build the request body - different format for per-tool vs dispatcher
    const requestBody = toolWebhookUrl
      ? {
          // Per-tool webhook: send args directly
          ...args,
          connection_id: connectionId,
          session_id: sessionId,
          timestamp: new Date().toISOString(),
          context: toolContext
        }
      : {
          // Dispatcher webhook: include function name
          function: functionName,
          args,
          connection_id: connectionId,
          timestamp: new Date().toISOString(),
          context: toolContext
        };

    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
      signal: AbortSignal.timeout(30000) // 30 second timeout
    });

    if (!response.ok) {
      throw new Error(`n8n webhook returned ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    log('INFO', `[${connectionId}] Tool executed successfully: ${functionName}`);

    // ==================== POST-EXECUTION CACHING ====================

    // Cache query_vector_db results for email reference
    if (functionName === 'query_vector_db' && result.success && result.results) {
      const queryId = `q_${Date.now()}`;
      await cache.setQueryResults(queryId, {
        query: args.user_query,
        filters: args.filters,
        results: result.results,
        summary: result.summary,
        executed_at: new Date().toISOString()
      });
      log('INFO', `[${connectionId}] Vector query results cached: ${queryId}`);
      result.query_id = queryId; // Add to response so agent can reference it
    }

    // Cache get_session_context results
    if (functionName === 'get_session_context' && result.success && result.context_value) {
      await cache.setContext(args.context_key, result.context_value);
      log('DEBUG', `[${connectionId}] Session context cached: ${args.context_key}`);
    }

    // Cache completed tool call for agent context
    if (result.success) {
      await cache.addCompletedTool({
        tool_call_id: `tc_${Date.now()}`,
        function_name: functionName,
        parameters: args,
        result: result,
        status: 'COMPLETED',
        voice_response: result.voice_response || result.message,
        created_at: new Date().toISOString()
      });
    }

    return result;

  } catch (error) {
    log('ERROR', `[${connectionId}] Tool execution failed: ${error.message}`);

    // Cache failed tool call for context
    await cache.addCompletedTool({
      tool_call_id: `tc_${Date.now()}`,
      function_name: functionName,
      parameters: args,
      result: null,
      status: 'FAILED',
      error_message: error.message,
      created_at: new Date().toISOString()
    });

    return {
      success: false,
      error: error.message,
      message: `Failed to execute ${functionName}: ${error.message}`
    };
  }
}

/**
 * Send transcript chunk to n8n Logging Agent (async, non-blocking)
 * This preserves your existing logging infrastructure
 *
 * ENHANCED: Includes full conversation context including tool calls
 */
function sendToLoggingAgent(transcript, metadata, connectionId, conversationContext = null) {
  if (!N8N_LOGGING_WEBHOOK) {
    log('DEBUG', `[${connectionId}] No N8N_LOGGING_WEBHOOK configured, skipping logging`);
    return;
  }

  // Fire-and-forget - don't await, don't block the conversation
  const headers = {
    'Content-Type': 'application/json'
  };

  if (WEBHOOK_SECRET) {
    headers['X-Webhook-Secret'] = WEBHOOK_SECRET;
  }

  // Build logging payload with context
  const payload = {
    transcript,
    metadata,
    connection_id: connectionId,
    timestamp: new Date().toISOString()
  };

  // Include conversation context if available
  if (conversationContext) {
    // For incremental logs, include recent context
    if (metadata.type !== 'conversation_complete') {
      payload.recent_context = conversationContext.items.slice(-5); // Last 5 items
      payload.tool_call_count = conversationContext.toolCalls.length;
    } else {
      // For final log, include full summary and transcript
      payload.summary = conversationContext.getSummary();
      payload.full_transcript = conversationContext.getFullTranscript();
    }
  }

  fetch(N8N_LOGGING_WEBHOOK, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  }).catch(error => {
    log('WARN', `[${connectionId}] Logging webhook failed (non-blocking): ${error.message}`);
  });

  log('DEBUG', `[${connectionId}] Transcript sent to logging agent (async)`);
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
// WEBSOCKET SERVER
// ============================================================

// ============================================================
// DATABASE VERIFICATION (Fail-fast if mandatory logging unavailable)
// ============================================================

async function verifyDatabaseConnection() {
  try {
    const result = await dbPool.query('SELECT NOW() as current_time');
    log('INFO', `Database connection verified: ${result.rows[0].current_time}`);
    return true;
  } catch (error) {
    log('ERROR', `CRITICAL: Database connection failed: ${error.message}`);
    log('ERROR', 'The relay server cannot start without mandatory logging capability.');
    process.exit(1);
  }
}

// Verify database before starting server
await verifyDatabaseConnection();

// Create HTTP server that handles both health checks AND WebSocket upgrades
const httpServer = http.createServer((req, res) => {
  if (req.url === '/health' && req.method === 'GET') {
    // Health check endpoint on main port for Railway
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      uptime: process.uptime(),
      connections: connections.size,
      database: 'connected',
      timestamp: new Date().toISOString()
    }));
  } else {
    // Non-WebSocket, non-health requests get 426 Upgrade Required
    res.writeHead(426, { 'Content-Type': 'text/plain' });
    res.end('WebSocket connection required');
  }
});

// Attach WebSocket server to HTTP server (handles upgrade requests)
const wss = new WebSocketServer({
  server: httpServer,
  perMessageDeflate: false // Disable compression for lower latency
});

// Start HTTP server (handles both HTTP health checks and WebSocket upgrades)
httpServer.listen(PORT, () => {
  log('INFO', `Server listening on port ${PORT} (HTTP + WebSocket)`);
});

log('INFO', `WebSocket relay server starting on port ${PORT}...`);
log('INFO', `Database: CONNECTED (mandatory logging enabled)`);
log('INFO', `Supabase: ${SUPABASE_URL ? 'CONNECTED (bot_state lookup enabled)' : '(not configured)'}`);
log('INFO', `n8n Tools Webhook: ${N8N_TOOLS_WEBHOOK || '(not configured)'}`);
log('INFO', `n8n Logging Webhook: ${N8N_LOGGING_WEBHOOK || '(optional backup)'}`);
log('INFO', `Recall.ai Integration: ${RECALL_API_KEY ? 'ENABLED' : '(not configured)'}`);
log('INFO', `Recall.ai Bot ID: ${RECALL_BOT_ID || '(dynamic via Supabase lookup)'}`);
log('INFO', `Tools available: ${VOICE_TOOLS.map(t => t.name).join(', ')}`);

wss.on('connection', async (browserWs, req) => {
  const connectionId = generateConnectionId();
  const clientIp = req.socket.remoteAddress;

  log('INFO', `[${connectionId}] Browser connected from ${clientIp}`);

  // Parse URL and query parameters
  const url = new URL(req.url, `http://${req.headers.host}`);

  // Validate connection path
  if (url.pathname !== '/' && url.pathname !== '') {
    log('WARN', `[${connectionId}] Invalid path: ${url.pathname}`);
    browserWs.close(1008, 'Invalid path');
    return;
  }

  // Extract optional parameters from query string
  // Client can pass: ?session_id=xxx or ?bot_id=xxx
  const clientSessionId = url.searchParams.get('session_id');
  const clientBotId = url.searchParams.get('bot_id');

  // Connection state with ConversationContext for full history tracking
  const conversationContext = new ConversationContext(connectionId);
  const audioMonitor = new AudioTransmissionMonitor(connectionId);

  // Determine bot_id: priority is client-provided > Supabase lookup > env default
  let recallBotId = clientBotId || RECALL_BOT_ID;
  let botState = null;

  // Look up bot_id from Supabase if we have Supabase configured
  if (SUPABASE_URL && SUPABASE_ANON_KEY) {
    if (clientSessionId) {
      // Try to find bot by session_id provided by client
      botState = await getBotStateFromSupabase(clientSessionId);
      if (botState?.bot_id) {
        recallBotId = botState.bot_id;
        log('INFO', `[${connectionId}] Using bot_id from Supabase session lookup: ${recallBotId}`);
      }
    }

    // Fallback: get latest active bot if no specific session matched
    if (!recallBotId) {
      botState = await getLatestActiveBotFromSupabase();
      if (botState?.bot_id) {
        recallBotId = botState.bot_id;
        log('INFO', `[${connectionId}] Using latest active bot from Supabase: ${recallBotId}`);
      }
    }
  }

  const state = {
    connectionId,
    openaiWs: null,
    messageQueue: [],
    isOpenAIConnected: false,
    isBrowserConnected: true,
    conversationContext, // Full conversation history including tool calls
    audioMonitor,        // Track audio quality
    recallBotId,         // Bot ID for Recall.ai audio output
    botState,            // Full bot state from Supabase (if available)
    clientSessionId      // Original session ID from client (for cross-referencing)
  };

  connections.set(connectionId, state);

  // MANDATORY: Log session start to audit trail
  logToDatabase('audit_trail', {
    session_id: connectionId,
    connection_id: connectionId,
    event_type: 'session_start',
    event_source: 'relay_server',
    severity: 'INFO',
    event_data: {
      client_ip: clientIp,
      recall_bot_id: state.recallBotId || null,
      client_session_id: clientSessionId || null,
      supabase_bot_state: botState ? {
        bot_id: botState.bot_id,
        meeting_url: botState.meeting_url,
        status: botState.status
      } : null,
      session_start: conversationContext.startTime
    }
  });

  // ============================================================
  // MESSAGE HANDLERS
  // ============================================================

  // Browser -> OpenAI (pass through)
  const handleBrowserMessage = (data) => {
    try {
      const message = data.toString();
      const event = JSON.parse(message);

      if (!event.type?.includes('audio')) {
        log('DEBUG', `[${connectionId}] Browser -> OpenAI: ${event.type}`);
      }

      if (state.isOpenAIConnected && state.openaiWs?.readyState === WebSocket.OPEN) {
        state.openaiWs.send(message);
      } else {
        state.messageQueue.push(message);
        log('DEBUG', `[${connectionId}] Queued message (OpenAI not ready)`);
      }
    } catch (error) {
      log('ERROR', `[${connectionId}] Failed to parse browser message:`, error.message);
    }
  };

  // OpenAI -> Browser (with function call interception and context tracking)
  const handleOpenAIMessage = async (data) => {
    try {
      const message = data.toString();
      const event = JSON.parse(message);

      // Track audio packets for quality monitoring
      if (event.type?.includes('audio')) {
        audioMonitor.trackPacket('received');
      } else {
        log('DEBUG', `[${connectionId}] OpenAI -> Browser: ${event.type}`);
      }

      // Handle function calls - AI agent decided to use a tool!
      if (event.type === 'response.function_call_arguments.done') {
        const { call_id, name, arguments: argsString } = event;
        log('INFO', `[${connectionId}] AI decided to call tool: ${name}`);

        // Parse arguments
        let args;
        try {
          args = JSON.parse(argsString);
        } catch {
          args = {};
        }

        // Track tool call in conversation context (BEFORE execution)
        conversationContext.addToolCall(name, args, call_id);

        const startTime = Date.now();
        let result;

        // Handle query tools directly (database access)
        if (name === 'query_conversation_history') {
          result = await queryConversationHistory(args, connectionId);
        } else if (name === 'query_user_analytics') {
          result = await queryUserAnalytics(args, connectionId);
        } else {
          // Execute other tools via n8n with full conversation context
          result = await executeToolViaN8n(name, args, connectionId, conversationContext);
        }

        const executionTimeMs = Date.now() - startTime;

        // MANDATORY: Log every tool execution to database
        logToDatabase('tool_executions', {
          session_id: connectionId,
          connection_id: connectionId,
          function_name: name,
          args: args,
          result: result,
          voice_response: result?.voice_response || null,
          status: result?.success === false ? 'error' : 'success',
          execution_time_ms: executionTimeMs,
          retry_attempts: 0
        });

        // Log to audit trail for compliance
        logToDatabase('audit_trail', {
          session_id: connectionId,
          connection_id: connectionId,
          event_type: 'tool_call',
          event_source: name.startsWith('query_') ? 'relay_server' : 'n8n',
          severity: result?.success === false ? 'WARN' : 'INFO',
          event_data: {
            function_name: name,
            args: args,
            success: result?.success !== false,
            execution_time_ms: executionTimeMs
          },
          latency_ms: executionTimeMs
        });

        // Update context with result
        conversationContext.setToolResult(call_id, result);

        // Send function call result back to OpenAI
        const functionResult = {
          type: 'conversation.item.create',
          item: {
            type: 'function_call_output',
            call_id,
            output: JSON.stringify(result)
          }
        };

        if (state.openaiWs?.readyState === WebSocket.OPEN) {
          state.openaiWs.send(JSON.stringify(functionResult));
          log('INFO', `[${connectionId}] Function result sent to OpenAI: ${name}`);

          // Tell OpenAI to continue the response
          state.openaiWs.send(JSON.stringify({ type: 'response.create' }));
        }
      }

      // Capture user transcripts and add to conversation context
      if (event.type === 'conversation.item.input_audio_transcription.completed') {
        const transcript = event.transcript;
        if (transcript) {
          // Add to conversation context (tracks full history including tool calls)
          conversationContext.addUserMessage(transcript);

          // Send to logging agent with context (async, non-blocking)
          sendToLoggingAgent(transcript, { role: 'user' }, connectionId, conversationContext);
        }
      }

      // Capture assistant responses and add to conversation context
      if (event.type === 'response.audio_transcript.done') {
        const transcript = event.transcript;
        if (transcript) {
          // Add to conversation context
          conversationContext.addAssistantMessage(transcript);

          // Send to logging agent with context (async, non-blocking)
          sendToLoggingAgent(transcript, { role: 'assistant' }, connectionId, conversationContext);

          // Send audio to Recall.ai meeting (async, non-blocking)
          // This enables the bot to speak in Teams/Zoom meetings
          if (RECALL_API_KEY && state.recallBotId) {
            sendAudioToRecallBot(state.recallBotId, transcript, connectionId)
              .catch(err => log('WARN', `[${connectionId}] Recall.ai audio send failed: ${err.message}`));
          }
        }
      }

      // Forward to browser
      if (state.isBrowserConnected && browserWs.readyState === WebSocket.OPEN) {
        browserWs.send(message);
      }
    } catch (error) {
      log('ERROR', `[${connectionId}] Failed to handle OpenAI message:`, error.message);
    }
  };

  // Set up browser WebSocket handlers
  browserWs.on('message', handleBrowserMessage);

  browserWs.on('close', (code, reason) => {
    log('INFO', `[${connectionId}] Browser disconnected: ${code} ${reason}`);
    state.isBrowserConnected = false;

    // Get audio quality stats
    const audioHealth = audioMonitor.checkHealth();
    const summary = conversationContext.getSummary();

    // MANDATORY: Log session end to database
    logToDatabase('audit_trail', {
      session_id: connectionId,
      connection_id: connectionId,
      event_type: 'session_end',
      event_source: 'relay_server',
      severity: 'INFO',
      event_data: {
        disconnect_code: code,
        disconnect_reason: reason?.toString() || 'normal',
        ...summary,
        audio_quality: audioHealth
      }
    });

    // MANDATORY: Log session analytics
    if (conversationContext.items.length > 0) {
      logToDatabase('user_session_analytics', {
        user_email: 'anonymous', // Can be enhanced with user identification
        session_id: connectionId,
        bot_id: state.recallBotId || null,
        session_duration_seconds: Math.round(summary.durationMs / 1000),
        total_interactions: summary.userMessages + summary.assistantMessages,
        tools_called: summary.toolCalls,
        tools_successful: summary.successfulTools,
        training_interactions: conversationContext.toolCalls.filter(tc =>
          ['knowledge_check', 'get_training_progress'].includes(tc.name)
        ).length,
        documentation_queries: conversationContext.toolCalls.filter(tc =>
          tc.name === 'search_documentation'
        ).length,
        audio_quality_score: audioHealth.isHealthy ? 1.0 : (1 - audioHealth.packetLossRate),
        packet_loss_rate: audioHealth.packetLossRate,
        started_at: summary.startTime,
        ended_at: summary.endTime
      });
    }

    // Send complete conversation record to logging agent (legacy - keep for n8n integration)
    if (conversationContext.items.length > 0) {
      log('INFO', `[${connectionId}] Session summary: ${summary.userMessages} user msgs, ${summary.assistantMessages} assistant msgs, ${summary.toolCalls} tool calls`);
      log('INFO', `[${connectionId}] Audio quality: ${(audioHealth.packetLossRate * 100).toFixed(1)}% loss, ${audioHealth.totalGaps} gaps`);

      sendToLoggingAgent(
        conversationContext.getFullTranscript(),
        {
          type: 'conversation_complete',
          ...summary,
          audioQuality: audioHealth
        },
        connectionId,
        conversationContext
      );
    }

    if (state.openaiWs?.readyState === WebSocket.OPEN) {
      state.openaiWs.close(1000, 'Browser disconnected');
    }

    connections.delete(connectionId);
  });

  browserWs.on('error', (error) => {
    log('ERROR', `[${connectionId}] Browser WebSocket error:`, error.message);
  });

  // Keepalive pings
  const pingInterval = setInterval(() => {
    if (browserWs.readyState === WebSocket.OPEN) {
      browserWs.ping();
    } else {
      clearInterval(pingInterval);
    }
  }, 30000);

  browserWs.on('close', () => clearInterval(pingInterval));

  // ============================================================
  // CONNECT TO OPENAI (with retry and circuit breaker)
  // ============================================================

  try {
    state.openaiWs = await connectionManager.connectWithRetry(connectionId);

    state.openaiWs.on('message', handleOpenAIMessage);

    state.openaiWs.on('close', (code, reason) => {
      log('INFO', `[${connectionId}] OpenAI disconnected: ${code} ${reason}`);
      state.isOpenAIConnected = false;

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

    // Send session configuration with tools
    // Use dynamic config with bot_name from Supabase (for interrupt trigger)
    const botName = state.botState?.bot_name || 'Assistant';
    const dynamicSessionConfig = getSessionConfig(botName);
    const sessionUpdate = {
      type: 'session.update',
      session: dynamicSessionConfig
    };
    state.openaiWs.send(JSON.stringify(sessionUpdate));
    log('INFO', `[${connectionId}] Session configured with ${VOICE_TOOLS.length} tools, bot_name="${botName}"`);

    log('INFO', `[${connectionId}] Relay established: Browser <-> OpenAI`);

  } catch (error) {
    log('ERROR', `[${connectionId}] Failed to connect to OpenAI:`, error.message);
    browserWs.close(1011, `OpenAI connection failed: ${error.message}`);
    connections.delete(connectionId);
  }
});

// ============================================================
// HEALTH CHECK ENDPOINT
// ============================================================

const healthServer = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'healthy',
      activeConnections: connections.size,
      uptime: process.uptime(),
      integrations: {
        n8nTools: !!N8N_TOOLS_WEBHOOK,
        n8nLogging: !!N8N_LOGGING_WEBHOOK,
        recallAi: !!RECALL_API_KEY
      },
      connectionManager: connectionManager.getStatus(),
      toolsAvailable: VOICE_TOOLS.map(t => t.name)
    }));
  } else if (req.url === '/stats') {
    // Detailed stats including per-connection audio quality
    const connectionStats = Array.from(connections.entries()).map(([id, state]) => ({
      connectionId: id,
      isOpenAIConnected: state.isOpenAIConnected,
      isBrowserConnected: state.isBrowserConnected,
      messageCount: state.conversationContext?.items.length || 0,
      toolCallCount: state.conversationContext?.toolCalls.length || 0,
      audioQuality: state.audioMonitor?.checkHealth() || null,
      hasRecallBot: !!state.recallBotId
    }));

    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      activeConnections: connections.size,
      connections: connectionStats,
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      connectionManager: connectionManager.getStatus(),
      integrations: {
        n8nToolsWebhook: N8N_TOOLS_WEBHOOK || null,
        n8nLoggingWebhook: N8N_LOGGING_WEBHOOK || null,
        recallAiConfigured: !!RECALL_API_KEY
      },
      tools: VOICE_TOOLS
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

  for (const [connectionId, state] of connections) {
    log('INFO', `[${connectionId}] Closing connection...`);
    if (state.openaiWs?.readyState === WebSocket.OPEN) {
      state.openaiWs.close(1000, 'Server shutdown');
    }
  }

  wss.close(() => {
    log('INFO', 'WebSocket server closed');
    httpServer.close(() => {
      log('INFO', 'HTTP server closed');
      healthServer.close(() => {
        log('INFO', 'Health server closed');
        process.exit(0);
      });
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
