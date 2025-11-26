"""
Resilience Domain Exceptions.
"""

from enum import Enum

class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class ResilienceError(Exception):
    """Base exception for resilience errors."""


class CircuitBreakerError(ResilienceError):
    """Exception raised when circuit breaker is open."""
    def __init__(self, message: str, state: CircuitBreakerState, failure_count: int):
        super().__init__(message)
        self.state = state
        self.failure_count = failure_count

class RetryError(ResilienceError):
    """Exception raised when all retry attempts are exhausted."""
    def __init__(self, message: str, attempts: int, last_exception: Exception):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception

class BulkheadError(ResilienceError):
    """Exception raised when bulkhead capacity is exceeded."""
    def __init__(self, message: str, bulkhead_name: str, capacity: int):
        super().__init__(message)
        self.bulkhead_name = bulkhead_name
        self.capacity = capacity

class ResilienceTimeoutError(ResilienceError):
    """Exception raised when an operation times out."""

