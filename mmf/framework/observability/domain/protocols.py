"""
Observability Domain Protocols.

This module defines the core interfaces (ports) for the observability framework.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol


class HealthStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check definition."""

    name: str
    check_func: Callable[[], bool]
    timeout: float = 5.0
    interval: float = 30.0
    enabled: bool = True
    last_run: datetime | None = None
    last_status: HealthStatus = HealthStatus.UNKNOWN
    failure_count: int = 0
    max_failures: int = 3


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class IMetricsCollector(Protocol):
    """Interface for metrics collection."""

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric."""
        ...

    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric."""
        ...

    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Record a histogram metric."""
        ...

    def record_request(self, method: str, status: str, duration: float) -> None:
        """Record an HTTP/gRPC request."""
        ...

    def record_error(self, method: str, error_type: str) -> None:
        """Record an error."""
        ...


class IHealthChecker(Protocol):
    """Interface for health checking."""

    def register_check(self, health_check: HealthCheck) -> None:
        """Register a health check."""
        ...

    def unregister_check(self, name: str) -> None:
        """Unregister a health check."""
        ...

    def run_check(self, name: str) -> HealthStatus:
        """Run a specific health check."""
        ...

    def run_all_checks(self) -> dict[str, HealthStatus]:
        """Run all registered health checks."""
        ...

    def get_overall_status(self) -> HealthStatus:
        """Get overall health status."""
        ...

    def start_periodic_checks(self) -> None:
        """Start periodic health check execution."""
        ...

    def stop_periodic_checks(self) -> None:
        """Stop periodic health check execution."""
        ...


class ITracer(Protocol):
    """Interface for distributed tracing."""

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> Any:
        """Start a new span."""
        ...

    def current_span(self) -> Any:
        """Get the current active span."""
        ...
