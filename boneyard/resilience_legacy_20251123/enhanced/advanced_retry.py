"""
Advanced retry mechanisms with enhanced backoff strategies and monitoring.

Ported from Marty's resilience framework to provide sophisticated retry
patterns for microservices.
"""

import asyncio
import logging
import random
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BackoffStrategy(str, Enum):
    """Available backoff strategies for retries."""

    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    FIBONACCI = "fibonacci"
    RANDOM = "random"
    JITTERED_EXPONENTIAL = "jittered_exponential"


@dataclass
class AdvancedRetryConfig:
    """Configuration for advanced retry mechanisms."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.1

    # Error classification
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)
    non_retryable_exceptions: tuple[type[Exception], ...] = ()

    # Circuit breaker integration
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout: float = 30.0

    # Monitoring
    collect_metrics: bool = True
    log_retries: bool = True


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    attempts: int
    total_time: float
    last_exception: Exception | None = None
    result: Any = None


@dataclass
class AdvancedRetryMetrics:
    """Metrics for retry operations."""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_retry_time: float = 0.0
    average_attempts_per_call: float = 0.0
    success_rate: float = 0.0

    def update(self, result: RetryResult) -> None:
        """Update metrics with retry result."""
        self.total_attempts += result.attempts
        if result.success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1
        self.total_retry_time += result.total_time

        total_calls = self.successful_attempts + self.failed_attempts
        if total_calls > 0:
            self.average_attempts_per_call = self.total_attempts / total_calls
            self.success_rate = self.successful_attempts / total_calls


class AdvancedRetryManager:
    """Manager for advanced retry operations with metrics."""

    def __init__(self, name: str, config: AdvancedRetryConfig):
        self.name = name
        self.config = config
        self.metrics = AdvancedRetryMetrics()
        self._retry_counts = defaultdict(int)

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        if self.config.backoff_strategy == BackoffStrategy.CONSTANT:
            delay = self.config.base_delay
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.base_delay * attempt
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))
        elif self.config.backoff_strategy == BackoffStrategy.FIBONACCI:
            delay = self.config.base_delay * self._fibonacci(attempt)
        elif self.config.backoff_strategy == BackoffStrategy.RANDOM:
            delay = random.uniform(self.config.base_delay, self.config.max_delay)
        elif self.config.backoff_strategy == BackoffStrategy.JITTERED_EXPONENTIAL:
            base_delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))
            jitter = (
                random.uniform(-self.config.jitter_range, self.config.jitter_range) * base_delay
            )
            delay = base_delay + jitter
        else:
            delay = self.config.base_delay

        # Apply jitter if enabled (except for random and jittered strategies)
        if self.config.jitter and self.config.backoff_strategy not in [
            BackoffStrategy.RANDOM,
            BackoffStrategy.JITTERED_EXPONENTIAL,
        ]:
            jitter = random.uniform(-self.config.jitter_range, self.config.jitter_range) * delay
            delay += jitter

        return min(delay, self.config.max_delay)

    def _fibonacci(self, n: int) -> int:
        """Calculate nth Fibonacci number."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    def is_retryable(self, exception: Exception) -> bool:
        """Check if an exception is retryable."""
        # Check non-retryable first (more specific)
        for exc_type in self.config.non_retryable_exceptions:
            if isinstance(exception, exc_type):
                return False

        # Check retryable
        for exc_type in self.config.retryable_exceptions:
            if isinstance(exception, exc_type):
                return True

        return False


# Global registry of retry managers
_retry_managers: dict[str, AdvancedRetryManager] = {}


def get_retry_manager(name: str, config: AdvancedRetryConfig | None = None) -> AdvancedRetryManager:
    """Get or create a retry manager."""
    if name not in _retry_managers:
        if config is None:
            config = AdvancedRetryConfig()
        _retry_managers[name] = AdvancedRetryManager(name, config)
    return _retry_managers[name]


def get_all_retry_manager_stats() -> dict[str, AdvancedRetryMetrics]:
    """Get statistics for all retry managers."""
    return {name: manager.metrics for name, manager in _retry_managers.items()}


def retry_with_advanced_policy(
    func: Callable[..., T],
    *args,
    config: AdvancedRetryConfig | None = None,
    manager_name: str = "default",
    **kwargs,
) -> RetryResult:
    """Execute function with advanced retry policy."""
    if config is None:
        config = AdvancedRetryConfig()

    manager = get_retry_manager(manager_name, config)
    start_time = time.time()
    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time

            retry_result = RetryResult(
                success=True, attempts=attempt, total_time=execution_time, result=result
            )

            if config.collect_metrics:
                manager.metrics.update(retry_result)

            if config.log_retries and attempt > 1:
                logger.info("Function succeeded on attempt %d after %.2fs", attempt, execution_time)

            return retry_result

        except Exception as e:  # noqa: BLE001
            last_exception = e

            if not manager.is_retryable(e):
                if config.log_retries:
                    logger.error("Non-retryable exception: %s", e)
                break

            if attempt < config.max_attempts:
                delay = manager.calculate_delay(attempt)

                if config.log_retries:
                    logger.warning(
                        "Attempt %d failed with %s, retrying in %.2fs", attempt, e, delay
                    )

                time.sleep(delay)
            else:
                if config.log_retries:
                    logger.error("All %d attempts failed", config.max_attempts)

    execution_time = time.time() - start_time
    retry_result = RetryResult(
        success=False,
        attempts=config.max_attempts,
        total_time=execution_time,
        last_exception=last_exception,
    )

    if config.collect_metrics:
        manager.metrics.update(retry_result)

    return retry_result


async def async_retry_with_advanced_policy(
    func: Callable[..., Any],
    *args,
    config: AdvancedRetryConfig | None = None,
    manager_name: str = "default",
    **kwargs,
) -> RetryResult:
    """Execute async function with advanced retry policy."""
    if config is None:
        config = AdvancedRetryConfig()

    manager = get_retry_manager(manager_name, config)
    start_time = time.time()
    last_exception = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            execution_time = time.time() - start_time

            retry_result = RetryResult(
                success=True, attempts=attempt, total_time=execution_time, result=result
            )

            if config.collect_metrics:
                manager.metrics.update(retry_result)

            if config.log_retries and attempt > 1:
                logger.info("Function succeeded on attempt %d after %.2fs", attempt, execution_time)

            return retry_result

        except Exception as e:  # noqa: BLE001
            last_exception = e

            if not manager.is_retryable(e):
                if config.log_retries:
                    logger.error("Non-retryable exception: %s", e)
                break

            if attempt < config.max_attempts:
                delay = manager.calculate_delay(attempt)

                if config.log_retries:
                    logger.warning(
                        "Attempt %d failed with %s, retrying in %.2fs", attempt, e, delay
                    )

                await asyncio.sleep(delay)
            else:
                if config.log_retries:
                    logger.error("All %d attempts failed", config.max_attempts)

    execution_time = time.time() - start_time
    retry_result = RetryResult(
        success=False,
        attempts=config.max_attempts,
        total_time=execution_time,
        last_exception=last_exception,
    )

    if config.collect_metrics:
        manager.metrics.update(retry_result)

    return retry_result
