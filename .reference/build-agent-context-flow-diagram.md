# Build Agent Context - Enhanced Data Flow

## Context Sources & Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                  PROCESS TRANSCRIPT NODE                        │
│              (Fast Classifier Output)                           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │   transcript.route                   │ ─────► Route code: PROCESS/WAIT/LISTEN/SILENT
        │   transcript.intent                  │ ─────► Classified intent: email_request/greeting/etc
        │   transcript.is_addressing_bot       │ ─────► Bot name detection flag
        │   transcript.is_first_message        │ ─────► Fresh session vs continuation
        │   transcript.response_timing         │ ─────► Urgency level & completeness
        │   transcript.session_state           │ ─────► From staticData persistence
        │      ├─ last_orchestrator_cues       │        What bot said in previous chunks
        │      ├─ pending_actions              │        Tools in progress from earlier chunks
        │      ├─ processing_count             │        Total chunks processed this session
        │      └─ session_start_time           │        When session began
        └──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LOAD BOT STATE NODE                            │
│              (Database History Query)                           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │   historyRows (last 4 interactions)  │
        │      ├─ transcript_exact             │ ─────► What users said
        │      ├─ agent_output_raw             │ ─────► What bot replied
        │      ├─ tool_calls                   │ ─────► Tools used
        │      └─ logged_at                    │ ─────► Timestamps
        └──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              BUILD AGENT CONTEXT NODE                           │
│          (Combines All Sources Into System Prompt)              │
└─────────────────────────────────────────────────────────────────┘
                       │
                       ▼
        ╔══════════════════════════════════════╗
        ║       ENHANCED SYSTEM PROMPT         ║
        ╚══════════════════════════════════════╝
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  SECTION 1  │ │  SECTION 2  │ │  SECTION 3  │ │  SECTION 4  │
│   Intent    │ │  Streaming  │ │   Session   │ │Anti-Repeat  │
│   Markers   │ │   Context   │ │    State    │ │    Rules    │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

---

## Section 1: Intent Markers (NEW)

**Source:** `transcript` from Process Transcript node

```javascript
const intentMarkersSection = `
## Understanding Intent Classification

Route Code: ${transcript.route}
Intent: ${transcript.intent}
Flags explained:
  - NEAR_END (1)
  - REQUEST (2)
  - INCOMPLETE (4)
  - TOOL_ACTIVE (8)
  - GREETING (16)
  - BOT_ADDRESSED (32)
  - FIRST_MSG (64)

Current: is_first_message=${isFirstMessage}, is_addressing_bot=${is_addressing_bot}
`;
```

**Purpose:** Agent understands classification already happened upstream

---

## Section 2: Streaming Context (NEW)

**Source:** `transcript.session_state.processing_count` + `transcript.is_first_message`

```javascript
const streamingContextSection = `
## Chunked Transcript Streaming (CRITICAL CONCEPT)

How Recall.ai sends transcripts:
  - Chunks arrive across SEPARATE EXECUTIONS
  - Each chunk = separate webhook call
  - Previous chunks processed in EARLIER WORKFLOW RUNS

Current Execution:
  - is_first_message: ${isFirstMessage ? 'TRUE' : 'FALSE'}
  - Processing count: ${processingCount} chunks
  - ${isFirstMessage ?
      'NEW SESSION - greeting appropriate' :
      'CHUNK #' + (processingCount + 1) + ' - user is CONTINUING'}

What this means:
  ${!isFirstMessage ?
    '- User CONTINUING conversation from ' + processingCount + ' chunks ago
     - Previous context exists (see Session State below)
     - Do NOT greet as if first interaction
     - Build on what was said in previous chunks' :
    '- Genuinely first message
     - Session just started
     - Greetings appropriate if user greeted'}
`;
```

**Purpose:** Agent understands it's processing chunk #X of fragmented stream

---

## Section 3: Session State (NEW)

**Source:** `transcript.session_state` from staticData persistence

```javascript
const sessionStateSection = `
## Session State (From Previous Chunks)

What you said in previous chunks:
  ${lastOrchestratorCues || '(Nothing yet - first chunk you're responding to)'}

Pending actions:
  ${pendingActions.length > 0 ? pendingActions.join('\n  - ') : '(No pending actions)'}

Session metrics:
  - Total chunks processed: ${processingCount}
  - Session start: ${sessionState.session_start_time}

Continuity instructions:
  ${lastOrchestratorCues && !isFirstMessage ?
    '- You previously said: "' + lastOrchestratorCues + '"
     - Build naturally on that response
     - Don't repeat what you already said
     - User is responding to YOUR previous statement' :
    '- No previous bot responses yet
     - This is your first chance to speak'}
`;
```

**Purpose:** Agent maintains continuity across separate executions

---

## Section 4: Anti-Repeat Rules (EXISTING - Enhanced)

**Source:** `historyRows` from database + new session state data

```javascript
// Existing anti-repeat logic ENHANCED with session state
const uniqueResponses = [...new Set(recentResponses)];

const antiRepeatSection = `
## CRITICAL ANTI-REPEAT RULES

YOUR PREVIOUS RESPONSES (DO NOT SAY THESE AGAIN):
  ${uniqueResponses.map((r, i) => `${i + 1}. "${r}"`).join('\n')}

${responseGuidance}  // Email address logic, continuation logic
`;
```

**Purpose:** Prevents verbatim response repetition

---

## Data Flow Summary

### Execution #1 (is_first_message=true)
```
User: "Hey bot, send an email"
  ↓
[Classifier] → route=PROCESS, intent=email_request, is_first_message=true
  ↓
[Session State] → processing_count=0, last_orchestrator_cues=""
  ↓
[System Prompt] → "This is a NEW SESSION START. Greeting appropriate."
  ↓
Agent: "Hi! I can help with that. What's the recipient's email address?"
  ↓
[Static Data] → Stores last_orchestrator_cues="Hi! I can help with that..."
```

### Execution #2 (is_first_message=false)
```
User: "Send it to john@example.com"
  ↓
[Classifier] → route=PROCESS, intent=email_address, is_first_message=false
  ↓
[Session State] → processing_count=1, last_orchestrator_cues="Hi! I can help..."
  ↓
[System Prompt] → "CHUNK #2 of ONGOING conversation. You previously said: 'Hi! I can help...'"
  ↓
Agent: "Got it. Sending the email to john@example.com now."
  ↓
[Static Data] → Updates last_orchestrator_cues="Got it. Sending the email..."
```

### Execution #3 (is_first_message=false)
```
User: "Thanks"
  ↓
[Classifier] → route=LISTEN, intent=acknowledgment, is_first_message=false
  ↓
[Session State] → processing_count=2, last_orchestrator_cues="Got it. Sending..."
  ↓
[System Prompt] → "CHUNK #3. You previously said: 'Got it. Sending...' NO greeting!"
  ↓
Agent: "You're welcome!"
  ↓
[Static Data] → Updates last_orchestrator_cues="You're welcome!"
```

---

## Key Behavioral Changes

| Scenario | Before Enhancement | After Enhancement |
|----------|-------------------|-------------------|
| **Chunk #2 arrives** | Agent might greet again | Agent sees `is_first_message=false`, no greeting |
| **User responds to bot's question** | No context of what bot asked | Agent sees `last_orchestrator_cues` with its previous question |
| **Pending tool in progress** | Agent might ask again | Agent sees `pending_actions`, waits for completion |
| **Session resets (5+ min)** | No clear indication | `processing_count` resets to 0, greeting appropriate |

---

## Technical Implementation

### staticData Persistence (Existing)
```javascript
// In Process Transcript node (classifier)
const staticData = $getWorkflowStaticData('global');
if (!staticData.botTranscripts[bot_id]) {
  staticData.botTranscripts[bot_id] = {
    lastProcessedTranscript: '',
    lastProcessedTime: 0,
    processingCount: 0,
    sessionStartTime: now,
    lastOrchestratorCues: '',  // ← Stored here
    pendingActions: []         // ← Stored here
  };
}
```

### Build Agent Context Extraction (NEW)
```javascript
// In Build Agent Context node
const sessionState = transcript.session_state || {};
const isFirstMessage = transcript.is_first_message || false;
const processingCount = sessionState.processing_count || 0;
const lastOrchestratorCues = sessionState.last_orchestrator_cues || '';
const pendingActions = sessionState.pending_actions || [];
```

### System Prompt Injection (NEW)
```javascript
const systemPrompt = `
You are a voice assistant...

${intentMarkersSection}      // ← NEW: Classifier explanation
${streamingContextSection}   // ← NEW: Chunking explanation
${sessionStateSection}       // ← NEW: Previous chunk continuity
${antiRepeatSection}         // ← ENHANCED: Existing + new data

...
`;
```

---

## Validation Checklist

Before deploying:
- [x] All 4 context sections included in system prompt
- [x] `session_state` data extracted from classifier output
- [x] `is_first_message` logic implemented
- [x] `last_orchestrator_cues` displayed in prompt
- [x] `pending_actions` array included
- [x] Existing anti-repeat logic preserved
- [x] Workflow validates (0 critical errors)
- [x] Node updated via `mcp__n8n-mcp__n8n_update_partial_workflow`

Testing needed:
- [ ] Fresh session (chunk #1) → verify greeting
- [ ] Mid-conversation (chunk #2-5) → verify NO greeting
- [ ] Continuity check → verify agent references `last_orchestrator_cues`
- [ ] Pending actions → verify agent waits for completion
