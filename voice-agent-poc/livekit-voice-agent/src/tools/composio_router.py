"""Composio Tool Router - Dynamic tool discovery and execution.

Instead of loading ALL Composio tool schemas into the LLM context (which can
consume 10K-60K tokens), this module exposes a SINGLE meta-tool that:
1. Takes a natural language description of what the user wants
2. Calls Composio's API to find the right tool
3. Executes it server-side
4. Returns the result

This keeps LLM context usage to ~200 tokens regardless of how many
integrations are connected in Composio.
"""
import json
import logging
from typing import Annotated, Optional

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Composio API endpoints
COMPOSIO_BASE = settings.composio_base_url.rstrip("/")
COMPOSIO_HEADERS = {
    "X-API-Key": settings.composio_api_key,
    "Content-Type": "application/json",
}


async def _composio_request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """Make an authenticated request to Composio API."""
    url = f"{COMPOSIO_BASE}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        if method == "GET":
            resp = await client.get(url, headers=COMPOSIO_HEADERS)
        else:
            resp = await client.post(url, headers=COMPOSIO_HEADERS, json=body or {})

        if resp.status_code != 200:
            error_text = resp.text[:200]
            logger.error(f"Composio API error ({resp.status_code}): {error_text}")
            return {"error": f"Composio API returned {resp.status_code}: {error_text}"}

        return resp.json()


async def composio_execute(
    service: Annotated[str, "The service to use: MICROSOFT_TEAMS, ONEDRIVE, EXCEL, CANVA, APIFY, FIRECRAWL, SUPABASE, or COMPOSIO_SEARCH"],
    action: Annotated[str, "What to do, e.g. 'send a message to the general channel' or 'list files in root folder' or 'read sheet named Q3 Revenue'"],
    parameters: Annotated[Optional[str], "JSON string of additional parameters if needed, e.g. '{\"channel\": \"general\", \"message\": \"hello\"}'"] = None,
) -> str:
    """Execute an action on a connected service via Composio Tool Router.

    Use this for Microsoft Teams, OneDrive, Excel, Canva, Apify, Firecrawl,
    and Supabase operations. For Google Drive, email, database, and contacts
    use the dedicated core tools instead.
    """
    if not settings.composio_api_key:
        return "Composio is not configured. Set COMPOSIO_API_KEY to enable extended tools."

    logger.info(f"Composio Router: service={service}, action={action}")

    # Step 1: Search for the right tool/action
    search_query = f"{service} {action}"
    search_result = await _composio_request("POST", "/v3/actions/list", {
        "query": search_query,
        "limit": 3,
    })

    if "error" in search_result:
        return f"Could not find the right tool: {search_result['error']}"

    actions = search_result.get("items", search_result.get("actions", []))
    if not actions:
        return f"No matching action found for '{service} {action}'. Try rephrasing or check if the service is connected."

    # Pick the best match (first result from search)
    best_action = actions[0]
    action_id = best_action.get("name", best_action.get("id", ""))
    action_display = best_action.get("display_name", best_action.get("description", action_id))

    logger.info(f"Composio Router: matched action '{action_id}' ({action_display})")

    # Step 2: Parse parameters
    params = {}
    if parameters:
        try:
            params = json.loads(parameters) if isinstance(parameters, str) else parameters
        except json.JSONDecodeError:
            # Treat as a single value parameter
            params = {"input": parameters}

    # Step 3: Execute the action
    exec_result = await _composio_request("POST", f"/v3/actions/{action_id}/execute", {
        "params": params,
        "text": action,  # Natural language fallback for param extraction
    })

    if "error" in exec_result:
        logger.error(f"Composio execution failed: {exec_result['error']}")
        return f"Action failed: {exec_result['error']}"

    # Step 4: Format result for voice output
    result_data = exec_result.get("result", exec_result.get("data", exec_result))

    # Truncate large results for voice context
    result_str = json.dumps(result_data) if isinstance(result_data, (dict, list)) else str(result_data)
    if len(result_str) > 1000:
        result_str = result_str[:1000] + "... (truncated)"

    logger.info(f"Composio Router: action '{action_id}' completed, result length={len(result_str)}")
    return result_str
