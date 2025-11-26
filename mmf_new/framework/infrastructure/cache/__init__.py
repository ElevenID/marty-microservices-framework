"""
Enterprise Caching Infrastructure.

This package provides comprehensive caching capabilities including:
- Multiple cache backends (Redis, Memcached, In-Memory)
- Cache patterns (Cache-Aside, Write-Through, Write-Behind, Refresh-Ahead)
- Distributed caching with consistency guarantees
- Cache hierarchies and tiered caching
- Performance monitoring and metrics
- TTL management and cache warming
- Serialization and compression

Usage:
from mmf_new.framework.infrastructure.cache import (
        CacheManager, CacheConfig, CacheBackend, CachePattern,
        create_cache_manager, get_cache_manager, cache_context,
        cached, cache_invalidate
    )

    # Create cache configuration
    config = CacheConfig(
        backend=CacheBackend.REDIS,
        host="localhost",
        port=6379,
        default_ttl=3600,
    )

    # Create cache manager
    cache = create_cache_manager("user_cache", config)
    await cache.start()

    # Use cache
    await cache.set("user:123", user_data, ttl=1800)
    user = await cache.get("user:123")

    # Or use decorators
    @cached("user:{args[0]}", ttl=1800)
    async def get_user(user_id: str):
        return await database.get_user(user_id)
"""

from .manager import (  # Core classes; Configuration and data classes; Enums; Global functions; Decorators
    CacheBackend,
    CacheBackendInterface,
    CacheConfig,
    CacheFactory,
    CacheManager,
    CachePattern,
    CacheSerializer,
    CacheStats,
    InMemoryCache,
    RedisCache,
    SerializationFormat,
    cache_context,
    cache_invalidate,
    cached,
    create_cache_manager,
    get_cache_manager,
)

__all__ = [
    # Enums
    "CacheBackend",
    "CacheBackendInterface",
    # Configuration and data classes
    "CacheConfig",
    "CacheFactory",
    # Core classes
    "CacheManager",
    "CachePattern",
    "CacheSerializer",
    "CacheStats",
    "InMemoryCache",
    "RedisCache",
    "SerializationFormat",
    "cache_context",
    "cache_invalidate",
    # Decorators
    "cached",
    "create_cache_manager",
    # Global functions
    "get_cache_manager",
]
