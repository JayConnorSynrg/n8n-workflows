# Teams Voice Bot v3.0 - Agent Orchestrator
## Complete Workflow Analysis

**Workflow ID:** `d3CxEaYk5mkC8sLo`
**Status:** Active
**Created:** 2025-12-27T04:48:10.416Z
**Last Updated:** 2026-01-10T07:47:00.470Z

---

## Executive Summary

This is a sophisticated voice bot orchestration workflow designed to handle real-time conversation management with Teams integration. It uses an ultra-fast pre-router to classify intents before routing to a LangChain-based agent for complex reasoning, with fallback paths for quick acknowledgments and template responses.

**Architecture Pattern:** Multi-stage pipeline with parallel processing and intelligent routing.

---

## Workflow Structure

### Node Count & Composition
- **Total Nodes:** 25
- **Total Connections:** 21
- **Code Nodes:** 9 (custom business logic)
- **AI/LangChain Nodes:** 4 (agent orchestration)
- **Database Nodes:** 5 (PostgreSQL)
- **Control Flow:** 2 (Switch, IF)
- **Other:** 5 (Webhook, ExecuteWorkflow, etc.)

### Node TypeVersion Compliance
| Node Type | Versions Used |
|-----------|---|
| `n8n-nodes-base.webhook` | 2.1 |
| `n8n-nodes-base.code` | 2 |
| `n8n-nodes-base.switch` | 3, 3.2 |
| `n8n-nodes-base.postgres` | 2.6 |
| `n8n-nodes-base.if` | 2.3 |
| `n8n-nodes-base.executeWorkflow` | 1.2 |
| `@n8n/n8n-nodes-langchain.agent` | 3 |
| `@n8n/n8n-nodes-langchain.lmChatOpenRouter` | 1 |
| `@n8n/n8n-nodes-langchain.toolWorkflow` | 2.2 |
| `@n8n/n8n-nodes-langchain.toolThink` | 1.1 |

**Status:** All nodes using latest or near-latest typeVersions. Minor upgrade available for Switch (3 → 3.2).

---

## Data Flow & Architecture

### Entry Point
```
POST /voice-bot-v3 (Webhook)
├─ Receives voice conversation data
├─ Extracts transcript, speaker, participant info
└─ Route: Immediate to Process Transcript
```

### Primary Pipeline
```
1. Process Transcript (Code v2)
   - Parses webhook payload
   - Checks for pre-processed data
   - Extracts: transcript, speaker, bot_id, words array

2. Ultra-Fast Pre-Router (Code v2) [11,976 chars]
   - Sub-10ms heuristic classification
   - Routes based on: silence detection, intent markers, greeting patterns
   - Output: pre_route flag (SILENT, BUFFER, WAIT_LOG, or FULL_PROCESS)

3. Pre-Route Switch (Switch v3)
   - Branches based on pre_route classification:
     * SILENT → Log Silent Transcript (Postgres)
     * BUFFER/WAIT_LOG → Wait Log Only (Code) → Log Wait Transcript
     * FULL_PROCESS → Intent Summary Merger → Orchestrator Agent

4. Intent Summary Merger (Code v6,503 chars)
   - Multi-signal routing decision
   - Weights: History (40%) + Intent (40%) + Interrupt (20%)
   - Pulls from Fast Intent Query (Postgres) for historical context

5. Load Bot State (Postgres v2.6)
   - Retrieves stored bot context and state

6. Build Agent Context (Code v3,278 chars)
   - Constructs system prompt and context
   - References Pre-Route Switch data for transcript/bot_id
   - Prepares agent input

7. Orchestrator Agent (LangChain Agent v3)
   - Model: OpenRouter (GPT-4o-mini)
   - Max iterations: 5
   - Prompt Type: define (uses dynamic prompt from context)
   - Input: {{ $json.chat_input }} + system message
   - Available Tools:
     * Gmail Agent Tool (toolWorkflow v2.2)
     * Think Tool (toolThink v1.1) - for reasoning
```

### Post-Agent Processing
```
8. Check Agent Output (IF v2.3)
   - Validates agent response

9. Split into Sentences (Code v2,644 chars)
   - Chunking for progressive TTS
   - Extracts bot_id, voice settings

10. Parallel TTS & Send (Code v4,151 chars)
    - External API calls to OpenAI TTS
    - Sequential delivery via Recall.ai
    - API Key embedded in code (security note)
```

### Interrupt Handling
```
11. Interrupt Handler (Code v2,196 chars)
    - Handles interrupts (hard_stop, soft, bot_name)
    - Routes to Log Interrupt (Postgres)
    - Support for interrupt analytics
```

### Quick Response Paths
```
- Quick Acknowledge (Code v413 chars)
  Returns: "I'm listening...", "Go ahead...", etc.

- Quick Reply (Code v794 chars)
  Template responses for greetings
  Uses static data for session context
```

---

## Critical Implementation Details

### Code Node Implementations

#### 1. **Process Transcript** (10,991 chars)
- **Purpose:** Initial webhook payload parsing
- **Key Logic:**
  - Detects pre-processed vs raw webhook data
  - Checks for `pre_route` flag from pre-router
  - Extracts: words array, participant info, transcript
  - Falls back to original parsing if not pre-processed
- **Mode:** runOnceForEachItem

#### 2. **Ultra-Fast Pre-Router** (11,976 chars)
- **Purpose:** Sub-10ms intent classification before agent processing
- **Classification Routes:**
  - `SILENT`: Detected silence/no speech
  - `BUFFER`: Partial data, wait for more
  - `WAIT_LOG`: Log without processing
  - `FULL_PROCESS`: Route to agent for full reasoning
- **Heuristics Detected:**
  - is_silence
  - is_partial_data
  - is_greeting
  - is_interruption
  - is_bot_name_mentioned
- **Key Fix (v4.6):** Routes partial_data to SILENT (not BUFFER) to reduce execution overhead from ~10 to 1 per utterance

#### 3. **Build Agent Context** (3,278 chars)
- **Purpose:** Construct agent input and system prompt
- **Critical Issue (v8 FIX):**
  - Load Bot State is a Postgres query, doesn't pass input through
  - Must reference Pre-Route Switch data directly for transcript/bot_id
  - Fixed to use `$('Pre-Route Switch').first().json` for source data
- **Output:** Prepared context with chat_input, system_prompt

#### 4. **Build Immutable Log** (3,630 chars)
- **Purpose:** Create TTS logging record
- **References:**
  - Orchestrator Agent output
  - Build Agent Context metadata
  - Classifier data from Pre-Router
  - Heuristics and intent markers
- **Logging:** Enhanced TTS events with route decision tracking

#### 5. **Intent Summary Merger** (6,503 chars)
- **Purpose:** Multi-signal routing decision
- **Weighting Algorithm:**
  - History signals: 40%
  - Intent signals: 40%
  - Interrupt signals: 20%
- **Inputs:**
  - fastSignals from Ultra-Fast Pre-Router
  - dbResults from Fast Intent Query
- **Output:** Final route decision with confidence scores

#### 6. **Split into Sentences** (2,644 chars)
- **Purpose:** Progressive TTS delivery chunking
- **Features:**
  - Splits agent response into sentences
  - Preserves bot_id, voice settings
  - Handles both agent output AND quick responses
- **v3.0 Fix:** Corrected bot_id extraction from Build Agent Context or Pre-Route Switch

#### 7. **Parallel TTS & Send** (4,151 chars)
- **Purpose:** External API calls to OpenAI TTS + Recall.ai delivery
- **Features:**
  - Parallel TTS generation
  - Sequential Recall.ai delivery
  - Voice selection (default: 'alloy')
  - Bot status check before sending
- **Security Note:** API key embedded in code

#### 8. **Quick Acknowledge** (413 chars)
- **Purpose:** Fast response when bot is not directly addressed
- **Response Templates:**
  - "I'm listening..."
  - "Go ahead..."
  - "Yes?"
  - "I hear you..."
- **Rotation:** Random selection based on timestamp

#### 9. **Quick Reply** (794 chars)
- **Purpose:** Template responses for simple greetings
- **Features:**
  - Greeting detection from heuristics
  - Static reply templates
  - Session-aware responses
  - Uses workflow static data

#### 10. **Interrupt Handler** (2,196 chars)
- **Purpose:** Handle mid-conversation interrupts
- **Interrupt Types:**
  - hard_stop: Complete interruption
  - soft: Gentle interruption
  - bot_name: User said bot name
- **Output:** Interrupt response + logging for analytics

---

## Orchestrator Agent (LangChain Agent v3)

### Configuration
| Setting | Value |
|---------|-------|
| Type | LangChain Agent v3 |
| Model | openai/gpt-4o-mini via OpenRouter |
| Max Iterations | 5 |
| Prompt Type | define (dynamic) |
| System Message | `={{ $json.system_prompt }}` |
| Chat Input | `={{ $json.chat_input }}` |

### Available Tools
1. **Gmail Agent Tool** (toolWorkflow v2.2)
   - Description: "Use this tool to search, read, and manage Gmail emails. Can search for emails, get email content, send emails, reply to emails, and manage labels."
   - Type: Workflow tool
   - Input: workflowId, workflowInputs

2. **Think Tool** (toolThink v1.1)
   - Purpose: Internal reasoning/thinking before action
   - Useful for complex decision-making within agent loop

---

## Database Operations (PostgreSQL v2.6)

### Nodes
1. **Load Bot State** - Retrieve stored bot context
2. **Log Silent Transcript** - Audit trail for silent inputs
3. **Log Wait Transcript** - Audit trail for buffered inputs
4. **Fast Intent Query** - Historical context lookup (for Intent Summary Merger)
5. **Log Interrupt** - Interrupt event analytics

### Integration Points
- Called from Route Switch (conditional paths)
- Called from Intent Summary Merger (context enrichment)
- Called from Interrupt Handler (analytics)

---

## Webhook Configuration

| Property | Value |
|----------|-------|
| Path | `/voice-bot-v3` |
| HTTP Method | POST |
| Webhook ID | `voice-bot-v3` |
| typeVersion | 2.1 |

### Expected Payload Structure
```json
{
  "body": {
    "data": {
      "data": {
        "words": [
          { "text": "...", "startTime": 0, "endTime": 100 }
        ],
        "participant": { "name": "user_name" }
      }
    }
  }
}
```

---

## Credentials & External Dependencies

### Required Credentials
1. **openRouterApi** - For OpenRouter LLM calls (GPT-4o-mini)
2. **postgres** - For all database operations

### External API Integrations
- **OpenAI API** (TTS) - Called from "Parallel TTS & Send" code
- **Recall.ai** - Sequential delivery of TTS audio
- **OpenRouter** - LLM inference via agent

---

## Workflow Settings

| Setting | Value |
|---------|-------|
| Execution Order | v1 |
| Caller Policy | workflowsFromSameOwner |
| Available in MCP | False |

---

## Current Routing Decision Tree

```
Webhook Input
    ↓
Process Transcript (parse raw data)
    ↓
Ultra-Fast Pre-Router (heuristic classification)
    ↓
    ├─ SILENT → Log Silent → End
    │
    ├─ BUFFER → Wait Log → Log Wait → End
    │
    ├─ WAIT_LOG → Wait Log → Log Wait → End
    │
    └─ FULL_PROCESS
        ↓
        Fast Intent Query (DB context)
        ↓
        Intent Summary Merger (weighted routing)
        ↓
        Load Bot State (DB context)
        ↓
        Build Agent Context (prepare prompt)
        ↓
        Orchestrator Agent (LLM reasoning)
        ├─ Uses tools: Gmail, Think
        └─ Max iterations: 5
            ↓
            Check Agent Output (IF validation)
            ↓
            Split into Sentences (TTS chunking)
            ↓
            Parallel TTS & Send (external TTS + delivery)
            ↓
            End
```

---

## Known Issues & Implementation Notes

### 1. **Interrupt Handler Integration**
- Routes to Log Interrupt for analytics
- Independent path from main agent flow
- May need connection/routing clarification for OpenAI Realtime integration

### 2. **API Key Security**
- OpenAI API key embedded in "Parallel TTS & Send" code
- Should be externalized to environment variables or n8n credentials

### 3. **Switch Node Conditions**
- Route Switch and Pre-Route Switch show 0 conditions in config
- Likely using expression-based routing (not visible in config extract)
- May need validation of actual condition logic

### 4. **Bot State Loading**
- Process flow assumes Load Bot State is called before Build Agent Context
- Fixed in Build Agent Context v8 to reference correct data source

### 5. **Connection Count vs Flow**
- 21 connections for complex routing
- All major nodes properly connected
- Some implicit connections via code node references

---

## Data Flow Summary

### Optimal Path (FULL_PROCESS)
1. Input: 100-200 bytes (webhook JSON)
2. Process Transcript: 10KB+ (parsed + metadata)
3. Ultra-Fast Pre-Router: 1-5KB (routing decision)
4. Intent Summary Merger: 2-3KB (weighted signal)
5. Load Bot State: Variable (DB query results)
6. Build Agent Context: 3-5KB (structured prompt)
7. Orchestrator Agent: Variable (LLM input/output)
8. TTS Pipeline: 1-10KB per sentence (chunked responses)

### Silent/Buffer Path
- Fast exit after heuristic classification
- Minimal database overhead
- Logging only

---

## Restructuring Considerations for OpenAI Realtime API

### Current Architecture Issues for Realtime
1. **Webhook-based input** - Assumes discrete requests (not streaming)
2. **Batch processing nodes** - Multiple code nodes with runOnceForEachItem
3. **Sequential TTS** - Built for discrete utterances, not continuous
4. **Intent classification** - Pre-router works with complete transcripts

### Required Changes
1. Replace webhook with streaming input mechanism
2. Convert batch processors to streaming processors
3. Implement bi-directional communication channel (WebSocket)
4. Simplify intent classification for real-time constraints
5. Handle partial transcripts and confidence updates
6. Manage tool output streaming to client
7. Implement cancellation/interruption handling

---

## Performance Characteristics

- **Pre-Router Target:** Sub-10ms classification
- **Agent Max Iterations:** 5 (prevents runaway loops)
- **TTS Chunking:** Sentence-level for progressive delivery
- **Execution Model:** Sequential with conditional branches

---

## Files & References

**Workflow Definition:** Saved in n8n database
**Analysis Date:** 2026-01-10
**Extract Method:** MCP n8n-mcp__n8n_get_workflow (full mode)
