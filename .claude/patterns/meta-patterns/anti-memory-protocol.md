# Meta-Pattern: Anti-Memory Protocol

> **Priority**: HIGH - Apply to prevent recurring configuration errors
>
> **Context**: Claude has documented patterns of repeatedly misconfiguring nodes despite having correct configurations documented
>
> **Root Cause**: FALSE CONFIDENCE LOOP - memory degradation between conversations

---

## The Problem: False Confidence Loop

```
Success → "I know this" → Skip validation → Memory degrades →
Error → Fix → Document → New context → "I know this" → REPEAT
```

**Evidence from AI Carousel Generator (8bhcEHkbbvnhdHBh):**

| Date | Issue | Status |
|------|-------|--------|
| 2025-11-22 | Wrong node types assumed | Fixed, documented |
| 2025-11-27 | TypeVersion mismatches | Fixed, documented |
| 2025-12-04 | binaryPropertyName: "=data" | Fixed, documented |

Same workflow, same node types, same mistakes - despite prior documentation.

---

## The Protocol: DO NOT TRUST MEMORY

### Mandatory Steps Before Configuring ANY Known Failure Point

```
┌─────────────────────────────────────────────────────────────┐
│  STOP - DO NOT IMPLEMENT FROM MEMORY                        │
│                                                             │
│  Even if you think you know the configuration, you don't.  │
│  Memory degrades between conversations. Documentation      │
│  doesn't. READ THE REFERENCE FIRST.                        │
└─────────────────────────────────────────────────────────────┘
```

### Step 1: STOP
Recognize the pattern is in the Known Failure Points registry

### Step 2: READ
Fetch the documented reference template from:
- `.claude/patterns/` (this directory)
- `.claude/CLAUDE.md` (project instructions)
- MCP tools (authoritative source)

### Step 3: COPY
Use exact syntax from reference - do not reconstruct from memory

### Step 4: VALIDATE
```javascript
mcp__n8n-mcp__validate_node({
  nodeType: "@n8n/n8n-nodes-langchain.openAi",
  config: { /* your config */ },
  mode: "full"
});
```

### Step 5: VERIFY
Check output confirms expected behavior

---

## Known Failure Points Registry

### OpenAI Image Nodes (`@n8n/n8n-nodes-langchain.openAi`)

**Image Generation Reference:**
```json
{
  "resource": "image",
  "operation": "generate",
  "model": "gpt-image-1",
  "prompt": "={{ $json.prompt_field }}",
  "options": {
    "quality": "high",
    "size": "1024x1536"
  }
}
```

**Image Analysis Reference:**
```json
{
  "resource": "image",
  "operation": "analyze",
  "modelId": {
    "__rl": true,
    "value": "gpt-4o",
    "mode": "list",
    "cachedResultName": "GPT-4O"
  },
  "text": "={{ $json.analysis_prompt }}",
  "inputType": "base64",
  "binaryPropertyName": "data",
  "simplify": true,
  "options": {
    "detail": "high",
    "maxTokens": 1000
  }
}
```

### Critical Parameter Rules

| Parameter | CORRECT | WRONG | Why |
|-----------|---------|-------|-----|
| `binaryPropertyName` | `"data"` | `"=data"` | Static property name, NOT expression |
| `modelId` | `{ "__rl": true, "value": "gpt-4o", "mode": "list" }` | `"gpt-4o"` | ResourceLocator format required |
| `prompt` (generation) | `"={{ $json.field }}"` | `"$json.field"` | Expression needs `={{ }}` wrapper |
| `text` (analysis) | `"={{ $json.field }}"` | `"$json.field"` | Expression needs `={{ }}` wrapper |
| `model` (generation) | `"gpt-image-1"` | `"={{ 'gpt-image-1' }}"` | Static enum, not expression |

### The One Mistake You Keep Making

```
❌ binaryPropertyName: "=data"   ← WRONG (breaks binary data flow)
✅ binaryPropertyName: "data"    ← CORRECT
```

The `=` prefix means "evaluate as expression" in n8n. Property names are NOT expressions.

---

## When to Apply This Protocol

Apply when configuring ANY of these:

- [ ] OpenAI image generation nodes
- [ ] OpenAI image analysis nodes
- [ ] Any node type that has failed 2+ times despite documentation
- [ ] Any configuration involving binary data properties
- [ ] Any configuration involving ResourceLocator format

---

## Why This Protocol Exists

**Memory is unreliable for precise technical configurations.**

Each conversation starts fresh. Documentation doesn't degrade. The solution is not to try harder to remember, but to build systems that assume memory failure and compensate with mandatory reference reading.

---

## Enforcement

- ❌ NEVER implement known failure point nodes without reading this section first
- ❌ NEVER skip validation step
- ❌ NEVER assume memory is correct
- ✅ ALWAYS copy from reference templates
- ✅ ALWAYS validate before applying
- ✅ ALWAYS re-read this section even if you "remember" the configuration

---

**Date**: 2025-12-04
**Source Pattern**: agents-evolution.md - Meta-Pattern: Claude Memory Degradation and False Confidence
