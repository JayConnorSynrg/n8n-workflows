# Teams Voice Bot v3.0 - OpenAI Realtime API Restructuring Guide

**Workflow ID:** `d3CxEaYk5mkC8sLo`
**Purpose:** Complete breakdown for restructuring to OpenAI Realtime API integration
**Date:** 2026-01-10

---

## Part 1: Current Architecture Analysis

### Quick Facts
- **Nodes:** 25 total (9 code, 4 LangChain, 5 PostgreSQL, 2 control flow)
- **Connections:** 21
- **Entry:** POST `/voice-bot-v3` (Webhook v2.1)
- **Agent:** OpenRouter (GPT-4o-mini) via LangChain Agent v3
- **Status:** Active, fully operational

### Architecture Pattern: Multi-Stage Pipeline

```
Webhook → Parse → Pre-Router (heuristic) → Route Switch
    ├─ SILENT → Log & Exit
    ├─ BUFFER → Log & Exit
    └─ FULL_PROCESS → Intent Merger → Agent → TTS Pipeline → Recall.ai
```

---

## Part 2: Critical Code Nodes (Ranked by Complexity)

### 1. Ultra-Fast Pre-Router (11,976 chars / 354 lines)
**Purpose:** Sub-10ms heuristic classification before agent processing

**Key Outputs:**
- `pre_route`: SILENT | BUFFER | WAIT_LOG | FULL_PROCESS
- `heuristics`: Object with signals (is_silence, is_greeting, is_interruption, etc.)
- `intent_markers`: Detected intent patterns
- `confidence`: Classification confidence scores

**Decision Factors:**
- Silence detection (audio analysis)
- Partial transcript detection
- Greeting pattern matching
- Bot name mentions
- Interruption signals

**Critical Note:** v4.6 routes partial_data to SILENT (not BUFFER) to reduce execution overhead from ~10 per utterance to 1.

### 2. Process Transcript (10,991 chars / 297 lines)
**Purpose:** Parse webhook data and extract voice information

**Key Logic:**
```javascript
// Detects pre-processed vs raw webhook data
const isPreProcessed = item.pre_route !== undefined && item.transcript !== undefined;

if (isPreProcessed) {
  // Use pre-processed data from Pre-Route Switch
  transcript = item.transcript;
  speaker = item.speaker;
  bot_id = item.bot_id;
} else {
  // Parse raw webhook structure: body.data.data.words[]
  const words = inner.words || [];
}
```

**Mode:** runOnceForEachItem (processes each input item separately)

### 3. Intent Summary Merger (6,503 chars / 214 lines)
**Purpose:** Multi-signal weighted routing decision

**Weighting Algorithm:**
- History signals (from DB): 40%
- Intent signals (from Pre-Router): 40%
- Interrupt signals: 20%

**Inputs:**
- `fastSignals`: Pre-Router classification
- `dbResults`: Fast Intent Query results (historical context)

**Output:** Final route decision with confidence scores

### 4. Build Agent Context (3,278 chars / 96 lines)
**Purpose:** Construct agent input and system prompt

**Critical Issue Fixed (v8):**
```javascript
// Load Bot State is a Postgres query - doesn't pass input through
// Must reference Pre-Route Switch data directly

let preRouterData = {};
try {
  // Use: $('Pre-Route Switch').first().json
  // NOT: $input (which is Load Bot State result)
  preRouterData = $('Pre-Route Switch').first().json;
} catch (e) {
  console.error('Pre-Route Switch reference failed');
}
```

**Output Structure:**
```javascript
{
  chat_input: string,           // User query for agent
  system_prompt: string,        // Instructions for agent
  bot_state: object,            // From Load Bot State
  transcript_data: object,      // From Pre-Router
  context_metadata: object      // Additional context
}
```

### 5. Build Immutable Log (3,630 chars / 106 lines)
**Purpose:** Create TTS logging record with all metadata

**References:**
- `Orchestrator Agent`: Agent output
- `Build Agent Context`: Context metadata
- `Parallel TTS & Send`: TTS processing info

**Logged Data:**
- Route decision and confidence
- Agent iterations and tool usage
- TTS chunk information
- Timing metadata

### 6. Split into Sentences (2,644 chars / 77 lines)
**Purpose:** Chunk agent response for progressive TTS delivery

**Node References:**
- `Build Agent Context` (for bot_id)
- `Pre-Route Switch` (fallback for bot_id)

**Process:**
```
Agent Response String → Sentence Split → Array of Sentences
                                        → Each with metadata (bot_id, voice, etc.)
```

### 7. Parallel TTS & Send (4,151 chars / 148 lines)
**Purpose:** External API calls to OpenAI TTS + sequential Recall.ai delivery

**Key Features:**
- Parallel TTS generation
- Sequential delivery
- Voice selection (default: 'alloy')
- Bot status check
- **Security Issue:** OpenAI API key embedded in code

**API Calls:**
```javascript
const OPENAI_API_KEY = 'sk-proj-...'; // EXPOSED

// Makes calls to OpenAI TTS API
// Then sends to Recall.ai for delivery
```

### 8-11. Quick Response Handlers
- **Quick Acknowledge** (413 chars): "I'm listening...", "Go ahead..."
- **Quick Reply** (794 chars): Template greetings
- **Wait Log Only** (423 chars): Logging for partial transcripts
- **Interrupt Handler** (2,196 chars): Interrupt analytics and responses

---

## Part 3: LangChain Agent Configuration

### Orchestrator Agent (v3)
```javascript
{
  type: "@n8n/n8n-nodes-langchain.agent",
  typeVersion: 3,
  parameters: {
    promptType: "define",
    text: "={{ $json.chat_input }}",
    options: {
      systemMessage: "={{ $json.system_prompt }}",
      maxIterations: 5
    }
  }
}
```

### Connected Model: OpenRouter Chat Model (v1)
```javascript
{
  type: "@n8n/n8n-nodes-langchain.lmChatOpenRouter",
  model: "openai/gpt-4o-mini"
}
```

### Available Tools
1. **Gmail Agent Tool** (toolWorkflow v2.2)
   - Searches, reads, sends Gmail emails
   - Manages labels

2. **Think Tool** (toolThink v1.1)
   - Internal reasoning
   - Used for complex decisions

---

## Part 4: Database Schema Integration

### PostgreSQL Operations (v2.6)

| Node | Purpose | Trigger |
|------|---------|---------|
| Load Bot State | Retrieve stored bot context | FULL_PROCESS route |
| Log Silent Transcript | Audit silent inputs | SILENT route |
| Log Wait Transcript | Audit buffered inputs | BUFFER/WAIT_LOG routes |
| Fast Intent Query | Historical context lookup | Called by Intent Summary Merger |
| Log Interrupt | Interrupt analytics | Interrupt Handler |

**Expected Schema Structure:**
- `bot_state` table: bot_id, state_json, updated_at
- `transcripts` table: transcript, speaker, bot_id, timestamp
- `intents` table: intent_name, confidence, bot_id
- `interrupts` table: interrupt_type, bot_id, timestamp

---

## Part 5: Data Flow Specifics

### Optimal Path (FULL_PROCESS)
```
1. Webhook (POST) → 100-200 bytes
2. Process Transcript → Extract transcript, speaker, bot_id
3. Ultra-Fast Pre-Router → Classify as FULL_PROCESS
4. Pre-Route Switch → Route to FULL_PROCESS branch
5. Fast Intent Query → Fetch historical intent data (1-5KB)
6. Intent Summary Merger → Weighted routing decision
7. Load Bot State → Fetch bot context (variable)
8. Build Agent Context → Prepare prompt (3-5KB)
9. Orchestrator Agent → LLM inference (variable)
10. Check Agent Output → Validate response
11. Split into Sentences → Chunk for TTS (1KB per sentence)
12. Parallel TTS & Send → External API calls (per sentence)
```

### Silent/Buffer Path
```
1. Webhook → Parse
2. Process Transcript → Extract
3. Ultra-Fast Pre-Router → Classify as SILENT/BUFFER
4. Pre-Route Switch → Route to SILENT/BUFFER branch
5. Log Silent/Wait Transcript → Database write
6. End (skip agent entirely)
```

---

## Part 6: Key Implementation Patterns

### Node Reference Pattern
```javascript
// Get data from previous node
const data = $('Node Name').first().json;

// Get all items from previous node
const items = $('Node Name').all();

// Used in:
// - Build Agent Context
// - Build Immutable Log
// - Split into Sentences
```

### Conditional Output Pattern
```javascript
// Objects conditionally passed based on routing decisions
// Smart fallback chains:
// Try node 1 → Fallback to node 2 → Fallback to node 3

// Example in Split into Sentences:
const botId = input.bot_id ||
              contextData?.bot_id ||
              'unknown';
```

### Weighted Scoring Pattern
```javascript
// Intent Summary Merger algorithm
const score = (history * 0.4) + (intent * 0.4) + (interrupt * 0.2);

// Used for intelligent routing vs. quick responses
```

---

## Part 7: Restructuring Requirements for OpenAI Realtime API

### Current Architecture → Realtime Challenges

#### 1. **Webhook-Based Input**
- **Current:** Discrete POST requests, full transcript in body
- **Challenge:** Realtime API uses WebSocket with streaming partial transcripts
- **Solution:** Replace Webhook with WebSocket listener node

#### 2. **Batch Processing Nodes**
- **Current:** Process Transcript uses `runOnceForEachItem`
- **Challenge:** Can't batch items in real-time streaming
- **Solution:** Convert to streaming/incremental processors

#### 3. **Complete Transcript Requirement**
- **Current:** Ultra-Fast Pre-Router expects full transcript for classification
- **Challenge:** Realtime API provides partial transcripts incrementally
- **Solution:** Implement partial transcript classification with confidence thresholds

#### 4. **Sequential TTS Pipeline**
- **Current:** Wait for agent response → Chunk → Send TTS
- **Challenge:** Need bi-directional streaming (agent talking while user might interrupt)
- **Solution:** Implement buffer management + interruption cancellation

#### 5. **Agent Max Iterations**
- **Current:** Fixed at 5 iterations max
- **Challenge:** Realtime API expects faster response times
- **Solution:** Reduce max iterations to 2-3 for latency control

#### 6. **Tool Output Handling**
- **Current:** Tools return complete results
- **Challenge:** Need to stream tool outputs
- **Solution:** Implement tool output streaming to client

#### 7. **Interruption Handling**
- **Current:** Post-conversation analysis
- **Challenge:** Need real-time interruption during agent execution
- **Solution:** Implement cancellation token propagation

---

## Part 8: Critical Configuration Details

### Webhook Configuration
```
Path: /voice-bot-v3
Method: POST
typeVersion: 2.1
```

### Expected Input Schema
```json
{
  "body": {
    "data": {
      "data": {
        "words": [
          {"text": "...", "startTime": 0, "endTime": 100}
        ],
        "participant": {"name": "user_name"}
      }
    }
  }
}
```

### Credentials Required
1. `openRouterApi` - For LLM calls
2. `postgres` - For all database operations

### Execution Settings
- **Execution Order:** v1
- **Caller Policy:** workflowsFromSameOwner
- **Available in MCP:** False

---

## Part 9: Known Issues & Fixes

### Issue 1: Build Agent Context Data Source (FIXED in v8)
**Problem:** Process expected data from Load Bot State (Postgres query), but queries don't pass input through.

**Fix:** Reference Pre-Route Switch directly:
```javascript
const preRouterData = $('Pre-Route Switch').first().json;
```

### Issue 2: API Key Exposure (SECURITY)
**Problem:** OpenAI API key embedded in "Parallel TTS & Send" code.

**Fix:** Move to n8n credentials or environment variable:
```javascript
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
// OR use n8n credential reference
```

### Issue 3: Switch Node Conditions (VERIFY)
**Problem:** Route Switch and Pre-Route Switch show 0 conditions in config.

**Action:** Likely using expression-based routing. Needs validation of actual condition logic.

### Issue 4: Connection Topology (VERIFY)
**Problem:** Some nodes referenced in code but routing unclear.

**Action:** Manually trace all 21 connections to verify complete flow.

---

## Part 10: Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Pre-Router Latency | <10ms | v4.6 optimized |
| Agent Max Iterations | Variable | 5 |
| TTS Chunk Size | Sentence-level | ~50 chars avg |
| DB Query Latency | <100ms | Postgres v2.6 |

---

## Part 11: File References for Restructuring

### Generated Analysis Files
1. `/Users/jelalconnor/CODING/N8N/Workflows/WORKFLOW_ANALYSIS_d3CxEaYk5mkC8sLo.md`
   - Complete workflow breakdown

2. `/Users/jelalconnor/CODING/N8N/Workflows/WORKFLOW_STRUCTURE_d3CxEaYk5mkC8sLo.json`
   - Node configuration reference (JSON)

3. `/Users/jelalconnor/CODING/N8N/Workflows/WORKFLOW_RESTRUCTURING_GUIDE_d3CxEaYk5mkC8sLo.md`
   - This file - implementation guide

### Code Patterns
- **Code Nodes:** 11 custom implementation nodes with 48+ KB total code
- **Node References:** 4 nodes cross-reference other nodes
- **External APIs:** 1 direct (OpenAI TTS), 1 indirect (Recall.ai), 1 LLM (OpenRouter)

---

## Part 12: Restructuring Roadmap

### Phase 1: Preparation
- [ ] Review all 25 nodes and 21 connections
- [ ] Document all code node logic
- [ ] Map database schema
- [ ] Identify LangChain tool requirements

### Phase 2: Architecture Design
- [ ] Design WebSocket listener replacement
- [ ] Plan streaming transcript handling
- [ ] Design agent response streaming
- [ ] Plan interruption handling

### Phase 3: Node Replacement/Updates
- [ ] Replace webhook with OpenAI Realtime listener
- [ ] Update Process Transcript for streaming
- [ ] Update Ultra-Fast Pre-Router for partial transcripts
- [ ] Simplify or remove Intent Summary Merger (faster response needed)

### Phase 4: Agent Configuration
- [ ] Adjust agent iteration limits
- [ ] Test tool output streaming
- [ ] Verify Think tool behavior
- [ ] Configure interruption handling

### Phase 5: TTS & Output Handling
- [ ] Replace Parallel TTS & Send with streaming
- [ ] Implement real-time audio delivery
- [ ] Add interruption cancellation
- [ ] Test bi-directional audio

### Phase 6: Testing & Validation
- [ ] Unit test each updated node
- [ ] Integration test full pipeline
- [ ] Load test streaming performance
- [ ] Validate interruption handling

---

## Summary

The current workflow is a sophisticated multi-stage voice bot with:
- **11 code nodes** implementing custom business logic
- **4 LangChain nodes** for AI agent orchestration
- **5 PostgreSQL nodes** for state and logging
- **Heuristic classification** before agent processing
- **Multi-path routing** for efficiency

For OpenAI Realtime API integration, the key changes are:
1. Replace discrete webhook with streaming WebSocket input
2. Convert batch processors to streaming processors
3. Implement partial transcript handling
4. Add real-time interruption management
5. Stream tool outputs and agent responses

All node configurations and code patterns have been documented for the restructuring effort.
