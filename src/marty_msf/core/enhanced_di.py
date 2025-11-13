"""
Enhanced Dependency Injection System for Marty MSF

This module extends the existing DI container with strongly typed service registry
and context-aware service management to eliminate global variables.
"""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from typing_extensions import Protocol

from marty_msf.core.di_container import DIContainer, ServiceFactory

T = TypeVar("T")
ServiceType = TypeVar("ServiceType")


class ServiceLifecycle(Protocol):
    """Protocol for services with lifecycle management."""

    async def initialize(self) -> None:
        """Initialize the service."""
        pass

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources."""
        pass

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the service."""
        pass


@dataclass
class ServiceRegistration(Generic[T]):
    """Registration information for a service."""

    service_type: type[T]
    factory: ServiceFactory[T] | None = None
    instance: T | None = None
    config: dict[str, Any] = field(default_factory=dict)
    is_singleton: bool = True
    initialized: bool = False


class ServiceScope:
    """Service scope for managing service lifetimes."""

    def __init__(self, name: str, parent: ServiceScope | None = None):
        self.name = name
        self.parent = parent
        self._services: dict[type[Any], Any] = {}
        self._lock = threading.RLock()

    def get_service(self, service_type: type[T]) -> T | None:
        """Get a service from this scope or parent scopes."""
        with self._lock:
            if service_type in self._services:
                return self._services[service_type]

            if self.parent:
                return self.parent.get_service(service_type)

            return None

    def set_service(self, service_type: type[T], instance: T) -> None:
        """Set a service in this scope."""
        with self._lock:
            self._services[service_type] = instance

    def clear(self) -> None:
        """Clear all services in this scope."""
        with self._lock:
            self._services.clear()


class EnhancedDIContainer(DIContainer):
    """Enhanced DI container with proper service lifecycle and scoping."""

    def __init__(self):
        super().__init__()
        self._registrations: dict[type[Any], ServiceRegistration[Any]] = {}
        self._scopes: dict[str, ServiceScope] = {}
        self._current_scope: ServiceScope | None = None
        self._initialization_lock = threading.RLock()
        self._thread_local = threading.local()

        # Create default scope
        self._default_scope = ServiceScope("default")
        self._scopes["default"] = self._default_scope
        self._current_scope = self._default_scope

    def register_service(
        self,
        service_type: type[T],
        factory: ServiceFactory[T] | None = None,
        instance: T | None = None,
        config: dict[str, Any] | None = None,
        is_singleton: bool = True,
    ) -> ServiceRegistration[T]:
        """Register a service with optional factory or instance."""
        with self._lock:
            registration = ServiceRegistration(
                service_type=service_type,
                factory=factory,
                instance=instance,
                config=config or {},
                is_singleton=is_singleton,
            )
            self._registrations[service_type] = registration

            # If instance provided, also register in parent container
            if instance:
                self.register_instance(service_type, instance)

            return registration

    def get_service_typed(self, service_type: type[T]) -> T:
        """Get a service instance with strong typing."""
        return self._get_or_create_service(service_type)

    def get_service_optional(self, service_type: type[T]) -> T | None:
        """Get a service instance or None if not registered."""
        try:
            return self._get_or_create_service(service_type)
        except (KeyError, ValueError, RuntimeError):
            return None

    def _get_or_create_service(self, service_type: type[T]) -> T:
        """Get or create a service instance."""
        # Check current scope first
        if self._current_scope:
            instance = self._current_scope.get_service(service_type)
            if instance is not None:
                return instance

        # Check if we have a registration
        with self._lock:
            if service_type not in self._registrations:
                # Fall back to parent container
                return super().get(service_type)

            registration = self._registrations[service_type]

            # Return existing instance if singleton
            if registration.is_singleton and registration.instance:
                return registration.instance

            # Create new instance
            if registration.factory:
                instance = registration.factory.create(registration.config)
            elif registration.instance:
                instance = registration.instance
            else:
                # Try parent container
                instance = super().get(service_type)

            # Initialize if needed
            if hasattr(instance, "initialize") and not registration.initialized:
                if hasattr(instance, "configure"):
                    instance.configure(registration.config)
                registration.initialized = True

            # Store as singleton if needed
            if registration.is_singleton:
                registration.instance = instance
                if self._current_scope:
                    self._current_scope.set_service(service_type, instance)

            return instance

    @contextmanager
    def create_scope(self, scope_name: str) -> Iterator[ServiceScope]:
        """Create or enter a service scope."""
        with self._lock:
            if scope_name not in self._scopes:
                self._scopes[scope_name] = ServiceScope(scope_name, self._current_scope)

            scope = self._scopes[scope_name]
            previous_scope = self._current_scope
            self._current_scope = scope

            try:
                yield scope
            finally:
                self._current_scope = previous_scope

    async def initialize_all_services(self) -> None:
        """Initialize all registered services."""
        with self._initialization_lock:
            for service_type, registration in self._registrations.items():
                if not registration.initialized:
                    instance = self._get_or_create_service(service_type)
                    if hasattr(instance, "initialize"):
                        await instance.initialize()
                    registration.initialized = True

    async def shutdown_all_services(self) -> None:
        """Shutdown all services."""
        with self._initialization_lock:
            for registration in self._registrations.values():
                if registration.instance and hasattr(registration.instance, "shutdown"):
                    await registration.instance.shutdown()
                registration.initialized = False

    def clear_scope(self, scope_name: str) -> None:
        """Clear a specific scope."""
        with self._lock:
            if scope_name in self._scopes:
                self._scopes[scope_name].clear()
                if scope_name != "default":
                    del self._scopes[scope_name]


# Container registry using the singleton pattern instead of global
class ContainerRegistry:
    """Registry for managing the enhanced DI container without globals."""

    _instance: ContainerRegistry | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._container: EnhancedDIContainer | None = None
        self._container_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> ContainerRegistry:
        """Get the singleton registry instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_container(self) -> EnhancedDIContainer:
        """Get the enhanced DI container instance."""
        if self._container is None:
            with self._container_lock:
                if self._container is None:
                    self._container = EnhancedDIContainer()
        return self._container

    def reset_container(self) -> None:
        """Reset the enhanced container (primarily for testing)."""
        with self._container_lock:
            if self._container is not None:
                self._container.clear()
            self._container = None


def get_enhanced_container() -> EnhancedDIContainer:
    """Get the global enhanced DI container instance."""
    return ContainerRegistry.get_instance().get_container()


def reset_enhanced_container() -> None:
    """Reset the enhanced container (primarily for testing)."""
    ContainerRegistry.get_instance().reset_container()


# Strongly typed convenience functions
def register_service(
    service_type: type[T],
    factory: ServiceFactory[T] | None = None,
    instance: T | None = None,
    config: dict[str, Any] | None = None,
    is_singleton: bool = True,
) -> ServiceRegistration[T]:
    """Register a service with the enhanced container."""
    return get_enhanced_container().register_service(
        service_type, factory, instance, config, is_singleton
    )


def get_service(service_type: type[T]) -> T:
    """Get a service instance with strong typing."""
    return get_enhanced_container().get_service_typed(service_type)


def get_service_optional(service_type: type[T]) -> T | None:
    """Get a service instance or None if not found."""
    return get_enhanced_container().get_service_optional(service_type)


def has_service(service_type: type[T]) -> bool:
    """Check if a service type is registered."""
    return get_enhanced_container().has(service_type)


@contextmanager
def service_scope(scope_name: str) -> Iterator[ServiceScope]:
    """Create or enter a service scope."""
    with get_enhanced_container().create_scope(scope_name) as scope:
        yield scope


# Service factory implementations
class LambdaFactory(ServiceFactory[T]):
    """Factory that uses a lambda function to create services."""

    def __init__(self, service_type: type[T], factory_func: Callable[[dict[str, Any]], T]):
        self._service_type = service_type
        self._factory_func = factory_func

    def create(self, config: dict[str, Any] | None = None) -> T:
        """Create a new instance using the factory function."""
        return self._factory_func(config or {})

    def get_service_type(self) -> type[T]:
        """Get the service type."""
        return self._service_type


class SingletonFactory(ServiceFactory[T]):
    """Factory that ensures only one instance is created."""

    def __init__(self, service_type: type[T], factory: ServiceFactory[T]):
        self._service_type = service_type
        self._factory = factory
        self._instance: T | None = None
        self._lock = threading.Lock()

    def create(self, config: dict[str, Any] | None = None) -> T:
        """Create or return the singleton instance."""
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._factory.create(config)
        return self._instance

    def get_service_type(self) -> type[T]:
        """Get the service type."""
        return self._service_type


# Decorator for automatic service registration
def service(
    service_type: type[T] | None = None,
    is_singleton: bool = True,
    config: dict[str, Any] | None = None,
) -> Callable[[type[T]], type[T]]:
    """Decorator to automatically register a service."""

    def decorator(cls: type[T]) -> type[T]:
        actual_service_type = service_type or cls

        def factory_func(_cfg: dict[str, Any]) -> T:
            return cls()  # Assuming default constructor

        factory = LambdaFactory(actual_service_type, factory_func)
        register_service(actual_service_type, factory, config=config, is_singleton=is_singleton)
        return cls

    return decorator


# Context manager for service initialization
@asynccontextmanager
async def service_context() -> AsyncIterator[EnhancedDIContainer]:
    """Context manager for service lifecycle."""
    container = get_enhanced_container()
    try:
        await container.initialize_all_services()
        yield container
    finally:
        await container.shutdown_all_services()
