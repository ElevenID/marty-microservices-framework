"""
Monitoring middleware integration for FastAPI and gRPC applications.

This module provides middleware components that automatically collect metrics,
perform health checks, and integrate with distributed tracing systems.
"""

import asyncio
import logging
import random
import re
import time
from datetime import datetime

# gRPC imports
import grpc

# FastAPI imports
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from grpc._server import _Context as GrpcContext
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .core import HealthStatus, get_monitoring_manager

# Framework imports
# TODO: Re-enable once grpc is migrated
# from mmf_new.core.grpc import UnifiedGrpcServer


logger = logging.getLogger(__name__)


class MonitoringMiddlewareConfig:
    """Configuration for monitoring middleware."""

    def __init__(self):
        # Metrics collection
        self.collect_request_metrics: bool = True
        self.collect_response_metrics: bool = True
        self.collect_error_metrics: bool = True

        # Health checks
        self.health_endpoint: str = "/health"
        self.metrics_endpoint: str = "/metrics"
        self.detailed_health_endpoint: str = "/health/detailed"

        # Performance
        self.sample_rate: float = 1.0  # Collect metrics for 100% of requests
        self.slow_request_threshold_seconds: float = 1.0

        # Filtering
        self.exclude_paths: list = ["/favicon.ico", "/robots.txt"]
        self.exclude_methods: list = []

        # Distributed tracing
        self.enable_tracing: bool = True
        self.trace_all_requests: bool = True


def should_monitor_request(
    request_path: str, method: str, config: MonitoringMiddlewareConfig
) -> bool:
    """Determine if request should be monitored based on configuration."""

    # Check excluded paths
    for excluded_path in config.exclude_paths:
        if request_path.startswith(excluded_path):
            return False

    # Check excluded methods
    if method.upper() in config.exclude_methods:
        return False

    # Apply sampling rate
    if random.random() > config.sample_rate:
        return False

    return True


class FastAPIMonitoringMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for monitoring and observability."""

    def __init__(self, app: FastAPI, config: MonitoringMiddlewareConfig | None = None):
        super().__init__(app)
        self.config = config or MonitoringMiddlewareConfig()
        logger.info("FastAPI monitoring middleware initialized")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and response with monitoring."""

        start_time = time.time()
        request_path = str(request.url.path)
        method = request.method

        # Handle built-in monitoring endpoints
        if request_path == self.config.health_endpoint:
            return await self._handle_health_endpoint(detailed=False)
        if request_path == self.config.detailed_health_endpoint:
            return await self._handle_health_endpoint(detailed=True)
        if request_path == self.config.metrics_endpoint:
            return await self._handle_metrics_endpoint()

        # Check if we should monitor this request
        if not should_monitor_request(request_path, method, self.config):
            return await call_next(request)

        monitoring_manager = get_monitoring_manager()
        if not monitoring_manager:
            return await call_next(request)

        # Start distributed trace if enabled
        trace_span = None
        if self.config.enable_tracing and monitoring_manager.tracer:
            trace_context = monitoring_manager.tracer.trace_operation(
                f"{method} {request_path}",
                {
                    "http.method": method,
                    "http.url": str(request.url),
                    "http.scheme": request.url.scheme,
                    "http.host": request.url.hostname or "unknown",
                    "user_agent": request.headers.get("user-agent", ""),
                },
            )
            trace_span = await trace_context.__aenter__()

        try:
            # Process request
            response = await call_next(request)

            # Calculate timing
            duration_seconds = time.time() - start_time

            # Collect metrics
            if self.config.collect_request_metrics:
                await monitoring_manager.record_request(
                    method=method,
                    endpoint=self._normalize_endpoint(request_path),
                    status_code=response.status_code,
                    duration_seconds=duration_seconds,
                )

            # Record slow requests
            if duration_seconds > self.config.slow_request_threshold_seconds:
                await monitoring_manager.record_error("slow_request")
                logger.warning(
                    f"Slow request: {method} {request_path} took {duration_seconds:.3f}s"
                )

            # Add trace attributes
            if trace_span:
                trace_span.set_attribute("http.status_code", response.status_code)
                trace_span.set_attribute(
                    "http.response_size",
                    len(response.body) if hasattr(response, "body") else 0,
                )

            return response

        except Exception as e:
            duration_seconds = time.time() - start_time

            # Record error metrics
            if self.config.collect_error_metrics:
                await monitoring_manager.record_error(type(e).__name__)

            # Add trace error information
            if trace_span:
                trace_span.record_exception(e)
                trace_span.set_status(
                    monitoring_manager.tracer.tracer.trace.Status(
                        monitoring_manager.tracer.tracer.trace.StatusCode.ERROR,
                        str(e),
                    )
                )

            raise

        finally:
            # Close trace span
            if trace_span and monitoring_manager.tracer:
                await trace_context.__aexit__(None, None, None)

    async def _handle_health_endpoint(self, detailed: bool = False) -> JSONResponse:
        """Handle health check endpoint."""
        monitoring_manager = get_monitoring_manager()

        if not monitoring_manager:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "message": "Monitoring not initialized",
                },
            )

        if detailed:
            health_data = await monitoring_manager.get_service_health()
            status_code = 200 if health_data["status"] == "healthy" else 503
            return JSONResponse(status_code=status_code, content=health_data)
        # Simple health check
        health_results = await monitoring_manager.perform_health_checks()

        # Determine overall status
        overall_healthy = all(
            result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            for result in health_results.values()
        )

        status_code = 200 if overall_healthy else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if overall_healthy else "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def _handle_metrics_endpoint(self) -> Response:
        """Handle metrics endpoint."""
        monitoring_manager = get_monitoring_manager()

        if not monitoring_manager:
            return Response("# Monitoring not initialized\n", media_type="text/plain")

        metrics_text = monitoring_manager.get_metrics_text()
        if metrics_text:
            return Response(metrics_text, media_type="text/plain")
        return Response("# No metrics available\n", media_type="text/plain")

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics (replace IDs with placeholders)."""
        # Simple normalization - replace numeric IDs with {id}

        # Replace UUIDs
        path = re.sub(
            r"/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
            "/{uuid}",
            path,
        )

        # Replace numeric IDs
        path = re.sub(r"/\d+", "/{id}", path)

        return path


class GRPCMonitoringInterceptor(grpc.ServerInterceptor):
    """gRPC server interceptor for monitoring."""

    def __init__(self, config: MonitoringMiddlewareConfig | None = None):
        self.config = config or MonitoringMiddlewareConfig()
        logger.info("gRPC monitoring interceptor initialized")

    def intercept_service(self, continuation, handler_call_details):
        """Intercept gRPC service calls."""

        monitoring_manager = get_monitoring_manager()
        if not monitoring_manager:
            return continuation(handler_call_details)

        method_name = handler_call_details.method

        def monitoring_wrapper(request, context: GrpcContext):
            start_time = time.time()

            # Start distributed trace if enabled
            if self.config.enable_tracing and monitoring_manager.tracer:
                monitoring_manager.tracer.trace_operation(
                    f"gRPC {method_name}",
                    {
                        "rpc.system": "grpc",
                        "rpc.service": method_name.split("/")[1]
                        if "/" in method_name
                        else "unknown",
                        "rpc.method": method_name.split("/")[-1]
                        if "/" in method_name
                        else method_name,
                    },
                )
                # Note: In real implementation, we'd need proper async context handling

            try:
                # Call the actual handler
                handler = continuation(handler_call_details)
                response = handler(request, context)

                # Calculate timing
                duration_seconds = time.time() - start_time

                # Determine status
                status_code = 0  # OK
                if hasattr(context, "_state") and context._state.code is not None:
                    status_code = context._state.code.value[0]

                # Record metrics (in real implementation, we'd use async)
                # This is a simplified version for the example
                try:
                    if asyncio.get_event_loop().is_running():
                        asyncio.create_task(
                            monitoring_manager.record_request(
                                method="gRPC",
                                endpoint=method_name,
                                status_code=status_code,
                                duration_seconds=duration_seconds,
                            )
                        )
                except Exception as e:
                    logger.warning(f"Failed to record gRPC metrics: {e}")

                return response

            except Exception as e:
                duration_seconds = time.time() - start_time

                # Record error metrics
                try:
                    if asyncio.get_event_loop().is_running():
                        asyncio.create_task(monitoring_manager.record_error(type(e).__name__))
                except Exception as record_error:
                    logger.warning(f"Failed to record gRPC error metrics: {record_error}")

                raise

        return monitoring_wrapper


def setup_fastapi_monitoring(
    app: FastAPI, config: MonitoringMiddlewareConfig | None = None
) -> None:
    """Setup FastAPI monitoring middleware."""
    middleware = FastAPIMonitoringMiddleware(app, config)
    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
    logger.info("FastAPI monitoring middleware added")


def setup_grpc_monitoring(server, config: MonitoringMiddlewareConfig | None = None):
    """Setup gRPC monitoring interceptor."""
    interceptor = GRPCMonitoringInterceptor(config)
    server.add_interceptor(interceptor)
    logger.info("gRPC monitoring interceptor added")


# Monitoring decorators for manual instrumentation
def monitor_function(
    operation_name: str | None = None,
    record_duration: bool = True,
    record_errors: bool = True,
):
    """Decorator to monitor function execution."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            monitoring_manager = get_monitoring_manager()
            if not monitoring_manager:
                return func(*args, **kwargs)

            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                if record_duration:
                    duration = time.time() - start_time
                    # In real implementation, record duration metric
                    logger.debug(f"Function {op_name} took {duration:.3f}s")

                return result

            except Exception as e:
                if record_errors:
                    # In real implementation, record error metric
                    logger.error(f"Function {op_name} failed: {e}")
                raise

        return wrapper

    return decorator


async def monitor_async_function(
    operation_name: str | None = None,
    record_duration: bool = True,
    record_errors: bool = True,
):
    """Decorator to monitor async function execution."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            monitoring_manager = get_monitoring_manager()
            if not monitoring_manager:
                return await func(*args, **kwargs)

            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            # Start distributed trace if available
            if monitoring_manager.tracer:
                async with monitoring_manager.tracer.trace_operation(op_name) as span:
                    try:
                        result = await func(*args, **kwargs)

                        if record_duration:
                            duration = time.time() - start_time
                            if span:
                                span.set_attribute("duration_seconds", duration)

                        return result

                    except Exception as e:
                        if record_errors and span:
                            span.record_exception(e)
                        raise
            else:
                try:
                    result = await func(*args, **kwargs)

                    if record_duration:
                        duration = time.time() - start_time
                        logger.debug(f"Async function {op_name} took {duration:.3f}s")

                    return result

                except Exception as e:
                    if record_errors:
                        logger.error(f"Async function {op_name} failed: {e}")
                    raise

        return wrapper

    return decorator
