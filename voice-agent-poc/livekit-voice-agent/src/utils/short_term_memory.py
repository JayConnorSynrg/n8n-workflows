"""Session-Based Short-Term Memory for Voice Agent Tool Results.

This module provides a centralized memory system that:
1. Stores results from ALL tool calls for the duration of the session
2. Enables cross-tool context (use email search results for vector store, etc.)
3. Allows the agent to recall and repurpose data without re-querying
4. Automatically clears when the session ends

Memory is SESSION-SCOPED, not time-based:
- Data persists for the entire conversation
- Cleared only when clear_session() is called (on disconnect)
- No arbitrary TTL expiration
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


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
    "google_drive_search": ToolCategory.DRIVE,
    "google_drive_get": ToolCategory.DRIVE,
    "google_drive_list": ToolCategory.DRIVE,
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


class SessionMemory:
    """Thread-safe session-scoped memory storage.

    Memory persists for the entire session and is only cleared
    when clear() is explicitly called (typically on session end).
    """

    def __init__(self):
        self._lock = Lock()
        # session_id -> category -> MemoryEntry
        self._sessions: Dict[str, Dict[ToolCategory, MemoryEntry]] = {}
        # session_id -> list of all entries (chronological)
        self._history: Dict[str, List[MemoryEntry]] = {}

    def store(
        self,
        session_id: str,
        entry: MemoryEntry,
    ) -> None:
        """Store an entry in session memory."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = {}
                self._history[session_id] = []

            # Store by category (most recent wins per category)
            self._sessions[session_id][entry.category] = entry

            # Also keep chronological history
            self._history[session_id].append(entry)

            logger.debug(f"Stored {entry.tool_name}.{entry.operation} to session {session_id}")

    def get_by_category(
        self,
        session_id: str,
        category: ToolCategory,
    ) -> Optional[MemoryEntry]:
        """Get the most recent entry for a category."""
        with self._lock:
            session_data = self._sessions.get(session_id, {})
            return session_data.get(category)

    def get_all_categories(
        self,
        session_id: str,
    ) -> Dict[ToolCategory, MemoryEntry]:
        """Get all category entries for a session."""
        with self._lock:
            return dict(self._sessions.get(session_id, {}))

    def get_history(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[MemoryEntry]:
        """Get chronological history for a session."""
        with self._lock:
            history = self._history.get(session_id, [])
            if limit:
                return history[-limit:]
            return list(history)

    def get_most_recent(
        self,
        session_id: str,
    ) -> Optional[MemoryEntry]:
        """Get the single most recent entry."""
        with self._lock:
            history = self._history.get(session_id, [])
            return history[-1] if history else None

    def clear(self, session_id: str) -> int:
        """Clear all memory for a session. Returns count of entries cleared."""
        with self._lock:
            count = 0
            if session_id in self._sessions:
                count = len(self._history.get(session_id, []))
                del self._sessions[session_id]
            if session_id in self._history:
                del self._history[session_id]
            logger.info(f"Cleared {count} memory entries for session {session_id}")
            return count

    def get_stats(self, session_id: str) -> Dict[str, Any]:
        """Get memory statistics for a session."""
        with self._lock:
            history = self._history.get(session_id, [])
            categories = self._sessions.get(session_id, {})
            return {
                "total_entries": len(history),
                "categories_active": len(categories),
                "categories": list(categories.keys()),
            }


# Global session memory instance
_session_memory = SessionMemory()


def _get_category(tool_name: str) -> ToolCategory:
    """Get the category for a tool by name."""
    # Check exact match first
    if tool_name.lower() in TOOL_CATEGORIES:
        return TOOL_CATEGORIES[tool_name.lower()]

    # Check partial matches
    tool_lower = tool_name.lower()
    for key, category in TOOL_CATEGORIES.items():
        if key in tool_lower or tool_lower in key:
            return category

    return ToolCategory.GENERAL


def store_tool_result(
    tool_name: str,
    operation: str,
    data: Any,
    summary: str,
    session_id: str = "livekit-agent",
    suggested_uses: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Store a tool result in session memory.

    Args:
        tool_name: Name of the tool that produced the result
        operation: Specific operation performed (e.g., "search", "get", "list")
        data: The actual result data to store
        summary: Human-readable summary for voice output
        session_id: Session identifier
        suggested_uses: List of suggested follow-up uses
        metadata: Additional metadata about the result
    """
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

    _session_memory.store(session_id, entry)
    logger.info(f"Stored {tool_name}.{operation} to session memory: {summary[:50]}...")


def recall_by_category(
    category: Union[ToolCategory, str],
    session_id: str = "livekit-agent",
) -> Optional[Dict[str, Any]]:
    """Recall the most recent result for a category.

    Args:
        category: Tool category (ToolCategory enum or string)
        session_id: Session identifier

    Returns:
        Most recent memory entry for category as dict, or None
    """
    if isinstance(category, str):
        try:
            category = ToolCategory(category.lower())
        except ValueError:
            category = ToolCategory.GENERAL

    entry = _session_memory.get_by_category(session_id, category)
    return entry.to_dict() if entry else None


def recall_by_tool(
    tool_name: str,
    operation: Optional[str] = None,
    session_id: str = "livekit-agent",
) -> Optional[Dict[str, Any]]:
    """Recall the most recent result for a specific tool.

    Args:
        tool_name: Name of the tool
        operation: Specific operation (optional, for filtering)
        session_id: Session identifier

    Returns:
        Memory entry as dict or None
    """
    category = _get_category(tool_name)
    entry = _session_memory.get_by_category(session_id, category)

    if entry and operation:
        # Check if operation matches
        if entry.operation != operation:
            # Search history for matching operation
            history = _session_memory.get_history(session_id)
            for e in reversed(history):
                if e.category == category and e.operation == operation:
                    return e.to_dict()
            return None

    return entry.to_dict() if entry else None


def recall_all(
    session_id: str = "livekit-agent",
) -> Dict[str, Dict[str, Any]]:
    """Recall all short-term memory entries for a session.

    Args:
        session_id: Session identifier

    Returns:
        Dict mapping category names to their most recent entries
    """
    all_entries = _session_memory.get_all_categories(session_id)
    return {cat.value: entry.to_dict() for cat, entry in all_entries.items()}


def recall_most_recent(
    session_id: str = "livekit-agent",
) -> Optional[Dict[str, Any]]:
    """Recall the single most recent memory entry.

    Args:
        session_id: Session identifier

    Returns:
        Most recent entry as dict, or None
    """
    entry = _session_memory.get_most_recent(session_id)
    return entry.to_dict() if entry else None


def recall_history(
    session_id: str = "livekit-agent",
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Recall chronological history of all tool results.

    Args:
        session_id: Session identifier
        limit: Optional limit on number of entries

    Returns:
        List of entries in chronological order
    """
    entries = _session_memory.get_history(session_id, limit)
    return [e.to_dict() for e in entries]


def get_memory_summary(
    session_id: str = "livekit-agent",
) -> str:
    """Get a voice-friendly summary of all session memory.

    Args:
        session_id: Session identifier

    Returns:
        Summary string for voice output
    """
    all_entries = _session_memory.get_all_categories(session_id)

    if not all_entries:
        return "No data in session memory"

    summaries = []
    for category, entry in all_entries.items():
        summary = entry.summary
        age = entry.age_seconds
        age_str = f"{int(age)}s ago" if age < 60 else f"{int(age/60)}m ago"
        summaries.append(f"{category.value}: {summary} ({age_str})")

    return "In memory: " + "; ".join(summaries)


def suggest_uses_for_category(category: Union[ToolCategory, str]) -> List[str]:
    """Get suggested uses for data in a category."""
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


def clear_session(session_id: str = "livekit-agent") -> int:
    """Clear all memory for a session. Call this when session ends.

    Args:
        session_id: Session identifier

    Returns:
        Number of entries cleared
    """
    return _session_memory.clear(session_id)


def get_session_stats(session_id: str = "livekit-agent") -> Dict[str, Any]:
    """Get memory statistics for a session."""
    return _session_memory.get_stats(session_id)
