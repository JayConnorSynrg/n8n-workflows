# Groq LLM Plugin Integration Pattern

**Pattern ID**: `voice-agents/groq-llm-plugin`
**Category**: Voice Agent LLM Integration
**Severity**: CRITICAL
**Created**: 2026-01-17
**Source**: Voice Agent POC debugging session

---

## Overview

Groq provides ultra-low latency LLM inference (~200ms TTFT) ideal for voice agents. This pattern documents the correct integration approach using the official LiveKit plugin.

---

## CRITICAL: Use Official Plugin Only

### Anti-Pattern: Custom GroqLLM Class

**DO NOT** create custom Groq LLM implementations:

```python
# ANTI-PATTERN - WILL FAIL
from groq import AsyncGroq
from livekit.agents import llm

class GroqLLM(llm.LLM):
    def chat(self, *, chat_ctx, ...):
        return GroqLLMStream(...)

class GroqLLMStream(llm.LLMStream):
    # This will fail with:
    # "TypeError: Can't instantiate abstract class GroqLLMStream
    # with abstract method _run"
    pass
```

### Why Custom Implementations Fail

1. **Abstract Method**: `llm.LLMStream` requires `_run` method implementation
2. **Sync/Async Contract**: `chat()` must be sync, returning async context manager
3. **Parameter Evolution**: New parameters added frequently (`conn_options`, etc.)
4. **Streaming Complexity**: Proper chunking and tool call handling is complex

### Correct Pattern: Official Plugin

```python
# CORRECT - Use livekit-plugins-groq
from livekit.plugins import groq

llm_instance = groq.LLM(
    model="llama-3.1-8b-instant",  # Fastest Groq model
    api_key=settings.groq_api_key,
    temperature=0.7,
)
```

---

## Requirements

```
# In requirements.txt
livekit-plugins-groq>=1.0.0,<2.0.0
```

**Note**: This replaces raw `groq>=0.9.0` dependency.

---

## Configuration

### Pydantic Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Groq configuration
    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"
    groq_temperature: float = 0.7
    groq_max_tokens: int = 256

    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra env vars
```

### Environment Variables

```env
GROQ_API_KEY=gsk_your_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
GROQ_TEMPERATURE=0.7
```

---

## Model Selection

### Recommended Models for Voice

| Model | TTFT | Use Case |
|-------|------|----------|
| `llama-3.1-8b-instant` | ~200ms | **Recommended** - Best latency |
| `llama-3.1-70b-versatile` | ~400ms | Complex reasoning needed |
| `mixtral-8x7b-32768` | ~300ms | Long context needed |

### Voice Agent Optimization

For voice agents, prioritize **latency over capability**:
- Use `llama-3.1-8b-instant` for fastest response
- Keep `max_tokens` low (256) for shorter responses
- Use `temperature=0.7` for natural but focused responses

---

## Tool Integration

### Defining Tools

```python
from livekit.agents import llm

send_email_tool = llm.FunctionTool(
    name="send_email",
    description="Send an email to a recipient",
    parameters={
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body"},
        },
        "required": ["to", "subject", "body"],
    },
    coroutine=execute_send_email,
)

agent = Agent(
    instructions=SYSTEM_PROMPT,
    tools=[send_email_tool],
)
```

### Tool Execution Pattern

```python
async def execute_send_email(to: str, subject: str, body: str) -> str:
    """Execute the email sending via n8n webhook."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.n8n_webhook_base}/send-email",
                json={"to": to, "subject": subject, "body": body},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    return "Email sent successfully"
                else:
                    return f"Failed to send email: {response.status}"
    except Exception as e:
        logger.error(f"Email tool error: {e}")
        return "I encountered an error sending the email"
```

---

## Debugging Journey

### Error Progression (From Commits)

| Error | Commit | Fix |
|-------|--------|-----|
| `got unexpected keyword argument 'tool_choice'` | 8d2f7e2 | Added tool_choice param |
| `got unexpected keyword argument 'conn_options'` | 85fefba | Added conn_options param |
| `coroutine object does not support async context manager` | b893746 | Added __aenter__/__aexit__ |
| `coroutine object does not support async context manager` | 1af6283 | Changed chat() to sync def |
| `Can't instantiate abstract class with abstract method _run` | d1e2a93 | **Switched to official plugin** |

### Lesson Learned

Each fix revealed another API requirement. The official plugin handles all of these internally.

---

## Performance Characteristics

### Groq LPU Inference

- **TTFT**: ~200ms (Time to First Token)
- **Throughput**: ~500 tokens/second
- **Concurrent Requests**: High capacity

### Voice Agent Impact

```
User speaks → VAD → STT (~500ms) → Groq LLM (~200ms) → TTS (~200ms) → Audio out
                                    ^^^^^^^^
                                    Critical path
```

Total perceived latency: ~1-1.5 seconds (excellent for voice)

---

## Error Handling

### Graceful Degradation

```python
@session.on("agent_state_changed")
def on_agent_state_changed(ev):
    state = str(ev.new_state).lower()
    if "error" in state:
        # LLM error - provide fallback response
        asyncio.create_task(session.say(
            "I'm having trouble processing that. Could you repeat it?"
        ))
```

### API Errors

The official plugin handles:
- Rate limiting with backoff
- Network timeouts
- Invalid responses
- Authentication errors

---

## System Prompt Optimization

### Voice-Optimized Prompt

```python
SYSTEM_PROMPT = """You are a professional voice assistant.

## RESPONSE GUIDELINES
- Keep responses under 2 sentences
- Use contractions (I'll, we're, that's)
- Speak naturally, not like reading
- If unclear, ask for clarification

## TOOL USAGE
- Always confirm before executing actions
- Announce when actions complete
- Never expose technical errors
"""
```

### Why Short Prompts

- Faster processing (fewer input tokens)
- More consistent behavior
- Lower API costs

---

## Migration Guide

### From Custom Implementation

```python
# Before (custom - broken)
from groq import AsyncGroq
llm_instance = GroqLLM(model="...", api_key="...")

# After (official plugin - works)
from livekit.plugins import groq
llm_instance = groq.LLM(model="...", api_key="...")
```

### Requirements Change

```
# Before
groq>=0.9.0

# After
livekit-plugins-groq>=1.0.0,<2.0.0
```

---

## Related Patterns

- `voice-agents/livekit-agents-1.3.x` - Overall integration patterns
- `voice-agents/vad-tuning-recall-ai` - Audio pipeline tuning

---

## Anti-Memory Flag

**ALWAYS use the official plugin.** Do not attempt custom LLM implementations regardless of prior experience. The API contract changes frequently.
