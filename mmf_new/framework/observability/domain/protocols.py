"""
Observability Domain Protocols.

This module defines the core interfaces (ports) for the observability framework.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Protocol


class HealthStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class MetricType(Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class IMetricsCollector(Protocol):
    """Interface for metrics collection."""

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""
        ...

    def gauge(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Set a gauge metric."""
        ...

    def histogram(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a histogram metric."""
        ...


class ITracer(Protocol):
    """Interface for distributed tracing."""

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> Any:
        """Start a new span."""
        ...

    def current_span(self) -> Any:
        """Get the current active span."""
        ...
