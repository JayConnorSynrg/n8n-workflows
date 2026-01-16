"""Main LiveKit voice agent implementation.

Based on LiveKit Agents 1.3.x documentation:
- https://docs.livekit.io/agents/logic/sessions/
- https://docs.livekit.io/agents/multimodality/audio/
"""
import asyncio
import json
import logging
from typing import Optional

from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    room_io,
)
from livekit.plugins import silero, deepgram, cartesia

# Try to import turn detector (optional but recommended)
try:
    from livekit.plugins.turn_detector.multilingual import MultilingualModel
    HAS_TURN_DETECTOR = True
except ImportError:
    HAS_TURN_DETECTOR = False
    MultilingualModel = None

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


def prewarm(proc: JobProcess):
    """Prewarm VAD model during server initialization for reduced first-call latency."""
    logger.info("Prewarming VAD model...")
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.05,      # 50ms - faster speech detection start
        min_silence_duration=0.55,     # 550ms - better end-of-turn detection
        prefix_padding_duration=0.5,   # 500ms padding before speech
        activation_threshold=0.5,      # Sensitivity (0.0-1.0)
        sample_rate=16000,             # Silero requires 8kHz or 16kHz
        force_cpu=True,                # Consistent CPU inference
    )
    logger.info("VAD model prewarmed")


async def entrypoint(ctx: JobContext):
    """Main entry point for the voice agent."""

    logger.info(f"Agent starting for room: {ctx.room.name}")
    tracker = LatencyTracker()

    # Use prewarmed VAD or load fresh if not available
    if "vad" in ctx.proc.userdata:
        vad = ctx.proc.userdata["vad"]
        logger.info("Using prewarmed VAD")
    else:
        logger.warning("VAD not prewarmed, loading now (adds latency)")
        vad = silero.VAD.load(
            min_speech_duration=0.05,
            min_silence_duration=0.55,
            prefix_padding_duration=0.5,
            activation_threshold=0.5,
            sample_rate=16000,
            force_cpu=True,
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
    # Using 24kHz sample rate (framework default, auto-resampled from VAD's 16kHz)
    tts = cartesia.TTS(
        model=settings.cartesia_model,
        voice=settings.cartesia_voice,
        api_key=settings.cartesia_api_key,
        sample_rate=24000,
    )

    # Create agent session with optimized settings
    session_kwargs = {
        "vad": vad,
        "stt": stt,
        "llm": llm_instance,
        "tts": tts,
        # Performance optimizations
        "preemptive_generation": True,  # Start LLM before turn ends
        # Handle background noise gracefully
        "resume_false_interruption": True,
        "false_interruption_timeout": 1.0,
    }

    # Add turn detection if available
    # Note: Import may succeed but initialization can fail if model files aren't downloaded
    if HAS_TURN_DETECTOR and MultilingualModel:
        try:
            session_kwargs["turn_detection"] = MultilingualModel()
            logger.info("Using semantic turn detection")
        except RuntimeError as e:
            logger.warning(f"Turn detector initialization failed: {e}")
            logger.warning("Using VAD-only turn detection (run 'python -m livekit.agents download-files' to enable)")
    else:
        logger.warning("Turn detector not available, using VAD-only turn detection")

    session = AgentSession(**session_kwargs)

    # Define agent with tools
    agent = Agent(
        instructions=SYSTEM_PROMPT,
        tools=[send_email_tool, query_database_tool],
    )

    # Register event handlers BEFORE starting session
    # LiveKit Agents 1.3.x requires synchronous callbacks - async work via asyncio.create_task

    # Safe publish helper - handles cases where room is disconnecting
    async def safe_publish_data(data: bytes) -> bool:
        """Safely publish data to room, handling disconnection gracefully."""
        try:
            if ctx.room.local_participant:
                await ctx.room.local_participant.publish_data(data)
                return True
        except Exception as e:
            logger.debug(f"Could not publish data (room may be closing): {e}")
        return False

    @session.on("user_state_changed")
    def on_user_state_changed(ev):
        """User state: speaking, listening, away."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"User state changed: {state}")
        if str(state) == "speaking":
            tracker.start("total_latency")
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"listening"}'
            ))

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev):
        """Called when user speech is transcribed."""
        text = ev.transcript if hasattr(ev, 'transcript') else str(ev)
        is_final = getattr(ev, 'is_final', True)
        # Safe text handling for logging
        text_preview = text[:100] if text and len(text) > 100 else (text or "(empty)")
        logger.info(f"User said: {text_preview}")
        # Publish user transcript to client for UI display
        asyncio.create_task(safe_publish_data(
            json.dumps({
                "type": "transcript.user",
                "text": text or "",
                "is_final": is_final
            }).encode()
        ))

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        """Agent state: initializing, idle, listening, thinking, speaking."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"Agent state changed: {state}")

        state_str = str(state).lower()
        if "thinking" in state_str:
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"thinking"}'
            ))
        elif "speaking" in state_str:
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"speaking"}'
            ))
        elif "listening" in state_str:
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"listening"}'
            ))
        elif "idle" in state_str:
            total = tracker.end("total_latency")
            if total:
                logger.info(f"Total latency: {total:.0f}ms")
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"idle"}'
            ))

    @session.on("speech_created")
    def on_speech_created(ev):
        """Called when agent generates speech - capture transcript."""
        # Get the text from the event with safe attribute access
        text = ""
        try:
            if hasattr(ev, 'source') and ev.source and hasattr(ev.source, 'text'):
                text = ev.source.text or ""
            elif hasattr(ev, 'text'):
                text = ev.text or ""
        except Exception as e:
            logger.debug(f"Could not extract speech text: {e}")

        if text:
            text_preview = text[:100] if len(text) > 100 else text
            logger.debug(f"Agent said: {text_preview}")
            asyncio.create_task(safe_publish_data(
                json.dumps({"type": "transcript.assistant", "text": text}).encode()
            ))

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

    # Wait for Output Media client to connect BEFORE starting session
    # This is CRITICAL - the session must link to the client participant
    # to receive audio from them
    # Timeout is 300s (5 min) - early arrival returns immediately, no delay
    async def wait_for_client(timeout_seconds: float = 300.0) -> Optional[rtc.RemoteParticipant]:
        """Wait for the Output Media webpage client to connect to the room.

        Returns immediately when client connects - the timeout only applies if
        client never arrives. Recall.ai can take 30-120s to join meetings and
        render the webpage, so we give it plenty of time.
        """
        start_time = asyncio.get_event_loop().time()
        check_interval = 0.5  # Check every 500ms for fast response when client arrives

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            # Check current participants for the client
            for participant in ctx.room.remote_participants.values():
                # Defensive null check - participant might be in transition state
                if participant is None:
                    continue
                identity = getattr(participant, 'identity', None)
                if identity is None:
                    continue
                identity_lower = identity.lower()
                # Output Media client identity format: 'output-media-{session_id}'
                if identity_lower.startswith('output-media-'):
                    logger.info(f"Client connected: {participant.identity}")
                    return participant

            await asyncio.sleep(check_interval)

        logger.warning(f"Timeout waiting for client after {timeout_seconds}s")
        return None

    logger.info("Waiting for Output Media client to connect (up to 5 min)...")
    client_participant = await wait_for_client(timeout_seconds=300.0)

    if client_participant:
        # Give the client's Web Audio API a moment to initialize after connection
        await asyncio.sleep(1.5)
        logger.info(f"Client connected: {client_participant.identity}, starting session linked to them")
    else:
        # Still start but log warning - agent won't receive audio
        logger.warning("Starting without confirmed client - audio input will not work!")

    # Start the agent session with audio configuration
    # CRITICAL: Link to the client participant via participant_identity in RoomOptions
    # This tells the session which participant to listen to and respond to
    participant_identity = client_participant.identity if client_participant else None

    try:
        await session.start(
            agent=agent,
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_output=room_io.AudioOutputOptions(
                    sample_rate=24000,
                    num_channels=1,
                ),
                audio_input=True,  # Enable audio input from linked participant
                # Link to specific participant's audio stream
                participant_identity=participant_identity,
            ),
        )
        logger.info(f"Agent session started successfully, linked to: {participant_identity or 'first participant'}")
    except Exception as e:
        logger.error(f"CRITICAL: session.start() failed: {e}")
        raise

    # Generate initial greeting with interruptions disabled
    # This allows the client to calibrate AEC (Acoustic Echo Cancellation)
    try:
        await session.say(
            "Hello! I'm your voice assistant. How can I help you today?",
            allow_interruptions=False  # Don't interrupt greeting
        )
        logger.info("Greeting sent successfully")
    except Exception as e:
        logger.error(f"CRITICAL: session.say() failed: {e}")

    # CRITICAL: Keep the agent alive until the room closes
    # Without this, the entrypoint returns and the agent disconnects!
    # If we started without a client, wait for one to connect
    if not client_participant:
        logger.info("No client yet - waiting for Output Media client to connect...")
        # Keep checking for the client while the room is active
        while True:
            await asyncio.sleep(5.0)  # Check every 5 seconds

            # Check if room is still active (defensive comparison)
            try:
                if ctx.room.connection_state != rtc.ConnectionState.CONN_CONNECTED:
                    logger.info("Room disconnected, exiting")
                    break
            except Exception as e:
                logger.error(f"Error checking connection state: {e}")
                break

            # Look for client participant with defensive null checks
            client_found = False
            for participant in ctx.room.remote_participants.values():
                if participant is None:
                    continue
                identity = getattr(participant, 'identity', None)
                if identity is None:
                    continue
                if identity.lower().startswith('output-media-'):
                    logger.info(f"Client connected late: {identity}")
                    # Client finally connected - but we can't re-link the session
                    # The session was already started without a participant
                    # Audio from client won't be received, but at least agent stays alive
                    client_found = True
                    break

            if client_found:
                break
            # No client yet, keep waiting
    else:
        # Client was linked - wait for session to naturally close
        # This happens when the linked participant leaves
        logger.info("Session linked to client, waiting for session close...")

    # Keep agent alive until room closes
    # The room closes when all participants leave or it times out
    while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
        await asyncio.sleep(1.0)

    logger.info("Agent session ended")


def main():
    """CLI entry point."""
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,  # Prewarm VAD on startup
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
            # Explicit dispatch mode: agent only joins when dispatched via AgentDispatchService
            # This is required for the n8n launcher workflow which uses CreateDispatch API
            agent_name="synrg-voice-agent",
        )
    )


if __name__ == "__main__":
    main()
