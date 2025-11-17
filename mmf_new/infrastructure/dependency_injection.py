"""
Dependency Injection Container for MMF Framework

This module provides a strongly typed dependency injection container to replace
global variables throughout the framework. It ensures proper lifecycle management,
thread safety, and strong typing support with MyPy.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Generic, Optional, TypeVar, Union, cast, overload

from typing_extensions import Protocol

from .cache import CacheBackend, CacheConfig, SerializationFormat, create_cache_manager

T = TypeVar("T")
ServiceType = TypeVar("ServiceType")
_MISSING = object()  # Sentinel value for missing defaults


class ServiceProtocol(Protocol):
    """Protocol for services that can be managed by the DI container."""

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the service with the given configuration."""
        ...

    def shutdown(self) -> None:
        """Clean shutdown of the service."""
        ...


class ServiceFactory(Generic[T], ABC):
    """Abstract base class for service factories."""

    @abstractmethod
    def create(self, config: dict[str, Any] | None = None) -> T:
        """Create a new instance of the service."""
        ...

    @abstractmethod
    def get_service_type(self) -> type[T]:
        """Get the type of service this factory creates."""
        ...


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
    def get(self, service_type: type[T]) -> T: ...

    @overload
    def get(self, service_type: type[T], default: object = _MISSING) -> T | None: ...

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
                    except Exception:
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
                    except Exception:
                        # Log error but don't re-raise during cleanup
                        pass

            self._services.clear()
            self._factories.clear()
            self._configurations.clear()

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
                            except Exception:
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
