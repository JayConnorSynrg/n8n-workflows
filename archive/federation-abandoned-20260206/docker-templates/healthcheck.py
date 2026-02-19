#!/usr/bin/env python3
"""
Federation AIO Voice Agent - Health Check
Version: 1.0.0
Purpose: Validate all critical systems before declaring healthy
"""

import sys
import os
import asyncio
from typing import Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='[healthcheck] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class HealthChecker:
    """Performs comprehensive health checks for the AIO agent."""

    def __init__(self):
        self.config_path = os.getenv('AIO_CONFIG_PATH', '/app/config/config.yaml')
        self.postgres_url = os.getenv('POSTGRES_URL', '')
        self.department_id = os.getenv('DEPARTMENT_ID', 'unknown')

    async def check_config_exists(self) -> bool:
        """Verify configuration file exists and is readable."""
        try:
            if not os.path.exists(self.config_path):
                logger.error(f"Configuration file not found: {self.config_path}")
                return False

            with open(self.config_path, 'r') as f:
                content = f.read()
                if not content.strip():
                    logger.error("Configuration file is empty")
                    return False

            logger.info("Configuration file check: OK")
            return True
        except Exception as e:
            logger.error(f"Configuration file check failed: {e}")
            return False

    async def check_database(self) -> bool:
        """Test database connectivity."""
        if not self.postgres_url:
            logger.warning("POSTGRES_URL not set, skipping database check")
            return True  # Non-critical for health check

        try:
            import asyncpg

            conn = await asyncpg.connect(self.postgres_url, timeout=5)
            await conn.execute('SELECT 1')
            await conn.close()

            logger.info("Database connectivity check: OK")
            return True
        except ImportError:
            logger.warning("asyncpg not available, skipping database check")
            return True  # Non-critical
        except Exception as e:
            logger.error(f"Database connectivity check failed: {e}")
            return False

    async def check_livekit_config(self) -> bool:
        """Verify LiveKit credentials are present."""
        required_vars = ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']

        missing = [var for var in required_vars if not os.getenv(var)]

        if missing:
            logger.error(f"Missing LiveKit credentials: {missing}")
            return False

        livekit_url = os.getenv('LIVEKIT_URL', '')
        if not livekit_url.startswith('wss://'):
            logger.error(f"Invalid LiveKit URL format: {livekit_url}")
            return False

        logger.info("LiveKit configuration check: OK")
        return True

    async def check_llm_config(self) -> bool:
        """Verify LLM credentials are present."""
        cerebras_key = os.getenv('CEREBRAS_API_KEY', '')

        if not cerebras_key:
            logger.error("Missing CEREBRAS_API_KEY")
            return False

        logger.info("LLM configuration check: OK")
        return True

    async def check_stt_tts_config(self) -> bool:
        """Verify STT/TTS credentials are present."""
        deepgram_key = os.getenv('DEEPGRAM_API_KEY', '')
        cartesia_key = os.getenv('CARTESIA_API_KEY', '')

        if not deepgram_key:
            logger.error("Missing DEEPGRAM_API_KEY")
            return False

        if not cartesia_key:
            logger.error("Missing CARTESIA_API_KEY")
            return False

        logger.info("STT/TTS configuration check: OK")
        return True

    async def check_n8n_config(self) -> bool:
        """Verify n8n webhook base URL is configured."""
        n8n_base = os.getenv('N8N_WEBHOOK_BASE', '')

        if not n8n_base:
            logger.error("Missing N8N_WEBHOOK_BASE")
            return False

        if not (n8n_base.startswith('http://') or n8n_base.startswith('https://')):
            logger.error(f"Invalid N8N_WEBHOOK_BASE format: {n8n_base}")
            return False

        logger.info("n8n configuration check: OK")
        return True

    async def check_agent_process(self) -> bool:
        """Check if agent process is responsive (basic check)."""
        # For MVP, just verify we can import the agent module
        try:
            # Attempt to import agent module (validates Python environment)
            import importlib.util
            spec = importlib.util.find_spec("src.agent")
            if spec is None:
                logger.error("Agent module not found")
                return False

            logger.info("Agent module check: OK")
            return True
        except Exception as e:
            logger.error(f"Agent module check failed: {e}")
            return False

    async def run_all_checks(self) -> Dict[str, bool]:
        """Execute all health checks in parallel."""
        checks = {
            'config': self.check_config_exists(),
            'database': self.check_database(),
            'livekit': self.check_livekit_config(),
            'llm': self.check_llm_config(),
            'stt_tts': self.check_stt_tts_config(),
            'n8n': self.check_n8n_config(),
            'agent_module': self.check_agent_process(),
        }

        results = {}
        for name, check_coro in checks.items():
            try:
                results[name] = await check_coro
            except Exception as e:
                logger.error(f"Health check '{name}' raised exception: {e}")
                results[name] = False

        return results


async def main():
    """Main health check execution."""
    logger.info(f"Starting health check for department: {os.getenv('DEPARTMENT_ID', 'unknown')}")

    checker = HealthChecker()
    results = await checker.run_all_checks()

    # Determine overall health
    critical_checks = ['config', 'livekit', 'llm', 'stt_tts', 'n8n', 'agent_module']
    critical_failed = [name for name in critical_checks if not results.get(name, False)]

    if critical_failed:
        logger.error(f"HEALTH CHECK FAILED - Critical checks failed: {critical_failed}")
        logger.error(f"Full results: {results}")
        return 1  # Exit code 1 = unhealthy

    # Check if any non-critical checks failed
    non_critical_failed = [name for name in results if name not in critical_checks and not results[name]]
    if non_critical_failed:
        logger.warning(f"Non-critical checks failed: {non_critical_failed}")

    logger.info("HEALTH CHECK PASSED - All critical systems operational")
    logger.info(f"Full results: {results}")
    return 0  # Exit code 0 = healthy


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
