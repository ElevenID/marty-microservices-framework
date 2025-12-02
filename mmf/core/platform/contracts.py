"""
Service Contracts for Platform Layer.

This module defines Protocol interfaces for all platform services,
following the hexagonal architecture principle of defining ports
(interfaces) that can be implemented by adapters.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class IContainer(Protocol):
    """Protocol for dependency injection container."""

    def get(self, service_type: type[T]) -> T:
        """Get a service instance by type."""


class IServiceLifecycle(Protocol):
    """Protocol for services with lifecycle management."""

    async def initialize(self) -> None:
        """Initialize the service."""

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the service."""


class IServiceRegistry(Protocol):
    """Protocol for service registry implementations."""

    def register(self, name: str, service: Any) -> None:
        """Register a service with the given name."""

    def get(self, name: str) -> Any:
        """Get a service by name."""

    def unregister(self, name: str) -> bool:
        """Unregister a service by name."""

    def has(self, name: str) -> bool:
        """Check if a service is registered."""

    def list_services(self) -> list[str]:
        """List all registered service names."""

    def clear(self) -> None:
        """Clear all registered services."""


class IConfigurationService(Protocol):
    """Protocol for configuration service implementations."""

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""

    def has(self, key: str) -> bool:
        """Check if a configuration key exists."""

    def reload(self) -> None:
        """Reload configuration from source."""

    def is_loaded(self) -> bool:
        """Check if configuration is loaded."""


class IObservabilityService(Protocol):
    """Protocol for observability service implementations."""

    def log(self, level: str, message: str, **kwargs: Any) -> None:
        """Log a message."""

    def metric(self, name: str, value: float, tags: dict[str, str] | None = None) -> None:
        """Record a metric."""

    def trace(self, operation: str) -> Any:
        """Start a trace for an operation."""

    def is_enabled(self) -> bool:
        """Check if observability is enabled."""


class ISecurityService(Protocol):
    """Protocol for security service implementations."""

    def authenticate(self, credentials: dict[str, Any]) -> bool:
        """Authenticate with credentials."""

    def authorize(self, user: str, resource: str, action: str) -> bool:
        """Authorize user action on resource."""

    def encrypt(self, data: str) -> str:
        """Encrypt data."""

    def decrypt(self, data: str) -> str:
        """Decrypt data."""

    def is_secure(self) -> bool:
        """Check if security is enabled."""

    async def analyze_event(self, event: Any) -> Any:
        """Analyze a security event for threats."""

    def scan_code(self, code: str, file_path: str = "") -> list[Any]:
        """Scan code for vulnerabilities."""


class IMessagingService(Protocol):
    """Protocol for messaging service implementations."""

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish a message to a topic."""

    async def subscribe(self, topic: str, handler: Any) -> None:
        """Subscribe to a topic with a handler."""

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""

    def is_connected(self) -> bool:
        """Check if messaging is connected."""
