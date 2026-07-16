from typing import Any

# Optional Redis imports
try:
    import redis.asyncio as redis
    from redis.asyncio import Redis
    from redis.exceptions import RedisError

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    Redis = Any  # type: ignore
    RedisError = Exception  # type: ignore

from .types import CacheBackendInterface, CacheConfig, CacheStats


class RedisCache(CacheBackendInterface):
    """Redis cache backend."""

    def __init__(self, config: CacheConfig):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not available. Please install redis: pip install redis")

        self.config = config
        self.redis: Any | None = None  # Type as Any to avoid typing issues
        self.stats = CacheStats()

    async def connect(self) -> None:
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not available")

        try:
            if redis is None:
                raise ImportError("Redis module not available")

            if self.config.url:
                self.redis = redis.from_url(
                    self.config.url,
                    db=self.config.database,
                    password=self.config.password,
                    max_connections=self.config.max_connections,
                    decode_responses=False,  # We handle serialization manually
                )
            else:
                self.redis = redis.Redis(
                    host=self.config.host,
                    port=self.config.port,
                    db=self.config.database,
                    password=self.config.password,
                    max_connections=self.config.max_connections,
                    decode_responses=False,
                )

            if self.redis:
                await self.redis.ping()
        except RedisError as e:
            self.stats.errors += 1
            raise ConnectionError(f"Failed to connect to Redis: {e}") from e

    async def get(self, key: str) -> bytes | None:
        """Get value from cache."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                value = await self.redis.get(key)
                if value:
                    self.stats.hits += 1
                    return value
            self.stats.misses += 1
            return None
        except RedisError:
            self.stats.errors += 1
            return None

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        """Set value in cache."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                await self.redis.set(key, value, ex=ttl)
                self.stats.sets += 1
                return True
            return False
        except RedisError:
            self.stats.errors += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                await self.redis.delete(key)
                self.stats.deletes += 1
                return True
            return False
        except RedisError:
            self.stats.errors += 1
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                return await self.redis.exists(key) > 0
            return False
        except RedisError:
            self.stats.errors += 1
            return False

    async def clear(self) -> bool:
        """Clear all cache entries."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                await self.redis.flushdb()
                return True
            return False
        except RedisError:
            self.stats.errors += 1
            return False

    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        if not self.redis:
            return self.stats

        try:
            if self.redis:
                info = await self.redis.info()
                self.stats.total_size = info.get("used_memory", 0)
            return self.stats
        except RedisError:
            self.stats.errors += 1
            return self.stats

    async def zadd(self, key: str, mapping: dict[bytes, float]) -> int:
        """Add members to sorted set."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                return await self.redis.zadd(key, mapping)
            return 0
        except RedisError:
            self.stats.errors += 1
            return 0

    async def zrevrangebyscore(
        self,
        key: str,
        max_score: float,
        min_score: float,
        start: int | None = None,
        num: int | None = None,
    ) -> list[bytes]:
        """Get members from sorted set by score (descending)."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                return await self.redis.zrevrangebyscore(
                    key, max_score, min_score, start=start, num=num
                )
            return []
        except RedisError:
            self.stats.errors += 1
            return []

    async def zcount(self, key: str, min_score: float, max_score: float) -> int:
        """Count members in sorted set with score within range."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                return await self.redis.zcount(key, min_score, max_score)
            return 0
        except RedisError:
            self.stats.errors += 1
            return 0

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """Remove members from sorted set by score range."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                return await self.redis.zremrangebyscore(key, min_score, max_score)
            return 0
        except RedisError:
            self.stats.errors += 1
            return 0

    async def zcard(self, key: str) -> int:
        """Get number of members in sorted set."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                return await self.redis.zcard(key)
            return 0
        except RedisError:
            self.stats.errors += 1
            return 0

    async def zremrangebyrank(self, key: str, min_rank: int, max_rank: int) -> int:
        """Remove members from sorted set by rank range."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                return await self.redis.zremrangebyrank(key, min_rank, max_rank)
            return 0
        except RedisError:
            self.stats.errors += 1
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                return await self.redis.expire(key, ttl)
            return False
        except RedisError:
            self.stats.errors += 1
            return False

    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        if not self.redis:
            await self.connect()

        try:
            if self.redis:
                keys = await self.redis.keys(pattern)
                return [k.decode("utf-8") if isinstance(k, bytes) else str(k) for k in keys]
            return []
        except RedisError:
            self.stats.errors += 1
            return []
