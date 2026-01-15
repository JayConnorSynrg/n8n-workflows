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

    # Register event handlers BEFORE starting session (avoids race conditions)
    # Using correct event names for livekit-agents 1.3.11

    @session.on("user_state_changed")
    def on_user_state_changed(ev):
        """User state: speaking, listening, away."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"User state changed: {state}")
        if str(state) == "speaking":
            tracker.start("total_latency")
            ctx.room.local_participant.publish_data(
                b'{"type":"agent.state","state":"listening"}'
            )

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev):
        """Called when user speech is transcribed."""
        text = ev.transcript if hasattr(ev, 'transcript') else str(ev)
        logger.info(f"User said: {text[:100] if len(text) > 100 else text}")
        # Publish user transcript to client for UI display
        ctx.room.local_participant.publish_data(
            json.dumps({"type": "transcript.user", "text": text}).encode()
        )

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        """Agent state: initializing, idle, listening, thinking, speaking."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"Agent state changed: {state}")

        state_str = str(state).lower()
        if "thinking" in state_str:
            ctx.room.local_participant.publish_data(
                b'{"type":"agent.state","state":"thinking"}'
            )
        elif "speaking" in state_str:
            ctx.room.local_participant.publish_data(
                b'{"type":"agent.state","state":"speaking"}'
            )
        elif "listening" in state_str:
            ctx.room.local_participant.publish_data(
                b'{"type":"agent.state","state":"listening"}'
            )
        elif "idle" in state_str:
            total = tracker.end("total_latency")
            if total:
                logger.info(f"Total latency: {total:.0f}ms")
            ctx.room.local_participant.publish_data(
                b'{"type":"agent.state","state":"idle"}'
            )

    @session.on("speech_created")
    def on_speech_created(ev):
        """Called when agent generates speech - capture transcript."""
        # Get the text from the event
        text = ""
        if hasattr(ev, 'source') and hasattr(ev.source, 'text'):
            text = ev.source.text
        elif hasattr(ev, 'text'):
            text = ev.text

        if text:
            logger.debug(f"Agent said: {text[:100] if len(text) > 100 else text}")
            ctx.room.local_participant.publish_data(
                json.dumps({"type": "transcript.assistant", "text": text}).encode()
            )

    @session.on("function_tools_executed")
    def on_function_tools_executed(ev):
        """Called when tools finish executing."""
        logger.info(f"Tools executed: {ev}")

    @session.on("metrics_collected")
    def on_metrics_collected(ev):
        """Collect and log metrics."""
        logger.debug(f"Metrics: {ev}")

    # Connect to room
    await ctx.connect(auto_subscribe=True)
    logger.info(f"Connected to room: {ctx.room.name}")

    # Start the agent session
    await session.start(agent=agent, room=ctx.room)
    logger.info("Agent session started")

    # Send initial greeting after brief delay for client to stabilize
    await asyncio.sleep(0.5)
    await session.say("Hello! I'm your voice assistant. How can I help you today?")

    # The session manages its own lifecycle - it stays active until:
    # 1. The linked participant leaves the room
    # 2. The room is deleted
    # 3. session.close() is called explicitly
    # No explicit wait needed - the framework handles this via ctx


def main():
    """CLI entry point."""
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
            # Auto-dispatch: agent automatically joins every new room
            # For explicit dispatch (agent_name="synrg-voice-agent"),
            # you must dispatch via API or participant token
        )
    )


if __name__ == "__main__":
    main()
