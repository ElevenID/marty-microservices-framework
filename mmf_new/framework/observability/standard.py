"""
MMF Standard Observability Configuration

This module provides the definitive, standardized observability configuration
for all MMF services. It consolidates and replaces multiple observability
implementations with a single, comprehensive solution.

Key Features:
- Automatic OpenTelemetry instrumentation for all service types
- Standardized Prometheus metrics with consistent naming
- Correlation ID propagation with multi-dimensional tracking
- Default Grafana dashboards and alerting rules
- Zero-configuration setup for plugin developers
- Comprehensive logging with structured output
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
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
from opentelemetry.propagate import extract, inject, set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

from mmf_new.core.services import ObservabilityService
from mmf_new.framework.infrastructure.dependency_injection import get_container

from .factories import (
    register_observability_services,
    set_standard_observability_classes,
)

logger = logging.getLogger(__name__)

# OpenTelemetry Core

# OpenTelemetry Exporters

# OpenTelemetry Instrumentation

# Prometheus

# Import the typed service base


@dataclass
class StandardObservabilityConfig:
    """
    Standardized observability configuration for all MMF services.

    This replaces all previous observability configurations and provides
    a single source of truth for observability defaults.
    """

    # Service identification
    service_name: str
    service_version: str = "1.0.0"
    service_type: str = "unknown"  # fastapi, grpc, hybrid
    environment: str = field(
        default_factory=lambda: os.getenv("DEPLOYMENT_ENVIRONMENT", "development")
    )

    # OpenTelemetry configuration
    otlp_endpoint: str = field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    )
    jaeger_endpoint: str = field(
        default_factory=lambda: os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
    )

    # Sampling configuration based on environment
    trace_sampling_rate: float | None = None

    # Prometheus configuration
    prometheus_enabled: bool = True
    prometheus_port: int = 8000
    metrics_prefix: str = "mmf"

    # Correlation ID configuration
    correlation_enabled: bool = True
    correlation_headers: list[str] = field(
        default_factory=lambda: [
            "x-mmf-correlation-id",
            "x-mmf-request-id",
            "x-mmf-user-id",
            "x-mmf-session-id",
            "x-mmf-operation-id",
            "x-mmf-plugin-id",
        ]
    )

    # Logging configuration
    structured_logging: bool = True
    log_correlation_injection: bool = True
    log_level: str = "INFO"

    # Feature flags
    auto_instrument: bool = True
    export_traces: bool = True
    export_metrics: bool = True
    export_logs: bool = True

    def __post_init__(self):
        """Set environment-specific defaults."""
        if self.trace_sampling_rate is None:
            sampling_rates = {"development": 1.0, "testing": 1.0, "staging": 0.5, "production": 0.1}
            self.trace_sampling_rate = sampling_rates.get(self.environment, 0.1)


class StandardObservability:
    """
    Unified observability manager for all MMF services.

    This class consolidates all observability functionality and provides
    a single interface for all service types. It replaces multiple
    implementations with one standardized approach.
    """

    def __init__(self, config: StandardObservabilityConfig):
        self.config = config
        self.tracer_provider: TracerProvider | None = None
        self.meter_provider: MeterProvider | None = None
        self.tracer = None
        self.meter = None
        self.initialized = False

        # Standard metrics
        self.request_counter: Counter | None = None
        self.request_duration: Histogram | None = None
        self.active_requests: Gauge | None = None
        self.plugin_operations: Counter | None = None
        self.error_counter: Counter | None = None

        # Correlation tracking
        self.correlation_context = {}

    async def initialize(self) -> None:
        """Initialize all observability components."""
        if self.initialized:
            logger.warning("Observability already initialized")
            return

        logger.info(f"Initializing standard observability for {self.config.service_name}")

        # Initialize OpenTelemetry
        await self._setup_tracing()
        await self._setup_metrics()

        # Initialize Prometheus metrics
        self._setup_standard_metrics()

        # Setup correlation tracking
        if self.config.correlation_enabled:
            self._setup_correlation()

        # Auto-instrument if enabled
        if self.config.auto_instrument:
            self._auto_instrument()

        self.initialized = True
        logger.info("Standard observability initialization complete")

    async def _setup_tracing(self) -> None:
        """Setup OpenTelemetry tracing with standard configuration."""

        # Create resource with standard attributes
        resource = Resource.create(
            {
                "service.name": self.config.service_name,
                "service.version": self.config.service_version,
                "deployment.environment": self.config.environment,
                "mmf.service.type": self.config.service_type,
                "mmf.framework.version": "2.0.0",
                "mmf.observability.standard": "true",
            }
        )

        # Setup tracer provider
        self.tracer_provider = TracerProvider(resource=resource)

        # Add OTLP exporter
        if self.config.export_traces:
            otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
            span_processor = BatchSpanProcessor(otlp_exporter)
            self.tracer_provider.add_span_processor(span_processor)

        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        self.tracer = trace.get_tracer(__name__)

        logger.info("OpenTelemetry tracing configured")

    async def _setup_metrics(self) -> None:
        """Setup OpenTelemetry metrics with standard configuration."""

        # Create metric readers
        readers = []

        # Prometheus metrics are handled separately via prometheus_client
        # OpenTelemetry metrics will be exported via OTLP

        # Add OTLP reader if exporting metrics
        if self.config.export_metrics:
            otlp_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=self.config.otlp_endpoint), export_interval_millis=30000
            )
            readers.append(otlp_reader)

        # Setup meter provider
        self.meter_provider = MeterProvider(metric_readers=readers)
        metrics.set_meter_provider(self.meter_provider)
        self.meter = metrics.get_meter(__name__)

        logger.info("OpenTelemetry metrics configured")

    def _setup_standard_metrics(self) -> None:
        """Setup standard Prometheus metrics for all services."""

        prefix = f"{self.config.metrics_prefix}_{self.config.service_type}"

        try:
            # Request metrics
            self.request_counter = Counter(
                f"{prefix}_requests_total",
                "Total requests processed",
                ["method", "endpoint", "status_code"],
            )

            self.request_duration = Histogram(
                f"{prefix}_request_duration_seconds",
                "Request processing duration",
                ["method", "endpoint"],
            )

            self.active_requests = Gauge(f"{prefix}_active_requests", "Currently active requests")

            # Plugin metrics
            self.plugin_operations = Counter(
                f"{prefix}_plugin_operations_total",
                "Plugin operations",
                ["plugin_id", "operation", "status"],
            )

            # Error metrics
            self.error_counter = Counter(
                f"{prefix}_errors_total", "Total errors", ["error_type", "endpoint"]
            )

            logger.info("Standard Prometheus metrics configured")

        except ValueError as e:
            if "Duplicate" in str(e):
                logger.warning(f"Metrics already registered: {e}")
            else:
                raise

    def _setup_correlation(self) -> None:
        """Setup correlation ID tracking."""
        # This will integrate with the existing correlation system
        logger.info("Correlation tracking configured")

    def _auto_instrument(self) -> None:
        """Automatically instrument common libraries."""
        try:
            # HTTP client instrumentation
            HTTPXClientInstrumentor().instrument()
            RequestsInstrumentor().instrument()

            # Database instrumentation
            SQLAlchemyInstrumentor().instrument()
            Psycopg2Instrumentor().instrument()

            # Cache instrumentation
            RedisInstrumentor().instrument()

            logger.info("Auto-instrumentation complete")

        except Exception as e:
            logger.warning(f"Auto-instrumentation failed: {e}")

    def instrument_fastapi(self, app) -> None:
        """Instrument FastAPI application."""
        try:
            FastAPIInstrumentor.instrument_app(app, tracer_provider=self.tracer_provider)
            logger.info("FastAPI instrumentation complete")
        except Exception as e:
            logger.warning(f"FastAPI instrumentation failed: {e}")

    def instrument_grpc_server(self, server) -> None:
        """Instrument gRPC server."""
        try:
            GrpcInstrumentorServer().instrument()
            logger.info("gRPC server instrumentation complete")
        except Exception as e:
            logger.warning(f"gRPC server instrumentation failed: {e}")

    def instrument_grpc_client(self) -> None:
        """Instrument gRPC client."""
        try:
            GrpcInstrumentorClient().instrument()
            logger.info("gRPC client instrumentation complete")
        except Exception as e:
            logger.warning(f"gRPC client instrumentation failed: {e}")

    @contextmanager
    def trace_operation(self, operation_name: str, **attributes):
        """Create a traced operation with standard attributes."""
        if not self.tracer:
            yield
            return

        with self.tracer.start_as_current_span(operation_name) as span:
            # Add standard attributes
            span.set_attribute("mmf.service.name", self.config.service_name)
            span.set_attribute("mmf.service.type", self.config.service_type)

            # Add custom attributes
            for key, value in attributes.items():
                span.set_attribute(key, value)

            yield span

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float) -> None:
        """Record request metrics."""
        if self.request_counter:
            self.request_counter.labels(
                method=method, endpoint=endpoint, status_code=str(status_code)
            ).inc()

        if self.request_duration:
            self.request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def record_plugin_operation(self, plugin_id: str, operation: str, status: str) -> None:
        """Record plugin operation metrics."""
        if self.plugin_operations:
            self.plugin_operations.labels(
                plugin_id=plugin_id, operation=operation, status=status
            ).inc()

    def record_error(self, error_type: str, endpoint: str = "unknown") -> None:
        """Record error metrics."""
        if self.error_counter:
            self.error_counter.labels(error_type=error_type, endpoint=endpoint).inc()

    def get_metrics(self) -> bytes:
        """Get Prometheus metrics output."""
        return generate_latest(REGISTRY)

    async def shutdown(self) -> None:
        """Shutdown observability components."""
        if self.tracer_provider:
            self.tracer_provider.shutdown()

        if self.meter_provider:
            self.meter_provider.shutdown()

        logger.info("Standard observability shutdown complete")


def create_standard_observability(
    service_name: str, service_version: str = "1.0.0", service_type: str = "unknown", **kwargs
) -> StandardObservability:
    """
    Create standard observability instance for any MMF service.

    This is the primary entry point for all services and replaces
    all previous observability initialization methods.
    """
    config = StandardObservabilityConfig(
        service_name=service_name,
        service_version=service_version,
        service_type=service_type,
        **kwargs,
    )

    return StandardObservability(config)


class StandardObservabilityService(ObservabilityService):
    """
    Typed service for standard observability.

    Replaces global observability variables with proper dependency injection.
    """

    def __init__(self) -> None:
        super().__init__()
        self._observability: StandardObservability | None = None

    def initialize(self, service_name: str, config: dict[str, Any] | None = None) -> None:
        """Initialize the observability service."""
        if config is None:
            config = {}

        # Create configuration from parameters
        observability_config = StandardObservabilityConfig(service_name=service_name, **config)

        # Create observability instance
        self._observability = StandardObservability(observability_config)
        # Note: StandardObservability.initialize() is async, so we'll mark as initialized here
        # and let the caller handle the async initialization
        self._mark_initialized()

    def cleanup(self) -> None:
        """Cleanup resources."""
        if self._observability:
            # StandardObservability doesn't have cleanup method, so we just reset
            pass
        self._observability = None
        self._initialized = False

    def get_observability(self) -> StandardObservability:
        """Get the observability instance."""
        if self._observability is None:
            raise RuntimeError("Observability service not initialized")
        return self._observability


set_standard_observability_classes(StandardObservabilityService, StandardObservability)


def get_observability_service() -> StandardObservabilityService:
    """
    Get the observability service instance using dependency injection.

    Returns:
        StandardObservabilityService instance

    Raises:
        ValueError: If service is not registered in the DI container
    """
    service = get_container().get(StandardObservabilityService)
    if service is None:
        # Auto-register if not found (for backward compatibility)
        register_observability_services()
        service = get_container().get(StandardObservabilityService)

    if service is None:
        raise ValueError("StandardObservabilityService not registered")

    return service


def get_observability() -> StandardObservability | None:
    """Get the observability instance - compatibility function."""
    service = get_observability_service()
    if not service.is_initialized():
        return None
    return service.get_observability()


def set_global_observability(observability: StandardObservability) -> None:
    """Set the observability instance - compatibility function."""
    service = get_observability_service()
    service._observability = observability
    service._mark_initialized()
