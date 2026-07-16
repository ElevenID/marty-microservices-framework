import builtins
import time
from typing import Any

from .types import CacheBackendInterface, CacheStats


class InMemoryCache(CacheBackendInterface):
    """In-memory cache backend."""

    def __init__(self, max_size: int = 1000):
        self.cache: builtins.dict[str, tuple] = {}  # key -> (value, expiry_time)
        self.zsets: builtins.dict[str, dict[bytes, float]] = {}  # key -> {member: score}
        self.zset_expiry: builtins.dict[str, float] = {}  # key -> expiry_time
        self.max_size = max_size
        self.stats = CacheStats()

    def _is_expired(self, expiry_time: float | None) -> bool:
        """Check if cache entry is expired."""
        return expiry_time is not None and time.time() > expiry_time

    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, expiry) in self.cache.items()
            if expiry is not None and current_time > expiry
        ]
        for key in expired_keys:
            del self.cache[key]

        expired_zsets = [key for key, expiry in self.zset_expiry.items() if current_time > expiry]
        for key in expired_zsets:
            if key in self.zsets:
                del self.zsets[key]
            del self.zset_expiry[key]

    def _evict_if_needed(self) -> None:
        """Evict entries if cache is full (LRU)."""
        if len(self.cache) >= self.max_size:
            # Simple LRU: remove oldest entry
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]

    async def get(self, key: str) -> bytes | None:
        """Get value from cache."""
        self._cleanup_expired()
        if key in self.cache:
            value, expiry = self.cache[key]
            if not self._is_expired(expiry):
                self.stats.hits += 1
                return value
            del self.cache[key]
        self.stats.misses += 1
        return None

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        """Set value in cache."""
        self._cleanup_expired()
        self._evict_if_needed()
        expiry = time.time() + ttl if ttl is not None else None
        self.cache[key] = (value, expiry)
        self.stats.sets += 1
        return True

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self.cache:
            del self.cache[key]
            self.stats.deletes += 1
            return True
        if key in self.zsets:
            del self.zsets[key]
            if key in self.zset_expiry:
                del self.zset_expiry[key]
            self.stats.deletes += 1
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        self._cleanup_expired()
        return key in self.cache or key in self.zsets

    async def clear(self) -> bool:
        """Clear all cache entries."""
        self.cache.clear()
        self.zsets.clear()
        self.zset_expiry.clear()
        return True

    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        # Estimate size (very rough)
        self.stats.total_size = len(self.cache) * 100  # Assume avg 100 bytes
        return self.stats

    async def zadd(self, key: str, mapping: dict[bytes, float]) -> int:
        """Add members to sorted set."""
        self._cleanup_expired()
        if key not in self.zsets:
            self.zsets[key] = {}

        count = 0
        for member, score in mapping.items():
            if member not in self.zsets[key]:
                count += 1
            self.zsets[key][member] = score
        return count

    async def zrevrangebyscore(
        self,
        key: str,
        max_score: float,
        min_score: float,
        start: int | None = None,
        num: int | None = None,
    ) -> list[bytes]:
        """Get members from sorted set by score (descending)."""
        self._cleanup_expired()
        if key not in self.zsets:
            return []

        members = [(m, s) for m, s in self.zsets[key].items() if min_score <= s <= max_score]
        members.sort(key=lambda x: x[1], reverse=True)

        if start is not None and num is not None:
            return [m for m, _ in members[start : start + num]]
        return [m for m, _ in members]

    async def zcount(self, key: str, min_score: float, max_score: float) -> int:
        """Count members in sorted set with score within range."""
        self._cleanup_expired()
        if key not in self.zsets:
            return 0

        return sum(1 for s in self.zsets[key].values() if min_score <= s <= max_score)

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """Remove members from sorted set by score range."""
        self._cleanup_expired()
        if key not in self.zsets:
            return 0

        to_remove = [m for m, s in self.zsets[key].items() if min_score <= s <= max_score]
        for m in to_remove:
            del self.zsets[key][m]
        return len(to_remove)

    async def zcard(self, key: str) -> int:
        """Get number of members in sorted set."""
        self._cleanup_expired()
        if key not in self.zsets:
            return 0
        return len(self.zsets[key])

    async def zremrangebyrank(self, key: str, min_rank: int, max_rank: int) -> int:
        """Remove members from sorted set by rank range."""
        self._cleanup_expired()
        if key not in self.zsets:
            return 0

        members = sorted(self.zsets[key].items(), key=lambda x: x[1])
        # Adjust negative indices
        if min_rank < 0:
            min_rank += len(members)
        if max_rank < 0:
            max_rank += len(members)

        to_remove = [m for m, _ in members[min_rank : max_rank + 1]]
        for m in to_remove:
            del self.zsets[key][m]
        return len(to_remove)

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key."""
        if key in self.cache:
            self.cache[key] = (self.cache[key][0], time.time() + ttl)
            return True
        if key in self.zsets:
            self.zset_expiry[key] = time.time() + ttl
            return True
        return False

    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        self._cleanup_expired()
        all_keys = list(self.cache.keys()) + list(self.zsets.keys())
        if pattern == "*":
            return all_keys
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in all_keys if k.startswith(prefix)]
        return [k for k in all_keys if k == pattern]
