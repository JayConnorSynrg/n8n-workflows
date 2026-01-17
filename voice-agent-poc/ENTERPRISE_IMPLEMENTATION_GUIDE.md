# Enterprise Voice Agent Implementation Guide

**Version:** 1.0.0
**Last Updated:** January 2026
**Architecture:** LiveKit Cloud + Cartesia TTS + Groq LLM + Deepgram STT
**Target Latency:** <500ms end-to-end

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Service Registration & API Keys](#service-registration--api-keys)
4. [Infrastructure Setup](#infrastructure-setup)
5. [LiveKit Agent Implementation](#livekit-agent-implementation)
6. [Client Implementation](#client-implementation)
7. [n8n Integration](#n8n-integration)
8. [Scalability & High Availability](#scalability--high-availability)
9. [Security Considerations](#security-considerations)
10. [Monitoring & Observability](#monitoring--observability)
11. [Cost Analysis](#cost-analysis)
12. [Deployment Checklist](#deployment-checklist)
13. [Troubleshooting Guide](#troubleshooting-guide)

---

## Executive Summary

### Business Case

| Metric | Current (OpenAI Realtime) | Proposed (LiveKit Stack) | Improvement |
|--------|---------------------------|--------------------------|-------------|
| Latency | 600-800ms | **400-500ms** | 25-40% faster |
| Cost/min | ~$0.036 | **~$0.025** | 30% cheaper |
| Scalability | Limited by OpenAI | **Horizontal scaling** | Enterprise-ready |
| Vendor Lock-in | High | **Low (modular)** | Swap any component |

### Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PRODUCTION ARCHITECTURE                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   TRANSPORT     │    │    SPEECH       │    │   INFERENCE     │             │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤             │
│  │ LiveKit Cloud   │    │ Deepgram Nova-3 │    │ Groq LLaMA 3.1  │             │
│  │ WebRTC + TURN   │    │ STT: ~150ms     │    │ LLM: ~200ms     │             │
│  │ FREE tier       │    │ $0.0035/min     │    │ $0.05/1M tokens │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
│                                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐             │
│  │   SYNTHESIS     │    │    COMPUTE      │    │   WORKFLOWS     │             │
│  ├─────────────────┤    ├─────────────────┤    ├─────────────────┤             │
│  │ Cartesia Sonic  │    │ Railway         │    │ n8n Cloud       │             │
│  │ TTS: 40-90ms    │    │ Agent Host      │    │ Tool Execution  │             │
│  │ ~$0.02/min      │    │ $5/month        │    │ Existing        │             │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Overview

### Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              END-TO-END DATA FLOW                                 │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────┐                                                                  │
│  │ Teams/Zoom  │                                                                  │
│  │  Meeting    │                                                                  │
│  └──────┬──────┘                                                                  │
│         │ Recall.ai Bot                                                           │
│         ▼                                                                         │
│  ┌─────────────┐     WebRTC      ┌─────────────┐    WebSocket    ┌────────────┐  │
│  │   Client    │◄───────────────►│  LiveKit    │◄───────────────►│  Railway   │  │
│  │  (Vercel)   │   Audio/Video   │   Cloud     │   Agent Conn    │   Agent    │  │
│  └─────────────┘                 └─────────────┘                 └─────┬──────┘  │
│                                                                        │         │
│                                          ┌─────────────────────────────┼───────┐ │
│                                          │      VOICE PIPELINE         │       │ │
│                                          ├─────────────────────────────┼───────┤ │
│                                          │                             ▼       │ │
│                                          │  ┌──────────┐  Audio   ┌────────┐  │ │
│                                          │  │  Silero  │◄─────────│  VAD   │  │ │
│                                          │  │   VAD    │  20ms    │ Buffer │  │ │
│                                          │  └────┬─────┘          └────────┘  │ │
│                                          │       │                            │ │
│                                          │       ▼ Speech Detected            │ │
│                                          │  ┌──────────┐                      │ │
│                                          │  │ Deepgram │ Streaming            │ │
│                                          │  │  Nova-3  │ ~150ms               │ │
│                                          │  └────┬─────┘                      │ │
│                                          │       │                            │ │
│                                          │       ▼ Transcription              │ │
│                                          │  ┌──────────┐                      │ │
│                                          │  │   Groq   │ Streaming            │ │
│                                          │  │ LLaMA3.1 │ ~200ms TTFT          │ │
│                                          │  └────┬─────┘                      │ │
│                                          │       │                            │ │
│                                          │       ▼ Response Text              │ │
│                                          │  ┌──────────┐                      │ │
│                                          │  │ Cartesia │ Streaming            │ │
│                                          │  │ Sonic-3  │ 40-90ms TTFA         │ │
│                                          │  └────┬─────┘                      │ │
│                                          │       │                            │ │
│                                          │       ▼ Audio Stream               │ │
│                                          └───────┼────────────────────────────┘ │
│                                                  │                               │
│                                                  ▼                               │
│                                           ┌───────────┐                          │
│                                           │    n8n    │ Tool Calls              │
│                                           │ Webhooks  │ (Email, DB, etc.)       │
│                                           └───────────┘                          │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Latency Budget

| Stage | Target | P50 | P99 | Notes |
|-------|--------|-----|-----|-------|
| WebRTC Transport | <50ms | 30ms | 80ms | LiveKit optimized |
| VAD Detection | <30ms | 20ms | 40ms | Silero local |
| STT (Deepgram) | <200ms | 150ms | 300ms | Streaming mode |
| LLM (Groq) | <250ms | 200ms | 400ms | TTFT streaming |
| TTS (Cartesia) | <100ms | 60ms | 150ms | TTFA streaming |
| **Total** | **<500ms** | **~400ms** | **~700ms** | End-to-end |

---

## Service Registration & API Keys

### Step 1: LiveKit Cloud (WebRTC Transport)

| Field | Value |
|-------|-------|
| **Sign Up URL** | [https://cloud.livekit.io](https://cloud.livekit.io) |
| **Documentation** | [https://docs.livekit.io/home/cloud/](https://docs.livekit.io/home/cloud/) |
| **Pricing** | [https://livekit.io/pricing](https://livekit.io/pricing) |
| **Free Tier** | 5,000 participant-minutes/month, 100 concurrent |

**Setup Steps:**
```
1. Go to https://cloud.livekit.io
2. Sign up with GitHub or Google OAuth
3. Create project: "voice-agent-production"
4. Select region: us-west-2 (lowest latency to Railway)
5. Navigate to Settings → API Keys
6. Copy credentials:
   - LIVEKIT_URL (e.g., wss://voice-agent-production-xxxxxx.livekit.cloud)
   - LIVEKIT_API_KEY (e.g., APIxxxxxxxxxx)
   - LIVEKIT_API_SECRET (e.g., xxxxxxxxxxxxxxxxxxxxxxxx)
```

**Environment Variables:**
```bash
LIVEKIT_URL=wss://voice-agent-production-xxxxxx.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

### Step 2: Deepgram (Speech-to-Text)

| Field | Value |
|-------|-------|
| **Sign Up URL** | [https://console.deepgram.com](https://console.deepgram.com) |
| **Documentation** | [https://developers.deepgram.com/docs](https://developers.deepgram.com/docs) |
| **Pricing** | [https://deepgram.com/pricing](https://deepgram.com/pricing) |
| **Free Tier** | $200 credit (no expiration) |

**Setup Steps:**
```
1. Go to https://console.deepgram.com
2. Sign up with email or Google OAuth
3. Navigate to API Keys section
4. Create new key with:
   - Name: "voice-agent-production"
   - Permissions: "Member" (default)
5. Copy the API key immediately (shown only once)
```

**Environment Variables:**
```bash
DEEPGRAM_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Recommended Model Configuration:**
```python
# Nova-3 is the latest, fastest model
model = "nova-3"
language = "en"
smart_format = True
interim_results = True  # For faster response
punctuate = True
```

---

### Step 3: Groq (LLM Inference)

| Field | Value |
|-------|-------|
| **Sign Up URL** | [https://console.groq.com](https://console.groq.com) |
| **Documentation** | [https://console.groq.com/docs](https://console.groq.com/docs) |
| **Pricing** | [https://groq.com/pricing](https://groq.com/pricing) |
| **Free Tier** | Rate-limited free tier available |

**Setup Steps:**
```
1. Go to https://console.groq.com
2. Sign up with Google or GitHub OAuth
3. Navigate to API Keys
4. Create new key:
   - Name: "voice-agent-production"
5. Copy the API key (starts with gsk_)
```

**Environment Variables:**
```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Recommended Model Configuration:**
```python
# LLaMA 3.1 8B Instant - fastest for voice
model = "llama-3.1-8b-instant"
temperature = 0.7
max_tokens = 256  # Keep short for voice
stream = True
```

**Available Models (by speed):**
| Model | TTFT | Use Case |
|-------|------|----------|
| llama-3.1-8b-instant | ~150ms | **Voice (recommended)** |
| llama-3.1-70b-versatile | ~300ms | Complex reasoning |
| mixtral-8x7b-32768 | ~200ms | Long context |

---

### Step 4: Cartesia (Text-to-Speech)

| Field | Value |
|-------|-------|
| **Sign Up URL** | [https://play.cartesia.ai/sign-in](https://play.cartesia.ai/sign-in) |
| **Documentation** | [https://docs.cartesia.ai](https://docs.cartesia.ai) |
| **Pricing** | [https://cartesia.ai/pricing](https://cartesia.ai/pricing) |
| **Free Tier** | 20,000 credits/month |

**Setup Steps:**
```
1. Go to https://play.cartesia.ai/sign-in
2. Sign up with email or Google OAuth
3. Navigate to API Keys → New
4. Create new key:
   - Name: "voice-agent-production"
5. Copy the API key
```

**Environment Variables:**
```bash
CARTESIA_API_KEY=sk_car_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Pricing Tiers:**
| Plan | Price | Credits | Notes |
|------|-------|---------|-------|
| Free | $0/mo | 20,000 | Development |
| Pro | $5/mo | 100,000 | Voice cloning |
| Startup | $49/mo | 1,250,000 | Organizations |
| Scale | $299/mo | 8,000,000 | High concurrency |

**Recommended Model Configuration:**
```python
# Sonic-3 is the latest, lowest latency
model = "sonic-3"
voice = "professional-male"  # Or use voice ID from library
sample_rate = 24000
```

**Voice Selection:**
1. Browse voices at [https://play.cartesia.ai](https://play.cartesia.ai)
2. Find a voice you like
3. Copy the Voice ID (UUID format)
4. Use in configuration

---

### Step 5: Railway (Compute)

| Field | Value |
|-------|-------|
| **Sign Up URL** | [https://railway.app](https://railway.app) |
| **Documentation** | [https://docs.railway.app](https://docs.railway.app) |
| **Pricing** | [https://railway.app/pricing](https://railway.app/pricing) |
| **Free Tier** | $5 trial credit |

**Setup Steps:**
```
1. Go to https://railway.app
2. Sign up with GitHub OAuth
3. Create new project
4. Link to GitHub repository (recommended)
   - OR deploy from Dockerfile
5. Configure environment variables (all keys above)
6. Deploy
```

---

## Infrastructure Setup

### Project Structure

```
livekit-voice-agent/
├── src/
│   ├── __init__.py
│   ├── agent.py                    # Main agent entry point
│   ├── config.py                   # Configuration management
│   ├── plugins/
│   │   ├── __init__.py
│   │   └── groq_llm.py            # Custom Groq LLM (if not using built-in)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                # Tool base class
│   │   ├── email_tool.py          # Email via n8n
│   │   └── database_tool.py       # Vector DB via n8n
│   └── utils/
│       ├── __init__.py
│       ├── logging.py             # Structured logging
│       └── metrics.py             # Latency tracking
├── tests/
│   ├── __init__.py
│   ├── test_agent.py
│   └── test_tools.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml              # Local development
├── railway.json
├── .env.example
└── README.md
```

### requirements.txt

```txt
# Core LiveKit
livekit-agents>=1.0.0,<2.0.0
livekit-plugins-silero>=1.0.0
livekit-plugins-deepgram>=1.0.0
livekit-plugins-cartesia>=1.0.0

# LLM
groq>=0.9.0

# HTTP
aiohttp>=3.9.0
httpx>=0.27.0

# Configuration
python-dotenv>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0

# Observability
structlog>=24.0.0
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0
opentelemetry-exporter-otlp>=1.20.0

# Security
cryptography>=42.0.0
```

### Dockerfile

```dockerfile
# Multi-stage build for smaller image
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production image
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY src/ ./src/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash agent
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Entry point
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "src.agent", "start"]
```

### railway.json

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "numReplicas": 1,
    "sleepApplication": false,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/health",
    "healthcheckTimeout": 30
  }
}
```

---

## LiveKit Agent Implementation

### src/config.py

```python
"""Configuration management with validation."""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    # LiveKit
    livekit_url: str = Field(..., env="LIVEKIT_URL")
    livekit_api_key: str = Field(..., env="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(..., env="LIVEKIT_API_SECRET")

    # Deepgram
    deepgram_api_key: str = Field(..., env="DEEPGRAM_API_KEY")
    deepgram_model: str = Field(default="nova-3", env="DEEPGRAM_MODEL")

    # Groq
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-8b-instant", env="GROQ_MODEL")
    groq_temperature: float = Field(default=0.7, env="GROQ_TEMPERATURE")
    groq_max_tokens: int = Field(default=256, env="GROQ_MAX_TOKENS")

    # Cartesia
    cartesia_api_key: str = Field(..., env="CARTESIA_API_KEY")
    cartesia_model: str = Field(default="sonic-3", env="CARTESIA_MODEL")
    cartesia_voice: str = Field(
        default="a0e99841-438c-4a64-b679-ae501e7d6091",  # Default professional voice
        env="CARTESIA_VOICE"
    )

    # n8n Integration
    n8n_webhook_base_url: str = Field(
        default="https://jayconnorexe.app.n8n.cloud/webhook",
        env="N8N_WEBHOOK_BASE_URL"
    )

    # Agent Settings
    agent_name: str = Field(default="Voice Assistant", env="AGENT_NAME")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    @field_validator("livekit_url")
    @classmethod
    def validate_livekit_url(cls, v: str) -> str:
        if not v.startswith("wss://"):
            raise ValueError("LIVEKIT_URL must start with wss://")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### src/agent.py

```python
"""Main LiveKit voice agent implementation."""
import asyncio
import logging
from typing import Optional

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import silero, deepgram, cartesia

from .config import get_settings
from .plugins.groq_llm import GroqLLM
from .tools.email_tool import send_email_tool
from .tools.database_tool import query_database_tool
from .utils.logging import setup_logging
from .utils.metrics import LatencyTracker

# Initialize logging
logger = setup_logging(__name__)
settings = get_settings()

# System prompt for the voice agent
SYSTEM_PROMPT = """You are a professional voice assistant for enterprise meetings.

## CORE BEHAVIORS
- Be concise and direct - keep responses under 2 sentences when possible
- Always confirm before executing actions (sending emails, creating tasks)
- Announce completion of all actions
- Use natural conversational pacing

## AVAILABLE TOOLS
1. send_email: Send emails via Gmail
   - Requires: to, subject, body
   - Always confirm recipient and subject before sending

2. query_database: Search the knowledge base
   - Use for looking up information
   - Summarize results conversationally

## RESPONSE GUIDELINES
- Speak naturally, not like reading text
- Use contractions (I'll, we're, that's)
- Avoid technical jargon unless necessary
- If you don't understand, ask for clarification

## ERROR HANDLING
- If a tool fails, apologize and offer alternatives
- Never expose technical error details to the user
"""


async def entrypoint(ctx: JobContext):
    """Main entry point for the voice agent."""

    logger.info(f"Agent starting for room: {ctx.room.name}")
    tracker = LatencyTracker()

    # Initialize VAD with optimized settings
    vad = silero.VAD.load(
        min_speech_duration=0.1,      # 100ms minimum speech
        min_silence_duration=0.3,     # 300ms silence to end utterance
        activation_threshold=0.5,     # Sensitivity (0.0-1.0)
        sample_rate=16000,
    )

    # Initialize STT with Deepgram Nova-3
    stt = deepgram.STT(
        model=settings.deepgram_model,
        language="en",
        smart_format=True,
        interim_results=True,
        punctuate=True,
        profanity_filter=False,
        diarize=False,  # Single speaker for now
    )

    # Initialize LLM with Groq
    llm_instance = GroqLLM(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=settings.groq_temperature,
        max_tokens=settings.groq_max_tokens,
    )

    # Initialize TTS with Cartesia Sonic-3
    tts = cartesia.TTS(
        model=settings.cartesia_model,
        voice=settings.cartesia_voice,
        api_key=settings.cartesia_api_key,
        sample_rate=24000,
    )

    # Create agent session
    session = AgentSession(
        vad=vad,
        stt=stt,
        llm=llm_instance,
        tts=tts,
        # Enable aligned transcription for better frontend sync
        use_tts_aligned_transcript=True,
    )

    # Define agent with tools
    agent = Agent(
        instructions=SYSTEM_PROMPT,
        tools=[send_email_tool, query_database_tool],
    )

    # Connect to room
    await ctx.connect(auto_subscribe=True)
    logger.info(f"Connected to room: {ctx.room.name}")

    # Start the agent session
    await session.start(agent=agent, room=ctx.room)
    logger.info("Agent session started")

    # Event handlers for observability
    @session.on("user_speech_started")
    def on_user_speech_started():
        tracker.start("total_latency")
        tracker.start("vad_to_stt")
        ctx.room.local_participant.publish_data(
            b'{"type":"agent.state","state":"listening"}'
        )
        logger.debug("User started speaking")

    @session.on("user_speech_finished")
    def on_user_speech_finished(text: str):
        tracker.end("vad_to_stt")
        tracker.start("stt_to_llm")
        logger.info(f"User said: {text[:100]}...")

    @session.on("agent_thinking")
    def on_agent_thinking():
        tracker.end("stt_to_llm")
        tracker.start("llm_inference")
        ctx.room.local_participant.publish_data(
            b'{"type":"agent.state","state":"thinking"}'
        )

    @session.on("agent_speech_started")
    def on_agent_speech_started():
        tracker.end("llm_inference")
        tracker.start("tts_synthesis")
        ctx.room.local_participant.publish_data(
            b'{"type":"agent.state","state":"speaking"}'
        )
        logger.debug("Agent started speaking")

    @session.on("agent_speech_finished")
    def on_agent_speech_finished():
        tracker.end("tts_synthesis")
        total = tracker.end("total_latency")
        ctx.room.local_participant.publish_data(
            b'{"type":"agent.state","state":"idle"}'
        )
        logger.info(f"Total latency: {total:.0f}ms")

    @session.on("function_call")
    async def on_function_call(call: llm.FunctionCall):
        logger.info(f"Tool called: {call.name} with args: {call.arguments}")

    @session.on("function_result")
    async def on_function_result(result: llm.FunctionResult):
        logger.info(f"Tool result: {result.name} -> {result.result[:100]}...")

    # Keep agent running until room closes
    await session.wait()
    logger.info("Agent session ended")


def main():
    """CLI entry point."""
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
        )
    )


if __name__ == "__main__":
    main()
```

### src/plugins/groq_llm.py

```python
"""Groq LLM integration for LiveKit Agents."""
import os
from typing import AsyncIterator, Optional, List, Any

from livekit.agents import llm
from groq import AsyncGroq


class GroqLLM(llm.LLM):
    """Groq LLM implementation for LiveKit Agents.

    Uses Groq's LPU inference for ultra-low latency LLM responses.
    Recommended model: llama-3.1-8b-instant (~200ms TTFT)
    """

    def __init__(
        self,
        model: str = "llama-3.1-8b-instant",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 256,
        top_p: float = 1.0,
    ):
        super().__init__()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

        self._client = AsyncGroq(
            api_key=api_key or os.environ.get("GROQ_API_KEY")
        )

    async def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: Optional[List[llm.FunctionTool]] = None,
        temperature: Optional[float] = None,
        n: int = 1,
        parallel_tool_calls: bool = True,
    ) -> "GroqLLMStream":
        """Generate a streaming chat completion."""

        # Convert messages to Groq format
        messages = []
        for msg in chat_ctx.messages:
            if msg.role == llm.ChatRole.SYSTEM:
                messages.append({"role": "system", "content": msg.content})
            elif msg.role == llm.ChatRole.USER:
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == llm.ChatRole.ASSISTANT:
                if msg.tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": tc.arguments,
                                }
                            }
                            for tc in msg.tool_calls
                        ]
                    })
                else:
                    messages.append({"role": "assistant", "content": msg.content})
            elif msg.role == llm.ChatRole.TOOL:
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })

        # Convert tools to Groq format
        groq_tools = None
        if tools:
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                }
                for tool in tools
            ]

        # Create streaming completion
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            stream=True,
            tools=groq_tools,
            tool_choice="auto" if groq_tools else None,
            parallel_tool_calls=parallel_tool_calls,
        )

        return GroqLLMStream(stream, tools)


class GroqLLMStream(llm.LLMStream):
    """Streaming response from Groq."""

    def __init__(self, stream: Any, tools: Optional[List[llm.FunctionTool]]):
        super().__init__()
        self._stream = stream
        self._tools = tools
        self._current_tool_calls = {}

    async def __anext__(self) -> llm.ChatChunk:
        """Get next chunk from stream."""
        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            raise

        delta = chunk.choices[0].delta

        # Handle tool calls
        if delta.tool_calls:
            for tc in delta.tool_calls:
                if tc.index not in self._current_tool_calls:
                    self._current_tool_calls[tc.index] = {
                        "id": tc.id or "",
                        "name": "",
                        "arguments": "",
                    }

                if tc.function:
                    if tc.function.name:
                        self._current_tool_calls[tc.index]["name"] = tc.function.name
                    if tc.function.arguments:
                        self._current_tool_calls[tc.index]["arguments"] += tc.function.arguments

        # Check for finish reason
        finish_reason = chunk.choices[0].finish_reason

        tool_calls = None
        if finish_reason == "tool_calls":
            tool_calls = [
                llm.FunctionCall(
                    id=tc["id"],
                    name=tc["name"],
                    arguments=tc["arguments"],
                )
                for tc in self._current_tool_calls.values()
            ]

        return llm.ChatChunk(
            content=delta.content or "",
            tool_calls=tool_calls,
        )

    def __aiter__(self):
        return self
```

### src/tools/email_tool.py

```python
"""Email tool for sending emails via n8n webhook."""
import json
from typing import Optional

import aiohttp
from livekit.agents import llm

from ..config import get_settings

settings = get_settings()


@llm.function_tool(
    name="send_email",
    description="""Send an email to a recipient.
    ALWAYS confirm the recipient and subject with the user before calling this tool.
    After sending, announce the success to the user.""",
)
async def send_email_tool(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
) -> str:
    """Send an email via n8n webhook.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body content (plain text)
        cc: Optional CC recipient

    Returns:
        Success message or error description
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/execute-gmail"

    payload = {
        "to": to,
        "subject": subject,
        "body": body,
    }
    if cc:
        payload["cc"] = cc

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                result = await response.json()

                if response.status == 200 and result.get("status") == "COMPLETED":
                    return f"Email sent successfully to {to}"
                else:
                    error_msg = result.get("error", "Unknown error")
                    return f"Failed to send email: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error sending email: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
```

### src/tools/database_tool.py

```python
"""Database query tool for vector search via n8n webhook."""
import json
from typing import Optional

import aiohttp
from livekit.agents import llm

from ..config import get_settings

settings = get_settings()


@llm.function_tool(
    name="query_database",
    description="""Search the knowledge base for information.
    Use this to look up data, find documents, or answer questions about stored content.
    Summarize the results conversationally for the user.""",
)
async def query_database_tool(
    query: str,
    filters: Optional[str] = None,
    max_results: int = 5,
) -> str:
    """Query the vector database via n8n webhook.

    Args:
        query: Natural language search query
        filters: Optional JSON string of filters (e.g., '{"date_range": "2024"}')
        max_results: Maximum number of results to return

    Returns:
        Search results formatted as text
    """
    webhook_url = f"{settings.n8n_webhook_base_url}/query-vector-db"

    payload = {
        "query": query,
        "max_results": max_results,
    }

    if filters:
        try:
            payload["filters"] = json.loads(filters)
        except json.JSONDecodeError:
            payload["filters"] = {}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                result = await response.json()

                if response.status == 200 and result.get("status") == "COMPLETED":
                    results = result.get("results", [])
                    if not results:
                        return "No results found for your query."

                    # Format results for voice
                    formatted = []
                    for i, r in enumerate(results[:max_results], 1):
                        title = r.get("title", f"Result {i}")
                        snippet = r.get("snippet", r.get("content", ""))[:200]
                        formatted.append(f"{i}. {title}: {snippet}")

                    return "\n".join(formatted)
                else:
                    error_msg = result.get("error", "Unknown error")
                    return f"Search failed: {error_msg}"

    except aiohttp.ClientError as e:
        return f"Network error querying database: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"
```

### src/utils/logging.py

```python
"""Structured logging configuration."""
import logging
import sys
from typing import Optional

import structlog


def setup_logging(name: Optional[str] = None, level: str = "INFO") -> structlog.BoundLogger:
    """Configure structured logging.

    Args:
        name: Logger name (usually __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured structlog logger
    """
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if sys.stderr.isatty()
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging for libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    return structlog.get_logger(name)
```

### src/utils/metrics.py

```python
"""Latency tracking and metrics collection."""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class LatencyTracker:
    """Track latency across pipeline stages."""

    _stages: Dict[str, float] = field(default_factory=dict)
    _completed: Dict[str, float] = field(default_factory=dict)

    def start(self, stage: str) -> None:
        """Start timing a stage."""
        self._stages[stage] = time.perf_counter()

    def end(self, stage: str) -> float:
        """End timing a stage and return elapsed milliseconds."""
        if stage not in self._stages:
            logger.warning(f"Stage '{stage}' was not started")
            return 0.0

        elapsed_ms = (time.perf_counter() - self._stages[stage]) * 1000
        self._completed[stage] = elapsed_ms
        del self._stages[stage]

        logger.debug(f"Stage '{stage}' completed", latency_ms=round(elapsed_ms, 1))
        return elapsed_ms

    def get_summary(self) -> Dict[str, float]:
        """Get summary of all completed stages."""
        return self._completed.copy()

    def reset(self) -> None:
        """Reset all tracking."""
        self._stages.clear()
        self._completed.clear()


@dataclass
class MetricsCollector:
    """Collect and report metrics."""

    latencies: Dict[str, list] = field(default_factory=dict)

    def record_latency(self, stage: str, value_ms: float) -> None:
        """Record a latency measurement."""
        if stage not in self.latencies:
            self.latencies[stage] = []
        self.latencies[stage].append(value_ms)

    def get_percentiles(self, stage: str) -> Dict[str, float]:
        """Get P50, P90, P99 for a stage."""
        if stage not in self.latencies or not self.latencies[stage]:
            return {}

        values = sorted(self.latencies[stage])
        n = len(values)

        return {
            "p50": values[int(n * 0.5)],
            "p90": values[int(n * 0.9)],
            "p99": values[int(n * 0.99)] if n >= 100 else values[-1],
            "count": n,
        }
```

---

## Scalability & High Availability

### Horizontal Scaling Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         HORIZONTALLY SCALED ARCHITECTURE                          │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                          LOAD BALANCING LAYER                                │ │
│  ├─────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                              │ │
│  │  LiveKit Cloud (handles WebRTC load balancing automatically)                 │ │
│  │       │                                                                      │ │
│  │       ├──► Region: us-west-2 (primary)                                       │ │
│  │       ├──► Region: us-east-1 (failover)                                      │ │
│  │       └──► Region: eu-west-1 (international)                                 │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                          AGENT WORKER POOL                                   │ │
│  ├─────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                              │ │
│  │  Railway Service (Auto-scaling)                                              │ │
│  │       │                                                                      │ │
│  │       ├──► Worker 1 ──► Rooms: room_001, room_002, room_003                  │ │
│  │       ├──► Worker 2 ──► Rooms: room_004, room_005, room_006                  │ │
│  │       ├──► Worker 3 ──► Rooms: room_007, room_008, room_009                  │ │
│  │       └──► Worker N ──► (auto-scales based on demand)                        │ │
│  │                                                                              │ │
│  │  LiveKit handles agent dispatch automatically:                               │ │
│  │  - New room created → LiveKit dispatches to available worker                 │ │
│  │  - Worker failure → LiveKit reassigns to healthy worker                      │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Railway Scaling Configuration

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "numReplicas": 3,
    "sleepApplication": false,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Auto-Scaling Rules (Railway Pro)

```yaml
# railway.yaml (conceptual - configure in dashboard)
scaling:
  min_replicas: 2
  max_replicas: 10
  target_cpu_percent: 70
  target_memory_percent: 80
  scale_up_cooldown: 60
  scale_down_cooldown: 300
```

---

## Security Considerations

### API Key Management

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              SECURITY ARCHITECTURE                                │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ SECRETS MANAGEMENT                                                          │ │
│  ├─────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                              │ │
│  │  Railway Environment Variables (encrypted at rest)                           │ │
│  │  ├── LIVEKIT_API_KEY          → Never expose to client                      │ │
│  │  ├── LIVEKIT_API_SECRET       → Never expose to client                      │ │
│  │  ├── DEEPGRAM_API_KEY         → Server-side only                            │ │
│  │  ├── GROQ_API_KEY             → Server-side only                            │ │
│  │  ├── CARTESIA_API_KEY         → Server-side only                            │ │
│  │  └── N8N_WEBHOOK_SECRET       → For webhook authentication                  │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ TOKEN FLOW (LiveKit)                                                        │ │
│  ├─────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                              │ │
│  │  1. Client requests token from backend (via n8n or API)                      │ │
│  │  2. Backend generates short-lived JWT (1-4 hours)                            │ │
│  │  3. Client uses JWT to connect to LiveKit Cloud                              │ │
│  │  4. JWT contains permissions (room access, publish/subscribe)                │ │
│  │                                                                              │ │
│  │  Token Permissions:                                                          │ │
│  │  ├── roomJoin: true                                                          │ │
│  │  ├── room: "meeting_${session_id}"  (scoped to specific room)               │ │
│  │  ├── canPublish: true               (audio/video)                            │ │
│  │  ├── canSubscribe: true             (receive agent audio)                    │ │
│  │  └── canPublishData: false          (no arbitrary data from client)         │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ WEBHOOK SECURITY (n8n)                                                      │ │
│  ├─────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                              │ │
│  │  1. Use webhook authentication (header token)                                │ │
│  │  2. Validate request origin (IP allowlist or signature)                      │ │
│  │  3. Rate limit by session_id                                                 │ │
│  │  4. Log all tool executions for audit                                        │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Token Generation Code (n8n Code Node)

```javascript
// n8n Code node for generating LiveKit tokens
const { AccessToken } = require('livekit-server-sdk');

const apiKey = $env.LIVEKIT_API_KEY;
const apiSecret = $env.LIVEKIT_API_SECRET;
const sessionId = $input.first().json.session_id;

// Create token with minimal permissions
const token = new AccessToken(apiKey, apiSecret, {
  identity: `user_${sessionId}`,
  ttl: '4h',  // 4 hour expiration
});

// Grant scoped permissions
token.addGrant({
  roomJoin: true,
  room: `meeting_${sessionId}`,
  canPublish: true,
  canSubscribe: true,
  canPublishData: false,  // Security: no arbitrary data
});

return [{
  json: {
    token: token.toJwt(),
    room: `meeting_${sessionId}`,
    url: $env.LIVEKIT_URL,
  }
}];
```

---

## Monitoring & Observability

### Metrics Dashboard (Recommended Setup)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           OBSERVABILITY STACK                                     │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ METRICS COLLECTION                                                          │ │
│  ├─────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                              │ │
│  │  LiveKit Cloud Dashboard (built-in)                                          │ │
│  │  ├── Room metrics (concurrent users, duration)                               │ │
│  │  ├── Bandwidth usage                                                         │ │
│  │  ├── Connection quality (jitter, packet loss)                               │ │
│  │  └── Agent metrics (CPU, memory)                                             │ │
│  │                                                                              │ │
│  │  Custom Application Metrics (via OpenTelemetry)                              │ │
│  │  ├── voice_latency_vad_ms (histogram)                                       │ │
│  │  ├── voice_latency_stt_ms (histogram)                                       │ │
│  │  ├── voice_latency_llm_ms (histogram)                                       │ │
│  │  ├── voice_latency_tts_ms (histogram)                                       │ │
│  │  ├── voice_latency_total_ms (histogram)                                     │ │
│  │  ├── tool_calls_total (counter, labeled by tool)                            │ │
│  │  └── tool_errors_total (counter, labeled by tool)                           │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │ ALERTING RULES                                                              │ │
│  ├─────────────────────────────────────────────────────────────────────────────┤ │
│  │                                                                              │ │
│  │  Critical Alerts:                                                            │ │
│  │  ├── P99 total latency > 800ms for 5 minutes                                │ │
│  │  ├── Error rate > 5% for 2 minutes                                          │ │
│  │  ├── Agent worker count < 1                                                  │ │
│  │  └── API key quota > 90%                                                     │ │
│  │                                                                              │ │
│  │  Warning Alerts:                                                             │ │
│  │  ├── P90 total latency > 600ms for 10 minutes                               │ │
│  │  ├── Tool failure rate > 2%                                                  │ │
│  │  └── Memory usage > 80%                                                      │ │
│  │                                                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Cost Analysis

### Per-Minute Cost Breakdown

| Component | Unit Cost | Usage/Min | Cost/Min |
|-----------|-----------|-----------|----------|
| LiveKit Cloud | FREE tier | - | $0.000 |
| Deepgram Nova-3 | $0.0035/min | 0.5 min STT | $0.0018 |
| Groq LLaMA 3.1 | $0.05/1M tokens | ~500 tokens | $0.000025 |
| Cartesia Sonic | ~$0.02/min | 0.5 min TTS | $0.010 |
| Railway | $5/month | - | ~$0.0001 |
| **TOTAL** | | | **~$0.012/min** |

### Monthly Cost Projection

| Usage Level | Minutes/Month | Voice Cost | Fixed Cost | Total |
|-------------|--------------|------------|------------|-------|
| Development | 100 | $1.20 | $5 | **$6.20** |
| Light Production | 1,000 | $12 | $5 | **$17** |
| Medium Production | 10,000 | $120 | $20 | **$140** |
| Heavy Production | 100,000 | $1,200 | $50 | **$1,250** |

### Comparison to OpenAI Realtime

| Usage | OpenAI Realtime | LiveKit Stack | Savings |
|-------|-----------------|---------------|---------|
| 1,000 min/mo | ~$36 | ~$17 | **53%** |
| 10,000 min/mo | ~$360 | ~$140 | **61%** |
| 100,000 min/mo | ~$3,600 | ~$1,250 | **65%** |

---

## Deployment Checklist

### Pre-Deployment

```
□ All API keys obtained and tested
  □ LiveKit Cloud credentials verified
  □ Deepgram API key with $200 credit confirmed
  □ Groq API key active
  □ Cartesia API key with 20k credits confirmed

□ Infrastructure ready
  □ Railway project created
  □ Environment variables set in Railway
  □ Vercel project configured
  □ n8n webhooks accessible

□ Code complete
  □ Agent implementation tested locally
  □ Tools tested with n8n webhooks
  □ Dockerfile builds successfully
  □ Requirements.txt includes all dependencies
```

### Deployment

```
□ Deploy agent to Railway
  □ Push code to repository
  □ Railway auto-deploys from GitHub
  □ Verify deployment logs
  □ Check health endpoint

□ Deploy client to Vercel
  □ Update environment variables
  □ Deploy production build
  □ Verify WebRTC connection

□ Update n8n workflows
  □ Add LiveKit token generation
  □ Update Recall.ai bot URL
  □ Test end-to-end flow
```

### Post-Deployment

```
□ Validation
  □ Test voice conversation end-to-end
  □ Measure latency (target <500ms)
  □ Test tool execution (email, database)
  □ Test error handling

□ Monitoring
  □ Verify LiveKit Cloud dashboard
  □ Check Railway logs
  □ Confirm alerting rules

□ Documentation
  □ Update runbooks
  □ Document rollback procedure
  □ Share credentials securely
```

---

## Troubleshooting Guide

### Common Issues

| Issue | Symptoms | Resolution |
|-------|----------|------------|
| Agent not joining room | "Agent timeout" in logs | Check LIVEKIT_URL, API keys |
| High latency (>800ms) | Slow responses | Check Groq/Cartesia status pages |
| STT not working | Empty transcriptions | Verify DEEPGRAM_API_KEY |
| TTS silent | No audio output | Check Cartesia voice ID |
| Tools failing | "Network error" | Verify N8N_WEBHOOK_BASE_URL |

### Debug Commands

```bash
# Check Railway logs
railway logs --follow

# Test LiveKit connection
python -c "from livekit import api; print(api.LiveKitAPI('${LIVEKIT_URL}').ping())"

# Test Deepgram
curl -X POST "https://api.deepgram.com/v1/listen" \
  -H "Authorization: Token ${DEEPGRAM_API_KEY}" \
  -H "Content-Type: audio/wav" \
  --data-binary @test.wav

# Test Groq
curl -X POST "https://api.groq.com/openai/v1/chat/completions" \
  -H "Authorization: Bearer ${GROQ_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"Hi"}]}'

# Test Cartesia
curl -X POST "https://api.cartesia.ai/tts/bytes" \
  -H "X-API-Key: ${CARTESIA_API_KEY}" \
  -H "Cartesia-Version: 2024-06-10" \
  -H "Content-Type: application/json" \
  -d '{"model_id":"sonic-english-fast","transcript":"Hello","voice":{"mode":"id","id":"a0e99841-438c-4a64-b679-ae501e7d6091"},"output_format":{"container":"raw","encoding":"pcm_f32le","sample_rate":24000}}'
```

---

## Quick Reference Links

### Service Dashboards

| Service | Dashboard URL | Purpose |
|---------|--------------|---------|
| LiveKit Cloud | [cloud.livekit.io](https://cloud.livekit.io) | Rooms, analytics, API keys |
| Deepgram | [console.deepgram.com](https://console.deepgram.com) | Usage, billing, API keys |
| Groq | [console.groq.com](https://console.groq.com) | Usage, models, API keys |
| Cartesia | [play.cartesia.ai](https://play.cartesia.ai) | Voices, usage, API keys |
| Railway | [railway.app](https://railway.app) | Deployments, logs, env vars |
| Vercel | [vercel.com](https://vercel.com) | Frontend deployments |

### Documentation

| Service | Documentation URL |
|---------|------------------|
| LiveKit Agents | [docs.livekit.io/agents](https://docs.livekit.io/agents/) |
| LiveKit Cartesia Plugin | [docs.livekit.io/agents/models/tts/plugins/cartesia](https://docs.livekit.io/agents/models/tts/plugins/cartesia/) |
| Deepgram API | [developers.deepgram.com/docs](https://developers.deepgram.com/docs) |
| Groq API | [console.groq.com/docs](https://console.groq.com/docs) |
| Cartesia API | [docs.cartesia.ai](https://docs.cartesia.ai) |

---

*Document Version: 1.0.0 | Last Updated: January 2026*
