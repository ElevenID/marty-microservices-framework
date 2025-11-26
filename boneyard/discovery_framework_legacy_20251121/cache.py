from __future__ import annotations

"""
Caching utilities extracted from the legacy discovery implementation.

Breaking the cache out into its own module keeps the client implementations
focused while preserving the existing behaviour and statistics tracking.
"""

import asyncio
import builtins
import logging
import time
from collections.abc import Callable

from .config import CacheStrategy, DiscoveryConfig, ServiceQuery
from .core import ServiceInstance

logger = logging.getLogger(__name__)


class CacheEntry:
    """Cache entry for service discovery results."""

    def __init__(
        self,
        instances: builtins.list[ServiceInstance],
        ttl: float,
        refresh_callback: Callable | None = None,
    ):
        self.instances = instances
        self.created_at = time.time()
        self.ttl = ttl
        self.last_accessed = time.time()
        self.access_count = 0
        self.refresh_callback = refresh_callback
        self._refreshing = False

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.created_at > self.ttl

    def should_refresh(self, refresh_ahead_factor: float = 0.8) -> bool:
        """Check if cache entry should be refreshed ahead of expiration."""
        age = time.time() - self.created_at
        return age > (self.ttl * refresh_ahead_factor)

    def access(self) -> builtins.list[ServiceInstance]:
        """Access cache entry and update statistics."""
        self.last_accessed = time.time()
        self.access_count += 1
        return self.instances.copy()


class ServiceCache:
    """Service discovery cache with multiple strategies."""

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self._cache: builtins.dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = {"hits": 0, "misses": 0, "refreshes": 0, "evictions": 0}

    def _generate_cache_key(self, query: ServiceQuery) -> str:
        """Generate cache key for service query."""
        key_parts = [
            query.service_name,
            query.version or "*",
            query.environment or "*",
            query.zone or "*",
            query.region or "*",
        ]

        if query.tags:
            tag_str = ",".join(f"{k}={v}" for k, v in sorted(query.tags.items()))
            key_parts.append(f"tags:{tag_str}")

        if query.labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(query.labels.items()))
            key_parts.append(f"labels:{label_str}")

        if query.protocols:
            proto_str = ",".join(sorted(query.protocols))
            key_parts.append(f"protocols:{proto_str}")

        return "|".join(key_parts)

    async def get(
        self, query: ServiceQuery, refresh_callback: Callable | None = None
    ) -> builtins.list[ServiceInstance] | None:
        """Get instances from cache."""
        if self.config.cache_strategy == CacheStrategy.NONE:
            return None

        cache_key = self._generate_cache_key(query)

        async with self._lock:
            entry = self._cache.get(cache_key)

            if not entry:
                self._stats["misses"] += 1
                return None

            if entry.is_expired():
                del self._cache[cache_key]
                self._stats["misses"] += 1
                return None

            if self.config.cache_strategy == CacheStrategy.REFRESH_AHEAD and refresh_callback:
                if entry.should_refresh(self.config.refresh_ahead_factor) and not entry._refreshing:
                    asyncio.create_task(self._refresh_entry(cache_key, entry, refresh_callback))

            self._stats["hits"] += 1
            return entry.access()

    async def put(
        self,
        query: ServiceQuery,
        instances: builtins.list[ServiceInstance],
        refresh_callback: Callable | None = None,
    ) -> None:
        """Put instances in cache."""
        if self.config.cache_strategy == CacheStrategy.NONE:
            return

        cache_key = self._generate_cache_key(query)

        async with self._lock:
            if len(self._cache) >= self.config.cache_max_size:
                await self._evict_lru()

            entry = CacheEntry(instances, self.config.cache_ttl, refresh_callback)
            self._cache[cache_key] = entry

    async def _refresh_entry(
        self, cache_key: str, entry: CacheEntry, refresh_callback: Callable
    ) -> None:
        """Refresh cache entry asynchronously."""
        entry._refreshing = True
        try:
            new_instances = await refresh_callback()
            if new_instances:
                async with self._lock:
                    if cache_key in self._cache:
                        entry.instances = new_instances
                        entry.created_at = time.time()
                        self._stats["refreshes"] += 1
        except Exception as e:  # noqa: BLE001 - surface warning and continue
            logger.warning("Failed to refresh cache entry %s: %s", cache_key, e)
        finally:
            entry._refreshing = False

    async def _evict_lru(self) -> None:
        """Evict least recently used cache entry."""
        if not self._cache:
            return

        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]
        self._stats["evictions"] += 1

    async def invalidate(self, service_name: str) -> None:
        """Invalidate cache entries for a service."""
        async with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys() if key.startswith(f"{service_name}|")
            ]

            for key in keys_to_remove:
                del self._cache[key]

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()

    def get_stats(self) -> builtins.dict[str, builtins.float | int]:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

        return {
            **self._stats,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache),
        }
