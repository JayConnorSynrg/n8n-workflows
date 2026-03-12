"""Main LiveKit voice agent implementation.

Based on LiveKit Agents 1.3.x documentation:
- https://docs.livekit.io/agents/logic/sessions/
- https://docs.livekit.io/agents/multimodality/audio/
"""
import asyncio
import os
import json
import logging
import threading
import time
from typing import Optional
import hashlib

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

import re

# OPTIMIZED: Turn detector loaded lazily to reduce cold start (saves ~300-500ms)
# Moved from module-level import to on-demand loading in get_turn_detector()
HAS_TURN_DETECTOR = None  # Will be set on first check
_turn_detector_model = None

# Session greeting registry — prevents re-greeting on reconnect within same process
_greeted_rooms: dict = {}

# Per-session tool step counter — tracks tool calls toward max_tool_steps limit
_session_tool_call_counts: dict = {}

# AGENTS.md dedup guard — skip re-injection if content unchanged since last session injection
_injected_agents_md_hash: dict = {}

# Wake word gate state
_wake_gate_suppress: bool = False
_AIO_WAKE_PATTERN = re.compile(
    r'\b(AIO|A\.I\.O\.|aye[- ]?oh?|ayo|eyoh|eye[- ]?oh|a[- ]\.?i[- ]\.?o)\b',
    re.IGNORECASE
)
_last_agent_listening_time: float = 0.0
_WAKE_GATE_GRACE_PERIOD_SECS: float = 30.0
_CONVERSATIONAL_BYPASS_PHRASES: frozenset = frozenset({
    "thanks", "thank you", "appreciate", "cool", "nice",
    "ok", "okay", "alright", "got it", "understood", "roger",
    "yes", "yeah", "yep", "yup", "correct", "right", "exactly",
    "no", "nope", "nah", "not really",
})


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
        except Exception as e:
            HAS_TURN_DETECTOR = False
            logger.warning(f"Turn detector initialization failed: {e}")

    return _turn_detector_model if HAS_TURN_DETECTOR else None

from .config import get_settings
from .tools.email_tool import send_email_tool
from .tools.database_tool import query_database_tool
from .tools.vector_store_tool import store_knowledge_tool
from .tools.google_drive_tool import search_documents_tool, get_document_tool, list_drive_files_tool, recall_drive_data_tool
from .tools.agent_context_tool import (
    query_context_tool,
    get_session_summary_tool,
    warm_session_cache,
    invalidate_session_cache,
    set_current_session_id,
    set_current_user_id,
)
from .tools.async_wrappers import ASYNC_TOOLS, _tool_session_id
from .tools.tool_executor import (
    cleanup_session as _cleanup_tool_session,
    evaluate_and_execute_from_speech as _evaluate_and_execute_from_speech,
    is_delegation_active as _is_delegation_active,
    register_session as _register_session,
    unregister_session as _unregister_session,
)
from .tools.user_profile_tool import set_user_mem_dir as _set_profile_mem_dir
from .prompts import CONVERSATION_PROMPT
from .tools.gamma_tool import get_notification_queue
from .utils.logging import setup_logging
from .utils.metrics import LatencyTracker
from .utils.context_cache import get_cache_manager
from .utils.async_tool_worker import AsyncToolWorker, set_worker
from .utils.short_term_memory import clear_session as clear_session_memory
from .utils.task_tracker import TaskTracker
from .utils.session_facts import (
    store_fact as _store_fact,
    get_fact as _get_fact,
    get_all_facts as _get_all_facts,
    clear_facts as _clear_facts,
    flush_facts_to_db as _flush_facts_to_db,
)
from .utils import pg_logger as _pg_logger
from .utils import user_identity as _user_identity

# pgvector semantic memory (Railway Postgres) — optional, gracefully disabled
try:
    from .utils import pgvector_store as _pgvector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    _pgvector = None  # type: ignore[assignment]
    _PGVECTOR_AVAILABLE = False

# Initialize logging
logger = setup_logging(__name__)
settings = get_settings()

# Memory layer — persistent cross-session memory (optional, gracefully disabled)
try:
    from .memory import memory_store as _mem_store
    from .memory import session_writer as _session_writer
    from .memory import capture as _mem_capture
    _MEM_AVAILABLE = True
except Exception as _mem_err:
    _mem_store = None  # type: ignore[assignment]
    _session_writer = None  # type: ignore[assignment]
    _mem_capture = None  # type: ignore[assignment]
    _MEM_AVAILABLE = False


def _inject_per_turn_context(turn_ctx, new_message, session_id: str, user_mem_dir: str) -> None:
    """Inject compact per-turn context into the LLM call — survives chat_ctx trimming.

    Called from the on_user_turn_completed session event (GAPS 1 + 4).
    Injects Gamma session facts and last-tool-result into the turn's chat context
    so every LLM inference has fresh in-session state regardless of trim cycles.
    """
    parts = []

    # 1. Gamma session facts (from in-memory session_facts — always fresh)
    try:
        gamma_url = _get_fact(session_id, "gammaUrl")
        gamma_id = _get_fact(session_id, "gammaGenerationId")
        gamma_topic = _get_fact(session_id, "gammaLastTopic")
        if gamma_url or gamma_id:
            fact_parts = []
            if gamma_url:
                fact_parts.append(f"URL={gamma_url}")
            if gamma_id:
                fact_parts.append(f"generationId={gamma_id}")
            if gamma_topic:
                fact_parts.append(f"topic={gamma_topic}")
            parts.append(f"[Last Gamma] {', '.join(fact_parts)}")
    except Exception:
        pass

    # 2. Last tool result context (survives stall recovery)
    try:
        last_result = _get_fact(session_id, "last_tool_result")
        if last_result:
            parts.append(f"[Last tool result] {last_result[:200]}")
    except Exception:
        pass

    # 3. AGENTS.md routing rules from user memory dir (compact, up to 300 chars)
    # Dedup guard: skip re-injection if content unchanged since last injection for this session
    try:
        if user_mem_dir:
            agents_md_path = os.path.join(user_mem_dir, "AGENTS.md")
            if os.path.exists(agents_md_path):
                agents_content = open(agents_md_path, encoding="utf-8").read().strip()
                if agents_content and len(agents_content) > 50:
                    content_hash = hashlib.md5(agents_content.encode()).hexdigest()
                    if _injected_agents_md_hash.get(session_id) != content_hash:
                        _injected_agents_md_hash[session_id] = content_hash
                        parts.append(f"[Routing rules]\n{agents_content[:300]}")
    except Exception:
        pass

    if parts:
        context_block = "\n".join(parts)
        try:
            turn_ctx.add_message(role="assistant", content=f"[Session context]\n{context_block}")
        except Exception:
            pass


async def _session_already_greeted(room_name: str, postgres_url: str) -> bool:
    """Check conversation_log to determine if this room has prior conversation history.

    Handles the container restart re-dispatch scenario: LiveKit dispatches the same
    active room to a new container where _greeted_rooms is empty. Without this check,
    the agent would greet again even though the user was mid-session.

    Returns True  → session has prior messages; greeting must be suppressed.
    Returns False → new session; greeting should proceed.
    Falls back to False on any error (fail-open: same behavior as before this fix).

    Uses a short-lived asyncpg connection (not the pg_logger pool) so it works even
    if the pool is not yet initialized at this point in entrypoint().
    """
    if not room_name or not postgres_url:
        return False
    try:
        import asyncpg  # type: ignore
        conn = await asyncio.wait_for(
            asyncpg.connect(postgres_url, ssl="require"), timeout=3.0
        )
        try:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM conversation_log
                WHERE session_id = $1
                  AND created_at > NOW() - INTERVAL '2 hours'
                """,
                room_name,
            )
            return (count or 0) > 0
        finally:
            await conn.close()
    except Exception as _e:
        logger.debug("[Greeting] DB check failed (will greet): %s", _e)
        return False


async def _immediate_flush_critical_facts(session_id: str, user_id: str, postgres_url: str) -> None:
    """Flush only critical session facts to Postgres immediately after significant tool completions.

    Called as a fire-and-forget task from on_function_tools_executed (GAP 6).
    Uses a single short-lived asyncpg connection with a 5s timeout — never blocks the event loop.
    """
    if not session_id or not postgres_url:
        return
    try:
        critical_keys = {"gammaUrl", "gammaGenerationId", "gammaLastTopic", "last_tool_result"}
        all_facts = _get_all_facts(session_id)
        critical_facts = {k: v for k, v in all_facts.items() if k in critical_keys and v}
        if not critical_facts:
            return
        import asyncpg  # type: ignore
        conn = await asyncio.wait_for(asyncpg.connect(postgres_url, ssl="require"), timeout=5)
        try:
            for key, value in critical_facts.items():
                await conn.execute(
                    """
                    INSERT INTO session_facts_log (session_id, user_id, key, value, created_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    ON CONFLICT (session_id, key)
                    DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
                    """,
                    session_id,
                    user_id or "_default",
                    key,
                    str(value),
                )
        finally:
            await conn.close()
        logger.debug(f"[FactFlush] Flushed {len(critical_facts)} critical facts to PG")
    except Exception as _e:
        logger.debug(f"[FactFlush] Immediate flush failed (non-critical): {_e}")


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

    # Pre-build Composio tool catalog in background thread (non-blocking).
    # Worker registration proceeds immediately. If catalog finishes before
    # first meeting, it gets injected into system prompt. If not, the lazy
    # build on first composioBatchExecute call handles it.
    proc.userdata["composio_catalog"] = ""  # default empty

    def _build_catalog():
        try:
            from .tools.composio_router import prewarm_slug_index
            proc.userdata["composio_catalog"] = prewarm_slug_index()
        except Exception as e:
            logger.warning(f"Composio catalog prewarm failed: {e}")

    catalog_thread = threading.Thread(target=_build_catalog, daemon=True, name="composio-prewarm")
    catalog_thread.start()
    proc.userdata["_composio_thread"] = catalog_thread
    logger.info("Composio catalog build started in background thread")

    # Pre-initialize memory store embedding model (non-blocking — failure is tolerated).
    # Per-user reinit happens in entrypoint(); prewarm only loads the embedding model.
    if _MEM_AVAILABLE and _mem_store is not None:
        try:
            _mem_store.init()
        except Exception as _e:
            logger.warning("[Memory] Store prewarm failed (non-critical): %s", _e)

    # pgvector startup connectivity test — runs at worker boot, not per-session
    if _PGVECTOR_AVAILABLE:
        _pv_url = getattr(settings, 'pgvector_url', None)
        if _pv_url:
            import threading as _threading
            def _pgvector_startup():
                import asyncio as _asyncio
                _loop = _asyncio.new_event_loop()
                _asyncio.set_event_loop(_loop)
                try:
                    ok = _loop.run_until_complete(_pgvector.init_pgvector_pool(_pv_url))
                    logger.info(f"pgvector: startup test {'PASSED — HNSW store ready' if ok else 'FAILED — using SQLite fallback'}")
                    # One-time SQLite -> pgvector migration (idempotent, sentinel-guarded)
                    if ok:
                        try:
                            from .utils.pgvector_migration import migrate_sqlite_to_pgvector as _migrate
                            _sqlite_path = os.path.join(
                                os.environ.get("AIO_MEMORY_DIR", "/app/data/memory"),
                                "users", "_default", "aio-voice-memory.sqlite",
                            )
                            _migrated = _loop.run_until_complete(
                                _migrate(_sqlite_path, _pgvector._pool)
                            )
                            if _migrated > 0:
                                logger.info(f"pgvector migration: {_migrated} historical memories migrated")
                        except Exception as _me:
                            logger.warning(f"pgvector migration: {_me}")
                except Exception as _e:
                    logger.warning(f"pgvector: startup test FAILED: {_e}")
                finally:
                    _loop.close()
            _t = _threading.Thread(target=_pgvector_startup, daemon=True)
            _t.start()
            _t.join(timeout=7)  # Short join — 1s margin before LiveKit IPC hard limit (8s); backfill continues as daemon


async def entrypoint(ctx: JobContext):
    """Main entry point for the voice agent."""
    global _wake_gate_suppress
    _wake_gate_suppress = False

    logger.info(f"Agent starting for room: {ctx.room.name}")
    tracker = LatencyTracker()

    # ── Per-user memory routing ──────────────────────────────────────────────
    # Resolve user identity from room context so all memory (SQLite + markdown)
    # is stored in /app/data/memory/users/{user_id}/ — never shared across users.
    _base_mem_dir = settings.memory_dir  # /app/data/memory
    _room_participants = (
        list(ctx.room.remote_participants.values())
        if hasattr(ctx.room, 'remote_participants') and ctx.room.remote_participants
        else []
    )
    _user_id = _user_identity.resolve_user_id(
        room_name=ctx.room.name or "",
        room_metadata_str=getattr(ctx.room, 'metadata', None) or "",
        participants=_room_participants,
    )
    _user_mem_dir = _user_identity.get_user_mem_dir(_base_mem_dir, _user_id)
    logger.info(f"[UserIdentity] User={_user_id!r} mem_dir={_user_mem_dir}")
    _set_profile_mem_dir(_user_mem_dir)

    # Switch SQLite memory store to this user's database
    if _MEM_AVAILABLE and _mem_store is not None:
        try:
            _mem_store.reinit_for_user(_user_mem_dir)
        except Exception as _uid_err:
            logger.warning("[Memory] Per-user reinit failed (non-critical): %s", _uid_err)

    # Ensure this user's memory files (SOUL.md, USER.md, MEMORY.md) exist
    if _MEM_AVAILABLE and _session_writer is not None:
        try:
            _session_writer.ensure_memory_files(_user_mem_dir)
        except Exception as _uid_err:
            logger.warning("[Memory] Per-user file init failed: %s", _uid_err)

        # One-time seed: write recovered profile data for _default user partition
        # if files are still template-only. Idempotent — guarded by MEMORY.md sentinel.
        try:
            seed_facts = _session_writer.seed_user_profile_if_empty(_user_mem_dir)
            if seed_facts and _mem_store is not None:
                for fact in seed_facts:
                    _mem_store.store(
                        text=fact,
                        category="identity",
                        source="seed_recovery",
                        session_id="manual_recovery",
                    )
                logger.info("[Memory] Seeded %d profile facts into SQLite", len(seed_facts))
        except Exception as _seed_err:
            logger.warning("[Memory] Profile seed failed (non-critical): %s", _seed_err)
    # ── End per-user memory routing ──────────────────────────────────────────

    # ── New user detection ──────────────────────────────────────────────────
    def _resolve_participant_display_name() -> str:
        """Return the best available display name for the non-agent participant."""
        try:
            for p in ctx.room.remote_participants.values():
                ident = getattr(p, "identity", "") or ""
                if ident.lower() in ("agent", "aiagent", "aio"):
                    continue
                name = getattr(p, "name", "") or ""
                return name.strip() or ident.strip()
        except Exception:
            pass
        return ""

    def _user_profile_is_empty(mem_dir: str) -> bool:
        """Return True if USER.md exists but contains only template boilerplate."""
        import os as _os
        from .memory.session_writer import _is_template_only as _check_template
        user_md = _os.path.join(mem_dir, "USER.md")
        try:
            if not _os.path.exists(user_md):
                return True
            with open(user_md, "r", encoding="utf-8") as _f:
                return _check_template(_f.read())
        except Exception:
            return True

    _is_new_user: bool = _user_profile_is_empty(_user_mem_dir)
    _participant_display_name: str = _resolve_participant_display_name()
    logger.info("[NewUser] is_new_user=%s display_name=%r", _is_new_user, _participant_display_name)
    # ── End new user detection ───────────────────────────────────────────────

    # Reset Composio slug index per-session so newly connected services are visible
    try:
        from .tools import composio_router as _cr
        _cr._slug_index_built = False
        logger.info("[Composio] Slug index reset — will rebuild on first tool call this session")
    except Exception:  # nosec B110
        pass

    # Surface slug drift to logs during session startup (non-blocking — drift report may be None
    # if detection hasn't completed yet since it runs async after the first index build)
    try:
        from .tools.composio_router import get_slug_drift_report as _get_slug_drift_report
        _drift_report = _get_slug_drift_report()
        if _drift_report:
            logger.warning(f"AIO Session startup: SLUG_DRIFT active — {_drift_report}. Some tool calls may fail.")
    except Exception:  # nosec B110
        pass

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
        )

    def init_llm():
        """Initialize Fireworks AI LLM."""
        if not settings.fireworks_api_key:
            raise RuntimeError(
                "No LLM configured. Set FIREWORKS_API_KEY. "
                f"Model: {settings.fireworks_model}"
            )
        logger.info(f"Initializing Fireworks AI LLM: {settings.fireworks_model}")
        return openai.LLM.with_fireworks(
            model=settings.fireworks_model,
            api_key=settings.fireworks_api_key,
            temperature=settings.fireworks_temperature,
            parallel_tool_calls=True,
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
        # Allow multi-step tool flows (schema lookup → execute → retry if needed)
        "max_tool_steps": settings.max_tool_steps,
    }

    # OPTIMIZED: Add turn detection using lazy loader (non-blocking at module load)
    turn_detector = get_turn_detector()
    if turn_detector:
        session_kwargs["turn_detection"] = turn_detector
        logger.info("Using semantic turn detection")
    else:
        logger.info("Using VAD-only turn detection (faster startup)")

    session = AgentSession(**session_kwargs)

    # CHANGE 2: Per-turn context injection (GAP 1 + 4)
    # on_user_turn_completed fires after STT, before LLM inference — canonical RAG injection point.
    # Agent is an inline Agent() instance (not a subclass), so we use the session event API.
    # session_id is assigned later at line ~1970; the closure captures it by name from the
    # enclosing scope — by the time any turn fires, session_id will be set.
    # Mutable container so on_user_turn_completed closure can read session_id
    # after it is assigned later in entrypoint (closures capture by reference in Python,
    # but a plain assignment to session_id rebinds the name — using a list avoids that).
    _session_id_ref: list = [None]

    @session.on("user_turn_completed")
    def on_user_turn_completed(ev):
        """Inject per-turn context: Gamma session facts, last tool result, AGENTS.md routing."""
        try:
            turn_ctx = getattr(ev, "turn_ctx", None) or getattr(ev, "chat_ctx", None)
            new_message = getattr(ev, "new_message", None) or getattr(ev, "message", None)
            if turn_ctx is not None:
                _sid = _session_id_ref[0] or ctx.room.name or "livekit-agent"
                _tool_session_id.set(_sid)
                _inject_per_turn_context(
                    turn_ctx,
                    new_message,
                    session_id=_sid,
                    user_mem_dir=_user_mem_dir,
                )
        except Exception as _e:
            logger.debug(f"on_user_turn_completed: context injection failed: {_e}")

    def _detect_aio_wake_word(text: str) -> bool:
        """Detect AIO wake word variants in transcript text."""
        return bool(_AIO_WAKE_PATTERN.search(text))

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

    # Set global room reference for tool event publishing
    from .utils.room_publisher import set_room as _set_room, publish_error as _publish_error
    _set_room(ctx.room)
    logger.info("Room publisher initialized for tool lifecycle events")

    # Initialize async tool worker for background execution
    tool_worker = AsyncToolWorker(room=ctx.room, max_concurrent=3)

    # Register result callback BEFORE starting (defined later, uses session)
    # The callback will be set after session is created
    await tool_worker.start()
    set_worker(tool_worker)
    logger.info("AsyncToolWorker started - tools will execute in background")

    # Build tool list: n8n webhook tools + Composio SDK execution wrappers
    all_tools = list(ASYNC_TOOLS)

    # Read pre-built Composio catalog from prewarm (zero latency — no network calls here)
    # If background thread is still running, proceed without catalog (lazy build handles it)
    composio_thread = ctx.proc.userdata.get("_composio_thread")
    if composio_thread and composio_thread.is_alive():
        logger.info("Composio catalog still building in background, proceeding without")
    composio_catalog = ctx.proc.userdata.get("composio_catalog", "")
    if settings.composio_api_key:
        logger.info(f"Composio: SDK enabled, catalog {'ready' if composio_catalog else 'empty'} ({len(all_tools)} tools)")
    else:
        logger.info("Composio: Disabled (no COMPOSIO_API_KEY)")

    logger.info(f"Agent tools: {len(all_tools)} total")

    # Inject pre-loaded catalog into system prompt via {COMPOSIO_CATALOG} marker
    active_prompt = CONVERSATION_PROMPT
    if composio_catalog:
        active_prompt = active_prompt.replace(
            "{COMPOSIO_CATALOG}",
            composio_catalog,
        )
    else:
        active_prompt = active_prompt.replace(
            "{COMPOSIO_CATALOG}",
            "No connected services catalog available. Use manageConnections with action status to check what is connected.",
        )

    # Inject current date/time context (no tool call needed)
    from datetime import datetime, timezone, timedelta
    est = timezone(timedelta(hours=-5))
    now = datetime.now(est)
    time_context = (
        f"\n\nCURRENT DATE AND TIME\n"
        f"{now.strftime('%Y-%m-%d %I:%M %p')} EST\n"
        f"{now.strftime('%A, %B %d, %Y')}\n"
        f"Always reference EST when discussing time"
    )
    active_prompt += time_context

    # MEMORY SAVE ENFORCEMENT — injected before memory context so it applies globally
    _save_enforcement = (
        "\n\n## MEMORY SAVE RULE (NON-NEGOTIABLE)\n"
        "NEVER say 'saved', 'stored', 'noted', 'I'll remember that', or any save confirmation "
        "UNTIL you have received a successful response from deepStore, updateUserProfile, or addContact. "
        "The sequence is always: call tool → receive success response → then confirm to user. "
        "If the user says 'remember X', 'save X', 'my favorite X is Y', 'note that' — "
        "call deepStore immediately with the content and a descriptive label. "
        "Do not ask permission. Do not delay. Call deepStore first, then confirm."
    )
    active_prompt += _save_enforcement

    # Load cross-session memory context for this user and inject into instructions
    _memory_context = ""
    if _MEM_AVAILABLE and _session_writer is not None:
        try:
            _memory_context = _session_writer.load_memory_context(_user_mem_dir, max_tokens=500)
        except Exception as _e:
            logger.warning("[Memory] Context load failed: %s", _e)

    if _memory_context:
        active_prompt = active_prompt + "\n\n## Cross-Session Memory\n" + _memory_context
        # Instruct agent to reference session list at greeting
        _session_list_instruction = (
            "\n\nWhen you see 'Recent Sessions' in the context above: "
            "at the START of your first response, briefly mention what you've been working on "
            "(e.g., 'I can see we worked on X and Y this week') "
            "and offer to recall full details from any session if needed."
        )
        active_prompt = active_prompt + _session_list_instruction

    if _is_new_user:
        _name_hint = (
            f" Their display name or ID appears to be '{_participant_display_name}'."
            if _participant_display_name else ""
        )
        _new_user_section = (
            "\n\n## NEW USER IDENTIFICATION (this session only)\n"
            f"You are meeting someone whose profile you don't yet have on file.{_name_hint}\n\n"
            "STEP 0 — Before anything else: call recall(\"user profile identity name\") to check "
            "if you already know this person from a previous session.\n"
            "- If recall returns their name and details: greet them by name and SKIP the onboarding below.\n"
            "- If recall returns nothing useful: proceed with the onboarding sequence.\n\n"
            "Onboarding sequence (only when recall finds nothing):\n"
            "1. After greeting, mention you haven't built a profile for them yet and ask if "
            "they'd like you to remember them going forward.\n"
            "2. If yes — ask their name, role/title, and company one at a time, conversationally.\n"
            "3. Call updateUserProfile with name, role, and company — this saves them permanently "
            "so you'll recognize them next session.\n"
            "4. Call deepStore to save: \"User profile: [Name], [Role] at [Company], "
            "first session [today's date]\"\n"
            "5. Call searchContacts with their name to check if they're already a saved contact.\n"
            "6. If not in contacts, ask if they'd like to be added. If yes, use addContact.\n"
            "7. Once complete, proceed normally with whatever they need.\n\n"
            "Keep this natural and brief — one exchange at a time, never like a form. "
            "If they decline to be remembered, respect that and move on immediately."
        )
        active_prompt = active_prompt + _new_user_section

    # Define agent with all tools (no MCP servers)
    agent = Agent(
        instructions=active_prompt,
        tools=all_tools,
    )

    # In-session task tracker — monitors tool execution progress for heartbeat continuation
    _task_tracker = TaskTracker(
        stall_threshold_seconds=6.0,          # 6s stall before Case 1/3 triggers
        max_continuations_per_objective=5,    # 5 attempts before giving up
        min_continuation_gap_seconds=8.0,     # 8s cooldown between Case 2/3 injections
    )

    # Register tracker with composio_router so it can call record_tool_call_started()
    # before slug resolution begins, preventing heartbeat CASE 2 false-positive fires.
    try:
        from .tools.composio_router import set_task_tracker as _set_composio_tracker
        _set_composio_tracker(_task_tracker)
    except Exception:  # nosec B110 — tracker registration is optional; never block entrypoint
        pass

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

        # Track user objective for heartbeat-driven continuation
        if text:
            _task_tracker.record_user_message(text)
            # Log user turn to PostgreSQL for full session context
            asyncio.create_task(_pg_logger.log_turn(session_id, "user", text, user_id=_user_id))

        # Publish user transcript to client for UI display
        asyncio.create_task(safe_publish_data(
            json.dumps({
                "type": "transcript.user",
                "text": text or "",
                "is_final": True
            }).encode(),
            log_type="transcript.user"
        ))

        # Wake word gate: suppress agent response if no wake word detected
        # and no active task objective is currently being executed
        global _wake_gate_suppress
        _transcript_text = text or ''
        _has_wake_word = _detect_aio_wake_word(_transcript_text)
        _has_active_task = (
            _task_tracker is not None
            and getattr(_task_tracker, '_current_objective', None) is not None
            and not getattr(_task_tracker, '_objective_completed', True)
        )
        # Grace period: bypass gate within 2.5s of agent finishing speaking
        _secs_since_listened = time.time() - _last_agent_listening_time
        _in_grace_period = (
            _last_agent_listening_time > 0
            and _secs_since_listened < _WAKE_GATE_GRACE_PERIOD_SECS
        )
        # Conversational bypass: short acknowledgments always pass through
        _is_conversational = any(
            phrase in _transcript_text.lower() for phrase in _CONVERSATIONAL_BYPASS_PHRASES
        )

        if _has_wake_word:
            _wake_gate_suppress = False
            logger.debug("[WakeGate] Wake word detected — response allowed")
        elif _in_grace_period or _is_conversational:
            _wake_gate_suppress = False
            logger.debug("[WakeGate] Grace period bypass (%.1fs since listening, conversational=%s)", _secs_since_listened, _is_conversational)
        elif not _has_active_task:
            _wake_gate_suppress = True
            logger.debug("[WakeGate] No wake word — suppressing next response")
            # Interrupt immediately before preemptive generation can commit text to chat.
            # This eliminates the race condition where preemptive_generation=True causes the
            # LLM to commit text to conversation_item_added BEFORE on_agent_state_changed("thinking")
            # fires — resulting in chat text with silent audio.
            try:
                session.interrupt()
                logger.debug("[WakeGate] Preemptive interrupt() issued at transcription time")
            except Exception as _wg_err:
                logger.debug("[WakeGate] Preemptive interrupt() call failed: %s", _wg_err)
        # If _has_active_task and no wake word: allow continuation of current task (don't suppress)

        # Parallel tool track: fire background evaluation simultaneously with conversation LLM
        # Fires when gate allows (wake word / grace period / active task) and transcript is substantive
        if not _wake_gate_suppress and text and len(text.split()) >= 3:
            _eval_ctx: list[str] = []
            try:
                _chat_ctx_obj = _get_chat_ctx(session)
                if _chat_ctx_obj and hasattr(_chat_ctx_obj, "messages"):
                    _eval_ctx = [
                        m.content for m in list(_chat_ctx_obj.messages)[-4:]
                        if getattr(m, "role", "") in ("user", "assistant")
                        and getattr(m, "content", None)
                    ]
            except Exception:
                pass
            _eval_gamma_url = ""
            try:
                _eval_gamma_url = _get_fact(session_id, "gammaUrl") or ""
            except Exception:
                pass
            _eval_ctx_hints: dict = {"user_id": _user_id}
            if _eval_gamma_url:
                _eval_ctx_hints["gammaUrl"] = _eval_gamma_url
            asyncio.create_task(
                _evaluate_and_execute_from_speech(
                    transcript=text,
                    session_id=session_id,
                    context_hints=_eval_ctx_hints,
                    recent_context=_eval_ctx,
                )
            )

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev):
        """Agent state: initializing, idle, listening, thinking, speaking."""
        state = ev.new_state if hasattr(ev, 'new_state') else str(ev)
        logger.debug(f"Agent state changed: {state}")

        state_str = str(state).lower()
        if "thinking" in state_str:
            # Wake word gate: reset suppress flag if it was set (interrupt already fired at
            # transcription time in on_user_input_transcribed — no second interrupt needed here)
            global _wake_gate_suppress
            if _wake_gate_suppress:
                _wake_gate_suppress = False  # Reset flag; interrupt already issued upstream
                logger.info("[WakeGate] Suppress flag reset in thinking state — interrupt already fired at transcription")
                _task_tracker.record_agent_responding()  # Fix 2A: task tracker must see LLM inference even when gate suppressed
                return  # Skip remaining state handling
            _task_tracker.record_agent_responding()
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
            global _last_agent_listening_time
            _last_agent_listening_time = time.time()
            _task_tracker.record_agent_idle()
            asyncio.create_task(safe_publish_data(
                b'{"type":"agent.state","state":"listening"}',
                log_type="agent.state"
            ))
        elif "idle" in state_str:
            # Fix 2B: do NOT update _last_agent_listening_time here — idle fires on every
            # tool execution pause, which resets the 30s grace period clock prematurely.
            # Grace period clock is only reset when the agent enters "listening" (post-speech).
            _task_tracker.record_agent_idle()
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

        # Auto-capture memory triggers from user utterances
        if _MEM_AVAILABLE and _mem_capture is not None:
            try:
                # Only capture from user messages, not agent responses
                if hasattr(item, 'role') and str(getattr(item, 'role', '')).lower() == 'user':
                    _text = ""
                    if hasattr(item, 'text_content'):
                        _text = item.text_content or ""
                    elif hasattr(item, 'content') and isinstance(item.content, str):
                        _text = item.content
                    if _text:
                        _mem_capture.detect_and_queue(_text)
            except Exception as _e:
                logger.debug("[Memory] Capture check failed: %s", _e)

        if role != 'assistant':
            return  # Only publish agent responses, user transcripts handled separately

        # Wake gate: don't publish agent text if response was suppressed
        # This prevents split-brain where chat shows text but audio is silent
        if _wake_gate_suppress:
            logger.debug("[WakeGate] Blocking suppressed assistant message from chat publication")
            return

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
            # OpenClaw-style interim-phrase detection: feed agent speech to task
            # tracker so Case 3 stall detection can arm if the LLM says something
            # like "let me try" or "working on it" without calling a tool.
            _task_tracker.record_agent_speech(text)
            # Log assistant turn to PostgreSQL for full session context
            if text:
                asyncio.create_task(_pg_logger.log_turn(session_id, "assistant", text, user_id=_user_id))

    @session.on("function_tools_executed")
    def on_function_tools_executed(ev):
        """Called when tools finish executing."""
        logger.info(f"Tools executed: {ev}")
        # Notify task tracker that tool work completed — heartbeat uses this
        # to determine whether a multi-step task was in progress
        _task_tracker.record_tool_call_completed()

        # CHANGE 4 (GAP 7): Background tools handle their own completion notification via
        # _gamma_notification_monitor / handle_tool_result — suppress the automatic LLM
        # reply that LiveKit would otherwise generate from the tool result.
        # cancel_tool_reply() confirmed in LiveKit Agents v1.3.12 — wrapped in try/except
        # so AttributeError on older builds is silently swallowed and never breaks tool flow.
        _BACKGROUND_TOOLS = frozenset({
            "generatePresentation", "generateDocument", "generateWebpage", "generateSocial",
            "composioBatchExecute", "runLeadGen", "scrapeProspects",
        })
        try:
            # Try .zipped() first (LiveKit >= 1.3.x FunctionToolsExecuted event API)
            _tool_names_bg = {call.name for call, _ in ev.zipped()}
            if _tool_names_bg & _BACKGROUND_TOOLS:
                ev.cancel_tool_reply()
                logger.debug(
                    f"[ToolGate] Suppressed LLM reply for background tools: "
                    f"{_tool_names_bg & _BACKGROUND_TOOLS}"
                )
        except AttributeError:
            # cancel_tool_reply or .zipped() not available in this SDK build — skip silently
            pass
        except Exception as _bg_e:
            logger.debug(f"[ToolGate] cancel_tool_reply check failed: {_bg_e}")

        # Load tool call result into session facts so the LLM is aware of what
        # already ran. Prevents re-calling gamma tools (or any tool) on heartbeat
        # continuation turns where the LLM would otherwise have no call history.
        try:
            tool_name = (
                getattr(ev, 'name', None)
                or getattr(ev, 'function_name', None)
                or getattr(ev, 'tool_name', None)
                or ''
            )
            tool_output = str(getattr(ev, 'output', '') or getattr(ev, 'result', '') or '')
            if tool_name:
                _store_fact(session_id, 'last_tool_called', tool_name)
                if tool_output:
                    _store_fact(session_id, 'last_tool_output', tool_output[:300])
                # Gamma-specific: flag that generation was started so the LLM
                # can reference it in follow-up turns without re-triggering
                if tool_name in ('generatePresentation', 'generateDocument', 'generateWebpage'):
                    _store_fact(session_id, 'gamma_generation_started', tool_name)
                    _store_fact(session_id, 'gamma_generation_output', tool_output[:300])
                    logger.info(f"[GammaTracker] Stored {tool_name} call in session facts")
        except Exception as e:
            logger.debug(f"on_function_tools_executed: session fact storage skipped: {e}")

        # CHANGE 3 (GAP 2): Store the first successful tool result under the canonical
        # "last_tool_result" key so per-turn context injection (on_user_turn_completed)
        # and heartbeat continuations can surface it to the LLM without re-fetching.
        try:
            # Prefer .zipped() which gives (FunctionCallInfo, FunctionCallOutput) pairs
            for _call, _output in ev.zipped():
                if _output is not None and not getattr(_output, "is_error", False):
                    _result_text = str(_output.output)[:300] if getattr(_output, "output", None) else ""
                    if _result_text:
                        _store_fact(session_id, "last_tool_result", _result_text)
                        break  # Store only the first successful result
        except AttributeError:
            # .zipped() not available — fall back to flat event attributes already stored
            # as last_tool_output above; map that to last_tool_result for key consistency
            try:
                _existing = _get_fact(session_id, "last_tool_output")
                if _existing:
                    _store_fact(session_id, "last_tool_result", _existing)
            except Exception:
                pass
        except Exception as _e:
            logger.debug(f"on_function_tools_executed: last_result store failed: {_e}")

        # CHANGE 5 (GAP 6): Immediately persist critical facts to Postgres after significant
        # tool completions — don't wait for session end.  Fire-and-forget via create_task.
        try:
            _critical_fact_keys = ("gammaUrl", "gammaGenerationId", "gammaLastTopic", "last_tool_result")
            _has_critical = any(
                _get_fact(session_id, k)
                for k in _critical_fact_keys
            )
            if _has_critical and settings.postgres_url:
                asyncio.create_task(
                    _immediate_flush_critical_facts(
                        session_id,
                        _user_id,
                        settings.postgres_url,
                    )
                )
        except Exception as _flush_e:
            logger.debug(f"[FactFlush] Critical fact flush check failed: {_flush_e}")

        # Fix 4D: Per-session tool step counter — warns LLM when approaching max_tool_steps.
        # Uses module-level dict keyed by session_id; cleared at session disconnect.
        try:
            _session_tool_call_counts[session_id] = _session_tool_call_counts.get(session_id, 0) + 1
            _step_count = _session_tool_call_counts[session_id]
            _step_limit = getattr(settings, "max_tool_steps", 20)
            _warn_at = _step_limit - 2  # Warn 2 steps before hard cap
            if _step_count == _warn_at:
                logger.warning(
                    f"[ToolSteps] Session {session_id[:8]} approaching max_tool_steps "
                    f"({_step_count}/{_step_limit})"
                )
                try:
                    _warn_msg = (
                        f"[System] You have used {_step_count} of {_step_limit} allowed tool steps "
                        f"in this turn. Prioritize completing the current task or summarize "
                        f"progress before calling more tools."
                    )
                    session.chat_ctx.add_message(role="system", content=_warn_msg)
                except Exception as _ctx_e:
                    logger.debug(f"[ToolSteps] chat_ctx injection failed: {_ctx_e}")
        except Exception as _step_e:
            logger.debug(f"[ToolSteps] Step counter update failed: {_step_e}")

        # Fix 4A: Invalidate the session context cache so the next checkContext call
        # fetches fresh data instead of returning stale pre-tool-call cached results.
        # invalidate_session_cache is already imported at module level.
        try:
            invalidate_session_cache(session_id)
        except Exception as _inv_e:
            logger.debug(f"[CacheInvalidate] Session cache invalidation failed: {_inv_e}")

    @session.on("metrics_collected")
    def on_metrics_collected(ev):
        """Collect and log metrics."""
        logger.debug(f"Metrics: {ev}")

    # =========================================================================
    # ASYNC TOOL RESULT HANDLER - AIO ECOSYSTEM v2
    # - No punctuation in voice output
    # - 20% programmatic wit (contextually relevant)
    # - Clean conversational announcements
    # =========================================================================

    import random

    # Standard announcements (no punctuation for voice)
    STANDARD_SUCCESS = [
        "Done",
        "All set",
        "Completed",
        "Finished",
    ]

    # Witty announcements (20% chance, contextually matched)
    WITTY_RESPONSES = {
        "email": [
            "Message delivered faster than a carrier pigeon",
            "Email sent and on its way",
            "Done that message is flying through the internet",
        ],
        "search": [
            "Found your needle in the digital haystack",
            "Eureka that is exactly what you were looking for",
            "Got some results for you",
        ],
        "save": [
            "Locked and loaded in the vault",
            "Saved and secure in the knowledge base",
            "Information stored successfully",
        ],
        "document": [
            "Found the document you needed",
            "Got that file pulled up",
            "Retrieved the document",
        ],
        "error": [
            "Hit a snag on that one let me try a different approach",
            "That did not work as expected want to try again",
            "Ran into an issue there",
        ],
    }

    def strip_punctuation(text: str) -> str:
        """Remove all punctuation from text for voice output."""
        import re
        # Remove common punctuation but keep apostrophes in contractions
        text = re.sub(r'[.,!?;:\-"\(\)\[\]{}]', '', text)
        # Clean up extra spaces
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def get_witty_response(tool_type: str) -> str:
        """Get a contextually relevant witty response."""
        responses = WITTY_RESPONSES.get(tool_type, WITTY_RESPONSES.get("save", []))
        return random.choice(responses) if responses else "Done"

    def format_tool_result_v2(tool_name: str, result: str, status: str) -> str:
        """Format tool result with 20% wit probability, no punctuation.

        Handles both core tools (sendEmail, searchDrive) and Composio tools
        (composio:batch:TEAMS_SEND+DRIVE_LIST). For Composio tools, the result
        string already contains voice-friendly text from _extract_voice_result.
        """

        # Determine tool type for contextual responses
        tool_lower = tool_name.lower()
        tool_type = "save"  # default
        if "email" in tool_lower or "gmail" in tool_lower or "send" in tool_lower:
            tool_type = "email"
        elif "search" in tool_lower or "query" in tool_lower or "find" in tool_lower or "list" in tool_lower:
            tool_type = "search"
        elif "document" in tool_lower or "file" in tool_lower or "drive" in tool_lower:
            tool_type = "document"
        elif "store" in tool_lower or "save" in tool_lower or "add" in tool_lower:
            tool_type = "save"
        elif "teams" in tool_lower or "slack" in tool_lower or "message" in tool_lower:
            tool_type = "email"  # messaging maps to email-like announcements

        if status == "failed":
            tool_type = "error"

        # For Composio tools, the result already has voice-friendly text
        # from _extract_voice_result — use it directly if substantive
        is_composio = tool_name.startswith("composio:")
        if is_composio and result and len(result) > 10 and status != "failed":
            clean_result = strip_punctuation(result[:150])
            return clean_result

        # 20% chance for witty response
        use_wit = random.random() < 0.20

        if use_wit:
            announcement = get_witty_response(tool_type)
        else:
            # Standard announcement based on tool type
            if status == "failed":
                announcement = "That did not work want to try again"
            elif tool_type == "email":
                announcement = "Sent"
            elif tool_type == "search":
                # Include summary of what was found
                if result and len(result) > 10:
                    clean_result = strip_punctuation(result[:120])
                    announcement = f"Here is what I found {clean_result}"
                else:
                    announcement = "Search complete"
            elif tool_type == "document":
                announcement = "Got the document"
            else:
                announcement = random.choice(STANDARD_SUCCESS)

        # Ensure no punctuation in final output
        return strip_punctuation(announcement)

    async def handle_tool_result(result_data: dict):
        """Handle async tool result with AIO v2 conversational announcement."""
        tool_name = result_data.get("tool_name", "unknown")
        status = result_data.get("status", "unknown")
        result = result_data.get("result", "")
        error = result_data.get("error", "")
        duration = result_data.get("duration_ms", 0)

        logger.info(f"Tool result: {tool_name} status={status} duration={duration}ms result_preview={str(result)[:120]}")

        # Detect soft errors — tool returned normally but with error content
        is_soft_error = result and ("I was not able to" in result or "do not retry" in result)

        if is_soft_error:
            # Tool completed but with an error message — announce as failure
            announcement = "That tool ran into an issue let me know if you want to try something else"
            try:
                await session.say(announcement, allow_interruptions=True)
            except Exception as e:
                logger.error(f"Failed to announce soft error: {e}")

        elif status == "completed":
            announcement = format_tool_result_v2(tool_name, result, status)
            try:
                await session.say(announcement, allow_interruptions=True)
            except Exception as e:
                logger.error(f"Failed to announce result: {e}")

        elif status == "failed":
            announcement = format_tool_result_v2(tool_name, error, status)

            try:
                await session.say(announcement, allow_interruptions=True)
            except Exception as e:
                logger.error(f"Failed to announce error: {e}")

    # Register callback on worker for direct notification
    tool_worker.on_result = handle_tool_result
    logger.info("Tool result callback registered on AsyncToolWorker")

    # Also listen for data_received for external tool results (from other participants)
    @ctx.room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        """Handle incoming data packets from OTHER participants."""
        try:
            message = json.loads(data.data.decode("utf-8"))
            msg_type = message.get("type", "")

            if msg_type == "tool_result":
                # Only handle if from external source (not our own worker)
                # Our worker notifies directly via callback
                task_id = message.get("task_id", "")
                if not task_id.startswith("task_"):
                    # External task, handle it
                    asyncio.create_task(handle_tool_result(message))

        except json.JSONDecodeError:
            pass  # Ignore non-JSON data
        except Exception as e:
            logger.error(f"Error handling data packet: {e}")

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
                            except Exception:  # nosec B110 - audio frame RMS calc is best-effort
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

        # Check if this is a new user we haven't profiled yet (late-join identification)
        try:
            _joining_ident = getattr(participant, "identity", "") or ""
            _joining_name = getattr(participant, "name", "") or _joining_ident
            if _joining_ident.lower() not in ("agent", "aiagent", "aio") and _joining_ident:
                _joining_user_id = _user_identity.resolve_user_id(
                    room_name=ctx.room.name or "",
                    room_metadata_str=getattr(ctx.room, "metadata", None) or "",
                    participants=[participant],
                )
                _joining_mem_dir = _user_identity.get_user_mem_dir(_base_mem_dir, _joining_user_id)
                if _user_profile_is_empty(_joining_mem_dir):
                    logger.info("[NewUser] Late-join new user detected: %r — queuing identification", _joining_ident)
                    asyncio.create_task(
                        session.generate_reply(
                            instructions=(
                                f"A participant named '{_joining_name}' just joined. "
                                "You haven't met them before. Greet them warmly and offer to add them "
                                "to your memory. Follow the NEW USER IDENTIFICATION flow: ask their name "
                                "(if not confirmed), role, and company one at a time. Use deepStore to save "
                                "their profile, then check searchContacts and offer addContact if needed."
                            )
                        )
                    )
        except Exception as _e:
            logger.debug("[NewUser] on_participant_connected identification check failed: %s", _e)

    # Connect to room with EXPLICIT auto_subscribe=True
    # This ensures we subscribe to ALL remote participant tracks
    await ctx.connect(auto_subscribe=True)
    logger.info(f"Connected to room: {ctx.room.name}")

    # DEBUG: Log room configuration
    logger.info(f"=== ROOM DEBUG ===")
    room_sid = await ctx.room.sid
    logger.info(f"Room SID: {room_sid}")
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
        _session_id_ref[0] = session_id  # Update ref so on_user_turn_completed closure sees it
        set_current_session_id(session_id)
        set_current_user_id(_user_id)
        _register_session(session_id, session)
        if _MEM_AVAILABLE and _mem_capture is not None:
            _mem_capture.set_user_id(_user_id)
        cache_warm_task = asyncio.create_task(warm_session_cache(session_id))
        # Initialize pg_logger pool once per session (idempotent — checks if already initialized)
        if settings.postgres_url:
            await _pg_logger.init_pool(settings.postgres_url)
            asyncio.create_task(_pg_logger.log_session_start(session_id, _user_id, ctx.room.name))

        # Initialize pgvector semantic memory store (once per worker lifetime — idempotent on subsequent sessions)
        _pgvector_url = getattr(settings, 'pgvector_url', None)
        if _pgvector_url and _PGVECTOR_AVAILABLE:
            try:
                await _pgvector.init_pgvector_pool(_pgvector_url)
                logger.info("pgvector: semantic memory store ready")
            except Exception as _pge:
                logger.warning("pgvector: init failed (SQLite fallback active): %s", _pge)

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
        try:
            await _publish_error(str(e)[:200], code="agent_error", severity="high")
        except Exception:  # nosec B110 - error publishing must not block error handling
            pass
        raise

    # ── New user detection ────────────────────────────────────────────────────
    # Check SQLite memory store: if empty → new user, log and seed first entry.
    # If returning → memory context is already injected into the system prompt above.
    if _MEM_AVAILABLE and _mem_store is not None:
        try:
            _existing_memories = await asyncio.to_thread(_mem_store.search, "user session", k=1)
            _is_new_user = len(_existing_memories) == 0
            if _is_new_user:
                logger.info("[Heartbeat] New user detected — no prior memories in store")
                await asyncio.to_thread(
                    _mem_store.store,
                    "AIO session started for new user",
                    category="fact",
                    source="session",
                )
                logger.info("[Heartbeat] New user entry recorded in memory store")
            else:
                logger.info(f"[Heartbeat] Returning user — {len(_existing_memories)} prior memory entries found")
        except Exception as _nud_err:
            logger.debug(f"[Heartbeat] New user detection failed (non-critical): {_nud_err}")

    # Generate AIO opening greeting (no punctuation - voice output)
    # Interruptions disabled to allow client AEC (Acoustic Echo Cancellation) calibration
    #
    # Two-layer guard:
    #   1. _greeted_rooms dict — fast in-process guard (same container reconnects).
    #   2. conversation_log DB check — handles container restart re-dispatch where
    #      _greeted_rooms is empty in the new process but the session has prior history.
    if not _greeted_rooms.get(ctx.room.name):
        # Guard against container restart re-dispatch: check if this room has prior
        # conversation history in the DB. If so, suppress the greeting — the user was
        # already mid-session and the container restart is transparent to them.
        _should_greet = True
        if settings.postgres_url:
            _already_greeted_db = await _session_already_greeted(ctx.room.name, settings.postgres_url)
            if _already_greeted_db:
                _should_greet = False
                _greeted_rooms[ctx.room.name] = True  # prevent future in-process re-greet
                logger.info(
                    "[Greeting] Suppressed — container restart recovery for room %s "
                    "(session has prior conversation history)",
                    ctx.room.name,
                )

        if _should_greet:
            try:
                await session.say(
                    "Hi I am AIO welcome to your ecosystem infinite possibilities at our fingertips where should we start",
                    allow_interruptions=False
                )
                _greeted_rooms[ctx.room.name] = True
                logger.info("AIO greeting sent successfully")
            except Exception as e:
                logger.error(f"CRITICAL: session.say() failed: {e}")
                try:
                    await _publish_error(str(e)[:200], code="agent_error", severity="high")
                except Exception:  # nosec B110 - error publishing must not block error handling
                    pass
    else:
        logger.info("[Session] Reconnect detected — skipping greeting for room: %s", ctx.room.name)

    # Start Gamma notification monitor — watches the module-level queue and proactively
    # speaks completion messages when background presentation generation finishes.
    # Stored in a variable to prevent garbage collection; cancelled naturally when the
    # enclosing coroutine (entrypoint) exits and the event loop tears down.
    async def _gamma_notification_monitor(session_ref):
        """Monitor gamma notification queue and proactively speak results.

        This runs as a persistent background task for the duration of the session.
        When Gamma generation completes (~45s), the background poller puts a
        notification into the queue and this monitor speaks it via session.say().
        """
        queue = get_notification_queue()
        while True:
            try:
                notification = await queue.get()
                message = notification.get("message", "")
                job_id = notification.get("job_id", "?")
                content_type = notification.get("content_type", "content")
                gamma_url = notification.get("gamma_url")
                topic = notification.get("topic", "")

                if message:
                    logger.info(f"Gamma monitor: speaking notification job={job_id} content_type={content_type} has_url={bool(gamma_url)}")
                    try:
                        _gamma_offer_instructions = (
                            f"The Gamma {content_type} on '{topic}' is ready. "
                            f"The URL is {gamma_url if gamma_url else 'stored in session facts'} — do NOT say this URL aloud. "
                            f"Tell the user their {content_type} is complete in one sentence, "
                            f"then offer to email them the link. "
                            f"Example: 'Your {content_type} on {topic} is ready — want me to email you the link?'"
                        )
                        await session_ref.generate_reply(instructions=_gamma_offer_instructions)
                        logger.info(f"Gamma monitor: notification delivered job={job_id}")

                        # Store Gamma context in session facts for multi-turn coherence.
                        # Without this, the LLM has no record of gammaUrl across correction
                        # turns and re-generates the full document on every follow-up.
                        generation_id = notification.get("generation_id", "")
                        if gamma_url:
                            _store_fact(session_id, f"gamma_{content_type}_url", gamma_url)
                            _store_fact(session_id, f"gamma_{content_type}_topic", topic)
                            if generation_id:
                                _store_fact(
                                    session_id,
                                    f"gamma_{content_type}_generation_id",
                                    generation_id,
                                )
                            # Canonical keys — always overwrite so agent_context_tool
                            # can read the most-recent Gamma result without knowing content_type
                            _store_fact(session_id, "gammaUrl", gamma_url)
                            _store_fact(session_id, "gammaLastTopic", topic)
                            if generation_id:
                                _store_fact(session_id, "gammaGenerationId", generation_id)

                        # session_facts already stores the URL persistently for follow-up
                        # turns via checkContext/_append_gamma_facts. No chat_ctx injection
                        # needed — injecting an assistant message here confuses LiveKit's
                        # turn-completion detection and can cause the reply to be suppressed.
                    except Exception as say_err:
                        logger.error(f"Gamma monitor: session.say() failed job={job_id}: {say_err}")
                        # Retry once after brief delay (session may be transitioning)
                        await asyncio.sleep(1.0)
                        try:
                            _retry_offer_instructions = (
                                f"The Gamma {content_type} on '{topic}' is ready. "
                                f"The URL is {gamma_url if gamma_url else 'stored in session facts'} — do NOT say this URL aloud. "
                                f"Tell the user their {content_type} is complete in one sentence, "
                                f"then offer to email them the link. "
                                f"Example: 'Your {content_type} on {topic} is ready — want me to email you the link?'"
                            )
                            await session_ref.generate_reply(instructions=_retry_offer_instructions)
                            logger.info(f"Gamma monitor: retry notification delivered job={job_id}")
                        except Exception as retry_err:
                            logger.error(f"Gamma monitor: retry also failed job={job_id}: {retry_err}")
                else:
                    # Silent notification (e.g. instant completion path) — no voice output,
                    # but still perform session_facts + chat_ctx injection so the LLM has the URL
                    if gamma_url:
                        logger.info(f"Gamma monitor: silent notification — injecting context job={job_id} url={gamma_url[:60]}")
                        generation_id = notification.get("generation_id", "")
                        _store_fact(session_id, f"gamma_{content_type}_url", gamma_url)
                        _store_fact(session_id, f"gamma_{content_type}_topic", topic)
                        if generation_id:
                            _store_fact(session_id, f"gamma_{content_type}_generation_id", generation_id)
                        # Canonical keys — always overwrite so agent_context_tool
                        # can read the most-recent Gamma result without knowing content_type
                        _store_fact(session_id, "gammaUrl", gamma_url)
                        _store_fact(session_id, "gammaLastTopic", topic)
                        if generation_id:
                            _store_fact(session_id, "gammaGenerationId", generation_id)
                        # Deliver the result via generate_reply so LiveKit produces actual
                        # speech. Injecting a silent assistant message into chat_ctx was
                        # causing LiveKit to consider the turn already answered → agent
                        # went to listening silently → heartbeat CASE 1 fired → second
                        # Gamma generation started. generate_reply forces a real LLM turn.
                        try:
                            instructions = (
                                f"The Gamma {content_type} on '{topic}' is ready. "
                                f"The URL is {gamma_url} — do NOT say this URL aloud. "
                                + (f"Generation ID: {generation_id}. " if generation_id else "")
                                + f"Tell the user their {content_type} is complete in one sentence, "
                                f"then offer to email them the link. "
                                f"Do NOT call generatePresentation/generateDocument/generateWebpage again."
                            )
                            await session_ref.generate_reply(instructions=instructions)
                            logger.info(f"Gamma monitor: silent path — generate_reply delivered job={job_id}")
                        except AttributeError:
                            logger.warning(f"Gamma monitor: generate_reply unavailable, falling back to say() job={job_id}")
                            try:
                                fallback_msg = f"Your Gamma {content_type} on '{topic}' is ready. Here's the link: {gamma_url}"
                                await session_ref.say(fallback_msg, allow_interruptions=True)
                            except Exception as say_err:
                                logger.error(f"Gamma monitor: silent fallback say() failed job={job_id}: {say_err}")
                        except Exception as gen_err:
                            logger.error(f"Gamma monitor: generate_reply failed job={job_id}: {gen_err}")
                    else:
                        logger.warning(f"Gamma monitor: empty message and no gamma_url in notification job={job_id}")

            except asyncio.CancelledError:
                logger.info("Gamma notification monitor cancelled")
                break
            except Exception as e:
                logger.error(f"Gamma notification monitor error: {e}")
                await asyncio.sleep(0.5)  # Brief pause before continuing loop

    gamma_monitor_task = asyncio.create_task(_gamma_notification_monitor(session))
    logger.info("Gamma notification monitor started")

    # ── In-session heartbeat monitor ─────────────────────────────────────────
    # Runs every 4 seconds SILENTLY. Does not speak to the user unless a multi-step
    # tool task has stalled (no activity for 4+ seconds while objective is incomplete).
    # When stalled, injects a continuation instruction to resume the task.
    def _get_chat_ctx(session_ref):
        """Safely retrieve the chat context from an AgentSession.

        LiveKit SDK versions differ on how chat_ctx is exposed.
        Tries common attribute paths before giving up.
        """
        for attr in ("chat_ctx", "_chat_ctx"):
            ctx = getattr(session_ref, attr, None)
            if ctx is not None:
                return ctx
        # Some SDK versions expose it via the underlying agent
        agent = getattr(session_ref, "_agent", None) or getattr(session_ref, "agent", None)
        if agent is not None:
            for attr in ("chat_ctx", "_chat_ctx"):
                ctx = getattr(agent, attr, None)
                if ctx is not None:
                    return ctx
        return None

    async def _trim_chat_context(session_ref, max_messages: int = 20) -> None:
        """Trim chat context to prevent unbounded memory growth.

        Keeps last max_messages items (system message preserved automatically).
        Called periodically (~60s) from heartbeat to bound session memory.
        Only trims when agent is not responding to avoid race conditions.
        """
        try:
            chat_ctx = _get_chat_ctx(session_ref)
            if chat_ctx is None:
                logger.debug("[Memory] chat_ctx not accessible on session — trim skipped")
                return
            before = len(chat_ctx.items)
            if before <= max_messages + 1:
                return  # Nothing to trim

            # truncate() uses .messages internally (SDK version mismatch) — slice directly
            keep = chat_ctx.items[-max_messages:]
            del chat_ctx.items[:]
            chat_ctx.items.extend(keep)
            removed = before - len(chat_ctx.items)

            logger.info(
                f"[Memory] Chat context trimmed: removed {removed} old messages, "
                f"kept {len(chat_ctx.items)} items"
            )
        except Exception as e:
            logger.warning(f"[Memory] Chat context trim failed: {e}")

    async def _heartbeat_monitor(session_ref, task_tracker_ref):
        """Background heartbeat: monitors tool execution and injects continuations.

        Design:
        - Runs every HEARTBEAT_INTERVAL seconds in the background
        - Checks TaskTracker.should_inject_continuation() — fires only when:
            * An active objective exists (user issued a task)
            * Tools were called (multi-step task, not idle chat)
            * Agent has been idle for 6+ seconds (stalled)
            * Max continuations (5) not exceeded
            * Minimum 8s cooldown since last continuation (prevents rapid-fire)
        - Uses session.generate_reply(instructions=...) to resume the LLM without
          injecting a raw say() call — this goes through the LLM for intelligent continuation
        - Falls back to session.say() if generate_reply is unavailable
        - Also trims chat_ctx every TRIM_EVERY_N cycles to bound memory growth
        """
        HEARTBEAT_INTERVAL = 4.0   # Assess every 4 seconds
        TRIM_EVERY_N_CYCLES = 5    # Trim chat_ctx every 5*4=20 seconds
        _hb_count = 0
        _delegation_active_since: dict[str, float] = {}
        _delegation_progress_said: dict[str, float] = {}
        logger.info("[Heartbeat] Background monitor started (interval=4s, stall=8s, max=5, gap=8s, trim=20s)")
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                _hb_count += 1

                # Periodic chat context trim — only when agent is idle to avoid races
                if _hb_count % TRIM_EVERY_N_CYCLES == 0 and not task_tracker_ref.is_agent_responding:
                    await _trim_chat_context(session_ref, max_messages=15)

                if _hb_count % 15 == 0:  # Every 60s — force GC to reclaim audio/embedding memory
                    import gc
                    gc.collect()
                    logger.debug(f"[Heartbeat] GC collected (cycle {_hb_count})")

                    # Fix 4B: Intermediate session facts flush — persists critical in-memory
                    # facts to Postgres every 60s so Railway container restarts mid-session
                    # don't lose gammaUrl, generationId, and last_tool_result.
                    # _session_id_ref and _user_id are captured from enclosing entrypoint scope.
                    _hb_sid = _session_id_ref[0] if _session_id_ref else None
                    _hb_pg_url = getattr(settings, "postgres_url", None)
                    if _hb_sid and _hb_pg_url:
                        try:
                            asyncio.create_task(
                                _immediate_flush_critical_facts(
                                    _hb_sid,
                                    _user_id or "_default",
                                    _hb_pg_url,
                                ),
                                name=f"hb_fact_flush_{_hb_count}",
                            )
                        except Exception as _hb_flush_e:
                            logger.debug(f"[Heartbeat] Periodic fact flush failed: {_hb_flush_e}")

                # Suppress continuation while gamma is generating in the background.
                # Without this guard the heartbeat re-triggers the LLM every 6s,
                # which calls generatePresentation/generateDocument again in a loop.
                from .tools.gamma_tool import is_gamma_pending
                if is_gamma_pending():
                    continue  # Gamma poller is running — stay silent until it completes

                # Fix 2C: check max-continuations exhaustion BEFORE should_inject_continuation
                # so the agent announces failure exactly once rather than freezing silently.
                if task_tracker_ref.is_max_continuations_reached():
                    logger.warning("[Heartbeat] Max continuations exhausted — announcing to user")
                    try:
                        await session_ref.say(
                            "I've attempted this task several times without completing it. "
                            "Could you rephrase or let me know how you'd like to proceed?",
                            allow_interruptions=True
                        )
                    except Exception as _say_err:
                        logger.error(f"[Heartbeat] Max-continuations announcement failed: {_say_err}")
                    task_tracker_ref.mark_objective_complete()  # reset so agent can take new tasks
                    continue

                # Skip heartbeat continuation if tool executor is actively running
                _hb_session_id = _session_id_ref[0] or ""
                if _hb_session_id and _is_delegation_active(_hb_session_id):
                    _now_hb = time.monotonic()
                    if _hb_session_id not in _delegation_active_since:
                        _delegation_active_since[_hb_session_id] = _now_hb
                    _hb_elapsed = _now_hb - _delegation_active_since[_hb_session_id]
                    _hb_last_said = _delegation_progress_said.get(_hb_session_id, 0.0)
                    if _hb_elapsed > 60.0 and (_now_hb - _hb_last_said) > 60.0:
                        logger.info(f"[heartbeat] Background delegation > 60s — firing progress update")
                        _say_task = asyncio.create_task(session_ref.say(
                            "I'm still working on that in the background — just a moment longer.",
                            allow_interruptions=True,
                        ))
                        _say_task.add_done_callback(
                            lambda t: logger.warning(f"[heartbeat] progress say() failed: {t.exception()}") if not t.cancelled() and t.exception() else None
                        )
                        _delegation_progress_said[_hb_session_id] = _now_hb
                    else:
                        logger.debug("[heartbeat] Skipping continuation — tool delegation active")
                    continue
                elif _hb_session_id:
                    # Clear tracking when delegation ends
                    _delegation_active_since.pop(_hb_session_id, None)
                    _delegation_progress_said.pop(_hb_session_id, None)

                if not task_tracker_ref.should_inject_continuation():
                    continue  # Nothing to do — stay silent

                _last_result = ""
                try:
                    _last_result = _get_fact(_session_id_ref[0] or "", "last_tool_result") or ""
                except Exception:
                    pass
                prompt = task_tracker_ref.get_continuation_prompt(last_tool_result=_last_result)
                logger.info(f"[Heartbeat] Stalled task detected — injecting continuation")

                # Fix 2D: inject session context into heartbeat continuations so the LLM
                # has Gamma URLs and last tool result even after chat_ctx has been trimmed.
                _sid = _session_id_ref[0] or ""
                _ctx_parts = []
                try:
                    _gamma_url = _get_fact(_sid, "gammaUrl")
                    if _gamma_url:
                        _ctx_parts.append(f"[Gamma URL from this session: {_gamma_url}]")
                except Exception:
                    pass
                try:
                    if _last_result:
                        _ctx_parts.append(f"[Last tool result: {_last_result[:500]}]")
                except Exception:
                    pass
                if _ctx_parts:
                    prompt = "[Session context]\n" + "\n".join(_ctx_parts) + "\n\n" + prompt

                try:
                    # generate_reply makes the LLM produce a new turn using the
                    # continuation instructions — intelligent, context-aware resumption
                    await session_ref.generate_reply(instructions=prompt)
                    logger.info("[Heartbeat] Continuation injected via generate_reply")
                except AttributeError:
                    # generate_reply not available in this SDK build — use say() fallback
                    logger.warning("[Heartbeat] generate_reply unavailable, using say() fallback")
                    try:
                        await session_ref.say(
                            "Let me continue working on that for you",
                            allow_interruptions=True
                        )
                    except Exception as say_err:
                        logger.error(f"[Heartbeat] say() fallback failed: {say_err}")
                except Exception as gen_err:
                    logger.error(f"[Heartbeat] generate_reply failed: {gen_err}")

            except asyncio.CancelledError:
                logger.info("[Heartbeat] Monitor cancelled — session ending")
                break
            except Exception as e:
                logger.error(f"[Heartbeat] Monitor error: {e}")
                await asyncio.sleep(1.0)  # Brief pause before continuing loop

    _heartbeat_task = asyncio.create_task(_heartbeat_monitor(session, _task_tracker))
    logger.info("[Heartbeat] In-session monitor started (4s interval, 8s stall threshold, max=5)")

    async def _composio_health_monitor():
        """Periodic background check: proactively detect EXPIRED/FAILED Composio connections.

        Runs every 10 minutes. Calls get_connected_services_status() which has the
        side-effect of syncing _service_auth_failed with live Composio API data.
        This means expired services are detected before a tool call fails —
        the LLM receives early re-auth guidance instead of a confusing execution error.
        """
        INTERVAL = 600  # 10 minutes
        logger.info("[ComposioHealth] Periodic connection health monitor started (interval=10min)")
        while True:
            try:
                await asyncio.sleep(INTERVAL)
                from .tools.composio_router import get_connected_services_status
                status_summary = await get_connected_services_status()
                logger.info(f"[ComposioHealth] Periodic check complete: {status_summary[:120]}")
            except asyncio.CancelledError:
                logger.info("[ComposioHealth] Monitor cancelled — session ending")
                break
            except Exception as e:
                logger.warning(f"[ComposioHealth] Periodic check failed: {e}")

    _composio_health_task = asyncio.create_task(_composio_health_monitor())
    logger.info("[ComposioHealth] Periodic Composio connection health monitor started")

    async def _dlq_consumer(
        postgres_url: str,
        session_id: str,
        user_id: str,
        poll_interval_secs: float = 60.0,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Background DLQ consumer: retries failed tool calls from tool_dlq.

        Polls PostgreSQL every 60s for rows belonging to the current session that:
        - have retry_after <= NOW()
        - have attempt < max_attempts
        - are not yet resolved

        On success: marks resolved_at = NOW()
        On failure: increments attempt, sets retry_after = NOW() + 120s * 2^attempt (capped at 3600s)
        Stops when stop_event is set or session ends.
        """
        if not postgres_url:
            return
        logger.info(f"[DLQ] Consumer started for session {session_id}")
        import asyncpg

        while True:
            # Wait for poll interval (or stop signal)
            try:
                if stop_event is not None:
                    try:
                        await asyncio.wait_for(
                            asyncio.shield(stop_event.wait()),
                            timeout=poll_interval_secs,
                        )
                        logger.info("[DLQ] Consumer stopping — stop event set")
                        return
                    except asyncio.TimeoutError:
                        pass  # normal poll cycle
                else:
                    await asyncio.sleep(poll_interval_secs)
            except asyncio.CancelledError:
                logger.info("[DLQ] Consumer cancelled")
                return

            # Poll for retryable rows
            try:
                conn = await asyncio.wait_for(
                    asyncpg.connect(postgres_url, ssl="require"), timeout=5.0
                )
                try:
                    rows = await conn.fetch(
                        """
                        SELECT id, slug, arguments, error_type, attempt, max_attempts
                        FROM tool_dlq
                        WHERE session_id = $1
                          AND retry_after <= NOW()
                          AND attempt < max_attempts
                          AND resolved_at IS NULL
                        ORDER BY created_at
                        LIMIT 5
                        """,
                        session_id,
                    )
                finally:
                    await conn.close()
            except Exception as poll_err:
                logger.debug(f"[DLQ] Poll failed (non-critical): {poll_err}")
                continue

            if not rows:
                continue

            logger.info(f"[DLQ] Found {len(rows)} retryable rows for session {session_id}")

            for row in rows:
                dlq_id = row["id"]
                slug = row["slug"]
                arguments = dict(row["arguments"] or {})
                attempt = row["attempt"]
                max_attempts = row["max_attempts"]

                logger.info(f"[DLQ] Retrying slug={slug} attempt={attempt+1}/{max_attempts} dlq_id={dlq_id}")

                success = False
                try:
                    from .tools.composio_router import execute_composio_tool  # type: ignore
                    # Fix 4C: 15s per-retry timeout prevents slow tools from blocking
                    # the event loop for a full 60s poll cycle.
                    result = await asyncio.wait_for(
                        execute_composio_tool(slug, arguments, user_id=user_id),
                        timeout=15.0,
                    )
                    # Consider it success if result doesn't look like an error string
                    success = bool(result and not result.lower().startswith(("error", "failed", "timeout")))
                except asyncio.TimeoutError:
                    logger.warning(
                        f"[DLQ] Retry for slug={slug} dlq_id={dlq_id} timed out after 15s "
                        f"— leaving in DLQ for next poll cycle"
                    )
                    # Don't mark resolved — leave row for next 60s poll cycle
                    continue
                except Exception as retry_err:
                    logger.warning(f"[DLQ] Retry failed for slug={slug} dlq_id={dlq_id}: {retry_err}")

                # Update the row
                try:
                    conn = await asyncio.wait_for(
                        asyncpg.connect(postgres_url, ssl="require"), timeout=5.0
                    )
                    try:
                        if success:
                            await conn.execute(
                                "UPDATE tool_dlq SET resolved_at = NOW() WHERE id = $1",
                                dlq_id,
                            )
                            logger.info(f"[DLQ] Resolved dlq_id={dlq_id} slug={slug}")
                        else:
                            new_attempt = attempt + 1
                            # Exponential backoff: 120s * 2^attempt, capped at 3600s
                            delay = min(120 * (2 ** attempt), 3600)
                            if new_attempt >= max_attempts:
                                # Mark as exhausted (resolved with max attempts hit)
                                await conn.execute(
                                    """
                                    UPDATE tool_dlq
                                    SET attempt = $1, resolved_at = NOW()
                                    WHERE id = $2
                                    """,
                                    new_attempt, dlq_id,
                                )
                                logger.warning(f"[DLQ] Exhausted dlq_id={dlq_id} slug={slug} after {new_attempt} attempts")
                            else:
                                await conn.execute(
                                    """
                                    UPDATE tool_dlq
                                    SET attempt = $1,
                                        retry_after = NOW() + ($2 || ' seconds')::interval
                                    WHERE id = $3
                                    """,
                                    new_attempt, str(delay), dlq_id,
                                )
                    finally:
                        await conn.close()
                except Exception as update_err:
                    logger.debug(f"[DLQ] Row update failed (non-critical): {update_err}")

    # Start DLQ consumer for this session
    _postgres_url = settings.postgres_url or os.environ.get("POSTGRES_URL", "")
    _dlq_stop_event = asyncio.Event()
    if _postgres_url:
        asyncio.create_task(
            _dlq_consumer(
                postgres_url=_postgres_url,
                session_id=session_id,
                user_id=_user_id or "_default",
                poll_interval_secs=60.0,
                stop_event=_dlq_stop_event,
            ),
            name=f"dlq_consumer_{session_id}",
        )
        logger.info(f"[DLQ] Consumer task started for session {session_id}")

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

    # Keep agent alive until room closes.
    # CRITICAL: Wrap the keep-alive loop AND all cleanup in try/finally so that
    # asyncio.CancelledError (raised by LiveKit worker framework on room disconnect)
    # does not bypass the cleanup block. Without this, sessions and session_facts_log
    # tables are always empty because lines after the loop are never reached.
    _session_summary: str = ""
    _session_n_calls: int = 0
    _session_msg_count: int = 0
    try:
        # The room closes when all participants leave or it times out
        while ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        logger.info("[SessionCleanup] Entrypoint cancelled by LiveKit framework — running cleanup")
        # Re-raise after cleanup block executes (in finally)
        raise
    finally:
        # Signal DLQ consumer to stop (if it was started)
        if "_dlq_stop_event" in dir():
            _dlq_stop_event.set()

        # Clean up session greeting registry entry for this room
        _greeted_rooms.pop(ctx.room.name, None)

        # Cancel any active tool delegation tasks
        _cleanup_tool_session(ctx.room.name or "livekit-agent")
        logger.debug(f"[disconnect] Tool executor session cleaned up: {ctx.room.name}")
        _unregister_session(ctx.room.name or "livekit-agent")

        # Clean up session memory when session ends
        session_id = ctx.room.name or "livekit-agent"

        # Flush session to persistent memory (8s timeout — must not block disconnect)
        if _MEM_AVAILABLE and _session_writer is not None and _mem_capture is not None:
            try:
                # Build a meaningful session summary using captured facts as objectives
                from .tools.short_term_memory import get_session_stats
                _stats = get_session_stats(session_id)
                # Compute pending facts FIRST so they can be used in the title
                _pending = _mem_capture.get_pending_facts()
                _fact_texts = [f for f, _ in _pending]

                _cats = list(_stats.get('categories', {}).keys())
                _cat_str = ", ".join(_cats[:4]) if _cats else "general"
                _session_n_calls = _stats.get('total_entries', 0)

                if _fact_texts:
                    # Use first 2 captured facts as the session objectives descriptor
                    _objectives = "; ".join([f.rstrip(".").strip() for f in _fact_texts[:2]])
                    if len(_objectives) > 120:
                        _objectives = _objectives[:117] + "..."
                    _session_summary = f"{_objectives}. ({_session_n_calls} tool calls, {_cat_str})"
                else:
                    _session_summary = f"Voice session. {_session_n_calls} tool calls ({_cat_str})."
                # Write session log to user's sessions/ dir (with 8s timeout)
                await asyncio.wait_for(
                    _session_writer.flush_session(_user_mem_dir, _session_summary, _fact_texts),
                    timeout=8.0,
                )
                # Flush facts to store
                if _mem_store is not None and _pending:
                    await _mem_capture.flush_to_store(_mem_store)
            except asyncio.TimeoutError:
                logger.warning("[Memory] Session flush timed out — session log skipped")
            except asyncio.CancelledError:
                logger.warning("[Memory] Session flush cancelled — session log skipped")
            except Exception as _e:
                logger.error("[Memory] Session flush failed: %s", _e)
            finally:
                _mem_capture.reset_session()

        # Save session summary to SQLite for cross-session semantic recall (recallSessions tool)
        if _MEM_AVAILABLE and _mem_store is not None:
            try:
                _tool_summary = _session_summary
                _tool_topics = list(_stats.get("categories", {}).keys()) if "_stats" in locals() else []
                _session_msg_count = len(ctx.chat_ctx.messages) if hasattr(ctx, "chat_ctx") else 0
                if _tool_summary:
                    asyncio.create_task(
                        asyncio.to_thread(
                            _mem_store.save_session_summary,
                            session_id,
                            _tool_summary,
                            _tool_topics,
                            _session_msg_count,
                            _user_id,
                        )
                    )
                    logger.info("[SessionSummary] Queued save for session_id=%r", session_id)
            except Exception as _ss_exc:
                logger.warning("[SessionSummary] Failed to queue summary save: %s", _ss_exc)

        cleared_count = clear_session_memory(session_id)
        logger.info(f"Cleared {cleared_count} session memory entries for {session_id}")

        # Persist session facts and session lifecycle rows to PostgreSQL.
        # Uses asyncio.shield() so CancelledError from the outer coroutine does not
        # abort these awaits mid-write — we need them to complete even during cancellation.
        if settings.postgres_url:
            try:
                await asyncio.shield(
                    _flush_facts_to_db(session_id, settings.postgres_url, user_id=_user_id or "_default")
                )
            except asyncio.CancelledError:
                pass  # shield absorbs cancel — flush was still dispatched
            except Exception as _pge:
                logger.warning("[SessionCleanup] flush_facts_to_db failed: %s", _pge)
            try:
                await asyncio.shield(
                    _pg_logger.log_session_end(
                        session_id,
                        _user_id,
                        _session_summary or None,
                        _session_msg_count,
                        _session_n_calls,
                    )
                )
            except asyncio.CancelledError:
                pass  # shield absorbs cancel — log_session_end was still dispatched
            except Exception as _pge:
                logger.warning("[SessionCleanup] log_session_end failed: %s", _pge)

        # pgvector pool is a worker-lifetime singleton — not closed per session

        cleared_facts = _clear_facts(session_id)
        if cleared_facts:
            logger.info(f"Cleared {cleared_facts} session facts for {session_id}")

        # Fix 4D: Clear per-session tool step counter at session end
        _session_tool_call_counts.pop(session_id, None)

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
