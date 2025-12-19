"""
Core service registry and thread-safe utilities.

This module provides a thread-safe dependency injection container and
atomic counters to replace global variables.
"""

import threading
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class AtomicCounter:
    """
    Thread-safe atomic counter.

    Replaces global integer counters.
    """

    def __init__(self, initial_value: int = 0) -> None:
        self._value = initial_value
        self._lock = threading.Lock()

    def increment(self) -> int:
        """Increment the counter and return the new value."""
        with self._lock:
            self._value += 1
            return self._value

    def get(self) -> int:
        """Get the current value."""
        with self._lock:
            return self._value

    def reset(self, value: int = 0) -> None:
        """Reset the counter to a specific value."""
        with self._lock:
            self._value = value


class ServiceRegistry:
    """
    Thread-safe service registry for dependency injection.

    Replaces global service instances.
    """

    _instance = None
    _lock = threading.RLock()

    def __init__(self) -> None:
        self._services: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], Any] = {}

    @classmethod
    def get_instance(cls) -> "ServiceRegistry":
        """Get the singleton registry instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, service_type: type[T], instance: T) -> None:
        """Register a service instance."""
        with self._lock:
            self._services[service_type] = instance

    def register_factory(self, service_type: type[T], factory: Any) -> None:
        """Register a service factory."""
        with self._lock:
            self._factories[service_type] = factory

    def get(self, service_type: type[T]) -> T:
        """Get a registered service instance."""
        with self._lock:
            if service_type in self._services:
                return self._services[service_type]

            if service_type in self._factories:
                instance = self._factories[service_type]()
                self._services[service_type] = instance
                return instance

            raise KeyError(f"Service {service_type.__name__} not registered")

    def clear(self) -> None:
        """Clear all registered services."""
        with self._lock:
            self._services.clear()
            self._factories.clear()


# Global helper functions for easier access


def register_singleton(service_type: type[T], instance: T) -> None:
    """Register a singleton service instance."""
    ServiceRegistry.get_instance().register(service_type, instance)


def get_service(service_type: type[T]) -> T:
    """Get a registered service instance."""
    return ServiceRegistry.get_instance().get(service_type)


def clear_registry() -> None:
    """Clear the service registry (useful for testing)."""
    ServiceRegistry.get_instance().clear()
