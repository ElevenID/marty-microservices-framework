"""
Resilience Framework API

Core interfaces, data models, and contracts for the resilience framework.
Following the level contract architecture pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


class ResilienceStrategy(Enum):
    """Resilience strategy for different call types."""

    INTERNAL_SERVICE = "internal_service"  # Internal microservice calls
    EXTERNAL_SERVICE = "external_service"  # External API calls
    DATABASE = "database"  # Database operations
    CACHE = "cache"  # Cache operations
    CUSTOM = "custom"  # Custom configuration


@dataclass
class ResilienceConfig:
    """Unified configuration for all resilience patterns."""

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    circuit_breaker_expected_exception: type[Exception] | None = None

    # Retry settings
    retry_enabled: bool = True
    retry_max_attempts: int = 3
    retry_delay: float = 1.0
    retry_backoff_multiplier: float = 2.0
    retry_max_delay: float = 60.0
    retry_jitter: bool = True

    # Timeout settings
    timeout_enabled: bool = True
    timeout_duration: float = 30.0

    # Bulkhead settings
    bulkhead_enabled: bool = False
    bulkhead_max_concurrent: int = 10

    # Strategy
    strategy: ResilienceStrategy = ResilienceStrategy.INTERNAL_SERVICE

    # Custom settings
    custom_settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResilienceMetrics:
    """Resilience operation metrics."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    circuit_breaker_open_count: int = 0
    retry_count: int = 0
    timeout_count: int = 0
    bulkhead_rejected_count: int = 0
    average_response_time: float = 0.0
    last_failure_time: float | None = None
    last_success_time: float | None = None


@dataclass
class ResilienceResult:
    """Result of a resilience operation."""

    success: bool
    result: Any = None
    error: Exception | None = None
    execution_time: float = 0.0
    retries_attempted: int = 0
    circuit_breaker_triggered: bool = False
    timeout_occurred: bool = False
    bulkhead_rejected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class IResilienceManager(ABC):
    """Abstract interface for resilience managers."""

    @abstractmethod
    async def execute_resilient(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with resilience patterns applied."""
        pass

    @abstractmethod
    def execute_resilient_sync(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a synchronous function with resilience patterns applied."""
        pass

    @abstractmethod
    async def apply_resilience(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Apply resilience patterns to a function call."""
        pass

    @abstractmethod
    def get_metrics(self) -> dict[str, Any]:
        """Get resilience metrics."""
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Perform health check on resilience components."""
        pass

    @abstractmethod
    def reset_metrics(self) -> None:
        """Reset resilience metrics."""
        pass

    @abstractmethod
    def update_config(self, config: dict[str, Any]) -> None:
        """Update resilience configuration."""
        pass


class IResilienceService(ABC):
    """Abstract interface for resilience service."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the resilience service."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the resilience service."""
        pass

    @abstractmethod
    def get_manager(self) -> IResilienceManager:
        """Get the resilience manager instance."""
        pass

    @abstractmethod
    def update_config(self, config: dict[str, Any]) -> None:
        """Update service configuration."""
        pass


# Exception classes
class ResilienceError(Exception):
    """Base exception for resilience operations."""

    pass


class CircuitBreakerOpenError(ResilienceError):
    """Raised when circuit breaker is open."""

    pass


class BulkheadRejectedError(ResilienceError):
    """Raised when bulkhead rejects a request."""

    pass


class ResilienceTimeoutError(ResilienceError):
    """Raised when operation times out."""

    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: float | None = None,
        operation: str = "operation",
    ):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.operation = operation


class RetryExhaustedError(ResilienceError):
    """Raised when all retry attempts are exhausted."""

    def __init__(self, message: str = "All retry attempts exhausted", attempts: int = 0):
        super().__init__(message)
        self.attempts = attempts
