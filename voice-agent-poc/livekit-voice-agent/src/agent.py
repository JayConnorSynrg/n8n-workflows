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
from livekit.plugins import silero, deepgram, cartesia, openai

# OPTIMIZED: Turn detector loaded lazily to reduce cold start (saves ~300-500ms)
# Moved from module-level import to on-demand loading in get_turn_detector()
HAS_TURN_DETECTOR = None  # Will be set on first check
_turn_detector_model = None


def get_turn_detector():
    """Lazy-load turn detector model on first use (non-blocking)."""
    global HAS_TURN_DETECTOR, _turn_detector_model

    if HAS_TURN_DETECTOR is None:
        try:
            from livekit.plugins.turn_detector.multilingual import MultilingualModel
            _turn_detector_model = MultilingualModel()
            HAS_TURN_DETECTOR = True
            logger.info("Turn detector loaded successfully (lazy)")
        except ImportError:
            HAS_TURN_DETECTOR = False
            logger.info("Turn detector not available (not installed)")
        except RuntimeError as e:
            HAS_TURN_DETECTOR = False
            logger.warning(f"Turn detector initialization failed: {e}")

    return _turn_detector_model if HAS_TURN_DETECTOR else None

from .config import get_settings
from .tools.email_tool import send_email_tool
from .tools.database_tool import query_database_tool
from .tools.vector_store_tool import store_knowledge_tool
from .tools.google_drive_tool import search_documents_tool, get_document_tool, list_drive_files_tool
from .tools.agent_context_tool import (
    query_context_tool,
    get_session_summary_tool,
    warm_session_cache,
    invalidate_session_cache,
)
from .utils.logging import setup_logging
from .utils.metrics import LatencyTracker
from .utils.context_cache import get_cache_manager

# Initialize logging
logger = setup_logging(__name__)
settings = get_settings()

# System prompt for the voice agent - OPTIMIZED for token efficiency
# Concise prompt reduces latency and token usage
SYSTEM_PROMPT = """You are a concise voice assistant. Keep responses under 2 sentences.

TOOLS:
- send_email: Send emails (~15-30s)
- query_database: Vector search in Pinecone (~5-10s)
- store_knowledge: Add to Pinecone vector DB (~10-20s)
- search_documents, get_document, list_drive_files: Google Drive folder 11KcezPe3NqgcC3TNvHxAAZS4nPYrMXRF (~5-15s)
- query_context, get_session_summary: Session history (~2-5s)

MANDATORY RULES:
1. ALWAYS announce before tool calls: "I'm going to [action] now, this takes about [time]"
2. ALWAYS announce when complete: "Done. [brief result]"
3. Never execute tools silently - user must know what's happening

DATABASE CONTEXT:
- Vector search (query_database): Pinecone semantic search, read-only
- Store knowledge (store_knowledge): Pinecone vector DB, content chunked/embedded
- Session context: Supabase PostgreSQL (table: session_context)

STYLE:
- Speak naturally with contractions
- If tool fails, apologize briefly and explain"""


def prewarm(proc: JobProcess):
    """Prewarm VAD model and initialize cache during server initialization."""
    logger.info("Prewarming VAD model...")
    proc.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.05,      # 50ms - faster speech detection start
        min_silence_duration=0.35,     # 350ms - OPTIMIZED from 550ms (saves ~200ms latency)
        prefix_padding_duration=0.25,  # 250ms - OPTIMIZED from 500ms (saves ~250ms latency)
        activation_threshold=0.1,      # OPTIMIZED from 0.05 (fewer false positives)
        sample_rate=16000,             # Silero requires 8kHz or 16kHz
        force_cpu=True,                # Consistent CPU inference
    )
    logger.info("VAD model prewarmed with optimized settings (silence=350ms, threshold=0.1)")

    # Initialize context cache manager
    cache_manager = get_cache_manager()
    proc.userdata["cache_manager"] = cache_manager
    logger.info("Context cache manager initialized")


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
            min_silence_duration=0.35,     # OPTIMIZED from 550ms
            prefix_padding_duration=0.25,  # OPTIMIZED from 500ms
            activation_threshold=0.1,      # OPTIMIZED from 0.05
            sample_rate=16000,
            force_cpu=True,
        )
        logger.info("VAD loaded with optimized settings (silence=350ms, threshold=0.1)")

    # OPTIMIZED: Initialize STT/LLM/TTS in parallel (saves ~150-200ms)
    # Using asyncio.gather with to_thread for synchronous constructors
    logger.info("Initializing STT/LLM/TTS in parallel...")

    def init_stt():
        return deepgram.STT(
            model=settings.deepgram_model,
            language="en",
            smart_format=True,
            interim_results=True,
            punctuate=True,
            profanity_filter=False,
            enable_diarization=False,
        )

    def init_llm():
        """Initialize Cerebras LLM with GLM-4.7 (~1000 TPS, 1M tokens/day free)."""
        logger.info(f"Initializing Cerebras LLM: {settings.cerebras_model}")
        return openai.LLM.with_cerebras(
            model=settings.cerebras_model,
            api_key=settings.cerebras_api_key,
            temperature=settings.cerebras_temperature,
        )

    def init_tts():
        return cartesia.TTS(
            model=settings.cartesia_model,
            voice=settings.cartesia_voice,
            api_key=settings.cartesia_api_key,
            sample_rate=24000,
        )

    stt, llm_instance, tts = await asyncio.gather(
        asyncio.to_thread(init_stt),
        asyncio.to_thread(init_llm),
        asyncio.to_thread(init_tts),
    )
    logger.info("STT/LLM/TTS initialized in parallel")

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

    # OPTIMIZED: Add turn detection using lazy loader (non-blocking at module load)
    turn_detector = get_turn_detector()
    if turn_detector:
        session_kwargs["turn_detection"] = turn_detector
        logger.info("Using semantic turn detection")
    else:
        logger.info("Using VAD-only turn detection (faster startup)")

    session = AgentSession(**session_kwargs)

    # =========================================================================
    # VAD DEBUG: Monitor if VAD is receiving audio frames
    # =========================================================================
    vad_frame_count = {"count": 0, "speech_frames": 0, "last_log_time": 0}

    @session.on("audio_input")
    def on_audio_input(ev):
        """Debug: Monitor raw audio input frames to VAD."""
        vad_frame_count["count"] += 1
        # Log every 100 frames (~5 seconds at 50ms frame size)
        import time
        now = time.time()
        if now - vad_frame_count["last_log_time"] > 5.0:
            vad_frame_count["last_log_time"] = now
            logger.info(f"🎤 VAD receiving audio: {vad_frame_count['count']} frames total")

    # Define agent with tools
    agent = Agent(
        instructions=SYSTEM_PROMPT,
        tools=[
            # Communication
            send_email_tool,
            # Knowledge Base
            query_database_tool,
            store_knowledge_tool,
            # Documents
            search_documents_tool,
            get_document_tool,
            list_drive_files_tool,
            # Context & History
            query_context_tool,
            get_session_summary_tool,
        ],
    )

    # Register event handlers BEFORE starting session
    # LiveKit Agents 1.3.x requires synchronous callbacks - async work via asyncio.create_task

    # Safe publish helper - handles cases where room is disconnecting
    async def safe_publish_data(data: bytes, log_type: str = "data") -> bool:
        """Safely publish data to room, handling disconnection gracefully."""
        try:
            if ctx.room.local_participant:
                await ctx.room.local_participant.publish_data(data)
                # Log successful publish at INFO level for debugging
                logger.info(f"📤 Published {log_type}: {data[:100].decode('utf-8', errors='ignore')}...")
                return True
            else:
                logger.warning(f"Cannot publish {log_type}: no local_participant")
        except Exception as e:
            logger.warning(f"Failed to publish {log_type}: {e}")
        return False

    @session.on("user_state_changed")
    def on_user_state_changed(ev):
        """User state: speaking, listening, away."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"User state changed: {state}")
        if str(state) == "speaking":
            tracker.start("total_latency")
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"listening"}',
                log_type="agent.state"
            ))

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev):
        """Called when user speech is transcribed."""
        text = ev.transcript if hasattr(ev, 'transcript') else str(ev)
        is_final = getattr(ev, 'is_final', True)

        # ONLY publish FINAL transcripts to avoid duplicates
        # Interim results are partial and will be superseded
        if not is_final:
            return

        # Safe text handling for logging
        text_preview = text[:100] if text and len(text) > 100 else (text or "(empty)")
        logger.info(f"User said (final): {text_preview}")
        # Publish user transcript to client for UI display
        asyncio.create_task(safe_publish_data(
            json.dumps({
                "type": "transcript.user",
                "text": text or "",
                "is_final": True
            }).encode(),
            log_type="transcript.user"
        ))

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        """Agent state: initializing, idle, listening, thinking, speaking."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"Agent state changed: {state}")

        state_str = str(state).lower()
        if "thinking" in state_str:
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"thinking"}',
                log_type="agent.state"
            ))
        elif "speaking" in state_str:
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"speaking"}',
                log_type="agent.state"
            ))
        elif "listening" in state_str:
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"listening"}',
                log_type="agent.state"
            ))
        elif "idle" in state_str:
            total = tracker.end("total_latency")
            if total:
                logger.info(f"Total latency: {total:.0f}ms")
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"idle"}',
                log_type="agent.state"
            ))

    @session.on("conversation_item_added")
    def on_conversation_item_added(ev):
        """Called when a new item is added to conversation - captures agent responses."""
        # Extract item from event
        item = getattr(ev, 'item', None)
        if not item:
            return

        # Check if this is an assistant (agent) message
        role = getattr(item, 'role', None)
        if role != 'assistant':
            return  # Only publish agent responses, user transcripts handled separately

        # Extract text content from the item
        text = ""
        try:
            # Try text_content attribute (common in conversation items)
            if hasattr(item, 'text_content'):
                text = item.text_content or ""
            # Try content attribute
            elif hasattr(item, 'content'):
                content = item.content
                if isinstance(content, str):
                    text = content
                elif hasattr(content, 'text'):
                    text = content.text or ""
            # Try text attribute directly
            elif hasattr(item, 'text'):
                text = item.text or ""
        except Exception as e:
            logger.debug(f"Could not extract conversation item text: {e}")

        if text:
            text_preview = text[:100] if len(text) > 100 else text
            logger.info(f"Agent said: {text_preview}")
            asyncio.create_task(safe_publish_data(
                json.dumps({"type": "transcript.assistant", "text": text}).encode(),
                log_type="transcript.assistant"
            ))

    @session.on("function_tools_executed")
    def on_function_tools_executed(ev):
        """Called when tools finish executing."""
        logger.info(f"Tools executed: {ev}")

    @session.on("metrics_collected")
    def on_metrics_collected(ev):
        """Collect and log metrics."""
        logger.debug(f"Metrics: {ev}")

    # =========================================================================
    # AUDIO INPUT DEBUGGING - Track subscription events
    # =========================================================================
    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        """Track when we subscribe to remote audio tracks."""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"🎤 AUDIO TRACK SUBSCRIBED:")
            logger.info(f"   - Track SID: {track.sid}")
            logger.info(f"   - Track Source: {publication.source}")
            logger.info(f"   - Participant: {participant.identity}")
            logger.info(f"   - Track Name: {publication.name}")

            # CRITICAL DIAGNOSTIC: Count actual audio frames from this track
            async def count_audio_frames():
                """Count audio frames to verify audio is flowing."""
                import struct
                import math

                frame_count = 0
                silent_frames = 0
                max_rms = 0.0
                rms_sum = 0.0
                last_log_time = asyncio.get_event_loop().time()

                try:
                    audio_stream = rtc.AudioStream(track)
                    async for frame_event in audio_stream:
                        frame_count += 1
                        frame = frame_event.frame

                        # Check if frame is silent (all zeros or very low)
                        samples = frame.data
                        rms = 0.0
                        if samples:
                            # Calculate RMS of frame
                            try:
                                # Assuming 16-bit PCM
                                num_samples = len(samples) // 2
                                if num_samples > 0:
                                    values = struct.unpack(f'{num_samples}h', samples[:num_samples*2])
                                    rms = (sum(v*v for v in values) / num_samples) ** 0.5
                                    rms_sum += rms
                                    if rms > max_rms:
                                        max_rms = rms
                                    if rms < 100:  # Very quiet (below -50dB)
                                        silent_frames += 1
                            except Exception:
                                pass

                        # Log every 5 seconds
                        now = asyncio.get_event_loop().time()
                        if now - last_log_time > 5.0:
                            last_log_time = now
                            pct_silent = (silent_frames / frame_count * 100) if frame_count > 0 else 0
                            avg_rms = rms_sum / frame_count if frame_count > 0 else 0

                            # Convert to dB for meaningful interpretation
                            # 32767 is max for 16-bit audio, so dB = 20*log10(rms/32767)
                            max_db = 20 * math.log10(max_rms / 32767) if max_rms > 0 else -100
                            avg_db = 20 * math.log10(avg_rms / 32767) if avg_rms > 0 else -100

                            logger.info(f"📊 AUDIO FRAME STATS: {frame_count} total, {silent_frames} silent ({pct_silent:.1f}%)")
                            logger.info(f"   Sample rate: {frame.sample_rate}, Channels: {frame.num_channels}")
                            logger.info(f"   RMS: avg={avg_rms:.1f} ({avg_db:.1f}dB), max={max_rms:.1f} ({max_db:.1f}dB)")

                            # VAD threshold 0.05 with Silero typically requires > -40dB audio
                            if max_db < -50:
                                logger.warning(f"⚠️ AUDIO VERY QUIET (max {max_db:.1f}dB) - VAD may not trigger!")
                            elif pct_silent > 90:
                                logger.warning(f"⚠️ AUDIO IS MOSTLY SILENT - Check Recall.ai audio source!")
                            else:
                                logger.info(f"   ✅ Audio levels look good for VAD (threshold=0.05)")

                except Exception as e:
                    logger.error(f"Audio frame counting error: {e}")

            # Start counting in background
            asyncio.create_task(count_audio_frames())

    @ctx.room.on("track_published")
    def on_track_published(publication, participant):
        """Track when remote participants publish tracks."""
        logger.info(f"📡 TRACK PUBLISHED by {participant.identity}:")
        logger.info(f"   - Track SID: {publication.sid}")
        logger.info(f"   - Track Kind: {publication.kind}")
        logger.info(f"   - Track Source: {publication.source}")
        logger.info(f"   - Track Name: {publication.name}")

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        """Track when participants connect."""
        logger.info(f"👤 PARTICIPANT CONNECTED: {participant.identity}")
        logger.info(f"   - SID: {participant.sid}")
        logger.info(f"   - Metadata: {participant.metadata}")
        # List their current tracks
        for pub in participant.track_publications.values():
            logger.info(f"   - Has track: {pub.kind} / {pub.source} / {pub.name}")

    # Connect to room with EXPLICIT auto_subscribe=True
    # This ensures we subscribe to ALL remote participant tracks
    await ctx.connect(auto_subscribe=True)
    logger.info(f"Connected to room: {ctx.room.name}")

    # DEBUG: Log room configuration
    logger.info(f"=== ROOM DEBUG ===")
    logger.info(f"Room SID: {ctx.room.sid}")
    logger.info(f"Room name: {ctx.room.name}")
    logger.info(f"Local participant: {ctx.room.local_participant.identity if ctx.room.local_participant else 'None'}")
    logger.info(f"Remote participants: {len(ctx.room.remote_participants)}")

    # Wait for Output Media client to connect BEFORE starting session
    # This is CRITICAL - the session must link to the client participant
    # to receive audio from them
    # Timeout is 300s (5 min) - early arrival returns immediately, no delay
    async def wait_for_client_with_audio(timeout_seconds: float = 300.0) -> Optional[rtc.RemoteParticipant]:
        """Wait for the Output Media webpage client to connect AND publish audio.

        CRITICAL: We must wait for the audio track to be published, not just for
        the participant to connect. Otherwise session.start() will link to a
        participant that hasn't published audio yet.

        Returns immediately when client's audio track is detected - the timeout
        only applies if client never arrives or never publishes audio.
        """
        start_time = asyncio.get_event_loop().time()
        check_interval = 0.5  # Check every 500ms for fast response

        client_participant = None
        audio_track_found = False

        while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
            # Check current participants for the client
            for participant in ctx.room.remote_participants.values():
                if participant is None:
                    continue
                identity = getattr(participant, 'identity', None)
                if identity is None:
                    continue
                identity_lower = identity.lower()

                # Output Media client identity format: 'output-media-{session_id}'
                if identity_lower.startswith('output-media-'):
                    if client_participant is None:
                        logger.info(f"👤 Client found: {participant.identity}")
                        client_participant = participant

                    # Check if client has published an audio track
                    for pub in participant.track_publications.values():
                        if pub.kind == rtc.TrackKind.KIND_AUDIO:
                            logger.info(f"🎤 Client audio track found!")
                            logger.info(f"   - Track SID: {pub.sid}")
                            logger.info(f"   - Track Name: {pub.name}")
                            logger.info(f"   - Track Source: {pub.source}")
                            audio_track_found = True
                            break

                    if audio_track_found:
                        return participant

            await asyncio.sleep(check_interval)

        if client_participant and not audio_track_found:
            logger.warning(f"Client connected but no audio track published after {timeout_seconds}s")
            return client_participant  # Return participant anyway, maybe track will come later

        logger.warning(f"Timeout waiting for client after {timeout_seconds}s")
        return None

    logger.info("Waiting for Output Media client to connect AND publish audio (up to 5 min)...")
    client_participant = await wait_for_client_with_audio(timeout_seconds=300.0)

    if client_participant:
        # Brief delay for Web Audio API initialization (OPTIMIZED from 1.5s to 0.3s)
        await asyncio.sleep(0.3)
        logger.info(f"Client connected: {client_participant.identity}, starting session linked to them")

        # =====================================================================
        # CRITICAL: VERIFY AUDIO SUBSCRIPTION
        # The agent MUST be subscribed to the client's audio track for VAD/STT
        # to receive audio frames. This is the most common failure point.
        # =====================================================================
        logger.info("=== AUDIO SUBSCRIPTION VERIFICATION ===")

        audio_track_subscribed = False
        for pub in client_participant.track_publications.values():
            if pub.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"Audio track publication found:")
                logger.info(f"  - SID: {pub.sid}")
                logger.info(f"  - Name: {pub.name}")
                logger.info(f"  - Source: {pub.source}")
                logger.info(f"  - Is Subscribed: {pub.subscribed}")
                logger.info(f"  - Is Muted: {pub.muted}")

                if pub.subscribed:
                    audio_track_subscribed = True
                    # Get the actual track
                    track = pub.track
                    if track:
                        logger.info(f"  - Track kind: {track.kind}")
                        logger.info(f"  - Track SID: {track.sid}")
                        logger.info(f"  ✅ Audio track is subscribed and ready!")
                    else:
                        logger.warning(f"  ⚠️ Publication subscribed but track is None!")
                else:
                    # CRITICAL: Force subscription if not subscribed
                    logger.warning(f"  ⚠️ Audio track NOT subscribed! Attempting manual subscription...")
                    try:
                        pub.set_subscribed(True)
                        await asyncio.sleep(0.5)  # Give time for subscription
                        if pub.subscribed:
                            logger.info(f"  ✅ Manual subscription successful!")
                            audio_track_subscribed = True
                        else:
                            logger.error(f"  ❌ Manual subscription FAILED!")
                    except Exception as e:
                        logger.error(f"  ❌ Manual subscription error: {e}")

        if not audio_track_subscribed:
            logger.warning("⚠️ NO AUDIO TRACK SUBSCRIBED - Agent will not hear client!")
            logger.warning("   This may happen if:")
            logger.warning("   1. Client hasn't published audio yet")
            logger.warning("   2. Auto-subscribe failed")
            logger.warning("   3. Track source type doesn't match expected")
        else:
            logger.info("✅ Audio subscription verified - agent should receive audio")

        logger.info("=== END VERIFICATION ===")
    else:
        # Still start but log warning - agent won't receive audio
        logger.warning("Starting without confirmed client - audio input will not work!")

    # Start the agent session with audio configuration
    # CRITICAL: Link to the client participant via participant_identity in RoomOptions
    # This tells the session which participant to listen to and respond to
    participant_identity = client_participant.identity if client_participant else None

    try:
        # Log what we're about to configure
        logger.info(f"=== STARTING SESSION ===")
        logger.info(f"  participant_identity: {participant_identity}")
        logger.info(f"  audio_input: sample_rate=16000, num_channels=1")
        logger.info(f"  audio_output: sample_rate=24000, num_channels=1")

        # Pre-warm context cache in background while session starts
        # This fetches session context before user speaks, reducing first-query latency
        session_id = ctx.room.name or "livekit-agent"
        cache_warm_task = asyncio.create_task(warm_session_cache(session_id))

        await session.start(
            agent=agent,
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_output=room_io.AudioOutputOptions(
                    sample_rate=24000,
                    num_channels=1,
                ),
                # CRITICAL: Explicit AudioInputOptions for proper audio capture
                # Sample rate 16000 matches VAD expectation (Silero requires 16kHz)
                audio_input=room_io.AudioInputOptions(
                    sample_rate=16000,  # Match VAD sample rate
                    num_channels=1,
                ),
                # Link to specific participant's audio stream
                participant_identity=participant_identity,
                # CRITICAL: Accept ALL participant kinds, not just SIP/STANDARD
                # Recall.ai Output Media may not be recognized as STANDARD
                participant_kinds=[
                    rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD,
                    rtc.ParticipantKind.PARTICIPANT_KIND_SIP,
                    rtc.ParticipantKind.PARTICIPANT_KIND_INGRESS,
                    rtc.ParticipantKind.PARTICIPANT_KIND_EGRESS,
                ],
            ),
        )
        logger.info(f"Agent session started successfully, linked to: {participant_identity or 'first participant'}")
        logger.info(f"Audio input configured: sample_rate=16000, num_channels=1")
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
