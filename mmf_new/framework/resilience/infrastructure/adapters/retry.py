"""
Retry Pattern Implementation.
"""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from mmf_new.framework.resilience.domain.config import (
    CircuitBreakerConfig,
    RetryConfig,
    RetryStrategy,
)
from mmf_new.framework.resilience.domain.exceptions import (
    CircuitBreakerError,
    RetryError,
)

from .circuit_breaker import get_circuit_breaker

T = TypeVar("T")
logger = logging.getLogger(__name__)


class BackoffStrategy(ABC):
    """Abstract base class for backoff strategies."""

    @abstractmethod
    def calculate_delay(self, attempt: int, base_delay: float, max_delay: float) -> float:
        """Calculate delay for given attempt number."""


class ExponentialBackoff(BackoffStrategy):
    """Exponential backoff with optional jitter."""

    def __init__(self, multiplier: float = 2.0, jitter: bool = True, jitter_factor: float = 0.1):
        self.multiplier = multiplier
        self.jitter = jitter
        self.jitter_factor = jitter_factor

    def calculate_delay(self, attempt: int, base_delay: float, max_delay: float) -> float:
        """Calculate exponential backoff delay."""
        delay = base_delay * (self.multiplier ** (attempt - 1))
        delay = min(delay, max_delay)

        if self.jitter:
            jitter_range = delay * self.jitter_factor
            jitter_value = random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay + jitter_value)

        return delay


class LinearBackoff(BackoffStrategy):
    """Linear backoff with optional jitter."""

    def __init__(self, increment: float = 1.0, jitter: bool = True, jitter_factor: float = 0.1):
        self.increment = increment
        self.jitter = jitter
        self.jitter_factor = jitter_factor

    def calculate_delay(self, attempt: int, base_delay: float, max_delay: float) -> float:
        """Calculate linear backoff delay."""
        delay = base_delay + (self.increment * (attempt - 1))
        delay = min(delay, max_delay)

        if self.jitter:
            jitter_range = delay * self.jitter_factor
            jitter_value = random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay + jitter_value)

        return delay


class ConstantBackoff(BackoffStrategy):
    """Constant delay with optional jitter."""

    def __init__(self, jitter: bool = True, jitter_factor: float = 0.1):
        self.jitter = jitter
        self.jitter_factor = jitter_factor

    def calculate_delay(self, attempt: int, base_delay: float, max_delay: float) -> float:
        """Calculate constant backoff delay."""
        delay = base_delay

        if self.jitter:
            jitter_range = delay * self.jitter_factor
            jitter_value = random.uniform(-jitter_range, jitter_range)
            delay = max(0, delay + jitter_value)

        return delay


class RetryManager:
    """Manages retry logic with configurable strategies."""

    def __init__(self, config: RetryConfig):
        self.config = config
        self._backoff_strategy = self._create_backoff_strategy()

    def _create_backoff_strategy(self) -> BackoffStrategy:
        """Create backoff strategy based on configuration."""
        if self.config.strategy == RetryStrategy.EXPONENTIAL:
            return ExponentialBackoff(
                multiplier=self.config.backoff_multiplier,
                jitter=self.config.jitter,
                jitter_factor=self.config.jitter_factor,
            )
        if self.config.strategy == RetryStrategy.LINEAR:
            return LinearBackoff(
                increment=self.config.base_delay,
                jitter=self.config.jitter,
                jitter_factor=self.config.jitter_factor,
            )
        if self.config.strategy == RetryStrategy.CONSTANT:
            return ConstantBackoff(
                jitter=self.config.jitter, jitter_factor=self.config.jitter_factor
            )
        # Default to exponential
        return ExponentialBackoff()

    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """Check if exception should trigger a retry."""
        # Check if we've exceeded max attempts
        if attempt >= self.config.max_attempts:
            return False

        # Check if exception is non-retryable
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False

        # Check if exception is retryable
        if not isinstance(exception, self.config.retryable_exceptions):
            return False

        # Check custom retry condition
        if self.config.retry_condition:
            return self.config.retry_condition(exception)

        return True

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt."""
        if self.config.custom_delay_func:
            return self.config.custom_delay_func(attempt, self.config.base_delay)

        return self._backoff_strategy.calculate_delay(
            attempt, self.config.base_delay, self.config.max_delay
        )

    async def execute_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute async function with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug("Retry attempt %d/%d", attempt, self.config.max_attempts)
                result = await func(*args, **kwargs)

                if attempt > 1:
                    logger.info("Function succeeded on attempt %d", attempt)

                return result

            except Exception as e:
                last_exception = e
                logger.warning("Attempt %d failed: %s", attempt, e)

                if not self._should_retry(e, attempt):
                    break

                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.debug("Waiting %.2f seconds before retry", delay)
                    await asyncio.sleep(delay)

        # All attempts failed
        raise RetryError(
            f"Function failed after {self.config.max_attempts} attempts",
            self.config.max_attempts,
            last_exception or Exception("Unknown error"),
        )

    def execute_sync(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute sync function with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug("Retry attempt %d/%d", attempt, self.config.max_attempts)
                result = func(*args, **kwargs)

                if attempt > 1:
                    logger.info("Function succeeded on attempt %d", attempt)

                return result

            except Exception as e:
                last_exception = e
                logger.warning("Attempt %d failed: %s", attempt, e)

                if not self._should_retry(e, attempt):
                    break

                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.debug("Waiting %.2f seconds before retry", delay)
                    time.sleep(delay)

        # All attempts failed
        raise RetryError(
            f"Function failed after {self.config.max_attempts} attempts",
            self.config.max_attempts,
            last_exception or Exception("Unknown error"),
        )


async def retry_async(
    func: Callable[..., Any], *args: Any, config: RetryConfig | None = None, **kwargs: Any
) -> Any:
    """Execute async function with retry logic."""
    retry_config = config or RetryConfig()
    manager = RetryManager(retry_config)
    return await manager.execute_async(func, *args, **kwargs)


def retry_sync(
    func: Callable[..., Any], *args: Any, config: RetryConfig | None = None, **kwargs: Any
) -> Any:
    """Execute sync function with retry logic."""
    retry_config = config or RetryConfig()
    manager = RetryManager(retry_config)
    return manager.execute_sync(func, *args, **kwargs)


def retry_decorator(
    config: RetryConfig | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic to functions."""
    retry_config = config or RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                return await retry_async(func, *args, config=retry_config, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            return retry_sync(func, *args, config=retry_config, **kwargs)

        return sync_wrapper

    return decorator


async def retry_with_circuit_breaker(
    func: Callable[..., T],
    *args: Any,
    retry_config: RetryConfig | None = None,
    circuit_breaker_config: CircuitBreakerConfig | None = None,
    circuit_breaker_name: str = "default",
    **kwargs: Any,
) -> T:
    """Execute function with both retry and circuit breaker protection."""
    retry_cfg = retry_config or RetryConfig()
    circuit = get_circuit_breaker(circuit_breaker_name, circuit_breaker_config)

    # Modify retry config to handle circuit breaker errors
    modified_config = RetryConfig(
        max_attempts=retry_cfg.max_attempts,
        base_delay=retry_cfg.base_delay,
        max_delay=retry_cfg.max_delay,
        strategy=retry_cfg.strategy,
        backoff_multiplier=retry_cfg.backoff_multiplier,
        jitter=retry_cfg.jitter,
        jitter_factor=retry_cfg.jitter_factor,
        retryable_exceptions=retry_cfg.retryable_exceptions,
        non_retryable_exceptions=retry_cfg.non_retryable_exceptions + (CircuitBreakerError,),
        custom_delay_func=retry_cfg.custom_delay_func,
        retry_condition=retry_cfg.retry_condition,
    )

    async def circuit_protected_func(*f_args: Any, **f_kwargs: Any) -> T:
        return await circuit.call(func, *f_args, **f_kwargs)

    return await retry_async(circuit_protected_func, *args, config=modified_config, **kwargs)
