"""
OpenTelemetry Integration for Marty Microservices Framework

Provides comprehensive distributed tracing capabilities with:
- Automatic instrumentation for FastAPI, gRPC, and HTTP requests
- Custom span creation and context propagation
- Integration with Jaeger for trace visualization
- Performance monitoring and service dependency mapping
"""

import asyncio
import builtins
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from opentelemetry import metrics, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader

# Instrumentation libraries
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.grpc import (
    GrpcInstrumentorClient,
    GrpcInstrumentorServer,
)
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

# Propagators for context passing
from opentelemetry.propagate import extract, inject
from opentelemetry.propagators.b3 import B3MultiFormat, B3SingleFormat
from opentelemetry.propagators.composite import CompositeHTTPPropagator
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from starlette.middleware.base import BaseHTTPMiddleware

# FastAPI and gRPC imports
try:
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TracingConfig:
    """Configuration for OpenTelemetry tracing"""

    service_name: str
    service_version: str = "1.0.0"
    environment: str = "production"
    jaeger_endpoint: str = "http://jaeger:14268/api/traces"
    otlp_endpoint: str | None = None
    enable_console_exporter: bool = False
    enable_prometheus_metrics: bool = True
    sample_rate: float = 1.0
    max_tag_value_length: int = 1024
    max_events: int = 128
    max_attributes: int = 64
    export_timeout: int = 30
    custom_resource_attributes: builtins.dict[str, str] | None = None
    enable_auto_instrumentation: bool = True
    enable_custom_spans: bool = True
    trace_all_requests: bool = True


class DistributedTracing:
    """
    Comprehensive distributed tracing setup with OpenTelemetry

    Features:
    - Automatic instrumentation for common libraries
    - Custom span creation and management
    - Context propagation across service boundaries
    - Performance monitoring and dependency tracking
    - Integration with multiple exporters (Jaeger, OTLP, Console)
    """

    def __init__(self, config: TracingConfig):
        self.config = config
        self.tracer_provider = None
        self.tracer = None
        self.meter_provider = None
        self.meter = None
        self._setup_tracing()

        logger.info(f"Distributed tracing initialized for {config.service_name}")

    def _setup_tracing(self):
        """Setup OpenTelemetry tracing with configured exporters"""
        try:
            # Create resource with service information
            resource = self._create_resource()

            # Setup tracer provider
            self.tracer_provider = TracerProvider(
                resource=resource,
                sampler=trace.TraceIdRatioBasedSampler(self.config.sample_rate),
            )

            # Configure exporters
            self._setup_exporters()

            # Set global tracer provider
            trace.set_tracer_provider(self.tracer_provider)

            # Create tracer
            self.tracer = trace.get_tracer(self.config.service_name, self.config.service_version)

            # Setup metrics if enabled
            if self.config.enable_prometheus_metrics:
                self._setup_metrics()

            # Setup auto-instrumentation
            if self.config.enable_auto_instrumentation:
                self._setup_auto_instrumentation()

            # Setup propagators
            self._setup_propagators()

            logger.info("OpenTelemetry tracing setup completed")

        except Exception as e:
            logger.error(f"Error setting up tracing: {e}")
            raise

    def _create_resource(self) -> Resource:
        """Create resource with service metadata"""
        attributes = {
            SERVICE_NAME: self.config.service_name,
            SERVICE_VERSION: self.config.service_version,
            "environment": self.config.environment,
            "telemetry.sdk.language": "python",
            "telemetry.sdk.name": "opentelemetry",
        }

        # Add custom resource attributes
        if self.config.custom_resource_attributes:
            attributes.update(self.config.custom_resource_attributes)

        return Resource.create(attributes)

    def _setup_exporters(self):
        """Setup trace exporters"""
        processors = []

        # Jaeger exporter
        if self.config.jaeger_endpoint:
            jaeger_exporter = JaegerExporter(
                agent_host_name="jaeger",
                agent_port=6831,
                collector_endpoint=self.config.jaeger_endpoint,
            )
            processors.append(BatchSpanProcessor(jaeger_exporter))
            logger.info(f"Jaeger exporter configured: {self.config.jaeger_endpoint}")

        # OTLP exporter
        if self.config.otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=self.config.otlp_endpoint)
            processors.append(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP exporter configured: {self.config.otlp_endpoint}")

        # Console exporter for debugging
        if self.config.enable_console_exporter:
            console_exporter = ConsoleSpanExporter()
            processors.append(BatchSpanProcessor(console_exporter))
            logger.info("Console exporter enabled")

        # Add all processors to tracer provider
        for processor in processors:
            self.tracer_provider.add_span_processor(processor)

    def _setup_metrics(self):
        """Setup OpenTelemetry metrics with Prometheus"""
        try:
            # Create metrics reader for Prometheus
            prometheus_reader = PrometheusMetricReader()

            # Create meter provider
            self.meter_provider = MeterProvider(
                resource=self._create_resource(), metric_readers=[prometheus_reader]
            )

            # Set global meter provider
            metrics.set_meter_provider(self.meter_provider)

            # Create meter
            self.meter = metrics.get_meter(self.config.service_name, self.config.service_version)

            logger.info("OpenTelemetry metrics with Prometheus configured")

        except Exception as e:
            logger.error(f"Error setting up metrics: {e}")

    def _setup_auto_instrumentation(self):
        """Setup automatic instrumentation for common libraries"""
        try:
            # HTTP requests instrumentation
            RequestsInstrumentor().instrument()
            URLLib3Instrumentor().instrument()

            # Database instrumentation
            try:
                RedisInstrumentor().instrument()
                logger.debug("Redis instrumentation enabled")
            except ImportError:
                logger.debug("Redis not available for instrumentation")

            try:
                Psycopg2Instrumentor().instrument()
                logger.debug("PostgreSQL instrumentation enabled")
            except ImportError:
                logger.debug("Psycopg2 not available for instrumentation")

            try:
                SQLAlchemyInstrumentor().instrument()
                logger.debug("SQLAlchemy instrumentation enabled")
            except ImportError:
                logger.debug("SQLAlchemy not available for instrumentation")

            # gRPC instrumentation
            try:
                GrpcInstrumentorServer().instrument()
                GrpcInstrumentorClient().instrument()
                logger.debug("gRPC instrumentation enabled")
            except ImportError:
                logger.debug("gRPC not available for instrumentation")

            logger.info("Auto-instrumentation setup completed")

        except Exception as e:
            logger.error(f"Error setting up auto-instrumentation: {e}")

    def _setup_propagators(self):
        """Setup context propagators"""

        # Configure multiple propagators for compatibility
        propagators = [
            TraceContextTextMapPropagator(),  # W3C Trace Context
            W3CBaggagePropagator(),  # W3C Baggage
            B3MultiFormat(),  # B3 Multi-header
            B3SingleFormat(),  # B3 Single-header
        ]

        composite_propagator = CompositeHTTPPropagator(propagators)
        trace.set_global_textmap(composite_propagator)

        logger.info("Context propagators configured")

    def instrument_fastapi(self, app: "FastAPI"):
        """Instrument FastAPI application"""
        if not FASTAPI_AVAILABLE:
            logger.warning("FastAPI not available for instrumentation")
            return

        try:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=self.tracer_provider,
                server_request_hook=self._fastapi_server_request_hook,
                client_request_hook=self._fastapi_client_request_hook,
                client_response_hook=self._fastapi_client_response_hook,
            )

            # Add custom middleware for enhanced tracing
            app.add_middleware(TracingMiddleware, tracing=self)

            logger.info("FastAPI instrumentation completed")

        except Exception as e:
            logger.error(f"Error instrumenting FastAPI: {e}")

    def _fastapi_server_request_hook(self, span: trace.Span, scope: dict):
        """Hook for FastAPI server requests"""
        if span and span.is_recording():
            # Add custom attributes
            span.set_attribute("http.framework", "fastapi")
            span.set_attribute("http.route", scope.get("route", {}).get("path", ""))

            # Add user information if available
            if "user" in scope:
                span.set_attribute("user.id", scope["user"].get("id", ""))
                span.set_attribute("user.role", scope["user"].get("role", ""))

    def _fastapi_client_request_hook(self, span: trace.Span, request):
        """Hook for FastAPI client requests"""
        if span and span.is_recording():
            span.set_attribute("http.client", "fastapi")

    def _fastapi_client_response_hook(self, span: trace.Span, request, response):
        """Hook for FastAPI client responses"""
        if span and span.is_recording():
            span.set_attribute(
                "http.response.size", len(response.content) if response.content else 0
            )

    @asynccontextmanager
    async def trace_async_operation(
        self,
        operation_name: str,
        attributes: builtins.dict[str, Any] | None = None,
        trace_level: str = "INFO",
    ):
        """Context manager for tracing async operations"""
        with self.tracer.start_as_current_span(operation_name) as span:
            try:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))

                span.set_attribute("operation.type", "async")
                span.set_attribute("trace.level", trace_level)
                span.add_event("operation.started")

                yield span

                span.set_status(trace.Status(trace.StatusCode.OK))
                span.add_event("operation.completed")

            except Exception as e:
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.add_event("operation.failed", {"error": str(e)})
                raise

    def trace_function(
        self,
        operation_name: str | None = None,
        attributes: builtins.dict[str, Any] | None = None,
    ):
        """Decorator for tracing functions"""

        def decorator(func: Callable):
            span_name = operation_name or f"{func.__module__}.{func.__name__}"

            if asyncio.iscoroutinefunction(func):

                async def async_wrapper(*args, **kwargs):
                    async with self.trace_async_operation(span_name, attributes):
                        return await func(*args, **kwargs)

                return async_wrapper

            def sync_wrapper(*args, **kwargs):
                with self.tracer.start_as_current_span(span_name) as span:
                    try:
                        if attributes:
                            for key, value in attributes.items():
                                span.set_attribute(key, str(value))

                        result = func(*args, **kwargs)
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        return result

                    except Exception as e:
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise

            return sync_wrapper

        return decorator

    def create_custom_span(
        self,
        name: str,
        attributes: builtins.dict[str, Any] | None = None,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
    ) -> trace.Span:
        """Create a custom span"""
        span = self.tracer.start_span(name, kind=kind)

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

        return span

    def add_span_event(self, name: str, attributes: builtins.dict[str, Any] | None = None):
        """Add an event to the current span"""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.add_event(name, attributes or {})

    def set_span_attribute(self, key: str, value: Any):
        """Set an attribute on the current span"""
        current_span = trace.get_current_span()
        if current_span and current_span.is_recording():
            current_span.set_attribute(key, str(value))

    def inject_context(self, carrier: builtins.dict[str, str]):
        """Inject trace context into a carrier (e.g., HTTP headers)"""
        inject(carrier)

    def extract_context(self, carrier: builtins.dict[str, str]):
        """Extract trace context from a carrier"""
        return extract(carrier)

    def get_trace_id(self) -> str | None:
        """Get the current trace ID"""
        current_span = trace.get_current_span()
        if current_span and current_span.get_span_context().is_valid:
            return format(current_span.get_span_context().trace_id, "032x")
        return None

    def get_span_id(self) -> str | None:
        """Get the current span ID"""
        current_span = trace.get_current_span()
        if current_span and current_span.get_span_context().is_valid:
            return format(current_span.get_span_context().span_id, "016x")
        return None


class TracingMiddleware(BaseHTTPMiddleware):
    """Custom FastAPI middleware for enhanced tracing"""

    def __init__(self, app, tracing: DistributedTracing):
        super().__init__(app)
        self.tracing = tracing

    async def dispatch(self, request: Request, call_next: Callable):
        # Extract trace context from request headers
        self.tracing.extract_context(dict(request.headers))

        with trace.use_span(trace.get_current_span(), end_on_exit=False):
            # Add request information to span
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute(
                    "http.request.size", request.headers.get("content-length", "0")
                )
                current_span.set_attribute("http.user_agent", request.headers.get("user-agent", ""))
                current_span.set_attribute(
                    "http.client_ip", request.client.host if request.client else ""
                )

            # Process request
            response = await call_next(request)

            # Add response information to span
            if current_span and current_span.is_recording():
                current_span.set_attribute("http.response.status_code", response.status_code)
                current_span.set_attribute(
                    "http.response.size", response.headers.get("content-length", "0")
                )

            return response


# Factory function for easy setup
def setup_distributed_tracing(
    service_name: str,
    jaeger_endpoint: str = "http://jaeger:14268/api/traces",
    **config_kwargs,
) -> DistributedTracing:
    """Setup distributed tracing with default configuration"""
    config = TracingConfig(
        service_name=service_name, jaeger_endpoint=jaeger_endpoint, **config_kwargs
    )
    return DistributedTracing(config)


# Convenience decorators for common use cases
def trace_grpc_method(method_name: str | None = None):
    """Decorator for tracing gRPC methods"""

    def decorator(func):
        span_name = method_name or f"grpc.{func.__name__}"
        return DistributedTracing.trace_function(span_name, {"grpc.method": func.__name__})(func)

    return decorator


def trace_database_operation(operation_type: str):
    """Decorator for tracing database operations"""

    def decorator(func):
        span_name = f"db.{operation_type}.{func.__name__}"
        attributes = {"db.operation": operation_type, "db.method": func.__name__}
        return DistributedTracing.trace_function(span_name, attributes)(func)

    return decorator


def trace_external_call(service_name: str):
    """Decorator for tracing external service calls"""

    def decorator(func):
        span_name = f"external.{service_name}.{func.__name__}"
        attributes = {"external.service": service_name, "call.type": "external"}
        return DistributedTracing.trace_function(span_name, attributes)(func)

    return decorator
