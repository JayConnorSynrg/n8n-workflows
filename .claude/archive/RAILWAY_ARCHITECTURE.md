# Railway Voice Agent - Architecture Documentation

**CRITICAL: READ THIS BEFORE MAKING CHANGES TO VOICE AGENT SYSTEM**

## Railway CLI Connection

```bash
# Login (already authenticated as jcreationsrai@gmail.com)
railway login

# Project: VOICE AGENT - N8N
# Project ID: b061af36-cda8-4458-a41b-fa2695f8dd0d

# Check status
railway status

# View logs
railway logs --tail 50

# Get domain
railway domain
# Returns: https://voice-agent-relay-production.up.railway.app

# View environment variables
railway variables

# Deploy changes (from relay-server directory)
cd voice-agent-poc/relay-server && railway up
```

## System Architecture (Updated: January 2026)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    TEAMS VOICE BOT - COMPLETE ARCHITECTURE                        │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. LAUNCHER WORKFLOW (n8n: kUcUSyPgz4Z9mYBt)                                │ │
│  │    - Form Trigger → Create Recall.ai Bot → Initialize bot_state             │ │
│  │    - Configures Recall.ai to send transcripts to n8n webhook                │ │
│  │    - Sends bot status events to n8n webhook                                 │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                            │
│                                      ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ 2. RECALL.AI BOT (joins Teams meeting)                                      │ │
│  │    - Captures meeting audio via Recall.ai                                   │ │
│  │    - Streams transcripts to: /webhook/voice-bot-v3 (n8n)                    │ │
│  │    - Status callbacks to: /webhook/recall-bot-events (n8n)                  │ │
│  │    - Receives TTS audio via Output Media API ← Railway pushes audio here    │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                            │
│                                      ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ 3. RAILWAY RELAY SERVER (WebSocket + OpenAI Realtime API)                   │ │
│  │    URL: voice-agent-relay-production.up.railway.app                         │ │
│  │                                                                             │ │
│  │    ┌─────────────────────────────────────────────────────────────────────┐  │ │
│  │    │ ENTERPRISE CACHE LAYER (In-Memory + PostgreSQL)                     │  │ │
│  │    │                                                                     │  │ │
│  │    │  In-Memory Map (HOT CACHE) ─── 1-5ms latency                        │  │ │
│  │    │  └── Session context, pending tools, recent tools, bot_state        │  │ │
│  │    │                                                                     │  │ │
│  │    │  PostgreSQL (PERSISTENT) ─── 30-50ms latency (fallback)             │  │ │
│  │    │  └── Persistent audit trail, session_context with TTL               │  │ │
│  │    └─────────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                             │ │
│  │    - Browser connects via WebSocket                                         │ │
│  │    - Bridges to OpenAI Realtime API                                         │ │
│  │    - Tool calls routed DIRECTLY to per-tool webhooks (NO dispatcher)        │ │
│  │    - Pushes TTS audio to Recall.ai Output Media API                         │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                            │
│            ┌─────────────────────────┼─────────────────────────┐                  │
│            │                         │                         │                  │
│            ▼                         ▼                         ▼                  │
│  ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐           │
│  │ SEND EMAIL      │      │ QUERY VECTOR DB │      │ GET SESSION CTX │           │
│  │ /execute-gmail  │      │ /query-vector-db│      │ /get-session-ctx│           │
│  │ (Real Gmail)    │      │ (Real Vector DB)│      │ (Cache-first)   │           │
│  └─────────────────┘      └─────────────────┘      └─────────────────┘           │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Tool Routing (Per-Tool Webhooks - NO Dispatcher)

The relay server routes DIRECTLY to per-tool webhooks:

```javascript
const TOOL_WEBHOOKS = {
  send_email: 'https://jayconnorexe.app.n8n.cloud/webhook/execute-gmail',
  get_session_context: 'https://jayconnorexe.app.n8n.cloud/webhook/get-session-context',
  query_vector_db: 'https://jayconnorexe.app.n8n.cloud/webhook/query-vector-db'
};
```

**3 REAL TOOLS ONLY** - No mock tools, no dispatcher workflow.

## Enterprise Cache Architecture (In-Memory + PostgreSQL)

### Cache Layers

| Layer | Purpose | TTL | Latency |
|-------|---------|-----|---------|
| **In-Memory Map** | Hot cache per session | Variable | ~1-5ms |
| **PostgreSQL** | Persistent source of truth | TTL-based | ~30-50ms |

### Cache TTLs

```javascript
const CACHE_TTL = {
  session_context: 3600,    // 1 hour
  pending_tool: 300,        // 5 minutes (memory-only)
  recent_tools: 1800,       // 30 minutes
  bot_state: 7200,          // 2 hours
  query_results: 900        // 15 minutes
};
```

### Read-Through Pattern

```
1. Check in-memory cache (hot path ~1-5ms)
2. On miss → Query PostgreSQL → Warm in-memory cache
```

### Write-Through Pattern

```
1. Write to PostgreSQL FIRST (persistent source of truth)
2. Update in-memory cache with TTL
```

### Memory Management

- Per-session cache instances with TTL expiry checking
- Automatic cleanup when session ends (`clearSessionCache()`)
- Graceful degradation to DB-only if memory pressure

## Railway Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `DATABASE_URL` | Railway PostgreSQL | Session logging, tool execution audit, session_context |
| `OPENAI_API_KEY` | sk-proj-... | OpenAI Realtime API access |
| `N8N_BASE_URL` | `https://jayconnorexe.app.n8n.cloud` | Base URL for n8n webhooks |
| `RECALL_API_KEY` | 4f12c2... | Recall.ai Output Media API |
| `SUPABASE_URL` | `https://shaefijojvpougpvdvqi.supabase.co` | bot_state lookup |
| `SUPABASE_ANON_KEY` | eyJhbG... | Supabase anonymous access |
| `CALLBACK_BASE_URL` | `https://voice-agent-relay-production.up.railway.app` | For gated callbacks |

## Key URLs

| Component | URL |
|-----------|-----|
| **Railway Relay Server** | `https://voice-agent-relay-production.up.railway.app` |
| **Railway Health Check** | `https://voice-agent-relay-production.up.railway.app/health` |
| **n8n Send Email** | `https://jayconnorexe.app.n8n.cloud/webhook/execute-gmail` |
| **n8n Query Vector DB** | `https://jayconnorexe.app.n8n.cloud/webhook/query-vector-db` |
| **n8n Get Session Context** | `https://jayconnorexe.app.n8n.cloud/webhook/get-session-context` |
| **Recall.ai Transcripts** | `https://jayconnorexe.app.n8n.cloud/webhook/voice-bot-v3` |
| **Recall.ai Status** | `https://jayconnorexe.app.n8n.cloud/webhook/recall-bot-events` |

## Tool Execution Flow (Updated)

```
Browser Client ──WebSocket──▶ Railway Relay ──WebSocket──▶ OpenAI Realtime API
                                   │
                                   │ (AI decides to call tool)
                                   ▼
                    ┌──────────────────────────────┐
                    │ CACHE-FIRST CHECK            │
                    │ (get_session_context only)   │
                    │                              │
                    │ Memory hit? → Return (~1ms)  │
                    │ DB hit? → Warm cache, return │
                    │ Miss? → Continue to n8n     │
                    └──────────────────────────────┘
                                   │
                                   ▼
                    POST directly to per-tool webhook
                    {
                      "to": "...",
                      "subject": "...",
                      "connection_id": "abc123",
                      "session_id": "bot123_session",
                      "context": { conversation history }
                    }
                                   │
                                   ▼
              ┌────────────────────┼────────────────────┐
              │                    │                    │
              ▼                    ▼                    ▼
        /execute-gmail    /query-vector-db   /get-session-context
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ POST-EXECUTION CACHING       │
                    │                              │
                    │ - Cache completed tool call  │
                    │ - Cache query results        │
                    │ - Cache session context      │
                    └──────────────────────────────┘
                                   │
                                   ▼
                    Response back to Railway
                                   │
                                   ▼
                    OpenAI processes function result
                                   │
                                   ▼
                    TTS audio generated by OpenAI
                                   │
                                   ▼
                    Railway pushes to Recall.ai Output Media API
                                   │
                                   ▼
                    User hears response in Teams meeting
```

## Database Tables

### Railway PostgreSQL (session logging)

```sql
-- tool_executions - Audit trail
CREATE TABLE tool_executions (...);

-- audit_trail - Session events
CREATE TABLE audit_trail (...);

-- session_context - Cross-tool data sharing (cache backup)
CREATE TABLE session_context (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    context_key VARCHAR(100) NOT NULL,
    context_value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(session_id, context_key)
);
```

### Supabase PostgreSQL (voice tools)

- `bot_state` - Recall.ai bot sessions (from launcher)
- `tool_calls` - Gated execution tracking
- `chat_messages` - Conversation history
- `session_summaries` - AI-generated summaries

## SessionCache Class

The relay server includes a `SessionCache` class that provides enterprise-grade caching:

```javascript
// Get or create cache for session
const cache = getSessionCache(sessionId);

// Session context (Memory + PostgreSQL write-through)
await cache.getContext('last_query_results');
await cache.setContext('user_preferences', {...}, 3600);

// Pending tool calls (memory-only with TTL)
await cache.setPendingTool('intent_123', {...});
await cache.getPendingTool('intent_123');
await cache.deletePendingTool('intent_123');
await cache.getAllPendingTools();

// Recent completed tools
await cache.getRecentTools(10);
await cache.addCompletedTool({...});

// Vector query results
await cache.setQueryResults('q_123', {...});
await cache.getQueryResults('q_123');
await cache.getQueryResults(); // Last query results

// Bot state (from Supabase, cached in memory)
await cache.getBotState();

// Full agent context (includes pending tools)
await cache.getAgentContext();

// Cleanup when session ends
clearSessionCache(sessionId);
```

## Relay Server Code Location

```
voice-agent-poc/relay-server/
├── index-enhanced.js  # Main server (~75KB with cache layer)
├── package.json       # Dependencies: ws, pg, dotenv
├── railway.json       # Railway config
├── .env.example       # Environment template
└── DEPLOYMENT.md      # Deployment guide
```

## Bot Name Interrupt Behavior

The system prompt includes dynamic bot_name interrupt handling:

```
INTERRUPT TRIGGER - "{bot_name}":
If the user says "{bot_name}" at any point, IMMEDIATELY:
1. Stop whatever you're saying mid-sentence
2. Briefly apologize: "Sorry about that."
3. Say: "Yes?"
4. Wait for the user's next instruction
```

## Troubleshooting

### Railway not responding
```bash
railway logs --tail 100  # Check for errors
railway redeploy         # Force redeploy
```

### Tool calls not working
1. Check Railway logs for per-tool webhook calls
2. Verify each webhook URL is active in n8n
3. Test individual webhooks:
   ```bash
   curl -X POST https://jayconnorexe.app.n8n.cloud/webhook/execute-gmail \
     -H "Content-Type: application/json" \
     -d '{"to":"test@example.com","subject":"Test","body":"Hello"}'
   ```

### Cache issues
1. Check Railway logs for cache hit/miss messages
2. Verify DATABASE_URL is correct for PostgreSQL
3. Check cache TTLs haven't expired (see CACHE_TTL values)
4. In-memory cache clears on server restart - DB should persist

### Recall.ai not receiving audio
1. Check RECALL_API_KEY is set in Railway
2. Check bot_state table in Supabase for active bot_id
3. Verify Recall.ai bot is in meeting (status: in_call_recording)
