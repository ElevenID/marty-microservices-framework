"""
Enterprise Monitoring and Observability Framework

This module provides comprehensive monitoring capabilities beyond basic Prometheus/Grafana,
including custom metrics, distributed tracing, health checks, and observability middleware.
"""

import builtins
import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import aiohttp
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Required dependencies
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
)

from mmf.framework.infrastructure.dependency_injection import (
    get_service_optional,
    register_instance,
)

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics supported by the framework."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class HealthStatus(Enum):
    """Health check status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class MetricDefinition:
    """Definition of a custom metric."""

    name: str
    metric_type: MetricType
    description: str
    labels: builtins.list[str] = field(default_factory=list)
    buckets: builtins.list[float] | None = None  # For histograms
    namespace: str = "microservice"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str | None = None
    details: builtins.dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float | None = None


@dataclass
class ServiceMetrics:
    """Service-level metrics collection."""

    service_name: str
    request_count: int = 0
    error_count: int = 0
    request_duration_sum: float = 0.0
    active_connections: int = 0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MetricsCollector(ABC):
    """Abstract base class for metrics collectors."""

    @abstractmethod
    async def collect_metric(
        self, name: str, value: int | float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Collect a metric value."""

    @abstractmethod
    async def increment_counter(
        self, name: str, labels: builtins.dict[str, str] = None, amount: float = 1.0
    ) -> None:
        """Increment a counter metric."""

    @abstractmethod
    async def set_gauge(
        self, name: str, value: float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Set a gauge metric value."""

    @abstractmethod
    async def observe_histogram(
        self, name: str, value: float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Observe a value in a histogram."""


class PrometheusCollector(MetricsCollector):
    """Prometheus metrics collector."""

    def __init__(self, registry: CollectorRegistry | None = None):
        """Initialize the Prometheus collector.

        Args:
            registry: Prometheus registry to use. If None, uses default registry.
        """
        self.registry = registry or CollectorRegistry()
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        self._summaries: dict[str, Summary] = {}

    def register_metric(self, definition: MetricDefinition) -> None:
        """Register a custom metric with Prometheus."""
        with self._lock:
            if definition.name in self.metrics:
                return

            metric_kwargs = {
                "name": f"{definition.namespace}_{definition.name}",
                "documentation": definition.description,
                "labelnames": definition.labels,
                "registry": self.registry,
            }

            if definition.metric_type == MetricType.COUNTER:
                metric = Counter(**metric_kwargs)
            elif definition.metric_type == MetricType.GAUGE:
                metric = Gauge(**metric_kwargs)
            elif definition.metric_type == MetricType.HISTOGRAM:
                if definition.buckets:
                    metric_kwargs["buckets"] = definition.buckets
                metric = Histogram(**metric_kwargs)
            elif definition.metric_type == MetricType.SUMMARY:
                metric = Summary(**metric_kwargs)
            else:
                raise ValueError(f"Unsupported metric type: {definition.metric_type}")

            self.metrics[definition.name] = metric
            logger.info(f"Registered {definition.metric_type.value} metric: {definition.name}")

    async def collect_metric(
        self, name: str, value: int | float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Collect a generic metric value."""
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return

        metric = self.metrics[name]
        labels = labels or {}

        if hasattr(metric, "set"):  # Gauge
            if labels:
                metric.labels(**labels).set(value)
            else:
                metric.set(value)

    async def increment_counter(
        self, name: str, labels: builtins.dict[str, str] = None, amount: float = 1.0
    ) -> None:
        """Increment a counter metric."""
        if name not in self.metrics:
            logger.warning(f"Counter {name} not registered")
            return

        counter = self.metrics[name]
        labels = labels or {}

        if labels:
            counter.labels(**labels).inc(amount)
        else:
            counter.inc(amount)

    async def set_gauge(
        self, name: str, value: float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Set a gauge metric value."""
        if name not in self.metrics:
            logger.warning(f"Gauge {name} not registered")
            return

        gauge = self.metrics[name]
        labels = labels or {}

        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)

    async def observe_histogram(
        self, name: str, value: float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Observe a value in a histogram."""
        if name not in self.metrics:
            logger.warning(f"Histogram {name} not registered")
            return

        histogram = self.metrics[name]
        labels = labels or {}

        if labels:
            histogram.labels(**labels).observe(value)
        else:
            histogram.observe(value)

    def get_metrics_text(self) -> str:
        """Get metrics in Prometheus text format."""
        return generate_latest(self.registry).decode("utf-8")


class InMemoryCollector(MetricsCollector):
    """In-memory metrics collector for testing/development."""

    def __init__(self):
        self.metrics: builtins.dict[str, builtins.dict[str, Any]] = defaultdict(dict)
        self.counters: builtins.dict[str, float] = defaultdict(float)
        self.gauges: builtins.dict[str, float] = {}
        self.histograms: builtins.dict[str, builtins.list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        logger.info("In-memory metrics collector initialized")

    async def collect_metric(
        self, name: str, value: int | float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Collect a generic metric value."""
        with self._lock:
            label_key = self._make_label_key(labels)
            self.metrics[name][label_key] = {
                "value": value,
                "labels": labels or {},
                "timestamp": datetime.now(timezone.utc),
            }

    async def increment_counter(
        self, name: str, labels: builtins.dict[str, str] = None, amount: float = 1.0
    ) -> None:
        """Increment a counter metric."""
        with self._lock:
            label_key = self._make_label_key(labels)
            key = f"{name}:{label_key}"
            self.counters[key] += amount

    async def set_gauge(
        self, name: str, value: float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Set a gauge metric value."""
        with self._lock:
            label_key = self._make_label_key(labels)
            key = f"{name}:{label_key}"
            self.gauges[key] = value

    async def observe_histogram(
        self, name: str, value: float, labels: builtins.dict[str, str] = None
    ) -> None:
        """Observe a value in a histogram."""
        with self._lock:
            label_key = self._make_label_key(labels)
            key = f"{name}:{label_key}"
            self.histograms[key].append(value)

    def _make_label_key(self, labels: builtins.dict[str, str] | None) -> str:
        """Create a consistent key from labels."""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def get_counter(self, name: str, labels: builtins.dict[str, str] = None) -> float:
        """Get counter value."""
        label_key = self._make_label_key(labels)
        key = f"{name}:{label_key}"
        return self.counters.get(key, 0.0)

    def get_gauge(self, name: str, labels: builtins.dict[str, str] = None) -> float | None:
        """Get gauge value."""
        label_key = self._make_label_key(labels)
        key = f"{name}:{label_key}"
        return self.gauges.get(key)

    def get_histogram_values(
        self, name: str, labels: builtins.dict[str, str] = None
    ) -> builtins.list[float]:
        """Get histogram values."""
        label_key = self._make_label_key(labels)
        key = f"{name}:{label_key}"
        return self.histograms.get(key, [])


class HealthCheck(ABC):
    """Abstract base class for health checks."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """Perform the health check."""


class SimpleHealthCheck(HealthCheck):
    """Simple health check that always returns healthy."""

    async def check(self) -> HealthCheckResult:
        return HealthCheckResult(
            name=self.name, status=HealthStatus.HEALTHY, message="Service is healthy"
        )


class DatabaseHealthCheck(HealthCheck):
    """Health check for database connectivity."""

    def __init__(self, name: str, db_session_factory: Callable):
        super().__init__(name)
        self.db_session_factory = db_session_factory

    async def check(self) -> HealthCheckResult:
        """Check database connectivity."""
        start_time = time.time()

        try:
            # Simple database connectivity check
            session = self.db_session_factory()
            try:
                # Execute a simple query
                session.execute("SELECT 1")
                duration_ms = (time.time() - start_time) * 1000

                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Database connection healthy",
                    duration_ms=duration_ms,
                    details={"connection_time_ms": duration_ms},
                )
            finally:
                session.close()

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {e!s}",
                duration_ms=duration_ms,
                details={"error": str(e)},
            )


class RedisHealthCheck(HealthCheck):
    """Health check for Redis connectivity."""

    def __init__(self, name: str, redis_client):
        super().__init__(name)
        self.redis_client = redis_client

    async def check(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        start_time = time.time()

        try:
            # Simple Redis ping
            await self.redis_client.ping()
            duration_ms = (time.time() - start_time) * 1000

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Redis connection healthy",
                duration_ms=duration_ms,
                details={"ping_time_ms": duration_ms},
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {e!s}",
                duration_ms=duration_ms,
                details={"error": str(e)},
            )


class ExternalServiceHealthCheck(HealthCheck):
    """Health check for external service dependencies."""

    def __init__(self, name: str, service_url: str, timeout_seconds: float = 5.0):
        super().__init__(name)
        self.service_url = service_url
        self.timeout_seconds = timeout_seconds

    async def check(self) -> HealthCheckResult:
        """Check external service availability."""
        start_time = time.time()

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
            ) as session:
                async with session.get(self.service_url) as response:
                    duration_ms = (time.time() - start_time) * 1000

                    if response.status < 400:
                        return HealthCheckResult(
                            name=self.name,
                            status=HealthStatus.HEALTHY,
                            message=f"External service responding (HTTP {response.status})",
                            duration_ms=duration_ms,
                            details={
                                "status_code": response.status,
                                "response_time_ms": duration_ms,
                            },
                        )
                    return HealthCheckResult(
                        name=self.name,
                        status=HealthStatus.DEGRADED,
                        message=f"External service returned HTTP {response.status}",
                        duration_ms=duration_ms,
                        details={
                            "status_code": response.status,
                            "response_time_ms": duration_ms,
                        },
                    )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"External service check failed: {e!s}",
                duration_ms=duration_ms,
                details={"error": str(e)},
            )


class DistributedTracer:
    """Distributed tracing integration."""

    def __init__(self, service_name: str, jaeger_endpoint: str | None = None):
        self.service_name = service_name
        self.enabled = True

        # Configure tracer provider
        trace.set_tracer_provider(TracerProvider())
        self.tracer = trace.get_tracer(service_name)

        # Configure Jaeger exporter if endpoint provided
        if jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name="localhost",
                agent_port=14268,
                collector_endpoint=jaeger_endpoint,
            )
            span_processor = BatchSpanProcessor(jaeger_exporter)
            trace.get_tracer_provider().add_span_processor(span_processor)
            logger.info(
                f"Distributed tracing configured for {service_name} with Jaeger endpoint: {jaeger_endpoint}"
            )
        else:
            logger.info(f"Distributed tracing configured for {service_name} (no Jaeger export)")

    @asynccontextmanager
    async def trace_operation(
        self, operation_name: str, attributes: builtins.dict[str, Any] | None = None
    ):
        """Create a trace span for an operation."""
        if not self.enabled:
            yield None
            return

        with self.tracer.start_as_current_span(operation_name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))

            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise

    def instrument_fastapi(self, app):
        """Instrument FastAPI application for distributed tracing."""
        if not self.enabled:
            return

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented for distributed tracing")

    def instrument_grpc_server(self, server):
        """Instrument gRPC server for distributed tracing."""
        if not self.enabled:
            return

        GrpcInstrumentorServer().instrument_server(server)
        logger.info("gRPC server instrumented for distributed tracing")


class MonitoringManager:
    """Central monitoring and observability manager."""

    def __init__(self, service_name: str, collector: MetricsCollector | None = None):
        self.service_name = service_name
        self.collector = collector or InMemoryCollector()
        self.health_checks: builtins.dict[str, HealthCheck] = {}
        self.metrics_definitions: builtins.dict[str, MetricDefinition] = {}
        self.service_metrics = ServiceMetrics(service_name)
        self.tracer: DistributedTracer | None = None

        # Default metrics
        self._register_default_metrics()
        logger.info(f"Monitoring manager initialized for service: {service_name}")

    def _register_default_metrics(self):
        """Register default service metrics."""
        default_metrics = [
            MetricDefinition(
                "requests_total",
                MetricType.COUNTER,
                "Total number of requests",
                ["method", "endpoint", "status"],
            ),
            MetricDefinition(
                "request_duration_seconds",
                MetricType.HISTOGRAM,
                "Request duration in seconds",
                ["method", "endpoint"],
            ),
            MetricDefinition(
                "active_connections", MetricType.GAUGE, "Number of active connections"
            ),
            MetricDefinition(
                "errors_total",
                MetricType.COUNTER,
                "Total number of errors",
                ["error_type"],
            ),
            MetricDefinition(
                "health_check_duration",
                MetricType.HISTOGRAM,
                "Health check duration",
                ["check_name"],
            ),
        ]

        for metric_def in default_metrics:
            self.register_metric(metric_def)

    def register_metric(self, definition: MetricDefinition) -> None:
        """Register a custom metric."""
        self.metrics_definitions[definition.name] = definition

        if isinstance(self.collector, PrometheusCollector):
            self.collector.register_metric(definition)

        logger.info(f"Registered metric: {definition.name}")

    def set_collector(self, collector: MetricsCollector) -> None:
        """Set the metrics collector."""
        self.collector = collector

        # Re-register all metrics with new collector
        if isinstance(collector, PrometheusCollector):
            for metric_def in self.metrics_definitions.values():
                collector.register_metric(metric_def)

    def enable_distributed_tracing(self, jaeger_endpoint: str | None = None) -> None:
        """Enable distributed tracing."""
        self.tracer = DistributedTracer(self.service_name, jaeger_endpoint)

    def add_health_check(self, health_check: HealthCheck) -> None:
        """Add a health check."""
        self.health_checks[health_check.name] = health_check
        logger.info(f"Added health check: {health_check.name}")

    async def record_request(
        self, method: str, endpoint: str, status_code: int, duration_seconds: float
    ) -> None:
        """Record a request metric."""
        labels = {"method": method, "endpoint": endpoint, "status": str(status_code)}

        await self.collector.increment_counter("requests_total", labels)
        await self.collector.observe_histogram(
            "request_duration_seconds",
            duration_seconds,
            {"method": method, "endpoint": endpoint},
        )

        # Update service metrics
        self.service_metrics.request_count += 1
        self.service_metrics.request_duration_sum += duration_seconds
        if status_code >= 400:
            self.service_metrics.error_count += 1
        self.service_metrics.last_update = datetime.now(timezone.utc)

    async def record_error(self, error_type: str) -> None:
        """Record an error metric."""
        await self.collector.increment_counter("errors_total", {"error_type": error_type})

    async def set_active_connections(self, count: int) -> None:
        """Set the number of active connections."""
        await self.collector.set_gauge("active_connections", float(count))
        self.service_metrics.active_connections = count

    async def perform_health_checks(self) -> builtins.dict[str, HealthCheckResult]:
        """Perform all registered health checks."""
        results = {}

        for name, health_check in self.health_checks.items():
            start_time = time.time()
            try:
                result = await health_check.check()
                results[name] = result

                # Record health check duration
                duration = time.time() - start_time
                await self.collector.observe_histogram(
                    "health_check_duration", duration, {"check_name": name}
                )

            except Exception as e:
                duration = time.time() - start_time
                results[name] = HealthCheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {e!s}",
                    duration_ms=duration * 1000,
                    details={"error": str(e)},
                )
                logger.error(f"Health check {name} failed: {e}")

        return results

    async def get_service_health(self) -> builtins.dict[str, Any]:
        """Get overall service health status."""
        health_results = await self.perform_health_checks()

        # Determine overall status
        overall_status = HealthStatus.HEALTHY
        if any(result.status == HealthStatus.UNHEALTHY for result in health_results.values()):
            overall_status = HealthStatus.UNHEALTHY
        elif any(result.status == HealthStatus.DEGRADED for result in health_results.values()):
            overall_status = HealthStatus.DEGRADED

        return {
            "service": self.service_name,
            "status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms,
                    "details": result.details,
                }
                for name, result in health_results.items()
            },
            "metrics": {
                "request_count": self.service_metrics.request_count,
                "error_count": self.service_metrics.error_count,
                "active_connections": self.service_metrics.active_connections,
                "avg_request_duration": (
                    self.service_metrics.request_duration_sum / self.service_metrics.request_count
                    if self.service_metrics.request_count > 0
                    else 0
                ),
            },
        }

    def get_metrics_text(self) -> str | None:
        """Get metrics in Prometheus text format."""
        if isinstance(self.collector, PrometheusCollector):
            return self.collector.get_metrics_text()
        return None


def get_monitoring_manager() -> MonitoringManager | None:
    """
    Get the monitoring manager instance using dependency injection.

    Returns:
        MonitoringManager instance or None if not registered
    """
    return get_service_optional(MonitoringManager)


def set_monitoring_manager(manager: MonitoringManager) -> None:
    """Set the monitoring manager instance using dependency injection."""
    register_instance(MonitoringManager, manager)


def initialize_monitoring(
    service_name: str,
    use_prometheus: bool = True,
    jaeger_endpoint: str | None = None,
) -> MonitoringManager:
    """Initialize monitoring for a service."""

    # Create collector
    if use_prometheus:
        collector = PrometheusCollector()
    else:
        collector = InMemoryCollector()

    # Create monitoring manager
    manager = MonitoringManager(service_name, collector)

    # Enable distributed tracing if requested
    if jaeger_endpoint:
        manager.enable_distributed_tracing(jaeger_endpoint)

    # Set as global instance
    set_monitoring_manager(manager)

    logger.info(f"Monitoring initialized for {service_name}")
    return manager
