"""
Cache Metrics for MMF.

This module provides Prometheus metrics for cache operations in the
Marty Microservices Framework. It tracks cache hits, misses, latency,
and errors for observability and alerting.

Usage:
    metrics = CacheMetrics(service_name="marty-ui")

    # Record hits/misses
    metrics.record_hit("auth:pkce")
    metrics.record_miss("auth:pkce")

    # Record latency
    metrics.record_latency("auth:pkce", "get", 0.0015)

    # Use as context manager
    with metrics.operation_timer("auth:pkce", "set"):
        await cache.set(key, value)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram

if TYPE_CHECKING:
    from mmf.core.cache import ICacheMetrics

logger = logging.getLogger(__name__)


class CacheMetrics:
    """
    Prometheus metrics collection for cache operations.

    Implements the ICacheMetrics protocol and provides standardized
    metrics for cache hit/miss rates, latency, and errors.

    Metrics:
        - mmf_cache_hits_total: Counter of cache hits by cache_name
        - mmf_cache_misses_total: Counter of cache misses by cache_name
        - mmf_cache_operations_total: Counter of all operations by cache_name and operation
        - mmf_cache_operation_duration_seconds: Histogram of operation latency
        - mmf_cache_errors_total: Counter of cache errors by cache_name and operation
    """

    def __init__(self, service_name: str = "marty"):
        """
        Initialize cache metrics.

        Args:
            service_name: Service name to include in metric labels
        """
        self.service_name = service_name

        # Cache hit counter
        self.cache_hits = Counter(
            "mmf_cache_hits_total",
            "Total cache hits",
            ["service", "cache_name"],
        )

        # Cache miss counter
        self.cache_misses = Counter(
            "mmf_cache_misses_total",
            "Total cache misses",
            ["service", "cache_name"],
        )

        # Total operations counter (including sets, deletes, etc.)
        self.cache_operations = Counter(
            "mmf_cache_operations_total",
            "Total cache operations",
            ["service", "cache_name", "operation"],
        )

        # Operation duration histogram
        self.operation_duration = Histogram(
            "mmf_cache_operation_duration_seconds",
            "Cache operation duration in seconds",
            ["service", "cache_name", "operation"],
            buckets=[0.0001, 0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        )

        # Error counter
        self.cache_errors = Counter(
            "mmf_cache_errors_total",
            "Total cache errors",
            ["service", "cache_name", "operation"],
        )

    def record_hit(self, cache_name: str) -> None:
        """
        Record a cache hit.

        Args:
            cache_name: Name/prefix of the cache (e.g., "auth:pkce")
        """
        self.cache_hits.labels(
            service=self.service_name,
            cache_name=cache_name,
        ).inc()

    def record_miss(self, cache_name: str) -> None:
        """
        Record a cache miss.

        Args:
            cache_name: Name/prefix of the cache (e.g., "auth:pkce")
        """
        self.cache_misses.labels(
            service=self.service_name,
            cache_name=cache_name,
        ).inc()

    def record_operation(self, cache_name: str, operation: str) -> None:
        """
        Record a cache operation.

        Args:
            cache_name: Name/prefix of the cache
            operation: Operation type (get, set, delete, etc.)
        """
        self.cache_operations.labels(
            service=self.service_name,
            cache_name=cache_name,
            operation=operation,
        ).inc()

    def record_latency(
        self,
        cache_name: str,
        operation: str,
        latency_seconds: float,
    ) -> None:
        """
        Record operation latency.

        Args:
            cache_name: Name/prefix of the cache
            operation: Operation type (get, set, delete, etc.)
            latency_seconds: Duration in seconds
        """
        self.operation_duration.labels(
            service=self.service_name,
            cache_name=cache_name,
            operation=operation,
        ).observe(latency_seconds)

    def record_error(self, cache_name: str, operation: str) -> None:
        """
        Record a cache error.

        Args:
            cache_name: Name/prefix of the cache
            operation: Operation that failed
        """
        self.cache_errors.labels(
            service=self.service_name,
            cache_name=cache_name,
            operation=operation,
        ).inc()

    @contextmanager
    def operation_timer(
        self,
        cache_name: str,
        operation: str,
    ) -> Generator[None, None, None]:
        """
        Context manager to time cache operations.

        Automatically records latency and operation count.

        Args:
            cache_name: Name/prefix of the cache
            operation: Operation type

        Example:
            with metrics.operation_timer("auth:pkce", "set"):
                await cache.set(key, value, ttl=600)
        """
        start = time.perf_counter()
        try:
            yield
            self.record_operation(cache_name, operation)
        except Exception:
            self.record_error(cache_name, operation)
            raise
        finally:
            latency = time.perf_counter() - start
            self.record_latency(cache_name, operation, latency)


class NullCacheMetrics:
    """
    No-op metrics implementation for when metrics are disabled.

    Implements ICacheMetrics but does nothing, useful for testing
    or when Prometheus is not available.
    """

    def record_hit(self, cache_name: str) -> None:
        """No-op."""

    def record_miss(self, cache_name: str) -> None:
        """No-op."""

    def record_operation(self, cache_name: str, operation: str) -> None:
        """No-op."""

    def record_latency(
        self,
        cache_name: str,
        operation: str,
        latency_seconds: float,
    ) -> None:
        """No-op."""

    def record_error(self, cache_name: str, operation: str) -> None:
        """No-op."""

    @contextmanager
    def operation_timer(
        self,
        cache_name: str,
        operation: str,
    ) -> Generator[None, None, None]:
        """No-op timer."""
        yield


# Singleton instance for easy import
_default_metrics: CacheMetrics | None = None


def get_cache_metrics(service_name: str = "marty") -> CacheMetrics:
    """
    Get or create the default cache metrics instance.

    Args:
        service_name: Service name for metric labels

    Returns:
        CacheMetrics singleton instance
    """
    global _default_metrics  # Transitional: Singleton pattern will migrate to DI
    if _default_metrics is None:
        _default_metrics = CacheMetrics(service_name)
    return _default_metrics


__all__ = [
    "CacheMetrics",
    "NullCacheMetrics",
    "get_cache_metrics",
]
