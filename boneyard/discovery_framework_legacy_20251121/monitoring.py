"""
Monitoring and Metrics for Service Discovery

Comprehensive monitoring, metrics collection, and observability for
service discovery operations, health checks, and load balancing.
"""

import asyncio
import builtins
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    TIMER = "timer"


class MetricUnit(Enum):
    """Metric units."""

    BYTES = "bytes"
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    COUNT = "count"
    PERCENTAGE = "percentage"
    REQUESTS_PER_SECOND = "requests_per_second"


@dataclass
class MetricPoint:
    """Individual metric data point."""

    timestamp: float
    value: float
    labels: builtins.dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {"timestamp": self.timestamp, "value": self.value, "labels": self.labels}


@dataclass
class MetricSeries:
    """Time series of metric data points."""

    name: str
    metric_type: MetricType
    unit: MetricUnit
    description: str = ""
    points: builtins.list[MetricPoint] = field(default_factory=list)
    max_points: int = 1000

    def add_point(self, value: float, labels: builtins.dict[str, str] | None = None):
        """Add metric point."""
        point = MetricPoint(timestamp=time.time(), value=value, labels=labels or {})

        self.points.append(point)

        # Keep only recent points
        if len(self.points) > self.max_points:
            self.points = self.points[-self.max_points :]

    def get_latest_value(self) -> float | None:
        """Get latest metric value."""
        return self.points[-1].value if self.points else None

    def get_average(self, window_seconds: float | None = None) -> float | None:
        """Get average value over time window."""
        if not self.points:
            return None

        if window_seconds is None:
            values = [p.value for p in self.points]
        else:
            cutoff_time = time.time() - window_seconds
            values = [p.value for p in self.points if p.timestamp >= cutoff_time]

        return sum(values) / len(values) if values else None

    def get_percentile(
        self, percentile: float, window_seconds: float | None = None
    ) -> float | None:
        """Get percentile value over time window."""
        if not self.points:
            return None

        if window_seconds is None:
            values = [p.value for p in self.points]
        else:
            cutoff_time = time.time() - window_seconds
            values = [p.value for p in self.points if p.timestamp >= cutoff_time]

        if not values:
            return None

        values.sort()
        index = int((percentile / 100.0) * len(values))
        return values[min(index, len(values) - 1)]

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.metric_type.value,
            "unit": self.unit.value,
            "description": self.description,
            "latest_value": self.get_latest_value(),
            "average": self.get_average(),
            "point_count": len(self.points),
            "points": [p.to_dict() for p in self.points[-10:]],  # Last 10 points
        }


class MetricsCollector:
    """Metrics collector for service discovery components."""

    def __init__(self):
        self._metrics: builtins.dict[str, MetricSeries] = {}
        self._labels: builtins.dict[str, str] = {}
        self._collection_enabled = True

    def set_global_labels(self, labels: builtins.dict[str, str]):
        """Set global labels applied to all metrics."""
        self._labels.update(labels)

    def enable_collection(self, enabled: bool = True):
        """Enable or disable metrics collection."""
        self._collection_enabled = enabled

    def create_counter(
        self, name: str, description: str = "", unit: MetricUnit = MetricUnit.COUNT
    ) -> MetricSeries:
        """Create counter metric."""
        return self._create_metric(name, MetricType.COUNTER, unit, description)

    def create_gauge(
        self, name: str, description: str = "", unit: MetricUnit = MetricUnit.COUNT
    ) -> MetricSeries:
        """Create gauge metric."""
        return self._create_metric(name, MetricType.GAUGE, unit, description)

    def create_histogram(
        self,
        name: str,
        description: str = "",
        unit: MetricUnit = MetricUnit.MILLISECONDS,
    ) -> MetricSeries:
        """Create histogram metric."""
        return self._create_metric(name, MetricType.HISTOGRAM, unit, description)

    def create_timer(
        self,
        name: str,
        description: str = "",
        unit: MetricUnit = MetricUnit.MILLISECONDS,
    ) -> MetricSeries:
        """Create timer metric."""
        return self._create_metric(name, MetricType.TIMER, unit, description)

    def _create_metric(
        self, name: str, metric_type: MetricType, unit: MetricUnit, description: str
    ) -> MetricSeries:
        """Create metric series."""
        if name not in self._metrics:
            self._metrics[name] = MetricSeries(
                name=name, metric_type=metric_type, unit=unit, description=description
            )

        return self._metrics[name]

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: builtins.dict[str, str] | None = None,
    ):
        """Increment counter metric."""
        if not self._collection_enabled:
            return

        metric = self._metrics.get(name)
        if metric and metric.metric_type == MetricType.COUNTER:
            current_value = metric.get_latest_value() or 0.0
            combined_labels = {**self._labels, **(labels or {})}
            metric.add_point(current_value + value, combined_labels)

    def set_gauge(self, name: str, value: float, labels: builtins.dict[str, str] | None = None):
        """Set gauge metric value."""
        if not self._collection_enabled:
            return

        metric = self._metrics.get(name)
        if metric and metric.metric_type == MetricType.GAUGE:
            combined_labels = {**self._labels, **(labels or {})}
            metric.add_point(value, combined_labels)

    def record_value(self, name: str, value: float, labels: builtins.dict[str, str] | None = None):
        """Record value for histogram/timer metric."""
        if not self._collection_enabled:
            return

        metric = self._metrics.get(name)
        if metric and metric.metric_type in [MetricType.HISTOGRAM, MetricType.TIMER]:
            combined_labels = {**self._labels, **(labels or {})}
            metric.add_point(value, combined_labels)

    def record_duration(
        self,
        name: str,
        start_time: float,
        labels: builtins.dict[str, str] | None = None,
    ):
        """Record duration for timer metric."""
        duration_ms = (time.time() - start_time) * 1000
        self.record_value(name, duration_ms, labels)

    def get_metric(self, name: str) -> MetricSeries | None:
        """Get metric series by name."""
        return self._metrics.get(name)

    def get_all_metrics(self) -> builtins.dict[str, MetricSeries]:
        """Get all metric series."""
        return self._metrics.copy()

    def clear_metrics(self):
        """Clear all metrics."""
        self._metrics.clear()

    def export_metrics(self) -> builtins.dict[str, Any]:
        """Export all metrics to dictionary."""
        return {name: metric.to_dict() for name, metric in self._metrics.items()}


class DiscoveryMetrics:
    """Specific metrics for service discovery operations."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self._initialize_metrics()

    def _initialize_metrics(self):
        """Initialize service discovery specific metrics."""

        # Service discovery metrics
        self.collector.create_counter(
            "discovery_requests_total",
            "Total number of service discovery requests",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            "discovery_requests_successful",
            "Number of successful service discovery requests",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            "discovery_requests_failed",
            "Number of failed service discovery requests",
            MetricUnit.COUNT,
        )

        self.collector.create_histogram(
            "discovery_request_duration",
            "Service discovery request duration",
            MetricUnit.MILLISECONDS,
        )

        self.collector.create_gauge(
            "discovered_services_count",
            "Number of discovered services",
            MetricUnit.COUNT,
        )

        self.collector.create_gauge(
            "healthy_services_count", "Number of healthy services", MetricUnit.COUNT
        )

        # Cache metrics
        self.collector.create_counter(
            "cache_hits_total", "Total number of cache hits", MetricUnit.COUNT
        )

        self.collector.create_counter(
            "cache_misses_total", "Total number of cache misses", MetricUnit.COUNT
        )

        self.collector.create_gauge("cache_size", "Current cache size", MetricUnit.COUNT)

        # Load balancing metrics
        self.collector.create_counter(
            "load_balancer_requests_total",
            "Total load balancer requests",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            "load_balancer_selections_total",
            "Total instance selections by load balancer",
            MetricUnit.COUNT,
        )

        self.collector.create_histogram(
            "load_balancer_selection_duration",
            "Load balancer selection duration",
            MetricUnit.MILLISECONDS,
        )

        # Health check metrics
        self.collector.create_counter(
            "health_checks_total", "Total number of health checks", MetricUnit.COUNT
        )

        self.collector.create_counter(
            "health_checks_successful",
            "Number of successful health checks",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            "health_checks_failed", "Number of failed health checks", MetricUnit.COUNT
        )

        self.collector.create_histogram(
            "health_check_duration", "Health check duration", MetricUnit.MILLISECONDS
        )

        # Circuit breaker metrics
        self.collector.create_counter(
            "circuit_breaker_state_changes",
            "Circuit breaker state changes",
            MetricUnit.COUNT,
        )

        self.collector.create_gauge(
            "circuit_breaker_open_count",
            "Number of open circuit breakers",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            "circuit_breaker_trips", "Circuit breaker trips", MetricUnit.COUNT
        )

    def record_discovery_request(self, success: bool, duration: float, service_name: str):
        """Record service discovery request metrics."""
        labels = {"service": service_name}

        self.collector.increment("discovery_requests_total", 1.0, labels)

        if success:
            self.collector.increment("discovery_requests_successful", 1.0, labels)
        else:
            self.collector.increment("discovery_requests_failed", 1.0, labels)

        self.collector.record_value("discovery_request_duration", duration * 1000, labels)

    def record_cache_operation(self, hit: bool, service_name: str):
        """Record cache operation metrics."""
        labels = {"service": service_name}

        if hit:
            self.collector.increment("cache_hits_total", 1.0, labels)
        else:
            self.collector.increment("cache_misses_total", 1.0, labels)

    def update_service_counts(self, total_services: int, healthy_services: int):
        """Update service count metrics."""
        self.collector.set_gauge("discovered_services_count", total_services)
        self.collector.set_gauge("healthy_services_count", healthy_services)

    def record_load_balancer_selection(self, duration: float, instance_id: str, algorithm: str):
        """Record load balancer selection metrics."""
        labels = {"instance": instance_id, "algorithm": algorithm}

        self.collector.increment("load_balancer_requests_total", 1.0, labels)
        self.collector.increment("load_balancer_selections_total", 1.0, labels)
        self.collector.record_value("load_balancer_selection_duration", duration * 1000, labels)

    def record_health_check(
        self, success: bool, duration: float, service_name: str, check_type: str
    ):
        """Record health check metrics."""
        labels = {"service": service_name, "type": check_type}

        self.collector.increment("health_checks_total", 1.0, labels)

        if success:
            self.collector.increment("health_checks_successful", 1.0, labels)
        else:
            self.collector.increment("health_checks_failed", 1.0, labels)

        self.collector.record_value("health_check_duration", duration * 1000, labels)

    def record_circuit_breaker_state_change(
        self, breaker_name: str, old_state: str, new_state: str
    ):
        """Record circuit breaker state change."""
        labels = {
            "breaker": breaker_name,
            "old_state": old_state,
            "new_state": new_state,
        }

        self.collector.increment("circuit_breaker_state_changes", 1.0, labels)

        if new_state == "open":
            self.collector.increment("circuit_breaker_trips", 1.0, {"breaker": breaker_name})


class MetricsExporter(ABC):
    """Abstract metrics exporter interface."""

    @abstractmethod
    async def export_metrics(self, metrics: builtins.dict[str, MetricSeries]):
        """Export metrics to external system."""


class PrometheusExporter(MetricsExporter):
    """Prometheus metrics exporter."""

    def __init__(self, endpoint: str = "/metrics", port: int = 8000):
        self.endpoint = endpoint
        self.port = port
        self._server = None

    async def start_server(self):
        """Start Prometheus metrics server."""
        # This would start an HTTP server for Prometheus to scrape
        # Using aiohttp or similar web framework
        logger.info("Prometheus metrics server started on port %d", self.port)

    async def stop_server(self):
        """Stop Prometheus metrics server."""
        if self._server:
            # Stop HTTP server
            pass
        logger.info("Prometheus metrics server stopped")

    async def export_metrics(self, metrics: builtins.dict[str, MetricSeries]):
        """Export metrics in Prometheus format."""
        prometheus_format = self._convert_to_prometheus_format(metrics)
        # Store or serve the metrics for Prometheus scraping
        return prometheus_format

    def _convert_to_prometheus_format(self, metrics: builtins.dict[str, MetricSeries]) -> str:
        """Convert metrics to Prometheus format."""
        lines = []

        for name, metric in metrics.items():
            # Add help comment
            if metric.description:
                lines.append(f"# HELP {name} {metric.description}")

            # Add type comment
            prometheus_type = self._get_prometheus_type(metric.metric_type)
            lines.append(f"# TYPE {name} {prometheus_type}")

            # Add metric values
            if metric.points:
                latest_point = metric.points[-1]
                label_str = self._format_labels(latest_point.labels)
                lines.append(
                    f"{name}{label_str} {latest_point.value} {int(latest_point.timestamp * 1000)}"
                )

        return "\n".join(lines)

    def _get_prometheus_type(self, metric_type: MetricType) -> str:
        """Get Prometheus type for metric type."""
        mapping = {
            MetricType.COUNTER: "counter",
            MetricType.GAUGE: "gauge",
            MetricType.HISTOGRAM: "histogram",
            MetricType.SUMMARY: "summary",
            MetricType.TIMER: "histogram",
        }
        return mapping.get(metric_type, "gauge")

    def _format_labels(self, labels: builtins.dict[str, str]) -> str:
        """Format labels for Prometheus."""
        if not labels:
            return ""

        label_pairs = [f'{key}="{value}"' for key, value in labels.items()]
        return "{" + ",".join(label_pairs) + "}"


class LoggingExporter(MetricsExporter):
    """Logging metrics exporter for debugging."""

    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level

    async def export_metrics(self, metrics: builtins.dict[str, MetricSeries]):
        """Export metrics to logs."""
        for name, metric in metrics.items():
            latest_value = metric.get_latest_value()
            average_value = metric.get_average(window_seconds=300)  # 5 minutes

            logger.log(
                self.log_level,
                "Metric: %s | Latest: %s | Avg(5m): %s | Type: %s | Points: %d",
                name,
                latest_value,
                average_value,
                metric.metric_type.value,
                len(metric.points),
            )


class InfluxDBExporter(MetricsExporter):
    """InfluxDB metrics exporter."""

    def __init__(self, url: str, database: str, username: str = None, password: str = None):
        self.url = url
        self.database = database
        self.username = username
        self.password = password
        self._client = None

    async def connect(self):
        """Connect to InfluxDB."""
        # Initialize InfluxDB client
        # This would use influxdb library
        logger.info("Connected to InfluxDB at %s", self.url)

    async def disconnect(self):
        """Disconnect from InfluxDB."""
        if self._client:
            # Close InfluxDB client
            pass
        logger.info("Disconnected from InfluxDB")

    async def export_metrics(self, metrics: builtins.dict[str, MetricSeries]):
        """Export metrics to InfluxDB."""
        points = []

        for name, metric in metrics.items():
            for point in metric.points[-100:]:  # Last 100 points
                influx_point = {
                    "measurement": name,
                    "tags": point.labels,
                    "fields": {"value": point.value},
                    "time": int(point.timestamp * 1000000000),  # Nanoseconds
                }
                points.append(influx_point)

        # Write points to InfluxDB
        # await self._client.write_points(points)

        logger.debug("Exported %d metric points to InfluxDB", len(points))


class MetricsAggregator:
    """Aggregates metrics from multiple sources."""

    def __init__(self):
        self._collectors: builtins.list[MetricsCollector] = []
        self._exporters: builtins.list[MetricsExporter] = []
        self._export_interval = 60.0  # Export every minute
        self._export_task: asyncio.Task | None = None
        self._running = False

    def add_collector(self, collector: MetricsCollector):
        """Add metrics collector."""
        self._collectors.append(collector)

    def add_exporter(self, exporter: MetricsExporter):
        """Add metrics exporter."""
        self._exporters.append(exporter)

    def set_export_interval(self, interval: float):
        """Set metrics export interval in seconds."""
        self._export_interval = interval

    async def start(self):
        """Start metrics aggregation and export."""
        self._running = True
        self._export_task = asyncio.create_task(self._export_loop())
        logger.info("Metrics aggregator started")

    async def stop(self):
        """Stop metrics aggregation and export."""
        self._running = False

        if self._export_task:
            self._export_task.cancel()
            try:
                await self._export_task
            except asyncio.CancelledError:
                pass

        logger.info("Metrics aggregator stopped")

    async def _export_loop(self):
        """Main export loop."""
        while self._running:
            try:
                await self._export_all_metrics()
                await asyncio.sleep(self._export_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Metrics export failed: %s", e)
                await asyncio.sleep(self._export_interval)

    async def _export_all_metrics(self):
        """Export metrics from all collectors to all exporters."""
        # Aggregate metrics from all collectors
        all_metrics = {}

        for collector in self._collectors:
            collector_metrics = collector.get_all_metrics()
            all_metrics.update(collector_metrics)

        # Export to all exporters
        for exporter in self._exporters:
            try:
                await exporter.export_metrics(all_metrics)
            except Exception as e:
                logger.error("Failed to export metrics: %s", e)

    def get_aggregated_stats(self) -> builtins.dict[str, Any]:
        """Get aggregated statistics."""
        stats = {
            "collectors": len(self._collectors),
            "exporters": len(self._exporters),
            "export_interval": self._export_interval,
            "running": self._running,
            "total_metrics": 0,
            "metrics_by_type": defaultdict(int),
        }

        for collector in self._collectors:
            collector_metrics = collector.get_all_metrics()
            stats["total_metrics"] += len(collector_metrics)

            for metric in collector_metrics.values():
                stats["metrics_by_type"][metric.metric_type.value] += 1

        return dict(stats)


# Global metrics infrastructure
global_metrics_collector = MetricsCollector()
global_discovery_metrics = DiscoveryMetrics(global_metrics_collector)
global_metrics_aggregator = MetricsAggregator()

# Add global collector to aggregator
global_metrics_aggregator.add_collector(global_metrics_collector)


# Convenience functions
def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector."""
    return global_metrics_collector


def get_discovery_metrics() -> DiscoveryMetrics:
    """Get global discovery metrics."""
    return global_discovery_metrics


def get_metrics_aggregator() -> MetricsAggregator:
    """Get global metrics aggregator."""
    return global_metrics_aggregator


class LoadBalancingMetrics:
    """Metrics specific to load balancing operations."""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector
        self._initialize_metrics()

    def _initialize_metrics(self):
        """Initialize load balancing specific metrics."""

        # Load balancing metrics
        self.collector.create_counter(
            "load_balancer_requests_total",
            "Total number of load balancer requests",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            "load_balancer_requests_successful",
            "Number of successful load balancer requests",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            "load_balancer_requests_failed",
            "Number of failed load balancer requests",
            MetricUnit.COUNT,
        )

        self.collector.create_histogram(
            "load_balancer_response_time",
            "Response time for load balancing operations",
            MetricUnit.SECONDS,
        )

        self.collector.create_gauge(
            "load_balancer_active_connections",
            "Number of active connections through load balancer",
            MetricUnit.COUNT,
        )

    def record_request(self, success: bool = True, response_time: float = 0.0):
        """Record a load balancing request."""
        self.collector.increment("load_balancer_requests_total")

        if success:
            self.collector.increment("load_balancer_requests_successful")
        else:
            self.collector.increment("load_balancer_requests_failed")

        if response_time > 0:
            self.collector.record_value("load_balancer_response_time", response_time)

    def set_active_connections(self, count: int):
        """Set the number of active connections."""
        self.collector.set_gauge("load_balancer_active_connections", count)


class ServiceMetrics:
    """Metrics specific to individual services."""

    def __init__(self, collector: MetricsCollector, service_name: str):
        self.collector = collector
        self.service_name = service_name
        self._initialize_metrics()

    def _initialize_metrics(self):
        """Initialize service specific metrics."""

        # Service metrics
        self.collector.create_counter(
            f"service_{self.service_name}_requests_total",
            f"Total number of requests to {self.service_name}",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            f"service_{self.service_name}_requests_successful",
            f"Number of successful requests to {self.service_name}",
            MetricUnit.COUNT,
        )

        self.collector.create_counter(
            f"service_{self.service_name}_requests_failed",
            f"Number of failed requests to {self.service_name}",
            MetricUnit.COUNT,
        )

        self.collector.create_histogram(
            f"service_{self.service_name}_response_time",
            f"Response time for {self.service_name}",
            MetricUnit.SECONDS,
        )

        self.collector.create_gauge(
            f"service_{self.service_name}_health_score",
            f"Health score for {self.service_name}",
            MetricUnit.PERCENTAGE,
        )

    def record_request(self, success: bool = True, response_time: float = 0.0):
        """Record a service request."""
        self.collector.increment(f"service_{self.service_name}_requests_total")

        if success:
            self.collector.increment(f"service_{self.service_name}_requests_successful")
        else:
            self.collector.increment(f"service_{self.service_name}_requests_failed")

        if response_time > 0:
            self.collector.record_value(f"service_{self.service_name}_response_time", response_time)

    def set_health_score(self, score: float):
        """Set the health score for the service."""
        self.collector.set_gauge(f"service_{self.service_name}_health_score", score)
