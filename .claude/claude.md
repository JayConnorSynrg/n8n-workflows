# N8N Workflows - Project Instructions

**Architecture:** Sub-agent delegation | **Pattern Library:** `.claude/patterns/`
**Global rules (SYNRG, delegation, communication):** See `~/.claude/CLAUDE.md`

---

## Sub-Agent Selection

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

---

## AIO Voice System

**When user says "AIO Voice System"** — the complete voice assistant ecosystem.
**Full architecture:** `.claude/aio-voice-system.md` (on-demand)

| Service | Location | Purpose |
|---------|----------|---------|
| Client | `voice-agent-poc/client-v2/` | React + LiveKit |
| Agent | `voice-agent-poc/livekit-voice-agent/` | Python voice agent |
| n8n | `jayconnorexe.app.n8n.cloud` | Tool backends |
| DB | PostgreSQL on Railway | tool_calls, session_context |

**AIO Tools Registry:** `voice-agent-poc/livekit-voice-agent/docs/AIO-TOOLS-REGISTRY.md`
**Key Workflows:** `IamjzfFxjHviJvJg` (Drive), `gjYSN6xNjLw8qsA1` (Teams VB v3), `ouWMjcKzbj6nrYXz` (Context), `kBuTRrXTJF1EEBEs` (Gmail gates)
**Known Issues:** Google Drive OAuth (`ylMLH2SMUpGQpUUr`), Gmail OAuth (`Wagsju9B8ofYq2Sl`)

**MANDATORY:** When debugging AIO, analyze the full ecosystem (agent code, tools/, Registry, n8n workflows via MCP). DO NOT ask the user how components interact.

---

## Critical N8N Rules

### 1. ALWAYS Use Latest TypeVersions
Research with `mcp__n8n-mcp__get_node` before implementing ANY node. Debug forward only.

### 2. Anti-Memory Protocol (OpenAI Image Nodes)
Read `.claude/patterns/api-integration/openai-image-nodes.md` EVERY TIME. `binaryPropertyName: "data"` (no = prefix). `modelId` requires ResourceLocator: `{ "__rl": true, "value": "gpt-4o", "mode": "list" }`

### 3. Expression Syntax
| Type | Format | Example |
|------|--------|---------|
| Static value | `"value"` | `"data"` |
| Dynamic expression | `"={{ expr }}"` | `"={{ $json.field }}"` |
| Property name | `"name"` (no prefix) | `"binaryPropertyName": "data"` |

### 4. Connection Syntax
`type` must be `"main"` not `"0"`. `index` must be integer not string.

### 5. Error Handling

| Node Category | Error Property | Retry Config |
|--------------|----------------|--------------|
| Switch/Route | `onError: "continueErrorOutput"` | N/A |
| External API | `onError: "continueRegularOutput"` | `retryOnFail: true, maxTries: 2` |
| OAuth APIs | `onError: "continueRegularOutput"` | Optional |
| Critical DB | `onError: "continueRegularOutput"` | `retryOnFail: true` |
| Logging DB | `onError: "continueRegularOutput"` | None |

Downstream Code nodes MUST detect errors when using `continueRegularOutput`:
```javascript
if (input.error || !input.expectedField) {
  return [{ json: { error: true, message: errorMsg } }];
}
```

---

## Validation Criteria

- [ ] All nodes use latest typeVersion
- [ ] No expression syntax errors
- [ ] All connections use `type: "main"`
- [ ] Error handling per node category
- [ ] `mcp__n8n-mcp__n8n_validate_workflow` passes
- [ ] Patterns consulted from `.claude/patterns/pattern-index.json`

---

## Credentials Registry

| Service | Credential Name | Credential ID | Status |
|---------|-----------------|---------------|--------|
| Google Drive | JayConnor@synrgscaling.com | `TBD` | PRIMARY |
| PostgreSQL | MICROSOFT TEAMS AGENT DATABASE | `NI3jbq1U8xPst3j3` | Active |
| OpenAI | OpenAi account | `6BIzzQu5jAD5jKlH` | Active |
| Gmail | Gmail account 2 | `kHDxu9JVLxm6iyMo` | Active |
| Google Sheets | Google Sheets account | `fzaSSwZ4tI357WUU` | Active |
| Google Docs | Google Docs account | `iNIP35ChYNUUqOCh` | Active |

**Deprecated:** `jlnNh8eZIxWdsvDS` (Autopayplusworkflows@gmail.com) — DO NOT USE

**Pre-deployment:** List required services → match credentials → if missing, ASK USER → confirm.

---

## Current Workflows
- **AI Carousel Generator** — `8bhcEHkbbvnhdHBh`
- **Google Drive Document Repository** — `IamjzfFxjHviJvJg` (needs credential update)
- **File Download & Email Subworkflow** — `z61gjAE9DtszE1u2`

## On-Demand Documentation
- `.claude/ORCHESTRATOR-DETAILS.md` — Delegation examples, agent creation
- `.claude/aio-voice-system.md` — Full AIO architecture, DB schema
- `.claude/skills/n8n-debugging/SKILL.md` — Debugging methodology
- `.claude/patterns/README.md` — Pattern library navigation
