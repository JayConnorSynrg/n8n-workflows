# OpenAI Audio Node Reference

> **Node Type**: `@n8n/n8n-nodes-langchain.openAi`
> **Latest TypeVersion**: 2.1
> **Last Verified**: 2025-12-28
> **Source**: MCP `get_node` with full detail
> **Resource**: `audio`

---

## Overview

The OpenAI node's audio resource provides:
- **Text-to-Speech (TTS)**: Generate spoken audio from text
- **Transcription**: Convert audio to text
- **Translation**: Translate audio to English text

**Required Credential**: `openAiApi`

---

## Text-to-Speech (TTS)

### Models
| Model | Description |
|-------|-------------|
| `tts-1` | Standard quality, faster |
| `tts-1-hd` | High definition, higher quality |

### Voices
| Voice | Character |
|-------|-----------|
| `alloy` | Neutral, versatile |
| `echo` | Warm, conversational |
| `fable` | Expressive, storytelling |
| `nova` | Bright, energetic |
| `onyx` | Deep, authoritative |
| `shimmer` | Soft, gentle |

### Output Formats
| Format | Use Case |
|--------|----------|
| `mp3` | Universal compatibility (default) |
| `opus` | Streaming, low latency |
| `aac` | Mobile devices |
| `flac` | Lossless, archival |

### Basic TTS Configuration
```json
{
  "name": "Generate Speech",
  "type": "@n8n/n8n-nodes-langchain.openAi",
  "typeVersion": 2.1,
  "parameters": {
    "resource": "audio",
    "operation": "generate",
    "model": "tts-1-hd",
    "input": "={{ $json.text }}",
    "voice": "nova",
    "options": {
      "responseFormat": "mp3",
      "speed": 1
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

### Speed Options
- Range: `0.25` to `4.0`
- Default: `1.0`
- Lower = slower speech
- Higher = faster speech

### High Quality TTS
```json
{
  "parameters": {
    "resource": "audio",
    "operation": "generate",
    "model": "tts-1-hd",
    "input": "={{ $json.text }}",
    "voice": "onyx",
    "options": {
      "responseFormat": "flac",
      "speed": 0.9
    }
  }
}
```

### TTS for Streaming
```json
{
  "parameters": {
    "resource": "audio",
    "operation": "generate",
    "model": "tts-1",
    "input": "={{ $json.text }}",
    "voice": "alloy",
    "options": {
      "responseFormat": "opus"
    }
  }
}
```

---

## Audio Transcription

### Model
| Model | Notes |
|-------|-------|
| `whisper-1` | Only option, high accuracy |

### Configuration
```json
{
  "name": "Transcribe Audio",
  "type": "@n8n/n8n-nodes-langchain.openAi",
  "typeVersion": 2.1,
  "parameters": {
    "resource": "audio",
    "operation": "transcribe",
    "binaryPropertyName": "data",
    "options": {
      "language": "en",
      "temperature": 0,
      "responseFormat": "json"
    }
  }
}
```

### Transcription Options
| Option | Values | Default |
|--------|--------|---------|
| `responseFormat` | json, text, srt, verbose_json, vtt | json |
| `language` | ISO-639-1 code (en, es, fr, etc.) | auto-detect |
| `temperature` | 0-1 | 0 |

### Transcription with Timestamps
```json
{
  "parameters": {
    "resource": "audio",
    "operation": "transcribe",
    "binaryPropertyName": "data",
    "options": {
      "responseFormat": "verbose_json"
    }
  }
}
```

### Transcription to SRT Subtitles
```json
{
  "parameters": {
    "resource": "audio",
    "operation": "transcribe",
    "binaryPropertyName": "data",
    "options": {
      "responseFormat": "srt"
    }
  }
}
```

---

## Audio Translation

Translates audio to English text.

### Configuration
```json
{
  "name": "Translate Audio",
  "type": "@n8n/n8n-nodes-langchain.openAi",
  "typeVersion": 2.1,
  "parameters": {
    "resource": "audio",
    "operation": "translate",
    "binaryPropertyName": "data",
    "options": {
      "temperature": 0
    }
  }
}
```

**Note**: Translation always outputs English text, regardless of source language.

---

## Operations Summary

| Operation | Input | Output |
|-----------|-------|--------|
| `generate` | Text string | Binary audio file |
| `transcribe` | Binary audio file | Text/JSON |
| `translate` | Binary audio file | English text |

---

## Binary Data Handling

### Input (Transcription/Translation)
```javascript
// Binary property name - NO = prefix
"binaryPropertyName": "data"  // CORRECT
"binaryPropertyName": "=data" // WRONG
```

### Output (TTS)
The generated audio is stored in binary data:
```json
{
  "binary": {
    "data": {
      "mimeType": "audio/mpeg",
      "fileName": "speech.mp3",
      "data": "base64-encoded..."
    }
  }
}
```

---

## Common Patterns

### Text-to-Speech Pipeline
```json
{
  "nodes": [
    {
      "name": "Get Text",
      "type": "n8n-nodes-base.set",
      "parameters": {
        "assignments": {
          "assignments": [
            { "name": "text", "value": "Hello, world!", "type": "string" }
          ]
        }
      }
    },
    {
      "name": "Generate Speech",
      "type": "@n8n/n8n-nodes-langchain.openAi",
      "parameters": {
        "resource": "audio",
        "operation": "generate",
        "model": "tts-1-hd",
        "input": "={{ $json.text }}",
        "voice": "nova"
      }
    },
    {
      "name": "Save Audio",
      "type": "n8n-nodes-base.writeBinaryFile",
      "parameters": {
        "fileName": "speech.mp3"
      }
    }
  ]
}
```

### Transcription Pipeline
```json
{
  "nodes": [
    {
      "name": "Read Audio File",
      "type": "n8n-nodes-base.readBinaryFiles",
      "parameters": {
        "fileSelector": "*.mp3"
      }
    },
    {
      "name": "Transcribe",
      "type": "@n8n/n8n-nodes-langchain.openAi",
      "parameters": {
        "resource": "audio",
        "operation": "transcribe",
        "binaryPropertyName": "data",
        "options": {
          "language": "en"
        }
      }
    }
  ]
}
```

### Voice Cloning Alternative (Multiple Voices)
```json
{
  "nodes": [
    {
      "name": "Switch Voice",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "rules": {
          "rules": [
            { "outputKey": "narrator", "conditions": { "value1": "={{ $json.role }}", "operation": "equals", "value2": "narrator" } },
            { "outputKey": "character", "conditions": { "value1": "={{ $json.role }}", "operation": "equals", "value2": "character" } }
          ]
        }
      }
    },
    {
      "name": "Narrator Voice",
      "type": "@n8n/n8n-nodes-langchain.openAi",
      "parameters": {
        "resource": "audio",
        "operation": "generate",
        "voice": "onyx",
        "input": "={{ $json.text }}"
      }
    },
    {
      "name": "Character Voice",
      "type": "@n8n/n8n-nodes-langchain.openAi",
      "parameters": {
        "resource": "audio",
        "operation": "generate",
        "voice": "fable",
        "input": "={{ $json.text }}"
      }
    }
  ]
}
```

---

## Supported Audio Formats (Input)

For transcription and translation:
| Format | Extension |
|--------|-----------|
| FLAC | .flac |
| MP3 | .mp3 |
| MP4 | .mp4 |
| MPEG | .mpeg |
| MPGA | .mpga |
| M4A | .m4a |
| OGG | .ogg |
| WAV | .wav |
| WEBM | .webm |

**Max file size**: 25 MB

---

## Anti-Patterns (AVOID)

### 1. Wrong Binary Property Format
```json
// WRONG
"binaryPropertyName": "=data"

// CORRECT
"binaryPropertyName": "data"
```

### 2. Missing Resource
```json
// WRONG - defaults to text resource
"operation": "generate"

// CORRECT - explicit audio resource
"resource": "audio",
"operation": "generate"
```

### 3. Invalid Voice Name
```json
// WRONG - not a valid voice
"voice": "custom"

// CORRECT - use supported voice
"voice": "nova"  // alloy, echo, fable, nova, onyx, shimmer
```

---

## Validation Checklist

- [ ] Using typeVersion 2.1
- [ ] Resource set to `audio`
- [ ] Operation specified (generate, transcribe, translate)
- [ ] Model specified for TTS (`tts-1` or `tts-1-hd`)
- [ ] Voice is valid option for TTS
- [ ] `binaryPropertyName` has NO `=` prefix
- [ ] Credential reference included
- [ ] Audio file under 25MB for transcription

---

## Related Documentation

- [OpenAI Image](openai-image.md) - Image generation/analysis
- [AI Agent](agent.md) - Agent integration
