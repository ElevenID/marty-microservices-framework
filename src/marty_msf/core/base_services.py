"""
Service base classes for the enhanced DI system.

This module provides base classes and type definitions for services
that integrate with the enhanced dependency injection system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar, cast

from marty_msf.core.enhanced_di import ServiceLifecycle, get_service

T = TypeVar("T")
ServiceT = TypeVar("ServiceT", bound="BaseService")


class BaseService(ABC, ServiceLifecycle):
    """Base class for all services in the framework."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._initialized = False

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the service with the given configuration."""
        self._config.update(config)

    async def initialize(self) -> None:
        """Initialize the service."""
        if self._initialized:
            return
        await self._on_initialize()
        self._initialized = True

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        if not self._initialized:
            return
        await self._on_shutdown()
        self._initialized = False

    @abstractmethod
    async def _on_initialize(self) -> None:
        """Override this method to implement service-specific initialization."""
        pass

    @abstractmethod
    async def _on_shutdown(self) -> None:
        """Override this method to implement service-specific shutdown."""
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized

    @property
    def config(self) -> dict[str, Any]:
        """Get the service configuration."""
        return self._config.copy()


class SingletonService(BaseService):
    """Base class for singleton services."""

    _instances: dict[type[SingletonService], SingletonService] = {}

    def __new__(cls, *_args, **_kwargs) -> SingletonService:
        """Ensure only one instance per class."""
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

    @classmethod
    def reset_instances(cls) -> None:
        """Reset all singleton instances (for testing)."""
        cls._instances.clear()


class DependentService(BaseService):
    """Base class for services that depend on other services."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._dependencies: dict[str, Any] = {}

    def add_dependency(self, name: str, service_type: type[T]) -> None:
        """Add a dependency that will be resolved from the DI container."""
        self._dependencies[name] = service_type

    def get_dependency(self, name: str) -> Any:
        """Get a resolved dependency."""
        if name not in self._dependencies:
            raise ValueError(f"Dependency '{name}' not registered")
        return get_service(self._dependencies[name])

    async def _on_initialize(self) -> None:
        """Default initialization that resolves dependencies."""
        # Resolve all dependencies
        for _name, service_type in self._dependencies.items():
            service = get_service(service_type)
            if hasattr(service, "initialize") and not getattr(service, "is_initialized", True):
                await service.initialize()

    async def _on_shutdown(self) -> None:
        """Default shutdown implementation."""
        pass
