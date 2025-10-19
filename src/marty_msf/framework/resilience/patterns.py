"""
Resilience Patterns Integration Module

Provides integrated resilience patterns that combine circuit breakers,
retries, bulkheads, timeouts, and fallbacks for comprehensive fault tolerance.
"""

import asyncio
import builtins
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from .bulkhead import BulkheadConfig, BulkheadPool, get_bulkhead_manager
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .fallback import (
    FallbackConfig,
    FallbackError,
    FallbackStrategy,
    get_fallback_manager,
)
from .retry import RetryConfig, retry_async
from .timeout import TimeoutConfig, get_timeout_manager

T = TypeVar("T")
logger = logging.getLogger(__name__)


class ResiliencePattern(Enum):
    """Available resilience patterns."""

    CIRCUIT_BREAKER = "circuit_breaker"
    RETRY = "retry"
    BULKHEAD = "bulkhead"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"
    COMBINED = "combined"


@dataclass
class ResilienceConfig:
    """Comprehensive configuration for resilience patterns."""

    # Circuit breaker configuration
    circuit_breaker_config: CircuitBreakerConfig | None = None
    circuit_breaker_name: str | None = None

    # Retry configuration
    retry_config: RetryConfig | None = None

    # Bulkhead configuration
    bulkhead_config: BulkheadConfig | None = None
    bulkhead_name: str | None = None

    # Timeout configuration
    timeout_config: TimeoutConfig | None = None
    timeout_seconds: float | None = None

    # Fallback configuration
    fallback_config: FallbackConfig | None = None
    fallback_strategy: str | FallbackStrategy | None = None

    # Pattern execution order
    execution_order: builtins.list[ResiliencePattern] = None

    # Enable pattern logging
    log_patterns: bool = True

    # Collect metrics
    collect_metrics: bool = True

    def __post_init__(self):
        if self.execution_order is None:
            self.execution_order = [
                ResiliencePattern.TIMEOUT,
                ResiliencePattern.CIRCUIT_BREAKER,
                ResiliencePattern.RETRY,
                ResiliencePattern.BULKHEAD,
                ResiliencePattern.FALLBACK,
            ]


class ResilienceManager:
    """Manages integrated resilience patterns."""

    def __init__(self, config: ResilienceConfig | None = None):
        self.config = config or ResilienceConfig()

        # Component managers
        self.bulkhead_manager = get_bulkhead_manager()
        self.timeout_manager = get_timeout_manager()
        self.fallback_manager = get_fallback_manager()

        # Circuit breakers
        self._circuit_breakers: builtins.dict[str, CircuitBreaker] = {}

        # Metrics
        self._total_operations = 0
        self._successful_operations = 0
        self._failed_operations = 0
        self._pattern_usage: builtins.dict[ResiliencePattern, int] = dict.fromkeys(
            ResiliencePattern, 0
        )

    def get_or_create_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create circuit breaker."""
        if name not in self._circuit_breakers:
            config = self.config.circuit_breaker_config or CircuitBreakerConfig()
            self._circuit_breakers[name] = CircuitBreaker(name, config)
        return self._circuit_breakers[name]

    def get_or_create_bulkhead(self, name: str) -> BulkheadPool:
        """Get or create bulkhead."""
        existing = self.bulkhead_manager.get_bulkhead(name)
        if existing:
            return existing

        config = self.config.bulkhead_config or BulkheadConfig()
        return self.bulkhead_manager.create_bulkhead(name, config)

    async def execute_with_patterns(
        self, func: Callable[..., T], operation_name: str = "operation", *args, **kwargs
    ) -> T:
        """Execute function with integrated resilience patterns."""
        self._total_operations += 1

        if self.config.log_patterns:
            logger.info("Executing operation '%s' with resilience patterns", operation_name)

        try:
            result = await self._execute_with_ordered_patterns(
                func, operation_name, *args, **kwargs
            )
            self._successful_operations += 1
            return result

        except Exception:
            self._failed_operations += 1

            # Try fallback if configured
            if (
                ResiliencePattern.FALLBACK in self.config.execution_order
                and self.config.fallback_strategy
            ):
                try:
                    self._pattern_usage[ResiliencePattern.FALLBACK] += 1
                    result = await self.fallback_manager.execute_with_fallback(
                        func, self.config.fallback_strategy, *args, **kwargs
                    )
                    self._successful_operations += 1
                    return result

                except FallbackError:
                    if self.config.log_patterns:
                        logger.error(
                            "All resilience patterns failed for operation '%s'",
                            operation_name,
                        )
                    raise

            raise

    async def _execute_with_ordered_patterns(
        self, func: Callable[..., T], operation_name: str, *args, **kwargs
    ) -> T:
        """Execute function with patterns in configured order."""

        async def execute_func():
            return await self._apply_patterns(func, operation_name, *args, **kwargs)

        # Apply patterns in reverse order for proper nesting
        current_func = execute_func

        for pattern in reversed(self.config.execution_order):
            if pattern == ResiliencePattern.FALLBACK:
                continue  # Fallback is handled separately

            current_func = await self._wrap_with_pattern(current_func, pattern, operation_name)

        return await current_func()

    async def _wrap_with_pattern(
        self, func: Callable[[], T], pattern: ResiliencePattern, operation_name: str
    ) -> Callable[[], T]:
        """Wrap function with specific resilience pattern."""

        if pattern == ResiliencePattern.TIMEOUT:
            if self.config.timeout_seconds or self.config.timeout_config:
                self._pattern_usage[ResiliencePattern.TIMEOUT] += 1
                timeout = self.config.timeout_seconds or (
                    self.config.timeout_config.default_timeout
                    if self.config.timeout_config
                    else 30.0
                )

                async def timeout_wrapper():
                    return await self.timeout_manager.execute_with_timeout(
                        func, timeout, operation_name
                    )

                return timeout_wrapper

        elif pattern == ResiliencePattern.CIRCUIT_BREAKER:
            if self.config.circuit_breaker_name or self.config.circuit_breaker_config:
                self._pattern_usage[ResiliencePattern.CIRCUIT_BREAKER] += 1
                cb_name = self.config.circuit_breaker_name or operation_name
                circuit_breaker = self.get_or_create_circuit_breaker(cb_name)

                async def circuit_breaker_wrapper():
                    return await circuit_breaker.call(func)

                return circuit_breaker_wrapper

        elif pattern == ResiliencePattern.RETRY:
            if self.config.retry_config:
                self._pattern_usage[ResiliencePattern.RETRY] += 1

                async def retry_wrapper():
                    return await retry_async(func, self.config.retry_config)

                return retry_wrapper

        elif pattern == ResiliencePattern.BULKHEAD:
            if self.config.bulkhead_name or self.config.bulkhead_config:
                self._pattern_usage[ResiliencePattern.BULKHEAD] += 1
                bulkhead_name = self.config.bulkhead_name or operation_name
                bulkhead = self.get_or_create_bulkhead(bulkhead_name)

                async def bulkhead_wrapper():
                    return await bulkhead.execute_async(func)

                return bulkhead_wrapper

        return func

    async def _apply_patterns(
        self, func: Callable[..., T], operation_name: str, *args, **kwargs
    ) -> T:
        """Apply the actual function execution."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get comprehensive resilience statistics."""
        success_rate = self._successful_operations / max(1, self._total_operations)

        return {
            "total_operations": self._total_operations,
            "successful_operations": self._successful_operations,
            "failed_operations": self._failed_operations,
            "success_rate": success_rate,
            "pattern_usage": {
                pattern.value: count for pattern, count in self._pattern_usage.items()
            },
            "circuit_breakers": {
                name: cb.get_stats() for name, cb in self._circuit_breakers.items()
            },
            "bulkheads": self.bulkhead_manager.get_all_stats(),
            "timeouts": self.timeout_manager.get_stats(),
            "fallbacks": self.fallback_manager.get_stats(),
        }


# Global resilience manager
# Service-based resilience manager access (not supported - use consolidated_manager instead)


def get_resilience_manager() -> ResilienceManager:
    """Get the default resilience manager (not supported)."""
    raise NotImplementedError(
        "patterns.get_resilience_manager is not supported. Use consolidated_manager.get_resilience_manager instead."
    )


def initialize_resilience(
    config: ResilienceConfig | None = None,
) -> ResilienceManager:
    """Initialize resilience patterns with configuration (not supported)."""
    raise NotImplementedError(
        "patterns.initialize_resilience is not supported. Use the DI container to configure ResilienceManagerService instead."
    )


def resilience_pattern(config: ResilienceConfig | None = None, operation_name: str | None = None):
    """
    Decorator to add comprehensive resilience patterns to functions.

    Args:
        config: Resilience configuration
        operation_name: Operation name for logging and metrics

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        op_name = operation_name or func.__name__
        manager = ResilienceManager(config) if config else get_resilience_manager()

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                return await manager.execute_with_patterns(func, op_name, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        async def sync_wrapper(*args, **kwargs) -> T:
            return await manager.execute_with_patterns(func, op_name, *args, **kwargs)

        return sync_wrapper

    return decorator


# Predefined resilience configurations
DEFAULT_RESILIENCE_CONFIG = ResilienceConfig()

AGGRESSIVE_RESILIENCE_CONFIG = ResilienceConfig(
    circuit_breaker_config=CircuitBreakerConfig(
        failure_threshold=3,
        timeout_seconds=30,
        use_failure_rate=True,
        failure_rate_threshold=0.3,
    ),
    retry_config=RetryConfig(max_attempts=5, base_delay=0.5, max_delay=10.0),
    timeout_seconds=15.0,
    execution_order=[
        ResiliencePattern.TIMEOUT,
        ResiliencePattern.CIRCUIT_BREAKER,
        ResiliencePattern.RETRY,
        ResiliencePattern.FALLBACK,
    ],
)

CONSERVATIVE_RESILIENCE_CONFIG = ResilienceConfig(
    circuit_breaker_config=CircuitBreakerConfig(
        failure_threshold=10, timeout_seconds=60, use_failure_rate=False
    ),
    retry_config=RetryConfig(max_attempts=3, base_delay=2.0, max_delay=30.0),
    timeout_seconds=60.0,
    execution_order=[
        ResiliencePattern.TIMEOUT,
        ResiliencePattern.RETRY,
        ResiliencePattern.CIRCUIT_BREAKER,
    ],
)

FAST_FAIL_CONFIG = ResilienceConfig(
    circuit_breaker_config=CircuitBreakerConfig(
        failure_threshold=2,
        timeout_seconds=10,
        use_failure_rate=True,
        failure_rate_threshold=0.5,
    ),
    retry_config=RetryConfig(max_attempts=2, base_delay=0.1, max_delay=1.0),
    timeout_seconds=5.0,
    execution_order=[ResiliencePattern.TIMEOUT, ResiliencePattern.CIRCUIT_BREAKER],
)
