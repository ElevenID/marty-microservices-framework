"""
Service health monitoring and metrics collection infrastructure.

Provides comprehensive monitoring capabilities including health checks, metrics collection,
centralized logging, and alerting for all microservices.
"""

from __future__ import annotations

import builtins
import concurrent.futures
import logging
import socket
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import psutil
import requests
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

from mmf.framework.observability.domain.protocols import (
    HealthCheck,
    HealthStatus,
    IHealthChecker,
    IMetricsCollector,
    MetricType,
)

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Metric:
    """Metric data point."""

    name: str
    value: float
    type: MetricType
    labels: builtins.dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    help_text: str = ""


@dataclass
class Alert:
    """Alert definition."""

    id: str
    name: str
    severity: AlertSeverity
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved: bool = False
    labels: builtins.dict[str, str] = field(default_factory=dict)


class MetricsCollector(IMetricsCollector):
    """Collects and manages metrics using Prometheus."""

    def __init__(self, service_name: str = "microservice", registry=None):
        self.service_name = service_name
        self.registry = registry or CollectorRegistry()

        # Service info metric
        self.service_info = Info("mmf_service_info", "Service information", registry=self.registry)
        self.service_info.info({"service": service_name, "version": "1.0.0"})

        # Request metrics
        self.requests_total = Counter(
            "mmf_requests_total",
            "Total requests",
            ["service", "method", "status"],
            registry=self.registry,
        )

        self.request_duration = Histogram(
            "mmf_request_duration_seconds",
            "Request duration in seconds",
            ["service", "method"],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            registry=self.registry,
        )

        # Error metrics
        self.errors_total = Counter(
            "mmf_errors_total",
            "Total errors",
            ["service", "method", "error_type"],
            registry=self.registry,
        )

        # Custom metrics registry
        self._custom_counters: dict[str, Counter] = {}
        self._custom_gauges: dict[str, Gauge] = {}
        self._custom_histograms: dict[str, Histogram] = {}

    def counter(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Value to add (default 1.0)
            labels: Optional labels
        """
        labels = labels or {}
        labels["service"] = self.service_name

        # Get or create counter
        counter_key = name
        if counter_key not in self._custom_counters:
            self._custom_counters[counter_key] = Counter(
                f"mmf_{name}",
                f"Custom counter: {name}",
                list(labels.keys()),
                registry=self.registry,
            )

        self._custom_counters[counter_key].labels(**labels).inc(value)

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge metric.

        Args:
            name: Metric name
            value: Current value
            labels: Optional labels
        """
        labels = labels or {}
        labels["service"] = self.service_name

        # Get or create gauge
        gauge_key = name
        if gauge_key not in self._custom_gauges:
            self._custom_gauges[gauge_key] = Gauge(
                f"mmf_{name}",
                f"Custom gauge: {name}",
                list(labels.keys()),
                registry=self.registry,
            )

        self._custom_gauges[gauge_key].labels(**labels).set(value)

    def histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Add a value to a histogram metric.

        Args:
            name: Metric name
            value: Value to add
            labels: Optional labels
        """
        labels = labels or {}
        labels["service"] = self.service_name

        # Get or create histogram
        hist_key = name
        if hist_key not in self._custom_histograms:
            self._custom_histograms[hist_key] = Histogram(
                f"mmf_{name}",
                f"Custom histogram: {name}",
                list(labels.keys()),
                registry=self.registry,
            )

        self._custom_histograms[hist_key].labels(**labels).observe(value)

    def record_request(self, method: str, status: str, duration: float) -> None:
        """Record an HTTP/gRPC request.

        Args:
            method: Request method/endpoint
            status: Response status
            duration: Request duration in seconds
        """
        self.requests_total.labels(service=self.service_name, method=method, status=status).inc()

        self.request_duration.labels(service=self.service_name, method=method).observe(duration)

    def record_error(self, method: str, error_type: str) -> None:
        """Record an error.

        Args:
            method: Request method/endpoint
            error_type: Type of error
        """
        self.errors_total.labels(
            service=self.service_name, method=method, error_type=error_type
        ).inc()

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus text format.

        Returns:
            Metrics in Prometheus format
        """
        if self.registry is None:
            return "# Registry not available\n"

        return generate_latest(self.registry).decode("utf-8")

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get metrics summary for compatibility.

        Returns:
            Metrics summary dictionary
        """
        return {
            "service": self.service_name,
            "registry": str(self.registry),
        }


class HealthChecker(IHealthChecker):
    """Manages health checks."""

    def __init__(self):
        self._checks: builtins.dict[str, HealthCheck] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def register_check(self, health_check: HealthCheck) -> None:
        """Register a health check.

        Args:
            health_check: Health check to register
        """
        self._checks[health_check.name] = health_check
        logger.info("Registered health check: %s", health_check.name)

    def unregister_check(self, name: str) -> None:
        """Unregister a health check.

        Args:
            name: Name of health check to remove
        """
        if name in self._checks:
            del self._checks[name]
            logger.info("Unregistered health check: %s", name)

    def run_check(self, name: str) -> HealthStatus:
        """Run a specific health check.

        Args:
            name: Name of health check to run

        Returns:
            Health status result
        """
        if name not in self._checks:
            return HealthStatus.UNKNOWN

        check = self._checks[name]
        if not check.enabled:
            return HealthStatus.UNKNOWN

        try:
            # Run check with timeout
            result = self._run_with_timeout(check.check_func, check.timeout)

            if result:
                check.last_status = HealthStatus.HEALTHY
                check.failure_count = 0
            else:
                check.failure_count += 1
                if check.failure_count >= check.max_failures:
                    check.last_status = HealthStatus.UNHEALTHY
                else:
                    check.last_status = HealthStatus.DEGRADED

            check.last_run = datetime.now(timezone.utc)
            return check.last_status

        except Exception as e:
            logger.error("Health check %s failed: %s", name, e)
            check.failure_count += 1
            check.last_status = HealthStatus.UNHEALTHY
            check.last_run = datetime.now(timezone.utc)
            return HealthStatus.UNHEALTHY

    def run_all_checks(self) -> builtins.dict[str, HealthStatus]:
        """Run all registered health checks.

        Returns:
            Dictionary of check names to status
        """
        results = {}
        for name in self._checks:
            results[name] = self.run_check(name)
        return results

    def get_overall_status(self) -> HealthStatus:
        """Get overall health status.

        Returns:
            Overall health status based on all checks
        """
        results = self.run_all_checks()

        if not results:
            return HealthStatus.UNKNOWN

        if any(status == HealthStatus.UNHEALTHY for status in results.values()):
            return HealthStatus.UNHEALTHY
        if any(status == HealthStatus.DEGRADED for status in results.values()):
            return HealthStatus.DEGRADED
        if all(status == HealthStatus.HEALTHY for status in results.values()):
            return HealthStatus.HEALTHY
        return HealthStatus.UNKNOWN

    def start_periodic_checks(self) -> None:
        """Start periodic health check execution."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._periodic_check_loop, daemon=True)
        self._thread.start()
        logger.info("Started periodic health checks")

    def stop_periodic_checks(self) -> None:
        """Stop periodic health check execution."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=5.0)

        logger.info("Stopped periodic health checks")

    def _periodic_check_loop(self) -> None:
        """Main loop for periodic health checks."""
        while self._running and not self._stop_event.is_set():
            try:
                current_time = datetime.now(timezone.utc)

                for check in self._checks.values():
                    if not check.enabled:
                        continue

                    # Check if it's time to run this check
                    if (
                        check.last_run is None
                        or (current_time - check.last_run).total_seconds() >= check.interval
                    ):
                        self.run_check(check.name)

                # Sleep for a short interval
                self._stop_event.wait(timeout=5.0)

            except Exception as e:
                logger.error("Error in periodic health check loop: %s", e)
                self._stop_event.wait(timeout=10.0)

    @staticmethod
    def _run_with_timeout(func: Callable[[], bool], timeout: float) -> bool:
        """Run a function with timeout."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                logger.warning("Health check timed out after %s seconds", timeout)
                return False


class SystemMetrics:
    """Collects system-level metrics."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics = metrics_collector
        self._hostname = socket.gethostname()

    def collect_cpu_metrics(self) -> None:
        """Collect CPU metrics."""
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics.gauge("system_cpu_usage_percent", cpu_percent, {"hostname": self._hostname})

        # Per-core metrics
        cpu_percents = psutil.cpu_percent(percpu=True)
        for i, percent in enumerate(cpu_percents):
            self.metrics.gauge(
                "system_cpu_core_usage_percent",
                percent,
                {"hostname": self._hostname, "core": str(i)},
            )

    def collect_memory_metrics(self) -> None:
        """Collect memory metrics."""
        memory = psutil.virtual_memory()

        self.metrics.gauge("system_memory_total_bytes", memory.total, {"hostname": self._hostname})
        self.metrics.gauge("system_memory_used_bytes", memory.used, {"hostname": self._hostname})
        self.metrics.gauge(
            "system_memory_available_bytes",
            memory.available,
            {"hostname": self._hostname},
        )
        self.metrics.gauge(
            "system_memory_usage_percent", memory.percent, {"hostname": self._hostname}
        )

    def collect_disk_metrics(self) -> None:
        """Collect disk metrics."""
        disk = psutil.disk_usage("/")

        self.metrics.gauge("system_disk_total_bytes", disk.total, {"hostname": self._hostname})
        self.metrics.gauge("system_disk_used_bytes", disk.used, {"hostname": self._hostname})
        self.metrics.gauge("system_disk_free_bytes", disk.free, {"hostname": self._hostname})
        self.metrics.gauge(
            "system_disk_usage_percent",
            (disk.used / disk.total) * 100,
            {"hostname": self._hostname},
        )

    def collect_network_metrics(self) -> None:
        """Collect network metrics."""
        network = psutil.net_io_counters()

        self.metrics.counter(
            "system_network_bytes_sent",
            network.bytes_sent,
            {"hostname": self._hostname},
        )
        self.metrics.counter(
            "system_network_bytes_recv",
            network.bytes_recv,
            {"hostname": self._hostname},
        )
        self.metrics.counter(
            "system_network_packets_sent",
            network.packets_sent,
            {"hostname": self._hostname},
        )
        self.metrics.counter(
            "system_network_packets_recv",
            network.packets_recv,
            {"hostname": self._hostname},
        )

    def collect_all_metrics(self) -> None:
        """Collect all system metrics."""
        try:
            self.collect_cpu_metrics()
            self.collect_memory_metrics()
            self.collect_disk_metrics()
            self.collect_network_metrics()
        except Exception as e:
            logger.error("Error collecting system metrics: %s", e)


class ServiceMonitor:
    """Main service monitoring coordinator."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics = MetricsCollector(service_name)
        self.health_checker = HealthChecker()
        self.system_metrics = SystemMetrics(self.metrics)
        self.alerts: builtins.list[Alert] = []

        # Register default health checks
        self._register_default_checks()

    def _register_default_checks(self) -> None:
        """Register default health checks."""

        # Basic connectivity check
        def basic_check() -> bool:
            return True

        self.health_checker.register_check(
            HealthCheck(
                name="basic",
                check_func=basic_check,
                interval=10.0,
            )
        )

        # Memory usage check
        def memory_check() -> bool:
            memory = psutil.virtual_memory()
            return memory.percent < 90.0

        self.health_checker.register_check(
            HealthCheck(
                name="memory",
                check_func=memory_check,
                interval=30.0,
            )
        )

        # Disk usage check
        def disk_check() -> bool:
            disk = psutil.disk_usage("/")
            usage_percent = (disk.used / disk.total) * 100
            return usage_percent < 90.0

        self.health_checker.register_check(
            HealthCheck(
                name="disk",
                check_func=disk_check,
                interval=60.0,
            )
        )

    def start_monitoring(self) -> None:
        """Start all monitoring components."""
        self.health_checker.start_periodic_checks()
        logger.info("Service monitoring started for %s", self.service_name)

    def stop_monitoring(self) -> None:
        """Stop all monitoring components."""
        self.health_checker.stop_periodic_checks()
        logger.info("Service monitoring stopped for %s", self.service_name)

    def get_health_status(self) -> builtins.dict[str, Any]:
        """Get comprehensive health status.

        Returns:
            Health status dictionary
        """
        overall_status = self.health_checker.get_overall_status()
        check_results = self.health_checker.run_all_checks()

        return {
            "service": self.service_name,
            "status": overall_status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {name: status.value for name, status in check_results.items()},
        }

    def get_metrics_summary(self) -> builtins.dict[str, Any]:
        """Get metrics summary.

        Returns:
            Metrics summary dictionary
        """
        # Collect current system metrics
        self.system_metrics.collect_all_metrics()

        return self.metrics.get_metrics_summary()


# Timing context manager
@contextmanager
def time_operation(
    metrics_collector: MetricsCollector,
    operation_name: str,
    labels: builtins.dict[str, str] | None = None,
):
    """Context manager to time operations.

    Args:
        metrics_collector: Metrics collector instance
        operation_name: Name of the operation
        labels: Optional labels

    Example:
        with time_operation(metrics, "database_query", {"table": "users"}):
            # Database operation
            pass
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        metrics_collector.histogram(f"{operation_name}_duration_seconds", duration, labels)


# Default health check functions
def database_health_check(connection_func: Callable[[], bool]) -> Callable[[], bool]:
    """Create a database health check.

    Args:
        connection_func: Function that tests database connectivity

    Returns:
        Health check function
    """

    def check() -> bool:
        try:
            return connection_func()
        except Exception as e:
            logger.error("Database health check failed: %s", e)
            return False

    return check


def external_service_health_check(url: str, timeout: float = 5.0) -> Callable[[], bool]:
    """Create an external service health check.

    Args:
        url: URL to check
        timeout: Request timeout

    Returns:
        Health check function
    """

    def check() -> bool:
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            logger.error("External service health check failed for %s: %s", url, e)
            return False

    return check
