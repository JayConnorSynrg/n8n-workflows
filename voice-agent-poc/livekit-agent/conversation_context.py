"""
Conversation Context Management for Voice Agent
Port of the JavaScript ConversationContext class from relay-server/index-enhanced.js

This class maintains full conversation history including tool calls for:
1. Logging to n8n
2. Tool execution context (n8n needs conversation history)
3. Session recovery if needed
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import json


@dataclass
class ConversationItem:
    """Base class for conversation items"""
    type: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class UserMessage(ConversationItem):
    """User message in conversation"""
    type: str = "user_message"
    content: str = ""


@dataclass
class AssistantMessage(ConversationItem):
    """Assistant message in conversation"""
    type: str = "assistant_message"
    content: str = ""


@dataclass
class ToolCall(ConversationItem):
    """Tool call in conversation"""
    type: str = "tool_call"
    name: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    call_id: str = ""
    result: Optional[Dict[str, Any]] = None
    completed_at: Optional[str] = None


@dataclass
class ToolResult(ConversationItem):
    """Tool result in conversation"""
    type: str = "tool_result"
    call_id: str = ""
    result: Dict[str, Any] = field(default_factory=dict)


class ConversationContext:
    """
    Maintains full conversation history including tool calls.

    OpenAI Realtime API maintains context automatically, but we track it for:
    1. Logging to n8n
    2. Tool execution context (n8n needs to know conversation history)
    3. Session recovery if needed
    """

    def __init__(self, connection_id: str):
        self.connection_id = connection_id
        self.items: List[ConversationItem] = []
        self.tool_calls: List[ToolCall] = []
        self.start_time = datetime.utcnow().isoformat()
        self.last_activity = datetime.utcnow().isoformat()

    def _update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow().isoformat()

    def add_user_message(self, transcript: str) -> UserMessage:
        """Add a user message to the conversation"""
        self._update_activity()
        message = UserMessage(
            content=transcript,
            timestamp=self.last_activity
        )
        self.items.append(message)
        return message

    def add_assistant_message(self, transcript: str) -> AssistantMessage:
        """Add an assistant message to the conversation"""
        self._update_activity()
        message = AssistantMessage(
            content=transcript,
            timestamp=self.last_activity
        )
        self.items.append(message)
        return message

    def add_tool_call(self, name: str, args: Dict[str, Any], call_id: str) -> ToolCall:
        """Add a tool call to the conversation"""
        self._update_activity()
        tool_call = ToolCall(
            name=name,
            args=args,
            call_id=call_id,
            timestamp=self.last_activity
        )
        self.items.append(tool_call)
        self.tool_calls.append(tool_call)
        return tool_call

    def set_tool_result(self, call_id: str, result: Dict[str, Any]) -> None:
        """Set the result of a tool call"""
        self._update_activity()

        # Update the tool call record
        for tool_call in self.tool_calls:
            if tool_call.call_id == call_id:
                tool_call.result = result
                tool_call.completed_at = self.last_activity
                break

        # Add result to items
        tool_result = ToolResult(
            call_id=call_id,
            result=result,
            timestamp=self.last_activity
        )
        self.items.append(tool_result)

    def get_tool_execution_context(self) -> Dict[str, Any]:
        """
        Get context summary for n8n tool execution.
        This gives n8n the conversation history so tools can be context-aware.
        """
        return {
            "connectionId": self.connection_id,
            "sessionStart": self.start_time,
            "lastActivity": self.last_activity,
            "recentMessages": [self._item_to_dict(item) for item in self.items[-10:]],
            "previousToolCalls": [
                {
                    "name": tc.name,
                    "args": tc.args,
                    "result": tc.result,
                    "timestamp": tc.timestamp
                }
                for tc in self.tool_calls
            ],
            "messageCount": len(self.items),
            "toolCallCount": len(self.tool_calls)
        }

    def get_full_transcript(self) -> str:
        """Get full transcript for logging"""
        lines = []
        for item in self.items:
            if isinstance(item, UserMessage):
                lines.append(f"[USER {item.timestamp}]: {item.content}")
            elif isinstance(item, AssistantMessage):
                lines.append(f"[ASSISTANT {item.timestamp}]: {item.content}")
            elif isinstance(item, ToolCall):
                lines.append(f"[TOOL_CALL {item.timestamp}]: {item.name}({json.dumps(item.args)})")
            elif isinstance(item, ToolResult):
                lines.append(f"[TOOL_RESULT {item.timestamp}]: {json.dumps(item.result)}")
            else:
                lines.append(f"[UNKNOWN {item.timestamp}]: {item}")
        return "\n".join(lines)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary for final logging"""
        user_messages = sum(1 for item in self.items if isinstance(item, UserMessage))
        assistant_messages = sum(1 for item in self.items if isinstance(item, AssistantMessage))
        successful_tools = sum(1 for tc in self.tool_calls if tc.result and tc.result.get("success"))

        return {
            "connectionId": self.connection_id,
            "startTime": self.start_time,
            "endTime": datetime.utcnow().isoformat(),
            "durationMs": int((datetime.utcnow() - datetime.fromisoformat(self.start_time.replace('Z', '+00:00').replace('+00:00', ''))).total_seconds() * 1000),
            "userMessages": user_messages,
            "assistantMessages": assistant_messages,
            "toolCalls": len(self.tool_calls),
            "successfulTools": successful_tools,
            "failedTools": len(self.tool_calls) - successful_tools,
            "toolsUsed": list(set(tc.name for tc in self.tool_calls))
        }

    def get_chat_history(self) -> List[Dict[str, str]]:
        """
        Get chat history in LLM-compatible format for context injection.
        Used when sending to LLM providers that need explicit chat history.
        """
        history = []
        for item in self.items:
            if isinstance(item, UserMessage):
                history.append({"role": "user", "content": item.content})
            elif isinstance(item, AssistantMessage):
                history.append({"role": "assistant", "content": item.content})
            elif isinstance(item, ToolCall):
                # Format tool call as assistant message with function call
                history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": item.call_id,
                        "type": "function",
                        "function": {
                            "name": item.name,
                            "arguments": json.dumps(item.args)
                        }
                    }]
                })
            elif isinstance(item, ToolResult):
                history.append({
                    "role": "tool",
                    "tool_call_id": item.call_id,
                    "content": json.dumps(item.result)
                })
        return history

    def _item_to_dict(self, item: ConversationItem) -> Dict[str, Any]:
        """Convert a conversation item to a dictionary"""
        if isinstance(item, UserMessage):
            return {"type": "user_message", "content": item.content, "timestamp": item.timestamp}
        elif isinstance(item, AssistantMessage):
            return {"type": "assistant_message", "content": item.content, "timestamp": item.timestamp}
        elif isinstance(item, ToolCall):
            return {
                "type": "tool_call",
                "name": item.name,
                "args": item.args,
                "callId": item.call_id,
                "timestamp": item.timestamp,
                "result": item.result
            }
        elif isinstance(item, ToolResult):
            return {"type": "tool_result", "callId": item.call_id, "result": item.result, "timestamp": item.timestamp}
        return {"type": "unknown", "timestamp": item.timestamp}
