"""
Service Initialization Helper

This module provides a simple service initialization pattern for example applications
to replace global variables with properly managed instances.
"""

from __future__ import annotations

from typing import Any, Optional, TypeVar

T = TypeVar("T")


class ServiceRegistry:
    """Simple service registry for example applications."""

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    def register(self, name: str, service: Any) -> None:
        """Register a service by name."""
        self._services[name] = service

    def get(self, name: str, service_type: type | None = None) -> Any:
        """Get a service by name."""
        service = self._services.get(name)
        if service is None:
            raise ValueError(f"Service '{name}' not registered")

        if service_type and not isinstance(service, service_type):
            raise TypeError(f"Service '{name}' is not of type {service_type}")

        return service

    def get_optional(self, name: str, service_type: type | None = None) -> Any | None:
        """Get a service by name, returning None if not found."""
        try:
            return self.get(name, service_type)
        except (ValueError, TypeError):
            return None

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()


# Global registry for backward compatibility
_registry = ServiceRegistry()


def get_service_registry() -> ServiceRegistry:
    """Get the global service registry."""
    return _registry


def register_service(name: str, service: Any) -> None:
    """Register a service globally."""
    _registry.register(name, service)


def get_service(name: str, service_type: type | None = None) -> Any:
    """Get a service globally."""
    return _registry.get(name, service_type)


def get_service_optional(name: str, service_type: type | None = None) -> Any | None:
    """Get a service globally (optional)."""
    return _registry.get_optional(name, service_type)


def clear_services() -> None:
    """Clear all services (for testing)."""
    _registry.clear()
