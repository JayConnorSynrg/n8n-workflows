# Google Gemini Chat Model Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.lmChatGoogleGemini`
> **Latest TypeVersion**: 1
> **Last Verified**: 2025-12-27
> **Source**: MCP `get_node` with full detail

---

## Overview

Google Gemini model integration for AI chains and agents. Supports all current Gemini models via dynamic API loading.

**Required Credential**: `googlePalmApi`

---

## Model Selection

- **Default**: `models/gemini-2.5-flash`
- **Options**: Dynamically loaded from Google API (`/v1beta/models`)
- **Filter**: Excludes embedding models automatically

---

## Core Parameters

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `modelName` | options | gemini-2.5-flash | dynamic | Model selection |
| `maxOutputTokens` | number | 2048 | - | Max tokens to generate |
| `temperature` | number | 0.4 | 0-1 | Randomness (lower=deterministic) |
| `topK` | number | 32 | -1 to 40 | Long-tail filter (-1=disabled) |
| `topP` | number | 1 | 0-1 | Nucleus sampling |

---

## Safety Settings

**Categories**:
- `HARM_CATEGORY_HARASSMENT`
- `HARM_CATEGORY_HATE_SPEECH`
- `HARM_CATEGORY_SEXUALLY_EXPLICIT`
- `HARM_CATEGORY_DANGEROUS_CONTENT`

**Thresholds**:
- `HARM_BLOCK_THRESHOLD_UNSPECIFIED` (default)
- `BLOCK_LOW_AND_ABOVE` (allows NEGLIGIBLE)
- `BLOCK_MEDIUM_AND_ABOVE` (allows NEGLIGIBLE + LOW)
- `BLOCK_ONLY_HIGH` (allows NEGLIGIBLE + LOW + MEDIUM)
- `BLOCK_NONE` (all content allowed)

---

## Reference Configuration

```json
{
  "name": "Gemini Chat",
  "type": "@n8n/n8n-nodes-langchain.lmChatGoogleGemini",
  "typeVersion": 1,
  "parameters": {
    "modelName": "models/gemini-2.5-flash",
    "options": {
      "maxOutputTokens": 2048,
      "temperature": 0.4,
      "topK": 32,
      "topP": 1,
      "safetySettings": {
        "values": [
          {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
          }
        ]
      }
    }
  },
  "credentials": {
    "googlePalmApi": "CREDENTIAL_ID"
  }
}
```

---

## Critical Rules

1. **AI Chain Required**: Must connect to downstream AI chain node
2. **AI Tool Capable**: Requires `N8N_COMMUNITY_PACKAGES_ALLOW_TOOL_USAGE=true`
3. **Safety by Default**: Includes harassment category with unspecified threshold
4. **Dynamic Model Loading**: Models list updates from Google API automatically
