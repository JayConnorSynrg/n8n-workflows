# N8N Workflows - Orchestrator

**Architecture:** Sub-agent delegation | **Pattern Library:** `.claude/patterns/`

---

## SUPREME RULE: Mandatory Sub-Agent Execution

**The orchestrator NEVER executes - it ONLY orchestrates.**
- ONLY: PLAN → ROUTE → DELEGATE → COORDINATE → VALIDATE → EVOLVE
- NEVER: Read large files, write code, call MCP, debug, research, or execute directly
- **Agent Gap:** No agent exists → STOP → PROPOSE → WAIT → CREATE → DELEGATE

**Sub-Agent Selection:**

| Task Category | Sub-Agent | Model | Definition |
|---------------|-----------|-------|------------|
| n8n node issues | `n8n-node-validator` | haiku | `agents/n8n-node-validator.md` |
| n8n connections | `n8n-connection-fixer` | haiku | `agents/n8n-connection-fixer.md` |
| n8n versions | `n8n-version-researcher` | haiku | `agents/n8n-version-researcher.md` |
| n8n expressions | `n8n-expression-debugger` | haiku | `agents/n8n-expression-debugger.md` |
| n8n patterns | `n8n-pattern-retriever` | haiku | `agents/n8n-pattern-retriever.md` |
| n8n complex | `n8n-workflow-expert` | sonnet | `agents/n8n-workflow-expert.md` |
| n8n MCP calls | `n8n-mcp-delegate` | haiku | - |
| GitHub MCP calls | `github-mcp-delegate` | haiku | - |
| Codebase exploration | `Explore` | sonnet | - |
| General research | `general-purpose` | sonnet | - |
| Code implementation | `full-stack-dev-expert` | sonnet | - |
| **NO AGENT EXISTS** | **PROPOSE NEW AGENT** | - | - |

---

## AIO Voice System (Priority Reference)

**When user says "AIO Voice System"** - the complete voice assistant ecosystem.
**Full architecture + diagrams + schema:** `.claude/aio-voice-system.md` (on-demand)

| Service | Location | Purpose |
|---------|----------|---------|
| Client | `voice-agent-poc/client-v2/` | React + LiveKit |
| Agent | `voice-agent-poc/livekit-voice-agent/` | Python voice agent |
| n8n | `jayconnorexe.app.n8n.cloud` | Tool backends (Drive, Email, DB) |
| DB | PostgreSQL on Railway | tool_calls, session_context |
| LLM | Cerebras (see MEMORY.md for current models) | Function calling |
| STT/TTS | Deepgram nova-3 / Cartesia sonic-3 | Audio I/O |

**AIO Tools Registry:** `voice-agent-poc/livekit-voice-agent/docs/AIO-TOOLS-REGISTRY.md`
**Key Workflows:** `IamjzfFxjHviJvJg` (Drive), `gjYSN6xNjLw8qsA1` (Teams VB v3), `ouWMjcKzbj6nrYXz` (Context), `kBuTRrXTJF1EEBEs` (Gmail gates)

**MANDATORY:** When debugging AIO components, analyze the full ecosystem yourself (agent code, tools/, AIO Tools Registry, n8n workflows via MCP). DO NOT ask the user how components interact.

**Known Issues:** Google Drive OAuth (`ylMLH2SMUpGQpUUr`), Gmail OAuth (`Wagsju9B8ofYq2Sl`), Cerebras model compatibility (see MEMORY.md)

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

**Index:** `.claude/patterns/pattern-index.json` (node_type_mappings, task_mappings). Sub-agents read patterns before acting.

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
- `.claude/aio-voice-system.md` - Full AIO architecture, data flow diagrams, DB schema
- `.claude/skills/n8n-debugging/SKILL.md` - Full debugging methodology
- `.claude/patterns/README.md` - Pattern library navigation
