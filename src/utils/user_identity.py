"""User identity resolution for per-user memory partitioning.

Resolves a stable, filesystem-safe user ID from LiveKit room context.
Used to route memory operations (SQLite, markdown files) to per-user directories.

Resolution order:
  1. room.metadata JSON  → user_name / user_id / name fields
  2. First human participant metadata JSON → same fields
  3. First human participant identity (LiveKit participant ID)
  4. Room name heuristics ("user-jay-abc123" → "jay")
  5. Default: "_default"
"""
import json
import logging
import os
import re
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Characters allowed in user directory names (lowercase a-z, 0-9, underscore, hyphen)
_SAFE_CHARS = re.compile(r'[^a-z0-9_-]')

# Participant identities that indicate the agent, not a human user
_AGENT_KEYWORDS = frozenset({'agent', 'livekit', 'aio', 'voice-agent', 'bot', 'assistant'})


def sanitize_user_id(name: str) -> str:
    """Normalize a user name to a safe, lowercase filesystem directory component.

    Examples:
      "Jay Connor"  → "jay_connor"
      "Jay"         → "jay"
      "jay@synrg"   → "jay_synrg"
      "Kevin Smith" → "kevin_smith"
      ""            → "_default"
    """
    if not name or not name.strip():
        return "_default"
    normalized = name.lower().strip()
    # Replace common separators (spaces, @, ., +) with underscore
    normalized = re.sub(r'[@.\s+]+', '_', normalized)
    # Remove any remaining unsafe characters
    normalized = _SAFE_CHARS.sub('', normalized)
    # Collapse multiple underscores and strip leading/trailing
    normalized = re.sub(r'_+', '_', normalized).strip('_')
    return normalized or "_default"


def _extract_from_metadata_str(metadata_str: str) -> Optional[str]:
    """Parse a JSON metadata string and return the first recognized name/id field."""
    if not metadata_str:
        return None
    try:
        data = json.loads(metadata_str)
        if not isinstance(data, dict):
            return None
        for key in ('user_name', 'userName', 'user_id', 'userId', 'name',
                    'participant_name', 'displayName', 'identity'):
            val = data.get(key)
            if val and isinstance(val, str) and len(val.strip()) > 1:
                return val.strip()
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    return None


def _extract_from_room_name(room_name: str) -> Optional[str]:
    """Extract user identity from common LiveKit room name patterns.

    Recognized patterns:
      "user-jay-abc123"         → "jay"
      "jay-abcdef1234567890"    → "jay"   (UUID-like suffix)
    """
    if not room_name:
        return None
    # Pattern: "user-{name}-{any_suffix}"
    m = re.match(r'^user[-_]([a-zA-Z][a-zA-Z0-9_-]{0,30})[-_]', room_name, re.IGNORECASE)
    if m:
        return m.group(1)
    # Pattern: "{name}-{uuid}" where uuid is hex+dashes, ≥8 chars
    m = re.match(r'^([a-zA-Z]{2,20})[-_][0-9a-fA-F-]{8,}$', room_name)
    if m:
        return m.group(1)
    return None


def _is_agent_participant(participant: Any) -> bool:
    """Return True if this participant appears to be the agent (not a human)."""
    identity = (getattr(participant, 'identity', '') or '').lower()
    name = (getattr(participant, 'name', '') or '').lower()
    return any(kw in identity or kw in name for kw in _AGENT_KEYWORDS)


def resolve_user_id(
    room_name: str = "",
    room_metadata_str: Optional[str] = None,
    participants: Optional[List[Any]] = None,
) -> str:
    """Resolve a stable, sanitized user ID from available LiveKit room context.

    Args:
        room_name: ctx.room.name
        room_metadata_str: ctx.room.metadata (raw JSON string or None)
        participants: list of remote participants (ctx.room.remote_participants.values())

    Returns:
        A sanitized, filesystem-safe user ID string (lowercase, underscores).
        Falls back to "_default" if no user can be identified.
    """
    # 1. Room-level metadata
    if room_metadata_str:
        uid = _extract_from_metadata_str(room_metadata_str)
        if uid:
            result = sanitize_user_id(uid)
            logger.info("[UserIdentity] Resolved from room metadata: %r → %r", uid, result)
            return result

    # 2. Participant metadata / identity
    if participants:
        for participant in participants:
            if _is_agent_participant(participant):
                continue
            # Try participant metadata JSON
            meta = getattr(participant, 'metadata', None)
            if meta:
                uid = _extract_from_metadata_str(meta)
                if uid:
                    result = sanitize_user_id(uid)
                    logger.info("[UserIdentity] Resolved from participant metadata: %r → %r", uid, result)
                    return result
            # Try participant identity (their LiveKit join ID)
            identity = getattr(participant, 'identity', None)
            if identity and identity.lower() not in ('', 'guest', 'anonymous'):
                result = sanitize_user_id(identity)
                logger.info("[UserIdentity] Resolved from participant identity: %r → %r", identity, result)
                return result
            # Try participant display name
            p_name = getattr(participant, 'name', None)
            if p_name and p_name.lower() not in ('', 'guest', 'anonymous'):
                result = sanitize_user_id(p_name)
                logger.info("[UserIdentity] Resolved from participant name: %r → %r", p_name, result)
                return result

    # 3. Room name heuristics
    if room_name:
        uid = _extract_from_room_name(room_name)
        if uid:
            result = sanitize_user_id(uid)
            logger.info("[UserIdentity] Resolved from room name %r → %r", room_name, result)
            return result

    logger.info("[UserIdentity] Could not resolve user identity, defaulting to _default")
    return "_default"


def get_user_mem_dir(base_mem_dir: str, user_id: str) -> str:
    """Return (and create) the per-user memory directory path.

    Creates the structure:
        {base_mem_dir}/users/{user_id}/
            SOUL.md          (created by session_writer.ensure_memory_files)
            USER.md          (created by session_writer.ensure_memory_files)
            MEMORY.md        (created by session_writer.ensure_memory_files)
            sessions/        (created by session_writer.ensure_memory_files)
                2026-02-23.md
            aio-voice-memory.sqlite  (created by memory_store.init)

    Args:
        base_mem_dir: Base memory directory (e.g., /app/data/memory)
        user_id: Sanitized user identifier from resolve_user_id()

    Returns:
        Absolute path to the user's memory directory.
    """
    user_dir = os.path.join(base_mem_dir, "users", user_id)
    try:
        os.makedirs(user_dir, exist_ok=True)
    except OSError as e:
        logger.warning("[UserIdentity] Failed to create user dir %r: %s", user_dir, e)
    return user_dir
