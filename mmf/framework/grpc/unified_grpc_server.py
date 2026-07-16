"""
Enhanced gRPC Service Factory with Unified Observability.

This module provides a factory for creating gRPC services with automatic
observability integration using the unified configuration system.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from concurrent import futures
from dataclasses import dataclass
from typing import Any, Protocol

import grpc
from aiohttp import web, web_runner
from grpc import aio
from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_health.v1.health import HealthServicer
from grpc_reflection.v1alpha import reflection

# MMF imports
from mmf.framework.infrastructure.config_manager import Environment
from mmf.framework.infrastructure.unified_config import (
    BaseSettings,
    ConfigurationStrategy,
    UnifiedConfigurationManager,
    create_unified_config_manager,
)
from mmf.framework.observability.standard import (
    create_standard_observability,
    set_global_observability,
)

logger = logging.getLogger(__name__)


class ServicerFactoryProtocol(Protocol):
    """Protocol for servicer factory functions."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Create a servicer instance."""
        ...


class ServiceRegistrationProtocol(Protocol):
    """Protocol for service registration functions (add_*Servicer_to_server)."""

    def __call__(self, servicer: Any, server: grpc.aio.Server) -> None:
        """Add servicer to gRPC server."""
        ...


@dataclass
class ServiceDefinition:
    """Definition of a gRPC service for factory creation."""

    name: str
    servicer_factory: ServicerFactoryProtocol
    registration_func: ServiceRegistrationProtocol
    health_service_name: str | None = None
    dependencies: dict[str, Any] | None = None
    priority: int = 100

    def __post_init__(self):
        """Post-initialization setup."""
        if self.health_service_name is None:
            self.health_service_name = self.name
        if self.dependencies is None:
            self.dependencies = {}

    def create_servicer(self, **kwargs: Any) -> Any:
        """Create servicer instance with merged dependencies and kwargs."""
        dependencies = self.dependencies or {}
        merged_kwargs = {**dependencies, **kwargs}
        return self.servicer_factory(**merged_kwargs)

    def register_servicer(self, servicer: Any, server: grpc.aio.Server) -> None:
        """Register servicer with the gRPC server."""
        self.registration_func(servicer, server)


class ObservableGrpcServiceMixin:
    """
    Mixin class that adds observability capabilities to gRPC services.

    This mixin automatically integrates metrics, tracing, and health checks
    for gRPC services using the unified configuration system.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Observability will be set by the factory
        self.observability = None
        self.service_metrics = {}

    def _setup_observability(self, observability):
        """Setup observability for the gRPC service."""
        self.observability = observability

        # Initialize observability components
        if self.observability:
            self.service_metrics = {
                "requests_total": self.observability.counter(
                    "grpc_requests_total", "Total gRPC requests"
                ),
                "request_duration": self.observability.histogram(
                    "grpc_request_duration_seconds", "Request duration"
                ),
                "active_connections": self.observability.gauge(
                    "grpc_active_connections", "Active connections"
                ),
            }

        # Register health checks
        self._register_grpc_health_checks()

    def _register_grpc_health_checks(self):
        """Register gRPC-specific health checks."""
        if self.observability:
            # gRPC service health check
            self.observability.register_health_check(
                name="grpc_service", check_func=self._check_grpc_service_health, interval_seconds=30
            )

    async def _check_grpc_service_health(self):
        """Check gRPC service health."""
        # Health status tracking

        try:
            # Check if service is accepting connections
            # This is a placeholder - actual implementation would check server state
            return "HEALTHY"
        except Exception:
            return "UNHEALTHY"

    def trace_grpc_call(self, method_name: str):
        """Decorator factory for tracing gRPC method calls."""

        def decorator(func):
            async def wrapper(request, context):
                if not self.observability:
                    return await func(request, context)

                with self.observability.trace_operation(
                    f"grpc.{method_name}",
                    grpc_method=method_name,
                    service=self.observability.service_name,
                ) as span:
                    start_time = asyncio.get_event_loop().time()

                    try:
                        # Execute the gRPC method
                        result = await func(request, context)

                        # Record success metrics
                        duration = asyncio.get_event_loop().time() - start_time

                        if self.service_metrics:
                            self.service_metrics["requests_total"].labels(
                                method=method_name, status="OK"
                            ).inc()

                            self.service_metrics["request_duration"].labels(
                                method=method_name
                            ).observe(duration)

                        if span:
                            span.set_attribute("grpc.success", True)
                            span.set_attribute("grpc.status", "OK")
                            span.set_attribute("grpc.duration", duration)

                        return result

                    except Exception as e:
                        # Record error metrics
                        if self.service_metrics:
                            self.service_metrics["requests_total"].labels(
                                method=method_name, status="ERROR"
                            ).inc()

                        if span:
                            span.set_attribute("grpc.success", False)
                            span.set_attribute("grpc.error", str(e))
                            span.set_attribute("grpc.error_type", type(e).__name__)

                        raise

            return wrapper

        return decorator


class UnifiedGrpcServer:
    """
    gRPC server with unified observability integration.

    This server automatically configures metrics endpoints, health checks,
    and distributed tracing based on the service configuration.
    Enhanced with service definition pattern for better service management.
    """

    def __init__(self, port: int = 50051, service_name: str | None = None, **kwargs):
        """
        Initialize the gRPC server with unified configuration.

        Args:
            port: Port to run the gRPC server on
            service_name: Name of the service
            **kwargs: Additional configuration options
        """
        self.logger = logging.getLogger("marty.grpc.server")

        # Store initialization parameters
        self.service_name = service_name or "grpc-server"
        self.port = port
        self.interceptors = kwargs.pop("interceptors", None) or []
        self.config_kwargs = kwargs

        # These will be initialized during start()
        self.config_manager: UnifiedConfigurationManager | None = None
        self.config: BaseSettings | None = None
        self.observability = None

        # gRPC server components
        self.server: aio.Server | None = None
        self.health_servicer: HealthServicer | None = None
        self.servicer_instances: dict[str, Any] = {}
        self.service_definitions: dict[str, ServiceDefinition] = {}
        self._pending_servicers: list = []
        self._running = False
        self._initialized = False

        self.logger.info("Unified gRPC server created for %s", self.service_name)

    async def initialize(self) -> None:
        """Initialize the unified configuration and observability systems."""
        if self._initialized:
            return

        # Initialize unified configuration using factory
        try:
            self.config_manager = create_unified_config_manager(
                service_name=self.service_name,
                environment=Environment.DEVELOPMENT,  # Will be auto-detected
                config_class=BaseSettings,
                strategy=ConfigurationStrategy.AUTO_DETECT,
            )
            await self.config_manager.initialize()
            self.config = await self.config_manager.get_configuration()

            self.logger.info("Configuration loaded for %s", self.service_name)
        except Exception as e:
            self.logger.warning("Failed to initialize unified configuration: %s", e)
            # Use minimal default configuration
            self.config = BaseSettings()

        # Initialize observability
        service_version = getattr(self.config, "service_version", "1.0.0")
        self.observability = create_standard_observability(
            service_name=self.service_name, service_version=service_version, service_type="grpc"
        )
        await self.observability.initialize()
        set_global_observability(self.observability)

        self._initialized = True
        self.logger.info("Unified gRPC server initialized for %s", self.service_name)

    def register_service(self, service_def: ServiceDefinition) -> None:
        """Register a service definition.

        Args:
            service_def: Service definition to register
        """
        self.service_definitions[service_def.name] = service_def
        self.logger.info("Registered service definition: %s", service_def.name)

    def add_servicer(self, servicer_class: type, add_servicer_func: Callable, *args, **kwargs):
        """
        Add a servicer to the gRPC server with observability integration.

        Args:
            servicer_class: The servicer class to instantiate
            add_servicer_func: Function to add servicer to server (from pb2_grpc)
            *args, **kwargs: Arguments to pass to servicer constructor
        """
        # Create servicer instance
        if issubclass(servicer_class, ObservableGrpcServiceMixin):
            servicer = servicer_class(*args, **kwargs)
            # Setup observability for service if it supports it
            if hasattr(servicer, "_setup_observability") and self.observability:
                servicer._setup_observability(self.observability)
        else:
            servicer = servicer_class(*args, **kwargs)

        # Store servicer reference
        servicer_name = servicer_class.__name__
        self.servicer_instances[servicer_name] = servicer

        # Add to server (will be called when server is created)
        self._pending_servicers.append((add_servicer_func, servicer))

        self.logger.info("Added servicer: %s", servicer_name)

    async def start(self):
        """Start the gRPC server with observability endpoints."""
        try:
            # Ensure initialization
            await self.initialize()

            # Get server configuration
            max_workers = getattr(self.config, "grpc_max_workers", 10)

            # Create gRPC server with production-ready options
            default_options = [
                ("grpc.keepalive_time_ms", 30000),
                ("grpc.keepalive_timeout_ms", 5000),
                ("grpc.keepalive_permit_without_calls", True),
                ("grpc.http2.max_pings_without_data", 0),
                ("grpc.http2.min_time_between_pings_ms", 10000),
                ("grpc.http2.min_ping_interval_without_data_ms", 5000),
            ]

            self.server = aio.server(
                futures.ThreadPoolExecutor(max_workers=max_workers),
                options=default_options,
                interceptors=self.interceptors or None,
            )

            # Add health service
            self.health_servicer = HealthServicer()
            health_pb2_grpc.add_HealthServicer_to_server(self.health_servicer, self.server)

            # Register all service definitions
            self._register_service_definitions()

            # Add all pending servicers (backward compatibility)
            if hasattr(self, "_pending_servicers"):
                for add_func, servicer in self._pending_servicers:
                    add_func(servicer, self.server)

            # Enable reflection if configured
            if getattr(self.config, "grpc_reflection_enabled", True):
                try:
                    # Collect all registered service names for reflection
                    service_names = [reflection.SERVICE_NAME]
                    for service_def in self.service_definitions.values():
                        if service_def.health_service_name:
                            service_names.append(service_def.health_service_name)
                    reflection.enable_server_reflection(service_names, self.server)
                except Exception as e:
                    self.logger.warning("Failed to enable server reflection: %s", e)

            # Configure server address
            listen_addr = self._configure_server_address()

            # Start server
            await self.server.start()
            self._running = True

            # Set all services to serving in health check
            if self.health_servicer:
                for service_def in self.service_definitions.values():
                    if service_def.health_service_name:
                        self.health_servicer.set(
                            service_def.health_service_name,
                            health_pb2.HealthCheckResponse.ServingStatus.SERVING,
                        )

            # Start observability endpoints
            await self._start_observability_endpoints()

            self.logger.info("gRPC server started on %s", listen_addr)

        except Exception as e:
            self.logger.error("Failed to start gRPC server: %s", e)
            raise

    def _register_service_definitions(self) -> None:
        """Register all service definitions with the server."""
        # Sort by priority (lower numbers first)
        sorted_services = sorted(self.service_definitions.values(), key=lambda s: s.priority)

        for service_def in sorted_services:
            try:
                # Create servicer instance
                servicer = service_def.create_servicer()

                # Register with server
                if self.server is None:
                    raise RuntimeError("Server not initialized")
                service_def.register_servicer(servicer, self.server)

                # Store servicer instance
                self.servicer_instances[service_def.name] = servicer

                self.logger.info("Registered service: %s", service_def.name)

            except Exception as e:
                self.logger.error("Failed to register service %s: %s", service_def.name, e)
                raise

    def _configure_server_address(self) -> str:
        """Configure server listen address with TLS if enabled."""
        if not self.config:
            raise RuntimeError("Configuration not initialized")

        # Use configured port or default
        port = getattr(self.config, "grpc_port", self.port)
        listen_addr = f"[::]:{port}"

        # Check for TLS configuration
        tls_enabled = getattr(self.config, "grpc_tls_enabled", False)

        if tls_enabled:
            # Load TLS credentials
            server_cert = getattr(self.config, "grpc_tls_server_cert", None)
            server_key = getattr(self.config, "grpc_tls_server_key", None)

            if server_cert and server_key:
                with open(server_cert, "rb") as f:
                    cert_data = f.read()
                with open(server_key, "rb") as f:
                    key_data = f.read()

                # mTLS: optionally require client certificates
                client_ca_cert = getattr(self.config, "grpc_tls_client_ca_cert", None)
                root_ca_data = None
                require_client_auth = getattr(self.config, "grpc_tls_require_client_auth", False)
                if client_ca_cert:
                    with open(client_ca_cert, "rb") as f:
                        root_ca_data = f.read()

                credentials = grpc.ssl_server_credentials(
                    [(key_data, cert_data)],
                    root_certificates=root_ca_data,
                    require_client_auth=require_client_auth,
                )
                if self.server is None:
                    raise RuntimeError("Server not initialized")
                self.server.add_secure_port(listen_addr, credentials)

                self.logger.info(
                    "gRPC TLS enabled (mTLS=%s)", "yes" if require_client_auth else "no"
                )
            else:
                self.logger.warning("TLS enabled but cert/key not configured, using insecure")
                if self.server is None:
                    raise RuntimeError("Server not initialized")
                self.server.add_insecure_port(listen_addr)
        else:
            if self.server is None:
                raise RuntimeError("Server not initialized")
            self.server.add_insecure_port(listen_addr)

        return listen_addr

    async def _start_observability_endpoints(self):
        """Start metrics and health check HTTP endpoints."""
        if not self.config or not self.observability:
            self.logger.warning("Observability not configured, skipping endpoints")
            return

        monitoring_enabled = getattr(self.config, "monitoring_enabled", True)
        if not monitoring_enabled:
            return

        try:
            # Create HTTP application for observability endpoints
            app = web.Application()

            # Metrics endpoint
            if getattr(self.config, "prometheus_enabled", True):
                app.router.add_get("/metrics", self._metrics_handler)

            # Health check endpoints
            app.router.add_get("/health", self._health_handler)
            app.router.add_get("/readiness", self._readiness_handler)
            app.router.add_get("/liveness", self._liveness_handler)

            # Start HTTP server for observability
            runner = web_runner.AppRunner(app)
            await runner.setup()

            health_port = getattr(self.config, "health_check_port", 8080)
            site = web_runner.TCPSite(runner, "localhost", health_port)
            await site.start()

            self.logger.info("Observability endpoints started on port %d", health_port)
        except ImportError:
            self.logger.warning("aiohttp not available, skipping HTTP observability endpoints")
        except Exception as e:
            self.logger.error("Failed to start observability endpoints: %s", e)

    async def _metrics_handler(self, request):
        """Handle Prometheus metrics requests."""

        if not self.observability:
            return web.Response(text="# No metrics available", content_type="text/plain")

        try:
            # Try to get metrics from observability system
            if hasattr(self.observability, "get_metrics"):
                metrics_output = self.observability.get_metrics()
            else:
                metrics_output = "# Metrics not available from observability system"

            # Ensure metrics_output is a string
            if isinstance(metrics_output, bytes):
                metrics_output = metrics_output.decode("utf-8")
            elif metrics_output is None:
                metrics_output = "# No metrics data"

            return web.Response(text=str(metrics_output), content_type="text/plain")
        except Exception as e:
            self.logger.error("Error getting metrics: %s", e)
            return web.Response(text=f"# Error: {e}", content_type="text/plain", status=500)

    async def _health_handler(self, request):
        """Handle general health check requests."""

        health_status = {
            "service": self.service_name,
            "status": "healthy" if self._running else "unhealthy",
            "server_running": self._running,
            "services_registered": len(self.service_definitions),
        }

        if self.observability:
            try:
                # Basic observability health check
                health_status["observability"] = "initialized"
            except Exception as e:
                health_status["observability_error"] = str(e)

        # Determine overall health
        is_healthy = self._running and health_status.get("status") == "healthy"
        status_code = 200 if is_healthy else 503
        return web.json_response(health_status, status=status_code)

    async def _readiness_handler(self, request):
        """Handle readiness probe requests."""

        # Check if server is ready to accept traffic
        is_ready = self._running and self.server is not None

        if is_ready:
            return web.json_response({"status": "ready"})
        else:
            return web.json_response({"status": "not_ready"}, status=503)

    async def _liveness_handler(self, request):
        """Handle liveness probe requests."""

        # Check if server is alive (basic check)
        return web.json_response({"status": "alive"})

    async def serve(self):
        """Run the server until shutdown."""
        await self.start()

        try:
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        finally:
            await self.stop()

    async def stop(self, grace_period: float = 30.0):
        """Stop the gRPC server gracefully.

        Args:
            grace_period: Grace period for shutdown in seconds
        """
        if self.server and self._running:
            self.logger.info("Stopping gRPC server...")

            # Set all services to not serving
            if self.health_servicer:
                for service_def in self.service_definitions.values():
                    if service_def.health_service_name:
                        self.health_servicer.set(
                            service_def.health_service_name,
                            health_pb2.HealthCheckResponse.ServingStatus.NOT_SERVING,
                        )

            # Stop server with grace period
            await self.server.stop(grace=grace_period)
            self._running = False

            # Shutdown observability
            if self.observability:
                await self.observability.shutdown()

            # Reset configuration state
            self.config_manager = None
            self.config = None
            self._initialized = False

            self.logger.info("gRPC server stopped")

    async def wait_for_termination(self) -> None:
        """Wait for server termination."""
        if self.server:
            await self.server.wait_for_termination()


# Factory functions for common service patterns


def create_grpc_server(
    port: int = 50051,
    service_name: str | None = None,
    interceptors: list | None = None,
    enable_health_service: bool = True,
    max_workers: int = 10,
    enable_reflection: bool = True,
    **kwargs,
) -> UnifiedGrpcServer:
    """Create a gRPC server with unified configuration.

    Args:
        port: Port to run the server on
        service_name: Name of the service
        interceptors: List of gRPC interceptors
        enable_health_service: Whether to enable health service
        max_workers: Maximum number of worker threads
        enable_reflection: Whether to enable gRPC reflection
        **kwargs: Additional configuration options

    Returns:
        Configured UnifiedGrpcServer instance
    """
    server = UnifiedGrpcServer(
        port=port,
        service_name=service_name,
        interceptors=interceptors,
        enable_health_service=enable_health_service,
        max_workers=max_workers,
        enable_reflection=enable_reflection,
        **kwargs,
    )
    return server


def create_trust_anchor_server(port: int = 50051) -> UnifiedGrpcServer:
    """Create a gRPC server for trust anchor service."""
    return create_grpc_server(port=port, service_name="trust_anchor")


def create_document_signer_server(port: int = 50051) -> UnifiedGrpcServer:
    """Create a gRPC server for document signer service."""
    return create_grpc_server(port=port, service_name="document_signer")


def create_service_server(service_name: str, port: int = 50051, **kwargs) -> UnifiedGrpcServer:
    """Create a gRPC server for any Marty service."""
    return create_grpc_server(port=port, service_name=service_name, **kwargs)
