# Pattern: Hybrid Logging Architecture

> **Priority**: HIGH
>
> **Workflow**: Teams Voice Bot System (Multiple Workflows)
>
> **Date**: 2025-12-28
>
> **Verified**: YES - Implemented across 4 workflows

---

## Overview

A dual-layer logging approach that combines:
1. **Layer 1 (Code Node)**: Immutable, deterministic data capture
2. **Layer 2 (Logging Agent)**: AI-powered semantic enrichment

This architecture ensures logging resilience while adding contextual intelligence.

---

## Problem Statement

Traditional logging approaches face a tradeoff:
- **Code-only logging**: Resilient but lacks semantic understanding
- **AI-only logging**: Rich context but can fail or produce inconsistent results

The hybrid approach provides both resilience AND intelligence.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CALLING WORKFLOW                            │
│  (Orchestrator, Gmail Agent, TTS Agent)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ LAYER 1: Build Immutable Log (Code Node)                  │ │
│  │                                                            │ │
│  │ Captures deterministic data:                               │ │
│  │ - transcript_exact (exact user input)                      │ │
│  │ - agent_output_raw (unmodified agent response)             │ │
│  │ - tool_calls[] (tool name, input, output)                  │ │
│  │ - timestamps (received_at, processed_at, logged_at)        │ │
│  │ - session_id, bot_id                                       │ │
│  │ - classifier_route, classifier_intent                      │ │
│  │ - tts_result (success, audio_sent)                         │ │
│  │ - workflow_source                                          │ │
│  │ - error_flags (agent_error, tts_error, etc.)               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ LAYER 2: Call Logging Agent (Sub-Workflow)                │ │
│  │                                                            │ │
│  │ Adds semantic analysis:                                    │ │
│  │ - intent_semantic (what user actually wants)               │ │
│  │ - conversation_state (greeting, task_in_progress, etc.)    │ │
│  │ - user_satisfaction (positive, neutral, negative)          │ │
│  │ - tool_usage_summary                                       │ │
│  │ - next_action_hint                                         │ │
│  │ - orchestrator_cues (context for next interaction)         │ │
│  │ - escalation_needed (boolean)                              │ │
│  │ - analysis_confidence (high, medium, low)                  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│                              ▼                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Save to Postgres                                           │ │
│  │ (Combined immutable + AI analysis as single log entry)     │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation

### Layer 1: Build Immutable Log (Code Node)

```javascript
// Build immutable log data (Code node layer)
// This captures all deterministic data before AI analysis

const agent = $('Orchestrator Agent').first().json;
const context = $('Build Agent Context').first().json;
const classifier = $('Fast Classifier').first().json;
const ttsResult = $input.item.json || {};

// Extract tool calls from agent output if available
let toolCalls = [];
try {
  if (agent.intermediateSteps) {
    toolCalls = agent.intermediateSteps.map(step => ({
      tool: step.action?.tool || 'unknown',
      input: step.action?.toolInput || {},
      output: step.observation || null
    }));
  }
} catch (e) {
  toolCalls = [];
}

// Build immutable log entry
const immutableLog = {
  transcript_exact: context.user_input || '',
  agent_output_raw: agent.output || '',
  tool_calls: toolCalls,
  timestamps: {
    received_at: context.received_at,
    processed_at: Date.now(),
    logged_at: new Date().toISOString()
  },
  session_id: context.session_id,
  bot_id: context.bot_id,
  classifier_route: classifier.route,
  classifier_intent: classifier.intent,
  tts_result: {
    success: ttsResult.success || false,
    audio_sent: ttsResult.audio_sent || false
  },
  workflow_source: 'orchestrator',
  error_flags: {
    agent_error: !agent.output,
    tts_error: ttsResult.success === false
  }
};

return [immutableLog];
```

### Layer 2: Logging Agent Sub-Workflow

**Workflow ID**: `8LX5tt3SkO8GNuLj`

**Structure**:
```
Workflow Input → Prepare Analysis Prompt → Logging Analysis Agent → Parse & Merge → Return
                                                    │
                                              Gemini Flash (LLM)
```

**AI Analysis Prompt Template**:
```javascript
const analysisPrompt = `Analyze this voice bot interaction and provide contextual insights.

IMMUTABLE DATA:
- Transcript: "${input.transcript_exact || ''}"
- Agent Response: "${input.agent_output_raw || ''}"
- Tool Calls: ${JSON.stringify(input.tool_calls || [])}
- Classifier Route: ${input.classifier_route || 'unknown'}
- Classifier Intent: ${input.classifier_intent || 'unknown'}
- Workflow Source: ${input.workflow_source || 'orchestrator'}
- TTS Sent: ${input.tts_result?.success || false}

Provide your analysis as JSON with these exact fields:
{
  "intent_semantic": "Brief description of what user actually wants (1 sentence)",
  "conversation_state": "one of: greeting, information_request, task_in_progress, task_completed, error_recovery, farewell, unclear",
  "user_satisfaction": "one of: positive, neutral, negative, uncertain",
  "tool_usage_summary": "What tools were called and outcome (1 sentence, or 'none' if no tools)",
  "next_action_hint": "What user might ask next (1 sentence)",
  "orchestrator_cues": "Context summary for next interaction (1-2 sentences)",
  "escalation_needed": false,
  "analysis_confidence": "high, medium, or low"
}

Respond ONLY with valid JSON, no other text.`;
```

---

## Final Log Schema

```json
{
  // Layer 1: Immutable (Code Node)
  "transcript_exact": "Hey bot, send an email to john@example.com",
  "agent_output_raw": "I'll help you send that email. What would you like the subject and message to be?",
  "tool_calls": [],
  "timestamps": {
    "received_at": 1735405200000,
    "processed_at": 1735405201500,
    "logged_at": "2025-12-28T17:00:01.500Z"
  },
  "session_id": "bot123_1735405200000",
  "bot_id": "bot123",
  "classifier_route": "PROCESS",
  "classifier_intent": "email_request",
  "tts_result": { "success": true, "audio_sent": true },
  "workflow_source": "orchestrator",
  "error_flags": { "agent_error": false, "tts_error": false },

  // Layer 2: AI Analysis
  "ai_analysis": {
    "intent_semantic": "User wants to send an email to john@example.com",
    "conversation_state": "task_in_progress",
    "user_satisfaction": "neutral",
    "tool_usage_summary": "No tools used yet - awaiting email content",
    "next_action_hint": "User will provide email subject and body",
    "orchestrator_cues": "Email recipient captured. Need subject and message content to proceed.",
    "escalation_needed": false,
    "analysis_confidence": "high"
  },

  // Metadata
  "log_version": "2.0",
  "logged_at": "2025-12-28T17:00:02.000Z"
}
```

---

## Key Benefits

| Benefit | Layer 1 (Code) | Layer 2 (AI) |
|---------|----------------|--------------|
| **Reliability** | ✅ Always succeeds | ⚠️ Can fail |
| **Speed** | ✅ Instant | ⚠️ ~200-500ms |
| **Consistency** | ✅ Deterministic | ⚠️ May vary |
| **Context** | ❌ Limited | ✅ Rich semantic |
| **Cost** | ✅ Free | ⚠️ LLM tokens |

**Graceful Degradation**: If AI analysis fails, the immutable log is still captured with fallback values.

---

## Workflows Using This Pattern

| Workflow | ID | Implementation |
|----------|-----|----------------|
| Orchestrator | `d3CxEaYk5mkC8sLo` | Build Immutable Log → Call Logging Agent → Save to Postgres |
| Gmail Agent | `kL0AP3CkRby6OmVb` | Build Immutable Log → Call Logging Agent → Return to Orchestrator |
| TTS Agent | `DdwpUSXz7GCZuhlC` | Build Immutable Log → Call Logging Agent → Return to Orchestrator |
| Logging Agent | `8LX5tt3SkO8GNuLj` | Reusable sub-workflow for Layer 2 |

---

## When to Use This Pattern

Use hybrid logging when:
- ✅ You need guaranteed log capture (compliance, debugging)
- ✅ You want semantic understanding of interactions
- ✅ AI failures shouldn't break logging
- ✅ You're building multi-workflow systems

Do NOT use when:
- ❌ Simple single-step workflows
- ❌ Cost-sensitive environments (AI adds token costs)
- ❌ Ultra-low latency requirements (<50ms)

---

## Related Patterns

- [Gmail Tool Configuration](../api-integration/gmail-tool-config.md) - Gmail Tool requires explicit resource/operation
- [AI Agent TypeVersion](./ai-agent-typeversion.md) - Use typeVersion 3 for AI Agents

---

**Date**: 2025-12-28
**Source Workflows**: Teams Voice Bot System
**Verified By**: Implementation across 4 workflows
