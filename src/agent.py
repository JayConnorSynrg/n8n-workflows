"""Main LiveKit voice agent implementation."""
import asyncio
import json
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
        enable_diarization=False,  # Single speaker for now
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

    # Send initial greeting to verify audio output path
    await asyncio.sleep(1)  # Brief delay for client to stabilize
    await session.say("Hello! I'm your voice assistant. How can I help you today?")

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
        # Publish user transcript to client for UI display
        ctx.room.local_participant.publish_data(
            json.dumps({"type": "transcript.user", "text": text}).encode()
        )

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

    # Capture and publish agent transcript for UI display
    @session.on("agent_speech_committed")
    def on_agent_speech_committed(text: str):
        """Called when agent produces final speech text (before TTS)."""
        ctx.room.local_participant.publish_data(
            json.dumps({"type": "transcript.assistant", "text": text}).encode()
        )
        logger.debug(f"Agent said: {text[:100]}...")

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
            # Enable explicit dispatch - agent must be dispatched via API
            # This allows pre-initializing agent before meeting participants join
            agent_name="synrg-voice-agent",
        )
    )


if __name__ == "__main__":
    main()
