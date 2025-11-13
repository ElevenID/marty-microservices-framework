"""
External Dependency Resilience Utilities

Provides high-level utilities for applying resilience patterns
specifically to external dependencies like databases, APIs, caches, etc.
"""

import asyncio
import builtins
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from .bulkhead import (
    CACHE_CONFIG,
    DATABASE_CONFIG,
    EXTERNAL_API_CONFIG,
    FILE_SYSTEM_CONFIG,
    MESSAGE_QUEUE_CONFIG,
    BulkheadConfig,
    BulkheadPool,
    get_bulkhead_manager,
)
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .timeout import TimeoutConfig, TimeoutManager

T = TypeVar("T")
logger = logging.getLogger(__name__)


class DependencyType(Enum):
    """Types of external dependencies."""

    DATABASE = "database"
    EXTERNAL_API = "external_api"
    CACHE = "cache"
    MESSAGE_QUEUE = "message_queue"
    FILE_SYSTEM = "file_system"
    CPU_INTENSIVE = "cpu_intensive"
    MEMORY_INTENSIVE = "memory_intensive"


@dataclass
class ExternalDependencyConfig:
    """Configuration for external dependency resilience."""

    dependency_name: str
    dependency_type: DependencyType
    bulkhead_config: BulkheadConfig | None = None
    timeout_config: TimeoutConfig | None = None
    circuit_breaker_config: CircuitBreakerConfig | None = None
    enable_metrics: bool = True


class ExternalDependencyManager:
    """Manages resilience patterns for external dependencies."""

    def __init__(self):
        self._bulkhead_manager = get_bulkhead_manager()
        self._timeout_manager = TimeoutManager()
        self._circuit_breakers: builtins.dict[str, CircuitBreaker] = {}
        self._dependency_configs: builtins.dict[str, ExternalDependencyConfig] = {}

    def register_dependency(self, config: ExternalDependencyConfig):
        """Register an external dependency with resilience patterns."""
        logger.info(
            "Registering external dependency: %s (type: %s)",
            config.dependency_name,
            config.dependency_type.value,
        )

        # Get default configuration based on dependency type
        bulkhead_config = config.bulkhead_config or self._get_default_bulkhead_config(
            config.dependency_type
        )

        # Create bulkhead
        self._bulkhead_manager.create_bulkhead(config.dependency_name, bulkhead_config)

        # Create circuit breaker if enabled
        if bulkhead_config.enable_circuit_breaker:
            cb_config = config.circuit_breaker_config or CircuitBreakerConfig(
                failure_threshold=bulkhead_config.circuit_breaker_failure_threshold,
                timeout_seconds=bulkhead_config.circuit_breaker_timeout,
            )
            self._circuit_breakers[config.dependency_name] = CircuitBreaker(
                config.dependency_name, cb_config
            )

        self._dependency_configs[config.dependency_name] = config

    def _get_default_bulkhead_config(self, dependency_type: DependencyType) -> BulkheadConfig:
        """Get default bulkhead configuration for dependency type."""
        config_map = {
            DependencyType.DATABASE: DATABASE_CONFIG,
            DependencyType.EXTERNAL_API: EXTERNAL_API_CONFIG,
            DependencyType.CACHE: CACHE_CONFIG,
            DependencyType.MESSAGE_QUEUE: MESSAGE_QUEUE_CONFIG,
            DependencyType.FILE_SYSTEM: FILE_SYSTEM_CONFIG,
        }
        return config_map.get(dependency_type, DATABASE_CONFIG)

    def _get_default_timeout_config(self, dependency_type: DependencyType) -> TimeoutConfig:
        """Get default timeout configuration for dependency type."""
        timeout_map = {
            DependencyType.DATABASE: 10.0,
            DependencyType.EXTERNAL_API: 15.0,
            DependencyType.CACHE: 2.0,
            DependencyType.MESSAGE_QUEUE: 5.0,
            DependencyType.FILE_SYSTEM: 30.0,
            DependencyType.CPU_INTENSIVE: 60.0,
            DependencyType.MEMORY_INTENSIVE: 120.0,
        }

        timeout = timeout_map.get(dependency_type, 30.0)
        config = TimeoutConfig(default_timeout=timeout)

        # Set specific timeout based on dependency type
        if dependency_type == DependencyType.DATABASE:
            config.database_timeout = timeout
        elif dependency_type == DependencyType.EXTERNAL_API:
            config.api_call_timeout = timeout
        elif dependency_type == DependencyType.CACHE:
            config.cache_timeout = timeout
        elif dependency_type == DependencyType.MESSAGE_QUEUE:
            config.message_queue_timeout = timeout

        return config

    async def execute_with_resilience(
        self,
        dependency_name: str,
        func: Callable[..., T],
        operation_name: str = "operation",
        *args,
        **kwargs,
    ) -> T:
        """Execute function with comprehensive resilience patterns for the dependency."""
        if dependency_name not in self._dependency_configs:
            raise ValueError(f"Dependency '{dependency_name}' not registered")

        config = self._dependency_configs[dependency_name]
        bulkhead = self._bulkhead_manager.get_bulkhead(dependency_name)
        circuit_breaker = self._circuit_breakers.get(dependency_name)

        if not bulkhead:
            raise ValueError(f"Bulkhead for dependency '{dependency_name}' not found")

        # Wrap function with circuit breaker if available
        async def protected_func():
            if circuit_breaker:
                return await circuit_breaker.call(func, *args, **kwargs)
            else:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, func, *args, **kwargs)

        # Execute with bulkhead isolation and timeout
        operation = f"{dependency_name}_{operation_name}"

        # Apply dependency-specific timeout
        if config.dependency_type == DependencyType.DATABASE:
            return await self._timeout_manager.execute_database_call(
                lambda: bulkhead.execute_async(protected_func), operation
            )
        elif config.dependency_type == DependencyType.EXTERNAL_API:
            return await self._timeout_manager.execute_api_call(
                lambda: bulkhead.execute_async(protected_func), operation
            )
        elif config.dependency_type == DependencyType.CACHE:
            return await self._timeout_manager.execute_cache_call(
                lambda: bulkhead.execute_async(protected_func), operation
            )
        elif config.dependency_type == DependencyType.MESSAGE_QUEUE:
            return await self._timeout_manager.execute_message_queue_call(
                lambda: bulkhead.execute_async(protected_func), operation
            )
        else:
            return await self._timeout_manager.execute_with_timeout(
                lambda: bulkhead.execute_async(protected_func), operation=operation
            )

    def get_dependency_stats(self, dependency_name: str) -> builtins.dict[str, Any]:
        """Get comprehensive statistics for a dependency."""
        if dependency_name not in self._dependency_configs:
            raise ValueError(f"Dependency '{dependency_name}' not registered")

        stats = {}

        # Bulkhead stats
        bulkhead = self._bulkhead_manager.get_bulkhead(dependency_name)
        if bulkhead:
            stats["bulkhead"] = bulkhead.get_stats()

        # Circuit breaker stats
        circuit_breaker = self._circuit_breakers.get(dependency_name)
        if circuit_breaker:
            stats["circuit_breaker"] = circuit_breaker.get_stats()

        return stats

    def get_all_dependencies_stats(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get statistics for all registered dependencies."""
        return {name: self.get_dependency_stats(name) for name in self._dependency_configs.keys()}


# Global external dependency manager
_external_dependency_manager = ExternalDependencyManager()


def get_external_dependency_manager() -> ExternalDependencyManager:
    """Get the global external dependency manager."""
    return _external_dependency_manager


def register_database_dependency(
    name: str,
    max_concurrent: int = 10,
    timeout_seconds: float = 10.0,
    enable_circuit_breaker: bool = True,
) -> None:
    """Register a database dependency with default configuration."""
    config = ExternalDependencyConfig(
        dependency_name=name,
        dependency_type=DependencyType.DATABASE,
        bulkhead_config=BulkheadConfig(
            max_concurrent=max_concurrent,
            timeout_seconds=timeout_seconds,
            dependency_type="database",
            enable_circuit_breaker=enable_circuit_breaker,
        ),
    )
    _external_dependency_manager.register_dependency(config)


def register_api_dependency(
    name: str,
    max_concurrent: int = 15,
    timeout_seconds: float = 15.0,
    enable_circuit_breaker: bool = True,
) -> None:
    """Register an external API dependency with default configuration."""
    config = ExternalDependencyConfig(
        dependency_name=name,
        dependency_type=DependencyType.EXTERNAL_API,
        bulkhead_config=BulkheadConfig(
            max_concurrent=max_concurrent,
            timeout_seconds=timeout_seconds,
            dependency_type="api",
            enable_circuit_breaker=enable_circuit_breaker,
            circuit_breaker_failure_threshold=3,
        ),
    )
    _external_dependency_manager.register_dependency(config)


def register_cache_dependency(
    name: str,
    max_concurrent: int = 50,
    timeout_seconds: float = 2.0,
    enable_circuit_breaker: bool = False,
) -> None:
    """Register a cache dependency with default configuration."""
    config = ExternalDependencyConfig(
        dependency_name=name,
        dependency_type=DependencyType.CACHE,
        bulkhead_config=BulkheadConfig(
            max_concurrent=max_concurrent,
            timeout_seconds=timeout_seconds,
            dependency_type="cache",
            enable_circuit_breaker=enable_circuit_breaker,
        ),
    )
    _external_dependency_manager.register_dependency(config)


# Convenience decorators for external dependencies
def database_call(dependency_name: str, operation_name: str = "db_operation"):
    """Decorator for database operations."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            return await _external_dependency_manager.execute_with_resilience(
                dependency_name, func, operation_name, *args, **kwargs
            )

        return wrapper

    return decorator


def api_call(dependency_name: str, operation_name: str = "api_operation"):
    """Decorator for external API operations."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            return await _external_dependency_manager.execute_with_resilience(
                dependency_name, func, operation_name, *args, **kwargs
            )

        return wrapper

    return decorator


def cache_call(dependency_name: str, operation_name: str = "cache_operation"):
    """Decorator for cache operations."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            return await _external_dependency_manager.execute_with_resilience(
                dependency_name, func, operation_name, *args, **kwargs
            )

        return wrapper

    return decorator
