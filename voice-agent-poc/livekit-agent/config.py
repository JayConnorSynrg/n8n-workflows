"""
LiveKit Voice Agent Configuration
Extracted from LiveKit Agents patterns for optimal streaming performance
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# AUDIO CONFIGURATION (from LiveKit patterns)
# =============================================================================

@dataclass
class AudioConfig:
    """Audio frame and buffer configuration based on LiveKit patterns"""

    # TTS Output (from livekit-agents/tts/tts.py)
    tts_frame_size_ms: int = 200          # 200ms chunks for TTS output
    tts_sample_rate: int = 24000          # OpenAI TTS standard

    # STT Input (from livekit-agents/utils/audio.py)
    stt_frame_size_ms: int = 100          # 100ms frames for STT input
    stt_sample_rate: int = 48000          # General input

    # Audio Format
    num_channels: int = 1                  # Mono
    bits_per_sample: int = 16              # PCM 16-bit

    @property
    def tts_samples_per_frame(self) -> int:
        return (self.tts_sample_rate // 1000) * self.tts_frame_size_ms

    @property
    def stt_samples_per_frame(self) -> int:
        return (self.stt_sample_rate // 1000) * self.stt_frame_size_ms

    @property
    def tts_bytes_per_frame(self) -> int:
        return self.tts_samples_per_frame * self.num_channels * (self.bits_per_sample // 8)

    @property
    def stt_bytes_per_frame(self) -> int:
        return self.stt_samples_per_frame * self.num_channels * (self.bits_per_sample // 8)


# =============================================================================
# SENTENCE CHUNKING CONFIGURATION (from LiveKit patterns)
# =============================================================================

@dataclass
class ChunkingConfig:
    """Sentence chunking configuration from livekit-agents/tokenize/_basic_sent.py"""

    min_sentence_length: int = 20         # Buffer until 20 chars
    min_context_length: int = 10          # Minimum context before tokenizing
    max_text_batch_length: int = 300      # Max chars per TTS request


# =============================================================================
# STREAM PACING CONFIGURATION (from LiveKit patterns)
# =============================================================================

@dataclass
class StreamPacingConfig:
    """Stream pacing from livekit-agents/tts/stream_pacer.py"""

    min_remaining_audio_sec: float = 5.0  # Wait until 5s audio remains
    first_sentence_immediate: bool = True  # Send first sentence immediately
    max_text_length: int = 300             # Max batch size


# =============================================================================
# CONNECTION POOLING CONFIGURATION (from LiveKit patterns)
# =============================================================================

@dataclass
class ConnectionPoolConfig:
    """WebSocket connection pooling from livekit-agents/utils/connection_pool.py"""

    max_session_duration_sec: float = 300.0  # 5 minutes
    prewarm_enabled: bool = True
    mark_refreshed_on_get: bool = True


# =============================================================================
# PREEMPTIVE GENERATION CONFIGURATION
# =============================================================================

@dataclass
class PreemptiveConfig:
    """Preemptive LLM generation from livekit-agents/voice/agent_activity.py"""

    enabled: bool = True
    confidence_threshold: float = 0.8      # STT confidence threshold
    min_words: int = 10                    # Minimum words before triggering
    cancel_on_user_speech: bool = True


# =============================================================================
# PROVIDER CONFIGURATION
# =============================================================================

@dataclass
class STTConfig:
    """Speech-to-Text configuration"""

    provider: str = "deepgram"             # Options: deepgram, whisper, azure
    model: str = "nova-2"                  # Deepgram model
    language: str = "en"

    # API Keys (from environment)
    deepgram_api_key: str = field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))

    # Whisper local config
    whisper_model: str = "base"            # Options: tiny, base, small, medium, large


@dataclass
class LLMConfig:
    """Language Model configuration"""

    provider: str = "openai"               # Options: openai, ollama, anthropic
    model: str = "gpt-4o"                  # Default model
    temperature: float = 0.7
    max_tokens: int = 1024

    # API Keys (from environment)
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))

    # Ollama config
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = "llama3.1"


@dataclass
class TTSConfig:
    """Text-to-Speech configuration"""

    provider: str = "openai"               # Options: openai, elevenlabs, cartesia, pyttsx3
    voice: str = "alloy"                   # Voice ID
    speed: float = 1.0                     # Playback speed (0.6-2.0)

    # API Keys (from environment)
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))

    # Streaming config
    use_streaming: bool = True


# =============================================================================
# N8N INTEGRATION CONFIGURATION
# =============================================================================

@dataclass
class N8nConfig:
    """n8n webhook integration configuration"""

    tools_webhook_url: str = field(default_factory=lambda: os.getenv("N8N_TOOLS_WEBHOOK", ""))
    logging_webhook_url: str = field(default_factory=lambda: os.getenv("N8N_LOGGING_WEBHOOK", ""))
    webhook_secret: str = field(default_factory=lambda: os.getenv("WEBHOOK_SECRET", ""))

    timeout_seconds: int = 30
    retry_count: int = 3
    retry_delay_sec: float = 1.0


# =============================================================================
# VOICE AGENT TOOLS (matching OpenAI relay server)
# =============================================================================

VOICE_TOOLS = [
    {
        "type": "function",
        "name": "schedule_meeting",
        "description": "Schedule a meeting on the user's calendar. Use when the user asks to book, schedule, or set up a meeting.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title or subject of the meeting"},
                "datetime": {"type": "string", "description": "Date and time in ISO 8601 format"},
                "duration_minutes": {"type": "number", "description": "Duration in minutes (default: 30)"},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "Email addresses of attendees"},
                "description": {"type": "string", "description": "Meeting description"}
            },
            "required": ["title", "datetime"]
        }
    },
    {
        "type": "function",
        "name": "send_email",
        "description": "Send an email on behalf of the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject line"},
                "body": {"type": "string", "description": "Email body content"},
                "cc": {"type": "array", "items": {"type": "string"}, "description": "CC recipients"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "type": "function",
        "name": "search_contacts",
        "description": "Search for contacts in the user's CRM or address book.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name, email, or company to search for"},
                "limit": {"type": "number", "description": "Maximum results to return (default: 5)"}
            },
            "required": ["query"]
        }
    },
    {
        "type": "function",
        "name": "get_calendar_availability",
        "description": "Check calendar availability for scheduling.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date to check in YYYY-MM-DD format"},
                "duration_minutes": {"type": "number", "description": "Minimum slot duration needed"}
            },
            "required": ["date"]
        }
    },
    {
        "type": "function",
        "name": "create_task",
        "description": "Create a task or reminder for the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title or description"},
                "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Task priority"}
            },
            "required": ["title"]
        }
    }
]


# =============================================================================
# SYSTEM PROMPT (matching OpenAI relay server)
# =============================================================================

SYSTEM_PROMPT = """You are an autonomous voice assistant for a business professional with real tool capabilities.

CAPABILITIES:
- Schedule meetings and check calendar availability (schedule_meeting, get_calendar_availability)
- Send emails on behalf of the user (send_email)
- Search contacts in their CRM (search_contacts)
- Create tasks and reminders (create_task)

DECISION-MAKING AUTONOMY:
You decide WHEN to use tools based on user intent. You are the decision-maker.
- If the user's request requires action (scheduling, sending, creating), USE THE TOOL immediately.
- If you need information to complete a request (availability, contacts), USE THE TOOL to get it.
- If the request is conversational/informational only, respond without tools.
- If the user confirms a previous suggestion, execute it immediately via tools.

CONVERSATION STYLE:
- Be concise and conversational
- When executing tools, briefly confirm what you're doing
- After tool execution, summarize the result naturally
- If a request is ambiguous, ask ONE clarifying question then act
- Reference previous tool calls when relevant to the current request

CRITICAL RULES:
- NEVER simulate or pretend to complete actions - always use actual tools
- NEVER say "I can help you with that" without actually doing it - USE THE TOOL
- If you mention an action capability, you MUST use the corresponding tool when requested
- You have full context of all previous tool calls in this conversation"""


# =============================================================================
# MASTER CONFIGURATION
# =============================================================================

@dataclass
class VoiceAgentConfig:
    """Master configuration combining all components"""

    # Audio & Processing
    audio: AudioConfig = field(default_factory=AudioConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    stream_pacing: StreamPacingConfig = field(default_factory=StreamPacingConfig)
    connection_pool: ConnectionPoolConfig = field(default_factory=ConnectionPoolConfig)
    preemptive: PreemptiveConfig = field(default_factory=PreemptiveConfig)

    # Providers
    stt: STTConfig = field(default_factory=STTConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)

    # Integration
    n8n: N8nConfig = field(default_factory=N8nConfig)

    # Server
    host: str = "0.0.0.0"
    port: int = 3000
    health_port: int = 3001

    # System prompt and tools
    system_prompt: str = SYSTEM_PROMPT
    tools: List[dict] = field(default_factory=lambda: VOICE_TOOLS)

    @classmethod
    def from_env(cls) -> "VoiceAgentConfig":
        """Create configuration from environment variables"""
        return cls(
            stt=STTConfig(
                provider=os.getenv("STT_PROVIDER", "deepgram"),
                model=os.getenv("STT_MODEL", "nova-2"),
            ),
            llm=LLMConfig(
                provider=os.getenv("LLM_PROVIDER", "openai"),
                model=os.getenv("LLM_MODEL", "gpt-4o"),
            ),
            tts=TTSConfig(
                provider=os.getenv("TTS_PROVIDER", "openai"),
                voice=os.getenv("TTS_VOICE", "alloy"),
                speed=float(os.getenv("TTS_SPEED", "1.0")),
            ),
            port=int(os.getenv("PORT", "3000")),
            health_port=int(os.getenv("HEALTH_PORT", "3001")),
        )
