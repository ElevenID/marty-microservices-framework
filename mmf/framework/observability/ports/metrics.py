"""
Metrics Collector Interface

This module defines the interface for metrics collection.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IMetricsCollector(ABC):
    """Interface for metrics collection."""

    @abstractmethod
    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric."""
        pass

    @abstractmethod
    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Set a gauge metric."""
        pass

    @abstractmethod
    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Add a value to a histogram metric."""
        pass

    @abstractmethod
    def record_request(self, method: str, status: str, duration: float) -> None:
        """Record an HTTP/gRPC request."""
        pass

    @abstractmethod
    def record_error(self, method: str, error_type: str) -> None:
        """Record an error."""
        pass

    @abstractmethod
    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus text format."""
        pass

    @abstractmethod
    def get_metrics_summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        pass
