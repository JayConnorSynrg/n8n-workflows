"""Vector store tool for adding content to Pinecone via n8n webhook.

The n8n workflow implements a 2-gate execution pattern:
1. PREPARING - Notification before adding content
2. READY_TO_STORE - Confirmation required before storage
3. COMPLETED - Completion notification
"""
import json
import uuid
from typing import Optional

from ..utils.n8n_client import n8n_post as _n8n_post
from livekit.agents import llm

from ..config import get_settings

settings = get_settings()


@llm.function_tool(
    name="store_knowledge",
    description="""Save information to the knowledge base for future retrieval.
    Use this to store important facts, meeting notes, or reference data.
    The content will be indexed for semantic search.
    Categories available: meeting notes, reference, or general.
    Takes about 10 to 20 seconds.""",
)
async def store_knowledge_tool(
    content: str,
    category: str = "general",
    source: Optional[str] = None,
) -> str:
    """Store content in the vector database via n8n webhook.

    Args:
        content: The text content to store (will be chunked and embedded)
        category: Category for organization (e.g., "meeting_notes", "reference", "general")
        source: Optional source identifier (e.g., "voice_session", "document")

    Returns:
        Success message or error description
    """
    intent_id = f"lk_{uuid.uuid4().hex[:12]}"
    payload = {
        "intent_id": intent_id,
        "session_id": "livekit-agent",
        "callback_url": f"{settings.n8n_webhook_base_url}/callback-noop",
        "content": content,
        "metadata": {
            "source": source or "voice_agent",
            "category": category,
            "added_by": "livekit-voice-agent",
        }
    }

    try:
        _status, result = await _n8n_post("voice-add-to-vector-db", payload, timeout=60)

        if _status == 200:
            status = result.get("status", "")
            if status == "COMPLETED":
                voice_response = result.get("voice_response")
                if voice_response:
                    return voice_response
                chunks = result.get("result", {}).get("chunks_stored", 0)
                return f"Successfully stored {chunks} chunks in the knowledge base."
            elif status == "CANCELLED":
                return result.get("voice_response", "Storage was cancelled")
            else:
                return "Content stored successfully."
        else:
            error_msg = result.get("error", result.get("voice_response", "Unknown error"))
            return f"Failed to store content: {error_msg}"

    except Exception as e:
        return f"Unexpected error: {str(e)}"
