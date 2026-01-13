"""
N8N Integration for Voice Agent
Port of n8n webhook integration from relay-server/index-enhanced.js

Handles:
1. Tool execution via n8n webhooks
2. Async logging to n8n Logging Agent
3. Conversation context passing for context-aware tool execution
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from conversation_context import ConversationContext

logger = logging.getLogger(__name__)


@dataclass
class N8nConfig:
    """N8N webhook configuration"""
    tools_webhook_url: str = ""
    logging_webhook_url: str = ""
    webhook_secret: str = ""
    timeout_seconds: int = 30
    retry_count: int = 3
    retry_delay_sec: float = 1.0


class N8nToolExecutor:
    """
    Executes tools via n8n webhooks with full conversation context.

    This is the "tool execution layer" - when the LLM decides to call a tool,
    we delegate to n8n which handles the actual integration (calendar, email, etc.)

    Key Feature: Includes conversation context so n8n can make context-aware decisions
    (e.g., create a task related to a just-scheduled meeting)
    """

    def __init__(self, config: N8nConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.config.timeout_seconds)
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def execute_tool(
        self,
        function_name: str,
        args: Dict[str, Any],
        connection_id: str,
        conversation_context: Optional[ConversationContext] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool via n8n webhook.

        Args:
            function_name: Name of the function to execute
            args: Function arguments
            connection_id: Unique connection identifier
            conversation_context: Full conversation context for n8n

        Returns:
            Tool execution result from n8n
        """
        if not self.config.tools_webhook_url:
            logger.warning(f"[{connection_id}] No N8N_TOOLS_WEBHOOK configured, returning mock response")
            return {
                "success": True,
                "message": f"Tool {function_name} executed successfully (mock - configure N8N_TOOLS_WEBHOOK for real execution)",
                "mock": True
            }

        try:
            logger.info(f"[{connection_id}] Executing tool via n8n: {function_name}")

            # Build headers
            headers = {"Content-Type": "application/json"}
            if self.config.webhook_secret:
                headers["X-Webhook-Secret"] = self.config.webhook_secret

            # Build payload with conversation context
            tool_context = conversation_context.get_tool_execution_context() if conversation_context else None

            payload = {
                "function": function_name,
                "args": args,
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat(),
                "context": tool_context
            }

            # Execute with retry
            client = await self._get_client()
            last_error = None

            for attempt in range(self.config.retry_count):
                try:
                    response = await client.post(
                        self.config.tools_webhook_url,
                        headers=headers,
                        json=payload
                    )

                    if response.status_code >= 400:
                        raise httpx.HTTPStatusError(
                            f"n8n webhook returned {response.status_code}",
                            request=response.request,
                            response=response
                        )

                    result = response.json()
                    logger.info(f"[{connection_id}] Tool executed successfully: {function_name}")
                    return result

                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    last_error = e
                    if attempt < self.config.retry_count - 1:
                        logger.warning(f"[{connection_id}] Tool execution attempt {attempt + 1} failed, retrying...")
                        await asyncio.sleep(self.config.retry_delay_sec * (attempt + 1))
                    else:
                        raise

            # Should not reach here, but just in case
            raise last_error or Exception("Unknown error during tool execution")

        except Exception as e:
            logger.error(f"[{connection_id}] Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to execute {function_name}: {e}"
            }


class N8nLogger:
    """
    Async logging to n8n Logging Agent.

    Fire-and-forget - never blocks the conversation.
    Preserves the existing logging infrastructure (Intent Tagger, LangChain agent, PostgreSQL).

    Enhanced: Includes full conversation context including tool calls
    """

    def __init__(self, config: N8nConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._pending_tasks: set = set()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)  # Short timeout for logging
        return self._client

    async def close(self):
        """Close the HTTP client and wait for pending tasks"""
        # Wait for pending logging tasks
        if self._pending_tasks:
            await asyncio.gather(*self._pending_tasks, return_exceptions=True)

        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def log_async(
        self,
        transcript: str,
        metadata: Dict[str, Any],
        connection_id: str,
        conversation_context: Optional[ConversationContext] = None
    ) -> None:
        """
        Send transcript to n8n logging agent asynchronously.

        Fire-and-forget - does not block the conversation.
        """
        if not self.config.logging_webhook_url:
            logger.debug(f"[{connection_id}] No N8N_LOGGING_WEBHOOK configured, skipping logging")
            return

        # Create background task
        task = asyncio.create_task(
            self._send_log(transcript, metadata, connection_id, conversation_context)
        )
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _send_log(
        self,
        transcript: str,
        metadata: Dict[str, Any],
        connection_id: str,
        conversation_context: Optional[ConversationContext] = None
    ) -> None:
        """Internal method to send log to n8n"""
        try:
            # Build headers
            headers = {"Content-Type": "application/json"}
            if self.config.webhook_secret:
                headers["X-Webhook-Secret"] = self.config.webhook_secret

            # Build payload
            payload = {
                "transcript": transcript,
                "metadata": metadata,
                "connection_id": connection_id,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Include conversation context if available
            if conversation_context:
                if metadata.get("type") != "conversation_complete":
                    # For incremental logs, include recent context
                    payload["recent_context"] = [
                        conversation_context._item_to_dict(item)
                        for item in conversation_context.items[-5:]
                    ]
                    payload["tool_call_count"] = len(conversation_context.tool_calls)
                else:
                    # For final log, include full summary and transcript
                    payload["summary"] = conversation_context.get_summary()
                    payload["full_transcript"] = conversation_context.get_full_transcript()

            # Send log
            client = await self._get_client()
            await client.post(
                self.config.logging_webhook_url,
                headers=headers,
                json=payload
            )

            logger.debug(f"[{connection_id}] Transcript sent to logging agent")

        except Exception as e:
            logger.warning(f"[{connection_id}] Logging webhook failed (non-blocking): {e}")


class N8nIntegration:
    """
    Combined n8n integration for tools and logging.
    Use this as the main interface for n8n operations.
    """

    def __init__(self, config: N8nConfig):
        self.config = config
        self.tool_executor = N8nToolExecutor(config)
        self.logger = N8nLogger(config)

    async def close(self):
        """Close all resources"""
        await self.tool_executor.close()
        await self.logger.close()

    async def execute_tool(
        self,
        function_name: str,
        args: Dict[str, Any],
        connection_id: str,
        conversation_context: Optional[ConversationContext] = None
    ) -> Dict[str, Any]:
        """Execute a tool via n8n"""
        return await self.tool_executor.execute_tool(
            function_name, args, connection_id, conversation_context
        )

    def log_message(
        self,
        transcript: str,
        role: str,
        connection_id: str,
        conversation_context: Optional[ConversationContext] = None
    ) -> None:
        """Log a message asynchronously"""
        self.logger.log_async(
            transcript,
            {"role": role, "type": "message"},
            connection_id,
            conversation_context
        )

    def log_conversation_complete(
        self,
        connection_id: str,
        conversation_context: ConversationContext
    ) -> None:
        """Log conversation completion with full summary"""
        self.logger.log_async(
            conversation_context.get_full_transcript(),
            {"type": "conversation_complete", **conversation_context.get_summary()},
            connection_id,
            conversation_context
        )
