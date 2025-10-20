"""
Security Caching Module

This module contains concrete implementations of cache management for security operations.
It depends only on the security.api layer, following the level contract principle.

Key Features:
- Advanced LRU caching with TTL support
- Tag-based cache invalidation
- Performance metrics and monitoring
- Thread-safe operations
"""

from __future__ import annotations

import logging
import time
import weakref
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from .api import ICacheManager

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata."""
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    ttl: float | None = None
    tags: set[str] = field(default_factory=set)
    access_count: int = 0

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """Update the last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


class AdvancedCache:
    """
    Advanced cache implementation with LRU eviction, TTL support, and tag-based invalidation.

    This cache provides:
    - LRU (Least Recently Used) eviction policy
    - TTL (Time To Live) support for automatic expiration
    - Tag-based invalidation for efficient cache management
    - Thread-safe operations
    - Performance metrics
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: float = 300.0,  # 5 minutes
        cleanup_interval: int = 100  # Cleanup every 100 operations
    ):
        """
        Initialize the advanced cache.

        Args:
            max_size: Maximum number of entries to cache
            default_ttl: Default TTL in seconds (None for no expiration)
            cleanup_interval: Number of operations between cleanup runs
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval

        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tags_to_keys: dict[str, set[str]] = {}
        self._lock = RLock()

        # Performance tracking
        self._operation_count = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Any | None:
        """
        Retrieve a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        with self._lock:
            self._operation_count += 1
            self._maybe_cleanup()

            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                self._remove_entry(key, entry)
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1

            logger.debug(f"Cache hit for key: {key}")
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        tags: set[str] | None = None
    ) -> bool:
        """
        Store a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            tags: Tags for invalidation (optional)

        Returns:
            True if successfully cached
        """
        with self._lock:
            try:
                # Use default TTL if not specified
                effective_ttl = ttl if ttl is not None else self.default_ttl
                effective_tags = tags or set()

                # Remove existing entry if present
                if key in self._cache:
                    old_entry = self._cache[key]
                    self._remove_entry(key, old_entry)

                # Create new entry
                entry = CacheEntry(
                    value=value,
                    ttl=effective_ttl,
                    tags=effective_tags
                )

                # Add to cache
                self._cache[key] = entry

                # Update tag mappings
                for tag in effective_tags:
                    if tag not in self._tags_to_keys:
                        self._tags_to_keys[tag] = set()
                    self._tags_to_keys[tag].add(key)

                # Evict if necessary
                if len(self._cache) > self.max_size:
                    self._evict_lru()

                logger.debug(f"Cached value for key: {key} with TTL: {effective_ttl}")
                return True

            except Exception as e:
                logger.error(f"Error caching value for key {key}: {e}")
                return False

    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.

        Args:
            key: Cache key

        Returns:
            True if successfully deleted
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False

            self._remove_entry(key, entry)
            logger.debug(f"Deleted cache entry for key: {key}")
            return True

    def invalidate_by_tags(self, tags: set[str]) -> int:
        """
        Invalidate cache entries by tags.

        Args:
            tags: Tags to invalidate

        Returns:
            Number of entries invalidated
        """
        with self._lock:
            keys_to_remove = set()

            for tag in tags:
                if tag in self._tags_to_keys:
                    keys_to_remove.update(self._tags_to_keys[tag])

            count = 0
            for key in keys_to_remove:
                if key in self._cache:
                    entry = self._cache[key]
                    self._remove_entry(key, entry)
                    count += 1

            logger.debug(f"Invalidated {count} cache entries for tags: {tags}")
            return count

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._tags_to_keys.clear()
            logger.debug("Cleared all cache entries")

    def size(self) -> int:
        """Get the current number of cache entries."""
        return len(self._cache)

    def get_metrics(self) -> dict[str, Any]:
        """
        Get cache performance metrics.

        Returns:
            Dictionary containing cache metrics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0.0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "evictions": self._evictions,
                "operation_count": self._operation_count,
                "tag_count": len(self._tags_to_keys)
            }

    def _maybe_cleanup(self) -> None:
        """Perform cleanup if needed."""
        if self._operation_count % self.cleanup_interval == 0:
            self._cleanup_expired()

    def _cleanup_expired(self) -> None:
        """Remove expired entries from the cache."""
        expired_keys = []

        for key, entry in self._cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            entry = self._cache[key]
            self._remove_entry(key, entry)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if self._cache:
            # Remove from beginning (least recently used)
            key, entry = self._cache.popitem(last=False)
            self._remove_entry_tags(key, entry)
            self._evictions += 1
            logger.debug(f"Evicted LRU cache entry: {key}")

    def _remove_entry(self, key: str, entry: CacheEntry) -> None:
        """Remove an entry and its tag mappings."""
        self._cache.pop(key, None)
        self._remove_entry_tags(key, entry)

    def _remove_entry_tags(self, key: str, entry: CacheEntry) -> None:
        """Remove tag mappings for an entry."""
        for tag in entry.tags:
            if tag in self._tags_to_keys:
                self._tags_to_keys[tag].discard(key)
                if not self._tags_to_keys[tag]:
                    del self._tags_to_keys[tag]


class SecurityCacheManager:
    """
    Manages multiple specialized caches for different security operations.

    This manager provides:
    - Separate caches for different security domains
    - Unified metrics and management
    - Coordinated invalidation strategies
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize the security cache manager.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        cache_config = config.get("cache", {})

        # Create specialized caches
        self.policy_cache = AdvancedCache(
            max_size=cache_config.get("policy_max_size", 1000),
            default_ttl=cache_config.get("policy_ttl", 300.0)
        )

        self.role_cache = AdvancedCache(
            max_size=cache_config.get("role_max_size", 500),
            default_ttl=cache_config.get("role_ttl", 600.0)
        )

        self.identity_cache = AdvancedCache(
            max_size=cache_config.get("identity_max_size", 200),
            default_ttl=cache_config.get("identity_ttl", 300.0)
        )

        self.permission_cache = AdvancedCache(
            max_size=cache_config.get("permission_max_size", 800),
            default_ttl=cache_config.get("permission_ttl", 300.0)
        )

    def get_policy_decision(self, cache_key: str) -> Any | None:
        """Get a cached policy decision."""
        return self.policy_cache.get(cache_key)

    def cache_policy_decision(
        self,
        cache_key: str,
        decision: Any,
        ttl: float | None = None,
        tags: set[str] | None = None
    ) -> bool:
        """Cache a policy decision."""
        return self.policy_cache.set(cache_key, decision, ttl, tags)

    def get_effective_roles(self, principal_id: str) -> set[str] | None:
        """Get cached effective roles for a principal."""
        return self.role_cache.get(f"roles:{principal_id}")

    def cache_effective_roles(
        self,
        principal_id: str,
        roles: set[str],
        ttl: float | None = None
    ) -> bool:
        """Cache effective roles for a principal."""
        tags = {f"principal:{principal_id}", "roles"}
        return self.role_cache.set(f"roles:{principal_id}", roles, ttl, tags)

    def get_effective_permissions(self, principal_id: str, resource: str) -> set[str] | None:
        """Get cached effective permissions."""
        cache_key = f"permissions:{principal_id}:{resource}"
        return self.permission_cache.get(cache_key)

    def cache_effective_permissions(
        self,
        principal_id: str,
        resource: str,
        permissions: set[str],
        ttl: float | None = None
    ) -> bool:
        """Cache effective permissions."""
        cache_key = f"permissions:{principal_id}:{resource}"
        tags = {f"principal:{principal_id}", f"resource:{resource}", "permissions"}
        return self.permission_cache.set(cache_key, permissions, ttl, tags)

    def invalidate_principal_cache(self, principal_id: str) -> int:
        """Invalidate all cached data for a principal."""
        tags = {f"principal:{principal_id}"}
        total_invalidated = 0

        for cache in [self.policy_cache, self.role_cache, self.identity_cache, self.permission_cache]:
            total_invalidated += cache.invalidate_by_tags(tags)

        return total_invalidated

    def invalidate_resource_cache(self, resource: str) -> int:
        """Invalidate all cached data for a resource."""
        tags = {f"resource:{resource}"}
        total_invalidated = 0

        for cache in [self.policy_cache, self.permission_cache]:
            total_invalidated += cache.invalidate_by_tags(tags)

        return total_invalidated

    def invalidate_by_category(self, category: str) -> int:
        """Invalidate cached data by category."""
        tags = {category}
        total_invalidated = 0

        cache_map = {
            "policies": [self.policy_cache],
            "roles": [self.role_cache],
            "identities": [self.identity_cache],
            "permissions": [self.permission_cache]
        }

        caches_to_invalidate = cache_map.get(category, [
            self.policy_cache, self.role_cache, self.identity_cache, self.permission_cache
        ])

        for cache in caches_to_invalidate:
            total_invalidated += cache.invalidate_by_tags(tags)

        return total_invalidated

    def clear_all_caches(self) -> None:
        """Clear all caches."""
        self.policy_cache.clear()
        self.role_cache.clear()
        self.identity_cache.clear()
        self.permission_cache.clear()

    def get_cache_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all caches."""
        return {
            "policy_cache": self.policy_cache.get_metrics(),
            "role_cache": self.role_cache.get_metrics(),
            "identity_cache": self.identity_cache.get_metrics(),
            "permission_cache": self.permission_cache.get_metrics()
        }


class InMemoryCacheManager:
    """
    Simple in-memory cache manager implementation.

    This is a basic implementation that can be used when advanced caching is not needed.
    """

    def __init__(self):
        """Initialize the in-memory cache manager."""
        self._cache: dict[str, Any] = {}
        self._lock = RLock()

    def get(self, key: str) -> Any | None:
        """Retrieve a value from cache."""
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: Any, ttl: float | None = None, tags: set[str] | None = None) -> bool:
        """Store a value in cache (TTL and tags ignored in this simple implementation)."""
        with self._lock:
            self._cache[key] = value
            return True

    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_by_tags(self, tags: set[str]) -> int:
        """Tags not supported in simple implementation."""
        return 0

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get the current number of cache entries."""
        return len(self._cache)
