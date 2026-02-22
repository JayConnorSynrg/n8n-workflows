"""
Async Gamma presentation tool for AIO Voice Agent.
Generation runs in background; agent is notified via notification queue when done.
"""
import asyncio
import logging
import uuid
from typing import Optional

from livekit.agents import llm

logger = logging.getLogger(__name__)

# Module-level notification queue — agent.py monitors this and calls session.say()
_notification_queue: asyncio.Queue = asyncio.Queue()

def get_notification_queue() -> asyncio.Queue:
    return _notification_queue


GAMMA_ETA_SECONDS = 45  # ~45s typical generation time
GAMMA_POLL_INTERVAL = 5
GAMMA_MAX_POLLS = 36  # 3 minutes max


async def _poll_gamma_completion(
    generation_id: str,
    topic: str,
    job_id: str,
) -> None:
    """
    Background coroutine: polls GAMMA_GET_GAMMA_FILE_URLS every 5s.
    On completion, puts notification into _notification_queue.
    """
    from ..config import get_settings
    from . import composio_router as _router

    for attempt in range(GAMMA_MAX_POLLS):
        await asyncio.sleep(GAMMA_POLL_INTERVAL)
        try:
            settings = get_settings()
            client = _router._get_client(settings)
            user_id = settings.composio_user_id.strip()

            raw = await asyncio.to_thread(
                lambda: client.tools.execute(
                    "GAMMA_GET_GAMMA_FILE_URLS",
                    {"generation_id": generation_id},
                    user_id=user_id,
                    dangerously_skip_version_check=True,
                )
            )

            logger.info(f"Gamma poll [{job_id}] attempt={attempt + 1} raw={str(raw)[:200]}")

            if not raw.get("successful"):
                logger.warning(f"Gamma poll [{job_id}] not successful yet: {raw.get('error', 'no error field')}")
                continue

            data = raw.get("data", {})
            status = data.get("status", "pending")
            logger.info(f"Gamma poll [{job_id}] attempt={attempt + 1} status={status}")

            if status == "completed":
                gamma_url = data.get("gammaUrl", "")
                message = (
                    f"Your presentation on {topic} is ready. "
                    f"You can find it at gamma dot app. "
                    f"Would you like me to email you the link?"
                )
                await _notification_queue.put({
                    "message": message,
                    "gamma_url": gamma_url,
                    "topic": topic,
                    "job_id": job_id,
                })
                return

        except Exception as e:
            logger.error(f"Gamma poll error [{job_id}] attempt={attempt + 1}: {e}")

    # Timeout after max polls
    await _notification_queue.put({
        "message": (
            f"Your presentation on {topic} is taking longer than expected. "
            f"Please check your Gamma workspace directly at gamma dot app."
        ),
        "gamma_url": None,
        "topic": topic,
        "job_id": job_id,
    })


@llm.function_tool(
    name="generatePresentation",
    description=(
        "Generate a Gamma AI presentation, document, or slide deck on any topic. "
        "Runs in the background — agent notifies user when the presentation is ready. "
        "Use when user asks to create, build, or generate a presentation, deck, or document."
    ),
)
async def generate_presentation_async(
    topic: str,
    slide_count: Optional[int] = 10,
    tone: Optional[str] = "professional",
    format: Optional[str] = "presentation",
) -> str:
    """
    Start async Gamma presentation generation.
    Returns immediately with ETA; background task polls and notifies via queue.
    """
    from ..config import get_settings
    from . import composio_router as _router

    job_id = str(uuid.uuid4())[:8]
    logger.info(f"Starting Gamma generation [{job_id}] topic={topic!r}")

    try:
        settings = get_settings()
        if not settings.composio_api_key or not settings.composio_user_id:
            return "Composio is not configured so I cannot generate presentations right now."

        client = _router._get_client(settings)
        user_id = settings.composio_user_id.strip()

        result = await asyncio.to_thread(
            lambda: client.tools.execute(
                "GAMMA_GENERATE_GAMMA",
                {
                    "inputText": topic,
                    "format": format,
                    "numCards": slide_count,
                    "textMode": "generate",
                    "textOptions": {
                        "tone": tone,
                        "language": "en",
                    },
                },
                user_id=user_id,
                dangerously_skip_version_check=True,
            )
        )

        if not result.get("successful"):
            error = result.get("error", "unknown error")
            logger.error(f"Gamma generate failed [{job_id}]: {error}")
            return (
                "I had trouble starting the presentation. "
                "Please make sure Gamma is connected and try again."
            )

        data = result.get("data", {})
        generation_id = data.get("generationId")
        status = data.get("status", "unknown")

        if status == "completed" and data.get("gammaUrl"):
            # Rare: instant completion
            return (
                f"Your presentation on {topic} is already ready. "
                f"You can view it at gamma dot app. "
                f"Would you like me to email you the link?"
            )

        if not generation_id:
            logger.error(f"Gamma returned no generationId [{job_id}]: {data}")
            return "I could not start the presentation. Please try again."

        # Spawn background poller — asyncio.create_task keeps it alive independently
        asyncio.create_task(
            _poll_gamma_completion(
                generation_id=generation_id,
                topic=topic,
                job_id=job_id,
            )
        )

        return (
            f"Got it. I am generating your presentation on {topic} right now. "
            f"It usually takes about {GAMMA_ETA_SECONDS} seconds. "
            f"I will let you know as soon as it is ready."
        )

    except Exception as e:
        logger.error(f"Gamma generation failed [{job_id}]: {e}")
        return (
            "I had trouble starting the presentation. "
            "Please make sure Gamma is connected and try again."
        )
