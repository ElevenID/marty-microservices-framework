"""
Redis Connection Pool Implementation

Provides standardized Redis connection pooling with health checking,
failover support, and integration with the resilience framework.
"""

import asyncio
import logging
import time
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, Union

import aioredis
from aioredis import ConnectionPool, Redis
from aioredis.exceptions import ConnectionError, RedisError, TimeoutError
from aioredis.sentinel import Sentinel

logger = logging.getLogger(__name__)


@dataclass
class RedisPoolConfig:
    """Redis connection pool configuration"""

    # Connection details
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    username: str | None = None

    # Pool sizing
    max_connections: int = 50
    min_connections: int = 5

    # Timeouts
    connect_timeout: float = 10.0
    socket_timeout: float = 30.0
    socket_connect_timeout: float = 10.0

    # Health and lifecycle
    max_idle_time: float = 300.0  # 5 minutes
    health_check_interval: float = 60.0  # 1 minute
    connection_ttl: float = 3600.0  # 1 hour

    # Retry behavior
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0

    # Redis-specific settings
    decode_responses: bool = True
    encoding: str = "utf-8"
    socket_keepalive: bool = True
    socket_keepalive_options: dict[str, int] = field(default_factory=dict)

    # Cluster support
    cluster_mode: bool = False
    cluster_nodes: list[dict[str, Any]] = field(default_factory=list)

    # Failover support
    sentinel_hosts: list[dict[str, Any]] = field(default_factory=list)
    sentinel_service_name: str | None = None

    # SSL/TLS
    ssl: bool = False
    ssl_ca_certs: str | None = None
    ssl_cert_reqs: str | None = None
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None

    # Metrics and monitoring
    enable_metrics: bool = True

    name: str = "default"


class RedisPooledConnection:
    """Wrapper for Redis connection with metadata and lifecycle management"""

    def __init__(self, redis: Redis, pool: 'RedisConnectionPool'):
        self.redis = redis
        self.pool = pool
        self.created_at = time.time()
        self.last_used = time.time()
        self.command_count = 0
        self.error_count = 0
        self.in_use = False
        self._closed = False

    async def __aenter__(self):
        self.last_used = time.time()
        self.in_use = True
        return self.redis

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.in_use = False
        if exc_type is not None:
            self.error_count += 1
        else:
            self.command_count += 1
        await self.pool._return_connection(self)

    @property
    def idle_time(self) -> float:
        """Time since last use"""
        return time.time() - self.last_used

    @property
    def age(self) -> float:
        """Age of connection"""
        return time.time() - self.created_at

    async def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        if self._closed:
            return False

        try:
            # Quick ping to check connectivity
            await self.redis.ping()
            return (
                self.idle_time < self.pool.config.max_idle_time and
                self.age < self.pool.config.connection_ttl
            )
        except Exception:
            return False

    async def close(self):
        """Close the connection"""
        if not self._closed:
            self._closed = True
            try:
                await self.redis.close()
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")


class RedisConnectionPool:
    """Redis connection pool with health checking and failover support"""

    def __init__(self, config: RedisPoolConfig):
        self.config = config
        self._connections: set[RedisPooledConnection] = set()
        self._available: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._closed = False

        # Metrics
        self.total_connections_created = 0
        self.total_connections_destroyed = 0
        self.total_commands = 0
        self.total_errors = 0
        self.active_connections = 0

        # Health checker task
        self._health_check_task: asyncio.Task | None = None
        self._start_health_checker()

    async def acquire(self) -> AbstractAsyncContextManager[Redis]:
        """Acquire a connection from the pool"""
        if self._closed:
            raise RuntimeError("Redis connection pool is closed")

        connection = await self._get_connection()
        return connection

    async def _get_connection(self) -> RedisPooledConnection:
        """Get or create a connection"""
        async with self._lock:
            # Try to get an available connection
            while not self._available.empty():
                try:
                    connection = self._available.get_nowait()
                    if await connection.is_healthy():
                        return connection
                    else:
                        await self._destroy_connection(connection)
                except asyncio.QueueEmpty:
                    break

            # Create new connection if under limit
            if len(self._connections) < self.config.max_connections:
                return await self._create_connection()

            # Wait for a connection to become available
            return await self._wait_for_connection()

    async def _create_connection(self) -> RedisPooledConnection:
        """Create a new Redis connection"""
        try:
            # Build connection parameters
            connection_params = {
                "host": self.config.host,
                "port": self.config.port,
                "db": self.config.db,
                "password": self.config.password,
                "username": self.config.username,
                "socket_timeout": self.config.socket_timeout,
                "socket_connect_timeout": self.config.socket_connect_timeout,
                "decode_responses": self.config.decode_responses,
                "encoding": self.config.encoding,
                "socket_keepalive": self.config.socket_keepalive,
                "socket_keepalive_options": self.config.socket_keepalive_options,
                "ssl": self.config.ssl,
                "ssl_ca_certs": self.config.ssl_ca_certs,
                "ssl_cert_reqs": self.config.ssl_cert_reqs,
                "ssl_certfile": self.config.ssl_certfile,
                "ssl_keyfile": self.config.ssl_keyfile,
            }

            # Remove None values
            connection_params = {k: v for k, v in connection_params.items() if v is not None}

            # Create Redis connection
            if self.config.cluster_mode:
                # Redis Cluster support
                redis = aioredis.Redis.from_url(
                    f"redis://{self.config.host}:{self.config.port}/{self.config.db}",
                    **connection_params
                )
            elif self.config.sentinel_hosts:
                # Redis Sentinel support
                sentinel = Sentinel(
                    [(host["host"], host["port"]) for host in self.config.sentinel_hosts]
                )
                redis = sentinel.master_for(
                    self.config.sentinel_service_name or "mymaster"
                )
            else:
                # Standard Redis connection
                redis = aioredis.Redis(**connection_params)

            # Test the connection
            await redis.ping()

            connection = RedisPooledConnection(redis, self)
            self._connections.add(connection)
            self.total_connections_created += 1
            self.active_connections += 1

            logger.debug(f"Created new Redis connection in pool '{self.config.name}'")
            return connection

        except Exception as e:
            logger.error(f"Failed to create Redis connection: {e}")
            raise

    async def _wait_for_connection(self) -> RedisPooledConnection:
        """Wait for a connection to become available"""
        # Simple implementation - in production you'd want more sophisticated queuing
        await asyncio.sleep(0.1)
        return await self._get_connection()

    async def _return_connection(self, connection: RedisPooledConnection):
        """Return a connection to the pool"""
        async with self._lock:
            if connection in self._connections and await connection.is_healthy():
                try:
                    self._available.put_nowait(connection)
                except asyncio.QueueFull:
                    await self._destroy_connection(connection)
            else:
                await self._destroy_connection(connection)

    async def _destroy_connection(self, connection: RedisPooledConnection):
        """Destroy a connection"""
        try:
            if connection in self._connections:
                self._connections.remove(connection)
                self.active_connections -= 1

            await connection.close()
            self.total_connections_destroyed += 1

            logger.debug(f"Destroyed Redis connection in pool '{self.config.name}'")

        except Exception as e:
            logger.warning(f"Error destroying Redis connection: {e}")

    def _start_health_checker(self):
        """Start background health checking task"""
        if self.config.health_check_interval > 0:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def _health_check_loop(self):
        """Background health check loop"""
        while not self._closed:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._health_check_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Redis health check error: {e}")

    async def _health_check_connections(self):
        """Check health of all connections"""
        async with self._lock:
            unhealthy_connections = []

            for connection in list(self._connections):
                if not connection.in_use and not await connection.is_healthy():
                    unhealthy_connections.append(connection)

            for connection in unhealthy_connections:
                await self._destroy_connection(connection)

    async def execute_command(self, command: str, *args, **kwargs) -> Any:
        """Execute a Redis command using the pool"""
        retries = 0
        last_exception: Exception | None = None

        while retries <= self.config.max_retries:
            try:
                connection = await self.acquire()
                async with connection as redis:
                    self.total_commands += 1
                    result = await redis.execute_command(command, *args, **kwargs)
                    return result

            except (ConnectionError, TimeoutError) as e:
                last_exception = e
                self.total_errors += 1
                retries += 1

                if retries <= self.config.max_retries:
                    delay = self.config.retry_delay * (self.config.retry_backoff_factor ** (retries - 1))
                    await asyncio.sleep(delay)
                    logger.warning(f"Redis command failed, retrying in {delay}s: {e}")
            except Exception as e:
                # Non-retriable errors
                self.total_errors += 1
                raise e

        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Redis command failed with no exception captured")

    # Convenience methods for common Redis operations
    async def get(self, key: str) -> Any:
        """Get value by key"""
        connection = await self.acquire()
        async with connection as redis:
            return await redis.get(key)

    async def set(self, key: str, value: Any, **kwargs) -> bool:
        """Set key-value pair"""
        connection = await self.acquire()
        async with connection as redis:
            return await redis.set(key, value, **kwargs)

    async def delete(self, *keys: str) -> int:
        """Delete keys"""
        connection = await self.acquire()
        async with connection as redis:
            return await redis.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """Check if keys exist"""
        connection = await self.acquire()
        async with connection as redis:
            return await redis.exists(*keys)

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration for key"""
        connection = await self.acquire()
        async with connection as redis:
            return await redis.expire(key, seconds)

    def get_metrics(self) -> dict[str, Any]:
        """Get pool metrics"""
        return {
            "pool_name": self.config.name,
            "total_connections": len(self._connections),
            "active_connections": self.active_connections,
            "available_connections": self._available.qsize(),
            "total_connections_created": self.total_connections_created,
            "total_connections_destroyed": self.total_connections_destroyed,
            "total_commands": self.total_commands,
            "total_errors": self.total_errors,
            "error_rate": self.total_errors / max(self.total_commands, 1),
            "max_connections": self.config.max_connections,
            "host": self.config.host,
            "port": self.config.port,
            "db": self.config.db
        }

    async def close(self):
        """Close the connection pool"""
        if self._closed:
            return

        self._closed = True

        # Cancel health checker
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        async with self._lock:
            for connection in list(self._connections):
                await self._destroy_connection(connection)

        logger.info(f"Redis connection pool '{self.config.name}' closed")


# Global Redis pools registry
_redis_pools: dict[str, RedisConnectionPool] = {}
_pools_lock = asyncio.Lock()


async def get_redis_pool(name: str = "default", config: RedisPoolConfig | None = None) -> RedisConnectionPool:
    """Get or create a Redis connection pool"""
    async with _pools_lock:
        if name not in _redis_pools:
            if config is None:
                config = RedisPoolConfig(name=name)
            _redis_pools[name] = RedisConnectionPool(config)
        return _redis_pools[name]


async def close_all_redis_pools():
    """Close all Redis connection pools"""
    async with _pools_lock:
        for pool in list(_redis_pools.values()):
            await pool.close()
        _redis_pools.clear()
