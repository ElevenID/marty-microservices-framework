"""
Framework metrics helpers for standardized custom metrics definition.

Provides utilities for defining and using custom application metrics in a standardized way,
ensuring consistency across all Marty microservices.
"""

from __future__ import annotations

import logging

from prometheus_client import Counter, Gauge, Histogram, Info

from ..core.di_container import configure_service, get_service, get_service_optional
from .factories import register_observability_services, set_framework_metrics_class

logger = logging.getLogger(__name__)



class FrameworkMetrics:
    """Framework metrics helper for standardized custom metrics."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._infos: dict[str, Info] = {}

        # Common application metrics (initialized regardless of Prometheus availability)
        self.documents_processed = self.create_counter(
            "documents_processed_total",
            "Total number of documents processed",
            ["document_type", "status"],
        )

        self.processing_duration = self.create_histogram(
            "processing_duration_seconds",
            "Time spent processing documents",
            ["document_type"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
        )

        self.active_connections = self.create_gauge(
            "active_connections", "Number of active connections"
        )

        self.queue_size = self.create_gauge("queue_size", "Current queue size", ["queue_name"])

        self.service_info = self.create_info("service_build_info", "Service build information")

    def create_counter(
        self, name: str, description: str, label_names: list[str] | None = None
    ) -> Counter | None:
        """Create a counter metric.

        Args:
            name: Metric name (without mmf_ prefix)
            description: Metric description
            label_names: List of label names

        Returns:
            Counter instance
        """
        full_name = f"mmf_{name}"
        label_names = label_names or []

        if full_name in self._counters:
            return self._counters[full_name]

        counter = Counter(
            full_name,
            description,
            label_names + ["service"],
        )
        self._counters[full_name] = counter
        return counter

    def create_gauge(
        self, name: str, description: str, label_names: list[str] | None = None
    ) -> Gauge | None:
        """Create a gauge metric.

        Args:
            name: Metric name (without mmf_ prefix)
            description: Metric description
            label_names: List of label names

        Returns:
            Gauge instance
        """
        full_name = f"mmf_{name}"
        label_names = label_names or []

        if full_name in self._gauges:
            return self._gauges[full_name]

        gauge = Gauge(
            full_name,
            description,
            label_names + ["service"],
        )
        self._gauges[full_name] = gauge
        return gauge

    def create_histogram(
        self,
        name: str,
        description: str,
        label_names: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram | None:
        """Create a histogram metric.

        Args:
            name: Metric name (without mmf_ prefix)
            description: Metric description
            label_names: List of label names
            buckets: Histogram buckets

        Returns:
            Histogram instance
        """
        full_name = f"mmf_{name}"
        label_names = label_names or []
        buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

        if full_name in self._histograms:
            return self._histograms[full_name]

        histogram = Histogram(
            full_name,
            description,
            label_names + ["service"],
            buckets=buckets,
        )
        self._histograms[full_name] = histogram
        return histogram

    def create_info(self, name: str, description: str) -> Info | None:
        """Create an info metric.

        Args:
            name: Metric name (without mmf_ prefix)
            description: Metric description

        Returns:
            Info instance
        """
        full_name = f"mmf_{name}"

        if full_name in self._infos:
            return self._infos[full_name]

        info = Info(
            full_name,
            description,
        )
        self._infos[full_name] = info
        return info

    # Convenience methods for common metrics

    def record_document_processed(self, document_type: str, status: str = "success") -> None:
        """Record that a document was processed.

        Args:
            document_type: Type of document (e.g., "passport", "license")
            status: Processing status ("success", "error", etc.)
        """
        if self.documents_processed:
            self.documents_processed.labels(
                document_type=document_type, status=status, service=self.service_name
            ).inc()

    def record_processing_time(self, document_type: str, duration: float) -> None:
        """Record document processing duration.

        Args:
            document_type: Type of document
            duration: Processing time in seconds
        """
        if self.processing_duration:
            self.processing_duration.labels(
                document_type=document_type, service=self.service_name
            ).observe(duration)

    def set_active_connections(self, count: int) -> None:
        """Set the number of active connections.

        Args:
            count: Number of active connections
        """
        if self.active_connections:
            self.active_connections.labels(service=self.service_name).set(count)

    def set_queue_size(self, queue_name: str, size: int) -> None:
        """Set the size of a queue.

        Args:
            queue_name: Name of the queue
            size: Current queue size
        """
        if self.queue_size:
            self.queue_size.labels(queue_name=queue_name, service=self.service_name).set(size)

    def set_service_info(self, version: str, build_date: str, **kwargs) -> None:
        """Set service build information.

        Args:
            version: Service version
            build_date: Build date
            **kwargs: Additional info labels
        """
        if self.service_info:
            info_dict = {
                "version": version,
                "build_date": build_date,
                "service": self.service_name,
                **kwargs,
            }
            self.service_info.info(info_dict)


def get_framework_metrics(service_name: str) -> FrameworkMetrics:
    """
    Get the framework metrics instance using dependency injection.

    Args:
        service_name: Name of the service

    Returns:
        FrameworkMetrics instance
    """

    # Try to get existing metrics
    metrics = get_service_optional(FrameworkMetrics)
    if metrics is not None and metrics.service_name == service_name:
        return metrics

    # Auto-register if not found or service name changed
    register_observability_services(service_name)

    # Configure with service name
    configure_service(FrameworkMetrics, {"service_name": service_name})

    return get_service(FrameworkMetrics)


set_framework_metrics_class(FrameworkMetrics)
