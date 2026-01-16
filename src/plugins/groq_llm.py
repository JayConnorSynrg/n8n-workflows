"""Groq LLM integration for LiveKit Agents."""
import os
from typing import AsyncIterator, Optional, List, Any

from livekit.agents import llm
from groq import AsyncGroq


class GroqLLM(llm.LLM):
    """Groq LLM implementation for LiveKit Agents.

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

        self._client = AsyncGroq(
            api_key=api_key or os.environ.get("GROQ_API_KEY")
        )

    @property
    def model(self) -> str:
        """Return the model name."""
        return self._model

    async def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: Optional[List[llm.FunctionTool]] = None,
        tool_choice: Optional[str] = None,  # Added: "auto", "none", or specific tool name
        temperature: Optional[float] = None,
        n: int = 1,
        parallel_tool_calls: bool = True,
    ) -> "GroqLLMStream":
        """Generate a streaming chat completion."""

        # Convert messages to Groq format
        messages = []
        for msg in chat_ctx.messages:
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
        if tools:
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    }
                }
                for tool in tools
            ]

        # Determine tool_choice: use passed value, default to "auto" if tools present
        effective_tool_choice = tool_choice if tool_choice else ("auto" if groq_tools else None)

        # Create streaming completion
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature or self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            stream=True,
            tools=groq_tools,
            tool_choice=effective_tool_choice,
            parallel_tool_calls=parallel_tool_calls if groq_tools else None,
        )

        return GroqLLMStream(stream, tools)


class GroqLLMStream(llm.LLMStream):
    """Streaming response from Groq."""

    def __init__(self, stream: Any, tools: Optional[List[llm.FunctionTool]]):
        super().__init__()
        self._stream = stream
        self._tools = tools
        self._current_tool_calls = {}

    async def __anext__(self) -> llm.ChatChunk:
        """Get next chunk from stream."""
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
