# OpenAI Image Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.openAi`
> **Latest TypeVersion**: 2.1
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail
> **Anti-Memory Protocol**: APPLIES - Known recurring failure point

---

## CRITICAL: Anti-Memory Protocol Active

**DO NOT trust memory for this node configuration.**
**ALWAYS re-read this file before configuring OpenAI image nodes.**

This node has caused repeated failures due to subtle configuration errors.

---

## Overview

The OpenAI node (`@n8n/n8n-nodes-langchain.openAi`) is a multi-resource node supporting:
- **Image**: Generate, analyze, edit images
- **Audio**: TTS, transcription, translation
- **Text**: Completions
- **File**: Upload/manage files
- **Conversation**: Chat completions
- **Video**: Video generation

**Required Credential**: `openAiApi`

---

## Image Resources

### Image Generation

#### Models
| Model | Quality Options | Size Options |
|-------|----------------|--------------|
| `dall-e-2` | N/A | 256x256, 512x512, 1024x1024 |
| `dall-e-3` | standard, hd | 1024x1024, 1792x1024, 1024x1792 |
| `gpt-image-1` | low, medium, high | 1024x1024, 1024x1536, 1536x1024 |

#### GPT Image 1 Configuration (Recommended)
```json
{
  "name": "Generate Image",
  "type": "@n8n/n8n-nodes-langchain.openAi",
  "typeVersion": 2.1,
  "parameters": {
    "resource": "image",
    "prompt": "={{ $json.prompt }}",
    "model": "gpt-image-1",
    "options": {
      "quality": "high",
      "size": "1024x1536"
    }
  },
  "credentials": {
    "openAiApi": {
      "id": "credential-id",
      "name": "OpenAI API"
    }
  }
}
```

#### DALL-E 3 Configuration
```json
{
  "parameters": {
    "resource": "image",
    "prompt": "={{ $json.prompt }}",
    "model": "dall-e-3",
    "options": {
      "quality": "hd",
      "size": "1024x1024",
      "style": "vivid"
    }
  }
}
```

**DALL-E 3 Style Options**: `vivid`, `natural`

---

### Image Analysis (Vision)

#### Models
| Model | Notes |
|-------|-------|
| `gpt-4o` | Recommended, best quality |
| `gpt-4o-mini` | Faster, cost-effective |
| `gpt-4-turbo` | Legacy |

#### Configuration - COPY EXACTLY
```json
{
  "name": "Analyze Image",
  "type": "@n8n/n8n-nodes-langchain.openAi",
  "typeVersion": 2.1,
  "parameters": {
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
}
```

#### Input Types
| Type | Parameter | Description |
|------|-----------|-------------|
| `base64` | `binaryPropertyName` | Binary data from previous node |
| `url` | `imageUrl` | URL to image |

#### Detail Options
| Detail | Description |
|--------|-------------|
| `auto` | Let API decide |
| `low` | Faster, less detail |
| `high` | Full resolution analysis |

---

### Image Edit

```json
{
  "parameters": {
    "resource": "image",
    "operation": "edit",
    "model": "gpt-image-1",
    "prompt": "={{ $json.edit_instruction }}",
    "inputType": "base64",
    "binaryPropertyName": "data",
    "options": {
      "size": "1024x1024"
    }
  }
}
```

---

## Critical Parameter Rules

| Parameter Type | CORRECT | WRONG | Reason |
|---------------|---------|-------|--------|
| Binary property name | `"data"` | `"=data"` | Property names are NOT expressions |
| Dynamic expression | `"={{ $json.field }}"` | `"$json.field"` | Expressions need `={{ }}` |
| Static enum | `"high"` | `"={{ 'high' }}"` | Enums don't need expressions |
| ResourceLocator | `{ "__rl": true, "value": "gpt-4o" }` | `"gpt-4o"` | Must use object format for modelId |
| Model (generation) | `"gpt-image-1"` (string) | ResourceLocator | Generation uses string model |

---

## TypeVersion Rules

| Use Case | typeVersion | operation | model format |
|----------|-------------|-----------|--------------|
| Image Generation | `2.1` | **OMIT** (default) | String: `"gpt-image-1"` |
| Image Analysis | `2.1` | `"analyze"` | ResourceLocator format |
| Image Edit | `2.1` | `"edit"` | String: `"gpt-image-1"` |

---

## Size Options by Model

### GPT Image 1
| Size | Orientation |
|------|-------------|
| `1024x1024` | Square |
| `1024x1536` | Portrait |
| `1536x1024` | Landscape |

### DALL-E 3
| Size | Orientation |
|------|-------------|
| `1024x1024` | Square |
| `1792x1024` | Landscape |
| `1024x1792` | Portrait |

### DALL-E 2
| Size | Notes |
|------|-------|
| `256x256` | Small |
| `512x512` | Medium |
| `1024x1024` | Large |

---

## Quality Options

### GPT Image 1
| Quality | Description |
|---------|-------------|
| `high` | Best quality, slower |
| `medium` | Balanced |
| `low` | Fastest, lower quality |

### DALL-E 3
| Quality | Description |
|---------|-------------|
| `hd` | Higher detail |
| `standard` | Default quality |

---

## Anti-Patterns (MEMORIZE THESE)

### 1. Expression Prefix on Property Names
```json
// WRONG - Breaks binary data flow
"binaryPropertyName": "=data"

// CORRECT - Static property name
"binaryPropertyName": "data"
```

### 2. Wrong Operation Default
```json
// WRONG for generation - generate is implicit default
"operation": "generate"

// CORRECT - Omit operation for generation
// (no operation parameter)
```

### 3. String Instead of ResourceLocator for Analysis
```json
// WRONG for analysis
"modelId": "gpt-4o"

// CORRECT - ResourceLocator format
"modelId": {
  "__rl": true,
  "value": "gpt-4o",
  "mode": "list"
}
```

### 4. ResourceLocator for Generation Model
```json
// WRONG for generation
"model": { "__rl": true, "value": "gpt-image-1" }

// CORRECT - String format for generation
"model": "gpt-image-1"
```

---

## Output Structure

### Generation Output
```json
{
  "url": "https://...",
  "binary": {
    "data": {
      "mimeType": "image/png",
      "data": "base64-encoded..."
    }
  }
}
```

### Analysis Output
```json
{
  "text": "The image shows...",
  "model": "gpt-4o",
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 200
  }
}
```

---

## Common Patterns

### Generate Then Analyze
```json
{
  "nodes": [
    {
      "name": "Generate Image",
      "type": "@n8n/n8n-nodes-langchain.openAi",
      "parameters": {
        "resource": "image",
        "model": "gpt-image-1",
        "prompt": "={{ $json.prompt }}"
      }
    },
    {
      "name": "Analyze Image",
      "type": "@n8n/n8n-nodes-langchain.openAi",
      "parameters": {
        "resource": "image",
        "operation": "analyze",
        "modelId": { "__rl": true, "value": "gpt-4o", "mode": "list" },
        "text": "Describe this image",
        "inputType": "base64",
        "binaryPropertyName": "data"
      }
    }
  ]
}
```

---

## Validation Checklist

Before deploying OpenAI image nodes:
- [ ] Read this file (do not trust memory)
- [ ] Copy reference template exactly
- [ ] Verify `binaryPropertyName` has NO `=` prefix
- [ ] Confirm `modelId` uses ResourceLocator format (for analysis)
- [ ] Check model uses string format (for generation)
- [ ] Verify typeVersion is `2.1`
- [ ] Credential reference included
- [ ] Run MCP validation:

```javascript
mcp__n8n-mcp__validate_node({
  nodeType: "@n8n/n8n-nodes-langchain.openAi",
  config: { /* your config */ },
  mode: "full"
});
```

---

## Related Documentation

- [OpenAI Audio](openai-audio.md) - TTS, transcription, translation
- [AI Agent](agent.md) - Agent integration
- `.claude/patterns/api-integration/openai-image-nodes.md` - Full pattern documentation
