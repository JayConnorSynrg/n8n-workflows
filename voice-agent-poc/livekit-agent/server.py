"""
WebSocket Server for LiveKit Voice Agent
Open-source alternative to OpenAI Realtime API relay server

This server:
1. Accepts WebSocket connections from browser clients
2. Routes audio to the voice agent pipeline
3. Streams audio responses back to the client
4. Provides health check endpoint
"""

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime
from typing import Dict, Set

import websockets
from websockets.server import serve, WebSocketServerProtocol
from aiohttp import web

from config import VoiceAgentConfig
from voice_agent import VoiceAgentSession

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S'
)
logger = logging.getLogger(__name__)


class VoiceAgentServer:
    """
    WebSocket server for voice agent sessions.

    Protocol:
        Client -> Server:
            - Binary: Audio data (PCM16, 48kHz, mono)
            - JSON: {"type": "config", ...}

        Server -> Client:
            - Binary: Audio data (PCM16, 24kHz, mono)
            - JSON: {"type": "transcript|response|tool_call|error", ...}
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.sessions: Dict[str, VoiceAgentSession] = {}
        self._shutdown_event = asyncio.Event()

    async def handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket connection"""
        connection_id = f"ws_{int(datetime.now().timestamp())}_{id(websocket)}"
        logger.info(f"[{connection_id}] Client connected from {websocket.remote_address}")

        # Create voice agent session
        session = VoiceAgentSession(self.config)
        self.sessions[session.connection_id] = session

        # Set up callbacks
        async def send_json(data: dict):
            try:
                await websocket.send(json.dumps(data))
            except Exception as e:
                logger.error(f"[{connection_id}] Failed to send JSON: {e}")

        async def send_audio(audio: bytes):
            try:
                await websocket.send(audio)
            except Exception as e:
                logger.error(f"[{connection_id}] Failed to send audio: {e}")

        def on_transcript(text: str, is_final: bool):
            asyncio.create_task(send_json({
                "type": "transcript",
                "text": text,
                "is_final": is_final
            }))

        def on_response_text(text: str):
            asyncio.create_task(send_json({
                "type": "response",
                "text": text
            }))

        def on_audio(audio: bytes):
            asyncio.create_task(send_audio(audio))

        def on_tool_call(name: str, args: dict):
            asyncio.create_task(send_json({
                "type": "tool_call",
                "name": name,
                "arguments": args
            }))

        session.on_transcript(on_transcript)
        session.on_response_text(on_response_text)
        session.on_audio(on_audio)
        session.on_tool_call(on_tool_call)

        # Start session processing
        session_task = asyncio.create_task(session.start())

        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    # Audio data from browser
                    await session.push_audio(message)

                elif isinstance(message, str):
                    # JSON message from browser
                    try:
                        data = json.loads(message)
                        msg_type = data.get("type")

                        if msg_type == "interrupt":
                            await session.interrupt()

                        elif msg_type == "stop":
                            await session.stop()
                            break

                        elif msg_type == "config":
                            # Handle runtime config updates
                            logger.info(f"[{connection_id}] Config update: {data}")

                    except json.JSONDecodeError as e:
                        logger.warning(f"[{connection_id}] Invalid JSON: {e}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"[{connection_id}] Connection closed: {e}")
        except Exception as e:
            logger.error(f"[{connection_id}] Connection error: {e}")
        finally:
            # Cleanup
            await session.stop()
            session_task.cancel()
            del self.sessions[session.connection_id]
            logger.info(f"[{connection_id}] Session cleaned up")

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        return web.json_response({
            "status": "healthy",
            "activeConnections": len(self.sessions),
            "uptime": (datetime.now() - self._start_time).total_seconds(),
            "n8nToolsConfigured": bool(self.config.n8n.tools_webhook_url),
            "n8nLoggingConfigured": bool(self.config.n8n.logging_webhook_url),
            "providers": {
                "stt": self.config.stt.provider,
                "llm": self.config.llm.provider,
                "tts": self.config.tts.provider
            },
            "toolsAvailable": [t["name"] for t in self.config.tools]
        })

    async def stats_handler(self, request: web.Request) -> web.Response:
        """Stats endpoint"""
        return web.json_response({
            "activeConnections": len(self.sessions),
            "connections": list(self.sessions.keys()),
            "uptime": (datetime.now() - self._start_time).total_seconds(),
            "config": {
                "stt": {
                    "provider": self.config.stt.provider,
                    "model": self.config.stt.model
                },
                "llm": {
                    "provider": self.config.llm.provider,
                    "model": self.config.llm.model
                },
                "tts": {
                    "provider": self.config.tts.provider,
                    "voice": self.config.tts.voice,
                    "speed": self.config.tts.speed
                }
            },
            "tools": self.config.tools
        })

    async def run(self):
        """Run the server"""
        self._start_time = datetime.now()

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        # Start WebSocket server
        ws_server = await serve(
            self.handle_connection,
            self.config.host,
            self.config.port,
            compression=None,  # Disable compression for lower latency
            ping_interval=30,
            ping_timeout=10
        )

        logger.info(f"WebSocket server listening on ws://{self.config.host}:{self.config.port}")

        # Start HTTP health server
        app = web.Application()
        app.router.add_get("/health", self.health_handler)
        app.router.add_get("/stats", self.stats_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        health_site = web.TCPSite(runner, self.config.host, self.config.health_port)
        await health_site.start()

        logger.info(f"Health server listening on http://{self.config.host}:{self.config.health_port}/health")

        # Log configuration
        logger.info(f"n8n Tools Webhook: {self.config.n8n.tools_webhook_url or '(not configured)'}")
        logger.info(f"n8n Logging Webhook: {self.config.n8n.logging_webhook_url or '(not configured)'}")
        logger.info(f"Providers: STT={self.config.stt.provider}, LLM={self.config.llm.provider}, TTS={self.config.tts.provider}")
        logger.info("Ready for connections")

        # Wait for shutdown
        await self._shutdown_event.wait()

        # Cleanup
        logger.info("Shutting down...")
        for session in list(self.sessions.values()):
            await session.stop()

        ws_server.close()
        await ws_server.wait_closed()
        await runner.cleanup()

        logger.info("Server stopped")

    async def shutdown(self):
        """Trigger graceful shutdown"""
        self._shutdown_event.set()


async def main():
    """Main entry point"""
    # Load configuration from environment
    config = VoiceAgentConfig.from_env()

    # Create and run server
    server = VoiceAgentServer(config)
    await server.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(0)
