"""
Standardized Connection Pooling Framework

Provides standardized connection pools for HTTP clients, Redis, and other network resources
with health checking, metrics, and automatic recovery.
"""

from .health import HealthCheckConfig, PoolHealthChecker
from .http_pool import HTTPConnectionPool, HTTPPoolConfig
from .manager import ConnectionPoolManager, PoolConfig
from .redis_pool import RedisConnectionPool, RedisPoolConfig

__all__ = [
    "HTTPConnectionPool",
    "HTTPPoolConfig",
    "RedisConnectionPool",
    "RedisPoolConfig",
    "ConnectionPoolManager",
    "PoolConfig",
    "PoolHealthChecker",
    "HealthCheckConfig",
]
