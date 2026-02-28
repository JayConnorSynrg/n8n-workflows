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
    publish_tool_error,
)
try:
    from ..utils.tool_logger import log_composio_call, log_perplexity_search
    _TOOL_LOGGER_AVAILABLE = True
except Exception:  # nosec B110 — tool_logger is optional; never block tool execution
    _TOOL_LOGGER_AVAILABLE = False

    def log_composio_call(*_a, **_kw):  # type: ignore[misc]
        pass

    def log_perplexity_search(*_a, **_kw):  # type: ignore[misc]
        pass

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

# Auth failure tracker: services where OAuth token is confirmed expired.
# Key = toolkit name (e.g. "microsoft_teams"), value = re-auth URL or True.
# Prevents hammering services that can't execute until user re-authenticates.
_service_auth_failed: dict[str, bool] = {}

# INITIATED connection tracking: service_key → timestamp when auth link was sent.
# Composio INITIATED connections auto-expire after 10 minutes.
# We warn at 8 minutes and prompt the user to re-request the link.
_initiated_connections: dict[str, float] = {}
_INITIATED_EXPIRY_SECS = 480  # 8 min — warn before Composio's 10-min hard expiry

# Multi-account tracking: toolkit_slug → connected_account_id for explicit account selection.
# Populated on slug index build (most recently connected account per toolkit).
# Can be overridden by manageConnections(action=select) for user-explicit account selection.
_preferred_account_by_toolkit: dict[str, str] = {}

# Canonical slug index: ALL available tool slugs from connected toolkits.
# Built once at first execute(), used to resolve LLM-generated short slugs
# (e.g. "TEAMS_LIST_CHANNELS") to canonical SDK slugs
# (e.g. "MICROSOFT_TEAMS_GET_CHANNEL").
_canonical_slugs: list[str] = []  # populated by _build_slug_index()
_slug_index_built = False

# Service-grouped slugs for catalog generation (zero-latency after index build)
_slugs_by_service: dict[str, list[str]] = {}
# Direct slug → toolkit mapping (most reliable for service key lookups)
_slug_to_toolkit: dict[str, str] = {}
# Slug → required params list (pre-fetched during index build for catalog hints)
_slug_required_params: dict[str, list[str]] = {}

# Full parameter schemas cached at index build — required + all properties with descriptions.
# Keys: slug → {"required": [...], "properties": {name: description_str}}
# Used for: catalog param hints, pre-execution validation, inline error messages.
# Zero extra API calls — populated from tool objects already fetched in _build_slug_index.
_slug_schemas: dict[str, dict] = {}

# Per-call active schema state — loaded at call start, cleared at call end (success OR failure).
# Implements the "schema lives only for the duration of a tool call" contract:
#   LOAD: schema pulled from _slug_schemas into _active_call_schemas[call_id] before execution
#   USE:  pre-execution check + error messages read from _active_call_schemas[call_id]
#   CLEAR: finally block removes call_id entry — schema leaves "context" when call finishes
# Schema never enters LLM context on success (clean voice result only).
# Schema enters LLM context ONLY on errors so the LLM can self-correct and retry.
_active_call_schemas: dict[str, dict] = {}  # call_id → {"slug", "required", "properties"}

# Dynamic prefix map: auto-generated from actual slug data at index build time.
# Sorted longest-first to avoid partial matches. Empty until first build.
_SERVICE_PREFIXES: list[tuple[str, str]] = []

# Retry delays (seconds) for transient 429/5xx errors — 2 attempts before giving up
_RETRY_DELAYS = (1.0, 2.0)

# Tier constants for resolution confidence
_TIER_EXACT = 1
_TIER_SUFFIX = 2
_TIER_PREFIX = 3
_TIER_WORDS = 4    # unreliable — triggers SDK fallback
_TIER_SUBSTR = 5
_TIER_PARTIAL = 6

# Service aliases for catalog filtering and user input normalization
_SERVICE_ALIASES: dict[str, str] = {
    "teams": "microsoft_teams",
    "onedrive": "one_drive",
    "drive": "one_drive",
    "sheets": "google_sheets",
    "docs": "google_docs",
    "search": "composio_search",
    "web": "composio_search",
}

# Single source of truth for service → voice-friendly display name.
# Used by initiate_service_connection and get_connected_services_status.
# Keys: canonical Composio toolkit names AND common short aliases.
_COMPOSIO_VOICE_NAMES: dict[str, str] = {
    # Canonical toolkit names (what Composio API returns)
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
    "notion": "Notion",
    "hubspot": "HubSpot",
    "salesforce": "Salesforce",
    "linear": "Linear",
    "jira": "Jira",
    "asana": "Asana",
    "dropbox": "Dropbox",
    "box": "Box",
    "zoom": "Zoom",
    "typeform": "Typeform",
    "airtable": "Airtable",
    # Short aliases (match what users say: "connect teams", "connect onedrive")
    "teams": "Microsoft Teams",
    "onedrive": "OneDrive",
    "sheets": "Google Sheets",
    "docs": "Google Docs",
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


def _extract_items_from_response(response) -> list:
    """RC2 fix: probe multiple attribute names for paginated item list.

    Composio SDK 1.0.0-rc2 uses .items; older/alternate shapes use
    .data, .connected_accounts, or a bare list. Probing all prevents
    silent [] fallback when the attribute name changes across versions.
    """
    for attr in ("items", "data", "connected_accounts", "accounts"):
        val = getattr(response, attr, None)
        if isinstance(val, list):
            return val
    # Final fallback: if response itself is iterable (bare list)
    try:
        return list(response)
    except TypeError:
        return []


def _discover_connected_toolkits(client, user_id: str) -> list[str]:
    """Query Composio API for the user's actually connected app toolkits.

    Returns toolkit slugs (lowercase) for all apps the user has connected.
    Fixes applied:
      RC1 — pagination: loops via next_cursor until exhausted
      RC2 — attribute probe: handles .items / .data / .connected_accounts
      RC5 — fallback: if ACTIVE query returns empty, retries without filter
             and logs a warning so operator can diagnose stale index builds
    """
    def _fetch_page(cursor=None):
        kwargs = {"user_ids": [user_id], "statuses": ["ACTIVE"]}
        if cursor:
            kwargs["cursor"] = cursor
        return client.connected_accounts.list(**kwargs)

    try:
        connected = set()
        cursor = None
        page_num = 0
        # Build: toolkit → list of (account_id, created_at_str) for recency sorting
        _toolkit_account_candidates: dict[str, list[tuple[str, str]]] = {}

        # RC1: paginate until no next_cursor
        while True:
            page_num += 1
            response = _fetch_page(cursor)
            items = _extract_items_from_response(response)  # RC2

            for account in items:
                toolkit_obj = getattr(account, "toolkit", None)
                slug = getattr(toolkit_obj, "slug", None) if toolkit_obj else None
                acct_id = getattr(account, "id", None) or getattr(account, "account_id", None) or ""
                created_at = str(getattr(account, "created_at", "") or "")
                if slug:
                    slug_lower = slug.lower().strip()
                    connected.add(slug_lower)
                    logger.debug(
                        f"Composio: discovered {slug_lower} account_id={acct_id or '?'}"
                    )
                    if acct_id:
                        _toolkit_account_candidates.setdefault(slug_lower, []).append(
                            (acct_id, created_at)
                        )

            # Advance cursor — SDK may expose it as next_cursor, cursor, or nextCursor
            cursor = (
                getattr(response, "next_cursor", None)
                or getattr(response, "cursor", None)
                or getattr(response, "nextCursor", None)
            )
            if not cursor:
                break

        # After all pages: populate _preferred_account_by_toolkit.
        # ISO 8601 strings sort lexicographically = chronologically, so newest first.
        # Full clear + repopulate on each index rebuild (no stale entries from previous builds).
        _preferred_account_by_toolkit.clear()
        for toolkit_slug, candidates in _toolkit_account_candidates.items():
            candidates.sort(key=lambda x: x[1], reverse=True)
            _preferred_account_by_toolkit[toolkit_slug] = candidates[0][0]
            logger.debug(
                f"Composio: {toolkit_slug} preferred_account={candidates[0][0]} "
                f"({len(candidates)} total account{'s' if len(candidates) != 1 else ''})"
            )

        # RC5: if ACTIVE query returned nothing, retry without status filter
        # to detect INITIATED/EXPIRED connections and surface a warning
        if not connected:
            logger.warning(
                "Composio: ACTIVE query returned 0 connections — retrying without "
                "status filter to check for non-ACTIVE connections"
            )
            try:
                fallback_resp = client.connected_accounts.list(user_ids=[user_id])
                fallback_items = _extract_items_from_response(fallback_resp)
                non_active = {}
                for account in fallback_items:
                    toolkit_obj = getattr(account, "toolkit", None)
                    slug = getattr(toolkit_obj, "slug", None) if toolkit_obj else None
                    status = getattr(account, "status", "UNKNOWN")
                    if slug:
                        non_active[slug.lower().strip()] = status
                if non_active:
                    logger.warning(
                        f"Composio: Found {len(non_active)} non-ACTIVE connection(s) — "
                        f"these will NOT be indexed: {non_active}. "
                        "If a connection shows ACTIVE in the dashboard but not here, "
                        "the connection may be in a different API key project scope (RC4)."
                    )
                else:
                    logger.warning(
                        "Composio: No connections found even without status filter. "
                        "Verify COMPOSIO_API_KEY project scope matches where connections were created."
                    )
            except Exception as fb_exc:
                logger.warning(f"Composio: Fallback status check failed: {fb_exc}")

        logger.info(
            f"Composio: {len(connected)} connected toolkit(s) discovered "
            f"across {page_num} page(s) — {sorted(connected)}"
        )
        return list(connected)

    except Exception as exc:
        logger.warning(f"Composio: Could not discover connected accounts: {exc}")
        return []


def _extract_service_key(slug: str) -> str:
    """Map a canonical slug to its service key.

    Uses direct toolkit mapping first (exact), then falls back
    to dynamic prefix matching for newly-discovered slugs.
    """
    toolkit = _slug_to_toolkit.get(slug)
    if toolkit:
        return toolkit
    for prefix, key in _SERVICE_PREFIXES:
        if slug.startswith(prefix):
            return key
    return "other"


def _common_prefix(strings: list[str]) -> str:
    """Find the longest common prefix of a list of strings."""
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def _auto_generate_prefixes(by_service: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Generate SERVICE_PREFIXES dynamically from toolkit slug groupings.

    Finds the common prefix for all slugs in each toolkit.
    Returns list of (PREFIX_, toolkit_key) sorted longest-first.
    """
    prefixes = []
    for service_key, slugs in by_service.items():
        if not slugs:
            continue
        if len(slugs) >= 2:
            common = _common_prefix(slugs)
            # Trim to last underscore boundary
            last_us = common.rfind("_")
            if last_us > 0:
                prefix = common[:last_us + 1]
                prefixes.append((prefix, service_key))
        elif len(slugs) == 1:
            # Single slug — use everything before the last segment
            parts = slugs[0].split("_")
            if len(parts) >= 2:
                prefix = "_".join(parts[:-1]) + "_"
                prefixes.append((prefix, service_key))
    # Sort longest first to avoid partial matches
    prefixes.sort(key=lambda x: -len(x[0]))
    return prefixes


def _build_slug_index(client, user_id: str = "") -> None:
    """Build canonical slug index from always-available + connected toolkits.

    Called at first tool execution and on manual refresh. Populates:
    - _canonical_slugs: every available tool slug
    - _slug_to_toolkit: slug → toolkit name mapping
    - _slugs_by_service: toolkit → [slugs] grouping
    - _SERVICE_PREFIXES: auto-detected prefix → toolkit mapping

    Strategy:
    1. Always load composio + composio_search (no connection required)
    2. Query Composio for user's connected apps (dynamic)
    3. Load all connected toolkits, tracking which toolkit each slug belongs to
    4. Auto-generate prefix map from loaded slugs (zero hardcoded lists)
    5. No config file or env var — 100% driven by Composio state
    """
    global _canonical_slugs, _slug_index_built, _slug_to_toolkit, _slugs_by_service, _SERVICE_PREFIXES, _slug_required_params, _slug_schemas

    if _slug_index_built:
        return

    ALWAYS_AVAILABLE = ["composio", "composio_search"]

    connected = set()
    if user_id:
        connected = set(_discover_connected_toolkits(client, user_id))

    active_toolkits = list(ALWAYS_AVAILABLE)
    for conn_toolkit in sorted(connected):
        if conn_toolkit not in ALWAYS_AVAILABLE:
            active_toolkits.append(conn_toolkit)

    if connected:
        logger.info(f"Composio: {len(connected)} connected services: {sorted(connected)}")
    else:
        logger.info("Composio: No connected accounts found, loading base toolkits only")

    all_slugs: list[str] = []
    slug_toolkit_map: dict[str, str] = {}
    by_service: dict[str, list[str]] = {}
    required_params: dict[str, list[str]] = {}
    schemas: dict[str, dict] = {}

    for toolkit in active_toolkits:
        try:
            tools = client.tools.get_raw_composio_tools(toolkits=[toolkit], limit=100)
            slugs = [t.slug for t in tools]
            all_slugs.extend(slugs)
            by_service[toolkit] = slugs
            for t in tools:
                slug_toolkit_map[t.slug] = toolkit
                # Extract full schema (required + all properties) from tool object.
                # Zero extra API calls — tool objects already fetched above.
                # Stores both required list (for pre-execution validation) and
                # property descriptions (for catalog hints and error messages).
                # Probe multiple attribute names — Composio SDK uses different names across versions:
                #   input_parameters = canonical field (confirmed from Composio docs)
                #   input_schema / args_schema / parameters = alternative names in older SDK versions
                schema = (
                    getattr(t, "input_parameters", None)
                    or getattr(t, "input_schema", None)
                    or getattr(t, "args_schema", None)
                    or getattr(t, "parameters", None)
                )
                if isinstance(schema, dict) and not schema.get("$ref"):
                    req = schema.get("required", [])
                    props = schema.get("properties", {})
                    # Drop properties that are pure $ref pointers (server-side refs, not resolvable locally)
                    props = {k: v for k, v in props.items() if not (isinstance(v, dict) and "$ref" in v and len(v) == 1)}
                    if req or props:
                        prop_desc = {
                            k: (v.get("description", v.get("type", "")) if isinstance(v, dict) else str(v))[:80]
                            for k, v in props.items()
                        }
                        schemas[t.slug] = {"required": req, "properties": prop_desc}
                    if req:
                        required_params[t.slug] = req
            logger.debug(f"Composio: Loaded {len(slugs)} tools from {toolkit}")
        except Exception as exc:
            logger.error(
                f"Composio: TOOLKIT_LOAD_FAILED toolkit={toolkit!r} — "
                f"all tools from this service will be unavailable: {exc!r}"
            )

    _canonical_slugs = all_slugs
    _slug_to_toolkit = slug_toolkit_map
    _slugs_by_service = by_service
    _slug_required_params = required_params
    _slug_schemas = schemas

    # Auto-generate prefix map from actual slug data (replaces hardcoded list)
    _SERVICE_PREFIXES = _auto_generate_prefixes(by_service)

    # Auto-extend service aliases for newly discovered toolkits
    for toolkit in by_service:
        parts = toolkit.split("_")
        if len(parts) >= 2:
            short = parts[-1]  # e.g., "teams" from "microsoft_teams"
            if short not in _SERVICE_ALIASES and short != toolkit:
                _SERVICE_ALIASES[short] = toolkit

    _slug_index_built = True

    logger.info(
        f"Composio: Slug index built — {len(_canonical_slugs)} tools "
        f"from {len(active_toolkits)} active toolkits. "
        f"Services: {', '.join(f'{k}({len(v)})' for k, v in sorted(by_service.items()))}. "
        f"Prefixes: {len(_SERVICE_PREFIXES)} auto-detected"
    )


def get_tool_catalog(service_filter: str | None = None) -> str:
    """Return plain-text catalog of exact slugs grouped by service.

    Zero latency after index build — reads from _slugs_by_service dict.
    Supports service aliases (e.g. "teams" → "microsoft_teams").
    """
    if not _slug_index_built:
        return "Tool catalog not ready yet. Call composioExecute or composioBatchExecute first to trigger index build."

    if not _slugs_by_service:
        return "No connected services available. Use manageConnections with action status to check what is connected."

    def _format_slug(slug: str) -> str:
        """Format a slug with inline parameter hints from cached schema.

        Shows required params when declared. Falls back to showing key optional
        params for tools that omit the 'required' array (e.g. ONE_DRIVE tools).
        This prevents the agent from calling tools blind without param context.
        """
        schema = _slug_schemas.get(slug, {})
        required = schema.get("required", [])
        properties = schema.get("properties", {})

        hints = []
        if required:
            hints.append(f"requires: {', '.join(required)}")
        elif properties:
            # Tool has parameters but no declared required array.
            # Show key params so the LLM knows what arguments exist.
            key_params = list(properties.keys())[:5]
            hints.append(f"key params: {', '.join(key_params)}")

        if hints:
            return f"  {slug} ({', '.join(hints)})"
        return f"  {slug}"

    # Resolve service alias
    if service_filter:
        key = service_filter.lower().strip()
        key = _SERVICE_ALIASES.get(key, key)
        slugs = _slugs_by_service.get(key)
        if slugs:
            lines = [f"=== {key.upper()} ({len(slugs)} tools) ==="]
            for slug in sorted(slugs):
                lines.append(_format_slug(slug))
            return "\n".join(lines)
        # Check if partial match
        matches = {k: v for k, v in _slugs_by_service.items() if key in k}
        if matches:
            lines = []
            for svc, slugs in sorted(matches.items()):
                lines.append(f"=== {svc.upper()} ({len(slugs)} tools) ===")
                for slug in sorted(slugs):
                    lines.append(_format_slug(slug))
            return "\n".join(lines)
        available = ", ".join(sorted(_slugs_by_service.keys()))
        return f"No tools found for service '{service_filter}'. Available services: {available}"

    # Full catalog — all services (exclude meta-toolkits that confuse LLM)
    # composio and composio_search are discovery/meta tools — the LLM calls them
    # instead of actual action tools, causing a stall after the search step.
    _EXCLUDED_SERVICES = {"composio", "composio_search"}
    action_slugs = {k: v for k, v in _slugs_by_service.items() if k not in _EXCLUDED_SERVICES}
    total = sum(len(v) for v in action_slugs.values())
    lines = [f"CONNECTED SERVICES CATALOG — {total} action tools"]
    lines.append("(requires: X, Y) = MUST pass these as arguments_json keys or the call will fail before reaching the API.")
    lines.append("(key params: A, B) = no required array declared but these are the available parameters.")
    for svc, slugs in sorted(action_slugs.items()):
        lines.append(f"\n=== {svc.upper()} ({len(slugs)} tools) ===")
        for slug in sorted(slugs):
            lines.append(_format_slug(slug))
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


# Slug prefix → (service label, voice suffix)
# Order matters: longer prefixes first to avoid partial matches
_SERVICE_DISPLAY_MAP: dict[str, tuple[str, str]] = {
    "MICROSOFT_TEAMS_": ("Teams", "in Teams"),
    "MICROSOFTTEAMS_": ("Teams", "in Teams"),
    "TEAMS_": ("Teams", "in Teams"),
    "ONE_DRIVE_": ("OneDrive", "on OneDrive"),
    "ONEDRIVE_": ("OneDrive", "on OneDrive"),
    "GOOGLE_SHEETS_": ("Sheets", "in Sheets"),
    "GOOGLESHEETS_": ("Sheets", "in Sheets"),
    "GOOGLE_DOCS_": ("Docs", "in Docs"),
    "GOOGLEDOCS_": ("Docs", "in Docs"),
    "GOOGLECALENDAR_": ("Calendar", "on Calendar"),
    "GOOGLE_CALENDAR_": ("Calendar", "on Calendar"),
    "GOOGLEDRIVE_": ("Drive", "on Drive"),
    "GOOGLE_DRIVE_": ("Drive", "on Drive"),
    "EXCEL_": ("Excel", "in Excel"),
    "SLACK_": ("Slack", "in Slack"),
    "GMAIL_": ("Gmail", "via email"),
    "GITHUB_": ("GitHub", "on GitHub"),
    "CANVA_": ("Canva", "in Canva"),
    "APIFY_": ("Apify", ""),
    "FIRECRAWL_": ("Firecrawl", ""),
    "SUPABASE_": ("Database", "in the database"),
    "PINECONE_": ("Search", "in search index"),
    "RECALLAI_": ("Recall", "via Recall"),
    "PERPLEXITYAI_": ("Search", "via search"),
    "GAMMA_": ("Gamma", "in Gamma"),
    "COMPOSIO_SEARCH_": ("Web Search", ""),
    "COMPOSIO_": ("Tools", ""),
}


def _parse_slug(tool_slug: str) -> tuple[str, str]:
    """Parse a slug into (service_label, action_text).

    Returns ("Teams", "Send Message") for MICROSOFT_TEAMS_SEND_MESSAGE.
    Falls back to ("Tools", "action name") for unknown prefixes.
    """
    slug = tool_slug.upper()
    for prefix, (label, _) in _SERVICE_DISPLAY_MAP.items():
        if slug.startswith(prefix):
            action = slug[len(prefix):].replace("_", " ").title()
            return label, action
    # Unknown service — use first word as label, rest as action
    parts = slug.split("_", 1)
    if len(parts) == 2:
        return parts[0].title(), parts[1].replace("_", " ").title()
    return "Tools", slug.replace("_", " ").title()


def _display_name(tool_slug: str) -> str:
    """Convert a slug to a UI display name: 'Teams: Send Message'.

    Used for tool call cards in the client UI. Never includes 'composio'.
    """
    label, action = _parse_slug(tool_slug)
    if action:
        return f"{label}: {action}"
    return label


def _friendly_name(tool_slug: str) -> str:
    """Convert a tool slug to a voice-friendly phrase.

    E.g. MICROSOFT_TEAMS_SEND_MESSAGE -> 'send message in Teams'
    Used for LLM error messages and speech context.
    """
    slug = tool_slug.upper()
    for prefix, (_, voice_suffix) in _SERVICE_DISPLAY_MAP.items():
        if slug.startswith(prefix):
            action = slug[len(prefix):].replace("_", " ").lower().strip()
            if voice_suffix:
                return f"{action} {voice_suffix}"
            return action
    return slug.replace("_", " ").lower().strip()


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
    # "value" is the OData standard key used by ALL Microsoft APIs (OneDrive, Teams, Excel, Calendar)
    for key in ("value", "items", "results", "messages", "files", "values", "records"):
        items = data.get(key, inner.get(key, None) if isinstance(inner, dict) else None)
        if isinstance(items, list):
            count = len(items)
            if count == 0:
                return f"No results found for {tool_display}"
            # Try to extract names/titles from first few items
            # Includes OData/Microsoft-specific fields: displayName (drives/users),
            # name (OneDrive items), subject (emails/events), title (documents)
            names = []
            for item in items[:5]:
                if isinstance(item, dict):
                    name = (
                        item.get("name")
                        or item.get("displayName")
                        or item.get("title")
                        or item.get("subject")
                        or item.get("fileName")
                        or ""
                    )
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


def _build_compact_catalog() -> str:
    """Build a compact service-only catalog summary for system prompt injection."""
    if not _slugs_by_service:
        return "No connected services available."

    services = sorted(k for k in _slugs_by_service.keys() if k != "other")
    service_counts = {svc: len(slugs) for svc, slugs in _slugs_by_service.items()}

    lines = ["CONNECTED SERVICES — call listComposioTools(service=X) for exact slugs"]
    for svc in services:
        count = service_counts.get(svc, 0)
        lines.append(f"  {svc} ({count} tools)")
    lines.append("")
    lines.append("Examples:")
    lines.append('  listComposioTools(service="gmail") → all Gmail slugs')
    lines.append('  listComposioTools(service="googlesheets") → all Sheets slugs')
    lines.append('  listComposioTools(service="composio_search") → all search slugs')
    lines.append("")
    lines.append("KEY SEARCH SLUGS (always available — no lookup needed):")
    # Add known search slugs inline since they're critical
    search_slugs = [s for s in _canonical_slugs if s.startswith("COMPOSIO_SEARCH_")]
    for slug in sorted(search_slugs)[:10]:  # top 10 search slugs
        lines.append(f"  {slug}")

    return "\n".join(lines)


def prewarm_slug_index() -> str:
    """Synchronous slug index build + compact catalog generation for prewarm phase.

    Called once at worker process start (not per-meeting). Returns a compact
    service summary string for injection into the system prompt. Full slug
    catalogs are fetched on-demand via listComposioTools(service=X).
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
        catalog = _build_compact_catalog()
        logger.info(f"Composio: Prewarm complete — compact catalog {len(catalog)} chars")
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


async def refresh_slug_index() -> str:
    """Force rebuild of slug index to pick up newly connected services.

    Resets the write-once lock, clears circuit breakers, and rebuilds
    from scratch. Call this after a user connects a new service so the
    agent can use it in the current session without restarting.

    Returns the updated tool catalog string.
    """
    global _slug_index_built, _slug_required_params, _slug_schemas
    _slug_index_built = False
    _failed_slugs.clear()
    _service_auth_failed.clear()  # Re-auth completed — clear auth circuit breakers
    _initiated_connections.clear()
    _slug_required_params = {}
    _slug_schemas = {}
    _active_call_schemas.clear()  # Defensive: discard any stale per-call states from before refresh

    from ..config import get_settings
    settings = get_settings()
    if not settings.composio_api_key or not settings.composio_user_id:
        return "Service connections are not configured on this instance"

    client = _get_client(settings)
    user_id = settings.composio_user_id.strip()
    await asyncio.to_thread(lambda: _build_slug_index(client, user_id))

    logger.info("Composio: Slug index refreshed (mid-session rebuild)")
    return get_tool_catalog()


async def get_tool_schema(tool_slug: str) -> str:
    """Fetch the parameter schema for a Composio tool slug.

    Returns a concise description of required and optional parameters
    formatted for LLM consumption. Uses the SDK's get_raw_composio_tools
    with search to find the tool and extract its input schema.
    """
    from ..config import get_settings
    settings = get_settings()
    if not settings.composio_api_key:
        return "Tool schema lookup is not available"

    client = _get_client(settings)
    slug_upper = tool_slug.upper().strip()

    # Resolve slug first
    resolved, tier = _resolve_slug_fast(slug_upper)
    if resolved:
        slug_upper = resolved

    def _fetch_schema():
        # Try direct toolkit lookup first
        try:
            # Search by slug terms
            terms = slug_upper.replace("_", " ").lower()
            results = client.tools.get_raw_composio_tools(search=terms, limit=5)
            for tool in results:
                if tool.slug == slug_upper:
                    return tool
        except Exception:  # nosec B110 - schema lookup is best-effort, falls through to toolkit method
            pass

        # Try loading by toolkit prefix
        toolkit = _slug_to_toolkit.get(slug_upper, "")
        if toolkit:
            try:
                tools = client.tools.get_raw_composio_tools(toolkits=[toolkit], limit=100)
                for tool in tools:
                    if tool.slug == slug_upper:
                        return tool
            except Exception:  # nosec B110 - schema lookup is best-effort, returns None on failure
                pass
        return None

    tool_obj = await asyncio.to_thread(_fetch_schema)

    if not tool_obj:
        return f"Could not find schema for {tool_slug}. Check the slug is correct against the catalog in your instructions."

    # Extract parameters from the tool's input schema
    params = getattr(tool_obj, "parameters", None) or {}
    # Handle Composio tool schema format
    if hasattr(tool_obj, "input_schema"):
        params = tool_obj.input_schema
    elif hasattr(tool_obj, "args_schema"):
        params = tool_obj.args_schema

    properties = {}
    required = []
    if isinstance(params, dict):
        properties = params.get("properties", {})
        required = params.get("required", [])

    if not properties:
        return f"Tool {slug_upper} has no documented parameters. Try executing with empty arguments."

    # Format for LLM consumption
    lines = [f"SCHEMA FOR {slug_upper}"]
    lines.append(f"Required fields: {', '.join(required) if required else 'none'}")
    lines.append("")

    for prop_name, prop_info in sorted(properties.items()):
        is_req = prop_name in required
        prop_type = prop_info.get("type", "string") if isinstance(prop_info, dict) else "string"
        description = prop_info.get("description", "") if isinstance(prop_info, dict) else ""
        marker = "REQUIRED" if is_req else "optional"
        desc_text = f" - {description[:80]}" if description else ""
        lines.append(f"  {prop_name} ({prop_type}, {marker}){desc_text}")

    return "\n".join(lines)


def _format_cached_schema(slug: str) -> str:
    """Return cached schema as concise text for LLM error messages.

    Uses data already populated in _slug_schemas during _build_slug_index.
    Zero API calls — pure local dict lookup. Returns empty string if no schema.
    """
    schema = _slug_schemas.get(slug, {})
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    if not required and not properties:
        return ""

    lines = []
    if required:
        lines.append(f"Required params: {', '.join(required)}")
    if properties:
        for prop, desc in sorted(properties.items()):
            marker = "[REQUIRED]" if prop in required else "[optional]"
            desc_text = f" — {desc[:70]}" if desc else ""
            lines.append(f"  {prop} {marker}{desc_text}")
    return "\n".join(lines)


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

    # Auth circuit breaker: check if this service's OAuth is known to be expired
    # (trip all tools in that service, not just the slug that first failed)
    service_key = _slug_to_toolkit.get(slug_key)
    if service_key and _service_auth_failed.get(service_key):
        service_display = service_key.replace("_", " ").title()
        logger.warning(f"Composio: Auth circuit breaker OPEN for service={service_key} (token expired)")
        return (
            f"The {service_display} connection needs to be re-authenticated before any {service_display} tools can run. "
            f"Do not retry {service_display} tools."
        )

    # INITIATED expiry check: auth link sent but service still not ACTIVE after 8 min
    if service_key and service_key in _initiated_connections:
        elapsed = time.time() - _initiated_connections[service_key]
        if elapsed > _INITIATED_EXPIRY_SECS:
            del _initiated_connections[service_key]
            service_display = service_key.replace("_", " ").title()
            logger.warning(f"Composio: INITIATED auth link expired for {service_key} ({elapsed:.0f}s ago)")
            return (
                f"The {service_display} connection link has expired — auth links are only valid for 10 minutes. "
                f"Use manageConnections with action connect to get a fresh link now."
            )

    if not settings.composio_api_key or not settings.composio_user_id:
        return "That connected service is not available on this instance"

    try:
        client = _get_client(settings)
    except ImportError:
        return "That connected service is not available on this instance"

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
                f"Check the catalog in your instructions for available slugs."
            )

    if resolved_slug != slug_key:
        logger.info(f"Composio: Slug remapped: {tool_slug} → {resolved_slug}")

    tool_display = _friendly_name(resolved_slug)
    ui_name = _display_name(resolved_slug)
    call_id = await publish_tool_start(ui_name, {k: str(v)[:60] for k, v in list(arguments.items())[:3]})

    # ── SCHEMA LOAD ────────────────────────────────────────────────────────────
    # Load cached schema into per-call active state.
    # Schema lives only for the duration of this tool call:
    #   LOAD here → USE in validation + error messages → CLEAR in finally block
    # On SUCCESS → schema never enters LLM context (voice result only, clean output)
    # On ERROR   → schema enters LLM context so LLM can self-correct and retry
    call_schema = _slug_schemas.get(resolved_slug, {})
    if not call_schema:
        # Cache miss — this tool may be from a newly-connected service.
        # Fetch schema live so pre-execution validation and error hints work correctly.
        logger.info(f"Composio: Schema cache miss for {resolved_slug} — fetching live")
        try:
            def _fetch_raw_for_schema():
                try:
                    terms = resolved_slug.replace("_", " ").lower()
                    results = client.tools.get_raw_composio_tools(search=terms, limit=5)
                    for tool in results:
                        if tool.slug == resolved_slug:
                            return tool
                except Exception:
                    return None
                return None

            raw_tool = await asyncio.to_thread(_fetch_raw_for_schema)
            if raw_tool is not None:
                try:
                    input_schema = raw_tool.input_parameters
                    if hasattr(input_schema, "properties"):
                        props = {}
                        for pname, pinfo in input_schema.properties.items():
                            desc = getattr(pinfo, "description", "") or getattr(pinfo, "title", "")
                            props[pname] = desc
                        required = list(getattr(input_schema, "required", []) or [])
                        call_schema = {"required": required, "properties": props}
                        _slug_schemas[resolved_slug] = call_schema  # Cache for subsequent calls
                        logger.info(f"Composio: Schema fetched live for {resolved_slug}: required={required}")
                except Exception as schema_parse_err:
                    logger.debug(f"Composio: Schema parse failed for {resolved_slug}: {schema_parse_err}")
        except Exception as live_err:
            logger.debug(f"Composio: Live schema fetch error for {resolved_slug}: {live_err}")
    _active_call_schemas[call_id] = call_schema
    call_required = call_schema.get("required", [])
    call_properties = call_schema.get("properties", {})
    logger.debug(
        f"Composio: Schema LOADED call={call_id} slug={resolved_slug} "
        f"required={call_required} props={len(call_properties)}"
    )

    # ── PRE-EXECUTION VALIDATION ───────────────────────────────────────────────
    # Check required params BEFORE hitting the API (saves a network round-trip).
    # Uses schema from _active_call_schemas — no separate API call needed.
    if call_required:
        missing = [p for p in call_required if p not in arguments]
        if missing:
            schema_text = _format_cached_schema(resolved_slug)
            schema_hint = f"\n{schema_text}" if schema_text else ""
            logger.warning(
                f"Composio: Pre-exec param check FAILED call={call_id} slug={resolved_slug}: "
                f"missing={missing}, passed={list(arguments.keys())}"
            )
            await publish_tool_error(call_id, f"Missing required params: {', '.join(missing)}")
            _active_call_schemas.pop(call_id, None)  # CLEAR — schema leaves context
            return (
                f"Tool {resolved_slug} requires these parameters: {', '.join(call_required)}. "
                f"You passed: {list(arguments.keys()) or 'nothing'}."
                f"{schema_hint}\nRetry now with all required parameters."
            )

    try:
        user_id = settings.composio_user_id.strip()
        logger.info(f"Composio SDK execute: slug={resolved_slug}, user_id={user_id}, args_keys={list(arguments.keys())}")

        await publish_tool_executing(call_id)
        start_ms = int(time.time() * 1000)

        _service_key_for_acct = (_slug_to_toolkit.get(resolved_slug) or "").lower()
        _acct_id = _preferred_account_by_toolkit.get(_service_key_for_acct) or None

        result = None
        for _attempt in range(len(_RETRY_DELAYS) + 1):
            result = await asyncio.to_thread(
                lambda: client.tools.execute(
                    resolved_slug,
                    arguments,
                    user_id=user_id,
                    connected_account_id=_acct_id,
                    dangerously_skip_version_check=True,
                )
            )
            if result.get("successful"):
                break
            # Check if this is a retryable transient error (429 or 5xx)
            _rd = result.get("data") if isinstance(result.get("data"), dict) else {}
            _sc = _rd.get("status_code")
            _es = str(result.get("error", "")).lower()
            _retryable = (
                _sc == 429 or "rate limit" in _es or "too many requests" in _es
                or (_sc is not None and 500 <= _sc < 600)
            )
            if _retryable and _attempt < len(_RETRY_DELAYS):
                _delay = _RETRY_DELAYS[_attempt]
                logger.info(f"Composio: transient error (status={_sc}) for {resolved_slug} — retry {_attempt + 1} in {_delay}s")
                await asyncio.sleep(_delay)
                continue
            break  # Non-retryable error or retries exhausted

        duration_ms = int(time.time() * 1000) - start_ms

        if result.get("successful"):
            data = result.get("data", {})
            logger.info(f"[TOOL_CALL] Composio OK: {resolved_slug} data_keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__} ({duration_ms}ms)")
            cache_slug(resolved_slug)
            # Reset circuit breaker on success
            _failed_slugs.pop(slug_key, None)
            voice_result = _extract_voice_result(data, resolved_slug, tool_display)
            await publish_tool_completed(call_id, voice_result[:100])
            # Fire-and-forget logging — zero latency impact
            log_composio_call(
                user_id=getattr(settings, 'composio_user_id', None),
                slug=resolved_slug,
                arguments=arguments,
                result_data=result.get("data"),
                voice_result=voice_result,
                success=True,
                error_message=None,
                duration_ms=duration_ms,
            )
            if "PERPLEXITYAI" in resolved_slug.upper():
                log_perplexity_search(
                    user_id=getattr(settings, 'composio_user_id', None),
                    arguments=arguments,
                    result_data=result.get("data"),
                    duration_ms=duration_ms,
                    success=True,
                )
            # MICRO 7: Parse active_connection field from COMPOSIO_SEARCH_TOOLS results.
            # Proactively sync connection status so the agent doesn't attempt disconnected services.
            if "COMPOSIO_SEARCH" in resolved_slug:
                try:
                    _search_items = []
                    if isinstance(data, dict):
                        _search_items = data.get("tools", data.get("results", data.get("items", [])))
                    elif isinstance(data, list):
                        _search_items = data
                    for _item in (_search_items if isinstance(_search_items, list) else []):
                        if not isinstance(_item, dict):
                            continue
                        _item_toolkit = (_item.get("toolkit") or _item.get("app") or "").lower().strip()
                        _active_conn = _item.get("active_connection")
                        if _item_toolkit and _active_conn is True and _item_toolkit in _service_auth_failed:
                            _service_auth_failed.pop(_item_toolkit, None)
                            logger.info(f"Composio: SEARCH shows {_item_toolkit} now connected — cleared auth failure")
                except Exception as _parse_err:
                    logger.debug(f"Composio: active_connection parse failed: {_parse_err}")

            # Schema NOT included in return — clean voice result only.
            # LLM context stays uncluttered on success. Schema cleared in finally.
            return voice_result
        else:
            error = result.get("error", "unknown error")
            error_str = str(error)
            # Extract status_code and log_id (Composio standardized these in Jan 2026 — always present on errors)
            result_data = result.get("data") if isinstance(result.get("data"), dict) else {}
            status_code = result_data.get("status_code")
            log_id = result.get("log_id")
            logger.warning(
                f"[TOOL_CALL] Composio FAIL: {resolved_slug} "
                f"status_code={status_code} log_id={log_id} error={error_str!r} ({duration_ms}ms)"
            )
            await publish_tool_error(call_id, error_str[:100])
            # Fire-and-forget failure logging — zero latency impact
            log_composio_call(
                user_id=getattr(settings, 'composio_user_id', None),
                slug=resolved_slug,
                arguments=arguments,
                result_data=None,
                voice_result="",
                success=False,
                error_message=error_str,
                duration_ms=duration_ms,
            )
            if "PERPLEXITYAI" in resolved_slug.upper():
                log_perplexity_search(
                    user_id=getattr(settings, 'composio_user_id', None),
                    arguments=arguments,
                    result_data=None,
                    duration_ms=duration_ms,
                    success=False,
                    error_message=error_str,
                )

            # Classify error using status_code (reliable, Jan 2026+) then string fallback.
            # CRITICAL DISTINCTION: 401 = token expired (circuit break + re-auth)
            #                       403 = permission denied (inform user, do NOT circuit break)
            error_lower = error_str.lower()
            is_param_error = (
                status_code in (400, 422)
                or (status_code not in (401, 403) and any(s in error_lower for s in [
                    "missing", "invalid request data", "required field",
                    "invalid value", "validation", "expected",
                    "must be provided", "are required", "is required",
                    "parameter", "argument",
                ]))
            )
            # 401 = token/credential issue → trip circuit breaker, require re-auth
            is_auth_error = (
                status_code == 401
                or (status_code is None and any(s in error_lower for s in [
                    "unauthorized", "401", "token expired", "invalid token",
                    "access token", "credentials expired", "reauthenticate",
                    "re-authenticate", "authentication failed", "oauth",
                ]))
            )
            # 403 = permission denied → OAuth is fine, resource/scope issue, do NOT circuit break
            is_permission_error = (
                status_code == 403
                or (status_code is None and not is_auth_error and any(s in error_lower for s in [
                    "forbidden", "403", "access denied", "not authorized", "permission denied",
                ]))
            )
            # 429 = rate limited → transient, do NOT circuit break
            is_rate_limited = (
                status_code == 429
                or "429" in error_str
                or "rate limit" in error_lower
                or "too many requests" in error_lower
            )
            # 5xx = server/infra error → transient, do NOT circuit break
            is_server_error = status_code is not None and 500 <= status_code < 600

            if is_param_error and not is_auth_error and not is_permission_error:
                # Parameter validation error — include schema in response so LLM can self-correct.
                # Schema comes from _active_call_schemas (no extra API call).
                # This IS the one case where schema enters LLM context — intentionally, to fix params.
                logger.info(f"Composio: Param error for {resolved_slug} — injecting cached schema for LLM retry")
                schema_text = _format_cached_schema(resolved_slug)
                if schema_text:
                    return (
                        f"Tool {resolved_slug} failed — wrong arguments: {error_str}. "
                        f"Correct parameters:\n{schema_text}\nRetry now with correct arguments."
                    )
                else:
                    return (
                        f"Tool {resolved_slug} failed — wrong arguments: {error_str}. "
                        f"Retry with corrected parameters."
                    )

            elif is_auth_error:
                # OAuth token expired (401) — attempt token refresh before circuit-breaking.
                service_key = _slug_to_toolkit.get(resolved_slug, resolved_slug)
                service_display = service_key.replace("_", " ").title()
                _refresh_ok = False
                try:
                    def _try_refresh():
                        acct_resp = client.connected_accounts.list(user_ids=[user_id])
                        for acct in _extract_items_from_response(acct_resp):
                            tk = getattr(getattr(acct, "toolkit", None), "slug", "") or ""
                            if tk.lower() == service_key.lower() and getattr(acct, "id", None):
                                client.connected_accounts.refresh(acct.id)
                                return True
                        return False
                    _refresh_ok = await asyncio.to_thread(_try_refresh)
                    if _refresh_ok:
                        logger.info(f"Composio: Token refresh attempted for {service_key} — retrying tool once")
                except Exception as _re:
                    logger.debug(f"Composio: Token refresh attempt failed for {service_key}: {_re}")

                if _refresh_ok:
                    # Retry once with a freshly refreshed token
                    try:
                        _retry = await asyncio.to_thread(
                            lambda: client.tools.execute(
                                resolved_slug, arguments,
                                user_id=user_id,
                                connected_account_id=_acct_id,
                                dangerously_skip_version_check=True,
                            )
                        )
                        if _retry.get("successful"):
                            _vr = _extract_voice_result(_retry.get("data", {}), resolved_slug, tool_display)
                            await publish_tool_completed(call_id, _vr[:100])
                            return _vr
                    except Exception:  # nosec B110 — intentional fallthrough to circuit-break on retry failure
                        pass

                # Refresh failed or retry still failed — circuit-break the service
                _service_auth_failed[service_key] = True
                _failed_slugs[slug_key] = _CB_MAX_FAILURES  # trip circuit breaker
                logger.warning(
                    f"[TOOL_CALL] Composio AUTH EXPIRED (401): {resolved_slug} "
                    f"service={service_key} log_id={log_id} error={error_str!r}"
                )
                return (
                    f"The {service_display} connection needs to be re-authorized. "
                    f"Tell the user their {service_display} access has expired and they need to reconnect it. "
                    f"You can say 'reconnect {service_display}' to send them a new authorization link via email. "
                    f"Do not retry {service_display} tools until reconnected."
                )

            elif is_permission_error:
                # Permission denied (403) — OAuth token is valid, user lacks access to this resource.
                # Do NOT circuit break — other tools on this service still work.
                service_key = _slug_to_toolkit.get(resolved_slug, resolved_slug)
                service_display = service_key.replace("_", " ").title()
                _failed_slugs[slug_key] = _failed_slugs.get(slug_key, 0) + 1
                logger.warning(
                    f"[TOOL_CALL] Composio PERMISSION (403): {resolved_slug} "
                    f"service={service_key} log_id={log_id} error={error_str!r}"
                )
                return (
                    f"I don't have permission to access that {tool_display} resource. "
                    f"Your {service_display} connection is still active — this is a permissions issue on that specific resource. "
                    f"Try a different resource or check your {service_display} account permissions."
                )

            elif is_rate_limited:
                # Rate limited (429) — transient, do NOT circuit break
                logger.warning(f"[TOOL_CALL] Composio RATE LIMITED: {resolved_slug} log_id={log_id}")
                return (
                    f"The {tool_display} service is temporarily rate-limited. "
                    f"Wait a moment and try again."
                )

            elif is_server_error:
                # Server/infra error (5xx) — transient, increment but don't max out circuit breaker
                _failed_slugs[slug_key] = _failed_slugs.get(slug_key, 0) + 1
                logger.warning(f"[TOOL_CALL] Composio SERVER ERROR {status_code}: {resolved_slug} log_id={log_id}")
                return (
                    f"The {tool_display} service returned a temporary error. "
                    f"You may retry once."
                )

            else:
                # Unknown error — suppress retries but don't claim auth issue
                _failed_slugs[slug_key] = _failed_slugs.get(slug_key, 0) + 1
                return f"I was not able to complete {tool_display} — the service returned an error. Do not retry this tool."

    except Exception as exc:
        logger.error(f"[TOOL_CALL] Composio ERROR: {resolved_slug} exception={exc}")
        _failed_slugs[slug_key] = _failed_slugs.get(slug_key, 0) + 1
        await publish_tool_error(call_id, str(exc)[:100])
        return f"I was not able to run {tool_display} due to a connection error do not retry this tool"

    finally:
        # ── SCHEMA CLEAR ───────────────────────────────────────────────────────
        # Schema leaves per-call context regardless of success or failure.
        # Keeps _active_call_schemas dict lean (no stale entries).
        if call_id in _active_call_schemas:
            _active_call_schemas.pop(call_id)
            logger.debug(f"Composio: Schema CLEARED call={call_id} slug={resolved_slug}")


async def get_connected_services_status() -> str:
    """Return voice-friendly list of services with live status values (ACTIVE/INITIATED/EXPIRED/FAILED).

    Calls connected_accounts.list() with all statuses so INITIATED and EXPIRED
    connections are visible. Side-effect: syncs _service_auth_failed with live data.
    Also shows per-account IDs when multiple accounts exist for a toolkit,
    and marks which account is currently selected.
    """
    from ..config import get_settings
    settings = get_settings()
    live_statuses: dict[str, str] = {}
    # toolkit → list of (account_id, status, created_at) for multi-account display
    _accounts_by_toolkit: dict[str, list[tuple[str, str, str]]] = {}

    if settings.composio_api_key and settings.composio_user_id:
        try:
            client = _get_client(settings)
            user_id = settings.composio_user_id.strip()

            def _fetch():
                return client.connected_accounts.list(user_ids=[user_id])

            response = await asyncio.to_thread(_fetch)
            for account in _extract_items_from_response(response):
                toolkit_obj = getattr(account, "toolkit", None)
                slug = getattr(toolkit_obj, "slug", None) if toolkit_obj else None
                status = getattr(account, "status", None)
                acct_id = getattr(account, "id", None) or getattr(account, "account_id", None) or ""
                created_at = str(getattr(account, "created_at", "") or "")
                if slug and status:
                    service_key = slug.lower().strip()
                    # Keep most-recent status per toolkit for the top-level list
                    # (prefer ACTIVE over other statuses if multiple accounts)
                    existing = live_statuses.get(service_key)
                    if existing != "ACTIVE":
                        live_statuses[service_key] = status
                    # Track all accounts per toolkit for detail lines
                    if acct_id:
                        _accounts_by_toolkit.setdefault(service_key, []).append(
                            (acct_id, status, created_at)
                        )
                    # Side-effect: keep auth failure state in sync with live data
                    if status in ("EXPIRED", "FAILED", "INACTIVE"):
                        _service_auth_failed[service_key] = True
                    elif status == "ACTIVE":
                        _service_auth_failed.pop(service_key, None)
        except Exception as exc:
            logger.warning(f"Composio: Could not fetch live connection statuses: {exc}")

    # Fall back to index-based view if live query failed
    if not live_statuses:
        await ensure_slug_index()
        if not _slugs_by_service:
            return "No services are connected yet"
        _EXCLUDED = {"composio", "composio_search", "other"}
        connected = sorted(k for k in _slugs_by_service.keys() if k not in _EXCLUDED)
        if not connected:
            return "No external services are connected yet"
        names = [_COMPOSIO_VOICE_NAMES.get(s, s.replace("_", " ").title()) for s in connected]
        return f"You have {len(connected)} active services: {', '.join(names)}"

    _EXCLUDED = {"composio", "composio_search", "other"}
    active_list, initiated_list, failed_list = [], [], []

    for service_key in sorted(live_statuses):
        if service_key in _EXCLUDED:
            continue
        status = live_statuses[service_key]
        display = _COMPOSIO_VOICE_NAMES.get(service_key, service_key.replace("_", " ").title())

        if status == "ACTIVE":
            tool_count = len(_slugs_by_service.get(service_key, []))
            cnt = f" ({tool_count} tools)" if tool_count else ""
            # Build per-account detail lines when multiple accounts exist
            accounts = _accounts_by_toolkit.get(service_key, [])
            if len(accounts) > 1:
                # Sort newest first (ISO 8601 sorts lexicographically)
                accounts_sorted = sorted(accounts, key=lambda x: x[2], reverse=True)
                selected_id = _preferred_account_by_toolkit.get(service_key, "")
                acct_lines = []
                for aid, _ast, _cat in accounts_sorted:
                    marker = " <- selected" if aid == selected_id else ""
                    acct_lines.append(f"    {aid}{marker}")
                acct_detail = "\n" + "\n".join(acct_lines)
                active_list.append(f"{display}{cnt}{acct_detail}")
            else:
                active_list.append(f"{display}{cnt}")
        elif status == "INITIATED":
            elapsed = time.time() - _initiated_connections.get(service_key, time.time())
            remaining = max(0, 600 - int(elapsed))
            if remaining > 60:
                initiated_list.append(f"{display} (auth link sent — {remaining // 60}m remaining to complete)")
            else:
                initiated_list.append(f"{display} (auth link expiring soon — complete it now or request a new one)")
        elif status in ("EXPIRED", "FAILED"):
            failed_list.append(f"{display} (needs re-authentication)")
        elif status == "INACTIVE":
            failed_list.append(f"{display} (inactive — not authorized)")
        elif status in ("INITIALIZING", "PENDING"):
            initiated_list.append(f"{display} (connection being set up)")

    parts = []
    if active_list:
        parts.append(f"Active: {', '.join(active_list)}")
    if initiated_list:
        parts.append(f"Pending auth: {', '.join(initiated_list)}")
    if failed_list:
        parts.append(f"Needs re-auth: {', '.join(failed_list)}")

    return " | ".join(parts) if parts else "No external services are connected yet"


async def initiate_service_connection(service: str, force_reauth: bool = False) -> tuple[str, str]:
    """Initiate a new Composio connection for a service.

    Attempt 1: COMPOSIO_MANAGE_CONNECTIONS meta-tool (toolkits as array).
    Attempt 2: SDK direct — auth_configs.list() → connected_accounts.initiate(user_id, auth_config_id).
    Attempt 3: Direct httpx REST API — GET /api/v1/integrations → POST /api/v1/connectedAccounts.
               This path bypasses the SDK entirely and hits the Composio backend directly.

    Returns (auth_url, display_name) on success, or (error_message, "") on failure.
    """
    service_lower = service.lower().strip().replace(" ", "_")
    service_lower = _SERVICE_ALIASES.get(service_lower, service_lower)
    display_name = _COMPOSIO_VOICE_NAMES.get(service_lower, service.replace("_", " ").title())

    from ..config import get_settings
    settings = get_settings()
    if not settings.composio_api_key or not settings.composio_user_id:
        return "Service connections are not configured on this instance", ""

    client = _get_client(settings)
    user_id = settings.composio_user_id.strip()

    def _execute_meta_tool():
        # CRITICAL: COMPOSIO_MANAGE_CONNECTIONS requires "toolkits" (plural array).
        # Sending "toolkit" (singular string) causes: "Validation error: Required at 'toolkits'"
        return client.tools.execute(
            "COMPOSIO_MANAGE_CONNECTIONS",
            {
                "action": "initiate",
                "toolkits": [service_lower],
            },
            user_id=user_id,
            dangerously_skip_version_check=True,
        )

    def _execute_sdk_direct():
        """Direct SDK fallback: connected_accounts.initiate() via auth_config_id lookup.

        Correct high-level signature: initiate(user_id, auth_config_id, ...)
        Does NOT accept a 'toolkit' kwarg — must resolve auth_config_id first.
        SDK auth_configs.list() does not accept a 'toolkit' filter kwarg, so
        list all configs and filter client-side by appName/slug/name fields.
        """
        # List all auth configs, filter by toolkit slug client-side
        # (SDK does not accept 'toolkit' kwarg — list() takes no filter args)
        configs_response = client.auth_configs.list()
        all_configs = _extract_items_from_response(configs_response)
        # Filter to matching service by probing multiple field names
        configs = [
            c for c in all_configs
            if (
                getattr(c, "appName", "") or getattr(c, "app_name", "") or getattr(c, "slug", "") or ""
            ).lower().replace(" ", "_") == service_lower
            or (
                getattr(c, "name", "") or ""
            ).lower().replace(" ", "_") == service_lower
        ]
        if not configs:
            raise ValueError(
                f"No auth config found for {service_lower} in {len(all_configs)} total configs — "
                "service may not be available for this entity."
            )
        auth_config_id = (
            getattr(configs[0], "id", None)
            or getattr(configs[0], "auth_config_id", None)
        )
        if not auth_config_id:
            raise ValueError(f"Auth config for {service_lower} has no id field: {configs[0]}")
        logger.info(
            f"Composio: SDK fallback found auth_config_id={auth_config_id} for {service_lower} "
            f"(filtered from {len(all_configs)} configs)"
        )
        return client.connected_accounts.initiate(user_id, auth_config_id)

    def _extract_redirect_url_from_dict(data: dict) -> str | None:
        """Probe multiple key shapes — SDK redirect URL field name varies across versions.

        MANAGE_CONNECTIONS returns URLs nested under data.results.{service}.redirect_url
        (not at top-level or response_data.*), so we must scan results entries too.
        """
        if not isinstance(data, dict):
            return None
        response_data = data.get("response_data", {}) or {}
        # Flat probes (older SDK shapes)
        flat = (
            response_data.get("redirect_url")
            or response_data.get("redirectUrl")
            or response_data.get("connectionUrl")
            or response_data.get("authUrl")
            or data.get("redirect_url")
            or data.get("redirectUrl")
            or data.get("connectionUrl")
            or data.get("authUrl")
        )
        if flat:
            return flat
        # MANAGE_CONNECTIONS shape: data.results.{service_name}.redirect_url
        for svc_data in (data.get("results") or {}).values():
            if isinstance(svc_data, dict):
                url = svc_data.get("redirect_url") or svc_data.get("redirectUrl")
                if url:
                    return url
        return None

    # --- Attempt 1: COMPOSIO_MANAGE_CONNECTIONS meta-tool ---
    try:
        result = await asyncio.to_thread(_execute_meta_tool)
        if result.get("successful"):
            redirect_url = _extract_redirect_url_from_dict(result.get("data", {}))
            if redirect_url:
                logger.info(f"Composio: Connection initiated via meta-tool for {service_lower}")
                _initiated_connections[service_lower] = time.time()
                _service_auth_failed.pop(service_lower, None)  # clear circuit breaker on fresh link
                return redirect_url, display_name
            status = (result.get("data", {}).get("response_data", {}) or {}).get("status", "")
            if not force_reauth and status in ("ACTIVE", "CONNECTED"):
                return f"{display_name} is already connected and active", ""
            # Check for already-active summary shape using actual dict values, not string matching.
            # String matching fires on "active_connections=0" (key always present in summary dict).
            data = result.get("data", {}) or {}
            summary_dict = data.get("summary") or {}
            message_str = (data.get("message") or "").lower()
            if not force_reauth:
                active_count = summary_dict.get("active_connections", 0) if isinstance(summary_dict, dict) else 0
                initiated_count = summary_dict.get("initiated_connections", 0) if isinstance(summary_dict, dict) else 0
                if active_count > 0 and initiated_count == 0:
                    return f"{display_name} is already connected and active", ""
                if "all connections are active" in message_str:
                    return f"{display_name} is already connected and active", ""
        meta_error = result.get("error") or "No redirect URL returned"
        # Diagnostic: log full data so we can see the actual response shape
        logger.warning(
            f"Composio: meta-tool initiate failed for {service_lower}: {meta_error} — "
            f"data={result.get('data', {})} successful={result.get('successful')} — "
            f"falling back to direct SDK"
        )
    except Exception as meta_exc:
        logger.warning(
            f"Composio: meta-tool initiate exception for {service_lower}: {meta_exc} — falling back to direct SDK"
        )

    # --- Attempt 2: Direct SDK connected_accounts.initiate() ---
    try:
        sdk_result = await asyncio.to_thread(_execute_sdk_direct)
        # SDK returns an object; probe attributes for the redirect URL
        redirect_url = None
        for attr in ("redirect_url", "redirectUrl", "connectionUrl", "authUrl", "connection_url"):
            val = getattr(sdk_result, attr, None)
            if val:
                redirect_url = val
                break
        if not redirect_url and isinstance(sdk_result, dict):
            redirect_url = _extract_redirect_url_from_dict(sdk_result)
        if redirect_url:
            logger.info(f"Composio: Connection initiated via direct SDK for {service_lower}")
            _initiated_connections[service_lower] = time.time()
            return redirect_url, display_name
        logger.warning(
            f"Composio: direct SDK initiate returned no redirect URL for {service_lower}: {sdk_result}"
        )
    except Exception as exc:
        logger.warning(
            f"Composio: SDK initiate exception for {service_lower}: {exc} — trying REST API fallback"
        )

    # --- Attempt 3: Direct REST API via httpx (bypasses SDK and meta-tool entirely) ---
    # This path hits the Composio backend directly, independent of SDK version quirks.
    try:
        import httpx  # already in requirements.txt

        _rest_headers = {
            "x-api-key": settings.composio_api_key,
            "Content-Type": "application/json",
        }
        _base = "https://backend.composio.tech"

        async def _rest_initiate() -> str | None:
            async with httpx.AsyncClient(timeout=15.0) as http:
                # Step 1: resolve integration_id for this service
                # Try multiple appName formats — Composio app names may differ from lowercase service name
                integration_id: str | None = None
                _app_name_variants = [
                    service_lower,
                    service_lower.upper(),
                    service_lower.replace("_", ""),
                    service_lower.title(),
                ]
                for path in ("/api/v1/integrations", "/api/v2/integrations"):
                    if integration_id:
                        break
                    for app_name in _app_name_variants:
                        try:
                            r = await http.get(
                                f"{_base}{path}",
                                params={"appName": app_name, "page": 1, "pageSize": 10},
                                headers=_rest_headers,
                            )
                            if r.status_code == 200:
                                body = r.json()
                                items = body.get("items") or body.get("integrations") or []
                                for item in items:
                                    iid = item.get("id") or item.get("integrationId")
                                    if iid:
                                        integration_id = iid
                                        break
                            if integration_id:
                                logger.info(
                                    f"Composio REST: resolved integration_id={integration_id}"
                                    f" for {service_lower} (appName={app_name!r}) via {path}"
                                )
                                break
                            else:
                                logger.debug(
                                    f"Composio REST: {path} appName={app_name!r} status={r.status_code}"
                                    f" body_keys={list(r.json().keys()) if r.status_code == 200 else r.text[:120]}"
                                )
                        except Exception as _e:
                            logger.debug(f"Composio REST: {path} appName={app_name!r} exception: {_e}")

                if not integration_id:
                    logger.warning(f"Composio REST: no integration_id found for {service_lower}")
                    return None

                # Step 2: initiate connected account → redirect URL
                for path in ("/api/v1/connectedAccounts", "/api/v2/connectedAccounts"):
                    try:
                        r = await http.post(
                            f"{_base}{path}",
                            json={"integrationId": integration_id, "userUuid": user_id},
                            headers=_rest_headers,
                        )
                        if r.status_code in (200, 201):
                            body = r.json()
                            url = (
                                body.get("redirectUrl")
                                or body.get("redirect_url")
                                or body.get("connectionUrl")
                                or body.get("authUrl")
                                or body.get("oauthUrl")
                                or (body.get("connectedAccount") or {}).get("redirectUrl")
                            )
                            if url:
                                return url
                            logger.warning(
                                f"Composio REST: {path} 200 but no URL — keys={list(body.keys())}"
                            )
                        else:
                            logger.warning(
                                f"Composio REST: {path} returned {r.status_code}: {r.text[:200]}"
                            )
                    except Exception as _e:
                        logger.debug(f"Composio REST: {path} POST exception: {_e}")
                return None

        redirect_url = await _rest_initiate()
        if redirect_url:
            logger.info(f"Composio: Connection initiated via REST API for {service_lower}")
            _initiated_connections[service_lower] = time.time()
            return redirect_url, display_name

        logger.error(f"Composio: REST API initiation returned no URL for {service_lower}")
    except Exception as rest_exc:
        logger.error(f"Composio: REST API fallback exception for {service_lower}: {rest_exc}")

    return f"Connection setup for {display_name} is temporarily unavailable — all initiation paths failed. Please try again in a moment.", ""


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
    display_names = [_display_name(s) for s in slugs[:3]]
    batch_label = " + ".join(display_names) if len(slugs) <= 3 else f"{display_names[0]} + {len(slugs) - 1} more"
    batch_call_id = await publish_tool_start(
        batch_label,
        {"count": str(len(slugs))},
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
