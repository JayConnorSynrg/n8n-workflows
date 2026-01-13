# Orchestrator Details - On-Demand Reference

**Purpose:** Detailed orchestrator documentation retrieved by sub-agents on-demand.
**Note:** This file is NOT auto-loaded. Agents read it when needed.

---

## How to Delegate (Task Tool Usage)

```javascript
// Atomic task - use focused agent
Task({
  subagent_type: "general-purpose",  // Claude matches to agent via description
  prompt: "Validate the OpenAI node configuration in workflow 8bhcEHkbbvnhdHBh. Check against patterns in /Users/jelalconnor/CODING/N8N/Workflows/.claude/patterns/",
  model: "haiku"  // Use haiku for focused tasks
})

// Complex task - use expert agent
Task({
  subagent_type: "general-purpose",
  prompt: "[detailed multi-step task]",
  model: "sonnet"
})
```

---

## Agent Auto-Creation Protocol

**When no qualified agent exists for a task:**

1. **Analyze** the task for atomic responsibility
2. **Generate** agent definition using this template:
```yaml
---
name: n8n-{focus-area}
description: Use this agent when {triggers}. Examples: {concrete examples}
tools: Read, Grep, Glob, Bash
model: haiku
---
# Agent prompt with pattern retrieval protocol
```
3. **Write** to `~/.claude/agents/n8n-{focus-area}.md`
4. **Document** creation in `.claude/agents-evolution.md`
5. **Delegate** the original task to the new agent

---

## Project Directory Structure

```
workflows/
├── development/    # WIP workflows
├── production/     # Live workflows
├── library/        # Reusable sub-workflows
└── templates/      # Workflow templates

.claude/
├── patterns/       # LLM-optimized rule library
│   ├── pattern-index.json  # Programmatic lookup
│   └── [categories]/       # Organized patterns
├── agents-evolution.md     # Raw pattern source (128KB - DO NOT LOAD)
├── commands/               # Slash commands
├── ORCHESTRATOR-DETAILS.md # This file (on-demand)
└── CLAUDE.md.full-backup   # Full 830-line documentation backup
```

---

## Full Documentation Reference

When detailed documentation is needed:
- `.claude/CLAUDE.md.full-backup` - Complete 830-line documentation
- `.claude/WORKFLOW-DEVELOPMENT-PROTOCOL.md` - Development process
- `.claude/agents-evolution.md` - All documented patterns (source)
- `.claude/patterns/README.md` - Pattern library navigation

---

## All Available Agents

### N8N Atomic Agents (Focused Tasks)

| Agent | Purpose | Triggers |
|-------|---------|----------|
| `n8n-node-validator` | Validate node configs against schemas | invalid nodes, validation errors |
| `n8n-connection-fixer` | Fix connection syntax and wiring | connection errors, type mismatches |
| `n8n-version-researcher` | Research latest typeVersions | version warnings, outdated nodes |
| `n8n-expression-debugger` | Fix expression syntax issues | expression errors, = prefix issues |
| `n8n-pattern-retriever` | Retrieve patterns from library | any n8n task (support agent) |

### N8N Expert Agent (Complex Tasks)

| Agent | Purpose |
|-------|---------|
| `n8n-workflow-expert` | Multi-step workflow operations, building, optimizing |

### General Agents

| Agent | Purpose |
|-------|---------|
| `full-stack-dev-expert` | General development tasks |
| `agency-automation-expert` | Business automation |
| `fashion-brand-operations` | Fashion brand ops |

**Location:** All agents in `~/.claude/agents/`

---

## MCP Tools Available

### Workflow Operations
- `mcp__n8n-mcp__n8n_get_workflow` - Fetch workflow by ID
- `mcp__n8n-mcp__n8n_update_partial_workflow` - Incremental updates (preferred)
- `mcp__n8n-mcp__n8n_update_full_workflow` - Full workflow replacement
- `mcp__n8n-mcp__n8n_validate_workflow` - Validate structure
- `mcp__n8n-mcp__n8n_autofix_workflow` - Auto-fix common issues

### Node Information
- `mcp__n8n-mcp__get_node` - Get node schema and parameters
- `mcp__n8n-mcp__search_nodes` - Find nodes by keyword
- `mcp__n8n-mcp__validate_node` - Validate node configuration

### Templates
- `mcp__n8n-mcp__search_templates` - Find workflow templates
- `mcp__n8n-mcp__get_template` - Get specific template

---

**Last Updated:** 2025-12-09
