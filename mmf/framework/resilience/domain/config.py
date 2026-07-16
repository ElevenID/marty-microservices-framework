"""
Resilience Domain Configuration.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResilienceStrategy(Enum):
    """Resilience strategy for different call types."""

    INTERNAL_SERVICE = "internal_service"
    EXTERNAL_SERVICE = "external_service"
    DATABASE = "database"
    CACHE = "cache"
    CUSTOM = "custom"


class RetryStrategy(Enum):
    """Retry strategy types."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"
    CUSTOM = "custom"


class BulkheadType(Enum):
    """Types of bulkhead isolation."""

    THREAD_POOL = "thread_pool"
    SEMAPHORE = "semaphore"
    ASYNC_SEMAPHORE = "async_semaphore"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5
    success_threshold: int = 3
    failure_window_seconds: int = 60
    timeout_seconds: int = 60
    failure_exceptions: tuple[type[Exception], ...] = (Exception,)
    ignore_exceptions: tuple[type[Exception], ...] = ()
    use_failure_rate: bool = False
    failure_rate_threshold: float = 0.5
    minimum_requests: int = 10


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_factor: float = 0.1
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)
    non_retryable_exceptions: tuple[type[Exception], ...] = ()
    custom_delay_func: Callable[[int, float], float] | None = None
    retry_condition: Callable[[Exception], bool] | None = None


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead behavior."""

    max_concurrent: int = 10
    timeout_seconds: float = 30.0
    bulkhead_type: BulkheadType = BulkheadType.SEMAPHORE
    max_workers: int | None = None
    thread_name_prefix: str = "BulkheadWorker"
    queue_size: int | None = None
    reject_on_full: bool = False
    collect_metrics: bool = True
    dependency_name: str | None = None
    dependency_type: str | None = None
    enable_circuit_breaker: bool = False
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout: float = 60.0


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""

    seconds: float = 30.0


@dataclass
class ResilienceConfig:
    """Unified configuration for all resilience patterns."""

    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    bulkhead: BulkheadConfig = field(default_factory=BulkheadConfig)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)

    circuit_breaker_enabled: bool = True
    retry_enabled: bool = True
    bulkhead_enabled: bool = False
    timeout_enabled: bool = True

    strategy: ResilienceStrategy = ResilienceStrategy.INTERNAL_SERVICE
    custom_settings: dict[str, Any] = field(default_factory=dict)
