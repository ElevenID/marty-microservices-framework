"""
Circuit Breaker Pattern Implementation.
"""

import asyncio
import threading
import time
from collections import deque
from collections.abc import Callable
from functools import wraps
from typing import Any, Generic, TypeVar

from mmf.framework.resilience.domain.config import CircuitBreakerConfig
from mmf.framework.resilience.domain.exceptions import (
    CircuitBreakerError,
    CircuitBreakerState,
)

T = TypeVar("T")


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker implementation with configurable failure handling.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        # Circuit state
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._last_request_time = 0.0

        # Sliding window for failure tracking
        self._request_window: deque = deque(maxlen=1000)
        self._lock = threading.RLock()

        # Metrics
        self._total_requests = 0
        self._total_failures = 0
        self._total_successes = 0
        self._state_transitions = 0

    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        with self._lock:
            return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        with self._lock:
            return self._failure_count

    @property
    def success_count(self) -> int:
        """Get current success count."""
        with self._lock:
            return self._success_count

    @property
    def failure_rate(self) -> float:
        """Calculate current failure rate."""
        with self._lock:
            if not self._request_window:
                return 0.0

            now = time.time()
            window_start = now - self.config.failure_window_seconds

            # Count requests in window
            recent_requests = [
                req for req in self._request_window if req["timestamp"] >= window_start
            ]

            if len(recent_requests) < self.config.minimum_requests:
                return 0.0

            failures = sum(1 for req in recent_requests if not req["success"])
            return failures / len(recent_requests)

    def _should_attempt_request(self) -> bool:
        """Check if request should be attempted based on current state."""
        current_time = time.time()

        if self._state == CircuitBreakerState.CLOSED:
            return True
        if self._state == CircuitBreakerState.OPEN:
            # Check if timeout period has passed
            if current_time - self._last_failure_time >= self.config.timeout_seconds:
                self._transition_to_half_open()
                return True
            return False
        if self._state == CircuitBreakerState.HALF_OPEN:
            return True

        return False

    def _record_success(self) -> None:
        """Record a successful request."""
        current_time = time.time()

        with self._lock:
            self._success_count += 1
            self._total_successes += 1
            self._total_requests += 1
            self._last_request_time = current_time

            # Add to sliding window
            self._request_window.append({"timestamp": current_time, "success": True})

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()

    def _record_failure(self, exception: Exception) -> None:
        """Record a failed request."""
        current_time = time.time()

        # Check if exception should be ignored
        if isinstance(exception, self.config.ignore_exceptions):
            return

        # Check if exception counts as failure
        if not isinstance(exception, self.config.failure_exceptions):
            return

        with self._lock:
            self._failure_count += 1
            self._total_failures += 1
            self._total_requests += 1
            self._last_failure_time = current_time
            self._last_request_time = current_time

            # Add to sliding window
            self._request_window.append(
                {
                    "timestamp": current_time,
                    "success": False,
                    "exception": type(exception).__name__,
                }
            )

            # Check if circuit should open
            if self._should_open_circuit():
                self._transition_to_open()

    def _should_open_circuit(self) -> bool:
        """Check if circuit should be opened based on failures."""
        if self.config.use_failure_rate:
            return (
                self.failure_rate >= self.config.failure_rate_threshold
                and len(self._request_window) >= self.config.minimum_requests
            )
        return self._failure_count >= self.config.failure_threshold

    def _transition_to_open(self) -> None:
        """Transition circuit to OPEN state."""
        if self._state != CircuitBreakerState.OPEN:
            self._state = CircuitBreakerState.OPEN
            self._state_transitions += 1
            self._reset_counters()

    def _transition_to_half_open(self) -> None:
        """Transition circuit to HALF_OPEN state."""
        if self._state != CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.HALF_OPEN
            self._state_transitions += 1
            self._reset_counters()

    def _transition_to_closed(self) -> None:
        """Transition circuit to CLOSED state."""
        if self._state != CircuitBreakerState.CLOSED:
            self._state = CircuitBreakerState.CLOSED
            self._state_transitions += 1
            self._reset_counters()

    def _reset_counters(self) -> None:
        """Reset failure and success counters."""
        self._failure_count = 0
        self._success_count = 0

    async def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """
        Execute a function through the circuit breaker.
        """
        if not self._should_attempt_request():
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is {self.state.value}",
                self.state,
                self.failure_count,
            )

        try:
            # Execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self._record_success()
            return result

        except Exception as e:
            self._record_failure(e)
            raise

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = 0.0
            self._last_request_time = 0.0
            self._request_window.clear()

    def force_open(self) -> None:
        """Force circuit breaker to OPEN state."""
        with self._lock:
            self._transition_to_open()

    def force_close(self) -> None:
        """Force circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to_closed()

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "total_requests": self._total_requests,
                "total_failures": self._total_failures,
                "total_successes": self._total_successes,
                "failure_rate": self.failure_rate,
                "state_transitions": self._state_transitions,
                "last_failure_time": self._last_failure_time,
                "last_request_time": self._last_request_time,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                    "failure_rate_threshold": self.config.failure_rate_threshold,
                    "use_failure_rate": self.config.use_failure_rate,
                },
            }


# Global registry for circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}
_registry_lock = threading.Lock()


def get_circuit_breaker(name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    with _registry_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name, config)
        return _circuit_breakers[name]


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Get all registered circuit breakers."""
    with _registry_lock:
        return _circuit_breakers.copy()


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers to initial state."""
    with _registry_lock:
        for cb in _circuit_breakers.values():
            cb.reset()


def get_circuit_breaker_stats() -> dict[str, dict[str, Any]]:
    """Get statistics for all circuit breakers."""
    with _registry_lock:
        return {name: cb.get_stats() for name, cb in _circuit_breakers.items()}
