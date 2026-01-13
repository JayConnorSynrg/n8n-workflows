"""
Voice Agent Session - Core Voice Pipeline
Open-source alternative to OpenAI Realtime API

Architecture:
  Browser Audio → STT → LLM (with tools) → TTS → Browser Audio

Based on patterns extracted from LiveKit Agents framework.
"""

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from config import VoiceAgentConfig, VOICE_TOOLS, SYSTEM_PROMPT
from conversation_context import ConversationContext
from sentence_chunker import SentenceChunker, TTSBatcher
from n8n_integration import N8nIntegration, N8nConfig

logger = logging.getLogger(__name__)


# =============================================================================
# ABSTRACT PROVIDER INTERFACES
# =============================================================================

class STTProvider(ABC):
    """Abstract Speech-to-Text provider interface"""

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Transcribe audio stream, yielding partial and final results.

        Yields:
            {"text": str, "is_final": bool, "confidence": float}
        """
        pass


class LLMProvider(ABC):
    """Abstract Language Model provider interface"""

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Generate response stream from chat messages.

        Yields:
            {"type": "text", "content": str} or
            {"type": "tool_call", "name": str, "arguments": dict, "call_id": str}
        """
        pass


class TTSProvider(ABC):
    """Abstract Text-to-Speech provider interface"""

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to audio stream.

        Yields:
            Audio chunks in PCM16 format
        """
        pass


# =============================================================================
# OPENAI IMPLEMENTATIONS (default providers)
# =============================================================================

class OpenAISTT(STTProvider):
    """OpenAI Whisper STT implementation"""

    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.api_key = api_key
        self.model = model
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Transcribe audio using Whisper.

        Note: Whisper doesn't support true streaming, so we buffer
        and transcribe chunks. For true streaming, use Deepgram.
        """
        import io
        import wave

        buffer = bytearray()
        sample_rate = 48000
        chunk_duration_sec = 2.0  # Transcribe every 2 seconds

        async for audio_chunk in audio_stream:
            buffer.extend(audio_chunk)

            # Calculate buffer duration
            bytes_per_sample = 2  # 16-bit audio
            buffer_samples = len(buffer) // bytes_per_sample
            buffer_duration = buffer_samples / sample_rate

            if buffer_duration >= chunk_duration_sec:
                # Create WAV in memory
                wav_buffer = io.BytesIO()
                with wave.open(wav_buffer, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(sample_rate)
                    wav.writeframes(bytes(buffer))

                wav_buffer.seek(0)

                try:
                    client = await self._get_client()
                    response = await client.audio.transcriptions.create(
                        model=self.model,
                        file=("audio.wav", wav_buffer, "audio/wav"),
                        response_format="text"
                    )

                    yield {
                        "text": response.strip(),
                        "is_final": True,
                        "confidence": 0.9
                    }

                except Exception as e:
                    logger.error(f"Whisper transcription error: {e}")

                buffer.clear()


class OpenAILLM(LLMProvider):
    """OpenAI GPT LLM implementation with function calling"""

    def __init__(self, api_key: str, model: str = "gpt-4o", temperature: float = 0.7):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response with tool support"""
        try:
            client = await self._get_client()

            # Build request
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "stream": True
            }

            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            stream = await client.chat.completions.create(**kwargs)

            current_text = ""
            current_tool_calls = {}

            async for chunk in stream:
                delta = chunk.choices[0].delta

                # Handle text content
                if delta.content:
                    current_text += delta.content
                    yield {"type": "text", "content": delta.content, "accumulated": current_text}

                # Handle tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": ""
                            }

                        if tc.id:
                            current_tool_calls[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            current_tool_calls[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            current_tool_calls[idx]["arguments"] += tc.function.arguments

                # Check for finish reason
                if chunk.choices[0].finish_reason == "tool_calls":
                    for tool_call in current_tool_calls.values():
                        try:
                            args = json.loads(tool_call["arguments"])
                        except json.JSONDecodeError:
                            args = {}

                        yield {
                            "type": "tool_call",
                            "call_id": tool_call["id"],
                            "name": tool_call["name"],
                            "arguments": args
                        }

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            yield {"type": "error", "error": str(e)}


class OpenAITTS(TTSProvider):
    """OpenAI TTS implementation"""

    def __init__(self, api_key: str, voice: str = "alloy", speed: float = 1.0):
        self.api_key = api_key
        self.voice = voice
        self.speed = speed
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def synthesize_stream(
        self,
        text: str
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize text to audio stream"""
        try:
            client = await self._get_client()

            # Note: OpenAI TTS doesn't support true streaming via API
            # For true streaming, use ElevenLabs or Cartesia
            response = await client.audio.speech.create(
                model="tts-1",
                voice=self.voice,
                input=text,
                response_format="pcm",
                speed=self.speed
            )

            # Yield in chunks for streaming simulation
            audio_data = response.content
            chunk_size = 4800  # 200ms at 24kHz
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i:i + chunk_size]

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")


# =============================================================================
# VOICE AGENT SESSION
# =============================================================================

@dataclass
class VoiceAgentState:
    """Current state of the voice agent session"""
    is_listening: bool = False
    is_speaking: bool = False
    is_processing: bool = False
    current_transcript: str = ""
    pending_tool_calls: List[Dict] = field(default_factory=list)


class VoiceAgentSession:
    """
    Voice Agent Session - Manages the full STT -> LLM -> TTS pipeline

    This is the open-source alternative to OpenAI Realtime API.

    Key Features:
    - Modular providers (swap STT/LLM/TTS independently)
    - Tool execution via n8n webhooks
    - Sentence chunking for streaming TTS
    - Full conversation context tracking

    Architecture:
        Browser Audio
             ↓
        [STT Provider]
             ↓
        [Sentence Chunker]
             ↓
        [LLM Provider + Tools]
             ↓
        [TTS Batcher]
             ↓
        [TTS Provider]
             ↓
        Browser Audio
    """

    def __init__(
        self,
        config: VoiceAgentConfig,
        stt_provider: Optional[STTProvider] = None,
        llm_provider: Optional[LLMProvider] = None,
        tts_provider: Optional[TTSProvider] = None
    ):
        self.config = config
        self.connection_id = f"session_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"

        # Initialize providers
        self.stt = stt_provider or self._create_default_stt()
        self.llm = llm_provider or self._create_default_llm()
        self.tts = tts_provider or self._create_default_tts()

        # Initialize components
        self.conversation = ConversationContext(self.connection_id)
        self.sentence_chunker = SentenceChunker()
        self.tts_batcher = TTSBatcher(max_batch_length=config.chunking.max_text_batch_length)

        # Initialize n8n integration
        n8n_config = N8nConfig(
            tools_webhook_url=config.n8n.tools_webhook_url,
            logging_webhook_url=config.n8n.logging_webhook_url,
            webhook_secret=config.n8n.webhook_secret
        )
        self.n8n = N8nIntegration(n8n_config)

        # State
        self.state = VoiceAgentState()
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._response_queue: asyncio.Queue[bytes] = asyncio.Queue()

        # Callbacks
        self._on_transcript: Optional[Callable[[str, bool], None]] = None
        self._on_response_text: Optional[Callable[[str], None]] = None
        self._on_audio: Optional[Callable[[bytes], None]] = None
        self._on_tool_call: Optional[Callable[[str, Dict], None]] = None

        logger.info(f"[{self.connection_id}] Voice agent session created")

    def _create_default_stt(self) -> STTProvider:
        """Create default STT provider based on config"""
        return OpenAISTT(
            api_key=self.config.stt.deepgram_api_key or self.config.llm.openai_api_key,
            model=self.config.stt.model
        )

    def _create_default_llm(self) -> LLMProvider:
        """Create default LLM provider based on config"""
        return OpenAILLM(
            api_key=self.config.llm.openai_api_key,
            model=self.config.llm.model,
            temperature=self.config.llm.temperature
        )

    def _create_default_tts(self) -> TTSProvider:
        """Create default TTS provider based on config"""
        return OpenAITTS(
            api_key=self.config.tts.openai_api_key or self.config.llm.openai_api_key,
            voice=self.config.tts.voice,
            speed=self.config.tts.speed
        )

    # =========================================================================
    # CALLBACK REGISTRATION
    # =========================================================================

    def on_transcript(self, callback: Callable[[str, bool], None]):
        """Register callback for user transcripts"""
        self._on_transcript = callback

    def on_response_text(self, callback: Callable[[str], None]):
        """Register callback for assistant response text"""
        self._on_response_text = callback

    def on_audio(self, callback: Callable[[bytes], None]):
        """Register callback for audio output"""
        self._on_audio = callback

    def on_tool_call(self, callback: Callable[[str, Dict], None]):
        """Register callback for tool calls"""
        self._on_tool_call = callback

    # =========================================================================
    # AUDIO INPUT HANDLING
    # =========================================================================

    async def push_audio(self, audio_data: bytes):
        """Push audio data from browser to the pipeline"""
        await self._audio_queue.put(audio_data)

    async def _audio_stream(self) -> AsyncGenerator[bytes, None]:
        """Internal audio stream generator"""
        while True:
            try:
                audio = await asyncio.wait_for(
                    self._audio_queue.get(),
                    timeout=1.0
                )
                yield audio
            except asyncio.TimeoutError:
                if not self.state.is_listening:
                    break

    # =========================================================================
    # MAIN PROCESSING LOOP
    # =========================================================================

    async def start(self):
        """Start the voice agent processing loop"""
        self.state.is_listening = True
        logger.info(f"[{self.connection_id}] Voice agent started")

        try:
            # Run STT processing in background
            stt_task = asyncio.create_task(self._process_stt())

            # Wait for stop signal
            while self.state.is_listening:
                await asyncio.sleep(0.1)

            stt_task.cancel()

        except Exception as e:
            logger.error(f"[{self.connection_id}] Voice agent error: {e}")
        finally:
            await self._cleanup()

    async def stop(self):
        """Stop the voice agent"""
        self.state.is_listening = False
        logger.info(f"[{self.connection_id}] Voice agent stopping")

        # Log conversation completion
        if self.conversation.items:
            self.n8n.log_conversation_complete(self.connection_id, self.conversation)

    async def _cleanup(self):
        """Cleanup resources"""
        await self.n8n.close()
        logger.info(f"[{self.connection_id}] Voice agent cleaned up")

    # =========================================================================
    # STT PROCESSING
    # =========================================================================

    async def _process_stt(self):
        """Process audio through STT and handle transcripts"""
        try:
            async for result in self.stt.transcribe_stream(self._audio_stream()):
                text = result.get("text", "")
                is_final = result.get("is_final", False)
                confidence = result.get("confidence", 0.0)

                if not text:
                    continue

                self.state.current_transcript = text

                # Callback for transcript updates
                if self._on_transcript:
                    self._on_transcript(text, is_final)

                # On final transcript, process through LLM
                if is_final:
                    logger.info(f"[{self.connection_id}] User: {text}")
                    self.conversation.add_user_message(text)
                    self.n8n.log_message(text, "user", self.connection_id, self.conversation)

                    # Generate response
                    await self._generate_response(text)
                    self.state.current_transcript = ""

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{self.connection_id}] STT processing error: {e}")

    # =========================================================================
    # LLM RESPONSE GENERATION
    # =========================================================================

    async def _generate_response(self, user_input: str):
        """Generate LLM response and handle tool calls"""
        self.state.is_processing = True

        try:
            # Build messages with system prompt and history
            messages = [
                {"role": "system", "content": self.config.system_prompt}
            ]
            messages.extend(self.conversation.get_chat_history())

            # Generate response
            full_response = ""
            pending_tool_calls = []

            async for chunk in self.llm.generate_stream(messages, self.config.tools):
                if chunk["type"] == "text":
                    content = chunk.get("content", "")
                    full_response += content

                    # Send to sentence chunker
                    for sentence in self.sentence_chunker.process(content):
                        self.tts_batcher.add_sentence(sentence)

                        # Stream TTS for ready batches
                        if self.tts_batcher.should_send_now():
                            batch = self.tts_batcher.get_batch()
                            if batch:
                                await self._synthesize_and_stream(batch)

                    # Callback for response text
                    if self._on_response_text:
                        self._on_response_text(content)

                elif chunk["type"] == "tool_call":
                    pending_tool_calls.append(chunk)

            # Handle any remaining text
            remaining = self.sentence_chunker.flush()
            if remaining:
                self.tts_batcher.add_sentence(remaining)

            # Flush remaining batches
            while self.tts_batcher.has_pending():
                batch = self.tts_batcher.get_batch()
                if batch:
                    await self._synthesize_and_stream(batch)

            # Process tool calls
            if pending_tool_calls:
                await self._handle_tool_calls(pending_tool_calls)
            else:
                # No tool calls, log the response
                if full_response:
                    self.conversation.add_assistant_message(full_response)
                    self.n8n.log_message(full_response, "assistant", self.connection_id, self.conversation)

        except Exception as e:
            logger.error(f"[{self.connection_id}] Response generation error: {e}")
        finally:
            self.state.is_processing = False

    # =========================================================================
    # TOOL CALL HANDLING
    # =========================================================================

    async def _handle_tool_calls(self, tool_calls: List[Dict]):
        """Handle tool calls from LLM response"""
        for tc in tool_calls:
            call_id = tc.get("call_id", str(uuid.uuid4()))
            name = tc.get("name", "")
            args = tc.get("arguments", {})

            logger.info(f"[{self.connection_id}] Tool call: {name}")

            # Callback for tool call
            if self._on_tool_call:
                self._on_tool_call(name, args)

            # Track in conversation context
            self.conversation.add_tool_call(name, args, call_id)

            # Execute via n8n
            result = await self.n8n.execute_tool(
                name, args, self.connection_id, self.conversation
            )

            # Update context with result
            self.conversation.set_tool_result(call_id, result)

            # Generate follow-up response with tool result
            await self._generate_tool_response(call_id, name, result)

    async def _generate_tool_response(self, call_id: str, tool_name: str, result: Dict):
        """Generate response after tool execution"""
        # Add tool result to messages for LLM
        messages = [
            {"role": "system", "content": self.config.system_prompt}
        ]
        messages.extend(self.conversation.get_chat_history())

        # Generate follow-up
        full_response = ""
        async for chunk in self.llm.generate_stream(messages, self.config.tools):
            if chunk["type"] == "text":
                content = chunk.get("content", "")
                full_response += content

                for sentence in self.sentence_chunker.process(content):
                    self.tts_batcher.add_sentence(sentence)
                    if self.tts_batcher.should_send_now():
                        batch = self.tts_batcher.get_batch()
                        if batch:
                            await self._synthesize_and_stream(batch)

                if self._on_response_text:
                    self._on_response_text(content)

        # Flush remaining
        remaining = self.sentence_chunker.flush()
        if remaining:
            self.tts_batcher.add_sentence(remaining)
        while self.tts_batcher.has_pending():
            batch = self.tts_batcher.get_batch()
            if batch:
                await self._synthesize_and_stream(batch)

        # Log response
        if full_response:
            self.conversation.add_assistant_message(full_response)
            self.n8n.log_message(full_response, "assistant", self.connection_id, self.conversation)

    # =========================================================================
    # TTS SYNTHESIS
    # =========================================================================

    async def _synthesize_and_stream(self, text: str):
        """Synthesize text and stream audio"""
        self.state.is_speaking = True
        logger.debug(f"[{self.connection_id}] Synthesizing: {text[:50]}...")

        try:
            async for audio_chunk in self.tts.synthesize_stream(text):
                if self._on_audio:
                    self._on_audio(audio_chunk)
                await self._response_queue.put(audio_chunk)
        except Exception as e:
            logger.error(f"[{self.connection_id}] TTS error: {e}")
        finally:
            self.state.is_speaking = False

    # =========================================================================
    # INTERRUPTION HANDLING
    # =========================================================================

    async def interrupt(self):
        """Handle user interruption (barge-in)"""
        logger.info(f"[{self.connection_id}] User interrupted")

        # Clear pending audio
        self.tts_batcher.clear()
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self.state.is_speaking = False
