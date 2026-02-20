"""Composio Tool Router — SDK-only execution.

Architecture:
  Python SDK (execution via AsyncToolWorker):
    - composioBatchExecute  — DEFAULT: parallel execution, always background
    - composioExecute       — FALLBACK: single sync reads when LLM needs results

  Slug resolution handles LLM-generated short slugs (e.g. TEAMS_SEND → MICROSOFT_TEAMS_SEND_MESSAGE).
  Circuit breaker prevents retry loops on unresolvable slugs.
"""

import asyncio
import logging
import time

from ..utils.room_publisher import (
    publish_tool_start,
    publish_tool_executing,
    publish_tool_completed,
    publish_composio_event,
)

logger = logging.getLogger(__name__)

# Cached Composio client (initialized on first use)
_composio_client = None

# Slug cache: recently-executed tool slugs with timestamp
_slug_cache: dict[str, float] = {}  # slug -> last_used_timestamp
_SLUG_CACHE_TTL = 300  # 5 minutes

# Circuit breaker: track slugs that failed resolution or execution.
# After _CB_MAX_FAILURES attempts, short-circuit with "tool does not exist".
_failed_slugs: dict[str, int] = {}  # slug -> failure count
_CB_MAX_FAILURES = 2

# Canonical slug index: ALL available tool slugs from connected toolkits.
# Built once at first execute(), used to resolve LLM-generated short slugs
# (e.g. "TEAMS_LIST_CHANNELS") to canonical SDK slugs
# (e.g. "MICROSOFT_TEAMS_GET_CHANNEL").
_canonical_slugs: list[str] = []  # populated by _build_slug_index()
_slug_index_built = False


def cache_slug(slug: str) -> None:
    """Mark a tool slug as recently used."""
    _slug_cache[slug] = time.time()


def is_slug_cached(slug: str) -> bool:
    """Check if a slug was recently used (within TTL)."""
    ts = _slug_cache.get(slug)
    if ts and (time.time() - ts) < _SLUG_CACHE_TTL:
        return True
    return False


def _build_slug_index(client, toolkits: list[str]) -> None:
    """Build canonical slug index from all connected toolkits.

    Called once at first tool execution. Populates _canonical_slugs
    with every available tool slug from the Composio API.

    NOTE: The API returns max ~20 tools per toolkit call, so we must
    load each toolkit individually and combine results.
    """
    global _canonical_slugs, _slug_index_built
    if _slug_index_built:
        return

    if not toolkits:
        logger.warning("Composio: No toolkits configured, slug index empty")
        _slug_index_built = True
        return

    all_slugs: list[str] = []
    for toolkit in toolkits:
        try:
            tools = client.tools.get_raw_composio_tools(toolkits=[toolkit])
            slugs = [t.slug for t in tools]
            all_slugs.extend(slugs)
            logger.debug(f"Composio: Loaded {len(slugs)} tools from {toolkit}")
        except Exception as exc:
            logger.warning(f"Composio: Failed to load toolkit {toolkit}: {exc}")

    _canonical_slugs = all_slugs
    _slug_index_built = True
    logger.info(
        f"Composio: Slug index built — {len(_canonical_slugs)} tools "
        f"from {len(toolkits)} toolkits"
    )


def _resolve_slug(raw_slug: str) -> str | None:
    """Resolve a potentially short/incorrect slug to the canonical SDK slug.

    The LLM often generates shortened slugs:
      - "TEAMS_SEARCH_MESSAGES" instead of "MICROSOFT_TEAMS_SEARCH_MESSAGES"
      - "GMAIL_SEND_EMAIL" instead of "GMAIL_SEND_EMAIL" (may be exact)

    Resolution strategy (ordered by confidence):
      1. Exact match in canonical index
      2. Canonical slug ends with the raw slug
      3. Try common prefix expansions (TEAMS_ → MICROSOFT_TEAMS_, etc.)
      4. Canonical slug contains all words from the raw slug
      5. Substring match (raw slug is substring of canonical)
      6. No match → return None (caller handles error)
    """
    if not _canonical_slugs:
        return raw_slug

    upper = raw_slug.upper().strip()

    # 1. Exact match
    if upper in _canonical_slugs:
        return upper

    # 2. Suffix match: canonical ends with the short slug
    suffix_matches = [s for s in _canonical_slugs if s.endswith(upper)]
    if len(suffix_matches) == 1:
        logger.info(f"Composio: Slug resolved (suffix): {raw_slug} → {suffix_matches[0]}")
        return suffix_matches[0]

    # 3. Common prefix expansion — LLM drops "MICROSOFT_" or "GOOGLE_" prefix
    prefix_expansions = {
        "TEAMS_": "MICROSOFT_TEAMS_",
        "ONEDRIVE_": "ONE_DRIVE_",
        "SHEETS_": "GOOGLESHEETS_",
        "DOCS_": "GOOGLEDOCS_",
        "DRIVE_": "ONE_DRIVE_",
    }
    for short_prefix, full_prefix in prefix_expansions.items():
        if upper.startswith(short_prefix):
            expanded = full_prefix + upper[len(short_prefix):]
            if expanded in _canonical_slugs:
                logger.info(f"Composio: Slug resolved (prefix): {raw_slug} → {expanded}")
                return expanded

    # 4. Word containment: all words in raw slug appear in canonical slug
    raw_words = set(upper.split("_"))
    best_match = None
    best_score = 0
    for canonical in _canonical_slugs:
        canonical_words = set(canonical.split("_"))
        overlap = len(raw_words & canonical_words)
        if overlap == len(raw_words):
            score = overlap * 100 - len(canonical)
            if score > best_score:
                best_score = score
                best_match = canonical

    if best_match:
        logger.info(f"Composio: Slug resolved (words): {raw_slug} → {best_match}")
        return best_match

    # 5. Substring match: raw slug appears within a canonical slug
    substr_matches = [s for s in _canonical_slugs if upper in s]
    if len(substr_matches) == 1:
        logger.info(f"Composio: Slug resolved (substring): {raw_slug} → {substr_matches[0]}")
        return substr_matches[0]
    elif len(substr_matches) > 1:
        # Pick shortest (most specific)
        shortest = min(substr_matches, key=len)
        logger.info(f"Composio: Slug resolved (substring/shortest): {raw_slug} → {shortest}")
        return shortest

    # 6. Partial word overlap (best effort, need at least 2 words)
    best_match = None
    best_score = 0
    for canonical in _canonical_slugs:
        canonical_words = set(canonical.split("_"))
        overlap = len(raw_words & canonical_words)
        if overlap >= 2 and overlap > best_score:
            best_score = overlap
            best_match = canonical

    if best_match:
        logger.info(f"Composio: Slug resolved (partial): {raw_slug} → {best_match}")
        return best_match

    # No match found — return None so caller can handle cleanly
    logger.warning(f"Composio: Could not resolve slug: {raw_slug} (not in {len(_canonical_slugs)} available tools)")
    return None


def _get_client(settings):
    """Get or create a cached Composio SDK client."""
    global _composio_client
    if _composio_client is None:
        from composio import Composio  # type: ignore[import]
        _composio_client = Composio(api_key=settings.composio_api_key)
        logger.info("Composio: SDK client initialized")
    return _composio_client


def _friendly_name(tool_slug: str) -> str:
    """Convert a tool slug like TEAMS_SEND_MESSAGE to a voice-friendly name.

    Strips common prefixes (service names) and produces natural phrases.
    E.g. GOOGLESHEETS_BATCH_UPDATE -> batch update sheets
         TEAMS_SEND_MESSAGE -> send message in Teams
    """
    slug = tool_slug.upper()
    # Known service prefixes → natural suffix
    # Order matters: longer prefixes first to avoid partial matches
    service_map = {
        "MICROSOFT_TEAMS_": "in Teams",
        "MICROSOFTTEAMS_": "in Teams",
        "TEAMS_": "in Teams",
        "ONE_DRIVE_": "on OneDrive",
        "ONEDRIVE_": "on OneDrive",
        "GOOGLE_SHEETS_": "in Sheets",
        "GOOGLESHEETS_": "in Sheets",
        "GOOGLE_DOCS_": "in Docs",
        "GOOGLEDOCS_": "in Docs",
        "EXCEL_": "in Excel",
        "SLACK_": "in Slack",
        "GMAIL_": "via email",
        "GITHUB_": "on GitHub",
        "CANVA_": "in Canva",
        "APIFY_": "",
        "FIRECRAWL_": "",
        "SUPABASE_": "in the database",
        "PERPLEXITYAI_": "via search",
        "GAMMA_": "in Gamma",
    }
    suffix = ""
    action_part = slug
    for prefix, svc_suffix in service_map.items():
        if slug.startswith(prefix):
            action_part = slug[len(prefix):]
            suffix = svc_suffix
            break

    # Convert ACTION_NAME to "action name"
    action = action_part.replace("_", " ").lower().strip()
    if suffix:
        return f"{action} {suffix}"
    return action


def _extract_voice_result(data, tool_slug: str, tool_display: str) -> str:
    """Extract a meaningful voice-friendly result from Composio response data.

    Tries multiple strategies to find useful content in the response:
    1. Explicit message field
    2. Title/name/subject fields (common in search/list results)
    3. Count of items (for list operations)
    4. Body/content/text fields (for content retrieval)
    5. Fallback to generic completion message
    """
    if not isinstance(data, dict):
        if isinstance(data, str) and len(data) > 5:
            return data[:200]
        return f"Completed {tool_display}"

    # 1. Explicit message
    message = data.get("message", "")
    if message and isinstance(message, str) and len(message) > 3:
        return message[:200]

    # 2. Response data nested in 'data' or 'response_data'
    inner = data.get("data", data.get("response_data", data))
    if isinstance(inner, dict) and inner is not data:
        msg = inner.get("message", "")
        if msg and isinstance(msg, str) and len(msg) > 3:
            return msg[:200]

    # 3. List of items (search results, file lists, messages)
    for key in ("items", "results", "messages", "files", "values", "records"):
        items = data.get(key, inner.get(key, None) if isinstance(inner, dict) else None)
        if isinstance(items, list):
            count = len(items)
            if count == 0:
                return f"No results found for {tool_display}"
            # Try to extract names/titles from first few items
            names = []
            for item in items[:5]:
                if isinstance(item, dict):
                    name = item.get("name", item.get("title", item.get("subject", "")))
                    if name:
                        names.append(str(name))
            if names:
                listing = " and ".join(names[:3])
                if count > 3:
                    listing += f" and {count - 3} more"
                return f"Found {count} results including {listing}"
            return f"Found {count} results for {tool_display}"

    # 4. Single item with title/name
    for key in ("title", "name", "subject", "fileName", "file_name"):
        val = data.get(key, "")
        if val and isinstance(val, str):
            return f"Got it {val}"

    # 5. Status/success indicators
    if data.get("success") or data.get("ok") or data.get("status") == "ok":
        return f"Done {tool_display}"

    # 6. Fallback
    return f"Completed {tool_display}"


async def execute_composio_tool(tool_slug: str, arguments: dict) -> str:
    """Execute a Composio tool via SDK and return a voice-friendly result string.

    Runs the synchronous SDK call in a thread executor to avoid blocking
    the asyncio event loop. Returns a natural language string suitable
    for TTS output (never raw JSON).

    Includes circuit breaker: after 2 failures for the same slug,
    short-circuits with "tool does not exist" to prevent retry loops.

    Args:
        tool_slug: Tool identifier (e.g. MICROSOFT_TEAMS_SEND_MESSAGE)
        arguments: Dict of arguments matching the tool's schema

    Returns:
        Voice-friendly result string
    """
    from ..config import get_settings
    settings = get_settings()

    slug_key = tool_slug.upper().strip()

    # Circuit breaker: check if this slug has failed too many times
    if _failed_slugs.get(slug_key, 0) >= _CB_MAX_FAILURES:
        logger.warning(f"Composio: Circuit breaker OPEN for {slug_key} ({_failed_slugs[slug_key]} failures)")
        return f"This tool does not exist or is not available do not retry it do not call it with different arguments"

    if not settings.composio_api_key or not settings.composio_user_id:
        return "I was not able to run this tool because Composio is not configured on this instance"

    try:
        client = _get_client(settings)
    except ImportError:
        return "I was not able to run this tool because the Composio package is not installed"

    # Build slug index on first call (loads all available tool slugs)
    if not _slug_index_built:
        toolkits_str = getattr(settings, "composio_toolkits", "")
        toolkits = [t.strip() for t in toolkits_str.split(",") if t.strip()] if toolkits_str else []
        await asyncio.to_thread(lambda: _build_slug_index(client, toolkits))

    # Resolve the slug to canonical format (handles LLM-generated short slugs)
    resolved_slug = _resolve_slug(tool_slug)

    # If slug resolution failed completely, trip circuit breaker immediately
    if resolved_slug is None:
        _failed_slugs[slug_key] = _failed_slugs.get(slug_key, 0) + 1
        logger.warning(f"Composio: Slug unresolvable: {tool_slug} (failure {_failed_slugs[slug_key]}/{_CB_MAX_FAILURES})")
        return f"This tool does not exist or is not available do not retry it do not call it with different arguments"

    if resolved_slug != slug_key:
        logger.info(f"Composio: Slug remapped: {tool_slug} → {resolved_slug}")

    tool_display = _friendly_name(resolved_slug)
    call_id = await publish_tool_start(f"composio:{resolved_slug}", {"slug": resolved_slug})

    try:
        user_id = settings.composio_user_id.strip()
        logger.info(f"Composio SDK execute: slug={resolved_slug}, user_id={user_id}, args_keys={list(arguments.keys())}")

        await publish_composio_event("composio.executing", resolved_slug, call_id, f"Running {tool_display}")
        start_ms = int(time.time() * 1000)

        result = await asyncio.to_thread(
            lambda: client.tools.execute(
                slug=resolved_slug,
                user_id=user_id,
                arguments=arguments,
                dangerously_skip_version_check=True,
            )
        )

        duration_ms = int(time.time() * 1000) - start_ms

        if result.get("successful"):
            data = result.get("data", {})
            logger.info(f"[TOOL_CALL] Composio OK: {resolved_slug} data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__} ({duration_ms}ms)")
            cache_slug(resolved_slug)
            # Reset circuit breaker on success
            _failed_slugs.pop(slug_key, None)
            voice_result = _extract_voice_result(data, resolved_slug, tool_display)
            await publish_composio_event("composio.completed", resolved_slug, call_id, voice_result[:100], duration_ms)
            await publish_tool_completed(call_id, voice_result[:100])
            return voice_result
        else:
            error = result.get("error", "unknown error")
            logger.warning(f"[TOOL_CALL] Composio FAIL: {resolved_slug} error={error} ({duration_ms}ms)")
            _failed_slugs[slug_key] = _failed_slugs.get(slug_key, 0) + 1
            await publish_composio_event("composio.error", resolved_slug, call_id, str(error)[:100], duration_ms)
            return f"I was not able to complete {tool_display} the service returned an error do not retry this tool"

    except Exception as exc:
        logger.error(f"[TOOL_CALL] Composio ERROR: {resolved_slug} exception={exc}")
        _failed_slugs[slug_key] = _failed_slugs.get(slug_key, 0) + 1
        await publish_composio_event("composio.error", resolved_slug, call_id, str(exc)[:100])
        return f"I was not able to run {tool_display} due to a connection error do not retry this tool"


async def batch_execute_composio_tools(tools: list) -> str:
    """Execute multiple Composio tools in parallel via SDK.

    Each tool in the list must have 'tool_slug' and 'arguments' keys.
    Uses asyncio.gather for true parallel execution on Composio's servers.
    Each individual tool publishes its own telemetry via execute_composio_tool().

    Returns a voice-friendly summary of all results.
    """
    if not tools:
        return "No tools to execute"

    slugs = [t.get("tool_slug", "unknown") for t in tools if t.get("tool_slug")]
    batch_call_id = await publish_tool_start(
        f"composio:batch:{len(slugs)}",
        {"tools": " + ".join(slugs[:3])},
    )
    await publish_tool_executing(batch_call_id)
    start_ms = int(time.time() * 1000)

    tasks = [
        execute_composio_tool(
            tool_slug=t.get("tool_slug", ""),
            arguments=t.get("arguments", {}),
        )
        for t in tools
        if t.get("tool_slug")
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    duration_ms = int(time.time() * 1000) - start_ms
    summaries = []
    for tool_spec, result in zip(tools, results):
        slug = tool_spec.get("tool_slug", "unknown")
        display = _friendly_name(slug)
        if isinstance(result, Exception):
            summaries.append(f"{display} failed")
            logger.error(f"Composio batch: {slug} raised {result}")
        else:
            summaries.append(str(result))

    summary = " and ".join(summaries) if summaries else "All tools completed"
    await publish_tool_completed(batch_call_id, f"{len(slugs)} tools in {duration_ms}ms")
    return summary


