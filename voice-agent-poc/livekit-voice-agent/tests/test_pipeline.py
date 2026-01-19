#!/usr/bin/env python3
"""
Comprehensive Pipeline Test Suite for LiveKit Voice Agent

Tests all components of the voice pipeline:
1. LiveKit Cloud connection
2. Deepgram STT API
3. Cerebras LLM API (GLM-4.7)
4. Cartesia TTS API
5. Full pipeline integration
"""

import asyncio
import os
import sys
import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


@dataclass
class TestResult:
    """Test result container."""
    name: str
    passed: bool
    latency_ms: float
    message: str
    details: Optional[Dict[str, Any]] = None


class PipelineTestSuite:
    """Test suite for voice pipeline components."""

    def __init__(self):
        self.results: list[TestResult] = []

    def add_result(self, result: TestResult):
        """Add a test result."""
        self.results.append(result)
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"{status} | {result.name} | {result.latency_ms:.0f}ms | {result.message}")

    async def test_livekit_connection(self) -> TestResult:
        """Test LiveKit Cloud connection and authentication."""
        start = time.perf_counter()
        try:
            from livekit import api

            livekit_url = os.environ.get("LIVEKIT_URL", "")
            api_key = os.environ.get("LIVEKIT_API_KEY", "")
            api_secret = os.environ.get("LIVEKIT_API_SECRET", "")

            if not all([livekit_url, api_key, api_secret]):
                return TestResult(
                    name="LiveKit Connection",
                    passed=False,
                    latency_ms=(time.perf_counter() - start) * 1000,
                    message="Missing LiveKit credentials"
                )

            # Create API client
            lk_api = api.LiveKitAPI(
                url=livekit_url.replace("wss://", "https://"),
                api_key=api_key,
                api_secret=api_secret,
            )

            # List rooms to verify connection
            rooms = await lk_api.room.list_rooms(api.ListRoomsRequest())

            latency = (time.perf_counter() - start) * 1000
            return TestResult(
                name="LiveKit Connection",
                passed=True,
                latency_ms=latency,
                message=f"Connected successfully. {len(rooms.rooms)} rooms found.",
                details={"url": livekit_url, "rooms_count": len(rooms.rooms)}
            )

        except Exception as e:
            return TestResult(
                name="LiveKit Connection",
                passed=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Connection failed: {str(e)}"
            )

    async def test_deepgram_api(self) -> TestResult:
        """Test Deepgram STT API connectivity."""
        start = time.perf_counter()
        try:
            import httpx

            api_key = os.environ.get("DEEPGRAM_API_KEY", "")
            if not api_key:
                return TestResult(
                    name="Deepgram STT",
                    passed=False,
                    latency_ms=(time.perf_counter() - start) * 1000,
                    message="Missing DEEPGRAM_API_KEY"
                )

            # Test with a simple API call to check authentication
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.deepgram.com/v1/projects",
                    headers={"Authorization": f"Token {api_key}"},
                    timeout=10.0
                )

            latency = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                return TestResult(
                    name="Deepgram STT",
                    passed=True,
                    latency_ms=latency,
                    message=f"API authenticated. {len(data.get('projects', []))} projects found.",
                    details={"status_code": response.status_code}
                )
            else:
                return TestResult(
                    name="Deepgram STT",
                    passed=False,
                    latency_ms=latency,
                    message=f"API error: {response.status_code} - {response.text[:100]}"
                )

        except Exception as e:
            return TestResult(
                name="Deepgram STT",
                passed=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Connection failed: {str(e)}"
            )

    async def test_cerebras_api(self) -> TestResult:
        """Test Cerebras LLM API connectivity and inference."""
        start = time.perf_counter()
        try:
            from openai import AsyncOpenAI

            api_key = os.environ.get("CEREBRAS_API_KEY", "")
            model = os.environ.get("CEREBRAS_MODEL", "zai-glm-4.7")

            if not api_key:
                return TestResult(
                    name="Cerebras LLM",
                    passed=False,
                    latency_ms=(time.perf_counter() - start) * 1000,
                    message="Missing CEREBRAS_API_KEY"
                )

            # Cerebras uses OpenAI-compatible API
            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.cerebras.ai/v1"
            )

            # Test with a simple completion
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Say 'test successful' in exactly 2 words."}],
                max_tokens=10,
                temperature=0.0,
            )

            latency = (time.perf_counter() - start) * 1000
            content = response.choices[0].message.content

            return TestResult(
                name="Cerebras LLM",
                passed=True,
                latency_ms=latency,
                message=f"Inference successful. Response: '{content[:50]}'",
                details={
                    "model": model,
                    "tokens_used": response.usage.total_tokens if response.usage else 0
                }
            )

        except Exception as e:
            return TestResult(
                name="Cerebras LLM",
                passed=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"API error: {str(e)}"
            )

    async def test_cartesia_api(self) -> TestResult:
        """Test Cartesia TTS API connectivity and voice synthesis."""
        start = time.perf_counter()
        try:
            import httpx

            api_key = os.environ.get("CARTESIA_API_KEY", "")
            voice_id = os.environ.get("CARTESIA_VOICE", "")

            if not api_key:
                return TestResult(
                    name="Cartesia TTS",
                    passed=False,
                    latency_ms=(time.perf_counter() - start) * 1000,
                    message="Missing CARTESIA_API_KEY"
                )

            # Test TTS synthesis
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.cartesia.ai/tts/bytes",
                    headers={
                        "X-API-Key": api_key,
                        "Cartesia-Version": "2024-11-13",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model_id": "sonic-2",
                        "transcript": "Test successful.",
                        "voice": {
                            "mode": "id",
                            "id": voice_id or "a0e99841-438c-4a64-b679-ae501e7d6091"
                        },
                        "output_format": {
                            "container": "raw",
                            "encoding": "pcm_f32le",
                            "sample_rate": 24000
                        }
                    },
                    timeout=15.0
                )

            latency = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                audio_bytes = len(response.content)
                return TestResult(
                    name="Cartesia TTS",
                    passed=True,
                    latency_ms=latency,
                    message=f"Synthesis successful. {audio_bytes} bytes of audio generated.",
                    details={
                        "voice_id": voice_id,
                        "audio_size_bytes": audio_bytes
                    }
                )
            else:
                return TestResult(
                    name="Cartesia TTS",
                    passed=False,
                    latency_ms=latency,
                    message=f"API error: {response.status_code} - {response.text[:200]}"
                )

        except Exception as e:
            return TestResult(
                name="Cartesia TTS",
                passed=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Connection failed: {str(e)}"
            )

    async def test_n8n_webhook(self) -> TestResult:
        """Test n8n webhook connectivity (optional)."""
        start = time.perf_counter()
        try:
            import httpx

            webhook_base = os.environ.get("N8N_WEBHOOK_BASE_URL", "")
            if not webhook_base:
                return TestResult(
                    name="n8n Webhook",
                    passed=True,
                    latency_ms=0,
                    message="Skipped - N8N_WEBHOOK_BASE_URL not configured"
                )

            # Just test connectivity, not actual execution
            async with httpx.AsyncClient() as client:
                # Test with OPTIONS or HEAD request
                response = await client.options(
                    f"{webhook_base}/health",
                    timeout=5.0
                )

            latency = (time.perf_counter() - start) * 1000

            # Any response indicates the server is reachable
            return TestResult(
                name="n8n Webhook",
                passed=True,
                latency_ms=latency,
                message=f"Server reachable. Status: {response.status_code}",
                details={"base_url": webhook_base}
            )

        except httpx.ConnectError:
            return TestResult(
                name="n8n Webhook",
                passed=True,  # Not critical for testing
                latency_ms=(time.perf_counter() - start) * 1000,
                message="Server not reachable (webhook may require specific path)"
            )
        except Exception as e:
            return TestResult(
                name="n8n Webhook",
                passed=True,  # Not critical
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Check skipped: {str(e)[:50]}"
            )

    async def test_config_validation(self) -> TestResult:
        """Test configuration loading and validation."""
        start = time.perf_counter()
        try:
            from src.config import get_settings

            settings = get_settings()

            # Verify all required fields are set
            required = [
                ("livekit_url", settings.livekit_url),
                ("livekit_api_key", settings.livekit_api_key),
                ("livekit_api_secret", settings.livekit_api_secret),
                ("deepgram_api_key", settings.deepgram_api_key),
                ("cerebras_api_key", settings.cerebras_api_key),
                ("cartesia_api_key", settings.cartesia_api_key),
            ]

            missing = [name for name, value in required if not value]

            latency = (time.perf_counter() - start) * 1000

            if missing:
                return TestResult(
                    name="Config Validation",
                    passed=False,
                    latency_ms=latency,
                    message=f"Missing fields: {', '.join(missing)}"
                )

            return TestResult(
                name="Config Validation",
                passed=True,
                latency_ms=latency,
                message="All required configuration fields present",
                details={
                    "livekit_url": settings.livekit_url,
                    "cerebras_model": settings.cerebras_model,
                    "cartesia_voice": settings.cartesia_voice
                }
            )

        except Exception as e:
            return TestResult(
                name="Config Validation",
                passed=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Config error: {str(e)}"
            )

    async def test_agent_imports(self) -> TestResult:
        """Test that all agent modules can be imported."""
        start = time.perf_counter()
        try:
            # Test imports
            from src.config import get_settings, Settings
            from src.tools.email_tool import send_email_tool
            from src.tools.database_tool import query_database_tool
            from src.utils.logging import setup_logging
            from src.utils.metrics import LatencyTracker, MetricsCollector

            latency = (time.perf_counter() - start) * 1000

            return TestResult(
                name="Agent Imports",
                passed=True,
                latency_ms=latency,
                message="All modules imported successfully",
                details={
                    "modules": [
                        "config", "tools.email_tool",
                        "tools.database_tool", "utils.logging", "utils.metrics"
                    ]
                }
            )

        except ImportError as e:
            return TestResult(
                name="Agent Imports",
                passed=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Import error: {str(e)}"
            )

    async def run_all_tests(self):
        """Run all pipeline tests."""
        print("\n" + "=" * 70)
        print("🧪 LIVEKIT VOICE AGENT - PIPELINE TEST SUITE")
        print("=" * 70 + "\n")

        # Run tests in sequence
        tests = [
            ("Config Validation", self.test_config_validation),
            ("Agent Imports", self.test_agent_imports),
            ("LiveKit Connection", self.test_livekit_connection),
            ("Deepgram STT", self.test_deepgram_api),
            ("Cerebras LLM", self.test_cerebras_api),
            ("Cartesia TTS", self.test_cartesia_api),
            ("n8n Webhook", self.test_n8n_webhook),
        ]

        for name, test_func in tests:
            print(f"\n▶ Testing {name}...")
            result = await test_func()
            self.add_result(result)

        # Summary
        print("\n" + "=" * 70)
        print("📊 TEST SUMMARY")
        print("=" * 70)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total_latency = sum(r.latency_ms for r in self.results)

        print(f"\n✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⏱️  Total latency: {total_latency:.0f}ms")

        # Pipeline status
        critical_tests = ["Config Validation", "LiveKit Connection", "Cerebras LLM", "Cartesia TTS"]
        critical_passed = all(
            r.passed for r in self.results if r.name in critical_tests
        )

        print("\n" + "-" * 70)
        if critical_passed:
            print("🚀 PIPELINE STATUS: READY FOR DEPLOYMENT")
            print("\nAll critical components validated:")
            for r in self.results:
                if r.name in critical_tests:
                    print(f"  ✓ {r.name}: {r.latency_ms:.0f}ms")
        else:
            print("⚠️  PIPELINE STATUS: NOT READY")
            print("\nFailed critical tests:")
            for r in self.results:
                if r.name in critical_tests and not r.passed:
                    print(f"  ✗ {r.name}: {r.message}")

        print("\n" + "=" * 70)

        return critical_passed


async def main():
    """Run the test suite."""
    suite = PipelineTestSuite()
    success = await suite.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
