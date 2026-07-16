"""
Observability Service Factories for Dependency Injection

This module provides factory classes for creating observability-related services
with proper dependency injection and type safety.
"""

from __future__ import annotations

from typing import Any, Optional

from mmf.framework.infrastructure.dependency_injection import (
    ServiceFactory,
    get_container,
    register_factory,
    register_instance,
)


# Use DI container to store class references instead of globals
class _StandardObservabilityServiceClassRegistry:
    """Registry for standard observability service class."""

    pass


class _StandardObservabilityClassRegistry:
    """Registry for standard observability class."""

    pass


class _TracingServiceClassRegistry:
    """Registry for tracing service class."""

    pass


class _FrameworkMetricsClassRegistry:
    """Registry for framework metrics class."""

    pass


def set_standard_observability_classes(
    service_cls: type[Any], observability_cls: type[Any]
) -> None:
    """Register the concrete observability service and implementation classes."""
    register_instance(_StandardObservabilityServiceClassRegistry, service_cls)
    register_instance(_StandardObservabilityClassRegistry, observability_cls)


def get_standard_observability_service_class() -> type[Any]:
    service_cls = get_container().get(_StandardObservabilityServiceClassRegistry)
    if service_cls is None:
        raise RuntimeError("StandardObservabilityService class not registered")
    return service_cls  # type: ignore[return-value]


def get_standard_observability_class() -> type[Any]:
    observability_cls = get_container().get(_StandardObservabilityClassRegistry)
    if observability_cls is None:
        raise RuntimeError("StandardObservability class not registered")
    return observability_cls  # type: ignore[return-value]


def set_tracing_service_class(service_cls: type[Any]) -> None:
    """Register the concrete tracing service class."""
    register_instance(_TracingServiceClassRegistry, service_cls)


def get_tracing_service_class() -> type[Any]:
    service_cls = get_container().get(_TracingServiceClassRegistry)
    if service_cls is None:
        raise RuntimeError("TracingService class not registered")
    return service_cls  # type: ignore[return-value]


def set_framework_metrics_class(metrics_cls: type[Any]) -> None:
    """Register the concrete framework metrics class."""
    register_instance(_FrameworkMetricsClassRegistry, metrics_cls)


def get_framework_metrics_class() -> type[Any]:
    metrics_cls = get_container().get(_FrameworkMetricsClassRegistry)
    if metrics_cls is None:
        raise RuntimeError("FrameworkMetrics class not registered")
    return metrics_cls  # type: ignore[return-value]


class StandardObservabilityServiceFactory(ServiceFactory):
    """Factory for creating StandardObservabilityService instances."""

    def create(self, config: dict[str, Any] | None = None) -> Any:
        """Create a new StandardObservabilityService instance."""
        service_cls = get_standard_observability_service_class()
        service = service_cls()
        if config:
            service_name = config.get("service_name", "unknown")
            service.initialize(service_name, config)
        return service

    def get_service_type(self) -> type[Any]:
        """Get the service type this factory creates."""
        return get_standard_observability_service_class()


class StandardObservabilityFactory(ServiceFactory):
    """Factory for creating StandardObservability instances."""

    def create(self, config: dict[str, Any] | None = None) -> Any:
        """Create a new StandardObservability instance."""

        # Get or create the service instance
        service = get_container().get(get_standard_observability_service_class())
        if service is None:
            raise ValueError("StandardObservabilityService not found")

        if config and not service.is_initialized():
            service_name = config.get("service_name", "unknown")
            service.initialize(service_name, config)

        observability = service.get_observability()
        if observability is None:
            raise ValueError("Failed to create StandardObservability instance")
        return observability

    def get_service_type(self) -> type[Any]:
        """Get the service type this factory creates."""
        return get_standard_observability_class()


class TracingServiceFactory(ServiceFactory):
    """Factory for creating TracingService instances."""

    def create(self, config: dict[str, Any] | None = None) -> Any:
        """Create a new TracingService instance."""
        service_cls = get_tracing_service_class()
        service = service_cls()
        if config:
            service_name = config.get("service_name", "unknown")
            service.initialize(service_name, config)
        return service

    def get_service_type(self) -> type[Any]:
        """Get the service type this factory creates."""
        return get_tracing_service_class()


class FrameworkMetricsFactory(ServiceFactory):
    """Factory for creating FrameworkMetrics instances."""

    def __init__(self, service_name: str = "unknown") -> None:
        """Initialize the factory with a default service name."""
        self._service_name = service_name

    def create(self, config: dict[str, Any] | None = None) -> Any:
        """Create a new FrameworkMetrics instance."""
        service_name = self._service_name
        if config and "service_name" in config:
            service_name = config["service_name"]

        metrics_cls = get_framework_metrics_class()
        metrics = metrics_cls(service_name)
        return metrics

    def get_service_type(self) -> type[Any]:
        """Get the service type this factory creates."""
        return get_framework_metrics_class()


# Convenience functions for registering observability services
def register_observability_services(service_name: str = "unknown") -> None:
    """Register all observability services with the DI container."""

    register_factory(
        get_standard_observability_service_class(),
        StandardObservabilityServiceFactory(),
    )
    register_factory(
        get_standard_observability_class(),
        StandardObservabilityFactory(),
    )
    register_factory(get_tracing_service_class(), TracingServiceFactory())
    register_factory(get_framework_metrics_class(), FrameworkMetricsFactory(service_name))
