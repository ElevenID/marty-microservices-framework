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
import functools
import inspect
import logging
import pickle
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from mmf.core.domain.ports.cache import CachePort

from .memory_cache import InMemoryCache
from .types import (
    CacheBackend,
    CacheBackendInterface,
    CacheConfig,
    CachePattern,
    CacheSerializer,
    CacheStats,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CacheManager(CachePort[T]):
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
        if hasattr(self.backend, "connect"):
            await self.backend.connect()  # type: ignore

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

        if hasattr(self.backend, "disconnect"):
            await self.backend.disconnect()  # type: ignore

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

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return await self.backend.exists(key)

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
            tasks.append(self.get_or_set(key, factory, ttl))

        await asyncio.gather(*tasks)

    async def zadd(self, key: str, mapping: dict[T, float]) -> int:
        """Add members to sorted set."""
        try:
            byte_mapping = {self.serializer.serialize(k): v for k, v in mapping.items()}
            return await self.backend.zadd(key, byte_mapping)
        except (ValueError, TypeError, pickle.PicklingError) as e:
            logger.error("Cache zadd failed for key %s: %s", key, e)
            return 0

    async def zrevrangebyscore(
        self,
        key: str,
        max_score: float,
        min_score: float,
        start: int | None = None,
        num: int | None = None,
    ) -> list[T]:
        """Get members from sorted set by score (descending)."""
        try:
            items = await self.backend.zrevrangebyscore(key, max_score, min_score, start, num)
            return [self.serializer.deserialize(item) for item in items]
        except (ValueError, TypeError, pickle.UnpicklingError) as e:
            logger.error("Cache zrevrangebyscore failed for key %s: %s", key, e)
            return []

    async def zcount(self, key: str, min_score: float, max_score: float) -> int:
        """Count members in sorted set with score within range."""
        return await self.backend.zcount(key, min_score, max_score)

    async def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> int:
        """Remove members from sorted set by score range."""
        return await self.backend.zremrangebyscore(key, min_score, max_score)

    async def zcard(self, key: str) -> int:
        """Get number of members in sorted set."""
        return await self.backend.zcard(key)

    async def zremrangebyrank(self, key: str, min_rank: int, max_rank: int) -> int:
        """Remove members from sorted set by rank range."""
        return await self.backend.zremrangebyrank(key, min_rank, max_rank)

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on key."""
        return await self.backend.expire(key, ttl)

    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        return await self.backend.keys(pattern)

    async def clear(self) -> bool:
        """Clear all cache entries."""
        return await self.backend.clear()

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
            from .redis_cache import RedisCache

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
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_values = {"args": args, "kwargs": kwargs}

            # Add function arguments by name
            try:
                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                key_values.update(bound_args.arguments)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Cache key argument binding failed for %s; skipping args",
                    func.__name__,
                    exc_info=True,
                )

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
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            cache_manager = get_cache_manager(cache_name)
            if cache_manager:
                # Generate invalidation key
                key_values = {"args": args, "kwargs": kwargs, "result": result}
                try:
                    sig = inspect.signature(func)
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    key_values.update(bound_args.arguments)
                except Exception:
                    pass

                cache_key = key_pattern.format(**key_values)
                await cache_manager.delete(cache_key)

            return result

        return wrapper

    return decorator
