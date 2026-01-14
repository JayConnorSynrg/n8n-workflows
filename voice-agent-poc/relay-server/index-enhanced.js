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
import crypto from 'crypto';

dotenv.config();

// ============================================================
// LOGGING UTILITIES (must be defined before use)
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
// SECURITY: Callback URL Whitelist (Priority 1 - SSRF Protection)
// ============================================================
// Only allow callbacks to these domains to prevent SSRF attacks
// Add your relay server domains and any trusted n8n instances
const ALLOWED_CALLBACK_DOMAINS = [
  'localhost',
  '127.0.0.1',
  'jayconnorexe.app.n8n.cloud',  // n8n cloud
  // Add Railway/production domains when deployed:
  // 'your-relay.railway.app',
];

// Parse CALLBACK_WHITELIST env var for additional domains
if (process.env.CALLBACK_WHITELIST) {
  const extraDomains = process.env.CALLBACK_WHITELIST.split(',').map(d => d.trim());
  ALLOWED_CALLBACK_DOMAINS.push(...extraDomains);
}

/**
 * Validate that a callback URL is on the whitelist
 * @param {string} callbackUrl - URL to validate
 * @returns {{ valid: boolean, reason?: string }}
 */
function validateCallbackUrl(callbackUrl) {
  if (!callbackUrl) {
    return { valid: true }; // No callback URL is valid (won't be used)
  }

  try {
    const url = new URL(callbackUrl);

    // Reject non-HTTPS in production (allow HTTP for localhost)
    if (url.protocol !== 'https:' && !['localhost', '127.0.0.1'].includes(url.hostname)) {
      return { valid: false, reason: 'HTTPS required for non-localhost callbacks' };
    }

    // Check against whitelist
    const hostname = url.hostname.toLowerCase();
    const isAllowed = ALLOWED_CALLBACK_DOMAINS.some(domain => {
      const d = domain.toLowerCase();
      return hostname === d || hostname.endsWith(`.${d}`);
    });

    if (!isAllowed) {
      return { valid: false, reason: `Domain '${hostname}' not in callback whitelist` };
    }

    return { valid: true };
  } catch (e) {
    return { valid: false, reason: `Invalid URL: ${e.message}` };
  }
}

// ============================================================
// N8N CALL TIMEOUT CONFIGURATION (Priority 2)
// ============================================================
const N8N_CALL_TIMEOUT_MS = parseInt(process.env.N8N_CALL_TIMEOUT_MS) || 30000;  // 30 second default

// ============================================================
// RATE LIMITING CONFIGURATION (Priority 2)
// ============================================================
const RATE_LIMIT_WINDOW_MS = 60000;  // 1 minute window
const RATE_LIMIT_MAX_REQUESTS = parseInt(process.env.RATE_LIMIT_MAX_REQUESTS) || 100;

// In-memory rate limit tracker: Map<ip, { count: number, windowStart: number }>
const rateLimitTracker = new Map();

/**
 * Check if request should be rate limited
 * @param {string} ip - Client IP address
 * @returns {{ allowed: boolean, remaining: number, resetAt: number }}
 */
function checkRateLimit(ip) {
  const now = Date.now();
  let tracker = rateLimitTracker.get(ip);

  // New IP or window expired - reset
  if (!tracker || (now - tracker.windowStart) > RATE_LIMIT_WINDOW_MS) {
    tracker = { count: 1, windowStart: now };
    rateLimitTracker.set(ip, tracker);
    return { allowed: true, remaining: RATE_LIMIT_MAX_REQUESTS - 1, resetAt: now + RATE_LIMIT_WINDOW_MS };
  }

  // Increment counter
  tracker.count++;
  const remaining = Math.max(0, RATE_LIMIT_MAX_REQUESTS - tracker.count);
  const resetAt = tracker.windowStart + RATE_LIMIT_WINDOW_MS;

  if (tracker.count > RATE_LIMIT_MAX_REQUESTS) {
    return { allowed: false, remaining: 0, resetAt };
  }

  return { allowed: true, remaining, resetAt };
}

// Cleanup stale rate limit entries every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [ip, tracker] of rateLimitTracker.entries()) {
    if ((now - tracker.windowStart) > RATE_LIMIT_WINDOW_MS * 2) {
      rateLimitTracker.delete(ip);
    }
  }
}, 300000);

// ============================================================
// IDEMPOTENCY KEY TRACKING (Priority 2)
// ============================================================
// Track processed gate callbacks to prevent duplicate processing
const processedGateCallbacks = new Map();  // Map<idempotency_key, { timestamp, response }>
const IDEMPOTENCY_TTL_MS = 300000;  // 5 minutes

/**
 * Check if this gate callback was already processed (idempotency)
 * @param {string} toolCallId
 * @param {number} gate
 * @returns {{ duplicate: boolean, cachedResponse?: object }}
 */
function checkIdempotency(toolCallId, gate) {
  const key = `${toolCallId}:gate${gate}`;
  const cached = processedGateCallbacks.get(key);

  if (cached && (Date.now() - cached.timestamp) < IDEMPOTENCY_TTL_MS) {
    return { duplicate: true, cachedResponse: cached.response };
  }

  return { duplicate: false };
}

/**
 * Record that a gate callback was processed
 * @param {string} toolCallId
 * @param {number} gate
 * @param {object} response
 */
function recordGateCallback(toolCallId, gate, response) {
  const key = `${toolCallId}:gate${gate}`;
  processedGateCallbacks.set(key, { timestamp: Date.now(), response });
}

// Cleanup old idempotency entries every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [key, entry] of processedGateCallbacks.entries()) {
    if ((now - entry.timestamp) > IDEMPOTENCY_TTL_MS) {
      processedGateCallbacks.delete(key);
    }
  }
}, 300000);

// ============================================================
// HMAC AUTHENTICATION (Priority 3 - Callback Security)
// ============================================================
// HMAC signatures ensure callbacks are from trusted n8n workflows
// Set N8N_WEBHOOK_SECRET env var to enable (shared with n8n HTTP nodes)

const N8N_WEBHOOK_SECRET = process.env.N8N_WEBHOOK_SECRET;
const HMAC_ENABLED = !!N8N_WEBHOOK_SECRET;
const HMAC_TIMESTAMP_TOLERANCE_MS = 300000;  // 5 minutes tolerance for clock skew

if (HMAC_ENABLED) {
  log('INFO', 'HMAC authentication enabled for callback endpoints');
} else {
  log('WARN', 'HMAC authentication DISABLED - callbacks are unauthenticated');
  log('WARN', 'Set N8N_WEBHOOK_SECRET env var to enable (use same value in n8n HTTP nodes)');
}

/**
 * Compute HMAC-SHA256 signature for request body
 * @param {string} body - Raw request body
 * @param {string} timestamp - Unix timestamp from header
 * @returns {string} - Hex-encoded HMAC signature
 */
function computeHmacSignature(body, timestamp) {
  const message = `${timestamp}.${body}`;
  return crypto.createHmac('sha256', N8N_WEBHOOK_SECRET)
    .update(message)
    .digest('hex');
}

/**
 * Verify HMAC signature on incoming callback request
 * @param {object} req - HTTP request
 * @param {string} rawBody - Raw request body string
 * @returns {{ valid: boolean, reason?: string }}
 */
function verifyHmacSignature(req, rawBody) {
  // If HMAC is disabled, always pass
  if (!HMAC_ENABLED) {
    return { valid: true, reason: 'HMAC disabled' };
  }

  const signature = req.headers['x-n8n-signature'] || req.headers['x-webhook-signature'];
  const timestamp = req.headers['x-n8n-timestamp'] || req.headers['x-webhook-timestamp'];

  if (!signature) {
    return { valid: false, reason: 'Missing signature header (x-n8n-signature or x-webhook-signature)' };
  }

  if (!timestamp) {
    return { valid: false, reason: 'Missing timestamp header (x-n8n-timestamp or x-webhook-timestamp)' };
  }

  // Check timestamp freshness to prevent replay attacks
  const timestampMs = parseInt(timestamp) * 1000;  // Assume unix seconds
  const now = Date.now();
  if (Math.abs(now - timestampMs) > HMAC_TIMESTAMP_TOLERANCE_MS) {
    return { valid: false, reason: `Timestamp too old or too far in future (${Math.abs(now - timestampMs)}ms difference)` };
  }

  // Compute expected signature
  const expectedSignature = computeHmacSignature(rawBody, timestamp);

  // Constant-time comparison to prevent timing attacks
  try {
    const sigBuffer = Buffer.from(signature, 'hex');
    const expectedBuffer = Buffer.from(expectedSignature, 'hex');

    if (sigBuffer.length !== expectedBuffer.length) {
      return { valid: false, reason: 'Signature length mismatch' };
    }

    if (!crypto.timingSafeEqual(sigBuffer, expectedBuffer)) {
      return { valid: false, reason: 'Invalid signature' };
    }

    return { valid: true };
  } catch (e) {
    return { valid: false, reason: `Signature verification error: ${e.message}` };
  }
}

// ============================================================
// GATE 2 WAITING MECHANISM (Priority 1 - True Human-in-the-Loop)
// ============================================================
// When Gate 2 (READY_TO_SEND) arrives, we hold the HTTP response
// and wait for user confirmation via voice/OpenAI before continuing.
// This enables true human-in-the-loop at the workflow level.

const GATE2_CONFIRMATION_TIMEOUT_MS = parseInt(process.env.GATE2_CONFIRMATION_TIMEOUT_MS) || 30000;

// Pending Gate 2 confirmations: Map<tool_call_id, { resolver, rejecter, timeoutId, createdAt }>
const pendingGate2Confirmations = new Map();

/**
 * Create a pending Gate 2 confirmation that waits for user response
 * @param {string} toolCallId - The tool call awaiting confirmation
 * @returns {Promise<{ continue: boolean, cancel: boolean, reason?: string }>}
 */
function createGate2Confirmation(toolCallId) {
  return new Promise((resolve, reject) => {
    const createdAt = Date.now();

    log('INFO', `[GATE2-FLOW] Creating confirmation wait for ${toolCallId}`);
    log('INFO', `[GATE2-FLOW] Timeout set to ${GATE2_CONFIRMATION_TIMEOUT_MS}ms (${GATE2_CONFIRMATION_TIMEOUT_MS / 1000}s)`);
    log('INFO', `[GATE2-FLOW] Pending confirmations: ${pendingGate2Confirmations.size + 1}`);

    // Set timeout for confirmation
    const timeoutId = setTimeout(() => {
      const pending = pendingGate2Confirmations.get(toolCallId);
      if (pending) {
        pendingGate2Confirmations.delete(toolCallId);
        const waitedMs = Date.now() - pending.createdAt;
        log('WARN', `[GATE2-FLOW] Confirmation TIMEOUT for ${toolCallId} after ${waitedMs}ms`);
        log('WARN', `[GATE2-FLOW] Auto-cancelling to prevent stale workflow`);
        // On timeout, cancel the operation to be safe
        resolve({ continue: false, cancel: true, reason: 'Confirmation timeout' });
      }
    }, GATE2_CONFIRMATION_TIMEOUT_MS);

    pendingGate2Confirmations.set(toolCallId, {
      resolve,
      reject,
      timeoutId,
      createdAt
    });

    log('INFO', `[GATE2-FLOW] HTTP response HELD - Waiting for user to say "yes/confirm" or "no/cancel"`);
    log('DEBUG', `[GATE2-FLOW] Resolution paths:`);
    log('DEBUG', `[GATE2-FLOW]   1. User confirms → resolveGate2Confirmation(${toolCallId}, true)`);
    log('DEBUG', `[GATE2-FLOW]   2. User cancels → resolveGate2Confirmation(${toolCallId}, false)`);
    log('DEBUG', `[GATE2-FLOW]   3. /tool-confirm endpoint → POST with confirmed: true`);
    log('DEBUG', `[GATE2-FLOW]   4. /tool-cancel endpoint → POST to cancel`);
    log('DEBUG', `[GATE2-FLOW]   5. Timeout → Auto-cancel after ${GATE2_CONFIRMATION_TIMEOUT_MS}ms`);
  });
}

/**
 * Resolve a pending Gate 2 confirmation (called when user confirms/cancels)
 * @param {string} toolCallId - The tool call to confirm/cancel
 * @param {boolean} confirmed - Whether user confirmed (true) or cancelled (false)
 * @param {string} reason - Optional reason for the decision
 * @returns {boolean} - Whether a pending confirmation was found and resolved
 */
function resolveGate2Confirmation(toolCallId, confirmed, reason = '') {
  const pending = pendingGate2Confirmations.get(toolCallId);
  if (!pending) {
    log('WARN', `[GATE2-FLOW] No pending confirmation found for ${toolCallId}`);
    log('WARN', `[GATE2-FLOW] Possible causes: already resolved, timed out, or wrong ID`);
    log('DEBUG', `[GATE2-FLOW] Current pending IDs: ${Array.from(pendingGate2Confirmations.keys()).join(', ') || '(none)'}`);
    return false;
  }

  const waitedMs = Date.now() - pending.createdAt;
  clearTimeout(pending.timeoutId);
  pendingGate2Confirmations.delete(toolCallId);

  const action = confirmed ? 'CONFIRMED' : 'CANCELLED';
  const reasonText = reason || (confirmed ? 'User confirmed' : 'User cancelled');

  log('INFO', `[GATE2-FLOW] ========================================`);
  log('INFO', `[GATE2-FLOW] CONFIRMATION RESOLVED: ${action}`);
  log('INFO', `[GATE2-FLOW] Tool Call ID: ${toolCallId}`);
  log('INFO', `[GATE2-FLOW] Wait Time: ${waitedMs}ms (${(waitedMs / 1000).toFixed(1)}s)`);
  log('INFO', `[GATE2-FLOW] Reason: ${reasonText}`);
  log('INFO', `[GATE2-FLOW] Remaining pending: ${pendingGate2Confirmations.size}`);
  log('INFO', `[GATE2-FLOW] ========================================`);

  if (confirmed) {
    log('INFO', `[GATE2-FLOW] Returning {continue: true} to n8n workflow - execution will proceed`);
  } else {
    log('INFO', `[GATE2-FLOW] Returning {cancel: true} to n8n workflow - execution will abort`);
  }

  pending.resolve({
    continue: confirmed,
    cancel: !confirmed,
    reason: reasonText
  });

  return true;
}

/**
 * Check if there's a pending Gate 2 confirmation for a tool call
 * @param {string} toolCallId
 * @returns {boolean}
 */
function hasPendingGate2Confirmation(toolCallId) {
  return pendingGate2Confirmations.has(toolCallId);
}

// Cleanup stale Gate 2 confirmations every minute
setInterval(() => {
  const now = Date.now();
  for (const [id, pending] of pendingGate2Confirmations.entries()) {
    if ((now - pending.createdAt) > GATE2_CONFIRMATION_TIMEOUT_MS * 2) {
      clearTimeout(pending.timeoutId);
      pending.resolve({ continue: false, cancel: true, reason: 'Stale confirmation cleanup' });
      pendingGate2Confirmations.delete(id);
    }
  }
}, 60000);

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
// GATED EXECUTION - Cancel Requests & Gate Callback State
// ============================================================
// Pattern: Track cancel requests per tool_call_id or intent_id
// n8n workflows call back to /tool-progress with gate status
// This state determines whether to continue or cancel execution

/**
 * Cancel requests map: Maps tool_call_id/intent_id to cancel state
 * When a user says "stop" or "cancel", we set this flag
 * n8n gate callbacks check this before proceeding
 */
const cancelRequests = new Map();  // Map<string, { cancelled: boolean, reason: string, timestamp: number }>

/**
 * Active tool callbacks - Maps tool_call_id to connection info
 * Used to route gate notifications back to the correct WebSocket
 */
const activeToolCallbacks = new Map();  // Map<tool_call_id, { connectionId, sessionId, ws }>

/**
 * Request cancellation for a tool call
 * @param {string} toolCallId - The tool_call_id or intent_id
 * @param {string} reason - Why cancellation was requested
 */
function requestCancellation(toolCallId, reason = 'User requested') {
  cancelRequests.set(toolCallId, {
    cancelled: true,
    reason,
    timestamp: Date.now()
  });
  log('INFO', `Cancellation requested: ${toolCallId} - ${reason}`);
}

/**
 * Check if a tool call has been cancelled
 * @param {string} toolCallId - The tool_call_id or intent_id
 * @returns {{ cancelled: boolean, reason?: string }}
 */
function checkCancellation(toolCallId) {
  const cancelState = cancelRequests.get(toolCallId);
  if (cancelState && cancelState.cancelled) {
    return { cancelled: true, reason: cancelState.reason };
  }
  return { cancelled: false };
}

/**
 * Clear cancellation state (after processing)
 * @param {string} toolCallId
 */
function clearCancellation(toolCallId) {
  cancelRequests.delete(toolCallId);
  log('DEBUG', `Cancellation cleared: ${toolCallId}`);
}

/**
 * Register a tool callback for gate notifications
 * @param {string} toolCallId
 * @param {object} connectionInfo
 */
function registerToolCallback(toolCallId, connectionInfo) {
  activeToolCallbacks.set(toolCallId, {
    ...connectionInfo,
    registeredAt: Date.now()
  });
  log('DEBUG', `Tool callback registered: ${toolCallId}`);
}

/**
 * Get connection info for a tool callback
 * @param {string} toolCallId
 */
function getToolCallbackInfo(toolCallId) {
  return activeToolCallbacks.get(toolCallId);
}

/**
 * Clear tool callback registration
 * @param {string} toolCallId
 */
function clearToolCallback(toolCallId) {
  activeToolCallbacks.delete(toolCallId);
  log('DEBUG', `Tool callback cleared: ${toolCallId}`);
}

/**
 * Clear all tool callbacks for a specific connection
 * Called when a session ends to clean up any pending gate callbacks
 * @param {string} connectionId
 */
function clearConnectionCallbacks(connectionId) {
  let cleared = 0;
  for (const [toolCallId, info] of activeToolCallbacks.entries()) {
    if (info.connectionId === connectionId) {
      activeToolCallbacks.delete(toolCallId);
      cleared++;
    }
  }
  // Also clear any cancel requests for this connection
  for (const [id, state] of cancelRequests.entries()) {
    // intent_id format typically includes connection ID or session ID
    if (id.includes(connectionId)) {
      cancelRequests.delete(id);
    }
  }
  if (cleared > 0) {
    log('DEBUG', `Cleared ${cleared} tool callbacks for connection: ${connectionId}`);
  }
}

// Cleanup stale cancel requests and callbacks (older than 10 minutes)
setInterval(() => {
  const staleThreshold = Date.now() - 600000;  // 10 minutes

  for (const [id, state] of cancelRequests.entries()) {
    if (state.timestamp < staleThreshold) {
      cancelRequests.delete(id);
    }
  }

  for (const [id, info] of activeToolCallbacks.entries()) {
    if (info.registeredAt < staleThreshold) {
      activeToolCallbacks.delete(id);
    }
  }
}, 60000);  // Run every minute

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
  },
  {
    type: "function",
    name: "confirm_pending_action",
    description: "Confirm or cancel a pending action (like sending an email). Call this when the user says 'yes', 'confirm', 'send it', 'go ahead' or 'no', 'cancel', 'stop', 'nevermind' in response to a confirmation request.",
    parameters: {
      type: "object",
      properties: {
        tool_call_id: {
          type: "string",
          description: "The ID of the pending tool call to confirm or cancel"
        },
        confirmed: {
          type: "boolean",
          description: "true if user confirmed (yes, send it), false if user cancelled (no, cancel)"
        },
        reason: {
          type: "string",
          description: "Optional reason for the decision"
        }
      },
      required: ["tool_call_id", "confirmed"]
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

    // Generate tool_call_id for gated execution tracking
    const toolCallId = `tc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Build callback URL for gated execution
    // n8n will call this URL at each gate to check for cancellation and report progress
    const callbackUrl = CALLBACK_BASE_URL ? `${CALLBACK_BASE_URL}/tool-progress` : null;

    // Validate callback URL against whitelist (SSRF protection)
    if (callbackUrl) {
      const urlValidation = validateCallbackUrl(callbackUrl);
      if (!urlValidation.valid) {
        log('WARN', `[${connectionId}] Callback URL rejected: ${urlValidation.reason}`);
        // Continue without callback rather than failing the entire tool call
        // This is a security measure, not a critical failure
      }
    }

    // Build the request body - different format for per-tool vs dispatcher
    const requestBody = toolWebhookUrl
      ? {
          // Per-tool webhook: send args directly
          ...args,
          connection_id: connectionId,
          session_id: sessionId,
          tool_call_id: toolCallId,
          callback_url: callbackUrl,  // For gated execution
          timestamp: new Date().toISOString(),
          context: toolContext
        }
      : {
          // Dispatcher webhook: include function name
          function: functionName,
          args,
          connection_id: connectionId,
          tool_call_id: toolCallId,
          callback_url: callbackUrl,  // For gated execution
          timestamp: new Date().toISOString(),
          context: toolContext
        };

    // Register callback for gate notifications (if callback URL is configured)
    if (callbackUrl) {
      // Note: The WebSocket connection is passed via conversationContext.connectionId
      // We'll need to look it up from the connections map
      const connectionState = connections.get(connectionId);
      if (connectionState && connectionState.browserWs) {
        registerToolCallback(toolCallId, {
          connectionId,
          sessionId,
          ws: connectionState.browserWs,
          functionName
        });
        log('DEBUG', `[${connectionId}] Registered gated callback for ${toolCallId}`);
      }
    }

    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
      signal: AbortSignal.timeout(N8N_CALL_TIMEOUT_MS) // Configurable timeout (default 30s)
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

// ============================================================
// HTTP SERVER WITH GATED EXECUTION CALLBACK ENDPOINTS
// ============================================================
// Handles:
// - /health (GET) - Health check for Railway
// - /tool-progress (POST) - n8n gate callbacks for gated execution
// - /tool-cancel (POST) - Request cancellation of a tool call
// - WebSocket upgrades for voice connections

/**
 * Parse JSON body from HTTP request
 */
function parseJSONBody(req, returnRaw = false) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => { body += chunk.toString(); });
    req.on('end', () => {
      try {
        const parsed = body ? JSON.parse(body) : {};
        if (returnRaw) {
          resolve({ parsed, raw: body });
        } else {
          resolve(parsed);
        }
      } catch (e) {
        reject(new Error('Invalid JSON body'));
      }
    });
    req.on('error', reject);
  });
}

/**
 * Send JSON response
 */
function sendJSON(res, statusCode, data) {
  res.writeHead(statusCode, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

/**
 * Notify OpenAI agent about gate status change
 * This injects a message into the conversation so the agent can speak to the user
 * @param {string} connectionId - Connection ID to look up OpenAI WebSocket
 * @param {string} gateStatus - Status of the gate (PREPARING, READY_TO_SEND, COMPLETED, etc.)
 * @param {object} details - Details about the gate status
 */
function notifyAgentOfGateStatus(connectionId, gateStatus, details) {
  const state = connections.get(connectionId);
  if (!state || !state.openaiWs || state.openaiWs.readyState !== WebSocket.OPEN) {
    log('WARN', `Cannot notify agent - OpenAI connection not available for ${connectionId}`);
    return false;
  }

  // Build the prompt based on gate status
  let promptText = '';

  switch (gateStatus) {
    case 'PREPARING':
      // Gate 1 - Just inform user we're starting
      promptText = details.voice_response ||
        `I'm preparing to ${details.functionName || 'execute the action'}. One moment...`;
      break;

    case 'READY_TO_SEND':
      // Gate 2 - Request final confirmation (if needed)
      promptText = details.voice_response ||
        `Ready to send. ${details.message || 'Should I proceed?'}`;
      break;

    case 'COMPLETED':
      // Gate 3 - Announce completion
      promptText = details.voice_response ||
        `Done! ${details.message || 'The action completed successfully.'}`;
      break;

    case 'CANCELLED':
      promptText = details.voice_response ||
        `I've cancelled that action. ${details.message || ''}`;
      break;

    case 'FAILED':
      promptText = details.voice_response ||
        `I'm sorry, there was an error. ${details.message || 'Please try again.'}`;
      break;

    default:
      promptText = details.voice_response || details.message || 'Processing...';
  }

  try {
    // Inject a system message to prompt the agent to speak
    // Using conversation.item.create with a function_call_output to provide context
    // Then response.create to make the agent respond

    // Option 1: Use response.create with instructions override (cleaner)
    state.openaiWs.send(JSON.stringify({
      type: 'response.create',
      response: {
        modalities: ['text', 'audio'],
        instructions: `The user's requested action status has changed to ${gateStatus}. Please inform the user: "${promptText}". Be natural and conversational.`
      }
    }));

    log('INFO', `[${connectionId}] Agent notified of gate ${gateStatus}: ${promptText.substring(0, 50)}...`);
    return true;
  } catch (error) {
    log('ERROR', `Failed to notify agent: ${error.message}`);
    return false;
  }
}

/**
 * Handle gate callback from n8n workflow
 *
 * Gate statuses:
 * - PREPARING (gate 1): Pre-execution, cancellable
 * - READY_TO_SEND (gate 2): Final confirmation before execution
 * - COMPLETED (gate 3): Execution finished successfully
 * - CANCELLED: Execution was cancelled
 * - FAILED: Execution failed
 *
 * Security features:
 * - Rate limiting per IP
 * - Idempotency key deduplication
 * - Callback URL validation (handled at tool dispatch)
 */
async function handleToolProgress(req, res) {
  try {
    // Rate limiting check (Priority 2)
    const clientIp = req.headers['x-forwarded-for']?.split(',')[0]?.trim() ||
                     req.socket.remoteAddress ||
                     'unknown';
    const rateLimitResult = checkRateLimit(clientIp);

    // Add rate limit headers
    res.setHeader('X-RateLimit-Limit', RATE_LIMIT_MAX_REQUESTS);
    res.setHeader('X-RateLimit-Remaining', rateLimitResult.remaining);
    res.setHeader('X-RateLimit-Reset', Math.ceil(rateLimitResult.resetAt / 1000));

    if (!rateLimitResult.allowed) {
      log('WARN', `Rate limit exceeded for ${clientIp}`);
      return sendJSON(res, 429, {
        error: 'Too many requests',
        retry_after_ms: rateLimitResult.resetAt - Date.now()
      });
    }

    // Parse body with raw for HMAC verification
    const { parsed: body, raw: rawBody } = await parseJSONBody(req, true);

    // HMAC Authentication check (Priority 3)
    const hmacResult = verifyHmacSignature(req, rawBody);
    if (!hmacResult.valid) {
      log('WARN', `[HMAC] Verification failed from ${clientIp}: ${hmacResult.reason}`);
      return sendJSON(res, 401, {
        error: 'Unauthorized',
        reason: hmacResult.reason
      });
    }
    if (HMAC_ENABLED) {
      log('DEBUG', `[HMAC] Signature verified for request from ${clientIp}`);
    }

    const {
      tool_call_id,
      intent_id,
      status,
      gate,
      cancellable,
      requires_confirmation,
      result,
      voice_response,
      message,
      execution_time_ms
    } = body;

    const id = tool_call_id || intent_id;

    if (!id) {
      return sendJSON(res, 400, { error: 'Missing tool_call_id or intent_id' });
    }

    // Idempotency check (Priority 2) - prevent duplicate gate processing
    if (gate) {
      const idempotencyResult = checkIdempotency(id, gate);
      if (idempotencyResult.duplicate) {
        log('INFO', `Duplicate gate callback ignored: ${id} gate ${gate}`);
        return sendJSON(res, 200, idempotencyResult.cachedResponse);
      }
    }

    log('INFO', `Gate callback: ${id} - Status: ${status}, Gate: ${gate}`);

    // Check for cancellation request
    const cancelState = checkCancellation(id);
    if (cancelState.cancelled && cancellable) {
      log('INFO', `Cancelling tool call: ${id} - ${cancelState.reason}`);
      clearCancellation(id);

      const cancelResponse = {
        continue: false,
        cancel: true,
        reason: cancelState.reason
      };

      // Record for idempotency
      if (gate) recordGateCallback(id, gate, cancelResponse);

      return sendJSON(res, 200, cancelResponse);
    }

    // Get callback info to notify the WebSocket connection
    const callbackInfo = getToolCallbackInfo(id);

    // Handle different gate statuses
    switch (status) {
      case 'PREPARING':
        // Gate 1: Tool is being prepared
        log('INFO', `Gate 1 (PREPARING): ${id}`);
        if (callbackInfo) {
          // Notify browser WebSocket
          if (callbackInfo.ws) {
            try {
              callbackInfo.ws.send(JSON.stringify({
                type: 'tool_gate',
                tool_call_id: id,
                gate: 1,
                status: 'PREPARING',
                message: message || 'Preparing to execute tool...',
                cancellable: true
              }));
            } catch (e) {
              log('WARN', `Failed to notify WebSocket: ${e.message}`);
            }
          }
          // Notify OpenAI agent to speak to user
          notifyAgentOfGateStatus(callbackInfo.connectionId, 'PREPARING', {
            functionName: callbackInfo.functionName,
            message,
            voice_response
          });
        }
        {
          const response = { continue: true, cancel: false };
          recordGateCallback(id, 1, response);
          return sendJSON(res, 200, response);
        }

      case 'READY_TO_SEND':
        // Gate 2: Ready for final confirmation - TRUE HUMAN-IN-THE-LOOP
        // This holds the HTTP response until user confirms or timeout occurs
        log('INFO', `Gate 2 (READY_TO_SEND): ${id} - Waiting for user confirmation...`);
        if (callbackInfo) {
          // Notify browser WebSocket
          if (callbackInfo.ws) {
            try {
              callbackInfo.ws.send(JSON.stringify({
                type: 'tool_gate',
                tool_call_id: id,
                gate: 2,
                status: 'READY_TO_SEND',
                message: message || 'Ready to execute. Please confirm.',
                requires_confirmation: true,
                cancellable: true,
                awaiting_confirmation: true  // Flag that we're waiting
              }));
            } catch (e) {
              log('WARN', `Failed to notify WebSocket: ${e.message}`);
            }
          }
          // Notify OpenAI agent to ask for final confirmation
          notifyAgentOfGateStatus(callbackInfo.connectionId, 'READY_TO_SEND', {
            functionName: callbackInfo.functionName,
            message,
            voice_response,
            tool_call_id: id  // Include ID so agent can reference it
          });
        }

        // TRUE WAITING: Hold the HTTP response until user confirms/cancels/timeout
        // The createGate2Confirmation promise resolves when:
        // 1. User says "yes/confirm" → resolveGate2Confirmation(id, true)
        // 2. User says "no/cancel" → resolveGate2Confirmation(id, false)
        // 3. Timeout (30s default) → auto-cancel for safety
        try {
          const confirmationResult = await createGate2Confirmation(id);
          recordGateCallback(id, 2, confirmationResult);
          log('INFO', `Gate 2 confirmation result for ${id}: ${JSON.stringify(confirmationResult)}`);
          return sendJSON(res, 200, confirmationResult);
        } catch (error) {
          log('ERROR', `Gate 2 confirmation error for ${id}: ${error.message}`);
          const response = { continue: false, cancel: true, reason: error.message };
          recordGateCallback(id, 2, response);
          return sendJSON(res, 200, response);
        }

      case 'COMPLETED':
        // Gate 3: Tool execution completed
        log('INFO', `Gate 3 (COMPLETED): ${id} - ${voice_response || 'Success'}`);
        if (callbackInfo) {
          // Notify browser WebSocket
          if (callbackInfo.ws) {
            try {
              callbackInfo.ws.send(JSON.stringify({
                type: 'tool_gate',
                tool_call_id: id,
                gate: 3,
                status: 'COMPLETED',
                result: result,
                voice_response: voice_response,
                message: message || 'Tool completed successfully',
                execution_time_ms: execution_time_ms
              }));
            } catch (e) {
              log('WARN', `Failed to notify WebSocket: ${e.message}`);
            }
          }
          // Notify OpenAI agent to announce completion
          notifyAgentOfGateStatus(callbackInfo.connectionId, 'COMPLETED', {
            functionName: callbackInfo.functionName,
            message,
            voice_response,
            result
          });
        }
        // Clear callback registration
        clearToolCallback(id);
        {
          const response = { received: true, status: 'acknowledged' };
          recordGateCallback(id, 3, response);
          return sendJSON(res, 200, response);
        }

      case 'CANCELLED':
        log('INFO', `Tool cancelled: ${id}`);
        if (callbackInfo) {
          // Notify browser WebSocket
          if (callbackInfo.ws) {
            try {
              callbackInfo.ws.send(JSON.stringify({
                type: 'tool_gate',
                tool_call_id: id,
                status: 'CANCELLED',
                message: message || 'Tool execution cancelled',
                voice_response: voice_response || 'The action was cancelled.'
              }));
            } catch (e) {
              log('WARN', `Failed to notify WebSocket: ${e.message}`);
            }
          }
          // Notify OpenAI agent to announce cancellation
          notifyAgentOfGateStatus(callbackInfo.connectionId, 'CANCELLED', {
            functionName: callbackInfo.functionName,
            message,
            voice_response
          });
        }
        clearToolCallback(id);
        clearCancellation(id);
        {
          const response = { received: true, status: 'acknowledged' };
          recordGateCallback(id, 0, response);  // 0 for cancelled
          return sendJSON(res, 200, response);
        }

      case 'FAILED':
        log('ERROR', `Tool failed: ${id} - ${message}`);
        if (callbackInfo) {
          // Notify browser WebSocket
          if (callbackInfo.ws) {
            try {
              callbackInfo.ws.send(JSON.stringify({
                type: 'tool_gate',
                tool_call_id: id,
                status: 'FAILED',
                message: message || 'Tool execution failed',
                voice_response: voice_response || 'Sorry, there was an error executing that action.'
              }));
            } catch (e) {
              log('WARN', `Failed to notify WebSocket: ${e.message}`);
            }
          }
          // Notify OpenAI agent to announce failure
          notifyAgentOfGateStatus(callbackInfo.connectionId, 'FAILED', {
            functionName: callbackInfo.functionName,
            message,
            voice_response
          });
        }
        clearToolCallback(id);
        return sendJSON(res, 200, { received: true, status: 'acknowledged' });

      default:
        log('WARN', `Unknown gate status: ${status}`);
        return sendJSON(res, 200, { continue: true, cancel: false });
    }

  } catch (error) {
    log('ERROR', `Gate callback error: ${error.message}`);
    sendJSON(res, 500, { error: error.message });
  }
}

/**
 * Handle cancel request from external source
 */
async function handleToolCancel(req, res) {
  try {
    const body = await parseJSONBody(req);
    const { tool_call_id, intent_id, reason } = body;

    const id = tool_call_id || intent_id;
    if (!id) {
      return sendJSON(res, 400, { error: 'Missing tool_call_id or intent_id' });
    }

    // If there's a pending Gate 2 confirmation, resolve it as cancelled
    if (hasPendingGate2Confirmation(id)) {
      resolveGate2Confirmation(id, false, reason || 'User cancelled');
      log('INFO', `Gate 2 confirmation cancelled via /tool-cancel: ${id}`);
    }

    requestCancellation(id, reason || 'External cancel request');

    // Notify WebSocket if available
    const callbackInfo = getToolCallbackInfo(id);
    if (callbackInfo && callbackInfo.ws) {
      try {
        callbackInfo.ws.send(JSON.stringify({
          type: 'tool_cancel_requested',
          tool_call_id: id,
          message: 'Cancellation requested'
        }));
      } catch (e) {
        log('WARN', `Failed to notify WebSocket of cancel: ${e.message}`);
      }
    }

    sendJSON(res, 200, { success: true, message: `Cancellation requested for ${id}` });

  } catch (error) {
    log('ERROR', `Cancel request error: ${error.message}`);
    sendJSON(res, 500, { error: error.message });
  }
}

/**
 * Handle tool confirmation requests (for Gate 2 human-in-the-loop)
 * POST /tool-confirm
 * Body: { tool_call_id: string }
 */
async function handleToolConfirm(req, res) {
  try {
    const body = await parseJSONBody(req);
    const { tool_call_id, intent_id } = body;

    const id = tool_call_id || intent_id;
    if (!id) {
      return sendJSON(res, 400, { error: 'Missing tool_call_id or intent_id' });
    }

    // Check if there's a pending Gate 2 confirmation
    if (!hasPendingGate2Confirmation(id)) {
      return sendJSON(res, 404, {
        error: 'No pending confirmation',
        message: `No pending Gate 2 confirmation found for ${id}. It may have timed out or been processed.`
      });
    }

    // Resolve the confirmation
    resolveGate2Confirmation(id, true, 'User confirmed via API');
    log('INFO', `Gate 2 confirmation confirmed via /tool-confirm: ${id}`);

    // Notify WebSocket if available
    const callbackInfo = getToolCallbackInfo(id);
    if (callbackInfo && callbackInfo.ws) {
      try {
        callbackInfo.ws.send(JSON.stringify({
          type: 'tool_confirmed',
          tool_call_id: id,
          message: 'Execution confirmed'
        }));
      } catch (e) {
        log('WARN', `Failed to notify WebSocket of confirm: ${e.message}`);
      }
    }

    sendJSON(res, 200, { success: true, message: `Tool execution confirmed for ${id}` });

  } catch (error) {
    log('ERROR', `Confirm request error: ${error.message}`);
    sendJSON(res, 500, { error: error.message });
  }
}

// Create HTTP server that handles health checks, callbacks, AND WebSocket upgrades
const httpServer = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = url.pathname;

  // Health check endpoint
  if (pathname === '/health' && req.method === 'GET') {
    return sendJSON(res, 200, {
      status: 'healthy',
      uptime: process.uptime(),
      connections: connections.size,
      database: 'connected',
      gated_execution: 'enabled',
      active_callbacks: activeToolCallbacks.size,
      pending_cancellations: cancelRequests.size,
      timestamp: new Date().toISOString()
    });
  }

  // Gate callback endpoint - n8n calls this during gated execution
  if (pathname === '/tool-progress' && req.method === 'POST') {
    return handleToolProgress(req, res);
  }

  // Cancel request endpoint
  if (pathname === '/tool-cancel' && req.method === 'POST') {
    return handleToolCancel(req, res);
  }

  // Confirm request endpoint (for Gate 2 human-in-the-loop)
  if (pathname === '/tool-confirm' && req.method === 'POST') {
    return handleToolConfirm(req, res);
  }

  // Status endpoint - check callback state
  if (pathname.startsWith('/tool-status/') && req.method === 'GET') {
    const id = pathname.split('/')[2];
    if (!id) {
      return sendJSON(res, 400, { error: 'Missing tool_call_id' });
    }
    const cancelState = checkCancellation(id);
    const callbackInfo = getToolCallbackInfo(id);
    return sendJSON(res, 200, {
      tool_call_id: id,
      cancelled: cancelState.cancelled,
      cancel_reason: cancelState.reason,
      has_callback: !!callbackInfo
    });
  }

  // Non-WebSocket, non-API requests get 426 Upgrade Required
  res.writeHead(426, { 'Content-Type': 'text/plain' });
  res.end('WebSocket connection required. API endpoints: /health, /tool-progress, /tool-cancel, /tool-confirm');
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
log('INFO', `Gated Execution: ${CALLBACK_BASE_URL ? `ENABLED (${CALLBACK_BASE_URL}/tool-progress)` : '(not configured - set CALLBACK_BASE_URL)'}`);
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
        } else if (name === 'confirm_pending_action') {
          // Handle Gate 2 confirmation locally (does NOT go to n8n)
          const { tool_call_id, confirmed, reason } = args;
          log('INFO', `[${connectionId}] confirm_pending_action called: ${tool_call_id}, confirmed=${confirmed}`);

          if (!tool_call_id) {
            result = {
              success: false,
              error: 'Missing tool_call_id',
              voice_response: "I need to know which action you're confirming. Could you be more specific?"
            };
          } else if (hasPendingGate2Confirmation(tool_call_id)) {
            // Resolve the pending Gate 2 confirmation
            resolveGate2Confirmation(tool_call_id, confirmed, reason || (confirmed ? 'User confirmed' : 'User cancelled'));
            result = {
              success: true,
              confirmed: confirmed,
              tool_call_id: tool_call_id,
              voice_response: confirmed
                ? "Got it, I'm proceeding with the action now."
                : "Understood, I've cancelled that action."
            };
          } else {
            // No pending confirmation found
            result = {
              success: false,
              error: 'No pending confirmation found for this tool call',
              tool_call_id: tool_call_id,
              voice_response: "I don't have any pending action to confirm right now. Is there something else I can help with?"
            };
          }
        } else if (name === 'get_session_context') {
          // Handle session context retrieval locally (cache-first, then database)
          result = await getAgentContext(connectionId);
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

    // Clean up session cache on connection close
    clearSessionCache(connectionId);
    // Clean up any pending tool callbacks for this connection
    clearConnectionCallbacks(connectionId);

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
    // Clean up session cache and pending tool callbacks on connection failure
    clearSessionCache(connectionId);
    clearConnectionCallbacks(connectionId);
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
