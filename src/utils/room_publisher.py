"""Room Publisher — Publish tool lifecycle events to LiveKit data channel.

Gives all tool modules access to publish real-time events to the client UI
without needing a direct reference to the LiveKit room.

Events published:
  tool.call      — Tool function invoked (with name, args preview)
  tool.executing — Tool actively running
  tool.completed — Tool finished successfully (with result preview)
  tool.error     — Tool failed

  composio.searching — Composio discovery in progress
  composio.executing — Composio SDK action running
  composio.completed — Composio SDK action finished
  composio.error     — Composio SDK action failed
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Optional

from livekit import rtc

logger = logging.getLogger(__name__)

# Module-level room reference (set once in agent.py entrypoint)
_room: Optional[rtc.Room] = None


def set_room(room: rtc.Room) -> None:
    """Set the global room reference for tool event publishing."""
    global _room
    _room = room
    logger.info("Room publisher initialized")


def _generate_call_id(tool_name: str) -> str:
    """Generate a unique call ID for a tool invocation."""
    return f"{tool_name}_{uuid.uuid4().hex[:8]}"


async def _publish(data: dict) -> bool:
    """Publish a JSON message to the room data channel."""
    if not _room or not _room.local_participant:
        return False
    try:
        payload = json.dumps(data).encode("utf-8")
        await _room.local_participant.publish_data(payload)
        return True
    except Exception as e:
        logger.debug(f"Room publish failed: {e}")
        return False


def _publish_fire_and_forget(data: dict) -> None:
    """Schedule publish without awaiting — for use in sync contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_publish(data))
    except RuntimeError:
        pass


async def publish_tool_start(tool_name: str, arguments: Optional[dict] = None) -> str:
    """Publish tool.call event. Returns the generated call_id."""
    call_id = _generate_call_id(tool_name)

    # Truncate arguments preview to avoid bloating the data channel
    args_preview = {}
    if arguments:
        for k, v in list(arguments.items())[:5]:
            val = str(v)
            args_preview[k] = val[:80] if len(val) > 80 else val

    await _publish({
        "type": "tool.call",
        "call_id": call_id,
        "name": tool_name,
        "arguments": args_preview,
        "timestamp": int(time.time() * 1000),
    })
    return call_id


async def publish_tool_executing(call_id: str) -> None:
    """Publish tool.executing event."""
    await _publish({
        "type": "tool.executing",
        "call_id": call_id,
        "timestamp": int(time.time() * 1000),
    })


async def publish_tool_completed(call_id: str, result_preview: str = "") -> None:
    """Publish tool.completed event with optional result preview."""
    await _publish({
        "type": "tool.completed",
        "call_id": call_id,
        "result": result_preview[:200] if result_preview else "",
        "timestamp": int(time.time() * 1000),
    })


async def publish_tool_error(call_id: str, error: str = "") -> None:
    """Publish tool.error event."""
    await _publish({
        "type": "tool.error",
        "call_id": call_id,
        "error": error[:200] if error else "Unknown error",
        "timestamp": int(time.time() * 1000),
    })


# =============================================================================
# Composio-specific events (richer detail for extended tool oversight)
# =============================================================================

async def publish_composio_event(
    event_type: str,
    tool_slug: str,
    call_id: str,
    detail: str = "",
    duration_ms: Optional[int] = None,
) -> None:
    """Publish a Composio-specific lifecycle event.

    event_type: "composio.searching" | "composio.executing" | "composio.completed" | "composio.error"
    """
    data = {
        "type": event_type,
        "call_id": call_id,
        "tool_slug": tool_slug,
        "detail": detail[:200] if detail else "",
        "timestamp": int(time.time() * 1000),
    }
    if duration_ms is not None:
        data["duration_ms"] = duration_ms
    await _publish(data)
