"""
Timeout Management Pattern Implementation

Provides comprehensive timeout handling for operations, requests, and services
to prevent resource exhaustion and improve system responsiveness.
"""

import asyncio
import builtins
import logging
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from .api import ResilienceTimeoutError

T = TypeVar("T")
logger = logging.getLogger(__name__)

# Import from api to avoid duplication


class TimeoutType(Enum):
    """Types of timeout strategies."""

    SIMPLE = "simple"  # Basic timeout
    SIGNAL_BASED = "signal"  # Signal-based timeout (Unix only)
    THREAD_BASED = "thread"  # Thread-based timeout
    ASYNC_WAIT_FOR = "async"  # Asyncio wait_for timeout


@dataclass
class TimeoutConfig:
    """Configuration for timeout behavior."""

    # Default timeout in seconds
    default_timeout: float = 30.0

    # Timeout strategy
    timeout_type: TimeoutType = TimeoutType.ASYNC_WAIT_FOR

    # Grace period before forced termination
    grace_period: float = 5.0

    # Enable timeout logging
    log_timeouts: bool = True

    # Custom timeout handler
    timeout_handler: Callable[[str, float], None] | None = None

    # Propagate timeout to nested operations
    propagate_timeout: bool = True

    # External dependency specific timeouts
    database_timeout: float = 10.0
    api_call_timeout: float = 15.0
    message_queue_timeout: float = 5.0
    cache_timeout: float = 2.0
    file_operation_timeout: float = 30.0

    # Circuit breaker integration
    circuit_breaker_timeout: float = 60.0  # How long to keep circuit open

    # Adaptive timeout settings
    enable_adaptive_timeout: bool = False
    adaptive_timeout_percentile: float = 0.95  # Use 95th percentile of response times
    adaptive_timeout_multiplier: float = 2.0  # Multiply percentile by this factor
    adaptive_timeout_min: float = 1.0  # Minimum adaptive timeout
    adaptive_timeout_max: float = 120.0  # Maximum adaptive timeout


class TimeoutContext:
    """Context for tracking timeout information."""

    def __init__(self, timeout_seconds: float, operation: str):
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        self.start_time = time.time()
        self.cancelled = False
        self._cancel_event = threading.Event()

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time since timeout started."""
        return time.time() - self.start_time

    @property
    def remaining_time(self) -> float:
        """Get remaining time before timeout."""
        return max(0, self.timeout_seconds - self.elapsed_time)

    def is_expired(self) -> bool:
        """Check if timeout has expired."""
        return self.elapsed_time >= self.timeout_seconds

    def cancel(self):
        """Cancel the timeout."""
        self.cancelled = True
        self._cancel_event.set()

    def wait_for_cancel(self, timeout: float | None = None) -> bool:
        """Wait for timeout to be cancelled."""
        return self._cancel_event.wait(timeout)


class TimeoutManager:
    """Manages timeout operations and contexts."""

    def __init__(self, config: TimeoutConfig | None = None):
        self.config = config or TimeoutConfig()
        self._active_timeouts: builtins.dict[str, TimeoutContext] = {}
        self._lock = threading.Lock()

        # Metrics
        self._total_operations = 0
        self._timed_out_operations = 0
        self._total_timeout_time = 0.0

    def create_timeout_context(
        self, timeout_seconds: float | None = None, operation: str = "operation"
    ) -> TimeoutContext:
        """Create a new timeout context."""
        timeout = timeout_seconds or self.config.default_timeout
        context = TimeoutContext(timeout, operation)

        with self._lock:
            self._active_timeouts[operation] = context
            self._total_operations += 1

        return context

    def remove_timeout_context(self, operation: str):
        """Remove timeout context."""
        with self._lock:
            if operation in self._active_timeouts:
                context = self._active_timeouts[operation]
                if context.is_expired():
                    self._timed_out_operations += 1
                self._total_timeout_time += context.elapsed_time
                del self._active_timeouts[operation]

    async def execute_with_timeout(
        self,
        func: Callable[..., T],
        timeout_seconds: float | None = None,
        operation: str = "async_operation",
        *args,
        **kwargs,
    ) -> T:
        """Execute async function with timeout."""
        timeout = timeout_seconds or self.config.default_timeout
        self.create_timeout_context(timeout, operation)

        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            else:
                # Run sync function in executor with timeout
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, func, *args, **kwargs), timeout=timeout
                )

            return result

        except asyncio.TimeoutError:
            if self.config.log_timeouts:
                logger.warning(f"Operation '{operation}' timed out after {timeout} seconds")

            if self.config.timeout_handler:
                self.config.timeout_handler(operation, timeout)

            raise ResilienceTimeoutError(
                f"Operation '{operation}' timed out after {timeout} seconds",
                timeout,
                operation,
            )
        finally:
            self.remove_timeout_context(operation)

    def execute_sync_with_timeout(
        self,
        func: Callable[..., T],
        timeout_seconds: float | None = None,
        operation: str = "sync_operation",
        *args,
        **kwargs,
    ) -> T:
        """Execute sync function with timeout using threading."""
        timeout = timeout_seconds or self.config.default_timeout
        self.create_timeout_context(timeout, operation)

        result = [None]
        exception = [None]
        completed = threading.Event()

        def target():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exception[0] = e
            finally:
                completed.set()

        thread = threading.Thread(target=target, daemon=True)
        thread.start()

        try:
            if completed.wait(timeout=timeout):
                if exception[0]:
                    raise exception[0]
                return result[0]
            if self.config.log_timeouts:
                logger.warning(f"Operation '{operation}' timed out after {timeout} seconds")

            if self.config.timeout_handler:
                self.config.timeout_handler(operation, timeout)

            raise ResilienceTimeoutError(
                f"Operation '{operation}' timed out after {timeout} seconds",
                timeout,
                operation,
            )
        finally:
            self.remove_timeout_context(operation)
            # Note: Thread will continue running but we can't forcefully kill it

    def get_active_timeouts(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get information about active timeouts."""
        with self._lock:
            return {
                name: {
                    "operation": context.operation,
                    "timeout_seconds": context.timeout_seconds,
                    "elapsed_time": context.elapsed_time,
                    "remaining_time": context.remaining_time,
                    "is_expired": context.is_expired(),
                }
                for name, context in self._active_timeouts.items()
            }

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get timeout manager statistics."""
        with self._lock:
            timeout_rate = self._timed_out_operations / max(1, self._total_operations)
            avg_execution_time = self._total_timeout_time / max(1, self._total_operations)

            return {
                "total_operations": self._total_operations,
                "timed_out_operations": self._timed_out_operations,
                "timeout_rate": timeout_rate,
                "average_execution_time": avg_execution_time,
                "active_timeouts": len(self._active_timeouts),
                "default_timeout": self.config.default_timeout,
            }


# Global timeout manager
_timeout_manager = TimeoutManager()


def get_timeout_manager() -> TimeoutManager:
    """Get the global timeout manager."""
    return _timeout_manager


async def with_timeout(
    func: Callable[..., T],
    timeout_seconds: float | None = None,
    operation: str = "operation",
    *args,
    **kwargs,
) -> T:
    """
    Execute async function with timeout.

    Args:
        func: Function to execute
        timeout_seconds: Timeout in seconds
        operation: Operation name for logging
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        ResilienceTimeoutError: If operation times out
    """
    manager = get_timeout_manager()
    return await manager.execute_with_timeout(func, timeout_seconds, operation, *args, **kwargs)


def with_sync_timeout(
    func: Callable[..., T],
    timeout_seconds: float | None = None,
    operation: str = "operation",
    *args,
    **kwargs,
) -> T:
    """
    Execute sync function with timeout.

    Args:
        func: Function to execute
        timeout_seconds: Timeout in seconds
        operation: Operation name for logging
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        ResilienceTimeoutError: If operation times out
    """
    manager = get_timeout_manager()
    return manager.execute_sync_with_timeout(func, timeout_seconds, operation, *args, **kwargs)


@asynccontextmanager
async def timeout_context(
    timeout_seconds: float | None = None, operation: str = "context_operation"
):
    """
    Async context manager for timeout operations.

    Args:
        timeout_seconds: Timeout in seconds
        operation: Operation name

    Yields:
        TimeoutContext: Context with timeout information

    Raises:
        ResilienceTimeoutError: If context times out
    """
    manager = get_timeout_manager()
    timeout = timeout_seconds or manager.config.default_timeout
    context = manager.create_timeout_context(timeout, operation)

    async def timeout_task():
        await asyncio.sleep(timeout)
        if not context.cancelled:
            if manager.config.log_timeouts:
                logger.warning(f"Context '{operation}' timed out after {timeout} seconds")

            if manager.config.timeout_handler:
                manager.config.timeout_handler(operation, timeout)

    timeout_handle = asyncio.create_task(timeout_task())

    try:
        yield context
        context.cancel()
        timeout_handle.cancel()

    except Exception:
        context.cancel()
        timeout_handle.cancel()
        raise

    finally:
        manager.remove_timeout_context(operation)
        if not timeout_handle.cancelled():
            timeout_handle.cancel()


@contextmanager
def sync_timeout_context(
    timeout_seconds: float | None = None, operation: str = "sync_context_operation"
):
    """
    Sync context manager for timeout operations.

    Args:
        timeout_seconds: Timeout in seconds
        operation: Operation name

    Yields:
        TimeoutContext: Context with timeout information

    Raises:
        ResilienceTimeoutError: If context times out
    """
    manager = get_timeout_manager()
    timeout = timeout_seconds or manager.config.default_timeout
    context = manager.create_timeout_context(timeout, operation)

    try:
        yield context

        if context.is_expired():
            if manager.config.log_timeouts:
                logger.warning(f"Context '{operation}' exceeded timeout of {timeout} seconds")

            if manager.config.timeout_handler:
                manager.config.timeout_handler(operation, timeout)

            raise ResilienceTimeoutError(
                f"Context '{operation}' exceeded timeout of {timeout} seconds",
                timeout,
                operation,
            )

    finally:
        manager.remove_timeout_context(operation)


def timeout_async(timeout_seconds: float | None = None, operation: str | None = None):
    """
    Decorator to add timeout to async functions.

    Args:
        timeout_seconds: Timeout in seconds
        operation: Operation name for logging

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        op_name = operation or func.__name__

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await with_timeout(func, timeout_seconds, op_name, *args, **kwargs)

        return async_wrapper

    return decorator


def timeout_sync(timeout_seconds: float | None = None, operation: str | None = None):
    """
    Decorator to add timeout to sync functions.

    Args:
        timeout_seconds: Timeout in seconds
        operation: Operation name for logging

    Returns:
        Decorated function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        op_name = operation or func.__name__

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return with_sync_timeout(func, timeout_seconds, op_name, *args, **kwargs)

        return sync_wrapper

    return decorator


# Common timeout configurations
DEFAULT_TIMEOUT_CONFIG = TimeoutConfig()

FAST_TIMEOUT_CONFIG = TimeoutConfig(
    default_timeout=5.0, timeout_type=TimeoutType.ASYNC_WAIT_FOR, log_timeouts=True
)

SLOW_TIMEOUT_CONFIG = TimeoutConfig(
    default_timeout=300.0,  # 5 minutes
    timeout_type=TimeoutType.ASYNC_WAIT_FOR,
    grace_period=30.0,
    log_timeouts=True,
)

DATABASE_TIMEOUT_CONFIG = TimeoutConfig(
    default_timeout=30.0, timeout_type=TimeoutType.ASYNC_WAIT_FOR, log_timeouts=True
)

API_TIMEOUT_CONFIG = TimeoutConfig(
    default_timeout=15.0, timeout_type=TimeoutType.ASYNC_WAIT_FOR, log_timeouts=True
)
