"""
Bulkhead Pattern Implementation.
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, TypeVar

from mmf.core.registry import get_service, register_singleton
from mmf.framework.resilience.domain.config import BulkheadConfig, BulkheadType
from mmf.framework.resilience.domain.exceptions import BulkheadError

T = TypeVar("T")
logger = logging.getLogger(__name__)


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
    async def execute_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute async function with bulkhead protection."""

    @abstractmethod
    def execute_sync(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
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

    def _record_request_start(self) -> None:
        """Record start of request."""
        with self._lock:
            self._total_requests += 1
            self._active_requests += 1
            self._max_concurrent_reached = max(self._max_concurrent_reached, self._active_requests)

    def _record_request_end(self, success: bool) -> None:
        """Record end of request."""
        with self._lock:
            self._active_requests -= 1
            if success:
                self._successful_requests += 1
            else:
                self._failed_requests += 1

    def _record_rejection(self) -> None:
        """Record rejected request."""
        with self._lock:
            self._rejected_requests += 1

    def _record_wait_time(self, wait_time: float) -> None:
        """Record wait time for resource acquisition."""
        with self._lock:
            self._total_wait_time += wait_time

    def get_stats(self) -> dict[str, Any]:
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

    def reset_stats(self) -> None:
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

    async def execute_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
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

    def execute_sync(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
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
        # Accessing internal _value is not ideal but standard for Semaphore inspection
        return self.config.max_concurrent - self._semaphore._value  # type: ignore

    def get_capacity(self) -> int:
        """Get maximum capacity."""
        return self.config.max_concurrent

    def is_available(self) -> bool:
        """Check if resources are available."""
        return self._semaphore._value > 0  # type: ignore


class ThreadPoolBulkhead(BulkheadPool):
    """Thread pool-based bulkhead for CPU-bound operations."""

    def __init__(self, name: str, config: BulkheadConfig):
        super().__init__(name, config)

        max_workers = config.max_workers or config.max_concurrent
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=f"{config.thread_name_prefix}-{name}",
        )
        self._active_futures: set[Any] = set()
        self._futures_lock = threading.Lock()

    async def execute_async(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
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

    def execute_sync(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
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

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown thread pool."""
        self._executor.shutdown(wait=wait)


class BulkheadManager:
    """Manages multiple bulkhead pools."""

    def __init__(self) -> None:
        self._bulkheads: dict[str, BulkheadPool] = {}
        self._lock = threading.Lock()

    def create_bulkhead(self, name: str, config: BulkheadConfig) -> BulkheadPool:
        """Create a new bulkhead pool."""
        with self._lock:
            if name in self._bulkheads:
                raise ValueError(f"Bulkhead '{name}' already exists")

            if config.bulkhead_type == BulkheadType.THREAD_POOL:
                bulkhead: BulkheadPool = ThreadPoolBulkhead(name, config)
            elif config.bulkhead_type in (
                BulkheadType.SEMAPHORE,
                BulkheadType.ASYNC_SEMAPHORE,
            ):
                bulkhead = SemaphoreBulkhead(name, config)
            else:
                raise ValueError(f"Unsupported bulkhead type: {config.bulkhead_type}")

            self._bulkheads[name] = bulkhead
            logger.info("Created bulkhead '%s' with capacity %d", name, config.max_concurrent)
            return bulkhead

    def get_bulkhead(self, name: str) -> BulkheadPool | None:
        """Get existing bulkhead pool."""
        with self._lock:
            return self._bulkheads.get(name)

    def remove_bulkhead(self, name: str) -> None:
        """Remove bulkhead pool."""
        with self._lock:
            if name in self._bulkheads:
                bulkhead = self._bulkheads[name]
                if isinstance(bulkhead, ThreadPoolBulkhead):
                    bulkhead.shutdown()
                del self._bulkheads[name]
                logger.info("Removed bulkhead '%s'", name)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all bulkheads."""
        with self._lock:
            return {name: bulkhead.get_stats() for name, bulkhead in self._bulkheads.items()}

    def shutdown_all(self) -> None:
        """Shutdown all bulkheads."""
        with self._lock:
            for _name, bulkhead in list(self._bulkheads.items()):
                if isinstance(bulkhead, ThreadPoolBulkhead):
                    bulkhead.shutdown()
            self._bulkheads.clear()


# Global bulkhead manager replaced with Service Registry pattern


def get_bulkhead_manager() -> BulkheadManager:
    """Get the global bulkhead manager."""
    try:
        return get_service(BulkheadManager)
    except KeyError:
        manager = BulkheadManager()
        register_singleton(BulkheadManager, manager)
        return manager


def bulkhead_isolate(
    name: str,
    config: BulkheadConfig | None = None,
    bulkhead: BulkheadPool | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to isolate function execution with bulkhead pattern.
    """

    if bulkhead is None:
        bulkhead_config = config or BulkheadConfig()
        manager = get_bulkhead_manager()

        existing_bulkhead = manager.get_bulkhead(name)
        if existing_bulkhead:
            bulkhead = existing_bulkhead
        else:
            bulkhead = manager.create_bulkhead(name, bulkhead_config)

    # We know bulkhead is not None here, but type checker might not
    assert bulkhead is not None

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await bulkhead.execute_async(func, *args, **kwargs)  # type: ignore

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return bulkhead.execute_sync(func, *args, **kwargs)  # type: ignore

        return sync_wrapper

    return decorator
