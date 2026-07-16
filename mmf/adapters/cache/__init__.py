"""
MMF Cache Adapters.

This module provides cache backend implementations for the MMF cache infrastructure.
"""

from mmf.adapters.cache.redis_cache import RedisCacheManager

__all__ = [
    "RedisCacheManager",
]
