"""
HTTP Connection Pool Implementation

Provides standardized HTTP connection pooling with health checking,
metrics, retry policies, and integration with the resilience framework.
"""

import asyncio
import logging
import ssl
import time
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class HTTPPoolConfig:
    """HTTP connection pool configuration"""

    # Pool sizing
    max_connections: int = 100
    max_connections_per_host: int = 30
    min_connections: int = 5

    # Timeouts
    connect_timeout: float = 10.0
    request_timeout: float = 30.0
    total_timeout: float = 60.0
    sock_read_timeout: float = 30.0

    # Health and lifecycle
    max_idle_time: float = 300.0  # 5 minutes
    health_check_interval: float = 60.0  # 1 minute
    connection_ttl: float = 3600.0  # 1 hour

    # Retry behavior
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0

    # SSL/TLS
    verify_ssl: bool = True
    ssl_context: ssl.SSLContext | None = None

    # Headers and behavior
    default_headers: dict[str, str] = field(default_factory=dict)
    enable_compression: bool = True
    follow_redirects: bool = True
    max_redirects: int = 10

    # Metrics and monitoring
    enable_metrics: bool = True
    enable_tracing: bool = True

    name: str = "default"


class HTTPPooledConnection:
    """Wrapper for HTTP connection with metadata and lifecycle management"""

    def __init__(self, session: aiohttp.ClientSession, pool: "HTTPConnectionPool"):
        self.session = session
        self.pool = pool
        self.created_at = time.time()
        self.last_used = time.time()
        self.request_count = 0
        self.error_count = 0
        self.in_use = False
        self._closed = False

    async def __aenter__(self):
        self.last_used = time.time()
        self.in_use = True
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.in_use = False
        if exc_type is not None:
            self.error_count += 1
        else:
            self.request_count += 1
        await self.pool._return_connection(self)

    @property
    def idle_time(self) -> float:
        """Time since last use"""
        return time.time() - self.last_used

    @property
    def age(self) -> float:
        """Age of connection"""
        return time.time() - self.created_at

    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy"""
        return (
            not self._closed
            and not self.session.closed
            and self.idle_time < self.pool.config.max_idle_time
            and self.age < self.pool.config.connection_ttl
        )

    async def close(self):
        """Close the connection"""
        if not self._closed:
            self._closed = True
            if not self.session.closed:
                await self.session.close()


class HTTPConnectionPool:
    """HTTP connection pool with health checking and metrics"""

    def __init__(self, config: HTTPPoolConfig):
        self.config = config
        self._connections: set[HTTPPooledConnection] = set()
        self._available: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._closed = False

        # Metrics
        self.total_connections_created = 0
        self.total_connections_destroyed = 0
        self.total_requests = 0
        self.total_errors = 0
        self.active_connections = 0

        # Health checker task
        self._health_check_task: asyncio.Task | None = None
        self._start_health_checker()

    async def acquire(self) -> AbstractAsyncContextManager[aiohttp.ClientSession]:
        """Acquire a connection from the pool"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        connection = await self._get_connection()
        return connection

    async def _get_connection(self) -> HTTPPooledConnection:
        """Get or create a connection"""
        async with self._lock:
            # Try to get an available connection
            while not self._available.empty():
                try:
                    connection = self._available.get_nowait()
                    if connection.is_healthy:
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

    async def _create_connection(self) -> HTTPPooledConnection:
        """Create a new HTTP connection"""
        try:
            # Configure SSL context
            ssl_setting = self.config.ssl_context
            if ssl_setting is None and self.config.verify_ssl:
                ssl_setting = ssl.create_default_context()
            elif not self.config.verify_ssl:
                ssl_setting = False

            # Configure connector
            connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                limit_per_host=self.config.max_connections_per_host,
                ttl_dns_cache=300,
                use_dns_cache=True,
                ssl=ssl_setting if ssl_setting is not None else True,
                enable_cleanup_closed=True,
                force_close=True,
                keepalive_timeout=self.config.max_idle_time,
            )

            # Configure timeout
            timeout = aiohttp.ClientTimeout(
                total=self.config.total_timeout,
                connect=self.config.connect_timeout,
                sock_read=self.config.sock_read_timeout,
            )

            # Create session
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.config.default_headers,
                auto_decompress=self.config.enable_compression,
                raise_for_status=False,
                skip_auto_headers={"User-Agent"},
            )

            connection = HTTPPooledConnection(session, self)
            self._connections.add(connection)
            self.total_connections_created += 1
            self.active_connections += 1

            logger.debug(f"Created new HTTP connection in pool '{self.config.name}'")
            return connection

        except Exception as e:
            logger.error(f"Failed to create HTTP connection: {e}")
            raise

    async def _wait_for_connection(self) -> HTTPPooledConnection:
        """Wait for a connection to become available"""
        # In a real implementation, you'd want a more sophisticated
        # waiting mechanism with timeouts
        await asyncio.sleep(0.1)
        return await self._get_connection()

    async def _return_connection(self, connection: HTTPPooledConnection):
        """Return a connection to the pool"""
        async with self._lock:
            if connection in self._connections and connection.is_healthy:
                try:
                    self._available.put_nowait(connection)
                except asyncio.QueueFull:
                    await self._destroy_connection(connection)
            else:
                await self._destroy_connection(connection)

    async def _destroy_connection(self, connection: HTTPPooledConnection):
        """Destroy a connection"""
        try:
            if connection in self._connections:
                self._connections.remove(connection)
                self.active_connections -= 1

            await connection.close()
            self.total_connections_destroyed += 1

            logger.debug(f"Destroyed HTTP connection in pool '{self.config.name}'")

        except Exception as e:
            logger.warning(f"Error destroying HTTP connection: {e}")

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
                logger.error(f"Health check error: {e}")

    async def _health_check_connections(self):
        """Check health of all connections"""
        async with self._lock:
            unhealthy_connections = []

            for connection in list(self._connections):
                if not connection.in_use and not connection.is_healthy:
                    unhealthy_connections.append(connection)

            for connection in unhealthy_connections:
                await self._destroy_connection(connection)

    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make an HTTP request using the pool"""
        retries = 0
        last_exception: Exception | None = None

        while retries <= self.config.max_retries:
            try:
                connection = await self.acquire()
                async with connection as session:
                    self.total_requests += 1
                    response = await session.request(method, url, **kwargs)
                    return response

            except Exception as e:
                last_exception = e
                self.total_errors += 1
                retries += 1

                if retries <= self.config.max_retries:
                    delay = self.config.retry_delay * (
                        self.config.retry_backoff_factor ** (retries - 1)
                    )
                    await asyncio.sleep(delay)
                    logger.warning(f"HTTP request failed, retrying in {delay}s: {e}")

        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("Request failed with no exception captured")

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make GET request"""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make POST request"""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make PUT request"""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make DELETE request"""
        return await self.request("DELETE", url, **kwargs)

    def get_metrics(self) -> dict[str, Any]:
        """Get pool metrics"""
        return {
            "pool_name": self.config.name,
            "total_connections": len(self._connections),
            "active_connections": self.active_connections,
            "available_connections": self._available.qsize(),
            "total_connections_created": self.total_connections_created,
            "total_connections_destroyed": self.total_connections_destroyed,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": self.total_errors / max(self.total_requests, 1),
            "max_connections": self.config.max_connections,
            "max_connections_per_host": self.config.max_connections_per_host,
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

        logger.info(f"HTTP connection pool '{self.config.name}' closed")


# Global HTTP pools registry
_http_pools: dict[str, HTTPConnectionPool] = {}
_pools_lock = asyncio.Lock()


async def get_http_pool(
    name: str = "default", config: HTTPPoolConfig | None = None
) -> HTTPConnectionPool:
    """Get or create an HTTP connection pool"""
    async with _pools_lock:
        if name not in _http_pools:
            if config is None:
                config = HTTPPoolConfig(name=name)
            _http_pools[name] = HTTPConnectionPool(config)
        return _http_pools[name]


async def close_all_http_pools():
    """Close all HTTP connection pools"""
    async with _pools_lock:
        for pool in list(_http_pools.values()):
            await pool.close()
        _http_pools.clear()
