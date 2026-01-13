# Teams Voice Bot v3.0 - Orchestrator Agent Configuration

**Workflow ID:** `d3CxEaYk5mkC8sLo`
**Created:** 2025-12-27T04:48:10.416Z
**Updated:** 2026-01-09T18:22:39.628Z
**Status:** Active

---

## Orchestrator Agent Node Configuration

### Node Details
- **Name:** Orchestrator Agent
- **Type:** `@n8n/n8n-nodes-langchain.agent`
- **Type Version:** 3
- **ID:** `6b9b0552-8540-47fa-b65d-d2d46882fc5a`
- **Position:** [1024, 480]

### Parameters

```json
{
  "promptType": "define",
  "text": "={{ $json.chat_input }}",
  "options": {
    "systemMessage": "={{ $json.system_prompt }}",
    "maxIterations": 5
  }
}
```

### Input Sources

The Orchestrator Agent receives input from the **Build Agent Context** node, which constructs:

1. **`chat_input`**: The user's transcript (from Process Transcript node)
2. **`system_prompt`**: Dynamically generated system message containing:
   - Voice assistant instructions
   - Anti-repeat rules with previous responses
   - Available tools list
   - Email workflow guidance
   - Conversation history (up to 4 recent interactions)
   - Response urgency indicator
   - Complete thought detection state

### System Prompt Structure

The system prompt is dynamically built and contains:

```
1. Role Definition: "You are a voice assistant in a Microsoft Teams meeting"
2. Critical Anti-Repeat Rules: Lists previous responses to avoid duplicates
3. Response Rules: Based on urgency level (wait/standard/immediate)
4. Tools Available:
   - gmail_agent: Send emails
   - think: Internal reasoning (silent)
5. Email Workflow Instructions: Step-by-step email handling
6. Conversation History: Up to 4 recent user messages + bot responses
7. Current Input: Intent, speaker, message count
```

### Connected Tools

The agent has access to two LangChain tools:

#### 1. Gmail Agent Tool
- **Type:** `@n8n/n8n-nodes-langchain.toolWorkflow`
- **Version:** 2.2
- **Workflow ID:** `kL0AP3CkRby6OmVb`
- **Input Parameters:**
  - `transcript` (required): Email content from AI extraction
  - `email_address` (required): Recipient's email address
  - `context` (optional): Additional context object
  - `bot_id`: Current bot identifier
  - `session_id`: Session tracking ID

#### 2. Think Tool
- **Type:** `@n8n/n8n-nodes-langchain.toolThink`
- **Version:** 1.1
- **Purpose:** Internal reasoning (silent, not spoken to user)

### Language Model

Connected to **OpenRouter Chat Model**:
- **Model:** `openai/gpt-4o-mini`
- **Type:** `@n8n/n8n-nodes-langchain.lmChatOpenRouter`
- **Credentials:** OpenRouter account (ID: OPPAOWUbmkR2frSd)

---

## Workflow Flow

```
Webhook (POST /voice-bot-v3)
  ↓
Process Transcript (classify intent, detect duplicates)
  ↓
Route Switch (SILENT | WAIT_LOG | LISTEN | PROCESS | NO_TRANSCRIPT)
  ↓
[Branch: PROCESS Route]
  ↓
Load Bot State (fetch last 4 interactions from database)
  ↓
Build Agent Context (construct system prompt + input context)
  ↓
Orchestrator Agent ← OpenRouter Chat Model (ai_languageModel)
                  ← Gmail Agent Tool (ai_tool)
                  ← Think Tool (ai_tool)
  ↓
Check Agent Output (validate response exists)
  ↓
Split into Sentences (chunk response for TTS)
  ↓
Parallel TTS & Send (convert to speech + send audio chunks)
  ↓
Build Immutable Log (record interaction metadata)
  ↓
Call Logging Agent (persist to database)
```

---

## Key Features

### 1. Anti-Repeat Logic
- Tracks previous responses per bot
- Prevents identical responses within same conversation
- Warns agent if already asked for email address
- Flags continuations to avoid duplicate confirmations

### 2. Response Timing
- Detects complete thoughts (punctuation + word count)
- Routes incomplete transcripts to WAIT_LOG (no response)
- Urgency levels: `wait`, `none`, `standard`, `immediate`
- Email requests and direct bot addressing = immediate

### 3. Session State Management
- Static workflow data stores bot transcript history per `bot_id`
- Tracks processing count, last response time, pending actions
- Resets session after 5+ minutes of inactivity
- Deduplication with 15-second window

### 4. Conversation Context
- Retrieves last 4 interactions from database
- Includes user messages + bot responses in system prompt
- Detects if user is continuing previous topic
- Adjusts response guidance based on conversation state

### 5. Email Workflow
- Guides agent to ask for email address if not provided
- Prevents re-asking if already requested
- Tracks email-related intents separately
- Uses Gmail workflow tool for sending

---

## Database Connections

All Postgres nodes use credential: **MICROSOFT TEAMS AGENT DATABASE** (ID: NI3jbq1U8xPst3j3)

**Tables:**
- `transcript_log` - Stores all transcript classifications
- `interaction_logs` - Stores full conversations with AI responses

---

## Important Configuration Notes

1. **Max Iterations:** 5 (agent can call tools up to 5 times per request)
2. **Response Mode:** onReceived (webhook responds immediately, processing continues)
3. **TTS Processing:** Response is split into sentences and converted to speech chunks
4. **Logging:** All interactions recorded immutably with full context

---

## Complete Workflow JSON

Full workflow configuration saved to:
**File:** `/Users/jelalconnor/CODING/N8N/Workflows/workflow-d3CxEaYk5mkC8sLo-COMPLETE.json`

This includes all 18 nodes with complete parameters, connections, and credentials.
