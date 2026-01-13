# Teams Voice Bot - Orchestrator Architecture

**Version:** 2.0 | **Status:** Design Phase
**Current Workflow:** `gjYSN6xNjLw8qsA1`

---

## Executive Summary

Transform the current sequential workflow into a **parallel orchestrator architecture** with specialized sub-workflows. The orchestrator classifies intents quickly (code-based, no LLM for routing), logs all decisions, and delegates to sub-workflows that can execute tools in parallel with TTS responses.

---

## Patterns Applied

Based on research from multi-agent n8n workflows:

| Pattern | Source | Application |
|---------|--------|-------------|
| Centralized Orchestrator | n8n_RAG_Workflow | Main workflow routes to specialists |
| Parallel Specialist Agents | travel-planner-agentic | Sub-workflows execute simultaneously |
| Task Decomposition | travel-planner-agentic | Break complex requests into tool calls |
| Execution Logging | travel-planner-agentic | Log all decisions and outcomes |
| Memory Store | n8n_RAG_Workflow | PostgreSQL for conversation context |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           MAIN ORCHESTRATOR WORKFLOW                            │
│                              (gjYSN6xNjLw8qsA1)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────────┐                │
│  │ Webhook │───>│ Filter  │───>│ Extract  │───>│ Load State  │                │
│  │ Trigger │    │ Final   │    │ Data     │    │ (DataTable) │                │
│  └─────────┘    └─────────┘    └──────────┘    └──────┬──────┘                │
│                                                        │                       │
│                                                        ▼                       │
│                                          ┌─────────────────────────┐           │
│                                          │    FAST CLASSIFIER      │           │
│                                          │    (Code Node - No LLM) │           │
│                                          │  • Bot address detection│           │
│                                          │  • Intent patterns      │           │
│                                          │  • End-of-thought check │           │
│                                          └───────────┬─────────────┘           │
│                                                      │                         │
│                                                      ▼                         │
│                                          ┌─────────────────────────┐           │
│                                          │    LOGGING AGENT        │           │
│                                          │  • Intent classified    │           │
│                                          │  • Chat history         │           │
│                                          │  • Routing decision     │           │
│                                          │  • Timestamp            │           │
│                                          └───────────┬─────────────┘           │
│                                                      │                         │
│                                                      ▼                         │
│                                          ┌─────────────────────────┐           │
│                                          │    ORCHESTRATOR ROUTER  │           │
│                                          │    (Switch Node)        │           │
│                                          └───────────┬─────────────┘           │
│                                                      │                         │
│          ┌────────────┬────────────┬────────────┬───┴────┬──────────┐         │
│          ▼            ▼            ▼            ▼        ▼          ▼         │
│     ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌───────┐  ┌──────┐  │
│     │ SILENT  │  │GREETING │  │SPELLING │  │ TOOL    │  │ CHAT  │  │ERROR │  │
│     │ IGNORE  │  │ DIRECT  │  │ MODE    │  │ CALL    │  │ AGENT │  │HANDLE│  │
│     └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └───┬───┘  └──┬───┘  │
│          │            │            │            │           │         │       │
│          │            │            │            ▼           │         │       │
│          │            │            │    ┌──────────────┐    │         │       │
│          │            │            │    │ PARALLEL     │    │         │       │
│          │            │            │    │ EXECUTION    │    │         │       │
│          │            │            │    ├──────────────┤    │         │       │
│          │            │            │    │ ┌──────────┐ │    │         │       │
│          │            │            │    │ │IMMEDIATE │ │    │         │       │
│          │            │            │    │ │TTS ACKGE │ │    │         │       │
│          │            │            │    │ └────┬─────┘ │    │         │       │
│          │            │            │    │      │       │    │         │       │
│          │            │            │    │ ┌────▼─────┐ │    │         │       │
│          │            │            │    │ │SUB-WKFLW │ │    │         │       │
│          │            │            │    │ │(Gmail)   │ │    │         │       │
│          │            │            │    │ └────┬─────┘ │    │         │       │
│          │            │            │    └──────┼───────┘    │         │       │
│          │            │            │           │            │         │       │
│          ▼            ▼            ▼           ▼            ▼         ▼       │
│     ┌───────────────────────────────────────────────────────────────────────┐ │
│     │                    RESULTS AGGREGATOR                                  │ │
│     │               (Merge Node - All Paths)                                 │ │
│     └───────────────────────────────────┬───────────────────────────────────┘ │
│                                         │                                      │
│                                         ▼                                      │
│     ┌───────────────────────────────────────────────────────────────────────┐ │
│     │                    TTS + RECALL OUTPUT                                 │ │
│     │         (OpenAI TTS → Base64 → Recall.ai Audio)                       │ │
│     └───────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

                                    ║
                                    ║ Execute "Call Workflow" Node
                                    ║
                                    ▼

┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SUB-WORKFLOW: GMAIL AGENT                             │
│                           (New Workflow - Template)                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │ Trigger │───>│ AI Agent    │───>│ Gmail Tool  │───>│ Format      │         │
│  │ (Input) │    │ (Composer)  │    │ (Send)      │    │ Response    │         │
│  └─────────┘    └─────────────┘    └─────────────┘    └──────┬──────┘         │
│                                                               │                 │
│                                                               ▼                 │
│                                                        ┌─────────────┐         │
│                                                        │ Return to   │         │
│                                                        │ Orchestrator│         │
│                                                        └─────────────┘         │
│                                                                                 │
│  Inputs: { transcript, email_address, context, bot_id }                        │
│  Outputs: { success, response_text, tool_result }                              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Fast Classifier (Code Node)

**Purpose:** Ultra-fast intent detection without LLM overhead

```javascript
// Fast Classifier Logic
const transcript = $json.transcript.toLowerCase();
const botNames = ['bot', 'assistant', 'ai', 'hey bot', 'hello bot'];
const emailPatterns = /send\s*(an\s*)?email|email\s*to|compose\s*email/i;
const questionPatterns = /\?$|what|how|when|where|why|can you|could you/i;
const spellingKeywords = ['alpha', 'bravo', 'at sign', 'dot', 'done', 'finished'];

// State-aware routing
const currentState = $('Load Bot State').item.json.state || 'IDLE';

// Decision tree (no LLM needed)
let route = 'silent_ignore';
let intent = 'irrelevant';

if (currentState === 'SPELLING_EMAIL') {
  route = 'spelling_mode';
  intent = 'spelling_continue';
} else if (currentState === 'CONFIRMING_EMAIL') {
  route = 'spelling_mode';
  intent = 'confirmation';
} else if (botNames.some(name => transcript.includes(name))) {
  if (emailPatterns.test(transcript)) {
    route = 'tool_call';
    intent = 'email_request';
  } else if (questionPatterns.test(transcript)) {
    route = 'chat_agent';
    intent = 'question';
  } else {
    route = 'greeting_direct';
    intent = 'greeting';
  }
}

// End-of-thought detection
const isCompleteThought = /[.!?]$/.test(transcript.trim()) ||
                          /\b(please|thanks|thank you)\b/i.test(transcript);

return {
  route,
  intent,
  isCompleteThought,
  shouldRespond: route !== 'silent_ignore',
  timestamp: new Date().toISOString()
};
```

**Route Outputs:**
| Route | Description | Next Step |
|-------|-------------|-----------|
| `silent_ignore` | Background chatter | Respond OK only |
| `greeting_direct` | Simple greeting | Static TTS response |
| `spelling_mode` | Email character input | Spelling handler |
| `tool_call` | Needs tool execution | Parallel: TTS ack + Sub-workflow |
| `chat_agent` | Conversational question | AI Agent |
| `error_handle` | Unrecoverable state | Error recovery |

---

### 2. Logging Agent (Postgres Insert)

**Purpose:** Log ALL orchestrator decisions for analytics and debugging

**Table Schema:**
```sql
CREATE TABLE orchestrator_logs (
    id SERIAL PRIMARY KEY,
    bot_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255),
    timestamp TIMESTAMPTZ DEFAULT NOW(),

    -- Classification
    transcript TEXT,
    intent VARCHAR(50),
    route VARCHAR(50),
    is_complete_thought BOOLEAN,
    should_respond BOOLEAN,

    -- State Context
    previous_state VARCHAR(50),
    new_state VARCHAR(50),

    -- Tool Calls (if any)
    tool_called VARCHAR(100),
    tool_input JSONB,
    tool_output JSONB,
    tool_duration_ms INTEGER,

    -- Response
    response_text TEXT,
    tts_duration_ms INTEGER,

    -- Metadata
    processing_time_ms INTEGER,
    error_message TEXT
);

CREATE INDEX idx_logs_bot_id ON orchestrator_logs(bot_id);
CREATE INDEX idx_logs_session ON orchestrator_logs(session_id);
CREATE INDEX idx_logs_intent ON orchestrator_logs(intent);
CREATE INDEX idx_logs_timestamp ON orchestrator_logs(timestamp);
```

**Log Entry Structure:**
```javascript
{
  bot_id: $json.bot_id,
  session_id: $json.session_id,
  transcript: $json.transcript,
  intent: $('Fast Classifier').item.json.intent,
  route: $('Fast Classifier').item.json.route,
  is_complete_thought: $('Fast Classifier').item.json.isCompleteThought,
  should_respond: $('Fast Classifier').item.json.shouldRespond,
  previous_state: $('Load Bot State').item.json.state,
  new_state: null, // Set after state update
  processing_time_ms: Date.now() - $json.received_at
}
```

---

### 3. Parallel Execution Pattern

**Key Innovation:** TTS acknowledgment runs PARALLEL to tool execution

```
                          ┌───────────────────────────┐
                          │ Tool Call Route Detected  │
                          └─────────────┬─────────────┘
                                        │
                          ┌─────────────┴─────────────┐
                          │                           │
                          ▼                           ▼
               ┌─────────────────┐         ┌─────────────────┐
               │ IMMEDIATE TTS   │         │ SUB-WORKFLOW    │
               │ "Working on it" │         │ (Gmail Agent)   │
               └────────┬────────┘         └────────┬────────┘
                        │                           │
                        ▼                           │
               ┌─────────────────┐                  │
               │ Send to Recall  │                  │
               │ (First audio)   │                  │
               └────────┬────────┘                  │
                        │                           │
                        │                           ▼
                        │                  ┌─────────────────┐
                        │                  │ Execute Tool    │
                        │                  │ (may take 2-5s) │
                        │                  └────────┬────────┘
                        │                           │
                        ▼                           ▼
               ┌─────────────────────────────────────────────┐
               │              WAIT FOR BOTH                  │
               │           (Merge Node - Wait All)           │
               └─────────────────────┬───────────────────────┘
                                     │
                                     ▼
               ┌─────────────────────────────────────────────┐
               │          RESULT TTS + SEND                  │
               │    "Done! I've sent the email to..."        │
               └─────────────────────────────────────────────┘
```

**Implementation:**
1. Switch node routes to "tool_call" output
2. First branch: Set static acknowledgment → TTS → Recall (fast path)
3. Second branch: Execute Sub-workflow → Wait for result
4. Merge node waits for BOTH to complete
5. Final TTS with tool result → Recall

---

### 4. Sub-Workflow Template: Gmail Agent

**Workflow Name:** `Gmail Agent Sub-Workflow`
**Trigger:** Execute Workflow Trigger (receives data from main workflow)

**Input Schema:**
```javascript
{
  transcript: "Send an email to john@example.com about the meeting",
  email_address: "john@example.com", // If already spelled/confirmed
  context: {
    conversation_history: [...], // Last 10 messages
    meeting_topic: "Q1 Review",
    participants: ["User", "Bot"]
  },
  bot_id: "abc123",
  session_id: "session_456"
}
```

**Nodes:**

| Node | Type | Purpose |
|------|------|---------|
| Execute Workflow Trigger | Trigger | Receive input from orchestrator |
| Compose Email | AI Agent | Draft subject/body from context |
| Gmail Send | Gmail Tool | Send the email |
| Format Response | Code | Create response text |
| Return Result | Set | Output for orchestrator |

**AI Agent System Prompt:**
```
You are an email composition assistant for a voice bot.

Given the conversation context and recipient, compose a professional email.

INPUT:
- Transcript: The user's request
- Email Address: The confirmed recipient
- Context: Recent conversation history

OUTPUT JSON:
{
  "subject": "Brief, clear subject line",
  "body": "Professional email body. 2-3 paragraphs max.",
  "summary": "One sentence for TTS confirmation"
}

Keep the email concise as it was dictated in a voice meeting.
```

**Output Schema:**
```javascript
{
  success: true,
  response_text: "I've sent the email to john@example.com about the Q1 review.",
  tool_result: {
    tool: "gmail",
    action: "send",
    recipient: "john@example.com",
    subject: "Q1 Review Discussion",
    status: "sent"
  }
}
```

---

### 5. Orchestrator Router (Switch Node)

**Configuration:**

```javascript
// Switch Node - 6 Outputs
{
  rules: [
    {
      output: 0, // silent_ignore
      condition: "={{ $json.route === 'silent_ignore' }}"
    },
    {
      output: 1, // greeting_direct
      condition: "={{ $json.route === 'greeting_direct' }}"
    },
    {
      output: 2, // spelling_mode
      condition: "={{ $json.route === 'spelling_mode' }}"
    },
    {
      output: 3, // tool_call
      condition: "={{ $json.route === 'tool_call' }}"
    },
    {
      output: 4, // chat_agent
      condition: "={{ $json.route === 'chat_agent' }}"
    },
    {
      output: 5, // error_handle (fallback)
      condition: "={{ true }}"
    }
  ]
}
```

---

### 6. State Management

**DataTable:** `bot_conversation_state` (existing: `kYJQ3EWJf9ImHQfK`)

**Enhanced Fields:**
```javascript
{
  bot_id: "PRIMARY KEY",
  state: "IDLE | LISTENING | SPELLING_EMAIL | CONFIRMING_EMAIL | TOOL_EXECUTING",
  session_id: "UUID for chat session",
  email_chars: "accumulated email characters",
  pending_email: "{ to, subject, body }",
  message_count: "messages in session",
  last_intent: "last classified intent",
  last_route: "last routing decision",
  context_summary: "AI-generated context summary",
  last_updated: "timestamp"
}
```

**State Transitions:**
```
IDLE ─────[bot addressed]─────> LISTENING
  │                                 │
  │                            [email intent]
  │                                 │
  │                                 ▼
  │                          SPELLING_EMAIL
  │                                 │
  │                            [done keyword]
  │                                 │
  │                                 ▼
  │                         CONFIRMING_EMAIL
  │                              ╱    ╲
  │                         [yes]      [no]
  │                           │          │
  │                           ▼          ▼
  │                    TOOL_EXECUTING   SPELLING_EMAIL
  │                           │
  │                      [complete]
  │                           │
  ▼                           ▼
IDLE <────────────────────────┘
```

---

## Credential References

| Service | Credential ID | Purpose |
|---------|---------------|---------|
| OpenAI API | `6BIzzQu5jAD5jKlH` | TTS audio generation |
| Recall.ai | `XksCwcWinBg0uQBa` | Audio output to Teams |
| OpenRouter | `OPPAOWUbmkR2frSd` | AI Agent chat model |
| Gmail OAuth | `Wagsju9B8ofYq2Sl` | Email sending |
| Postgres | `NEW - TO CREATE` | Logging database |

---

## Implementation Phases

### Phase 1: Database Setup
- [ ] Create Postgres credentials in n8n
- [ ] Create `orchestrator_logs` table
- [ ] Test connection

### Phase 2: Logging Agent
- [ ] Add Postgres INSERT node after Fast Classifier
- [ ] Test log entries

### Phase 3: Gmail Sub-Workflow
- [ ] Create new workflow "Gmail Agent Sub-Workflow"
- [ ] Add Execute Workflow Trigger
- [ ] Add AI Agent for email composition
- [ ] Add Gmail tool
- [ ] Add output formatting
- [ ] Test standalone

### Phase 4: Parallel Execution
- [ ] Add branch after tool_call detection
- [ ] Implement immediate TTS acknowledgment path
- [ ] Add Execute Workflow node for Gmail sub-workflow
- [ ] Add Merge node (wait for both)
- [ ] Test parallel timing

### Phase 5: Orchestrator Refactor
- [ ] Replace current state router with new Switch node
- [ ] Update Fast Classifier code
- [ ] Connect all 6 output paths
- [ ] Update state management

### Phase 6: Testing
- [ ] Test silent ignore (background chatter)
- [ ] Test greeting flow
- [ ] Test email request → spelling → confirm → send
- [ ] Test parallel TTS timing
- [ ] Test error recovery
- [ ] Verify all logs captured

---

## Metrics to Track

| Metric | Source | Target |
|--------|--------|--------|
| Classification latency | Fast Classifier | < 50ms |
| TTS acknowledgment time | First audio send | < 500ms |
| Tool execution time | Sub-workflow | Logged |
| End-to-end response | Webhook → Audio | < 2s |
| Silent ignore rate | Logs | 60-80% |
| Intent accuracy | Manual review | > 95% |

---

## Future Sub-Workflows

| Agent | Purpose | Priority |
|-------|---------|----------|
| Gmail Agent | Send emails | P1 (First) |
| Calendar Agent | Schedule meetings | P2 |
| Search Agent | Web/knowledge search | P2 |
| Summary Agent | Meeting summarization | P3 |
| Task Agent | Create tasks/reminders | P3 |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Sub-workflow timeout | 30s timeout, fallback response |
| Parallel branch failure | Each branch has error handler |
| State corruption | Atomic updates, rollback on error |
| Log table growth | Daily partition, 30-day retention |
| Classification errors | Fallback to chat_agent if uncertain |
