"""
Retry Pattern Implementation

Provides configurable retry mechanisms with exponential backoff, jitter,
and integration with circuit breakers for robust error handling.
"""

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import TypeVar

from .circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerError,
    get_circuit_breaker,
)

T = TypeVar("T")
logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"
    CUSTOM = "custom"


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, message: str, attempts: int, last_exception: Exception):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    # Maximum number of retry attempts
    max_attempts: int = 3

    # Base delay between retries (seconds)
    base_delay: float = 1.0

    # Maximum delay between retries (seconds)
    max_delay: float = 60.0

    # Retry strategy
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL

    # Exponential backoff multiplier
    backoff_multiplier: float = 2.0

    # Add random jitter to prevent thundering herd
    jitter: bool = True

    # Maximum jitter factor (0.0 to 1.0)
    jitter_factor: float = 0.1

    # Exception types that trigger retries
    retryable_exceptions: tuple = (Exception,)

    # Exception types that should not be retried
    non_retryable_exceptions: tuple = ()

    # Custom delay calculation function
    custom_delay_func: Callable[[int, float], float] | None = None

    # Retry only on specific conditions
    retry_condition: Callable[[Exception], bool] | None = None


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

    async def execute_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute async function with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"Retry attempt {attempt}/{self.config.max_attempts}")
                result = await func(*args, **kwargs)

                if attempt > 1:
                    logger.info(f"Function succeeded on attempt {attempt}")

                return result

            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt} failed: {e!s}")

                if not self._should_retry(e, attempt):
                    break

                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.debug(f"Waiting {delay:.2f} seconds before retry")
                    await asyncio.sleep(delay)

        # All attempts failed
        raise RetryError(
            f"Function failed after {self.config.max_attempts} attempts",
            self.config.max_attempts,
            last_exception,
        )

    def execute_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute sync function with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"Retry attempt {attempt}/{self.config.max_attempts}")
                result = func(*args, **kwargs)

                if attempt > 1:
                    logger.info(f"Function succeeded on attempt {attempt}")

                return result

            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt} failed: {e!s}")

                if not self._should_retry(e, attempt):
                    break

                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.debug(f"Waiting {delay:.2f} seconds before retry")
                    time.sleep(delay)

        # All attempts failed
        raise RetryError(
            f"Function failed after {self.config.max_attempts} attempts",
            self.config.max_attempts,
            last_exception,
        )


async def retry_async(
    func: Callable[..., T], config: RetryConfig | None = None, *args, **kwargs
) -> T:
    """
    Execute async function with retry logic.

    Args:
        func: Async function to execute
        config: Retry configuration
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        RetryError: If all attempts fail
    """
    retry_config = config or RetryConfig()
    manager = RetryManager(retry_config)
    return await manager.execute_async(func, *args, **kwargs)


def retry_sync(func: Callable[..., T], config: RetryConfig | None = None, *args, **kwargs) -> T:
    """
    Execute sync function with retry logic.

    Args:
        func: Function to execute
        config: Retry configuration
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        RetryError: If all attempts fail
    """
    retry_config = config or RetryConfig()
    manager = RetryManager(retry_config)
    return manager.execute_sync(func, *args, **kwargs)


def retry_decorator(config: RetryConfig | None = None):
    """
    Decorator to add retry logic to functions.

    Args:
        config: Retry configuration

    Returns:
        Decorated function
    """
    retry_config = config or RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                return await retry_async(func, retry_config, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return retry_sync(func, retry_config, *args, **kwargs)

        return sync_wrapper

    return decorator


async def retry_with_circuit_breaker(
    func: Callable[..., T],
    retry_config: RetryConfig | None = None,
    circuit_breaker_config: CircuitBreakerConfig | None = None,
    circuit_breaker_name: str = "default",
    *args,
    **kwargs,
) -> T:
    """
    Execute function with both retry and circuit breaker protection.

    Args:
        func: Function to execute
        retry_config: Retry configuration
        circuit_breaker_config: Circuit breaker configuration
        circuit_breaker_name: Circuit breaker name
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        RetryError: If all attempts fail
        CircuitBreakerError: If circuit breaker is open
    """

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

    async def circuit_protected_func(*f_args, **f_kwargs):
        return await circuit.call(func, *f_args, **f_kwargs)

    return await retry_async(circuit_protected_func, modified_config, *args, **kwargs)


# Common retry configurations
DEFAULT_RETRY_CONFIG = RetryConfig()

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
    strategy=RetryStrategy.EXPONENTIAL,
    backoff_multiplier=1.5,
    jitter=True,
)

CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=10.0,
    strategy=RetryStrategy.LINEAR,
    jitter=True,
)

FAST_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.1,
    max_delay=1.0,
    strategy=RetryStrategy.CONSTANT,
    jitter=True,
)
