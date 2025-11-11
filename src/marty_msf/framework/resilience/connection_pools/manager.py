"""
Unified Connection Pool Manager

Provides centralized management for all connection pools with
monitoring, configuration, and lifecycle management.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union

from marty_msf.core.di_container import (
    get_service,
    get_service_optional,
    register_instance,
)

from .http_pool import HTTPConnectionPool, HTTPPoolConfig
from .redis_pool import RedisConnectionPool, RedisPoolConfig

logger = logging.getLogger(__name__)


class PoolType(Enum):
    """Types of connection pools"""

    HTTP = "http"
    REDIS = "redis"
    DATABASE = "database"  # Handled by existing database manager
    CUSTOM = "custom"


@dataclass
class PoolConfig:
    """Unified pool configuration"""

    name: str
    pool_type: PoolType
    enabled: bool = True

    # Type-specific configs
    http_config: HTTPPoolConfig | None = None
    redis_config: RedisPoolConfig | None = None

    # Common settings
    max_connections: int = 10
    health_check_interval: float = 60.0
    enable_metrics: bool = True
    tags: dict[str, str] = field(default_factory=dict)


class ConnectionPoolManager:
    """Centralized manager for all connection pools"""

    def __init__(self):
        self._pools: dict[str, HTTPConnectionPool | RedisConnectionPool] = {}
        self._configs: dict[str, PoolConfig] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._monitoring_task: asyncio.Task | None = None

        # Global metrics
        self.total_pools_created = 0
        self.total_pools_destroyed = 0
        self.monitoring_enabled = True

    async def initialize(self, configs: list[PoolConfig]):
        """Initialize the pool manager with configurations"""
        async with self._lock:
            if self._initialized:
                logger.warning("Pool manager already initialized")
                return

            for config in configs:
                if config.enabled:
                    await self._create_pool(config)

            self._initialized = True

            if self.monitoring_enabled:
                self._start_monitoring()

            logger.info("Connection pool manager initialized with %d pools", len(self._pools))

    async def _create_pool(self, config: PoolConfig):
        """Create a specific type of pool"""
        try:
            if config.pool_type == PoolType.HTTP:
                if config.http_config is None:
                    config.http_config = HTTPPoolConfig(
                        name=config.name,
                        max_connections=config.max_connections,
                        health_check_interval=config.health_check_interval,
                        enable_metrics=config.enable_metrics,
                    )
                pool = HTTPConnectionPool(config.http_config)

            elif config.pool_type == PoolType.REDIS:
                if config.redis_config is None:
                    config.redis_config = RedisPoolConfig(
                        name=config.name,
                        max_connections=config.max_connections,
                        health_check_interval=config.health_check_interval,
                        enable_metrics=config.enable_metrics,
                    )
                pool = RedisConnectionPool(config.redis_config)

            else:
                raise ValueError(f"Unsupported pool type: {config.pool_type}")

            self._pools[config.name] = pool
            self._configs[config.name] = config
            self.total_pools_created += 1

            logger.info("Created %s pool '%s'", config.pool_type.value, config.name)

        except Exception as e:
            logger.error("Failed to create pool '%s': %s", config.name, e)
            raise

    async def get_pool(self, name: str) -> HTTPConnectionPool | RedisConnectionPool:
        """Get a pool by name"""
        if not self._initialized:
            raise RuntimeError("Pool manager not initialized")

        pool = self._pools.get(name)
        if pool is None:
            raise KeyError(f"Pool '{name}' not found")

        return pool

    async def get_http_pool(self, name: str = "default") -> HTTPConnectionPool:
        """Get an HTTP pool by name"""
        pool = await self.get_pool(name)
        if not isinstance(pool, HTTPConnectionPool):
            raise TypeError(f"Pool '{name}' is not an HTTP pool")
        return pool

    async def get_redis_pool(self, name: str = "default") -> RedisConnectionPool:
        """Get a Redis pool by name"""
        pool = await self.get_pool(name)
        if not isinstance(pool, RedisConnectionPool):
            raise TypeError(f"Pool '{name}' is not a Redis pool")
        return pool

    async def add_pool(self, config: PoolConfig):
        """Add a new pool dynamically"""
        async with self._lock:
            if config.name in self._pools:
                raise ValueError(f"Pool '{config.name}' already exists")

            if config.enabled:
                await self._create_pool(config)

    async def remove_pool(self, name: str):
        """Remove and close a pool"""
        async with self._lock:
            pool = self._pools.get(name)
            if pool is None:
                logger.warning("Pool '%s' not found for removal", name)
                return

            await pool.close()
            del self._pools[name]
            del self._configs[name]
            self.total_pools_destroyed += 1

            logger.info("Removed pool '%s'", name)

    def list_pools(self) -> list[dict[str, Any]]:
        """List all pools with basic information"""
        pools_info = []

        for name, config in self._configs.items():
            pool = self._pools.get(name)
            pool_info = {
                "name": name,
                "type": config.pool_type.value,
                "enabled": config.enabled,
                "tags": config.tags,
                "status": "active" if pool else "inactive",
            }

            if pool and hasattr(pool, "get_metrics"):
                pool_info.update(pool.get_metrics())

            pools_info.append(pool_info)

        return pools_info

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics for all pools"""
        metrics = {
            "manager": {
                "initialized": self._initialized,
                "total_pools": len(self._pools),
                "total_pools_created": self.total_pools_created,
                "total_pools_destroyed": self.total_pools_destroyed,
                "monitoring_enabled": self.monitoring_enabled,
            },
            "pools": {},
        }

        for name, pool in self._pools.items():
            if hasattr(pool, "get_metrics"):
                metrics["pools"][name] = pool.get_metrics()

        return metrics

    def _start_monitoring(self):
        """Start background monitoring task"""
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._initialized and self.monitoring_enabled:
            try:
                await asyncio.sleep(60)  # Monitor every minute
                await self._collect_metrics()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Pool monitoring error: %s", e)

    async def _collect_metrics(self):
        """Collect and log metrics from all pools"""
        try:
            metrics = self.get_metrics()

            # Log summary metrics
            total_connections = sum(
                pool.get("total_connections", 0) for pool in metrics["pools"].values()
            )
            logger.info(
                "Pool Manager Metrics: %d pools, %d total connections",
                metrics["manager"]["total_pools"],
                total_connections,
            )

            # Check for any unhealthy pools
            for pool_name, pool_metrics in metrics["pools"].items():
                error_rate = pool_metrics.get("error_rate", 0)
                if error_rate > 0.1:  # More than 10% error rate
                    logger.warning(
                        "High error rate in pool '%s': %.2f%%", pool_name, error_rate * 100
                    )

                active_connections = pool_metrics.get("active_connections", 0)
                max_connections = pool_metrics.get("max_connections", 1)
                utilization = active_connections / max_connections

                if utilization > 0.9:  # More than 90% utilization
                    logger.warning(
                        "High utilization in pool '%s': %.2f%%", pool_name, utilization * 100
                    )

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.error("Error collecting pool metrics: %s", e)

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on all pools"""
        results = {
            "manager_status": "healthy" if self._initialized else "unhealthy",
            "pools": {},
            "overall_status": "healthy",
        }

        unhealthy_count = 0

        for name, pool in self._pools.items():
            try:
                if hasattr(pool, "get_metrics"):
                    metrics = pool.get_metrics()
                    error_rate = metrics.get("error_rate", 0)
                    active_connections = metrics.get("active_connections", 0)

                    if error_rate > 0.5 or active_connections == 0:
                        status = "unhealthy"
                        unhealthy_count += 1
                    else:
                        status = "healthy"

                    results["pools"][name] = {
                        "status": status,
                        "error_rate": error_rate,
                        "active_connections": active_connections,
                    }
                else:
                    results["pools"][name] = {"status": "unknown"}

            except (AttributeError, KeyError, TypeError, ValueError) as e:
                results["pools"][name] = {"status": "error", "error": str(e)}
                unhealthy_count += 1

        if unhealthy_count > 0:
            results["overall_status"] = (
                "degraded" if unhealthy_count < len(self._pools) else "unhealthy"
            )

        return results

    async def close(self):
        """Close all pools and shut down the manager"""
        async with self._lock:
            if not self._initialized:
                return

            # Stop monitoring
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass

            # Close all pools
            for name, pool in list(self._pools.items()):
                try:
                    await pool.close()
                except (AttributeError, RuntimeError, OSError) as e:
                    logger.error("Error closing pool '%s': %s", name, e)

            self._pools.clear()
            self._configs.clear()
            self._initialized = False

            logger.info("Connection pool manager closed")


# DI Container integration functions


def get_pool_manager() -> ConnectionPoolManager:
    """Get the pool manager instance from DI container"""
    manager = get_service_optional(ConnectionPoolManager)
    if manager is None:
        manager = ConnectionPoolManager()
        register_instance(ConnectionPoolManager, manager)
    return manager


async def initialize_pools(configs: list[PoolConfig]):
    """Initialize the pool manager with configurations"""
    manager = get_pool_manager()
    await manager.initialize(configs)


async def get_pool(name: str) -> HTTPConnectionPool | RedisConnectionPool:
    """Get a pool by name from the manager"""
    manager = get_pool_manager()
    return await manager.get_pool(name)


async def close_all_pools() -> None:
    """Close all pools and shut down the manager"""
    manager = get_service_optional(ConnectionPoolManager)
    if manager:
        await manager.close()


def register_pool_manager(manager: ConnectionPoolManager):
    """Register a pool manager instance in the DI container"""
    register_instance(ConnectionPoolManager, manager)
