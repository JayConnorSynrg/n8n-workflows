# N8N Workflows - Orchestrator

**Architecture:** Sub-agent delegation | **Pattern Library:** `.claude/patterns/`

---

## SUPREME RULE: Mandatory Sub-Agent Execution

**The orchestrator NEVER executes - it ONLY orchestrates.**

```
┌────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR RESPONSIBILITIES (ONLY THESE)                       │
├────────────────────────────────────────────────────────────────────┤
│  ✓ PLAN     → Define objectives, break tasks into sub-tasks       │
│  ✓ ROUTE    → Select appropriate sub-agent for each task          │
│  ✓ DELEGATE → Invoke sub-agents via Task() tool                   │
│  ✓ COORDINATE → Manage parallel execution, handle dependencies    │
│  ✓ VALIDATE → Review sub-agent outputs, approve/reject            │
│  ✓ EVOLVE   → Document patterns, propose improvements             │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR MUST NEVER (ZERO TOLERANCE)                         │
├────────────────────────────────────────────────────────────────────┤
│  ✗ READ large files directly     → Delegate to Explore agent      │
│  ✗ WRITE code directly           → Delegate to specialist agent   │
│  ✗ CALL MCP tools directly       → Delegate to *-mcp-delegate     │
│  ✗ DEBUG errors directly         → Delegate to debugger agents    │
│  ✗ RESEARCH directly             → Delegate to Explore/general    │
│  ✗ EXECUTE any implementation    → ALWAYS delegate                │
└────────────────────────────────────────────────────────────────────┘
```

**Agent Gap Protocol:**
If no suitable sub-agent exists for a task:
1. **STOP** - Do NOT execute directly
2. **PROPOSE** - Suggest new agent to user (name, purpose, tools, model)
3. **WAIT** - Get user approval
4. **CREATE** - Use `/synrg-swarm` or create in `.claude/agents/`
5. **DELEGATE** - Then route the task to the new agent

**Sub-Agent Selection Quick Reference:**

| Task Category | Sub-Agent | Model |
|---------------|-----------|-------|
| n8n node issues | `n8n-node-validator` | haiku |
| n8n connections | `n8n-connection-fixer` | haiku |
| n8n versions | `n8n-version-researcher` | haiku |
| n8n expressions | `n8n-expression-debugger` | haiku |
| n8n patterns | `n8n-pattern-retriever` | haiku |
| n8n complex | `n8n-workflow-expert` | sonnet |
| n8n MCP calls | `n8n-mcp-delegate` | haiku |
| GitHub MCP calls | `github-mcp-delegate` | haiku |
| Codebase exploration | `Explore` | sonnet |
| General research | `general-purpose` | sonnet |
| Code implementation | `full-stack-dev-expert` | sonnet |
| **NO AGENT EXISTS** | **PROPOSE NEW AGENT** | - |

---

## AIO Voice System (Priority Reference)

**When user says "AIO Voice System"** - refers to the complete voice assistant ecosystem:

### Service Architecture (Railway + External)

| Service | Location | Purpose | Key Files |
|---------|----------|---------|-----------|
| **Client (Web UI)** | `voice-agent-poc/client-v2/` | React app with LiveKit connection | `src/hooks/useLiveKitAgent.ts`, `src/lib/store.ts` |
| **LiveKit Agent** | `voice-agent-poc/livekit-voice-agent/` | Python voice agent | `src/agent.py`, `src/tools/` |
| **Async Worker** | (in agent) | Background tool execution | `src/utils/async_tool_worker.py` |
| **Database** | PostgreSQL on Railway | Tool call logging, session context | `database/schema.sql` |
| **n8n Workflows** | `jayconnorexe.app.n8n.cloud` | Tool backends (Drive, Email, DB) | MCP tools |
| **Recall.ai** | External | Meeting bot audio capture | - |
| **LLM** | Cerebras `llama-3.3-70b` | Function calling + reasoning | - |
| **STT** | Deepgram `nova-3` | Speech-to-text | - |
| **TTS** | Cartesia `sonic-3` | Text-to-speech | - |

### Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CLIENT (React)                                                              │
│  useLiveKitAgent.ts → LiveKit Room → Data Channel messages                   │
│  Message types: tool.call, tool.executing, tool.completed, tool.error        │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │ ▲
                     LiveKit WebRTC │ │ Data Channel
                                    ▼ │
┌──────────────────────────────────────────────────────────────────────────────┐
│  LIVEKIT AGENT (Python)                                                      │
│  agent.py → LLM (Cerebras) → Tool calls → async_tool_worker.py              │
│  Publishes results to data channel topic: "tool_result"                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                     HTTP webhooks  │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  N8N WORKFLOWS                                                               │
│  /execute-gmail, /drive-document-repo, /database-query, etc.                │
│  Logs to PostgreSQL tool_calls table, returns voice_response for TTS         │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  POSTGRESQL DATABASE                                                         │
│  Tables: tool_calls (gated execution), session_context, audit_trail          │
│  tool_calls.status: EXECUTING → COMPLETED/FAILED/CANCELLED                   │
│  tool_calls.voice_response: TTS text for agent announcement                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Key Database Schema (tool_calls)

```sql
CREATE TABLE tool_calls (
    tool_call_id VARCHAR(100) UNIQUE NOT NULL,  -- tc_xxx or lk_xxx format
    session_id VARCHAR(100) NOT NULL,
    function_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'EXECUTING',  -- EXECUTING, COMPLETED, FAILED, CANCELLED
    result JSONB,
    voice_response TEXT,  -- TTS text for agent to speak
    callback_url TEXT,    -- For gated execution (multi-turn)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

**AIO Tools Registry:** `voice-agent-poc/livekit-voice-agent/docs/AIO-TOOLS-REGISTRY.md`
- Security ratings for all voice agent tools
- Modular format for adding new tools
- Reference this when user mentions "AIO tools"

**Key Workflows:**
- `IamjzfFxjHviJvJg` - Google Drive Document Repository
- `gjYSN6xNjLw8qsA1` - Teams Voice Bot v3
- `ouWMjcKzbj6nrYXz` - Agent Context Access
- `kBuTRrXTJF1EEBEs` - Voice Tool: Send Gmail (multi-turn async gates)

**Health Check Command:** `railway logs` + n8n execution history

**🔴 MANDATORY: AIO Ecosystem Analysis Protocol**
When debugging or modifying ANY AIO Voice System component:
1. **DO NOT ask the user** about how components interact
2. **Analyze the full ecosystem yourself** by examining:
   - LiveKit agent code: `voice-agent-poc/livekit-voice-agent/`
   - Tool definitions: `voice-agent-poc/livekit-voice-agent/tools/`
   - AIO Tools Registry: `voice-agent-poc/livekit-voice-agent/docs/AIO-TOOLS-REGISTRY.md`
   - n8n workflow structures via MCP tools
3. The agent IS configured for multi-turn gate callbacks - this has been verified working

**Known Issues to Monitor:**
- Google Drive OAuth expiration (credential: `ylMLH2SMUpGQpUUr`)
- Gmail OAuth expiration (credential: `Wagsju9B8ofYq2Sl` - Jayconnor@synrgscaling.com) - **CHECK STATUS**
- Cerebras tool calling with smaller models (use 70b+)

---

## Agent Selection (Delegate via Task tool)

**Agent Definitions:** `.claude/agents/`

| Task | Agent | Model | Definition |
|------|-------|-------|------------|
| Invalid nodes | `n8n-node-validator` | haiku | `agents/n8n-node-validator.md` |
| Connection errors | `n8n-connection-fixer` | haiku | `agents/n8n-connection-fixer.md` |
| Version issues | `n8n-version-researcher` | haiku | `agents/n8n-version-researcher.md` |
| Expression errors | `n8n-expression-debugger` | haiku | `agents/n8n-expression-debugger.md` |
| Pattern lookup | `n8n-pattern-retriever` | haiku | `agents/n8n-pattern-retriever.md` |
| Complex/multi-step | `n8n-workflow-expert` | sonnet | `agents/n8n-workflow-expert.md` |

**Delegation Example:**
```javascript
Task({
  subagent_type: "n8n-pattern-retriever",
  prompt: "Retrieve patterns for @n8n/n8n-nodes-langchain.openAi",
  model: "haiku"
})
```

---

## Critical N8N Rules

### 1. ALWAYS Use Latest TypeVersions
- Research with `mcp__n8n-mcp__get_node` before implementing ANY node
- Never rollback to older versions - debug forward only

### 2. Anti-Memory Protocol (OpenAI Image Nodes)
- **DO NOT trust memory** - read `.claude/patterns/api-integration/openai-image-nodes.md` EVERY TIME
- `binaryPropertyName: "data"` NOT `"=data"` (no = prefix on property names)
- `modelId` requires ResourceLocator format: `{ "__rl": true, "value": "gpt-4o", "mode": "list" }`

### 3. Expression Syntax
| Type | Format | Example |
|------|--------|---------|
| Static value | `"value"` | `"data"`, `"high"` |
| Dynamic expression | `"={{ expr }}"` | `"={{ $json.field }}"` |
| Property name | `"name"` (no prefix) | `"binaryPropertyName": "data"` |

### 4. Connection Syntax
- `type` must be `"main"` not `"0"`
- `index` must be integer not string

### 5. Error Handling (Build Resilient from Start)
**Apply error handling during initial build, not as afterthought:**

| Node Category | Error Property | Retry Config |
|--------------|----------------|--------------|
| Switch/Route nodes | `onError: "continueErrorOutput"` | N/A |
| External API (OpenAI) | `onError: "continueRegularOutput"` | `retryOnFail: true, maxTries: 2` |
| OAuth APIs (Google) | `onError: "continueRegularOutput"` | Optional |
| Critical DB (Search) | `onError: "continueRegularOutput"` | `retryOnFail: true` |
| Logging DB | `onError: "continueRegularOutput"` | None |

**Symbiotic Error Handling:** When using `continueRegularOutput`, downstream Code nodes MUST detect errors:
```javascript
// At START of Code nodes downstream of error-handled nodes:
if (input.error || !input.expectedField) {
  return [{ json: { error: true, message: errorMsg, /* defaults */ } }];
}
```

---

## Validation Criteria

**Valid workflow requires:**
- [ ] All nodes use latest typeVersion
- [ ] No expression syntax errors (= prefix contamination)
- [ ] All connections use `type: "main"`
- [ ] Error handling applied per node category (Rule 5)
- [ ] Downstream Code nodes detect errors (symbiotic handling)
- [ ] `mcp__n8n-mcp__n8n_validate_workflow` passes
- [ ] Patterns consulted for node types in `.claude/patterns/pattern-index.json`

---

## Pattern Retrieval

**Index:** `.claude/patterns/pattern-index.json`
- `node_type_mappings` - Node type → pattern IDs
- `task_mappings` - Task type → pattern IDs

**Sub-agents read patterns before acting. Orchestrator delegates, doesn't implement.**

---

## Credentials Registry (MANDATORY)

**ALWAYS confirm credentials before workflow creation/modification.**

### Active Credentials

| Service | Credential Name | Credential ID | Status |
|---------|-----------------|---------------|--------|
| **Google Drive** | JayConnor@synrgscaling.com | `TBD - needs creation` | PRIMARY |
| **PostgreSQL** | MICROSOFT TEAMS AGENT DATABASE | `NI3jbq1U8xPst3j3` | Active |
| **OpenAI** | OpenAi account | `6BIzzQu5jAD5jKlH` | Active |
| **Gmail** | Gmail account 2 | `kHDxu9JVLxm6iyMo` | Active |
| **Google Sheets** | Google Sheets account | `fzaSSwZ4tI357WUU` | Active |
| **Google Docs** | Google Docs account | `iNIP35ChYNUUqOCh` | Active |

### Deprecated Credentials (DO NOT USE)

| Service | Credential Name | Credential ID | Reason |
|---------|-----------------|---------------|--------|
| Google Drive | Autopayplusworkflows@gmail.com | `jlnNh8eZIxWdsvDS` | Legacy, OAuth disabled |

### Pre-Deployment Gate

Before ANY workflow creation:
1. List required services
2. Match to credentials above
3. If credential missing or uncertain → **ASK USER**
4. Present credential plan for approval

---

## Current Workflows
- **AI Carousel Generator** - ID: `8bhcEHkbbvnhdHBh`
- **Google Drive Document Repository** - ID: `IamjzfFxjHviJvJg` (needs credential update)
- **File Download & Email Subworkflow** - ID: `z61gjAE9DtszE1u2` (callable via webhook `/file-download-email` or Execute Workflow node)

## Skills Available

| Skill | Location | Purpose |
|-------|----------|---------|
| `n8n-debugging` | `.claude/skills/n8n-debugging/` | Systematic debugging methodology with 5-Why analysis |

**Sub-agents inherit skills automatically.** All n8n agents have `skills: n8n-debugging` in their frontmatter.

---

## On-Demand Documentation
- `.claude/ORCHESTRATOR-DETAILS.md` - Delegation examples, agent creation, MCP tools
- `.claude/skills/n8n-debugging/SKILL.md` - Full debugging methodology (replaces /synrg-n8ndebug for sub-agents)
- `.claude/patterns/README.md` - Pattern library navigation
- `.claude/CLAUDE.md.full-backup` - Complete 830-line reference
