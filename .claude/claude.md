# N8N Workflows - Orchestrator

**Architecture:** Sub-agent delegation | **Pattern Library:** `.claude/patterns/`

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

---

## Validation Criteria

**Valid workflow requires:**
- [ ] All nodes use latest typeVersion
- [ ] No expression syntax errors (= prefix contamination)
- [ ] All connections use `type: "main"`
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
