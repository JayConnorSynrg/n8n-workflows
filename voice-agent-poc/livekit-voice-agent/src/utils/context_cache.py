"""In-memory context cache with TTL and LRU eviction.

This cache sits between the agent and n8n webhooks to:
1. Reduce database load by caching frequently accessed context
2. Provide instant access to recently retrieved data
3. Maintain maximum context without memory pressure

Cache Strategy:
- Session context: 5-minute TTL, refreshed on access
- Tool history: 2-minute TTL (more volatile)
- Global context: 10-minute TTL (stable data)
- Query results: 1-minute TTL (fresh data preference)

Memory Management:
- Max 1000 entries per cache type
- LRU eviction when limit reached
- Automatic cleanup of expired entries every 60 seconds
"""
import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, TypeVar, Generic
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Single cache entry with value, TTL, and access tracking."""
    value: T
    created_at: float
    last_accessed: float
    ttl_seconds: float
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() > (self.created_at + self.ttl_seconds)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def touch(self) -> None:
        """Update last access time and increment counter."""
        self.last_accessed = time.time()
        self.access_count += 1


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with TTL support.

    Features:
    - O(1) get/set operations
    - Automatic TTL expiration
    - LRU eviction when max size reached
    - Access count tracking for analytics
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,  # 5 minutes
        name: str = "cache"
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.name = name
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[T]:
        """Get value from cache, returning None if missing or expired."""
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            self._cache.pop(key, None)
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.touch()
        self._hits += 1

        return entry.value

    def set(
        self,
        key: str,
        value: T,
        ttl: Optional[float] = None
    ) -> None:
        """Set value in cache with optional custom TTL."""
        now = time.time()
        ttl = ttl if ttl is not None else self.default_ttl

        # Remove if exists (to update position)
        if key in self._cache:
            self._cache.pop(key)

        # Evict oldest if at capacity
        while len(self._cache) >= self.max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            self._evictions += 1
            logger.debug(f"[{self.name}] Evicted: {evicted_key}")

        self._cache[key] = CacheEntry(
            value=value,
            created_at=now,
            last_accessed=now,
            ttl_seconds=ttl
        )

    def invalidate(self, key: str) -> bool:
        """Remove specific key from cache."""
        if key in self._cache:
            self._cache.pop(key)
            return True
        return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all keys starting with prefix."""
        keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
        for key in keys_to_remove:
            self._cache.pop(key)
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all entries."""
        self._cache.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired
        ]
        for key in expired_keys:
            self._cache.pop(key)
        return len(expired_keys)

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "name": self.name,
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "evictions": self._evictions,
        }


class ContextCacheManager:
    """Centralized context cache manager for the voice agent.

    Manages multiple specialized caches:
    - session_cache: Session-specific context (5-min TTL)
    - tool_cache: Tool call history (2-min TTL)
    - global_cache: Cross-session context (10-min TTL)
    - query_cache: Query results (1-min TTL)
    """

    def __init__(self):
        # Session context cache - longer TTL, frequently accessed
        self.session_cache = LRUCache[Dict[str, Any]](
            max_size=500,
            default_ttl=300.0,  # 5 minutes
            name="session_context"
        )

        # Tool history cache - shorter TTL, more volatile
        self.tool_cache = LRUCache[list](
            max_size=200,
            default_ttl=120.0,  # 2 minutes
            name="tool_history"
        )

        # Global context cache - longer TTL, stable data
        self.global_cache = LRUCache[Dict[str, Any]](
            max_size=100,
            default_ttl=600.0,  # 10 minutes
            name="global_context"
        )

        # Query result cache - short TTL, fresh data preferred
        self.query_cache = LRUCache[Any](
            max_size=500,
            default_ttl=60.0,  # 1 minute
            name="query_results"
        )

        # Cleanup task reference
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start background cleanup task."""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Context cache manager started")

    async def stop(self) -> None:
        """Stop background cleanup task."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Context cache manager stopped")

    async def _cleanup_loop(self) -> None:
        """Background task to cleanup expired entries every 60 seconds."""
        while self._running:
            try:
                await asyncio.sleep(60)

                # Cleanup all caches
                session_cleaned = self.session_cache.cleanup_expired()
                tool_cleaned = self.tool_cache.cleanup_expired()
                global_cleaned = self.global_cache.cleanup_expired()
                query_cleaned = self.query_cache.cleanup_expired()

                total_cleaned = session_cleaned + tool_cleaned + global_cleaned + query_cleaned

                if total_cleaned > 0:
                    logger.debug(
                        f"Cache cleanup: {total_cleaned} expired entries removed "
                        f"(session={session_cleaned}, tool={tool_cleaned}, "
                        f"global={global_cleaned}, query={query_cleaned})"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    # -------------------------------------------------------------------------
    # Session Context Methods
    # -------------------------------------------------------------------------

    def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached session context."""
        return self.session_cache.get(f"session:{session_id}")

    def set_session_context(
        self,
        session_id: str,
        context: Dict[str, Any],
        ttl: Optional[float] = None
    ) -> None:
        """Cache session context."""
        self.session_cache.set(f"session:{session_id}", context, ttl)

    def invalidate_session(self, session_id: str) -> None:
        """Invalidate all caches for a session."""
        self.session_cache.invalidate(f"session:{session_id}")
        self.tool_cache.invalidate_prefix(f"tools:{session_id}:")
        self.query_cache.invalidate_prefix(f"query:{session_id}:")

    # -------------------------------------------------------------------------
    # Tool History Methods
    # -------------------------------------------------------------------------

    def get_tool_history(
        self,
        session_id: Optional[str] = None,
        function_name: Optional[str] = None
    ) -> Optional[list]:
        """Get cached tool history."""
        key_parts = ["tools"]
        if session_id:
            key_parts.append(session_id)
        if function_name:
            key_parts.append(function_name)
        key = ":".join(key_parts)
        return self.tool_cache.get(key)

    def set_tool_history(
        self,
        history: list,
        session_id: Optional[str] = None,
        function_name: Optional[str] = None,
        ttl: Optional[float] = None
    ) -> None:
        """Cache tool history."""
        key_parts = ["tools"]
        if session_id:
            key_parts.append(session_id)
        if function_name:
            key_parts.append(function_name)
        key = ":".join(key_parts)
        self.tool_cache.set(key, history, ttl)

    def append_tool_call(self, session_id: str, tool_call: Dict[str, Any]) -> None:
        """Append a tool call to cached history (if exists)."""
        key = f"tools:{session_id}"
        existing = self.tool_cache.get(key)
        if existing is not None:
            existing.append(tool_call)
            self.tool_cache.set(key, existing)

    # -------------------------------------------------------------------------
    # Global Context Methods
    # -------------------------------------------------------------------------

    def get_global_context(self, key: str = "default") -> Optional[Dict[str, Any]]:
        """Get cached global context."""
        return self.global_cache.get(f"global:{key}")

    def set_global_context(
        self,
        context: Dict[str, Any],
        key: str = "default",
        ttl: Optional[float] = None
    ) -> None:
        """Cache global context."""
        self.global_cache.set(f"global:{key}", context, ttl)

    # -------------------------------------------------------------------------
    # Query Result Methods (generic)
    # -------------------------------------------------------------------------

    def get_query_result(self, query_key: str) -> Optional[Any]:
        """Get cached query result."""
        return self.query_cache.get(f"query:{query_key}")

    def set_query_result(
        self,
        query_key: str,
        result: Any,
        ttl: Optional[float] = None
    ) -> None:
        """Cache query result."""
        self.query_cache.set(f"query:{query_key}", result, ttl)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all caches."""
        return {
            "session": self.session_cache.stats,
            "tool": self.tool_cache.stats,
            "global": self.global_cache.stats,
            "query": self.query_cache.stats,
        }

    def log_stats(self) -> None:
        """Log cache statistics."""
        stats = self.get_all_stats()
        logger.info(f"Cache stats: {stats}")


# Global singleton instance
_cache_manager: Optional[ContextCacheManager] = None


def get_cache_manager() -> ContextCacheManager:
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = ContextCacheManager()
    return _cache_manager


# Convenience functions for common operations
def cache_session_context(session_id: str, context: Dict[str, Any]) -> None:
    """Convenience function to cache session context."""
    get_cache_manager().set_session_context(session_id, context)


def get_cached_session_context(session_id: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get cached session context."""
    return get_cache_manager().get_session_context(session_id)
