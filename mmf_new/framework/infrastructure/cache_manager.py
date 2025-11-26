"""Cache manager implementation."""

import json
import logging
from typing import Any

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from ..security.ports.common import ICacheManager

logger = logging.getLogger(__name__)


class CacheManager(ICacheManager):
    """Cache manager implementation using Redis or in-memory storage."""

    def __init__(self, redis_url: str | None = None, default_ttl: int = 3600):
        """Initialize cache manager."""
        self.redis_client = None
        self._memory_cache = {}
        self.default_ttl = default_ttl

        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
                logger.info("Connected to Redis cache")
            except Exception as e:
                logger.warning(
                    f"Failed to connect to Redis: {e}. Falling back to in-memory cache."
                )
                self.redis_client = None
        elif redis_url and not REDIS_AVAILABLE:
            logger.warning(
                "Redis URL provided but redis package not installed. Using in-memory cache."
            )

    def get(self, key: str) -> Any | None:
        """Retrieve a value from cache."""
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    return json.loads(value)
                return None
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                return self._memory_cache.get(key)
        return self._memory_cache.get(key)

    def set(
        self,
        key: str,
        value: Any,
        ttl: float | None = None,
        tags: set[str] | None = None,
    ) -> bool:
        """Store a value in cache."""
        try:
            # Handle non-serializable objects if necessary, but assuming JSON serializable for now
            serialized = json.dumps(value, default=str)
            if self.redis_client:
                if ttl:
                    return bool(self.redis_client.setex(key, int(ttl), serialized))
                return bool(self.redis_client.set(key, serialized))

            self._memory_cache[key] = value
            # Note: TTL not implemented for in-memory cache in this simple version
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if self.redis_client:
            return bool(self.redis_client.delete(key))
        if key in self._memory_cache:
            del self._memory_cache[key]
            return True
        return False

    def invalidate_by_tags(self, tags: set[str]) -> int:
        """Invalidate cache entries by tags."""
        # Simple implementation: no-op as tag support requires more complex logic
        return 0
