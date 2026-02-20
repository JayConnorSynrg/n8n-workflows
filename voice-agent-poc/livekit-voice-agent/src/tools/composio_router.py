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

# Service-grouped slugs for catalog generation (zero-latency after index build)
_slugs_by_service: dict[str, list[str]] = {}

# Ordered longest-prefix-first to avoid partial matches
_SERVICE_PREFIXES: list[tuple[str, str]] = [
    ("MICROSOFT_TEAMS_", "microsoft_teams"),
    ("ONE_DRIVE_", "one_drive"),
    ("COMPOSIO_SEARCH_", "composio_search"),
    ("COMPOSIO_", "composio"),
    ("GOOGLESHEETS_", "google_sheets"),
    ("GOOGLEDOCS_", "google_docs"),
    ("GMAIL_", "gmail"),
    ("GITHUB_", "github"),
    ("CANVA_", "canva"),
    ("SUPABASE_", "supabase"),
    ("SLACK_", "slack"),
    ("EXCEL_", "excel"),
    ("PINECONE_", "pinecone"),
    ("RECALLAI_", "recallai"),
    ("GAMMA_", "gamma"),
]

# Tier constants for resolution confidence
_TIER_EXACT = 1
_TIER_SUFFIX = 2
_TIER_PREFIX = 3
_TIER_WORDS = 4    # unreliable — triggers SDK fallback
_TIER_SUBSTR = 5
_TIER_PARTIAL = 6

# Service aliases for catalog filtering
_SERVICE_ALIASES: dict[str, str] = {
    "teams": "microsoft_teams",
    "onedrive": "one_drive",
    "drive": "one_drive",
    "sheets": "google_sheets",
    "docs": "google_docs",
    "search": "composio_search",
    "web": "composio_search",
}


def cache_slug(slug: str) -> None:
    """Mark a tool slug as recently used."""
    _slug_cache[slug] = time.time()


def is_slug_cached(slug: str) -> bool:
    """Check if a slug was recently used (within TTL)."""
    ts = _slug_cache.get(slug)
    if ts and (time.time() - ts) < _SLUG_CACHE_TTL:
        return True
    return False


def _discover_connected_toolkits(client, user_id: str) -> list[str]:
    """Query Composio API for the user's actually connected app toolkits.

    Returns toolkit slugs (lowercase) for all apps the user has connected
    on the Composio dashboard. These are merged with the static config
    to ensure we only index tools the user can actually execute.

    SDK signature: client.connected_accounts.list(user_ids=[...], statuses=[...])
    Returns ConnectedAccountListResponse with .items: List[Item]
    Each Item has .toolkit.slug (str) and .status (str)
    """
    try:
        response = client.connected_accounts.list(
            user_ids=[user_id],
            statuses=["ACTIVE"],
        )

        items = response.items if hasattr(response, "items") else []
        if not items:
            logger.info("Composio: No active connected accounts found for user")
            return []

        connected = set()
        for account in items:
            toolkit_obj = getattr(account, "toolkit", None)
            slug = getattr(toolkit_obj, "slug", None) if toolkit_obj else None
            if slug:
                connected.add(slug.lower().strip())

        logger.info(f"Composio: {len(connected)} connected accounts discovered — {sorted(connected)}")
        return list(connected)

    except Exception as exc:
        logger.warning(f"Composio: Could not discover connected accounts: {exc}")
        return []


def _extract_service_key(slug: str) -> str:
    """Map a canonical slug to its service key using prefix table."""
    for prefix, key in _SERVICE_PREFIXES:
        if slug.startswith(prefix):
            return key
    return "other"


def _build_slug_index(client, user_id: str = "") -> None:
    """Build canonical slug index from always-available + connected toolkits.

    Called once at first tool execution. Populates _canonical_slugs
    with every available tool slug from the Composio API.

    Strategy:
    1. Always load composio + composio_search (no connection required)
    2. Query Composio for user's connected apps (dynamic)
    3. Load all connected toolkits
    4. No config file or env var — 100% driven by Composio state

    NOTE: The API returns max ~20 tools per toolkit call, so we must
    load each toolkit individually and combine results.
    """
    global _canonical_slugs, _slug_index_built
    if _slug_index_built:
        return

    # These two toolkits are always available (no connection required)
    ALWAYS_AVAILABLE = ["composio", "composio_search"]

    # Discover what the user actually has connected
    connected = set()
    if user_id:
        connected = set(_discover_connected_toolkits(client, user_id))

    # Build active toolkit list: base + all connected
    active_toolkits = list(ALWAYS_AVAILABLE)
    for conn_toolkit in sorted(connected):
        if conn_toolkit not in ALWAYS_AVAILABLE:
            active_toolkits.append(conn_toolkit)

    if connected:
        logger.info(f"Composio: {len(connected)} connected services: {sorted(connected)}")
    else:
        logger.info("Composio: No connected accounts found, loading base toolkits only")

    all_slugs: list[str] = []
    for toolkit in active_toolkits:
        try:
            tools = client.tools.get_raw_composio_tools(toolkits=[toolkit])
            slugs = [t.slug for t in tools]
            all_slugs.extend(slugs)
            logger.debug(f"Composio: Loaded {len(slugs)} tools from {toolkit}")
        except Exception as exc:
            logger.warning(f"Composio: Failed to load toolkit {toolkit}: {exc}")

    _canonical_slugs = all_slugs
    _slug_index_built = True

    # Build service-grouped index for catalog generation
    global _slugs_by_service
    by_service: dict[str, list[str]] = {}
    for slug in _canonical_slugs:
        key = _extract_service_key(slug)
        by_service.setdefault(key, []).append(slug)
    _slugs_by_service = by_service

    logger.info(
        f"Composio: Slug index built — {len(_canonical_slugs)} tools "
        f"from {len(active_toolkits)} active toolkits. "
        f"Service grouping: {', '.join(f'{k}({len(v)})' for k, v in sorted(by_service.items()))}"
    )


def get_tool_catalog(service_filter: str | None = None) -> str:
    """Return plain-text catalog of exact slugs grouped by service.

    Zero latency after index build — reads from _slugs_by_service dict.
    Supports service aliases (e.g. "teams" → "microsoft_teams").
    """
    if not _slug_index_built:
        return "Tool catalog not ready yet. Call composioExecute or composioBatchExecute first to trigger index build."

    if not _slugs_by_service:
        return "No tools available. Check Composio configuration and connected accounts."

    # Resolve service alias
    if service_filter:
        key = service_filter.lower().strip()
        key = _SERVICE_ALIASES.get(key, key)
        slugs = _slugs_by_service.get(key)
        if slugs:
            lines = [f"=== {key.upper()} ({len(slugs)} tools) ==="]
            for slug in sorted(slugs):
                lines.append(f"  {slug}")
            return "\n".join(lines)
        # Check if partial match
        matches = {k: v for k, v in _slugs_by_service.items() if key in k}
        if matches:
            lines = []
            for svc, slugs in sorted(matches.items()):
                lines.append(f"=== {svc.upper()} ({len(slugs)} tools) ===")
                for slug in sorted(slugs):
                    lines.append(f"  {slug}")
            return "\n".join(lines)
        available = ", ".join(sorted(_slugs_by_service.keys()))
        return f"No tools found for service '{service_filter}'. Available services: {available}"

    # Full catalog — all services (exclude meta-toolkits that confuse LLM)
    # composio and composio_search are discovery/meta tools — the LLM calls them
    # instead of actual action tools, causing a stall after the search step.
    _EXCLUDED_SERVICES = {"composio", "composio_search"}
    action_slugs = {k: v for k, v in _slugs_by_service.items() if k not in _EXCLUDED_SERVICES}
    total = sum(len(v) for v in action_slugs.values())
    lines = [f"COMPOSIO TOOL CATALOG — {total} action tools"]
    for svc, slugs in sorted(action_slugs.items()):
        lines.append(f"\n=== {svc.upper()} ({len(slugs)} tools) ===")
        for slug in sorted(slugs):
            lines.append(f"  {slug}")
    return "\n".join(lines)


def _resolve_slug_fast(raw_slug: str) -> tuple[str | None, int]:
    """Resolve a slug to canonical form and return confidence tier.

    Returns (resolved_slug, tier). Tiers 1-3 are trusted.
    Tiers 4-6 are UNVERIFIED and should trigger SDK search for verification.

    Tiers:
      1. Exact match
      2. Suffix match (unique)
      3. Prefix expansion match
      4. Word containment (unreliable — may match wrong tool)
      5. Substring match
      6. Partial word overlap
    """
    if not _canonical_slugs:
        return raw_slug, _TIER_EXACT  # No index, pass through

    upper = raw_slug.upper().strip()

    # Tier 1: Exact match
    if upper in _canonical_slugs:
        return upper, _TIER_EXACT

    # Tier 2: Suffix match (canonical ends with raw slug)
    suffix_matches = [s for s in _canonical_slugs if s.endswith(upper)]
    if len(suffix_matches) == 1:
        logger.info(f"Composio: Slug resolved (tier 2 suffix): {raw_slug} → {suffix_matches[0]}")
        return suffix_matches[0], _TIER_SUFFIX

    # Tier 3: Prefix expansion (TEAMS_ → MICROSOFT_TEAMS_, etc.)
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
                logger.info(f"Composio: Slug resolved (tier 3 prefix): {raw_slug} → {expanded}")
                return expanded, _TIER_PREFIX

    # Tier 4: Word containment (all words in raw slug appear in canonical)
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
        logger.info(f"Composio: Slug resolved (tier 4 words UNVERIFIED): {raw_slug} → {best_match}")
        return best_match, _TIER_WORDS

    # Tier 5: Substring match
    substr_matches = [s for s in _canonical_slugs if upper in s]
    if len(substr_matches) == 1:
        logger.info(f"Composio: Slug resolved (tier 5 substring UNVERIFIED): {raw_slug} → {substr_matches[0]}")
        return substr_matches[0], _TIER_SUBSTR
    elif len(substr_matches) > 1:
        shortest = min(substr_matches, key=len)
        logger.info(f"Composio: Slug resolved (tier 5 substring/shortest UNVERIFIED): {raw_slug} → {shortest}")
        return shortest, _TIER_SUBSTR

    # Tier 6: Partial word overlap (need at least 2 words)
    best_match = None
    best_score = 0
    for canonical in _canonical_slugs:
        canonical_words = set(canonical.split("_"))
        overlap = len(raw_words & canonical_words)
        if overlap >= 2 and overlap > best_score:
            best_score = overlap
            best_match = canonical

    if best_match:
        logger.info(f"Composio: Slug resolved (tier 6 partial UNVERIFIED): {raw_slug} → {best_match}")
        return best_match, _TIER_PARTIAL

    # No match at any tier
    logger.warning(f"Composio: Could not resolve slug: {raw_slug} (not in {len(_canonical_slugs)} available tools)")
    return None, 0


def _sdk_search_slug(client, raw_slug: str) -> str | None:
    """Search Composio SDK for a tool matching the raw slug.

    Converts the slug to search terms and queries the API.
    Extends _canonical_slugs with any new slugs discovered.
    Returns best match or None.

    This is a synchronous function — call via asyncio.to_thread().
    """
    global _canonical_slugs

    # Convert slug to search terms: TEAMS_LIST_CHANNELS → "teams list channels"
    terms = raw_slug.upper().strip().replace("_", " ").lower()

    try:
        results = client.tools.get_raw_composio_tools(search=terms, limit=5)
    except Exception as exc:
        logger.warning(f"Composio SDK search failed for '{terms}': {exc}")
        return None

    if not results:
        logger.info(f"Composio SDK search: no results for '{terms}'")
        return None

    # Extend canonical index with any new slugs
    existing = set(_canonical_slugs)
    new_slugs = [t.slug for t in results if t.slug not in existing]
    if new_slugs:
        _canonical_slugs.extend(new_slugs)
        # Update service grouping
        for slug in new_slugs:
            key = _extract_service_key(slug)
            _slugs_by_service.setdefault(key, []).append(slug)
        logger.info(f"Composio SDK search: added {len(new_slugs)} new slugs to index")

    # Score results by word overlap with raw slug
    raw_words = set(raw_slug.upper().strip().split("_"))
    best_match = None
    best_score = 0
    for tool in results:
        tool_words = set(tool.slug.split("_"))
        overlap = len(raw_words & tool_words)
        # Prefer exact word count match, penalize extra words
        score = overlap * 100 - abs(len(tool_words) - len(raw_words)) * 10
        if score > best_score:
            best_score = score
            best_match = tool.slug

    if best_match:
        logger.info(f"Composio SDK search: '{raw_slug}' → {best_match} (score={best_score})")
    return best_match


def _get_alternative_slugs(raw_slug: str, top_n: int = 5) -> list[str]:
    """Score all canonical slugs by word overlap and return top N candidates."""
    if not _canonical_slugs:
        return []

    raw_words = set(raw_slug.upper().strip().split("_"))
    scored: list[tuple[int, str]] = []
    for canonical in _canonical_slugs:
        canonical_words = set(canonical.split("_"))
        overlap = len(raw_words & canonical_words)
        if overlap >= 1:
            # Score: word overlap * 100 - length penalty
            score = overlap * 100 - len(canonical)
            scored.append((score, canonical))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [slug for _, slug in scored[:top_n]]


def _get_client(settings):
    """Get or create a cached Composio SDK client.

    NOTE: toolkit_versions="latest" does NOT work for manual tools.execute() calls.
    The SDK requires either a specific version string or dangerously_skip_version_check=True
    when calling execute() directly (not through framework integrations).
    """
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

    # 2.5. Direct content fields (search answers, text content, body)
    for key in ("answer", "text", "content", "body", "summary", "description", "output"):
        val = data.get(key, inner.get(key, "") if isinstance(inner, dict) else "")
        if val and isinstance(val, str) and len(val) > 5:
            return val[:500]

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


def prewarm_slug_index() -> str:
    """Synchronous slug index build + catalog generation for prewarm phase.

    Called once at worker process start (not per-meeting). Returns the
    full tool catalog string for injection into the system prompt.
    """
    from ..config import get_settings
    settings = get_settings()
    if not settings.composio_api_key or not settings.composio_user_id:
        logger.info("Composio: Skipping prewarm (no API key or user ID)")
        return ""
    try:
        client = _get_client(settings)
        user_id = settings.composio_user_id.strip()
        _build_slug_index(client, user_id)
        catalog = get_tool_catalog()
        logger.info(f"Composio: Prewarm complete — catalog {len(catalog)} chars")
        return catalog
    except Exception as exc:
        logger.warning(f"Composio: Prewarm failed: {exc}")
        return ""


async def ensure_slug_index() -> None:
    """Build slug index if not already built. Safe to call multiple times."""
    if _slug_index_built:
        return
    from ..config import get_settings
    settings = get_settings()
    if not settings.composio_api_key or not settings.composio_user_id:
        return
    client = _get_client(settings)
    user_id = settings.composio_user_id.strip()
    await asyncio.to_thread(lambda: _build_slug_index(client, user_id))


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

    # Build slug index on first call (discovers connected accounts + loads tool slugs)
    if not _slug_index_built:
        user_id = settings.composio_user_id.strip()
        await asyncio.to_thread(lambda: _build_slug_index(client, user_id))

    # Two-stage slug resolution:
    # Stage 1: Fast local resolution with confidence tier
    fast_match, tier = _resolve_slug_fast(tool_slug)

    # Stage 2: SDK search for low-confidence or failed matches
    resolved_slug = fast_match
    if tier >= _TIER_WORDS and fast_match is not None:
        # Tier 4-6: fuzzy match — verify/override via SDK search
        logger.info(f"Composio: Tier {tier} match for {tool_slug} → {fast_match}, verifying via SDK search")
        sdk_match = await asyncio.to_thread(lambda: _sdk_search_slug(client, tool_slug))
        if sdk_match:
            resolved_slug = sdk_match
            logger.info(f"Composio: SDK search overrode tier {tier}: {tool_slug} → {sdk_match}")
        else:
            logger.info(f"Composio: SDK search confirmed tier {tier} match: {fast_match}")
    elif fast_match is None:
        # No local match at all — SDK search as last resort
        logger.info(f"Composio: No local match for {tool_slug}, trying SDK search")
        sdk_match = await asyncio.to_thread(lambda: _sdk_search_slug(client, tool_slug))
        if sdk_match:
            resolved_slug = sdk_match
            logger.info(f"Composio: SDK search found: {tool_slug} → {sdk_match}")
        else:
            # Complete failure — return error with alternatives
            _failed_slugs[slug_key] = _failed_slugs.get(slug_key, 0) + 1
            alternatives = _get_alternative_slugs(tool_slug)
            alt_text = " or ".join(alternatives[:3]) if alternatives else "none found"
            logger.warning(
                f"Composio: Slug unresolvable: {tool_slug} "
                f"(failure {_failed_slugs[slug_key]}/{_CB_MAX_FAILURES}, alternatives: {alternatives[:5]})"
            )
            return (
                f"Tool {tool_slug} not found. Did you mean: {alt_text}? "
                f"Call listComposioTools to see all available slugs."
            )

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
                resolved_slug,
                arguments,
                user_id=user_id,
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


async def get_connected_services_status() -> str:
    """Return voice-friendly list of connected and available services.

    Uses the slug index service grouping to report what's connected.
    If index not built, triggers a build first.
    """
    await ensure_slug_index()

    if not _slugs_by_service:
        return "No services are connected yet"

    # Exclude meta-toolkits from the connected list
    _EXCLUDED = {"composio", "composio_search", "other"}
    connected = sorted(k for k in _slugs_by_service.keys() if k not in _EXCLUDED)

    if not connected:
        return "No external services are connected yet"

    # Format service names for voice
    _VOICE_NAMES = {
        "microsoft_teams": "Microsoft Teams",
        "one_drive": "OneDrive",
        "gmail": "Gmail",
        "google_sheets": "Google Sheets",
        "google_docs": "Google Docs",
        "github": "GitHub",
        "canva": "Canva",
        "supabase": "Supabase",
        "excel": "Excel",
        "slack": "Slack",
        "pinecone": "Pinecone",
        "recallai": "Recall AI",
        "gamma": "Gamma",
    }

    names = [_VOICE_NAMES.get(s, s.replace("_", " ").title()) for s in connected]
    tool_counts = [f"{_VOICE_NAMES.get(s, s)} with {len(_slugs_by_service[s])} tools" for s in connected]

    if len(names) == 1:
        summary = names[0]
    elif len(names) == 2:
        summary = f"{names[0]} and {names[1]}"
    else:
        summary = ", ".join(names[:-1]) + f", and {names[-1]}"

    return f"You have {len(connected)} services connected: {summary}"


async def initiate_service_connection(service: str) -> tuple[str, str]:
    """Initiate a new Composio connection for a service.

    Calls the COMPOSIO_INITIATE_CONNECTION tool to get an auth URL.
    Returns (auth_url, display_name) on success, or (error_message, "") on failure.
    """
    # Normalize service name
    service_lower = service.lower().strip().replace(" ", "_")
    _VOICE_NAMES = {
        "teams": "Microsoft Teams",
        "microsoft_teams": "Microsoft Teams",
        "onedrive": "OneDrive",
        "one_drive": "OneDrive",
        "gmail": "Gmail",
        "sheets": "Google Sheets",
        "google_sheets": "Google Sheets",
        "docs": "Google Docs",
        "google_docs": "Google Docs",
        "github": "GitHub",
        "canva": "Canva",
        "supabase": "Supabase",
        "excel": "Excel",
        "slack": "Slack",
        "pinecone": "Pinecone",
        "gamma": "Gamma",
    }
    display_name = _VOICE_NAMES.get(service_lower, service.title())

    # Try to initiate connection via Composio toolkit
    result = await execute_composio_tool(
        tool_slug="COMPOSIO_INITIATE_CONNECTION",
        arguments={"app_name": service_lower},
    )

    # Check if result contains a URL (auth link)
    if result and ("http" in result.lower() or "url" in result.lower()):
        # Extract URL from result
        import re
        url_match = re.search(r'https?://[^\s"\'<>]+', result)
        if url_match:
            return url_match.group(0), display_name

    # If no URL found, return the result as error
    if "does not exist" in result.lower() or "not found" in result.lower():
        return f"Connection setup for {display_name} is not available through voice. Please set it up at composio.dev", ""

    return result, display_name


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
