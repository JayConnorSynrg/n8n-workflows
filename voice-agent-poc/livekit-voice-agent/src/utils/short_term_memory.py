"""Universal Short-Term Memory for Voice Agent Tool Results.

This module provides a centralized short-term memory system that:
1. Stores results from ALL tool calls (not just Drive)
2. Enables cross-tool context (use email search results for vector store, etc.)
3. Allows the agent to recall and repurpose data without re-querying
4. Provides summaries for voice-friendly responses

Memory Structure:
- Tool results stored by category (drive, email, database, vector)
- Automatic TTL management (default 5 minutes)
- Most recent result per category readily accessible
- Search across all memory for relevant context
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TypeVar, Union
from enum import Enum

from .context_cache import get_cache_manager

logger = logging.getLogger(__name__)

# Short-term memory TTL (5 minutes for conversation reuse)
DEFAULT_STM_TTL = 300.0


class ToolCategory(str, Enum):
    """Categories of tools for memory organization."""
    DRIVE = "drive"           # Google Drive operations
    EMAIL = "email"           # Email send/search
    DATABASE = "database"     # PostgreSQL queries
    VECTOR = "vector"         # Vector store operations
    CONTEXT = "context"       # Session context queries
    GENERAL = "general"       # Uncategorized tool results


@dataclass
class MemoryEntry:
    """A single entry in short-term memory."""
    tool_name: str
    category: ToolCategory
    operation: str
    data: Any
    summary: str
    timestamp: float = field(default_factory=time.time)
    suggested_uses: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "category": self.category.value,
            "operation": self.operation,
            "data": self.data,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "suggested_uses": self.suggested_uses,
            "metadata": self.metadata,
        }


# Tool name to category mapping
TOOL_CATEGORIES = {
    # Drive tools
    "search_documents": ToolCategory.DRIVE,
    "get_document": ToolCategory.DRIVE,
    "list_drive_files": ToolCategory.DRIVE,
    "recall_drive_data": ToolCategory.DRIVE,
    "google_drive_tool": ToolCategory.DRIVE,
    "drive_file_retrieval": ToolCategory.DRIVE,
    "drive_file_listing": ToolCategory.DRIVE,

    # Email tools
    "send_email": ToolCategory.EMAIL,
    "email_tool": ToolCategory.EMAIL,

    # Database tools
    "database_query_tool": ToolCategory.DATABASE,
    "query_database": ToolCategory.DATABASE,

    # Vector store tools
    "vector_database_tool": ToolCategory.VECTOR,
    "vector_store_async": ToolCategory.VECTOR,
    "store_knowledge": ToolCategory.VECTOR,

    # Context tools
    "session_history_tool": ToolCategory.CONTEXT,
    "query_context": ToolCategory.CONTEXT,
    "get_session_summary": ToolCategory.CONTEXT,
}


def _get_category(tool_name: str) -> ToolCategory:
    """Get the category for a tool by name."""
    return TOOL_CATEGORIES.get(tool_name.lower(), ToolCategory.GENERAL)


def _make_memory_key(
    session_id: str,
    category: ToolCategory,
    operation: Optional[str] = None
) -> str:
    """Generate a cache key for short-term memory."""
    parts = ["stm", session_id, category.value]
    if operation:
        parts.append(operation)
    return ":".join(parts)


def store_tool_result(
    tool_name: str,
    operation: str,
    data: Any,
    summary: str,
    session_id: str = "livekit-agent",
    suggested_uses: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ttl: float = DEFAULT_STM_TTL,
) -> None:
    """Store a tool result in short-term memory.

    Args:
        tool_name: Name of the tool that produced the result
        operation: Specific operation performed (e.g., "search", "get", "list")
        data: The actual result data to store
        summary: Human-readable summary for voice output
        session_id: Session identifier
        suggested_uses: List of suggested follow-up uses (e.g., ["email", "vector_store"])
        metadata: Additional metadata about the result
        ttl: Time-to-live in seconds (default 5 minutes)
    """
    cache_manager = get_cache_manager()
    category = _get_category(tool_name)

    entry = MemoryEntry(
        tool_name=tool_name,
        category=category,
        operation=operation,
        data=data,
        summary=summary,
        suggested_uses=suggested_uses or [],
        metadata=metadata or {},
    )

    # Store by category (most recent wins)
    category_key = _make_memory_key(session_id, category)
    cache_manager.query_cache.set(category_key, entry.to_dict(), ttl)

    # Also store by specific operation for targeted recall
    operation_key = _make_memory_key(session_id, category, operation)
    cache_manager.query_cache.set(operation_key, entry.to_dict(), ttl)

    logger.info(f"Stored {tool_name}.{operation} to STM: {summary[:50]}...")


def recall_by_category(
    category: Union[ToolCategory, str],
    session_id: str = "livekit-agent",
) -> Optional[Dict[str, Any]]:
    """Recall the most recent result for a category.

    Args:
        category: Tool category (ToolCategory enum or string)
        session_id: Session identifier

    Returns:
        Most recent memory entry for category, or None
    """
    cache_manager = get_cache_manager()

    if isinstance(category, str):
        try:
            category = ToolCategory(category.lower())
        except ValueError:
            category = ToolCategory.GENERAL

    key = _make_memory_key(session_id, category)
    return cache_manager.query_cache.get(key)


def recall_by_tool(
    tool_name: str,
    operation: Optional[str] = None,
    session_id: str = "livekit-agent",
) -> Optional[Dict[str, Any]]:
    """Recall the most recent result for a specific tool.

    Args:
        tool_name: Name of the tool
        operation: Specific operation (optional)
        session_id: Session identifier

    Returns:
        Memory entry or None
    """
    cache_manager = get_cache_manager()
    category = _get_category(tool_name)

    if operation:
        key = _make_memory_key(session_id, category, operation)
        result = cache_manager.query_cache.get(key)
        if result:
            return result

    # Fall back to category-level recall
    key = _make_memory_key(session_id, category)
    return cache_manager.query_cache.get(key)


def recall_all(
    session_id: str = "livekit-agent",
) -> Dict[str, Dict[str, Any]]:
    """Recall all short-term memory entries for a session.

    Args:
        session_id: Session identifier

    Returns:
        Dict mapping category names to their most recent entries
    """
    results = {}
    for category in ToolCategory:
        entry = recall_by_category(category, session_id)
        if entry:
            results[category.value] = entry
    return results


def recall_most_recent(
    session_id: str = "livekit-agent",
) -> Optional[Dict[str, Any]]:
    """Recall the single most recent memory entry.

    Args:
        session_id: Session identifier

    Returns:
        Most recent entry across all categories, or None
    """
    all_entries = recall_all(session_id)
    if not all_entries:
        return None

    # Find the most recent by timestamp
    most_recent = None
    most_recent_time = 0

    for entry in all_entries.values():
        entry_time = entry.get("timestamp", 0)
        if entry_time > most_recent_time:
            most_recent_time = entry_time
            most_recent = entry

    return most_recent


def get_memory_summary(
    session_id: str = "livekit-agent",
) -> str:
    """Get a voice-friendly summary of all short-term memory.

    Args:
        session_id: Session identifier

    Returns:
        Summary string for voice output
    """
    all_entries = recall_all(session_id)

    if not all_entries:
        return "No recent data in short-term memory"

    summaries = []
    for category, entry in all_entries.items():
        summary = entry.get("summary", f"{category} data")
        age = time.time() - entry.get("timestamp", time.time())
        age_str = f"{int(age)}s ago" if age < 60 else f"{int(age/60)}m ago"
        summaries.append(f"{category}: {summary} ({age_str})")

    return "In memory: " + "; ".join(summaries)


def suggest_uses_for_category(category: Union[ToolCategory, str]) -> List[str]:
    """Get suggested uses for data in a category.

    Args:
        category: Tool category

    Returns:
        List of suggested follow-up actions
    """
    if isinstance(category, str):
        try:
            category = ToolCategory(category.lower())
        except ValueError:
            return ["reference"]

    suggestions = {
        ToolCategory.DRIVE: ["email_summary", "vector_store", "reference", "analysis"],
        ToolCategory.EMAIL: ["reference", "follow_up"],
        ToolCategory.DATABASE: ["email_report", "vector_store", "analysis"],
        ToolCategory.VECTOR: ["reference", "further_search"],
        ToolCategory.CONTEXT: ["reference"],
        ToolCategory.GENERAL: ["reference"],
    }

    return suggestions.get(category, ["reference"])


def clear_category(
    category: Union[ToolCategory, str],
    session_id: str = "livekit-agent",
) -> bool:
    """Clear short-term memory for a specific category.

    Args:
        category: Tool category to clear
        session_id: Session identifier

    Returns:
        True if something was cleared
    """
    cache_manager = get_cache_manager()

    if isinstance(category, str):
        try:
            category = ToolCategory(category.lower())
        except ValueError:
            return False

    key = _make_memory_key(session_id, category)
    return cache_manager.query_cache.invalidate(key)


def clear_all(session_id: str = "livekit-agent") -> int:
    """Clear all short-term memory for a session.

    Args:
        session_id: Session identifier

    Returns:
        Number of categories cleared
    """
    cleared = 0
    for category in ToolCategory:
        if clear_category(category, session_id):
            cleared += 1
    return cleared
