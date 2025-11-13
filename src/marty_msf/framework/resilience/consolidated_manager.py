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

from .api import (
    BulkheadRejectedError,
    CircuitBreakerOpenError,
    IResilienceManager,
    ResilienceConfig,
    ResilienceMetrics,
    ResilienceStrategy,
    ResilienceTimeoutError,
    RetryExhaustedError,
)
from .bulkhead import BulkheadConfig, BulkheadError, SemaphoreBulkhead
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerError
from .enhanced.advanced_retry import (
    AdvancedRetryConfig,
    async_retry_with_advanced_policy,
)
from .timeout import TimeoutConfig, with_sync_timeout, with_timeout

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ConsolidatedResilienceConfig:
    """Extended configuration for consolidated resilience manager."""

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


class ConsolidatedResilienceManager(IResilienceManager):
    """
    Unified resilience manager that automatically applies circuit breakers,
    retries, and timeouts to internal client calls.

    This consolidates all fragmented resilience implementations into a
    single, cohesive solution.
    """

    def __init__(self, config: ConsolidatedResilienceConfig | None = None):
        """Initialize the consolidated resilience manager."""
        self.config = config or ConsolidatedResilienceConfig()
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._bulkheads: dict[str, SemaphoreBulkhead] = {}
        self._metrics = ResilienceMetrics()

    async def execute_with_resilience(
        self,
        func: Callable[[], Awaitable[T]],
        strategy: ResilienceStrategy = ResilienceStrategy.INTERNAL_SERVICE,
        config_override: ConsolidatedResilienceConfig | None = None,
        operation_name: str | None = None,
    ) -> T:
        """Execute a function with resilience patterns applied."""
        start_time = time.time()
        operation_name = operation_name or f"{func.__name__}_{strategy.value}"

        # Get effective configuration
        effective_config = config_override or self.config.get_strategy_config(strategy)

        try:
            # Create execution function with appropriate resilience patterns
            execution_func = func

            # Apply timeout if enabled
            if effective_config.timeout_enabled:

                async def timeout_execution():
                    try:
                        return await asyncio.wait_for(
                            execution_func(),
                            timeout=effective_config.timeout_seconds,
                        )
                    except asyncio.TimeoutError as e:
                        raise ResilienceTimeoutError(
                            f"Operation {operation_name} timed out after {effective_config.timeout_seconds}s"
                        ) from e

                execution_func = timeout_execution

            # Apply circuit breaker if enabled
            if effective_config.circuit_breaker_enabled:
                circuit_breaker = self._get_or_create_circuit_breaker(
                    operation_name, effective_config
                )

                async def circuit_breaker_execution():
                    try:
                        return await circuit_breaker.call_async(execution_func)
                    except CircuitBreakerError as e:
                        raise CircuitBreakerOpenError(
                            f"Circuit breaker open for {operation_name}"
                        ) from e

                execution_func = circuit_breaker_execution

            # Apply bulkhead if enabled
            if effective_config.bulkhead_enabled:
                bulkhead = self._get_or_create_bulkhead(operation_name, effective_config)

                async def bulkhead_execution():
                    try:
                        return await bulkhead.execute_async(execution_func)
                    except BulkheadError as e:
                        raise BulkheadRejectedError(
                            f"Bulkhead rejected request for {operation_name}"
                        ) from e

                execution_func = bulkhead_execution

            # Apply retry if enabled
            if effective_config.retry_enabled:
                execution_func = async_retry_with_advanced_policy(
                    max_attempts=effective_config.retry_max_attempts,
                    base_delay=effective_config.retry_base_delay,
                    max_delay=effective_config.retry_max_delay,
                    backoff_multiplier=effective_config.retry_exponential_base,
                    jitter=effective_config.retry_jitter,
                    retry_exceptions=effective_config.retry_exceptions,
                    ignore_exceptions=effective_config.ignore_exceptions,
                )(execution_func)

            # Execute the function with all resilience patterns applied
            result = await execution_func()

            # Update metrics
            self._metrics.record_success(operation_name, time.time() - start_time)

            return result

        except Exception as e:
            # Update metrics
            self._metrics.record_failure(operation_name, time.time() - start_time, str(e))
            raise

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all resilience components."""
        return {
            "circuit_breakers": {
                name: {
                    "state": breaker.state.name,
                    "failure_count": breaker.failure_count,
                    "last_failure_time": breaker.last_failure_time,
                }
                for name, breaker in self._circuit_breakers.items()
            },
            "bulkheads": {
                name: {
                    "active_requests": bulkhead.active_count,
                    "max_concurrent": bulkhead.max_concurrent,
                    "queue_size": bulkhead.queue_size,
                }
                for name, bulkhead in self._bulkheads.items()
            },
            "metrics": {
                "total_operations": self._metrics.total_operations,
                "success_count": self._metrics.success_count,
                "failure_count": self._metrics.failure_count,
                "success_rate": self._metrics.get_success_rate(),
                "average_duration": self._metrics.get_average_duration(),
            },
        }

    def execute_resilient_sync(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a synchronous function with resilience patterns applied."""

        # Convert to async and run synchronously
        async def async_wrapper():
            async def sync_to_async():
                return func(*args, **kwargs)

            return await self.execute_resilient(sync_to_async)

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_wrapper())
        finally:
            loop.close()

    async def apply_resilience(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Apply resilience patterns to a function call."""

        # Create a wrapper function and execute with resilience
        async def wrapper():
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return await self.execute_resilient(wrapper)

    def update_config(self, config: dict[str, Any]) -> None:
        """Update resilience configuration."""
        # Convert dict to ConsolidatedResilienceConfig
        new_config = ConsolidatedResilienceConfig(**config)
        self.config = new_config

        # Clear caches to force recreation with new config
        self._circuit_breakers.clear()
        self._bulkheads.clear()

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on resilience components."""
        return self.get_health_status()

    def get_metrics(self) -> dict[str, Any]:
        """Get resilience metrics as dict."""
        return {
            "total_operations": self._metrics.total_operations,
            "success_count": self._metrics.success_count,
            "failure_count": self._metrics.failure_count,
            "success_rate": self._metrics.get_success_rate(),
            "average_duration": self._metrics.get_average_duration(),
        }

    def get_resilience_metrics(self) -> ResilienceMetrics:
        """Get current resilience metrics object."""
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset all metrics."""
        self._metrics = ResilienceMetrics()

    def _get_or_create_circuit_breaker(
        self, operation_name: str, config: ConsolidatedResilienceConfig
    ) -> CircuitBreaker:
        """Get or create a circuit breaker for the operation."""
        if operation_name not in self._circuit_breakers:
            breaker_config = CircuitBreakerConfig(
                failure_threshold=config.circuit_breaker_failure_threshold,
                recovery_timeout=config.circuit_breaker_recovery_timeout,
                success_threshold=config.circuit_breaker_success_threshold,
                failure_exceptions=config.circuit_breaker_exceptions,
                ignore_exceptions=config.ignore_exceptions,
            )
            self._circuit_breakers[operation_name] = CircuitBreaker(breaker_config)

        return self._circuit_breakers[operation_name]

    def _get_or_create_bulkhead(
        self, operation_name: str, config: ConsolidatedResilienceConfig
    ) -> SemaphoreBulkhead:
        """Get or create a bulkhead for the operation."""
        if operation_name not in self._bulkheads:
            bulkhead_config = BulkheadConfig(
                max_concurrent=config.bulkhead_max_concurrent,
                timeout_seconds=config.bulkhead_timeout,
            )
            self._bulkheads[operation_name] = SemaphoreBulkhead(bulkhead_config)

        return self._bulkheads[operation_name]


# Convenience function for backward compatibility
def create_consolidated_resilience_manager(
    resilience_config: dict[str, Any] | None = None,
) -> ConsolidatedResilienceManager:
    """Create a consolidated resilience manager with configuration."""
    if resilience_config is None:
        return ConsolidatedResilienceManager()

    config = ConsolidatedResilienceConfig(
        circuit_breaker_enabled=resilience_config.get("circuit_breaker_enabled", True),
        circuit_breaker_failure_threshold=resilience_config.get(
            "circuit_breaker_failure_threshold", 5
        ),
        circuit_breaker_recovery_timeout=resilience_config.get(
            "circuit_breaker_recovery_timeout", 60.0
        ),
        circuit_breaker_success_threshold=resilience_config.get(
            "circuit_breaker_success_threshold", 3
        ),
        retry_enabled=resilience_config.get("retry_enabled", True),
        retry_max_attempts=resilience_config.get("retry_max_attempts", 3),
        retry_base_delay=resilience_config.get("retry_base_delay", 1.0),
        retry_max_delay=resilience_config.get("retry_max_delay", 60.0),
        retry_exponential_base=resilience_config.get("retry_exponential_base", 2.0),
        retry_jitter=resilience_config.get("retry_jitter", True),
        timeout_enabled=resilience_config.get("timeout_enabled", True),
        timeout_seconds=resilience_config.get("timeout_seconds", 30.0),
        bulkhead_enabled=resilience_config.get("bulkhead_enabled", False),
        bulkhead_max_concurrent=resilience_config.get("bulkhead_max_concurrent", 100),
        bulkhead_timeout=resilience_config.get("bulkhead_timeout", 30.0),
    )

    return ConsolidatedResilienceManager(config)
