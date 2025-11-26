"""
Base Service Classes for Platform Layer.

This module provides base classes for services that integrate with
the dependency injection container and follow the ServiceLifecycle protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from mmf_new.core.platform.contracts import IContainer, IServiceLifecycle

T = TypeVar("T")
ServiceT = TypeVar("ServiceT", bound="BaseService")


class BaseService(ABC, IServiceLifecycle):
    """Base class for all services in the framework."""

    def __init__(self, container: IContainer, config: dict[str, Any] | None = None):
        """Initialize with dependency injection container."""
        self._container = container
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

    @abstractmethod
    async def _on_shutdown(self) -> None:
        """Override this method to implement service-specific shutdown."""

    @property
    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized

    @property
    def config(self) -> dict[str, Any]:
        """Get the service configuration."""
        return self._config.copy()

    @property
    def container(self) -> IContainer:
        """Get the dependency injection container."""
        return self._container


class ServiceWithDependencies(BaseService):
    """Base class for services that depend on other services."""

    def __init__(self, container: IContainer, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self._dependencies: dict[str, type[Any]] = {}
        self._resolved_dependencies: dict[str, Any] = {}

    def add_dependency(self, name: str, service_type: type[T]) -> None:
        """Add a dependency that will be resolved from the DI container."""
        self._dependencies[name] = service_type

    def get_dependency(self, name: str) -> Any:
        """Get a resolved dependency."""
        if name not in self._dependencies:
            raise ValueError(f"Dependency '{name}' not registered")

        # Return cached dependency if already resolved
        if name in self._resolved_dependencies:
            return self._resolved_dependencies[name]

        # Resolve from container
        service = self._container.get(self._dependencies[name])
        self._resolved_dependencies[name] = service
        return service

    async def _on_initialize(self) -> None:
        """Default initialization that resolves and initializes dependencies."""
        # Resolve all dependencies
        for name, service_type in self._dependencies.items():
            service = self._container.get(service_type)
            self._resolved_dependencies[name] = service

            # Initialize dependency if it supports initialization
            if hasattr(service, "initialize") and hasattr(service, "is_initialized"):
                if not service.is_initialized:
                    await service.initialize()

    async def _on_shutdown(self) -> None:
        """Default shutdown implementation."""
        # Clear resolved dependencies
        self._resolved_dependencies.clear()
