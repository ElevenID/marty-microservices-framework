"""
Redis Cache Manager for MMF.

This module provides a Redis-backed implementation of the ICacheManager protocol.
It includes automatic key prefixing, metrics collection, and serialization.

Usage:
    import redis.asyncio as redis

    redis_client = redis.from_url("redis://localhost:6379/0")
    prefix = KeyPrefixConfig(app_prefix="marty", plugin_prefix="auth")
    metrics = CacheMetrics(service_name="marty-ui")

    cache = RedisCacheManager(redis_client, prefix, metrics)

    await cache.set("session:abc123", {"user_id": "123"}, ttl=3600)
    data = await cache.get("session:abc123")
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from mmf.core.cache import BaseCacheManager, ICacheMetrics, KeyPrefixConfig

logger = logging.getLogger(__name__)


class RedisCacheManager(BaseCacheManager):
    """
    Redis-backed cache manager implementation.

    Provides:
    - Automatic key prefixing for namespace isolation
    - JSON serialization/deserialization
    - Metrics collection for hits, misses, latency
    - Atomic operations where possible

    Compatible with redis.asyncio client.
    """

    def __init__(
        self,
        redis_client: Any,
        prefix_config: KeyPrefixConfig | None = None,
        metrics: ICacheMetrics | None = None,
        default_ttl: int = 3600,
    ):
        """
        Initialize Redis cache manager.

        Args:
            redis_client: Async Redis client (redis.asyncio)
            prefix_config: Key prefix configuration for namespacing
            metrics: Cache metrics collector (optional)
            default_ttl: Default TTL in seconds for keys without explicit TTL
        """
        super().__init__(prefix_config, metrics, default_ttl)
        self._redis = redis_client

    def _serialize(self, value: Any) -> str:
        """Serialize value to JSON string."""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            self._logger.warning(f"Serialization error: {e}, storing as string")
            return str(value)

    def _deserialize(self, data: str | bytes | None) -> Any:
        """Deserialize JSON string to value."""
        if data is None:
            return None
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            # Return raw string if not valid JSON
            return data

    async def get(self, key: str) -> Any | None:
        """
        Get a value from Redis.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            Deserialized value or None if not found
        """
        start = time.perf_counter()
        full_key = self._build_key(key)

        try:
            data = await self._redis.get(full_key)
            latency = time.perf_counter() - start

            if data is None:
                self._record_miss()
                self._record_latency("get", latency)
                return None

            self._record_hit()
            self._record_latency("get", latency)
            return self._deserialize(data)

        except Exception as e:
            self._record_error("get")
            self._logger.error(f"Redis GET error for {key}: {e}")
            raise

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value in Redis.

        Args:
            key: Cache key (will be prefixed automatically)
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live in seconds, defaults to default_ttl

        Returns:
            True if successful
        """
        start = time.perf_counter()
        full_key = self._build_key(key)
        ttl = ttl if ttl is not None else self._default_ttl
        serialized = self._serialize(value)

        try:
            if ttl > 0:
                await self._redis.setex(full_key, ttl, serialized)
            else:
                await self._redis.set(full_key, serialized)

            self._record_latency("set", time.perf_counter() - start)
            return True

        except Exception as e:
            self._record_error("set")
            self._logger.error(f"Redis SET error for {key}: {e}")
            raise

    async def delete(self, key: str) -> bool:
        """
        Delete a key from Redis.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            True if key was deleted, False if it didn't exist
        """
        start = time.perf_counter()
        full_key = self._build_key(key)

        try:
            result = await self._redis.delete(full_key)
            self._record_latency("delete", time.perf_counter() - start)
            return result > 0

        except Exception as e:
            self._record_error("delete")
            self._logger.error(f"Redis DELETE error for {key}: {e}")
            raise

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in Redis.

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            True if key exists
        """
        start = time.perf_counter()
        full_key = self._build_key(key)

        try:
            result = await self._redis.exists(full_key)
            self._record_latency("exists", time.perf_counter() - start)
            return result > 0

        except Exception as e:
            self._record_error("exists")
            self._logger.error(f"Redis EXISTS error for {key}: {e}")
            raise

    async def get_and_delete(self, key: str) -> Any | None:
        """
        Atomically get and delete a key (consume pattern).

        Uses separate GET + DELETE for maximum Redis compatibility
        (GETDEL requires Redis 6.2+).

        Args:
            key: Cache key (will be prefixed automatically)

        Returns:
            Deserialized value or None if not found
        """
        start = time.perf_counter()
        full_key = self._build_key(key)

        try:
            # Use pipeline for pseudo-atomic get+delete
            # Note: For true atomicity, use GETDEL on Redis 6.2+
            pipe = self._redis.pipeline()
            pipe.get(full_key)
            pipe.delete(full_key)
            results = await pipe.execute()

            data = results[0]
            latency = time.perf_counter() - start

            if data is None:
                self._record_miss()
                self._record_latency("get_and_delete", latency)
                return None

            self._record_hit()
            self._record_latency("get_and_delete", latency)
            return self._deserialize(data)

        except Exception as e:
            self._record_error("get_and_delete")
            self._logger.error(f"Redis GET+DELETE error for {key}: {e}")
            raise

    async def set_if_not_exists(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value only if the key doesn't exist (SETNX pattern).

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if set, False if key already existed
        """
        start = time.perf_counter()
        full_key = self._build_key(key)
        ttl = ttl if ttl is not None else self._default_ttl
        serialized = self._serialize(value)

        try:
            if ttl > 0:
                # SET with NX and EX options
                result = await self._redis.set(full_key, serialized, nx=True, ex=ttl)
            else:
                result = await self._redis.setnx(full_key, serialized)

            self._record_latency("setnx", time.perf_counter() - start)
            return bool(result)

        except Exception as e:
            self._record_error("setnx")
            self._logger.error(f"Redis SETNX error for {key}: {e}")
            raise

    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment a counter in Redis.

        Args:
            key: Cache key
            amount: Amount to increment by

        Returns:
            New value after increment
        """
        start = time.perf_counter()
        full_key = self._build_key(key)

        try:
            result = await self._redis.incrby(full_key, amount)
            self._record_latency("incr", time.perf_counter() - start)
            return result

        except Exception as e:
            self._record_error("incr")
            self._logger.error(f"Redis INCRBY error for {key}: {e}")
            raise

    async def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration on an existing key.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds

        Returns:
            True if expiration was set, False if key doesn't exist
        """
        start = time.perf_counter()
        full_key = self._build_key(key)

        try:
            result = await self._redis.expire(full_key, ttl)
            self._record_latency("expire", time.perf_counter() - start)
            return bool(result)

        except Exception as e:
            self._record_error("expire")
            self._logger.error(f"Redis EXPIRE error for {key}: {e}")
            raise

    async def ttl(self, key: str) -> int:
        """
        Get remaining TTL for a key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds, -1 if no expiration, -2 if key doesn't exist
        """
        start = time.perf_counter()
        full_key = self._build_key(key)

        try:
            result = await self._redis.ttl(full_key)
            self._record_latency("ttl", time.perf_counter() - start)
            return result

        except Exception as e:
            self._record_error("ttl")
            self._logger.error(f"Redis TTL error for {key}: {e}")
            raise

    async def keys(self, pattern: str = "*") -> list[str]:
        """
        Get all keys matching a pattern within this cache's namespace.

        Note: Uses SCAN for Redis Cluster compatibility. For large keyspaces,
        consider implementing pagination or using more specific patterns.

        Args:
            pattern: Glob-style pattern (applied after prefix)

        Returns:
            List of matching keys (with prefix stripped)
        """
        full_pattern = self._build_key(pattern)

        try:
            # Use SCAN instead of KEYS for Redis Cluster compatibility
            # SCAN is cursor-based and doesn't block the server
            keys = []
            cursor = 0
            while True:
                cursor, batch = await self._redis.scan(
                    cursor=cursor,
                    match=full_pattern,
                    count=100,  # Reasonable batch size
                )
                keys.extend(batch)
                if cursor == 0:
                    break

            # Strip prefix from returned keys
            return [
                self._prefix.strip_prefix(k.decode() if isinstance(k, bytes) else k) for k in keys
            ]
        except Exception as e:
            self._record_error("keys")
            self._logger.error(f"Redis SCAN error for {pattern}: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check Redis connectivity.

        Returns:
            True if Redis is healthy
        """
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False


__all__ = [
    "RedisCacheManager",
]
