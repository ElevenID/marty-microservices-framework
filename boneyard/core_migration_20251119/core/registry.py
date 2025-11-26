"""
Strongly-typed dependency injection and service registry system.

This module provides a type-safe replacement for global variables using
dependency injection principles with proper mypy typing support.
"""

from __future__ import annotations

import logging
import weakref
from collections.abc import Callable
from contextlib import contextmanager
from threading import RLock
from typing import Any, Generic, Optional, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceRegistry(Generic[T]):
    """
    Type-safe service registry for dependency injection.

    This replaces global variables with a proper registry system that:
    - Maintains type safety with mypy
    - Provides proper lifecycle management
    - Supports both singleton and factory patterns
    - Allows for testing with easy mocking/reset
    """

    def __init__(self) -> None:
        self._services: dict[type[T], T] = {}
        self._factories: dict[type[T], Callable[[], T]] = {}
        self._lock = RLock()
        self._initialized: dict[type[T], bool] = {}

    def register_singleton(self, service_type: type[T], instance: T) -> None:
        """Register a singleton instance for a service type."""
        with self._lock:
            self._services[service_type] = instance
            self._initialized[service_type] = True
            logger.debug("Registered singleton %s", service_type.__name__)

    def register_factory(self, service_type: type[T], factory: Callable[[], T]) -> None:
        """Register a factory function for lazy initialization."""
        with self._lock:
            self._factories[service_type] = factory
            self._initialized[service_type] = False
            logger.debug("Registered factory for %s", service_type.__name__)

    def get(self, service_type: type[T]) -> T:
        """Get a service instance, creating it if necessary."""
        with self._lock:
            # Return existing singleton
            if service_type in self._services:
                return self._services[service_type]

            # Create from factory if available
            if service_type in self._factories:
                instance = self._factories[service_type]()
                self._services[service_type] = instance
                self._initialized[service_type] = True
                logger.debug("Created instance of %s from factory", service_type.__name__)
                return instance

            raise ValueError(f"No service registered for type {service_type.__name__}")

    def get_optional(self, service_type: type[T]) -> T | None:
        """Get a service instance or None if not registered."""
        try:
            return self.get(service_type)
        except ValueError:
            return None

    def is_registered(self, service_type: type[T]) -> bool:
        """Check if a service type is registered."""
        with self._lock:
            return service_type in self._services or service_type in self._factories

    def is_initialized(self, service_type: type[T]) -> bool:
        """Check if a service has been initialized."""
        with self._lock:
            return self._initialized.get(service_type, False)

    def unregister(self, service_type: type[T]) -> None:
        """Unregister a service (useful for testing)."""
        with self._lock:
            self._services.pop(service_type, None)
            self._factories.pop(service_type, None)
            self._initialized.pop(service_type, None)
            logger.debug("Unregistered %s", service_type.__name__)

    def clear(self) -> None:
        """Clear all registered services (useful for testing)."""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._initialized.clear()
            logger.debug("Cleared all registered services")

    @contextmanager
    def temporary_override(self, service_type: type[T], instance: T):
        """Temporarily override a service for testing or specific contexts."""
        original_service = self._services.get(service_type)
        original_factory = self._factories.get(service_type)
        original_initialized = self._initialized.get(service_type, False)

        try:
            self.register_singleton(service_type, instance)
            yield instance
        finally:
            with self._lock:
                if original_service is not None:
                    self._services[service_type] = original_service
                else:
                    self._services.pop(service_type, None)

                if original_factory is not None:
                    self._factories[service_type] = original_factory
                else:
                    self._factories.pop(service_type, None)

                self._initialized[service_type] = original_initialized


# Global registry instance - this is the only global we'll keep
_global_registry: ServiceRegistry[Any] = ServiceRegistry()


def get_service(service_type: type[T]) -> T:
    """Get a service from the global registry."""
    return cast(T, _global_registry.get(service_type))


def get_service_optional(service_type: type[T]) -> T | None:
    """Get a service from the global registry or None if not registered."""
    return cast(T | None, _global_registry.get_optional(service_type))


def register_singleton(service_type: type[T], instance: T) -> None:
    """Register a singleton in the global registry."""
    _global_registry.register_singleton(service_type, instance)


def register_factory(service_type: type[T], factory: Callable[[], T]) -> None:
    """Register a factory in the global registry."""
    _global_registry.register_factory(service_type, factory)


def is_service_registered(service_type: type[T]) -> bool:
    """Check if a service is registered in the global registry."""
    return _global_registry.is_registered(service_type)


def unregister_service(service_type: type[T]) -> None:
    """Unregister a service from the global registry."""
    _global_registry.unregister(service_type)


def clear_registry() -> None:
    """Clear the global registry (useful for testing)."""
    _global_registry.clear()


@contextmanager
def temporary_service_override(service_type: type[T], instance: T):
    """Temporarily override a service in the global registry."""
    with _global_registry.temporary_override(service_type, instance):
        yield instance


class AtomicCounter:
    """
    Thread-safe atomic counter to replace global counter variables.

    This provides a properly typed, thread-safe alternative to global
    counter variables used for ID generation.
    """

    def __init__(self, initial_value: int = 0) -> None:
        self._value = initial_value
        self._lock = RLock()

    def increment(self) -> int:
        """Increment and return the new value."""
        with self._lock:
            self._value += 1
            return self._value

    def get(self) -> int:
        """Get the current value."""
        with self._lock:
            return self._value

    def set(self, value: int) -> None:
        """Set the counter value."""
        with self._lock:
            self._value = value

    def reset(self) -> None:
        """Reset the counter to 0."""
        with self._lock:
            self._value = 0


class TypedSingleton(Generic[T]):
    """
    Base class for creating typed singleton services.

    This provides a pattern for services that need singleton behavior
    but with proper typing and testability.
    """

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._instances: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        cls._lock = RLock()

    def __new__(cls):
        if not hasattr(cls, "_instances"):
            cls._instances = weakref.WeakValueDictionary()
            cls._lock = RLock()

        with cls._lock:
            if cls not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[cls] = instance
            return cls._instances[cls]

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        if hasattr(cls, "_instances") and hasattr(cls, "_lock"):
            with cls._lock:
                cls._instances.pop(cls, None)

    @classmethod
    def get_instance(cls):
        """Get the current instance if it exists."""
        if hasattr(cls, "_instances") and hasattr(cls, "_lock"):
            with cls._lock:
                return cls._instances.get(cls)
        return None


def inject(service_type: type[T]) -> Callable[[Callable], Callable]:
    """
    Decorator for dependency injection.

    Automatically injects a service as the first argument to a function.
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            service = get_service(service_type)
            return func(service, *args, **kwargs)

        return wrapper

    return decorator


# Type aliases for common service patterns
ConfigService = TypeVar("ConfigService")
ObservabilityService = TypeVar("ObservabilityService")
SecurityService = TypeVar("SecurityService")
MessagingService = TypeVar("MessagingService")
