"""
Bulkhead Pattern Implementation

Provides resource isolation through thread pools and semaphores to prevent
one failing component from consuming all resources and affecting other components.
"""

import asyncio
import builtins
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


class BulkheadType(Enum):
    """Types of bulkhead isolation."""

    THREAD_POOL = "thread_pool"
    SEMAPHORE = "semaphore"
    ASYNC_SEMAPHORE = "async_semaphore"


class BulkheadError(Exception):
    """Exception raised when bulkhead capacity is exceeded."""

    def __init__(self, message: str, bulkhead_name: str, capacity: int):
        super().__init__(message)
        self.bulkhead_name = bulkhead_name
        self.capacity = capacity


@dataclass
class BulkheadConfig:
    """Configuration for bulkhead behavior."""

    # Maximum concurrent operations
    max_concurrent: int = 10

    # Timeout for acquiring resource (seconds)
    timeout_seconds: float = 30.0

    # Type of bulkhead isolation
    bulkhead_type: BulkheadType = BulkheadType.SEMAPHORE

    # Thread pool specific settings
    max_workers: int | None = None
    thread_name_prefix: str = "BulkheadWorker"

    # Queue size for thread pool
    queue_size: int | None = None

    # Reject requests when capacity exceeded
    reject_on_full: bool = False

    # Enable metrics collection
    collect_metrics: bool = True

    # External dependency specific settings
    dependency_name: str | None = None
    dependency_type: str | None = None  # "database", "api", "cache", "message_queue", etc.

    # Circuit breaker integration for bulkheads
    enable_circuit_breaker: bool = False
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_timeout: float = 60.0


class BulkheadPool(ABC):
    """Abstract base class for bulkhead implementations."""

    def __init__(self, name: str, config: BulkheadConfig):
        self.name = name
        self.config = config
        self._lock = threading.RLock()

        # Metrics
        self._total_requests = 0
        self._active_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._rejected_requests = 0
        self._total_wait_time = 0.0
        self._max_concurrent_reached = 0

    @abstractmethod
    async def execute_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute async function with bulkhead protection."""

    @abstractmethod
    def execute_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute sync function with bulkhead protection."""

    @abstractmethod
    def get_current_load(self) -> int:
        """Get current number of active operations."""

    @abstractmethod
    def get_capacity(self) -> int:
        """Get maximum capacity."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if resources are available."""

    def _record_request_start(self):
        """Record start of request."""
        with self._lock:
            self._total_requests += 1
            self._active_requests += 1
            self._max_concurrent_reached = max(self._max_concurrent_reached, self._active_requests)

    def _record_request_end(self, success: bool):
        """Record end of request."""
        with self._lock:
            self._active_requests -= 1
            if success:
                self._successful_requests += 1
            else:
                self._failed_requests += 1

    def _record_rejection(self):
        """Record rejected request."""
        with self._lock:
            self._rejected_requests += 1

    def _record_wait_time(self, wait_time: float):
        """Record wait time for resource acquisition."""
        with self._lock:
            self._total_wait_time += wait_time

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get bulkhead statistics."""
        with self._lock:
            avg_wait_time = (
                self._total_wait_time / self._total_requests if self._total_requests > 0 else 0.0
            )

            return {
                "name": self.name,
                "type": self.config.bulkhead_type.value,
                "capacity": self.get_capacity(),
                "current_load": self.get_current_load(),
                "total_requests": self._total_requests,
                "active_requests": self._active_requests,
                "successful_requests": self._successful_requests,
                "failed_requests": self._failed_requests,
                "rejected_requests": self._rejected_requests,
                "max_concurrent_reached": self._max_concurrent_reached,
                "average_wait_time": avg_wait_time,
                "success_rate": (
                    self._successful_requests
                    / max(1, self._total_requests - self._rejected_requests)
                ),
                "rejection_rate": (self._rejected_requests / max(1, self._total_requests)),
            }

    def reset_stats(self):
        """Reset all bulkhead statistics."""
        with self._lock:
            self._total_requests = 0
            self._active_requests = 0
            self._successful_requests = 0
            self._failed_requests = 0
            self._rejected_requests = 0
            self._max_concurrent_reached = 0
            self._total_wait_time = 0.0


class SemaphoreBulkhead(BulkheadPool):
    """Semaphore-based bulkhead for controlling concurrent access."""

    def __init__(self, name: str, config: BulkheadConfig):
        super().__init__(name, config)
        self._semaphore = threading.Semaphore(config.max_concurrent)
        self._async_semaphore = asyncio.Semaphore(config.max_concurrent)

    async def execute_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute async function with semaphore protection."""
        start_time = time.time()

        try:
            # Try to acquire semaphore
            acquired = await asyncio.wait_for(
                self._async_semaphore.acquire(), timeout=self.config.timeout_seconds
            )

            if not acquired:
                self._record_rejection()
                raise BulkheadError(
                    f"Could not acquire semaphore for bulkhead '{self.name}'",
                    self.name,
                    self.config.max_concurrent,
                )

            wait_time = time.time() - start_time
            self._record_wait_time(wait_time)
            self._record_request_start()

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    # Run sync function in thread pool
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, func, *args, **kwargs)

                self._record_request_end(True)
                return result

            except Exception:
                self._record_request_end(False)
                raise
            finally:
                self._async_semaphore.release()

        except asyncio.TimeoutError:
            self._record_rejection()
            raise BulkheadError(
                f"Timeout acquiring semaphore for bulkhead '{self.name}'",
                self.name,
                self.config.max_concurrent,
            )

    def execute_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute sync function with semaphore protection."""
        start_time = time.time()

        acquired = self._semaphore.acquire(timeout=self.config.timeout_seconds)

        if not acquired:
            self._record_rejection()
            raise BulkheadError(
                f"Could not acquire semaphore for bulkhead '{self.name}'",
                self.name,
                self.config.max_concurrent,
            )

        wait_time = time.time() - start_time
        self._record_wait_time(wait_time)
        self._record_request_start()

        try:
            result = func(*args, **kwargs)
            self._record_request_end(True)
            return result

        except Exception:
            self._record_request_end(False)
            raise
        finally:
            self._semaphore.release()

    def get_current_load(self) -> int:
        """Get current number of active operations."""
        return self.config.max_concurrent - self._semaphore._value

    def get_capacity(self) -> int:
        """Get maximum capacity."""
        return self.config.max_concurrent

    def is_available(self) -> bool:
        """Check if resources are available."""
        return self._semaphore._value > 0


class ThreadPoolBulkhead(BulkheadPool):
    """Thread pool-based bulkhead for CPU-bound operations."""

    def __init__(self, name: str, config: BulkheadConfig):
        super().__init__(name, config)

        max_workers = config.max_workers or config.max_concurrent
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=f"{config.thread_name_prefix}-{name}",
        )
        self._active_futures = set()
        self._futures_lock = threading.Lock()

    async def execute_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function in thread pool."""
        if self.config.reject_on_full and not self.is_available():
            self._record_rejection()
            raise BulkheadError(
                f"Thread pool bulkhead '{self.name}' is at capacity",
                self.name,
                self.get_capacity(),
            )

        start_time = time.time()
        self._record_request_start()

        try:
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(self._executor, func, *args, **kwargs)

            with self._futures_lock:
                self._active_futures.add(future)

            try:
                result = await asyncio.wait_for(future, timeout=self.config.timeout_seconds)
                wait_time = time.time() - start_time
                self._record_wait_time(wait_time)
                self._record_request_end(True)
                return result

            except asyncio.TimeoutError:
                future.cancel()
                self._record_request_end(False)
                raise BulkheadError(
                    f"Timeout executing in thread pool bulkhead '{self.name}'",
                    self.name,
                    self.get_capacity(),
                )
            finally:
                with self._futures_lock:
                    self._active_futures.discard(future)

        except Exception:
            self._record_request_end(False)
            raise

    def execute_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function in thread pool synchronously."""
        if self.config.reject_on_full and not self.is_available():
            self._record_rejection()
            raise BulkheadError(
                f"Thread pool bulkhead '{self.name}' is at capacity",
                self.name,
                self.get_capacity(),
            )

        start_time = time.time()
        self._record_request_start()

        try:
            future = self._executor.submit(func, *args, **kwargs)

            with self._futures_lock:
                self._active_futures.add(future)

            try:
                result = future.result(timeout=self.config.timeout_seconds)
                wait_time = time.time() - start_time
                self._record_wait_time(wait_time)
                self._record_request_end(True)
                return result

            except TimeoutError:
                future.cancel()
                self._record_request_end(False)
                raise BulkheadError(
                    f"Timeout executing in thread pool bulkhead '{self.name}'",
                    self.name,
                    self.get_capacity(),
                )
            finally:
                with self._futures_lock:
                    self._active_futures.discard(future)

        except Exception:
            self._record_request_end(False)
            raise

    def get_current_load(self) -> int:
        """Get current number of active operations."""
        with self._futures_lock:
            return len(self._active_futures)

    def get_capacity(self) -> int:
        """Get maximum capacity."""
        return self._executor._max_workers

    def is_available(self) -> bool:
        """Check if resources are available."""
        return self.get_current_load() < self.get_capacity()

    def shutdown(self, wait: bool = True):
        """Shutdown thread pool."""
        self._executor.shutdown(wait=wait)


class BulkheadManager:
    """Manages multiple bulkhead pools."""

    def __init__(self):
        self._bulkheads: builtins.dict[str, BulkheadPool] = {}
        self._lock = threading.Lock()

    def create_bulkhead(self, name: str, config: BulkheadConfig) -> BulkheadPool:
        """Create a new bulkhead pool."""
        with self._lock:
            if name in self._bulkheads:
                raise ValueError(f"Bulkhead '{name}' already exists")

            if config.bulkhead_type == BulkheadType.THREAD_POOL:
                bulkhead = ThreadPoolBulkhead(name, config)
            elif config.bulkhead_type in (
                BulkheadType.SEMAPHORE,
                BulkheadType.ASYNC_SEMAPHORE,
            ):
                bulkhead = SemaphoreBulkhead(name, config)
            else:
                raise ValueError(f"Unsupported bulkhead type: {config.bulkhead_type}")

            self._bulkheads[name] = bulkhead
            logger.info(f"Created bulkhead '{name}' with capacity {config.max_concurrent}")
            return bulkhead

    def get_bulkhead(self, name: str) -> BulkheadPool | None:
        """Get existing bulkhead pool."""
        with self._lock:
            return self._bulkheads.get(name)

    def remove_bulkhead(self, name: str):
        """Remove bulkhead pool."""
        with self._lock:
            if name in self._bulkheads:
                bulkhead = self._bulkheads[name]
                if isinstance(bulkhead, ThreadPoolBulkhead):
                    bulkhead.shutdown()
                del self._bulkheads[name]
                logger.info(f"Removed bulkhead '{name}'")

    def get_all_stats(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get statistics for all bulkheads."""
        with self._lock:
            return {name: bulkhead.get_stats() for name, bulkhead in self._bulkheads.items()}

    def shutdown_all(self):
        """Shutdown all bulkheads."""
        with self._lock:
            for _name, bulkhead in list(self._bulkheads.items()):
                if isinstance(bulkhead, ThreadPoolBulkhead):
                    bulkhead.shutdown()
            self._bulkheads.clear()


# Global bulkhead manager
_bulkhead_manager = BulkheadManager()


def get_bulkhead_manager() -> BulkheadManager:
    """Get the global bulkhead manager."""
    return _bulkhead_manager


def bulkhead_isolate(
    name: str,
    config: BulkheadConfig | None = None,
    bulkhead: BulkheadPool | None = None,
):
    """
    Decorator to isolate function execution with bulkhead pattern.

    Args:
        name: Bulkhead name
        config: Bulkhead configuration
        bulkhead: Existing bulkhead instance

    Returns:
        Decorated function
    """

    if bulkhead is None:
        bulkhead_config = config or BulkheadConfig()
        manager = get_bulkhead_manager()

        existing_bulkhead = manager.get_bulkhead(name)
        if existing_bulkhead:
            bulkhead = existing_bulkhead
        else:
            bulkhead = manager.create_bulkhead(name, bulkhead_config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                return await bulkhead.execute_async(func, *args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return bulkhead.execute_sync(func, *args, **kwargs)

        return sync_wrapper

    return decorator


# Common bulkhead configurations
DEFAULT_BULKHEAD_CONFIG = BulkheadConfig()

CPU_INTENSIVE_CONFIG = BulkheadConfig(
    max_concurrent=4,  # Limited by CPU cores
    bulkhead_type=BulkheadType.THREAD_POOL,
    timeout_seconds=60.0,
    reject_on_full=True,
)

IO_INTENSIVE_CONFIG = BulkheadConfig(
    max_concurrent=20,  # Higher concurrency for I/O
    bulkhead_type=BulkheadType.SEMAPHORE,
    timeout_seconds=30.0,
    reject_on_full=False,
)

DATABASE_CONFIG = BulkheadConfig(
    max_concurrent=10,  # Database connection pool size
    bulkhead_type=BulkheadType.SEMAPHORE,
    timeout_seconds=15.0,
    reject_on_full=False,
    dependency_type="database",
    enable_circuit_breaker=True,
)

# External dependency configurations for different service types
EXTERNAL_API_CONFIG = BulkheadConfig(
    max_concurrent=15,  # API call concurrency
    bulkhead_type=BulkheadType.SEMAPHORE,
    timeout_seconds=20.0,
    reject_on_full=True,
    dependency_type="api",
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=3,
)

CACHE_CONFIG = BulkheadConfig(
    max_concurrent=50,  # High concurrency for cache
    bulkhead_type=BulkheadType.SEMAPHORE,
    timeout_seconds=2.0,
    reject_on_full=True,
    dependency_type="cache",
    enable_circuit_breaker=False,  # Cache failures shouldn't circuit break
)

MESSAGE_QUEUE_CONFIG = BulkheadConfig(
    max_concurrent=20,  # Message queue operations
    bulkhead_type=BulkheadType.SEMAPHORE,
    timeout_seconds=10.0,
    reject_on_full=False,
    dependency_type="message_queue",
    enable_circuit_breaker=True,
    circuit_breaker_failure_threshold=5,
)

FILE_SYSTEM_CONFIG = BulkheadConfig(
    max_concurrent=8,  # File I/O operations
    bulkhead_type=BulkheadType.THREAD_POOL,
    timeout_seconds=30.0,
    reject_on_full=True,
    dependency_type="file_system",
    enable_circuit_breaker=False,
)

MEMORY_INTENSIVE_CONFIG = BulkheadConfig(
    max_concurrent=2,  # Memory-heavy operations
    bulkhead_type=BulkheadType.THREAD_POOL,
    timeout_seconds=120.0,
    reject_on_full=True,
    dependency_type="memory_intensive",
    enable_circuit_breaker=False,
)

EXTERNAL_API_CONFIG = BulkheadConfig(
    max_concurrent=5,  # Limited external API calls
    bulkhead_type=BulkheadType.SEMAPHORE,
    timeout_seconds=30.0,
    reject_on_full=True,
)
