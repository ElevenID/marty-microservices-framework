"""
Utility Classes for Platform Layer.

This module provides utility classes like Registry, AtomicCounter,
and TypedSingleton converted to DI-injectable services.
"""

from __future__ import annotations

import logging
import weakref
from collections.abc import Callable
from contextlib import contextmanager
from threading import RLock
from typing import Any, Generic, TypeVar

from mmf_new.core.platform.base_services import BaseService
from mmf_new.core.platform.contracts import IServiceRegistry
from mmf_new.framework.infrastructure.dependency_injection import DIContainer

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Registry(BaseService, IServiceRegistry):
    """
    Type-safe service registry for dependency injection.

    This replaces global variables with a proper registry system that:
    - Maintains type safety with mypy
    - Provides proper lifecycle management
    - Supports both singleton and factory patterns
    - Allows for testing with easy mocking/reset
    """

    def __init__(self, container: DIContainer, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self._services: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._lock = RLock()
        self._initialized_services: dict[str, bool] = {}

    def register(self, name: str, service: Any) -> None:
        """Register a service with the given name."""
        with self._lock:
            self._services[name] = service
            self._initialized_services[name] = True
            logger.debug("Registered service %s", name)

    def register_factory(self, name: str, factory: Callable[[], Any]) -> None:
        """Register a factory function for lazy initialization."""
        with self._lock:
            self._factories[name] = factory
            self._initialized_services[name] = False
            logger.debug("Registered factory for %s", name)

    def get(self, name: str) -> Any:
        """Get a service by name."""
        with self._lock:
            # Return existing instance
            if name in self._services:
                return self._services[name]

            # Create from factory if available
            if name in self._factories:
                instance = self._factories[name]()
                self._services[name] = instance
                self._initialized_services[name] = True
                logger.debug("Created instance of %s from factory", name)
                return instance

            raise ValueError(f"No service registered with name {name}")

    def get_optional(self, name: str) -> Any | None:
        """Get a service by name or None if not registered."""
        try:
            return self.get(name)
        except ValueError:
            return None

    def unregister(self, name: str) -> bool:
        """Unregister a service by name."""
        with self._lock:
            removed = False
            if name in self._services:
                self._services.pop(name)
                removed = True
            if name in self._factories:
                self._factories.pop(name)
                removed = True
            if name in self._initialized_services:
                self._initialized_services.pop(name)
            if removed:
                logger.debug("Unregistered %s", name)
            return removed

    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        with self._lock:
            return name in self._services or name in self._factories

    def list_services(self) -> list[str]:
        """List all registered service names."""
        with self._lock:
            all_names = set(self._services.keys()) | set(self._factories.keys())
            return list(all_names)

    def clear(self) -> None:
        """Clear all registered services."""
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._initialized_services.clear()
            logger.debug("Cleared all registered services")

    @contextmanager
    def temporary_override(self, name: str, service: Any):
        """Temporarily override a service."""
        original_service = self._services.get(name)
        original_factory = self._factories.get(name)
        original_initialized = self._initialized_services.get(name, False)

        try:
            self.register(name, service)
            yield service
        finally:
            with self._lock:
                if original_service is not None:
                    self._services[name] = original_service
                else:
                    self._services.pop(name, None)

                if original_factory is not None:
                    self._factories[name] = original_factory
                else:
                    self._factories.pop(name, None)

                self._initialized_services[name] = original_initialized

    async def _on_initialize(self) -> None:
        """Initialize the registry."""
        logger.info("Registry initialized")

    async def _on_shutdown(self) -> None:
        """Shutdown the registry."""
        self.clear()
        logger.info("Registry shutdown")


class AtomicCounter(BaseService):
    """
    Thread-safe atomic counter to replace global counter variables.

    This provides a properly typed, thread-safe alternative to global
    counter variables used for ID generation.
    """

    def __init__(self, container: DIContainer, initial_value: int = 0, config: dict[str, Any] | None = None):
        super().__init__(container, config)
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

    async def _on_initialize(self) -> None:
        """Initialize the counter."""
        logger.debug("AtomicCounter initialized with value %d", self._value)

    async def _on_shutdown(self) -> None:
        """Shutdown the counter."""
        logger.debug("AtomicCounter shutdown")


class TypedSingleton(BaseService, Generic[T]):
    """
    Service that manages typed singleton instances.

    This provides a pattern for services that need singleton behavior
    but with proper typing and testability via DI container.
    """

    def __init__(self, container: DIContainer, config: dict[str, Any] | None = None):
        super().__init__(container, config)
        self._instances: dict[type[Any], Any] = {}
        self._lock = RLock()

    def get_or_create(self, type_cls: type[T], factory: Callable[[], T] | type[T]) -> T:
        """Get existing instance or create new one using factory."""
        with self._lock:
            if type_cls not in self._instances:
                if isinstance(factory, type):
                    instance = factory()
                else:
                    instance = factory()
                self._instances[type_cls] = instance
            return self._instances[type_cls]

    def clear(self) -> None:
        """Clear all singleton instances."""
        with self._lock:
            self._instances.clear()

    async def _on_initialize(self) -> None:
        """Initialize the singleton manager."""
        logger.debug("TypedSingleton manager initialized")

    async def _on_shutdown(self) -> None:
        """Shutdown the singleton manager."""
        self.clear()
        logger.debug("TypedSingleton manager shutdown")
