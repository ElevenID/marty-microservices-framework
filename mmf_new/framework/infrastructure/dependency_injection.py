"""
Dependency Injection Container for MMF Framework

This module provides a strongly typed dependency injection container to replace
global variables throughout the framework. It ensures proper lifecycle management,
thread safety, and strong typing support with MyPy.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar, cast, overload

from typing_extensions import Protocol

from mmf_new.core.platform.contracts import IServiceLifecycle

from .cache import CacheBackend, CacheConfig, SerializationFormat, create_cache_manager

T = TypeVar("T")
ServiceType = TypeVar("ServiceType")
_MISSING = object()  # Sentinel value for missing defaults

# Alias for backward compatibility
ServiceLifecycle = IServiceLifecycle


class ServiceProtocol(Protocol):
    """Protocol for services that can be managed by the DI container."""

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the service with the given configuration."""

    def shutdown(self) -> None:
        """Clean shutdown of the service."""


@dataclass
class RegistrationInfo(Generic[T]):
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


class ServiceFactory(Generic[T], ABC):
    """Abstract base class for service factories."""

    @abstractmethod
    def create(self, config: dict[str, Any] | None = None) -> T:
        """Create a new instance of the service."""

    @abstractmethod
    def get_service_type(self) -> type[T]:
        """Get the type of service this factory creates."""


class SingletonMeta(type):
    """Thread-safe singleton metaclass."""

    _instances: dict[type, Any] = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class DIContainer(metaclass=SingletonMeta):
    """
    Dependency Injection Container with strong typing support.

    This container manages service instances with proper lifecycle management,
    thread safety, and MyPy-compatible type annotations.
    """

    def __init__(self) -> None:
        # Initialize enterprise caches for DI container

        # Cache for service instances
        services_cache_config = CacheConfig(
            backend=CacheBackend.MEMORY,
            serialization=SerializationFormat.PICKLE,  # Services may not be JSON serializable
            default_ttl=0,  # Services persist for app lifetime
            namespace="di_services",
        )
        self._services_cache = create_cache_manager("di_services", services_cache_config)

        # Cache for service factories
        factories_cache_config = CacheConfig(
            backend=CacheBackend.MEMORY,
            serialization=SerializationFormat.PICKLE,  # Factories may not be JSON serializable
            default_ttl=0,  # Factories persist for app lifetime
            namespace="di_factories",
        )
        self._factories_cache = create_cache_manager("di_factories", factories_cache_config)

        # Cache for service configurations (JSON safe)
        config_cache_config = CacheConfig(
            backend=CacheBackend.MEMORY,
            serialization=SerializationFormat.JSON,
            default_ttl=0,  # Configurations persist for app lifetime
            namespace="di_config",
        )
        self._configurations_cache = create_cache_manager("di_config", config_cache_config)

        # Enhanced DI features
        self._registrations: dict[type[Any], RegistrationInfo[Any]] = {}
        self._scopes: dict[str, ServiceScope] = {}
        self._current_scope: ServiceScope | None = None
        self._initialization_lock = threading.RLock()

        # Maintain compatibility with cache-based approach
        self._services: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], ServiceFactory[Any]] = {}
        self._configurations: dict[type[Any], dict[str, Any]] = {}

        # Create default scope
        self._default_scope = ServiceScope("default")
        self._scopes["default"] = self._default_scope
        self._current_scope = self._default_scope

        self._lock = threading.RLock()
        self._started = False

    async def start(self) -> None:
        """Start the DI container and initialize caches."""
        if self._started:
            return
        await self._services_cache.start()
        await self._factories_cache.start()
        await self._configurations_cache.start()
        self._started = True

    async def stop(self) -> None:
        """Stop the DI container and clean up caches."""
        await self._services_cache.stop()
        await self._factories_cache.stop()
        await self._configurations_cache.stop()
        self._started = False

    def register_factory(self, service_type: type[T], factory: ServiceFactory[T]) -> None:
        """Register a factory for a service type."""
        with self._lock:
            self._factories[service_type] = factory

    def register_instance(self, service_type: type[T], instance: T) -> None:
        """Register a pre-created instance for a service type."""
        with self._lock:
            self._services[service_type] = instance

    def configure(self, service_type: type[T], config: dict[str, Any]) -> None:
        """Configure a service type with the given configuration."""
        with self._lock:
            self._configurations[service_type] = config
            # If instance already exists, reconfigure it
            if service_type in self._services:
                service = self._services[service_type]
                if hasattr(service, "configure"):
                    service.configure(config)

    @overload
    def get(self, service_type: type[T]) -> T:
        pass

    @overload
    def get(self, service_type: type[T], default: object = _MISSING) -> T | None:
        pass

    def get(self, service_type: type[T], default: object = _MISSING) -> T | None:
        """
        Get a service instance of the specified type.

        Args:
            service_type: The type of service to retrieve
            default: Default value if service not found

        Returns:
            The service instance or default value

        Raises:
            ValueError: If service type is not registered and no default provided
        """
        with self._lock:
            # Return existing instance if available
            if service_type in self._services:
                return cast(T, self._services[service_type])

            # Create instance using factory
            if service_type in self._factories:
                factory = self._factories[service_type]
                config = self._configurations.get(service_type, {})
                instance = factory.create(config)
                self._services[service_type] = instance
                return cast(T, instance)

            # Return default if provided
            if default is not _MISSING:
                return default  # type: ignore

            raise ValueError(f"No factory or instance registered for {service_type}")

    def get_or_create(self, service_type: type[T], factory_func: Callable[[], T]) -> T:
        """
        Get existing service or create using factory function.

        Args:
            service_type: The type of service to retrieve
            factory_func: Function to create the service if it doesn't exist

        Returns:
            The service instance
        """
        with self._lock:
            if service_type in self._services:
                return cast(T, self._services[service_type])

            instance = factory_func()
            self._services[service_type] = instance
            return instance

    def has(self, service_type: type[T]) -> bool:
        """Check if a service type is registered."""
        with self._lock:
            return service_type in self._services or service_type in self._factories

    def remove(self, service_type: type[T]) -> bool:
        """
        Remove a service from the container.

        Args:
            service_type: The type of service to remove

        Returns:
            True if service was removed, False if not found
        """
        with self._lock:
            removed = False
            if service_type in self._services:
                service = self._services.pop(service_type)
                # Call shutdown if available
                if hasattr(service, "shutdown"):
                    try:
                        service.shutdown()
                    except (AttributeError, RuntimeError):
                        # Log error but don't re-raise during cleanup
                        pass
                removed = True

            if service_type in self._factories:
                self._factories.pop(service_type)
                removed = True

            if service_type in self._configurations:
                self._configurations.pop(service_type)

            return removed

    def clear(self) -> None:
        """Clear all services from the container."""
        with self._lock:
            # Shutdown all services
            for service in self._services.values():
                if hasattr(service, "shutdown"):
                    try:
                        service.shutdown()
                    except (AttributeError, RuntimeError):
                        # Log error but don't re-raise during cleanup
                        pass

            self._services.clear()
            self._factories.clear()
            self._configurations.clear()

    def register_service(
        self,
        service_type: type[T],
        factory: ServiceFactory[T] | None = None,
        instance: T | None = None,
        config: dict[str, Any] | None = None,
        is_singleton: bool = True,
    ) -> RegistrationInfo[T]:
        """Register a service with optional factory or instance."""
        with self._lock:
            registration = RegistrationInfo(
                service_type=service_type,
                factory=factory,
                instance=instance,
                config=config or {},
                is_singleton=is_singleton,
            )
            self._registrations[service_type] = registration

            # If instance provided, also register in legacy container
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
                # Fall back to standard get method
                return self.get(service_type)

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
                # Try standard get method
                instance = self.get(service_type)

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

    @contextmanager
    def scope(self):
        """Create a scoped context for temporary service registration."""
        original_services = self._services.copy()
        original_factories = self._factories.copy()
        original_configurations = self._configurations.copy()

        try:
            yield self
        finally:
            # Restore original state
            with self._lock:
                # Shutdown any services that weren't in original state
                for service_type, service in self._services.items():
                    if service_type not in original_services:
                        if hasattr(service, "shutdown"):
                            try:
                                service.shutdown()
                            except (AttributeError, RuntimeError):
                                pass

                self._services = original_services
                self._factories = original_factories
                self._configurations = original_configurations


# Container singleton management using class-based approach
class _ContainerSingleton:
    _instance: DIContainer | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> DIContainer:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DIContainer()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the container instance - primarily for testing."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.clear()
                cls._instance = None


def get_container() -> DIContainer:
    """Get the global DI container instance."""
    return _ContainerSingleton.get_instance()


def reset_container() -> None:
    """Reset the global container (primarily for testing)."""
    _ContainerSingleton.reset()


# Convenience functions with strong typing
def register_factory(service_type: type[T], factory: ServiceFactory[T]) -> None:
    """Register a factory for a service type."""
    get_container().register_factory(service_type, factory)


def register_instance(service_type: type[T], instance: T) -> None:
    """Register a pre-created instance for a service type."""
    get_container().register_instance(service_type, instance)


def configure_service(service_type: type[T], config: dict[str, Any]) -> None:
    """Configure a service type with the given configuration."""
    get_container().configure(service_type, config)


def get_service(service_type: type[T]) -> T:
    """Get a service instance of the specified type."""
    return get_container().get(service_type)


def get_service_optional(service_type: type[T]) -> T | None:
    """Get a service instance of the specified type, or None if not found."""
    return get_container().get(service_type, None)


def has_service(service_type: type[T]) -> bool:
    """Check if a service type is registered."""
    return get_container().has(service_type)


# Enhanced DI convenience functions
def register_service(
    service_type: type[T],
    factory: ServiceFactory[T] | None = None,
    instance: T | None = None,
    config: dict[str, Any] | None = None,
    is_singleton: bool = True,
) -> RegistrationInfo[T]:
    """Register a service with the enhanced container."""
    return get_container().register_service(service_type, factory, instance, config, is_singleton)


def get_service_typed(service_type: type[T]) -> T:
    """Get a service instance with strong typing."""
    return get_container().get_service_typed(service_type)


@contextmanager
def service_scope(scope_name: str) -> Iterator[ServiceScope]:
    """Create or enter a service scope."""
    with get_container().create_scope(scope_name) as scope:
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
def injectable(
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
async def with_dependency_injection() -> AsyncIterator[DIContainer]:
    """Context manager for service lifecycle."""
    container = get_container()
    try:
        await container.initialize_all_services()
        yield container
    finally:
        await container.shutdown_all_services()
