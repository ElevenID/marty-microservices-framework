"""
Circuit Breaker Integration for Service Discovery

Circuit breaker patterns for service discovery to handle service failures
gracefully and prevent cascade failures in distributed systems.
"""

import asyncio
import builtins
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerStrategy(Enum):
    """Circuit breaker strategies."""

    FAILURE_COUNT = "failure_count"  # Based on failure count
    FAILURE_RATE = "failure_rate"  # Based on failure percentage
    RESPONSE_TIME = "response_time"  # Based on response time
    CUSTOM = "custom"  # Custom strategy


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    # Strategy configuration
    strategy: CircuitBreakerStrategy = CircuitBreakerStrategy.FAILURE_COUNT

    # Failure count strategy
    failure_threshold: int = 5
    success_threshold: int = 3  # Successes needed in half-open to close

    # Failure rate strategy
    failure_rate_threshold: float = 0.5  # 50% failure rate
    minimum_request_threshold: int = 10  # Min requests before calculating rate

    # Response time strategy
    response_time_threshold: float = 5.0  # Seconds
    slow_request_threshold: int = 5  # Number of slow requests

    # Timing configuration
    timeout: float = 60.0  # Time to wait before trying half-open
    half_open_timeout: float = 30.0  # Time to stay in half-open
    half_open_max_calls: int = 3  # Max calls allowed in half-open

    # Window configuration
    sliding_window_size: int = 100  # Size of sliding window for statistics
    time_window_size: float = 60.0  # Time window in seconds

    # Recovery configuration
    recovery_timeout: float = 60.0
    exponential_backoff: bool = True
    max_recovery_timeout: float = 300.0  # 5 minutes max
    backoff_multiplier: float = 2.0

    # Monitoring
    enable_metrics: bool = True
    state_change_callback: Callable | None = None

    # Fallback configuration
    fallback_enabled: bool = True
    fallback_function: Callable | None = None


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker."""

    # State information
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    state_changed_at: float = field(default_factory=time.time)

    # Request statistics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Timing statistics
    total_response_time: float = 0.0
    slow_requests: int = 0

    # Window statistics
    recent_requests: builtins.list[bool] = field(default_factory=list)  # True for success
    recent_response_times: builtins.list[float] = field(default_factory=list)
    window_start_time: float = field(default_factory=time.time)

    # Half-open statistics
    half_open_requests: int = 0
    half_open_successes: int = 0
    half_open_failures: int = 0

    # State change history
    state_changes: builtins.list[builtins.tuple[CircuitBreakerState, float]] = field(
        default_factory=list
    )

    def get_failure_rate(self) -> float:
        """Calculate current failure rate."""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    def get_recent_failure_rate(self) -> float:
        """Calculate failure rate in recent window."""
        if not self.recent_requests:
            return 0.0

        failures = sum(1 for success in self.recent_requests if not success)
        return failures / len(self.recent_requests)

    def get_average_response_time(self) -> float:
        """Calculate average response time."""
        if self.total_requests == 0:
            return 0.0
        return self.total_response_time / self.total_requests

    def get_recent_average_response_time(self) -> float:
        """Calculate average response time in recent window."""
        if not self.recent_response_times:
            return 0.0
        return sum(self.recent_response_times) / len(self.recent_response_times)


class CircuitBreakerException(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str, state: CircuitBreakerState):
        super().__init__(message)
        self.state = state


class CircuitBreaker:
    """Circuit breaker implementation for service discovery."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.metrics = CircuitBreakerMetrics()
        self._lock = threading.RLock()
        self._recovery_attempts = 0

        # Validate configuration
        self._validate_config()

    def _validate_config(self):
        """Validate circuit breaker configuration."""
        if self.config.failure_threshold <= 0:
            raise ValueError("Failure threshold must be positive")

        if self.config.timeout <= 0:
            raise ValueError("Timeout must be positive")

        if not 0 < self.config.failure_rate_threshold <= 1:
            raise ValueError("Failure rate threshold must be between 0 and 1")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""

        # Check if we can proceed
        await self._check_state()

        start_time = time.time()

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Record success
            response_time = time.time() - start_time
            await self._record_success(response_time)

            return result

        except Exception:
            # Record failure
            response_time = time.time() - start_time
            await self._record_failure(response_time)
            raise

    async def _check_state(self):
        """Check circuit breaker state and determine if request can proceed."""

        with self._lock:
            current_time = time.time()

            if self.metrics.state == CircuitBreakerState.CLOSED:
                # Normal operation - check if we should open
                if self._should_open():
                    await self._change_state(CircuitBreakerState.OPEN)
                    raise CircuitBreakerException(
                        f"Circuit breaker opened for {self.name}",
                        CircuitBreakerState.OPEN,
                    )

            elif self.metrics.state == CircuitBreakerState.OPEN:
                # Check if we should try half-open
                time_since_open = current_time - self.metrics.state_changed_at
                recovery_timeout = self._get_recovery_timeout()

                if time_since_open >= recovery_timeout:
                    await self._change_state(CircuitBreakerState.HALF_OPEN)
                else:
                    # Still open - reject request
                    if self.config.fallback_enabled and self.config.fallback_function:
                        return await self._execute_fallback()

                    raise CircuitBreakerException(
                        f"Circuit breaker open for {self.name} "
                        f"(recovery in {recovery_timeout - time_since_open:.1f}s)",
                        CircuitBreakerState.OPEN,
                    )

            elif self.metrics.state == CircuitBreakerState.HALF_OPEN:
                # Check if we've exceeded half-open limits
                if self.metrics.half_open_requests >= self.config.half_open_max_calls:
                    # Too many requests in half-open, reopen
                    await self._change_state(CircuitBreakerState.OPEN)
                    raise CircuitBreakerException(
                        f"Circuit breaker reopened for {self.name} (half-open limit exceeded)",
                        CircuitBreakerState.OPEN,
                    )

                # Check half-open timeout
                time_since_half_open = current_time - self.metrics.state_changed_at
                if time_since_half_open >= self.config.half_open_timeout:
                    # Half-open timeout - reopen
                    await self._change_state(CircuitBreakerState.OPEN)
                    raise CircuitBreakerException(
                        f"Circuit breaker reopened for {self.name} (half-open timeout)",
                        CircuitBreakerState.OPEN,
                    )

    def _should_open(self) -> bool:
        """Check if circuit breaker should open based on strategy."""

        if self.config.strategy == CircuitBreakerStrategy.FAILURE_COUNT:
            return self.metrics.failed_requests >= self.config.failure_threshold

        if self.config.strategy == CircuitBreakerStrategy.FAILURE_RATE:
            if self.metrics.total_requests < self.config.minimum_request_threshold:
                return False

            failure_rate = self.metrics.get_recent_failure_rate()
            return failure_rate >= self.config.failure_rate_threshold

        if self.config.strategy == CircuitBreakerStrategy.RESPONSE_TIME:
            return self.metrics.slow_requests >= self.config.slow_request_threshold

        return False

    def _get_recovery_timeout(self) -> float:
        """Get recovery timeout with optional exponential backoff."""

        if not self.config.exponential_backoff:
            return self.config.recovery_timeout

        # Calculate exponential backoff
        backoff_timeout = self.config.recovery_timeout * (
            self.config.backoff_multiplier**self._recovery_attempts
        )

        return min(backoff_timeout, self.config.max_recovery_timeout)

    async def _change_state(self, new_state: CircuitBreakerState):
        """Change circuit breaker state."""

        old_state = self.metrics.state
        self.metrics.state = new_state
        self.metrics.state_changed_at = time.time()

        # Record state change
        self.metrics.state_changes.append((new_state, self.metrics.state_changed_at))

        # Reset half-open counters
        if new_state == CircuitBreakerState.HALF_OPEN:
            self.metrics.half_open_requests = 0
            self.metrics.half_open_successes = 0
            self.metrics.half_open_failures = 0

        # Update recovery attempts
        if new_state == CircuitBreakerState.OPEN:
            self._recovery_attempts += 1
        elif new_state == CircuitBreakerState.CLOSED:
            self._recovery_attempts = 0

        # Call state change callback
        if self.config.state_change_callback:
            try:
                if asyncio.iscoroutinefunction(self.config.state_change_callback):
                    await self.config.state_change_callback(
                        self.name, old_state, new_state, self.metrics
                    )
                else:
                    self.config.state_change_callback(self.name, old_state, new_state, self.metrics)
            except Exception as e:
                logger.error("State change callback failed: %s", e)

        logger.info(
            "Circuit breaker %s state changed: %s -> %s",
            self.name,
            old_state.value,
            new_state.value,
        )

    async def _record_success(self, response_time: float):
        """Record successful request."""

        with self._lock:
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.total_response_time += response_time

            # Update sliding window
            self._update_sliding_window(True, response_time)

            # Check for slow response
            if response_time > self.config.response_time_threshold:
                self.metrics.slow_requests += 1

            # Handle half-open state
            if self.metrics.state == CircuitBreakerState.HALF_OPEN:
                self.metrics.half_open_requests += 1
                self.metrics.half_open_successes += 1

                # Check if we should close
                if self.metrics.half_open_successes >= self.config.success_threshold:
                    await self._change_state(CircuitBreakerState.CLOSED)

    async def _record_failure(self, response_time: float):
        """Record failed request."""

        with self._lock:
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.total_response_time += response_time

            # Update sliding window
            self._update_sliding_window(False, response_time)

            # Handle half-open state
            if self.metrics.state == CircuitBreakerState.HALF_OPEN:
                self.metrics.half_open_requests += 1
                self.metrics.half_open_failures += 1

                # Reopen on any failure in half-open
                await self._change_state(CircuitBreakerState.OPEN)

    def _update_sliding_window(self, success: bool, response_time: float):
        """Update sliding window statistics."""

        current_time = time.time()

        # Add new data point
        self.metrics.recent_requests.append(success)
        self.metrics.recent_response_times.append(response_time)

        # Remove old data points (sliding window)
        if len(self.metrics.recent_requests) > self.config.sliding_window_size:
            self.metrics.recent_requests.pop(0)
            self.metrics.recent_response_times.pop(0)

        # Remove data points outside time window
        cutoff_time = current_time - self.config.time_window_size
        while self.metrics.recent_requests and self.metrics.window_start_time < cutoff_time:
            self.metrics.recent_requests.pop(0)
            self.metrics.recent_response_times.pop(0)
            self.metrics.window_start_time = current_time

    async def _execute_fallback(self) -> Any:
        """Execute fallback function."""

        if not self.config.fallback_function:
            raise CircuitBreakerException(
                f"Circuit breaker open for {self.name} and no fallback configured",
                self.metrics.state,
            )

        try:
            if asyncio.iscoroutinefunction(self.config.fallback_function):
                return await self.config.fallback_function()
            return self.config.fallback_function()
        except Exception as e:
            logger.error("Fallback function failed for %s: %s", self.name, e)
            raise CircuitBreakerException(
                f"Circuit breaker open for {self.name} and fallback failed: {e}",
                self.metrics.state,
            )

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self.metrics.state

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics."""
        return self.metrics

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.metrics.state.value,
                "state_changed_at": self.metrics.state_changed_at,
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "failure_rate": self.metrics.get_failure_rate(),
                "recent_failure_rate": self.metrics.get_recent_failure_rate(),
                "average_response_time": self.metrics.get_average_response_time(),
                "recent_average_response_time": self.metrics.get_recent_average_response_time(),
                "slow_requests": self.metrics.slow_requests,
                "recovery_attempts": self._recovery_attempts,
                "half_open_requests": self.metrics.half_open_requests,
                "half_open_successes": self.metrics.half_open_successes,
                "half_open_failures": self.metrics.half_open_failures,
                "state_changes": len(self.metrics.state_changes),
            }

    async def force_open(self):
        """Force circuit breaker to open state."""
        await self._change_state(CircuitBreakerState.OPEN)

    async def force_close(self):
        """Force circuit breaker to closed state."""
        await self._change_state(CircuitBreakerState.CLOSED)

    async def force_half_open(self):
        """Force circuit breaker to half-open state."""
        await self._change_state(CircuitBreakerState.HALF_OPEN)

    def reset(self):
        """Reset circuit breaker metrics."""
        with self._lock:
            self.metrics = CircuitBreakerMetrics()
            self._recovery_attempts = 0


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""

    def __init__(self):
        self._circuit_breakers: builtins.dict[str, CircuitBreaker] = {}
        self._default_config = CircuitBreakerConfig()

    def set_default_config(self, config: CircuitBreakerConfig):
        """Set default configuration for new circuit breakers."""
        self._default_config = config

    def get_circuit_breaker(
        self, name: str, config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Get or create circuit breaker."""

        if name not in self._circuit_breakers:
            breaker_config = config or self._default_config
            self._circuit_breakers[name] = CircuitBreaker(name, breaker_config)

        return self._circuit_breakers[name]

    def remove_circuit_breaker(self, name: str):
        """Remove circuit breaker."""
        self._circuit_breakers.pop(name, None)

    def get_all_stats(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get statistics for all circuit breakers."""
        return {name: breaker.get_stats() for name, breaker in self._circuit_breakers.items()}

    def get_open_circuit_breakers(self) -> builtins.list[str]:
        """Get list of open circuit breakers."""
        return [
            name
            for name, breaker in self._circuit_breakers.items()
            if breaker.get_state() == CircuitBreakerState.OPEN
        ]

    def get_half_open_circuit_breakers(self) -> builtins.list[str]:
        """Get list of half-open circuit breakers."""
        return [
            name
            for name, breaker in self._circuit_breakers.items()
            if breaker.get_state() == CircuitBreakerState.HALF_OPEN
        ]

    async def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._circuit_breakers.values():
            breaker.reset()


# Decorator for circuit breaker protection
def circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
    manager: CircuitBreakerManager | None = None,
):
    """Decorator to protect function with circuit breaker."""

    def decorator(func):
        breaker_manager = manager or CircuitBreakerManager()
        breaker = breaker_manager.get_circuit_breaker(name, config)

        async def async_wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            return asyncio.run(breaker.call(func, *args, **kwargs))

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Global circuit breaker manager instance
global_circuit_breaker_manager = CircuitBreakerManager()


# Convenience functions
def get_circuit_breaker(name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
    """Get circuit breaker from global manager."""
    return global_circuit_breaker_manager.get_circuit_breaker(name, config)


def get_all_circuit_breaker_stats() -> builtins.dict[str, builtins.dict[str, Any]]:
    """Get stats for all circuit breakers."""
    return global_circuit_breaker_manager.get_all_stats()


# Pre-configured circuit breaker configs
AGGRESSIVE_CONFIG = CircuitBreakerConfig(failure_threshold=3, timeout=30.0, half_open_max_calls=2)

CONSERVATIVE_CONFIG = CircuitBreakerConfig(
    failure_threshold=10, timeout=120.0, half_open_max_calls=5, success_threshold=5
)

FAST_RECOVERY_CONFIG = CircuitBreakerConfig(
    failure_threshold=5, timeout=30.0, exponential_backoff=False
)
