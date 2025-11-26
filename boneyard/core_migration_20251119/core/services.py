"""
Typed service base classes for common global patterns.

This module provides strongly-typed base classes for common patterns
found in the microservices framework, replacing global variable usage.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Protocol, TypeVar

from .registry import TypedSingleton, get_service, register_singleton

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConfigService(TypedSingleton[Any], ABC):
    """
    Base class for configuration services.

    Replaces global config variables with proper typed singleton pattern.
    """

    def __init__(self) -> None:
        super().__init__()
        self._config_data: dict[str, Any] = {}
        self._is_loaded = False

    @abstractmethod
    def load_from_env(self) -> None:
        """Load configuration from environment variables."""
        pass

    @abstractmethod
    def load_from_file(self, config_path: str | Path) -> None:
        """Load configuration from file."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate the current configuration."""
        pass

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        return self._config_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        self._config_data[key] = value

    def is_loaded(self) -> bool:
        """Check if configuration has been loaded."""
        return self._is_loaded

    def _mark_loaded(self) -> None:
        """Mark configuration as loaded."""
        self._is_loaded = True


class ObservabilityService(TypedSingleton[Any], ABC):
    """
    Base class for observability services.

    Replaces global observability instances with proper typed pattern.
    """

    def __init__(self) -> None:
        super().__init__()
        self._initialized = False

    @abstractmethod
    def initialize(self, service_name: str, config: dict[str, Any] | None = None) -> None:
        """Initialize the observability service."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources."""
        pass

    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized

    def _mark_initialized(self) -> None:
        """Mark service as initialized."""
        self._initialized = True


class SecurityService(TypedSingleton[Any], ABC):
    """
    Base class for security services.

    Replaces global security manager instances.
    """

    def __init__(self) -> None:
        super().__init__()
        self._configured = False

    @abstractmethod
    def configure(self, config: dict[str, Any]) -> None:
        """Configure the security service."""
        pass

    @abstractmethod
    def is_authenticated(self, token: str) -> bool:
        """Check if a token is authenticated."""
        pass

    @abstractmethod
    def is_authorized(self, user_id: str, resource: str, action: str) -> bool:
        """Check if a user is authorized for an action."""
        pass

    def is_configured(self) -> bool:
        """Check if the service is configured."""
        return self._configured

    def _mark_configured(self) -> None:
        """Mark service as configured."""
        self._configured = True


class MessagingService(TypedSingleton[Any], ABC):
    """
    Base class for messaging services.

    Replaces global event bus and messaging instances.
    """

    def __init__(self) -> None:
        super().__init__()
        self._started = False

    @abstractmethod
    async def start(self) -> None:
        """Start the messaging service."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the messaging service."""
        pass

    @abstractmethod
    async def publish(self, topic: str, message: Any) -> None:
        """Publish a message to a topic."""
        pass

    @abstractmethod
    async def subscribe(self, topic: str, handler: Any) -> None:
        """Subscribe to a topic with a handler."""
        pass

    def is_started(self) -> bool:
        """Check if the service is started."""
        return self._started

    def _mark_started(self) -> None:
        """Mark service as started."""
        self._started = True

    def _mark_stopped(self) -> None:
        """Mark service as stopped."""
        self._started = False


class ManagerService(TypedSingleton[Any], ABC):
    """
    Base class for manager services.

    Generic base for various manager types (resilience, monitoring, etc.).
    """

    def __init__(self) -> None:
        super().__init__()
        self._active = False

    @abstractmethod
    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the manager."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the manager."""
        pass

    def is_active(self) -> bool:
        """Check if the manager is active."""
        return self._active

    def _mark_active(self) -> None:
        """Mark manager as active."""
        self._active = True

    def _mark_inactive(self) -> None:
        """Mark manager as inactive."""
        self._active = False


# Service discovery protocol for type checking
class ServiceProtocol(Protocol):
    """Protocol for discoverable services."""

    def get_service_name(self) -> str:
        """Get the service name."""
        ...

    def get_service_version(self) -> str:
        """Get the service version."""
        ...

    def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        ...


def get_config_service(service_type: type[T]) -> T:
    """Get a configuration service instance."""
    return get_service(service_type)


def get_observability_service(service_type: type[T]) -> T:
    """Get an observability service instance."""
    return get_service(service_type)


def get_security_service(service_type: type[T]) -> T:
    """Get a security service instance."""
    return get_service(service_type)


def get_messaging_service(service_type: type[T]) -> T:
    """Get a messaging service instance."""
    return get_service(service_type)


def get_manager_service(service_type: type[T]) -> T:
    """Get a manager service instance."""
    return get_service(service_type)


def register_config_service(service: ConfigService) -> None:
    """Register a configuration service."""
    register_singleton(type(service), service)


def register_observability_service(service: ObservabilityService) -> None:
    """Register an observability service."""
    register_singleton(type(service), service)


def register_security_service(service: SecurityService) -> None:
    """Register a security service."""
    register_singleton(type(service), service)


def register_messaging_service(service: MessagingService) -> None:
    """Register a messaging service."""
    register_singleton(type(service), service)


def register_manager_service(service: ManagerService) -> None:
    """Register a manager service."""
    register_singleton(type(service), service)
