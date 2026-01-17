"""Groq LLM integration for LiveKit Agents 1.3.x.

CRITICAL: LiveKit Agents 1.3.x uses `async with llm.chat(...) as stream:`
The chat() method must be SYNCHRONOUS and return an async context manager.
The actual API call happens inside __aenter__, not in chat().
"""
import os
from typing import Optional, List, Any

from livekit.agents import llm
from groq import AsyncGroq


class GroqLLM(llm.LLM):
    """Groq LLM implementation for LiveKit Agents 1.3.x.

    Uses Groq's LPU inference for ultra-low latency LLM responses.
    Recommended model: llama-3.1-8b-instant (~200ms TTFT)
    """

    def __init__(
        self,
        model: str = "llama-3.1-8b-instant",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 256,
        top_p: float = 1.0,
    ):
        super().__init__()
        self._model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self._api_key = api_key or os.environ.get("GROQ_API_KEY")

    @property
    def model(self) -> str:
        """Return the model name."""
        return self._model

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: Optional[List[llm.FunctionTool]] = None,
        tool_choice: Optional[str] = None,
        conn_options: Optional[Any] = None,
        temperature: Optional[float] = None,
        n: int = 1,
        parallel_tool_calls: bool = True,
    ) -> "GroqLLMStream":
        """Return a stream object for async context manager usage.

        IMPORTANT: This is a SYNCHRONOUS method (no async def).
        LiveKit calls it as: `async with llm.chat(...) as stream:`
        The actual API call happens in GroqLLMStream.__aenter__()
        """
        return GroqLLMStream(
            api_key=self._api_key,
            model=self._model,
            chat_ctx=chat_ctx,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature or self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            parallel_tool_calls=parallel_tool_calls,
        )


class GroqLLMStream(llm.LLMStream):
    """Streaming response from Groq.

    This class is an async context manager AND async iterator.
    The API call is made in __aenter__, not in the constructor.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        chat_ctx: llm.ChatContext,
        tools: Optional[List[llm.FunctionTool]],
        tool_choice: Optional[str],
        temperature: float,
        max_tokens: int,
        top_p: float,
        parallel_tool_calls: bool,
    ):
        super().__init__()
        self._api_key = api_key
        self._model = model
        self._chat_ctx = chat_ctx
        self._tools = tools
        self._tool_choice = tool_choice
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._top_p = top_p
        self._parallel_tool_calls = parallel_tool_calls

        self._stream = None
        self._client = None
        self._current_tool_calls = {}

    async def __aenter__(self) -> "GroqLLMStream":
        """Enter async context - make the API call here."""
        self._client = AsyncGroq(api_key=self._api_key)

        # Convert messages to Groq format
        messages = []
        for msg in self._chat_ctx.messages:
            if msg.role == llm.ChatRole.SYSTEM:
                messages.append({"role": "system", "content": msg.content})
            elif msg.role == llm.ChatRole.USER:
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == llm.ChatRole.ASSISTANT:
                if msg.tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": tc.arguments,
                                }
                            }
                            for tc in msg.tool_calls
                        ]
                    })
                else:
                    messages.append({"role": "assistant", "content": msg.content})
            elif msg.role == llm.ChatRole.TOOL:
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id,
                    "content": msg.content,
                })

        # Convert tools to Groq format
        groq_tools = None
        if self._tools:
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                }
                for tool in self._tools
            ]

        # Determine tool_choice
        effective_tool_choice = self._tool_choice if self._tool_choice else ("auto" if groq_tools else None)

        # Create streaming completion
        self._stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            top_p=self._top_p,
            stream=True,
            tools=groq_tools,
            tool_choice=effective_tool_choice,
            parallel_tool_calls=self._parallel_tool_calls if groq_tools else None,
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context - cleanup."""
        if self._stream:
            if hasattr(self._stream, 'close'):
                await self._stream.close()
            elif hasattr(self._stream, 'aclose'):
                await self._stream.aclose()
        if self._client:
            await self._client.close()
        return None

    async def __anext__(self) -> llm.ChatChunk:
        """Get next chunk from stream."""
        if self._stream is None:
            raise StopAsyncIteration

        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            raise

        delta = chunk.choices[0].delta

        # Handle tool calls
        if delta.tool_calls:
            for tc in delta.tool_calls:
                if tc.index not in self._current_tool_calls:
                    self._current_tool_calls[tc.index] = {
                        "id": tc.id or "",
                        "name": "",
                        "arguments": "",
                    }

                if tc.function:
                    if tc.function.name:
                        self._current_tool_calls[tc.index]["name"] = tc.function.name
                    if tc.function.arguments:
                        self._current_tool_calls[tc.index]["arguments"] += tc.function.arguments

        # Check for finish reason
        finish_reason = chunk.choices[0].finish_reason

        tool_calls = None
        if finish_reason == "tool_calls":
            tool_calls = [
                llm.FunctionCall(
                    id=tc["id"],
                    name=tc["name"],
                    arguments=tc["arguments"],
                )
                for tc in self._current_tool_calls.values()
            ]

        return llm.ChatChunk(
            content=delta.content or "",
            tool_calls=tool_calls,
        )

    def __aiter__(self):
        return self
