"""
Unified Observability Configuration for Marty Microservices Framework

This module provides standardized observability defaults that integrate OpenTelemetry,
Prometheus metrics, structured logging with correlation IDs, and comprehensive
instrumentation across all service types (FastAPI, gRPC, Hybrid).

Key Features:
- Automatic OpenTelemetry instrumentation for all common libraries
- Standardized Prometheus metrics with service-specific labeling
- Correlation ID propagation throughout the request lifecycle
- Unified configuration interface for all observability components
- Default dashboards and alerting rules
- Plugin developer debugging utilities
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

# Core OpenTelemetry imports
from opentelemetry import metrics, trace

# OpenTelemetry components
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.context import attach
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Prometheus integration
from opentelemetry.exporter.prometheus import PrometheusMetricReader

# Instrumentation libraries
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.grpc import (
    GrpcInstrumentorClient,
    GrpcInstrumentorServer,
)
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry.propagate import extract, inject, set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Framework imports
from mmf.framework.observability.adapters.logging import (
    CorrelationFilter,
    TraceContextFilter,
    UnifiedJSONFormatter,
)

logger = logging.getLogger(__name__)


@dataclass
class ObservabilityConfig:
    """Configuration for unified observability system."""

    # Service identification
    service_name: str
    service_version: str = "1.0.0"
    environment: str = "production"
    deployment_name: str | None = None

    # Tracing configuration
    tracing_enabled: bool = True
    jaeger_endpoint: str = "http://jaeger:14268/api/traces"
    otlp_trace_endpoint: str = "http://opentelemetry-collector:4317"
    trace_sample_rate: float = 1.0
    trace_export_timeout: int = 30

    # Metrics configuration
    metrics_enabled: bool = True
    prometheus_enabled: bool = True
    prometheus_port: int = 8000
    otlp_metrics_endpoint: str = "http://opentelemetry-collector:4317"
    metrics_export_interval: int = 60

    # Logging configuration
    structured_logging: bool = True
    log_level: str = "INFO"
    correlation_id_enabled: bool = True
    trace_context_in_logs: bool = True

    # Instrumentation configuration
    auto_instrument_fastapi: bool = True
    auto_instrument_grpc: bool = True
    auto_instrument_http_clients: bool = True
    auto_instrument_databases: bool = True
    auto_instrument_redis: bool = True

    # Advanced configuration
    enable_console_exporter: bool = False
    custom_resource_attributes: dict[str, str] = field(default_factory=dict)
    custom_tags: dict[str, str] = field(default_factory=dict)
    debug_mode: bool = False

    @classmethod
    def from_environment(cls, service_name: str) -> ObservabilityConfig:
        """Create configuration from environment variables."""
        return cls(
            service_name=service_name,
            service_version=os.getenv("SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ENVIRONMENT", os.getenv("ENV", "production")),
            deployment_name=os.getenv("DEPLOYMENT_NAME"),
            # Tracing
            tracing_enabled=os.getenv("TRACING_ENABLED", "true").lower() == "true",
            jaeger_endpoint=os.getenv("JAEGER_ENDPOINT", "http://jaeger:14268/api/traces"),
            otlp_trace_endpoint=os.getenv(
                "OTLP_TRACE_ENDPOINT", "http://opentelemetry-collector:4317"
            ),
            trace_sample_rate=float(os.getenv("TRACE_SAMPLE_RATE", "1.0")),
            # Metrics
            metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            prometheus_enabled=os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true",
            prometheus_port=int(os.getenv("PROMETHEUS_PORT", "8000")),
            otlp_metrics_endpoint=os.getenv(
                "OTLP_METRICS_ENDPOINT", "http://opentelemetry-collector:4317"
            ),
            # Logging
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
        )


class UnifiedObservability:
    """
    Unified observability system that provides standardized OpenTelemetry,
    Prometheus, and logging configuration for all MMF services.
    """

    def __init__(self, config: ObservabilityConfig):
        self.config = config
        self.tracer = None
        self.meter = None
        self.correlation_filter = None
        self._instrumented = False
        self._metrics_server_started = False

    def initialize(self) -> None:
        """Initialize the complete observability stack."""
        try:
            # Setup logging first
            self._setup_logging()

            # Setup tracing
            if self.config.tracing_enabled:
                self._setup_tracing()

            # Setup metrics
            if self.config.metrics_enabled:
                self._setup_metrics()

            # Setup automatic instrumentation
            self._setup_auto_instrumentation()

            # Start Prometheus metrics server if enabled
            if self.config.prometheus_enabled:
                self._start_prometheus_server()

            logger.info(
                "Unified observability initialized for service %s",
                self.config.service_name,
                extra={
                    "service_version": self.config.service_version,
                    "environment": self.config.environment,
                },
            )

        except Exception as e:
            logger.error("Failed to initialize observability: %s", e, exc_info=True)
            raise

    def _setup_logging(self) -> None:
        """Setup structured logging with correlation IDs and trace context."""
        if not self.config.structured_logging:
            return

        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.config.log_level.upper()))

        # Clear existing handlers
        root_logger.handlers.clear()

        # Create console handler with JSON formatter
        console_handler = logging.StreamHandler()

        # Setup filters
        filters = []

        # Service name filter (always included)
        service_filter = ServiceNameFilter(self.config.service_name)
        filters.append(service_filter)

        # Correlation ID filter
        if self.config.correlation_id_enabled:
            self.correlation_filter = CorrelationFilter()
            filters.append(self.correlation_filter)

        # Trace context filter
        if self.config.trace_context_in_logs:
            trace_filter = TraceContextFilter()
            filters.append(trace_filter)

        # Apply filters to handler
        for filter_obj in filters:
            console_handler.addFilter(filter_obj)

        # Setup JSON formatter
        formatter = UnifiedJSONFormatter(
            include_trace=self.config.trace_context_in_logs,
            include_correlation=self.config.correlation_id_enabled,
        )
        console_handler.setFormatter(formatter)

        # Add handler to root logger
        root_logger.addHandler(console_handler)

        logger.info("Structured logging configured")

    def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracing with standardized configuration."""
        # Create resource
        resource_attributes = {
            SERVICE_NAME: self.config.service_name,
            SERVICE_VERSION: self.config.service_version,
            "deployment.environment": self.config.environment,
            "telemetry.sdk.name": "opentelemetry",
            "telemetry.sdk.language": "python",
            "service.instance.id": str(uuid.uuid4()),
        }

        # Add deployment name if specified
        if self.config.deployment_name:
            resource_attributes["service.deployment.name"] = self.config.deployment_name

        # Add custom resource attributes
        resource_attributes.update(self.config.custom_resource_attributes)

        resource = Resource.create(resource_attributes)

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Setup OTLP exporter
        if self.config.otlp_trace_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=self.config.otlp_trace_endpoint,
                insecure=True,  # Use insecure for internal cluster communication
            )
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # Setup console exporter for debugging
        if self.config.enable_console_exporter:
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set global tracer provider
        trace.set_tracer_provider(tracer_provider)

        # Get tracer instance
        self.tracer = trace.get_tracer(self.config.service_name, self.config.service_version)

        # Setup propagators for trace context
        propagators: list[Any] = [TraceContextTextMapPropagator()]

        propagators.append(B3MultiFormat())

        propagators.append(W3CBaggagePropagator())

        composite_propagator = CompositePropagator(propagators)
        set_global_textmap(composite_propagator)

        logger.info("OpenTelemetry tracing configured")

    def _setup_metrics(self) -> None:
        """Setup OpenTelemetry metrics with Prometheus integration."""
        readers = []

        # Add Prometheus reader if enabled
        if self.config.prometheus_enabled:
            prometheus_reader = PrometheusMetricReader()
            readers.append(prometheus_reader)

        # Add OTLP metrics reader
        if self.config.otlp_metrics_endpoint:
            otlp_metrics_exporter = OTLPMetricExporter(
                endpoint=self.config.otlp_metrics_endpoint,
                insecure=True,
            )
            otlp_reader = PeriodicExportingMetricReader(
                otlp_metrics_exporter,
                export_interval_millis=self.config.metrics_export_interval * 1000,
            )
            readers.append(otlp_reader)

        # Create meter provider
        meter_provider = MeterProvider(
            resource=Resource.create(
                {
                    SERVICE_NAME: self.config.service_name,
                    SERVICE_VERSION: self.config.service_version,
                    "deployment.environment": self.config.environment,
                }
            ),
            metric_readers=readers,
        )

        # Set global meter provider
        metrics.set_meter_provider(meter_provider)

        # Get meter instance
        self.meter = metrics.get_meter(self.config.service_name, self.config.service_version)

        logger.info("OpenTelemetry metrics configured")

    def _setup_auto_instrumentation(self) -> None:
        """Setup automatic instrumentation for common libraries."""
        if self._instrumented:
            return

        try:
            # HTTP clients
            if self.config.auto_instrument_http_clients:
                RequestsInstrumentor().instrument()
                logger.debug("Requests instrumentation applied")

                HTTPXClientInstrumentor().instrument()
                logger.debug("HTTPX instrumentation applied")

                URLLib3Instrumentor().instrument()
                logger.debug("URLLib3 instrumentation applied")

            # Databases
            if self.config.auto_instrument_databases:
                try:
                    SQLAlchemyInstrumentor().instrument()
                    logger.debug("SQLAlchemy instrumentation applied")
                except Exception as e:
                    logger.debug("SQLAlchemy instrumentation failed: %s", e)

                try:
                    Psycopg2Instrumentor().instrument()
                    logger.debug("Psycopg2 instrumentation applied")
                except Exception as e:
                    logger.debug("Psycopg2 instrumentation failed: %s", e)

            # Redis
            if self.config.auto_instrument_redis:
                try:
                    RedisInstrumentor().instrument()
                    logger.debug("Redis instrumentation applied")
                except Exception as e:
                    logger.debug("Redis instrumentation failed: %s", e)

            self._instrumented = True
            logger.info("Automatic instrumentation configured")

        except Exception as e:
            logger.warning("Some auto-instrumentation failed: %s", e)

    def instrument_fastapi(self, app) -> None:
        """Instrument FastAPI application with OpenTelemetry."""
        if not self.config.auto_instrument_fastapi or not self.config.tracing_enabled:
            return

        # FastAPI instrumentation is required

        try:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=trace.get_tracer_provider(),
                excluded_urls="health,metrics,ready",
            )
            logger.info("FastAPI instrumentation applied")
        except Exception as e:
            logger.error("Failed to instrument FastAPI: %s", e)

    def instrument_grpc_server(self, server) -> None:
        """Instrument gRPC server with OpenTelemetry."""
        if not self.config.auto_instrument_grpc or not self.config.tracing_enabled:
            return

        # gRPC instrumentation is required

        try:
            GrpcInstrumentorServer().instrument()
            logger.info("gRPC server instrumentation applied")
        except Exception as e:
            logger.error("Failed to instrument gRPC server: %s", e)

    def instrument_grpc_client(self) -> None:
        """Instrument gRPC client with OpenTelemetry."""
        if not self.config.auto_instrument_grpc or not self.config.tracing_enabled:
            return

        # gRPC instrumentation is required

        try:
            GrpcInstrumentorClient().instrument()
            logger.info("gRPC client instrumentation applied")
        except Exception as e:
            logger.error("Failed to instrument gRPC client: %s", e)

    def _start_prometheus_server(self) -> None:
        """Start Prometheus metrics HTTP server."""
        if self._metrics_server_started:
            return

        try:
            start_http_server(self.config.prometheus_port)
            self._metrics_server_started = True
            logger.info("Prometheus metrics server started on port %d", self.config.prometheus_port)
        except Exception as e:
            logger.error("Failed to start Prometheus server: %s", e)

    @contextmanager
    def trace_operation(self, operation_name: str, **attributes):
        """Context manager for tracing operations with automatic error handling."""
        if not self.tracer:
            yield
            return

        with self.tracer.start_as_current_span(operation_name) as span:
            # Add default attributes
            span.set_attribute("service.name", self.config.service_name)
            span.set_attribute("service.version", self.config.service_version)

            # Add custom attributes
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

            # Add custom tags from config
            for key, value in self.config.custom_tags.items():
                span.set_attribute(f"custom.{key}", value)

            try:
                yield span
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise

    def create_counter(self, name: str, description: str, unit: str = "1"):
        """Create a counter metric with standardized labels."""
        if not self.meter:
            return None

        return self.meter.create_counter(
            name=f"{self.config.service_name}_{name}",
            description=description,
            unit=unit,
        )

    def create_histogram(self, name: str, description: str, unit: str = "ms"):
        """Create a histogram metric with standardized labels."""
        if not self.meter:
            return None

        return self.meter.create_histogram(
            name=f"{self.config.service_name}_{name}",
            description=description,
            unit=unit,
        )

    def create_gauge(self, name: str, description: str, unit: str = "1"):
        """Create a gauge metric with standardized labels."""
        if not self.meter:
            return None

        return self.meter.create_up_down_counter(
            name=f"{self.config.service_name}_{name}",
            description=description,
            unit=unit,
        )

    def get_correlation_id(self) -> str | None:
        """Get current correlation ID."""
        if self.correlation_filter:
            return self.correlation_filter.correlation_id
        return None

    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for current context."""
        if self.correlation_filter:
            self.correlation_filter.update_correlation_id(correlation_id)

    def extract_trace_context(self, headers: dict):
        """Extract trace context from incoming headers."""
        if not self.config.tracing_enabled:
            return None

        # Extract context from headers
        context = extract(headers)
        if context:
            # Activate the extracted context

            token = attach(context)
            return token
        return None

    def inject_trace_context(self, headers: dict) -> dict:
        """Inject trace context into outgoing headers."""
        if not self.config.tracing_enabled:
            return headers

        inject(headers)
        return headers


class ServiceNameFilter(logging.Filter):
    """Filter to inject service name into log records."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service_name = self.service_name  # type: ignore[attr-defined]
        return True


# Factory function for easy initialization
def create_observability(
    service_name: str, config: ObservabilityConfig | None = None
) -> UnifiedObservability:
    """Create and initialize unified observability for a service."""
    if config is None:
        config = ObservabilityConfig.from_environment(service_name)

    observability = UnifiedObservability(config)
    observability.initialize()
    return observability


# Decorator for automatic operation tracing
def trace_operation(operation_name: str | None = None, **attributes):
    """Decorator for automatic operation tracing."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Try to get observability from common locations
            observability = None
            if hasattr(args[0], "observability"):
                observability = args[0].observability
            elif hasattr(args[0], "_observability"):
                observability = args[0]._observability

            if not observability:
                # No observability found, execute without tracing
                return func(*args, **kwargs)

            name = operation_name or f"{func.__module__}.{func.__name__}"
            with observability.trace_operation(name, **attributes):
                return func(*args, **kwargs)

        return wrapper

    return decorator
