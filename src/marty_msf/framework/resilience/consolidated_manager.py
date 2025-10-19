"""
Consolidated Resilience Manager

A unified resilience manager that automatically applies circuit breakers,
retries, and timeouts to internal client calls. This replaces fragmented
implementations with a single, comprehensive solution.
"""

import asyncio
import copy
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from marty_msf.core.enhanced_di import get_service

from .bulkhead import BulkheadConfig, BulkheadError, SemaphoreBulkhead
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerError
from .enhanced.advanced_retry import (
    AdvancedRetryConfig,
    async_retry_with_advanced_policy,
)
from .resilience_manager_service import ResilienceManagerService
from .timeout import TimeoutConfig, with_sync_timeout, with_timeout

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResilienceStrategy(Enum):
    """Resilience strategy for different call types."""
    INTERNAL_SERVICE = "internal_service"  # Internal microservice calls
    EXTERNAL_SERVICE = "external_service"  # External API calls
    DATABASE = "database"  # Database operations
    CACHE = "cache"  # Cache operations
    CUSTOM = "custom"  # Custom configuration


@dataclass
class ConsolidatedResilienceConfig:
    """Unified configuration for all resilience patterns."""

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    circuit_breaker_success_threshold: int = 3

    # Retry settings
    retry_enabled: bool = True
    retry_max_attempts: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0
    retry_exponential_base: float = 2.0
    retry_jitter: bool = True

    # Timeout settings
    timeout_enabled: bool = True
    timeout_seconds: float = 30.0

    # Bulkhead settings
    bulkhead_enabled: bool = False
    bulkhead_max_concurrent: int = 100
    bulkhead_timeout: float = 30.0

    # Strategy-specific overrides
    strategy_overrides: dict[ResilienceStrategy, dict[str, Any]] = field(default_factory=dict)

    # Exception handling
    retry_exceptions: tuple = (Exception,)
    circuit_breaker_exceptions: tuple = (Exception,)
    ignore_exceptions: tuple = (KeyboardInterrupt, SystemExit)

    def get_strategy_config(self, strategy: ResilienceStrategy) -> "ConsolidatedResilienceConfig":
        """Get configuration for a specific strategy."""
        if strategy not in self.strategy_overrides:
            return self

        # Create a copy with strategy-specific overrides
        config = copy.deepcopy(self)
        overrides = self.strategy_overrides[strategy]

        for key, value in overrides.items():
            if hasattr(config, key):
                setattr(config, key, value)

        return config


class ConsolidatedResilienceManager:
    """
    Unified resilience manager that automatically applies circuit breakers,
    retries, and timeouts to internal client calls.

    This consolidates all fragmented resilience implementations into a
    single, cohesive solution.
    """

    def __init__(self, config: ConsolidatedResilienceConfig | None = None, service_config: dict[str, Any] | None = None):
        # Load from service configuration if provided
        if service_config and not config:
            config = self._load_from_service_config(service_config)

        self.config = config or ConsolidatedResilienceConfig()
        self.service_config = service_config

        # Circuit breakers by name
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # Bulkheads by name
        self._bulkheads: dict[str, SemaphoreBulkhead] = {}

        # Metrics
        self._metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "circuit_breaker_opens": 0,
            "retries_executed": 0,
            "timeouts": 0,
            "bulkhead_rejections": 0
        }

        logger.info("Consolidated resilience manager initialized")

    def _load_from_service_config(self, service_config: dict[str, Any]) -> ConsolidatedResilienceConfig:
        """Load resilience configuration from service configuration."""
        resilience_config = service_config.get("resilience", {})

        return ConsolidatedResilienceConfig(
            # Circuit breaker settings
            circuit_breaker_enabled=resilience_config.get("circuit_breaker_enabled", True),
            circuit_breaker_failure_threshold=resilience_config.get("circuit_breaker_failure_threshold", 5),
            circuit_breaker_recovery_timeout=resilience_config.get("circuit_breaker_recovery_timeout", 60.0),

            # Retry settings
            retry_enabled=resilience_config.get("retry_enabled", True),
            retry_max_attempts=resilience_config.get("retry_max_attempts", 3),
            retry_base_delay=resilience_config.get("retry_base_delay", 1.0),
            retry_exponential_base=resilience_config.get("retry_exponential_base", 2.0),

            # Timeout settings
            timeout_enabled=resilience_config.get("timeout_enabled", True),
            timeout_seconds=resilience_config.get("timeout_seconds", 30.0),

            # Bulkhead settings
            bulkhead_enabled=resilience_config.get("bulkhead_enabled", False),
            bulkhead_max_concurrent=resilience_config.get("bulkhead_max_concurrent", 100),
        )

    def get_or_create_circuit_breaker(self, name: str, config: ConsolidatedResilienceConfig | None = None) -> CircuitBreaker:
        """Get or create a circuit breaker for the given name."""
        if name not in self._circuit_breakers:
            effective_config = config or self.config
            cb_config = CircuitBreakerConfig(
                failure_threshold=effective_config.circuit_breaker_failure_threshold,
                success_threshold=effective_config.circuit_breaker_success_threshold,
                timeout_seconds=int(effective_config.circuit_breaker_recovery_timeout),
                failure_exceptions=effective_config.circuit_breaker_exceptions,
                ignore_exceptions=effective_config.ignore_exceptions
            )
            self._circuit_breakers[name] = CircuitBreaker(name, cb_config)

        return self._circuit_breakers[name]

    def get_or_create_bulkhead(self, name: str, config: ConsolidatedResilienceConfig | None = None) -> SemaphoreBulkhead:
        """Get or create a bulkhead for the given name."""
        if name not in self._bulkheads:
            effective_config = config or self.config
            bulkhead_config = BulkheadConfig(
                max_concurrent=effective_config.bulkhead_max_concurrent,
                timeout_seconds=effective_config.bulkhead_timeout
            )
            self._bulkheads[name] = SemaphoreBulkhead(name, bulkhead_config)

        return self._bulkheads[name]

    async def execute_resilient(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        name: str = "default",
        strategy: ResilienceStrategy = ResilienceStrategy.INTERNAL_SERVICE,
        config_override: ConsolidatedResilienceConfig | None = None,
        **kwargs
    ) -> T:
        """
        Execute an async function with comprehensive resilience patterns.

        Args:
            func: The async function to execute
            *args: Arguments to pass to the function
            name: Unique name for circuit breaker/bulkhead identification
            strategy: Resilience strategy to use
            config_override: Optional configuration override
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the function execution

        Raises:
            CircuitBreakerError: When circuit breaker is open
            BulkheadError: When bulkhead capacity is exceeded
            TimeoutError: When operation times out
            Exception: The original exception if all retries fail
        """
        # Get effective configuration
        effective_config = config_override or self.config.get_strategy_config(strategy)

        self._metrics["total_calls"] += 1

        # Define the execution chain
        async def execute_with_patterns() -> T:
            async def base_execution():
                return await func(*args, **kwargs)

            execution_func = base_execution

            # Apply timeout if enabled
            if effective_config.timeout_enabled:
                async def timeout_execution():
                    try:
                        return await with_timeout(
                            execution_func,
                            timeout_seconds=effective_config.timeout_seconds,
                            operation=name
                        )
                    except asyncio.TimeoutError:
                        self._metrics["timeouts"] += 1
                        raise

                execution_func = timeout_execution

            # Apply circuit breaker if enabled
            if effective_config.circuit_breaker_enabled:
                circuit_breaker = self.get_or_create_circuit_breaker(name, effective_config)

                async def circuit_breaker_execution():
                    try:
                        return await circuit_breaker.call(execution_func)
                    except CircuitBreakerError:
                        self._metrics["circuit_breaker_opens"] += 1
                        raise

                execution_func = circuit_breaker_execution

            # Apply bulkhead if enabled
            if effective_config.bulkhead_enabled:
                bulkhead = self.get_or_create_bulkhead(name, effective_config)

                async def bulkhead_execution():
                    try:
                        return await bulkhead.execute_async(execution_func)
                    except BulkheadError:
                        self._metrics["bulkhead_rejections"] += 1
                        raise

                execution_func = bulkhead_execution

            return await execution_func()

        # Apply retry if enabled
        if effective_config.retry_enabled:
            retry_config = AdvancedRetryConfig(
                max_attempts=effective_config.retry_max_attempts,
                base_delay=effective_config.retry_base_delay,
                max_delay=effective_config.retry_max_delay,
                backoff_multiplier=effective_config.retry_exponential_base,
                jitter=effective_config.retry_jitter,
                retryable_exceptions=effective_config.retry_exceptions,
                non_retryable_exceptions=effective_config.ignore_exceptions
            )

            result = await async_retry_with_advanced_policy(execute_with_patterns, config=retry_config)

            if result.success:
                self._metrics["successful_calls"] += 1
                return result.result
            else:
                self._metrics["failed_calls"] += 1
                self._metrics["retries_executed"] += result.attempts - 1

                if result.last_exception:
                    raise result.last_exception
                else:
                    raise RuntimeError("Operation failed without specific exception")
        else:
            try:
                result = await execute_with_patterns()
                self._metrics["successful_calls"] += 1
                return result
            except Exception:
                self._metrics["failed_calls"] += 1
                raise

    def execute_resilient_sync(
        self,
        func: Callable[..., T],
        *args,
        name: str = "default",
        strategy: ResilienceStrategy = ResilienceStrategy.INTERNAL_SERVICE,
        config_override: ConsolidatedResilienceConfig | None = None,
        **kwargs
    ) -> T:
        """
        Execute a sync function with comprehensive resilience patterns.

        Args:
            func: The sync function to execute
            *args: Arguments to pass to the function
            name: Unique name for circuit breaker identification
            strategy: Resilience strategy to use
            config_override: Optional configuration override
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the function execution
        """
        # Get effective configuration
        effective_config = config_override or self.config.get_strategy_config(strategy)

        self._metrics["total_calls"] += 1

        def execute_with_patterns() -> T:
            def execution_func():
                return func(*args, **kwargs)

            # Apply timeout if enabled
            if effective_config.timeout_enabled:
                def timeout_execution():
                    try:
                        return with_sync_timeout(
                            execution_func,
                            timeout_seconds=effective_config.timeout_seconds,
                            operation=name
                        )
                    except TimeoutError:
                        self._metrics["timeouts"] += 1
                        raise

                execution_func = timeout_execution

            # Apply circuit breaker if enabled
            if effective_config.circuit_breaker_enabled:
                circuit_breaker = self.get_or_create_circuit_breaker(name, effective_config)

                def circuit_breaker_execution():
                    try:
                        return circuit_breaker.call(execution_func)
                    except CircuitBreakerError:
                        self._metrics["circuit_breaker_opens"] += 1
                        raise

                execution_func = circuit_breaker_execution

            return execution_func()

        # Note: Bulkhead and retry for sync functions would require threading
        # For now, we apply timeout and circuit breaker only

        try:
            result = execute_with_patterns()
            self._metrics["successful_calls"] += 1
            return result
        except Exception:
            self._metrics["failed_calls"] += 1
            raise

    def resilient_call(
        self,
        name: str = "default",
        strategy: ResilienceStrategy = ResilienceStrategy.INTERNAL_SERVICE,
        config_override: ConsolidatedResilienceConfig | None = None,
    ):
        """
        Decorator for applying resilience patterns to functions.

        Usage:
            @manager.resilient_call(name="user_service", strategy=ResilienceStrategy.INTERNAL_SERVICE)
            async def get_user(user_id: str):
                # Your function implementation
                pass
        """
        def decorator(func: Callable):
            if asyncio.iscoroutinefunction(func):
                @wraps(func)
                async def async_wrapper(*args, **kwargs):
                    return await self.execute_resilient(
                        func, *args,
                        name=name,
                        strategy=strategy,
                        config_override=config_override,
                        **kwargs
                    )
                return async_wrapper
            else:
                @wraps(func)
                def sync_wrapper(*args, **kwargs):
                    return self.execute_resilient_sync(
                        func, *args,
                        name=name,
                        strategy=strategy,
                        config_override=config_override,
                        **kwargs
                    )
                return sync_wrapper

        return decorator

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive resilience metrics."""
        circuit_breaker_metrics = {}
        for name, cb in self._circuit_breakers.items():
            circuit_breaker_metrics[name] = {
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "success_count": cb.success_count,
                "failure_rate": cb.failure_rate
            }

        bulkhead_metrics = {}
        for name, bulkhead in self._bulkheads.items():
            stats = bulkhead.get_stats()
            bulkhead_metrics[name] = stats

        return {
            "overall": self._metrics.copy(),
            "circuit_breakers": circuit_breaker_metrics,
            "bulkheads": bulkhead_metrics
        }

    def reset_metrics(self):
        """Reset all metrics."""
        self._metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "circuit_breaker_opens": 0,
            "retries_executed": 0,
            "timeouts": 0,
            "bulkhead_rejections": 0
        }

        # Reset individual component metrics
        for cb in self._circuit_breakers.values():
            cb.reset()

        # Reset bulkhead stats
        for bulkhead in self._bulkheads.values():
            bulkhead.reset_stats()


# Service-based resilience manager access


def get_resilience_manager(config: ConsolidatedResilienceConfig | None = None, service_config: dict[str, Any] | None = None) -> ConsolidatedResilienceManager:
    """Get the resilience manager instance from the DI container."""
    # Import here to avoid circular dependency

    service = get_service(ResilienceManagerService)
    # Update config if provided
    if config is not None or service_config is not None:
        service.update_config(service_config or {})
    return service.get_manager()


def set_resilience_manager(manager: ConsolidatedResilienceManager):
    """Set the resilience manager instance (not supported - use DI container instead)."""
    raise NotImplementedError(
        "set_resilience_manager is not supported. Use the DI container to register ResilienceManagerService instead."
    )


# Convenience functions for common strategies
async def resilient_internal_call(
    func: Callable[..., Awaitable[T]],
    *args,
    name: str = "internal_service",
    **kwargs
) -> T:
    """Execute an internal service call with resilience patterns."""
    manager = get_resilience_manager()
    return await manager.execute_resilient(
        func, *args,
        name=name,
        strategy=ResilienceStrategy.INTERNAL_SERVICE,
        **kwargs
    )


async def resilient_external_call(
    func: Callable[..., Awaitable[T]],
    *args,
    name: str = "external_service",
    **kwargs
) -> T:
    """Execute an external service call with resilience patterns."""
    manager = get_resilience_manager()
    return await manager.execute_resilient(
        func, *args,
        name=name,
        strategy=ResilienceStrategy.EXTERNAL_SERVICE,
        **kwargs
    )


async def resilient_database_call(
    func: Callable[..., Awaitable[T]],
    *args,
    name: str = "database",
    **kwargs
) -> T:
    """Execute a database call with resilience patterns."""
    manager = get_resilience_manager()
    return await manager.execute_resilient(
        func, *args,
        name=name,
        strategy=ResilienceStrategy.DATABASE,
        **kwargs
    )


# Predefined strategy configurations
DEFAULT_STRATEGIES = {
    ResilienceStrategy.INTERNAL_SERVICE: {
        "circuit_breaker_failure_threshold": 3,
        "circuit_breaker_recovery_timeout": 30.0,
        "retry_max_attempts": 3,
        "retry_base_delay": 0.5,
        "timeout_seconds": 10.0,
        "bulkhead_enabled": True,
        "bulkhead_max_concurrent": 50
    },
    ResilienceStrategy.EXTERNAL_SERVICE: {
        "circuit_breaker_failure_threshold": 5,
        "circuit_breaker_recovery_timeout": 60.0,
        "retry_max_attempts": 3,
        "retry_base_delay": 1.0,
        "timeout_seconds": 30.0,
        "bulkhead_enabled": True,
        "bulkhead_max_concurrent": 20
    },
    ResilienceStrategy.DATABASE: {
        "circuit_breaker_failure_threshold": 3,
        "circuit_breaker_recovery_timeout": 15.0,
        "retry_max_attempts": 2,
        "retry_base_delay": 0.1,
        "timeout_seconds": 5.0,
        "bulkhead_enabled": True,
        "bulkhead_max_concurrent": 100
    },
    ResilienceStrategy.CACHE: {
        "circuit_breaker_failure_threshold": 5,
        "circuit_breaker_recovery_timeout": 10.0,
        "retry_max_attempts": 1,
        "retry_base_delay": 0.1,
        "timeout_seconds": 2.0,
        "bulkhead_enabled": False
    }
}


def create_resilience_manager_with_defaults() -> ConsolidatedResilienceManager:
    """Create a resilience manager with sensible defaults for different strategies."""
    config = ConsolidatedResilienceConfig(strategy_overrides=DEFAULT_STRATEGIES)
    return ConsolidatedResilienceManager(config)


def create_resilience_manager_from_service_config(service_config: dict[str, Any]) -> ConsolidatedResilienceManager:
    """Create a resilience manager from service configuration."""
    return ConsolidatedResilienceManager(service_config=service_config)


def configure_resilience_manager(service_config: dict[str, Any]) -> None:
    """Configure the resilience manager with service configuration (not supported)."""
    raise NotImplementedError(
        "configure_resilience_manager is not supported. Use the DI container to configure ResilienceManagerService instead."
    )
