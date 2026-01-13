# Pattern: OpenAI Image Node Configuration

> **Priority**: HIGH - Known failure point, apply Anti-Memory Protocol
>
> **Workflow**: AI Carousel Generator (ID: 8bhcEHkbbvnhdHBh)
>
> **Date**: 2025-12-10 (updated)
> **Last Verified**: 2025-12-10

---

## Anti-Pattern: Expression Prefix Contamination in Binary Property Names

### What Happened

When configuring the native OpenAI image analysis node (`@n8n/n8n-nodes-langchain.openAi`), the `binaryPropertyName` parameter was set to `"=data"` instead of the correct `"data"`. This erroneous `=` prefix was introduced during workflow updates.

### Root Cause Analysis

1. In n8n expressions, the `=` prefix denotes a dynamic expression (e.g., `={{ $json.field }}`)
2. For static string values like `binaryPropertyName`, the value should be a plain string: `"data"`
3. The contamination happened when copying expression patterns across different parameter types
4. Similar issue: Text prompts can have `=` prefix for expressions, but property names cannot

### Impact

- Binary data flow completely broken - image analysis node couldn't find the binary data
- Image quality analysis returned errors or empty results
- Required multiple debug cycles to identify the subtle `=` prefix issue
- Pattern of this error repeated across conversations despite documentation

### Why It Failed

- Memory-based implementation without re-reading reference documentation
- Pattern contamination from adjacent expression-based parameters
- The `=` prefix is valid for some parameters but breaks others
- Subtle difference between `"data"` and `"=data"` is easy to miss

---

## Positive Pattern: OpenAI Native Image Node Configuration Checklist

### Reference Templates (COPY EXACTLY)

**Image Generation - GPT Image 1 (typeVersion: 2):**

> ⚠️ **CRITICAL**: Do NOT include `"operation": "generate"` - image generation is the DEFAULT behavior for `resource: "image"` with typeVersion 2. Adding it will break the node.

Portrait (1024x1536):
```json
{
  "resource": "image",
  "model": "gpt-image-1",
  "prompt": "={{ $json.current_prompt }}",
  "options": {
    "quality": "high",
    "size": "1024x1536"
  }
}
```

Square (1024x1024):
```json
{
  "resource": "image",
  "model": "gpt-image-1",
  "prompt": "={{ $json.current_prompt }}",
  "options": {
    "quality": "high",
    "size": "1024x1024"
  }
}
```

Landscape (1536x1024):
```json
{
  "resource": "image",
  "model": "gpt-image-1",
  "prompt": "={{ $json.current_prompt }}",
  "options": {
    "quality": "high",
    "size": "1536x1024"
  }
}
```

**Node Configuration:**
- **typeVersion**: 2 (REQUIRED - do NOT use 2.1 for image generation)
- **model**: `"gpt-image-1"` (plain string, NOT ResourceLocator)
- **operation**: OMIT entirely for generation (it's the default)

**Image Analysis - GPT-4o Vision:**
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
  "text": "={{ $json.quality_prompt }}",
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

| Parameter Type | CORRECT | WRONG | Reason |
|---------------|---------|-------|--------|
| Static string (property name) | `"data"` | `"=data"` | Property names are NOT expressions |
| Dynamic expression | `"={{ $json.field }}"` | `"$json.field"` | Expressions need `={{ }}` wrapper |
| Enum value | `"high"` | `"={{ 'high' }}"` | Static enums don't need expressions |
| ResourceLocator | `{ "__rl": true, "value": "...", "mode": "list" }` | `"gpt-4o"` | Must use object format |

### The Critical Rule

```
❌ binaryPropertyName: "=data"   ← BREAKS binary data flow
✅ binaryPropertyName: "data"    ← CORRECT - static property name
```

---

## GPT Image 1 Model Specifics

**Quality Options:**
- `"high"` - Best quality, slower
- `"medium"` - Balanced
- `"low"` - Fastest, lower quality

**Note**: NOT `"hd"` / `"standard"` like DALL-E 3

**Size Options:**
- `"1024x1024"` - Square
- `"1024x1536"` - Portrait
- `"1536x1024"` - Landscape

---

## Validation Before Implementation

**ALWAYS run this before applying configuration:**

```javascript
mcp__n8n-mcp__validate_node({
  nodeType: "@n8n/n8n-nodes-langchain.openAi",
  config: { /* your config */ },
  mode: "full"
});
```

---

## Checklist Before Configuring OpenAI Image Nodes

- [ ] Read this pattern file (do not trust memory)
- [ ] Copy reference template exactly
- [ ] Verify `binaryPropertyName` has NO `=` prefix
- [ ] Confirm `modelId` uses ResourceLocator format (`__rl: true`)
- [ ] Check all static values are plain strings (NOT expressions)
- [ ] Verify expression values use `={{ }}` syntax
- [ ] Run MCP validation before deployment

---

## Result After Applying Pattern

- Workflow version 48+ deployed with correct configurations
- `binaryPropertyName` fixed from `"=data"` to `"data"`
- Added `simplify: true` for cleaner analysis output
- Binary data now flows correctly to image analysis
- Quality scores accurately reflect actual image analysis

---

## 2025-12-10 Update: CRITICAL typeVersion Correction

**Issue**: Previous documentation incorrectly specified typeVersion 2.1 with `operation: "generate"`. This is WRONG.

**Root Cause Analysis**:
- typeVersion 2.1 with explicit `operation: "generate"` creates BROKEN nodes
- typeVersion 2 WITHOUT `operation` parameter is the CORRECT working format
- The `operation` parameter should only be used for `analyze` (image analysis), not generation

**CORRECT Working Configuration** (verified from live workflow):
```json
{
  "name": "Generate an image",
  "type": "@n8n/n8n-nodes-langchain.openAi",
  "typeVersion": 2,
  "parameters": {
    "resource": "image",
    "model": "gpt-image-1",
    "prompt": "={{ $json.current_prompt }}{{ $json.slide_purpose }}{{ $json.description }}{{ $json.visual_elements }}{{ $json.style_description }}",
    "options": {
      "quality": "high",
      "size": "1024x1024"
    }
  }
}
```

**Key Differences Table:**

| Attribute | ❌ WRONG | ✅ CORRECT |
|-----------|----------|------------|
| `typeVersion` | 2.1 | **2** |
| `operation` | `"generate"` | **OMIT entirely** |

**Why This Matters**:
- For `resource: "image"` with typeVersion 2, generation is the DEFAULT behavior
- Explicitly adding `operation: "generate"` causes node misconfiguration
- Only use `operation: "analyze"` when doing image analysis (different use case)

---

**Date**: 2025-12-10
**Source Pattern**: Live workflow verification after failed deployment
**Anti-Memory Protocol**: APPLIES - Known recurring failure point
