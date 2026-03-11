"""Prospect scraper tool for LinkedIn talent sourcing via n8n/Apify webhook.

Fire-and-forget pattern: POSTs to n8n, which triggers an Apify LinkedIn scrape.
The webhook returns 200 immediately — results are compiled asynchronously by n8n
and delivered downstream (email, Google Sheets, CRM, etc.).

No response body is consumed; the 10s timeout covers only webhook receipt confirmation.
"""
import logging

from ..utils.n8n_client import n8n_post as _n8n_post

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def scrape_prospects_tool(
    job_title: str,
    location: str = "United States",
    company: str = "",
    limit: int = 10,
) -> str:
    """Trigger LinkedIn prospect scrape via n8n/Apify webhook.

    Fire-and-forget: POSTs payload and returns a voice confirmation immediately.
    n8n handles all async processing; no response body is parsed.

    Args:
        job_title: Target job title to search for (e.g. "VP of Sales")
        location: Geographic location filter (default "United States")
        company: Optional company name to scope the search
        limit: Maximum number of prospects to return (default 10)

    Returns:
        Voice-friendly confirmation string for TTS output
    """
    payload: dict = {
        "jobTitle": job_title,
        "location": location,
        "limit": limit,
    }
    if company:
        payload["company"] = company

    try:
        _status, _body = await _n8n_post("apify-prospect-scrape", payload, timeout=10)
        if _status in (200, 201, 202):
            location_phrase = f" in {location}" if location and location.lower() != "united states" else f" in {location}"
            return (
                f"Starting LinkedIn prospect search for {job_title}{location_phrase}. "
                f"Results will be compiled shortly."
            )
        else:
            logger.warning(
                "scrape_prospects_tool: webhook returned HTTP %s for job_title=%r",
                _status,
                job_title,
            )
            return f"Prospect search could not be started. Webhook returned status {_status}."
    except Exception as e:
        logger.error("scrape_prospects_tool: webhook error: %s", e)
        return "Prospect search could not be started due to a network error. Please try again."
