"""
Observability Service Factories for Dependency Injection

This module provides factory classes for creating observability-related services
with proper dependency injection and type safety.
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.di_container import ServiceFactory, get_service, register_factory
from .framework_metrics import FrameworkMetrics
from .standard import StandardObservability, StandardObservabilityService
from .tracing import TracingService


class StandardObservabilityServiceFactory(ServiceFactory[StandardObservabilityService]):
    """Factory for creating StandardObservabilityService instances."""

    def create(self, config: dict[str, Any] | None = None) -> StandardObservabilityService:
        """Create a new StandardObservabilityService instance."""
        service = StandardObservabilityService()
        if config:
            service_name = config.get("service_name", "unknown")
            service.initialize(service_name, config)
        return service

    def get_service_type(self) -> type[StandardObservabilityService]:
        """Get the service type this factory creates."""
        return StandardObservabilityService


class StandardObservabilityFactory(ServiceFactory[StandardObservability]):
    """Factory for creating StandardObservability instances."""

    def create(self, config: dict[str, Any] | None = None) -> StandardObservability:
        """Create a new StandardObservability instance."""

        # Get or create the service instance
        service = get_service(StandardObservabilityService)
        if config and not service.is_initialized():
            service_name = config.get("service_name", "unknown")
            service.initialize(service_name, config)

        observability = service.get_observability()
        if observability is None:
            raise ValueError("Failed to create StandardObservability instance")
        return observability

    def get_service_type(self) -> type[StandardObservability]:
        """Get the service type this factory creates."""
        return StandardObservability


class TracingServiceFactory(ServiceFactory[TracingService]):
    """Factory for creating TracingService instances."""

    def create(self, config: dict[str, Any] | None = None) -> TracingService:
        """Create a new TracingService instance."""
        service = TracingService()
        if config:
            service_name = config.get("service_name", "unknown")
            service.initialize(service_name, config)
        return service

    def get_service_type(self) -> type[TracingService]:
        """Get the service type this factory creates."""
        return TracingService


class FrameworkMetricsFactory(ServiceFactory[FrameworkMetrics]):
    """Factory for creating FrameworkMetrics instances."""

    def __init__(self, service_name: str = "unknown") -> None:
        """Initialize the factory with a default service name."""
        self._service_name = service_name

    def create(self, config: dict[str, Any] | None = None) -> FrameworkMetrics:
        """Create a new FrameworkMetrics instance."""
        service_name = self._service_name
        if config and "service_name" in config:
            service_name = config["service_name"]

        metrics = FrameworkMetrics(service_name)
        return metrics

    def get_service_type(self) -> type[FrameworkMetrics]:
        """Get the service type this factory creates."""
        return FrameworkMetrics


# Convenience functions for registering observability services
def register_observability_services(service_name: str = "unknown") -> None:
    """Register all observability services with the DI container."""

    register_factory(StandardObservabilityService, StandardObservabilityServiceFactory())
    register_factory(StandardObservability, StandardObservabilityFactory())
    register_factory(TracingService, TracingServiceFactory())
    register_factory(FrameworkMetrics, FrameworkMetricsFactory(service_name))
