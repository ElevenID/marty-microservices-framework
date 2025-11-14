"""
Metrics collection infrastructure for Marty Microservices Framework

Provides standardized metrics collection with Prometheus integration,
including gRPC metrics, business metrics, and custom metrics.
"""

import builtins
import functools
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)


@dataclass
class MetricsConfig:
    """Configuration for metrics collection"""

    service_name: str
    service_version: str = "1.0.0"
    namespace: str = "marty"
    enable_grpc_metrics: bool = True
    enable_business_metrics: bool = True
    custom_labels: builtins.dict[str, str] | None = None


class MetricsCollector:
    """
    Centralized metrics collector for microservices

    Provides standardized metrics collection with:
    - gRPC request/response metrics
    - Business logic metrics
    - System performance metrics
    - Custom metrics registration
    """

    def __init__(self, config: MetricsConfig):
        self.config = config
        self.registry = CollectorRegistry()
        self.labels = self._build_default_labels()

        # Initialize standard metrics
        self._init_grpc_metrics()
        self._init_business_metrics()
        self._init_system_metrics()

    def _build_default_labels(self) -> builtins.dict[str, str]:
        """Build default labels for all metrics"""
        labels = {
            "service_name": self.config.service_name,
            "service_version": self.config.service_version,
        }

        if self.config.custom_labels:
            labels.update(self.config.custom_labels)

        return labels

    def _init_grpc_metrics(self) -> None:
        """Initialize gRPC-specific metrics"""
        if not self.config.enable_grpc_metrics:
            return

        # gRPC request counters
        self.grpc_requests_total = Counter(
            name=f"{self.config.namespace}_grpc_requests_total",
            documentation="Total number of gRPC requests",
            labelnames=["service_name", "grpc_method", "grpc_service"],
            registry=self.registry,
        )

        self.grpc_responses_total = Counter(
            name=f"{self.config.namespace}_grpc_responses_total",
            documentation="Total number of gRPC responses",
            labelnames=["service_name", "grpc_method", "grpc_service", "grpc_code"],
            registry=self.registry,
        )

        # gRPC request duration
        self.grpc_request_duration = Histogram(
            name=f"{self.config.namespace}_grpc_request_duration_seconds",
            documentation="Duration of gRPC requests in seconds",
            labelnames=["service_name", "grpc_method", "grpc_service"],
            buckets=[
                0.001,
                0.005,
                0.01,
                0.025,
                0.05,
                0.1,
                0.25,
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
            ],
            registry=self.registry,
        )

        # gRPC request size
        self.grpc_request_size = Histogram(
            name=f"{self.config.namespace}_grpc_request_size_bytes",
            documentation="Size of gRPC requests in bytes",
            labelnames=["service_name", "grpc_method", "grpc_service"],
            buckets=[32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384],
            registry=self.registry,
        )

        # gRPC response size
        self.grpc_response_size = Histogram(
            name=f"{self.config.namespace}_grpc_response_size_bytes",
            documentation="Size of gRPC responses in bytes",
            labelnames=["service_name", "grpc_method", "grpc_service"],
            buckets=[32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384],
            registry=self.registry,
        )

        # Active gRPC connections
        self.grpc_connections_active = Gauge(
            name=f"{self.config.namespace}_grpc_connections_active",
            documentation="Number of active gRPC connections",
            labelnames=["service_name"],
            registry=self.registry,
        )

    def _init_business_metrics(self) -> None:
        """Initialize business-specific metrics"""
        if not self.config.enable_business_metrics:
            return

        # Business transaction counters
        self.business_transactions_total = Counter(
            name=f"{self.config.namespace}_business_transactions_total",
            documentation="Total number of business transactions",
            labelnames=["service_name", "transaction_type", "status"],
            registry=self.registry,
        )

        # Business transaction duration
        self.business_transaction_duration = Histogram(
            name=f"{self.config.namespace}_business_transaction_duration_seconds",
            documentation="Duration of business transactions in seconds",
            labelnames=["service_name", "transaction_type"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry,
        )

        # Active business operations
        self.business_operations_active = Gauge(
            name=f"{self.config.namespace}_business_operations_active",
            documentation="Number of active business operations",
            labelnames=["service_name", "operation_type"],
            registry=self.registry,
        )

    def _init_system_metrics(self) -> None:
        """Initialize system performance metrics"""
        # Database connection pool
        self.db_connections_active = Gauge(
            name=f"{self.config.namespace}_db_connections_active",
            documentation="Number of active database connections",
            labelnames=["service_name", "database"],
            registry=self.registry,
        )

        self.db_connections_max = Gauge(
            name=f"{self.config.namespace}_db_connections_max",
            documentation="Maximum number of database connections",
            labelnames=["service_name", "database"],
            registry=self.registry,
        )

        # Cache hit rates
        self.cache_hits_total = Counter(
            name=f"{self.config.namespace}_cache_hits_total",
            documentation="Total number of cache hits",
            labelnames=["service_name", "cache_name"],
            registry=self.registry,
        )

        self.cache_misses_total = Counter(
            name=f"{self.config.namespace}_cache_misses_total",
            documentation="Total number of cache misses",
            labelnames=["service_name", "cache_name"],
            registry=self.registry,
        )

        # Event bus metrics
        self.events_published_total = Counter(
            name=f"{self.config.namespace}_events_published_total",
            documentation="Total number of events published",
            labelnames=["service_name", "event_type", "topic"],
            registry=self.registry,
        )

        self.events_consumed_total = Counter(
            name=f"{self.config.namespace}_events_consumed_total",
            documentation="Total number of events consumed",
            labelnames=["service_name", "event_type", "topic"],
            registry=self.registry,
        )

    def record_grpc_request(
        self,
        method: str,
        service: str,
        duration: float,
        request_size: int,
        response_size: int,
        status_code: str,
    ) -> None:
        """Record gRPC request metrics"""
        labels = {
            "service_name": self.config.service_name,
            "grpc_method": method,
            "grpc_service": service,
        }

        response_labels = {**labels, "grpc_code": status_code}

        self.grpc_requests_total.labels(**labels).inc()
        self.grpc_responses_total.labels(**response_labels).inc()
        self.grpc_request_duration.labels(**labels).observe(duration)
        self.grpc_request_size.labels(**labels).observe(request_size)
        self.grpc_response_size.labels(**labels).observe(response_size)

    def record_business_transaction(
        self, transaction_type: str, duration: float, status: str = "success"
    ) -> None:
        """Record business transaction metrics"""
        labels = {
            "service_name": self.config.service_name,
            "transaction_type": transaction_type,
            "status": status,
        }

        duration_labels = {
            "service_name": self.config.service_name,
            "transaction_type": transaction_type,
        }

        self.business_transactions_total.labels(**labels).inc()
        self.business_transaction_duration.labels(**duration_labels).observe(duration)

    def record_event_published(self, event_type: str, topic: str) -> None:
        """Record event publication"""
        labels = {
            "service_name": self.config.service_name,
            "event_type": event_type,
            "topic": topic,
        }
        self.events_published_total.labels(**labels).inc()

    def record_event_consumed(self, event_type: str, topic: str) -> None:
        """Record event consumption"""
        labels = {
            "service_name": self.config.service_name,
            "event_type": event_type,
            "topic": topic,
        }
        self.events_consumed_total.labels(**labels).inc()

    def record_cache_hit(self, cache_name: str) -> None:
        """Record cache hit"""
        labels = {"service_name": self.config.service_name, "cache_name": cache_name}
        self.cache_hits_total.labels(**labels).inc()

    def record_cache_miss(self, cache_name: str) -> None:
        """Record cache miss"""
        labels = {"service_name": self.config.service_name, "cache_name": cache_name}
        self.cache_misses_total.labels(**labels).inc()

    def set_db_connections(self, active: int, max_connections: int, database: str) -> None:
        """Set database connection metrics"""
        labels = {"service_name": self.config.service_name, "database": database}
        self.db_connections_active.labels(**labels).set(active)
        self.db_connections_max.labels(**labels).set(max_connections)

    def create_custom_counter(
        self, name: str, description: str, labels: builtins.list[str]
    ) -> Counter:
        """Create a custom counter metric"""
        return Counter(
            name=f"{self.config.namespace}_{name}",
            documentation=description,
            labelnames=labels,
            registry=self.registry,
        )

    def create_custom_histogram(
        self,
        name: str,
        description: str,
        labels: builtins.list[str],
        buckets: builtins.list[float] | None = None,
    ) -> Histogram:
        """Create a custom histogram metric"""
        histogram_kwargs = {
            "name": f"{self.config.namespace}_{name}",
            "documentation": description,
            "labelnames": labels,
            "registry": self.registry,
        }
        if buckets is not None:
            histogram_kwargs["buckets"] = buckets

        return Histogram(**histogram_kwargs)

    def create_custom_gauge(self, name: str, description: str, labels: builtins.list[str]) -> Gauge:
        """Create a custom gauge metric"""
        return Gauge(
            name=f"{self.config.namespace}_{name}",
            documentation=description,
            labelnames=labels,
            registry=self.registry,
        )

    def get_metrics(self) -> str:
        """Generate Prometheus metrics output"""
        return generate_latest(self.registry).decode("utf-8")

    def get_content_type(self) -> str:
        """Get content type for metrics endpoint"""
        return CONTENT_TYPE_LATEST


def grpc_metrics_decorator(metrics_collector: MetricsCollector):
    """Decorator to automatically collect gRPC metrics"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            # Extract method and service from function
            method = func.__name__
            service = func.__module__.split(".")[-1] if hasattr(func, "__module__") else "unknown"

            try:
                result = await func(*args, **kwargs)

                # Calculate metrics
                duration = time.time() - start_time
                request_size = len(str(args)) + len(str(kwargs))  # Approximate
                response_size = len(str(result)) if result else 0  # Approximate

                metrics_collector.record_grpc_request(
                    method=method,
                    service=service,
                    duration=duration,
                    request_size=request_size,
                    response_size=response_size,
                    status_code="OK",
                )

                return result

            except Exception:
                duration = time.time() - start_time

                metrics_collector.record_grpc_request(
                    method=method,
                    service=service,
                    duration=duration,
                    request_size=len(str(args)) + len(str(kwargs)),
                    response_size=0,
                    status_code="INTERNAL",
                )

                raise

        return wrapper

    return decorator


def business_metrics_decorator(metrics_collector: MetricsCollector, transaction_type: str):
    """Decorator to automatically collect business transaction metrics"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                metrics_collector.record_business_transaction(
                    transaction_type=transaction_type,
                    duration=duration,
                    status="success",
                )

                return result

            except Exception:
                duration = time.time() - start_time

                metrics_collector.record_business_transaction(
                    transaction_type=transaction_type, duration=duration, status="error"
                )

                raise

        return wrapper

    return decorator
