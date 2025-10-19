"""
Unified Observability Framework for Marty Services.

This module provides a standardized observability layer that integrates with the
unified configuration system to provide consistent metrics, tracing, and health
monitoring across all Marty microservices.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest

# MMF framework imports
from marty_msf.framework.config import BaseServiceConfig
from marty_msf.observability.monitoring import (
    HealthCheck,
    HealthChecker,
    HealthStatus,
    MetricsCollector,
)

# OpenTelemetry imports for tracing
try:

    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False

# Prometheus client
try:

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class BusinessMetric:
    """Definition for a business-specific metric."""

    name: str
    metric_type: str  # counter, histogram, gauge, info
    description: str
    labels: list[str] = field(default_factory=list)
    buckets: list[float] | None = None  # For histograms


class ObservabilityManager:
    """
    Unified observability manager that provides consistent monitoring, metrics,
    and tracing across all Marty services using the unified configuration system.
    """

    def __init__(self, config: BaseServiceConfig):
        """
        Initialize observability manager with unified configuration.

        Args:
            config: Service configuration from unified config system
        """
        self.config = config
        self.service_name = config.service_name
        self.monitoring_config = config.monitoring
        self.logger = logging.getLogger(f"marty.{self.service_name}.observability")

        # Initialize components
        self._metrics_collector: MetricsCollector | None = None
        self._health_checker: HealthChecker | None = None
        self._tracer: Any | None = None
        self._business_metrics: dict[str, Any] = {}

        # Setup observability components
        self._setup_metrics()
        self._setup_health_checks()
        self._setup_tracing()

        self.logger.info(f"Observability manager initialized for {self.service_name}")

    def _setup_metrics(self) -> None:
        """Setup metrics collection using configuration."""
        if not self.monitoring_config.enabled:
            self.logger.info("Monitoring disabled in configuration")
            return

        if not PROMETHEUS_AVAILABLE:
            self.logger.warning("Prometheus client not available, metrics disabled")
            return

        # Create MMF metrics collector
        self._metrics_collector = MetricsCollector(
            service_name=self.service_name,
            registry=None,  # Use default registry
        )

        # Setup business metrics from configuration
        self._setup_business_metrics()

        self.logger.info(
            f"Metrics collection enabled on port {self.monitoring_config.metrics_port}"
        )

    def _setup_business_metrics(self) -> None:
        """Setup business-specific metrics from configuration."""
        if not hasattr(self.monitoring_config, "business_metrics"):
            return

        business_metrics = getattr(self.monitoring_config, "business_metrics", [])

        for metric_def in business_metrics:
            if isinstance(metric_def, dict):
                business_metric = BusinessMetric(**metric_def)
            else:
                business_metric = metric_def

            metric_name = f"marty_{self.service_name}_{business_metric.name}"

            if business_metric.metric_type == "counter":
                self._business_metrics[business_metric.name] = Counter(
                    metric_name, business_metric.description, business_metric.labels
                )
            elif business_metric.metric_type == "histogram":
                buckets = business_metric.buckets or [
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
                ]
                self._business_metrics[business_metric.name] = Histogram(
                    metric_name,
                    business_metric.description,
                    business_metric.labels,
                    buckets=buckets,
                )
            elif business_metric.metric_type == "gauge":
                self._business_metrics[business_metric.name] = Gauge(
                    metric_name, business_metric.description, business_metric.labels
                )
            elif business_metric.metric_type == "info":
                self._business_metrics[business_metric.name] = Info(
                    metric_name, business_metric.description
                )

        self.logger.info(f"Setup {len(self._business_metrics)} business metrics")

    def _setup_health_checks(self) -> None:
        """Setup health checking system."""
        if not self.monitoring_config.enabled:
            return

        self._health_checker = HealthChecker()

        # Register default health checks
        self._register_default_health_checks()

        self.logger.info("Health checking system initialized")

    def _register_default_health_checks(self) -> None:
        """Register default health checks for all services."""

        # Database health check (if database is configured)
        if hasattr(self.config, "database") and self.config.database:
            self._health_checker.register_check(
                HealthCheck(
                    name="database", check_func=self._check_database_health, timeout_seconds=10
                )
            )

        # Service discovery health check
        if hasattr(self.config, "service_discovery"):
            self._health_checker.register_check(
                HealthCheck(
                    name="service_discovery",
                    check_func=self._check_service_discovery_health,
                    timeout_seconds=5,
                )
            )

    async def _check_database_health(self) -> HealthStatus:
        """Check database connectivity."""
        try:
            # This would use the database manager from service dependencies
            # For now, return healthy as placeholder
            return HealthStatus.HEALTHY
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return HealthStatus.UNHEALTHY

    async def _check_service_discovery_health(self) -> HealthStatus:
        """Check service discovery connectivity."""
        try:
            # Check if we can resolve configured services
            discovery_config = self.config.service_discovery
            if len(discovery_config.hosts) == 0:
                return HealthStatus.DEGRADED
            return HealthStatus.HEALTHY
        except Exception as e:
            self.logger.error(f"Service discovery health check failed: {e}")
            return HealthStatus.DEGRADED

    def _setup_tracing(self) -> None:
        """Setup distributed tracing using configuration."""
        if not self.monitoring_config.enabled:
            return

        if not TRACING_AVAILABLE:
            self.logger.warning("OpenTelemetry not available, tracing disabled")
            return

        tracing_config = getattr(self.monitoring_config, "tracing", None)
        if not tracing_config or not getattr(tracing_config, "enabled", False):
            self.logger.info("Tracing disabled in configuration")
            return

        # Setup tracing provider
        resource = Resource.create(
            {
                "service.name": self.service_name,
                "service.version": "1.0.0",
                "deployment.environment": self.config.environment.value,
            }
        )

        provider = TracerProvider(resource=resource)

        # Setup Jaeger exporter
        jaeger_endpoint = getattr(tracing_config, "jaeger_endpoint", None)
        if jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name="localhost",
                agent_port=6831,
                collector_endpoint=jaeger_endpoint,
            )

            # Setup batch span processor
            span_processor = BatchSpanProcessor(jaeger_exporter)
            provider.add_span_processor(span_processor)

        # Set the tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer for this service
        self._tracer = trace.get_tracer(f"marty.{self.service_name}", version="1.0.0")

        self.logger.info("Distributed tracing initialized")

    # Public API methods

    def get_metrics_collector(self) -> MetricsCollector | None:
        """Get the metrics collector instance."""
        return self._metrics_collector

    def get_business_metrics(self) -> dict[str, Any]:
        """Get business-specific metrics for the service."""
        return self._business_metrics

    def counter(self, name: str, description: str, labels: list[str] = None) -> Any | None:
        """Create or get a counter metric."""
        if not PROMETHEUS_AVAILABLE or not self._metrics_collector:
            return None

        labels = labels or []
        metric_name = f"marty_{self.service_name}_{name}"
        return Counter(metric_name, description, labels)

    def histogram(
        self, name: str, description: str, labels: list[str] = None, buckets: list[float] = None
    ) -> Any | None:
        """Create or get a histogram metric."""
        if not PROMETHEUS_AVAILABLE or not self._metrics_collector:
            return None

        labels = labels or []
        buckets = buckets or [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        metric_name = f"marty_{self.service_name}_{name}"
        return Histogram(metric_name, description, labels, buckets=buckets)

    def gauge(self, name: str, description: str, labels: list[str] = None) -> Any | None:
        """Create or get a gauge metric."""
        if not PROMETHEUS_AVAILABLE or not self._metrics_collector:
            return None

        labels = labels or []
        metric_name = f"marty_{self.service_name}_{name}"
        return Gauge(metric_name, description, labels)

    @contextmanager
    def trace_operation(self, operation_name: str, **attributes):
        """Context manager for tracing operations."""
        if not self._tracer:
            yield None
            return

        with self._tracer.start_as_current_span(operation_name) as span:
            # Set service attributes
            span.set_attribute("service.name", self.service_name)
            span.set_attribute("service.operation", operation_name)

            # Set custom attributes
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

            yield span

    @asynccontextmanager
    async def trace_async_operation(self, operation_name: str, **attributes):
        """Async context manager for tracing operations."""
        if not self._tracer:
            yield None
            return

        with self._tracer.start_as_current_span(operation_name) as span:
            # Set service attributes
            span.set_attribute("service.name", self.service_name)
            span.set_attribute("service.operation", operation_name)

            # Set custom attributes
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

            yield span

    def register_health_check(
        self, name: str, check_func: Callable, interval_seconds: int = 30, timeout_seconds: int = 10
    ) -> None:
        """Register a custom health check."""
        if not self._health_checker:
            self.logger.warning("Health checker not available")
            return

        health_check = HealthCheck(
            name=name,
            check_func=check_func,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
        )

        self._health_checker.register_check(health_check)
        self.logger.info(f"Registered health check: {name}")

    async def get_health_status(self, check_name: str = None) -> dict[str, Any]:
        """Get health status for service or specific check."""
        if not self._health_checker:
            return {"status": "unknown", "message": "Health checker not available"}

        if check_name:
            return await self._health_checker.run_check(check_name)
        else:
            return await self._health_checker.run_all_checks()

    def get_metrics_output(self) -> str:
        """Get Prometheus metrics output."""
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus not available"

        return generate_latest().decode("utf-8")

    async def shutdown(self) -> None:
        """Shutdown observability components."""
        self.logger.info("Shutting down observability components")

        if self._health_checker:
            # Stop health checking background tasks if any
            pass

        # Flush any remaining traces
        if self._tracer and hasattr(trace.get_tracer_provider(), "shutdown"):
            trace.get_tracer_provider().shutdown()

        self.logger.info("Observability shutdown complete")


# Factory function for easy integration
def create_observability_manager(config: BaseServiceConfig) -> ObservabilityManager:
    """
    Factory function to create an observability manager from service config.

    Args:
        config: Service configuration from unified config system

    Returns:
        ObservabilityManager instance
    """
    return ObservabilityManager(config)


# Decorator for automatic operation tracing
def trace_grpc_method(observability_manager: ObservabilityManager):
    """Decorator to automatically trace gRPC service methods."""

    def decorator(func):
        async def wrapper(self, request, context):
            method_name = func.__name__

            with observability_manager.trace_operation(
                f"grpc.{method_name}",
                grpc_method=method_name,
                service=observability_manager.service_name,
            ) as span:
                try:
                    # Execute the method
                    result = await func(self, request, context)

                    # Record success
                    if span:
                        span.set_attribute("grpc.success", True)
                        span.set_attribute("grpc.status", "OK")

                    return result

                except Exception as e:
                    # Record error
                    if span:
                        span.set_attribute("grpc.success", False)
                        span.set_attribute("grpc.error", str(e))
                        span.set_attribute("grpc.error_type", type(e).__name__)

                    raise

        return wrapper

    return decorator


# Marty-specific metric helpers
class MartyMetrics:
    """Helper class for Marty-specific business metrics."""

    @staticmethod
    def certificate_validation_metrics(observability: ObservabilityManager):
        """Setup certificate validation metrics for trust services."""
        return {
            "validations_total": observability.counter(
                "certificate_validations_total",
                "Total certificate validations performed",
                ["result", "certificate_type", "issuer_country"],
            ),
            "validation_duration": observability.histogram(
                "certificate_validation_duration_seconds",
                "Time to validate certificates",
                ["certificate_type"],
                buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 5.0],
            ),
            "trust_chain_length": observability.histogram(
                "trust_chain_length",
                "Length of certificate trust chains",
                ["certificate_type"],
                buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            ),
        }

    @staticmethod
    def document_signing_metrics(observability: ObservabilityManager):
        """Setup document signing metrics for signing services."""
        return {
            "documents_signed": observability.counter(
                "documents_signed_total",
                "Total documents signed",
                ["algorithm", "document_type", "result"],
            ),
            "signing_duration": observability.histogram(
                "document_signing_duration_seconds",
                "Time to sign documents",
                ["algorithm", "document_type"],
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
            ),
            "key_operations": observability.counter(
                "cryptographic_key_operations_total",
                "Cryptographic key operations",
                ["operation", "key_type", "result"],
            ),
        }

    @staticmethod
    def pkd_sync_metrics(observability: ObservabilityManager):
        """Setup PKD synchronization metrics."""
        return {
            "sync_operations": observability.counter(
                "pkd_sync_operations_total",
                "PKD synchronization operations",
                ["result", "sync_type"],
            ),
            "sync_duration": observability.histogram(
                "pkd_sync_duration_seconds",
                "Time to complete PKD sync",
                ["sync_type"],
                buckets=[1, 5, 10, 30, 60, 120, 300],
            ),
            "records_processed": observability.histogram(
                "pkd_records_processed",
                "Number of records processed during sync",
                ["sync_type"],
                buckets=[10, 50, 100, 500, 1000, 5000, 10000],
            ),
        }
