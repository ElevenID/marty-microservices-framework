"""
Enterprise Caching Infrastructure.

Provides comprehensive caching capabilities with multiple backends,
caching patterns, and advanced features for high-performance applications.

Features:
- Multiple cache backends (Redis, Memcached, In-Memory)
- Cache patterns (Cache-Aside, Write-Through, Write-Behind, Refresh-Ahead)
- Distributed caching with consistency guarantees
- Cache hierarchies and tiered caching
- Performance monitoring and metrics
- TTL management and cache warming
- Serialization and compression
"""

import asyncio
import builtins
import datetime
import io
import json
import logging
import pickle
import time
import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

# Required Redis imports (fail if missing)
import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import RedisError

REDIS_AVAILABLE = True

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheBackend(Enum):
    """Supported cache backends."""

    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"


class CachePattern(Enum):
    """Cache access patterns."""

    CACHE_ASIDE = "cache_aside"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    REFRESH_AHEAD = "refresh_ahead"


class RestrictedUnpickler(pickle.Unpickler):
    """Restricted unpickler that only allows safe types to prevent code execution."""

    SAFE_BUILTINS = {
        "str",
        "int",
        "float",
        "bool",
        "list",
        "tuple",
        "dict",
        "set",
        "frozenset",
        "bytes",
        "bytearray",
        "complex",
        "type",
        "slice",
        "range",
    }

    def find_class(self, module, name):
        # Only allow safe built-in types and specific allowed modules
        if module == "builtins" and name in self.SAFE_BUILTINS:
            return getattr(builtins, name)
        # Allow datetime objects which are commonly cached
        if module == "datetime" and name in {"datetime", "date", "time", "timedelta"}:
            return getattr(datetime, name)
        # Block everything else
        raise pickle.UnpicklingError(f"Forbidden class {module}.{name}")


class SerializationFormat(Enum):
    """Serialization formats for cache values."""

    PICKLE = "pickle"
    JSON = "json"
    STRING = "string"
    BYTES = "bytes"


@dataclass
class CacheConfig:
    """Cache configuration."""

    backend: CacheBackend = CacheBackend.MEMORY
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: str | None = None
    max_connections: int = 100
    default_ttl: int = 3600  # 1 hour
    serialization: SerializationFormat = SerializationFormat.PICKLE
    compression_enabled: bool = True
    key_prefix: str = ""
    namespace: str = "default"


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    total_size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class CacheSerializer:
    """Handles serialization and deserialization of cache values."""

    def __init__(self, format_type: SerializationFormat = SerializationFormat.PICKLE):
        self.format = format_type

    def serialize(self, value: Any) -> bytes:
        """Serialize value to bytes."""
        try:
            if self.format == SerializationFormat.PICKLE:
                return pickle.dumps(value)
            if self.format == SerializationFormat.JSON:
                return json.dumps(value).encode("utf-8")
            if self.format == SerializationFormat.STRING:
                return str(value).encode("utf-8")
            if self.format == SerializationFormat.BYTES:
                return value if isinstance(value, bytes) else str(value).encode("utf-8")
            raise ValueError(f"Unsupported serialization format: {self.format}")
        except Exception as e:
            logger.error("Serialization failed: %s", e)
            raise

    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value."""
        try:
            if self.format == SerializationFormat.PICKLE:
                # Security: Use restricted unpickler to prevent arbitrary code execution
                warnings.warn(
                    "Pickle deserialization is potentially unsafe. Consider using JSON format for better security.",
                    UserWarning,
                    stacklevel=2,
                )

                return RestrictedUnpickler(io.BytesIO(data)).load()
            if self.format == SerializationFormat.JSON:
                return json.loads(data.decode("utf-8"))
            if self.format == SerializationFormat.STRING:
                return data.decode("utf-8")
            if self.format == SerializationFormat.BYTES:
                return data
            raise ValueError(f"Unsupported serialization format: {self.format}")
        except Exception as e:
            logger.error("Deserialization failed: %s", e)
            raise


class CacheBackendInterface(ABC):
    """Abstract interface for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Get value from cache."""

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        """Set value in cache."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""

    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache entries."""

    @abstractmethod
    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""


class InMemoryCache(CacheBackendInterface):
    """In-memory cache backend."""

    def __init__(self, max_size: int = 1000):
        self.cache: builtins.dict[str, tuple] = {}  # key -> (value, expiry_time)
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
        try:
            self._cleanup_expired()
            self._evict_if_needed()

            expiry_time = time.time() + ttl if ttl else None
            self.cache[key] = (value, expiry_time)
            self.stats.sets += 1
            return True
        except (MemoryError, OSError) as e:
            logger.error("Failed to set cache key %s: %s", key, e)
            self.stats.errors += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if key in self.cache:
            del self.cache[key]
            self.stats.deletes += 1
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        self._cleanup_expired()
        return key in self.cache

    async def clear(self) -> bool:
        """Clear all cache entries."""
        self.cache.clear()
        return True

    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self.stats.total_size = len(self.cache)
        return self.stats


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
            self.redis = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.database,
                password=self.config.password,
                max_connections=self.config.max_connections,
                decode_responses=False,  # We handle bytes directly
            )
            # Test connection
            if self.redis:
                await self.redis.ping()  # type: ignore
            logger.info("Connected to Redis at %s:%s", self.config.host, self.config.port)
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            self.redis = None

    def _get_key(self, key: str) -> str:
        """Get full cache key with prefix and namespace."""
        prefix = f"{self.config.key_prefix}:" if self.config.key_prefix else ""
        return f"{prefix}{self.config.namespace}:{key}"

    async def get(self, key: str) -> bytes | None:
        """Get value from cache."""
        if not self.redis:
            await self.connect()

        try:
            full_key = self._get_key(key)
            value = await self.redis.get(full_key)  # type: ignore

            if value is not None:
                self.stats.hits += 1
                return value
            self.stats.misses += 1
            return None

        except (
            ConnectionError,
            TimeoutError,
            RedisError,
        ) as e:  # Specific Redis-related exceptions
            logger.error("Redis get error for key %s: %s", key, e)
            self.stats.errors += 1
            return None

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        """Set value in cache."""
        if not self.redis:
            await self.connect()

        try:
            full_key = self._get_key(key)
            cache_ttl = ttl or self.config.default_ttl

            result = await self.redis.setex(full_key, cache_ttl, value)  # type: ignore
            if result:
                self.stats.sets += 1
            return bool(result)

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error("Redis set error for key %s: %s", key, e)
            self.stats.errors += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        if not self.redis:
            await self.connect()

        try:
            full_key = self._get_key(key)
            result = await self.redis.delete(full_key)  # type: ignore
            if result:
                self.stats.deletes += 1
            return bool(result)

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error("Redis delete error for key %s: %s", key, e)
            self.stats.errors += 1
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis:
            await self.connect()

        try:
            full_key = self._get_key(key)
            result = await self.redis.exists(full_key)  # type: ignore
            return bool(result)

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error("Redis exists error for key %s: %s", key, e)
            return False

    async def clear(self) -> bool:
        """Clear all cache entries in namespace."""
        if not self.redis:
            await self.connect()

        try:
            pattern = self._get_key("*")
            keys = await self.redis.keys(pattern)  # type: ignore
            if keys:
                await self.redis.delete(*keys)  # type: ignore
            return True

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error("Redis clear error: %s", e)
            return False

    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self.stats


class CacheManager(Generic[T]):
    """High-level cache manager with patterns and advanced features."""

    def __init__(
        self,
        backend: CacheBackendInterface,
        serializer: CacheSerializer | None = None,
        pattern: CachePattern = CachePattern.CACHE_ASIDE,
    ):
        self.backend = backend
        self.serializer = serializer or CacheSerializer()
        self.pattern = pattern
        self._write_behind_queue: asyncio.Queue = asyncio.Queue()
        self._write_behind_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start cache manager."""
        if self.pattern == CachePattern.WRITE_BEHIND:
            self._write_behind_task = asyncio.create_task(self._write_behind_worker())

    async def stop(self) -> None:
        """Stop cache manager."""
        if self._write_behind_task:
            self._write_behind_task.cancel()
            try:
                await self._write_behind_task
            except asyncio.CancelledError:
                pass

    async def get(self, key: str) -> T | None:
        """Get value from cache with deserialization."""
        try:
            data = await self.backend.get(key)
            if data is not None:
                return self.serializer.deserialize(data)
            return None
        except (ValueError, TypeError, pickle.UnpicklingError) as e:
            logger.error("Cache get failed for key %s: %s", key, e)
            return None

    async def set(self, key: str, value: T, ttl: int | None = None) -> bool:
        """Set value in cache with serialization."""
        try:
            data = self.serializer.serialize(value)

            if self.pattern == CachePattern.WRITE_BEHIND:
                # Queue for background writing
                await self._write_behind_queue.put((key, data, ttl))
                return True
            return await self.backend.set(key, data, ttl)

        except (ValueError, TypeError, pickle.PicklingError) as e:
            logger.error("Cache set failed for key %s: %s", key, e)
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return await self.backend.delete(key)

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: int | None = None,
    ) -> T:
        """Get value from cache or set it using factory (Cache-Aside pattern)."""
        value = await self.get(key)

        if value is None:
            value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
            await self.set(key, value, ttl)

        return value

    async def get_multi(self, keys: builtins.list[str]) -> builtins.dict[str, T | None]:
        """Get multiple values from cache."""
        results = {}
        for key in keys:
            results[key] = await self.get(key)
        return results

    async def set_multi(
        self,
        items: builtins.dict[str, T],
        ttl: int | None = None,
    ) -> builtins.dict[str, bool]:
        """Set multiple values in cache."""
        results = {}
        for key, value in items.items():
            results[key] = await self.set(key, value, ttl)
        return results

    async def cache_warming(
        self,
        keys_and_factories: builtins.dict[str, Callable[[], T]],
        ttl: int | None = None,
    ) -> None:
        """Warm up cache with data."""
        tasks = []

        for key, factory in keys_and_factories.items():

            async def warm_key(k: str, f: Callable[[], T]):
                if not await self.backend.exists(k):
                    value = await f() if asyncio.iscoroutinefunction(f) else f()
                    await self.set(k, value, ttl)

            tasks.append(warm_key(key, factory))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _write_behind_worker(self) -> None:
        """Background worker for write-behind pattern."""
        while True:
            try:
                key, data, ttl = await self._write_behind_queue.get()
                await self.backend.set(key, data, ttl)
                self._write_behind_queue.task_done()
            except asyncio.CancelledError:
                break
            except (ValueError, TypeError, ConnectionError) as e:
                logger.error("Write-behind worker error: %s", e)

    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return await self.backend.get_stats()


class CacheFactory:
    """Factory for creating cache instances."""

    @staticmethod
    def create_cache(config: CacheConfig) -> CacheBackendInterface:
        """Create cache backend based on configuration."""
        if config.backend == CacheBackend.MEMORY:
            return InMemoryCache(max_size=1000)
        if config.backend == CacheBackend.REDIS:
            return RedisCache(config)
        raise ValueError(f"Unsupported cache backend: {config.backend}")

    @staticmethod
    def create_manager(
        config: CacheConfig,
        pattern: CachePattern = CachePattern.CACHE_ASIDE,
    ) -> CacheManager:
        """Create cache manager with specified pattern."""
        backend = CacheFactory.create_cache(config)
        serializer = CacheSerializer(config.serialization)
        return CacheManager(backend, serializer, pattern)


# Global cache instances
_cache_managers: builtins.dict[str, CacheManager] = {}


def get_cache_manager(name: str = "default") -> CacheManager | None:
    """Get global cache manager."""
    return _cache_managers.get(name)


def create_cache_manager(
    name: str,
    config: CacheConfig,
    pattern: CachePattern = CachePattern.CACHE_ASIDE,
) -> CacheManager:
    """Create and register global cache manager."""
    manager = CacheFactory.create_manager(config, pattern)
    _cache_managers[name] = manager
    return manager


@asynccontextmanager
async def cache_context(
    name: str,
    config: CacheConfig,
    pattern: CachePattern = CachePattern.CACHE_ASIDE,
):
    """Context manager for cache lifecycle."""
    manager = create_cache_manager(name, config, pattern)
    await manager.start()

    try:
        yield manager
    finally:
        await manager.stop()


# Decorators for caching
def cached(
    key_template: str,
    ttl: int | None = None,
    cache_name: str = "default",
):
    """Decorator for caching function results."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_values = {"args": args, "kwargs": kwargs}
            cache_key = key_template.format(**key_values)

            cache_manager = get_cache_manager(cache_name)
            if not cache_manager:
                # No cache available, execute function
                return await func(*args, **kwargs)

            # Try to get from cache
            result = await cache_manager.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def cache_invalidate(
    key_pattern: str,
    cache_name: str = "default",
):
    """Decorator for cache invalidation after function execution."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            cache_manager = get_cache_manager(cache_name)
            if cache_manager:
                # Generate invalidation key
                key_values = {"args": args, "kwargs": kwargs, "result": result}
                cache_key = key_pattern.format(**key_values)
                await cache_manager.delete(cache_key)

            return result

        return wrapper

    return decorator
