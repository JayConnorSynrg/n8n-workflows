"""Centralized n8n webhook HTTP client.

Automatically injects X-AIO-Webhook-Secret and Content-Type headers
on every request. All tool files use this instead of raw aiohttp.
"""
import logging
import aiohttp
from ..config import get_settings

logger = logging.getLogger(__name__)


async def n8n_post(path: str, payload: dict, timeout: int = 30) -> tuple[int, dict]:
    """POST to an n8n webhook with auth headers automatically injected.

    Args:
        path: Webhook path relative to N8N_WEBHOOK_BASE_URL (e.g. "execute-gmail").
              Leading slash is optional.
        payload: JSON-serializable dict sent as request body.
        timeout: Request timeout in seconds (default 30).

    Returns:
        Tuple of (http_status_code, response_dict).
        On network error, raises the underlying aiohttp exception.
    """
    settings = get_settings()
    url = f"{settings.n8n_webhook_base_url}/{path.lstrip('/')}"
    headers = {
        "Content-Type": "application/json",
        "X-AIO-Webhook-Secret": settings.n8n_webhook_secret,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            return response.status, await response.json()
