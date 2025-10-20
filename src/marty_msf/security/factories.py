"""
Security Service Factory for Dependency Injection

This module provides factory classes for creating security-related services
with proper dependency injection and type safety. Uses interfaces to avoid
circular dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..core.di_container import (
    ServiceFactory,
    get_service,
    get_service_optional,
    register_instance,
)
from .audit import SecurityAuditor
from .config import RateLimitConfig
from .interfaces import ConsolidatedSecurityManager, ConsolidatedSecurityManagerService
from .rate_limiting import RateLimiter


# Use DI container to store class references instead of globals
class _SecurityManagerServiceClassRegistry:
    """Registry for security manager service class."""
    pass


def set_security_manager_service_class(
    service_cls: type[ConsolidatedSecurityManagerService],
) -> None:
    """Set the concrete class used to create security manager services."""
    register_instance(_SecurityManagerServiceClassRegistry, service_cls)


def get_security_manager_service_class() -> type[ConsolidatedSecurityManagerService]:
    """Return the configured security manager service class."""
    service_cls = get_service_optional(_SecurityManagerServiceClassRegistry)
    if service_cls is None:
        raise RuntimeError("Security manager service class not registered")
    return service_cls  # type: ignore[return-value]


class SecurityManagerServiceFactory(ServiceFactory):
    """Factory for creating ConsolidatedSecurityManagerService instances."""

    def __init__(
        self, service_cls: type[ConsolidatedSecurityManagerService] | None = None
    ):
        self._service_cls = service_cls

    def create(self, config: dict[str, Any] | None = None):
        """Create a new ConsolidatedSecurityManagerService instance."""

        service_cls = self._service_cls or get_security_manager_service_class()
        service = service_cls()
        if config:
            service.configure(config)
        return service

    def get_service_type(self):
        """Get the service type this factory creates."""
        return ConsolidatedSecurityManagerService


class SecurityManagerFactory(ServiceFactory):
    """Factory for creating ConsolidatedSecurityManager instances."""

    def create(self, config: dict[str, Any] | None = None):
        """Create a new ConsolidatedSecurityManager instance."""

        service = get_service(ConsolidatedSecurityManagerService)
        if config:
            service.configure(config)
        return service.get_security_manager()

    def get_service_type(self):
        """Get the service type this factory creates."""
        return ConsolidatedSecurityManager


class SecurityAuditorFactory(ServiceFactory):
    """Factory for creating SecurityAuditor instances."""

    def __init__(self, service_name: str = "unknown") -> None:
        """Initialize the factory with a default service name."""
        self._service_name = service_name

    def create(self, config: dict[str, Any] | None = None):
        """Create a new SecurityAuditor instance."""

        service_name = self._service_name
        if config and "service_name" in config:
            service_name = config["service_name"]

        auditor = SecurityAuditor(service_name)
        if config:
            # Apply any additional configuration to the auditor
            pass
        return auditor

    def get_service_type(self):
        """Get the service type this factory creates."""

        return SecurityAuditor


class RateLimiterFactory(ServiceFactory):
    """Factory for creating RateLimiter instances."""

    def create(self, config: dict[str, Any] | None = None):
        """Create a new RateLimiter instance."""

        # Use provided config or create default one
        if config:
            rate_limit_config = RateLimitConfig(**config)
        else:
            rate_limit_config = RateLimitConfig()

        return RateLimiter(rate_limit_config)

    def get_service_type(self):
        """Get the service type this factory creates."""
        return RateLimiter
