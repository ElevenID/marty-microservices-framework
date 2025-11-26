"""
Enhanced circuit breaker with monitoring and error classification.

Ported from Marty's resilience framework to provide advanced circuit breaker
capabilities for microservices.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ErrorClassifier(Protocol):
    """Protocol for error classification in circuit breakers."""

    def should_count_as_failure(self, exception: Exception) -> bool:
        """Determine if an exception should count as a failure."""
        ...


class DefaultErrorClassifier:
    """Default error classifier for circuit breakers."""

    def __init__(
        self,
        counted_exceptions: tuple[type[Exception], ...] = (Exception,),
        ignored_exceptions: tuple[type[Exception], ...] = (),
    ):
        self.counted_exceptions = counted_exceptions
        self.ignored_exceptions = ignored_exceptions

    def should_count_as_failure(self, exception: Exception) -> bool:
        """Determine if an exception should count as a failure."""
        # Check ignored exceptions first (more specific)
        for exc_type in self.ignored_exceptions:
            if isinstance(exception, exc_type):
                return False

        # Check counted exceptions
        for exc_type in self.counted_exceptions:
            if isinstance(exception, exc_type):
                return True

        return False


@dataclass
class EnhancedCircuitBreakerConfig:
    """Configuration for enhanced circuit breaker."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: tuple[type[Exception], ...] = (Exception,)

    # Success threshold for half-open state
    success_threshold: int = 3

    # Monitoring and metrics
    collect_metrics: bool = True
    log_state_changes: bool = True

    # Error classification
    error_classifier: ErrorClassifier | None = None

    # Advanced features
    failure_rate_threshold: float = 0.5  # 50% failure rate
    minimum_throughput: int = 10  # Minimum calls before failure rate calculation
    sliding_window_size: int = 100  # Size of sliding window for failure rate


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, state: CircuitBreakerState, message: str = "Circuit breaker is open"):
        self.state = state
        super().__init__(message)


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker operations."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    circuit_open_time: float = 0.0
    state_changes: int = 0
    last_failure_time: float | None = None

    @property
    def failure_rate(self) -> float:
        """Calculate current failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    @property
    def success_rate(self) -> float:
        """Calculate current success rate."""
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls


class EnhancedCircuitBreaker:
    """Enhanced circuit breaker with monitoring and error classification."""

    def __init__(self, name: str, config: EnhancedCircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.state_change_time = time.time()

        # Metrics
        self.metrics = CircuitBreakerMetrics()

        # Error classifier
        self.error_classifier = config.error_classifier or DefaultErrorClassifier(
            counted_exceptions=config.expected_exception
        )

        # Sliding window for failure rate calculation
        self.call_results: list[bool] = []  # True for success, False for failure

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection."""
        async with self._lock:
            await self._check_state()

            if self.state == CircuitBreakerState.OPEN:
                raise CircuitBreakerError(self.state, f"Circuit breaker '{self.name}' is open")

        try:
            result = func(*args, **kwargs)
            if asyncio.iscoroutine(result):
                result = await result

            async with self._lock:
                await self._on_success()

            return result

        except Exception as e:
            async with self._lock:
                should_count = self.error_classifier.should_count_as_failure(e)
                if should_count:
                    await self._on_failure()
                else:
                    await self._on_ignored_error()

            raise

    async def _check_state(self) -> None:
        """Check and update circuit breaker state."""
        current_time = time.time()

        if self.state == CircuitBreakerState.OPEN:
            if current_time - self.state_change_time >= self.config.recovery_timeout:
                await self._change_state(CircuitBreakerState.HALF_OPEN)
        elif self.state == CircuitBreakerState.HALF_OPEN:
            if self.success_count >= self.config.success_threshold:
                await self._change_state(CircuitBreakerState.CLOSED)

    async def _on_success(self) -> None:
        """Handle successful call."""
        self.metrics.total_calls += 1
        self.metrics.successful_calls += 1
        self.call_results.append(True)

        # Maintain sliding window size
        if len(self.call_results) > self.config.sliding_window_size:
            self.call_results.pop(0)

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = 0  # Reset failure count on success

    async def _on_failure(self) -> None:
        """Handle failed call."""
        self.metrics.total_calls += 1
        self.metrics.failed_calls += 1
        self.metrics.last_failure_time = time.time()
        self.call_results.append(False)

        # Maintain sliding window size
        if len(self.call_results) > self.config.sliding_window_size:
            self.call_results.pop(0)

        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state in [CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN]:
            await self._check_failure_threshold()

    async def _on_ignored_error(self) -> None:
        """Handle ignored error (doesn't count as failure)."""
        self.metrics.total_calls += 1
        # Don't count as success or failure for circuit breaker logic

        if self.config.log_state_changes:
            logger.debug("Ignored error in circuit breaker '%s'", self.name)

    async def _check_failure_threshold(self) -> None:
        """Check if failure threshold is exceeded."""
        should_open = False

        # Check simple failure count threshold
        if self.failure_count >= self.config.failure_threshold:
            should_open = True

        # Check failure rate threshold (if we have enough data)
        if (
            len(self.call_results) >= self.config.minimum_throughput
            and self.config.failure_rate_threshold > 0
        ):
            recent_failures = sum(1 for result in self.call_results if not result)
            failure_rate = recent_failures / len(self.call_results)

            if failure_rate >= self.config.failure_rate_threshold:
                should_open = True

        if should_open and self.state != CircuitBreakerState.OPEN:
            await self._change_state(CircuitBreakerState.OPEN)

    async def _change_state(self, new_state: CircuitBreakerState) -> None:
        """Change circuit breaker state."""
        old_state = self.state
        self.state = new_state
        self.state_change_time = time.time()
        self.metrics.state_changes += 1

        # Reset counters based on new state
        if new_state == CircuitBreakerState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitBreakerState.HALF_OPEN:
            self.success_count = 0
        elif new_state == CircuitBreakerState.OPEN:
            self.metrics.circuit_open_time = time.time()

        if self.config.log_state_changes:
            logger.info(
                "Circuit breaker '%s' state changed from %s to %s",
                self.name,
                old_state.value,
                new_state.value,
            )

    async def force_open(self) -> None:
        """Force circuit breaker to open state."""
        async with self._lock:
            await self._change_state(CircuitBreakerState.OPEN)

    async def force_close(self) -> None:
        """Force circuit breaker to closed state."""
        async with self._lock:
            await self._change_state(CircuitBreakerState.CLOSED)

    async def force_half_open(self) -> None:
        """Force circuit breaker to half-open state."""
        async with self._lock:
            await self._change_state(CircuitBreakerState.HALF_OPEN)

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self.state

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics."""
        return self.metrics

    def get_status(self) -> dict[str, Any]:
        """Get comprehensive status information."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "metrics": {
                "total_calls": self.metrics.total_calls,
                "successful_calls": self.metrics.successful_calls,
                "failed_calls": self.metrics.failed_calls,
                "failure_rate": self.metrics.failure_rate,
                "success_rate": self.metrics.success_rate,
                "state_changes": self.metrics.state_changes,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "failure_rate_threshold": self.config.failure_rate_threshold,
                "minimum_throughput": self.config.minimum_throughput,
            },
            "last_failure_time": self.last_failure_time,
            "state_change_time": self.state_change_time,
        }


# Global registry of circuit breakers
_circuit_breakers: dict[str, EnhancedCircuitBreaker] = {}


def get_circuit_breaker(
    name: str, config: EnhancedCircuitBreakerConfig | None = None
) -> EnhancedCircuitBreaker:
    """Get or create a circuit breaker."""
    if name not in _circuit_breakers:
        if config is None:
            config = EnhancedCircuitBreakerConfig()
        _circuit_breakers[name] = EnhancedCircuitBreaker(name, config)
    return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict[str, EnhancedCircuitBreaker]:
    """Get all registered circuit breakers."""
    return _circuit_breakers.copy()


async def circuit_breaker_decorator(name: str, config: EnhancedCircuitBreakerConfig | None = None):
    """Decorator for circuit breaker protection."""

    def decorator(func: Callable[..., Any]):
        circuit_breaker = get_circuit_breaker(name, config)

        async def wrapper(*args, **kwargs):
            return await circuit_breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator
