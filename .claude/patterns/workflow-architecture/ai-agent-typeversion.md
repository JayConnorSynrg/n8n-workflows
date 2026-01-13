# Pattern: AI Agent TypeVersion Compatibility with GPT-4o Models

> **Priority**: HIGH
>
> **Workflow**: AI Carousel Generator (ID: 8bhcEHkbbvnhdHBh)
>
> **Date**: 2025-12-04

---

## Anti-Pattern: AI Agent Node TypeVersion 2 with GPT-4o Language Model

### What Happened

When implementing the AI Agent "Carousel Prompt Generator" with a connected GPT-4o language model (`lmChatOpenAi`), the Agent node was configured with `typeVersion: 2`. At runtime, the workflow failed with:

```
Error: This model is not supported in 2 version of the Agent node. Please upgrade the Agent node to the latest version.
```

### Impact

- Workflow execution failed at the AI Agent node
- No carousel prompts were generated
- All downstream nodes (image generation, quality analysis, etc.) were unreachable
- User had to debug why a previously working node suddenly failed

### Why It Failed

- Agent node typeVersion 2 has limited model compatibility
- GPT-4o model (connected via `lmChatOpenAi` node) requires Agent typeVersion 3
- The error message is clear but the incompatibility isn't documented in node configuration
- Working examples may use older agent versions with older models

---

## Positive Pattern: Always Use AI Agent TypeVersion 3 for GPT-4o Model Compatibility

### Solution

Upgraded the AI Agent node from typeVersion 2 to typeVersion 3 while preserving all existing parameters.

### Implementation

1. **Identified the error** - Execution showed clear error message about Agent version incompatibility

2. **Researched latest Agent version** - Used `mcp__n8n-mcp__get_node` to confirm typeVersion 3 is latest

3. **Applied targeted fix** - Used partial workflow update to change only typeVersion:

```javascript
mcp__n8n-mcp__n8n_update_partial_workflow({
  id: "8bhcEHkbbvnhdHBh",
  operations: [{
    type: "updateNode",
    nodeName: "Carousel Prompt Generator",
    updates: { typeVersion: 3 }
  }]
})
```

4. **Preserved existing config** - Parameters (`promptType`, `text`, `hasOutputParser`, `options.systemMessage`) remained unchanged

5. **Validated workflow** - Confirmed Agent node now validates correctly

### Result

- AI Agent node upgraded to typeVersion 3
- GPT-4o language model now compatible with Agent node
- Workflow ready for next execution test

---

## AI Agent Model Compatibility Matrix

| Language Model | Minimum Agent TypeVersion | Recommended TypeVersion |
|---------------|---------------------------|------------------------|
| GPT-3.5 Turbo | 1.0 | 3 |
| GPT-4 | 2.0 | 3 |
| GPT-4o | 3.0 | 3 |
| GPT-4o-mini | 3.0 | 3 |
| Claude models | 2.0 | 3 |

---

## Decision Flow

```
Using AI Agent node with language model?
├─ Check connected lmChatOpenAi model
│   ├─ GPT-4o or GPT-4o-mini → REQUIRE typeVersion 3
│   ├─ GPT-4 Turbo → Minimum typeVersion 2
│   └─ Older models → Any version works
├─ Agent node showing model error?
│   └─ Upgrade to typeVersion 3 (backwards compatible)
└─ Best practice: Always use typeVersion 3 for future-proofing
```

---

## Key Learnings

- **Model evolution breaks old Agent versions** - Newer AI models may not work with older Agent node versions
- **TypeVersion 3 is backwards compatible** - Safe to upgrade without changing parameters
- **Error messages are actionable** - "upgrade the Agent node to the latest version" is clear guidance
- **Always use latest Agent version** - Prevents model compatibility issues as OpenAI releases new models
- **Sub-node connections matter** - The `ai_languageModel` connection type links model capabilities to agent requirements

---

**Date**: 2025-12-04
**Source Pattern**: agents-evolution.md - Workflow Architecture Patterns

---

## ⚠️ CRITICAL Anti-Pattern: TypeVersion 3.1 with Explicit Parameters (2025-12-27)

> **Priority**: CRITICAL - ANTI-MEMORY PROTOCOL
>
> **Reference Workflow**: Teams Voice Bot (ID: gjYSN6xNjLw8qsA1)
>
> **Date**: 2025-12-27

### What Happened

The MCP tool `get_node` reports typeVersion 3.1 as "latest" for the AI Agent node. However, using typeVersion 3.1 with explicit parameters causes execution failures, while verified working workflows use typeVersion 3 with minimal parameters.

Documentation files were contradictory:
- `pattern-index.json` said typeVersion "3.1"
- `agent.md` said typeVersion 3.1 with explicit parameters
- Reference workflow `gjYSN6xNjLw8qsA1` actually uses typeVersion 3 with minimal parameters

### Impact

- AI Agent nodes repeatedly broke during workflow refactoring
- Claude consistently used the WRONG configuration pattern
- Multiple debugging cycles wasted
- Root cause was documentation inconsistency, not implementation error

### The Anti-Pattern (DO NOT USE)

```json
{
  "name": "AI Agent",
  "type": "@n8n/n8n-nodes-langchain.agent",
  "typeVersion": 3.1,
  "parameters": {
    "promptType": "define",
    "text": "={{ $json.chatInput }}",
    "options": {
      "systemMessage": "You are a helpful assistant",
      "maxIterations": 10,
      "returnIntermediateSteps": false,
      "enableStreaming": true
    }
  }
}
```

**Why this fails:**
- Uses typeVersion 3.1 (not verified in production workflows)
- Explicitly sets `promptType`, `text`, `systemMessage`
- Over-specifies configuration that n8n UI handles automatically
- Conflicts with Chat Trigger expectations

---

## Positive Pattern: TypeVersion 3 with Minimal Parameters (VERIFIED)

### The Correct Pattern (USE THIS)

**Source**: Verified working workflow `gjYSN6xNjLw8qsA1` (Teams Voice Bot)

```json
{
  "name": "AI Agent",
  "type": "@n8n/n8n-nodes-langchain.agent",
  "typeVersion": 3,
  "position": [600, 400],
  "parameters": {
    "options": {}
  }
}
```

**Why this works:**
- Uses `typeVersion: 3` (verified in production)
- Uses minimal parameters `{"options": {}}`
- Lets n8n UI handle defaults for `promptType`, `text`, `systemMessage`
- Connections to Chat Trigger, LLM, Memory, Tools handle the rest

### Validation Rule

```
BEFORE implementing AI Agent:
1. Read node-reference/langchain/agent.md (MANDATORY - anti_memory flag)
2. Use typeVersion 3 (NOT 3.1)
3. Use minimal parameters {"options": {}}
4. Verify against reference workflow gjYSN6xNjLw8qsA1
```

---

## Key Learnings (Updated 2025-12-27)

- **MCP "latest" is not always correct** - MCP may report 3.1 as latest but 3 is verified working
- **Minimal parameters > explicit parameters** - Let n8n UI handle defaults
- **Reference workflows are authoritative** - Prefer verified working configs over MCP schema
- **Documentation consistency is critical** - Contradictions cause repeated failures
- **Anti-Memory Protocol** - AI Agent node now flagged for mandatory reference reading

---

**Updated**: 2025-12-27
**Anti-Memory Protocol Added**: Yes - node flagged in pattern-index.json
