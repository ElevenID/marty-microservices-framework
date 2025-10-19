"""
Security Service Factory for Dependency Injection

This module provides factory classes for creating security-related services
with proper dependency injection and type safety.
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.di_container import ServiceFactory, get_service, register_factory
from .audit import SecurityAuditor
from .manager import ConsolidatedSecurityManager, ConsolidatedSecurityManagerService


class SecurityManagerServiceFactory(ServiceFactory[ConsolidatedSecurityManagerService]):
    """Factory for creating ConsolidatedSecurityManagerService instances."""

    def create(self, config: dict[str, Any] | None = None) -> ConsolidatedSecurityManagerService:
        """Create a new ConsolidatedSecurityManagerService instance."""
        service = ConsolidatedSecurityManagerService()
        if config:
            service.configure(config)
        return service

    def get_service_type(self) -> type[ConsolidatedSecurityManagerService]:
        """Get the service type this factory creates."""
        return ConsolidatedSecurityManagerService


class SecurityManagerFactory(ServiceFactory[ConsolidatedSecurityManager]):
    """Factory for creating ConsolidatedSecurityManager instances."""

    def create(self, config: dict[str, Any] | None = None) -> ConsolidatedSecurityManager:
        """Create a new ConsolidatedSecurityManager instance."""

        # Get or create the service instance
        service = get_service(ConsolidatedSecurityManagerService)
        if config:
            service.configure(config)
        return service.get_security_manager()

    def get_service_type(self) -> type[ConsolidatedSecurityManager]:
        """Get the service type this factory creates."""
        return ConsolidatedSecurityManager


class SecurityAuditorFactory(ServiceFactory[SecurityAuditor]):
    """Factory for creating SecurityAuditor instances."""

    def __init__(self, service_name: str = "unknown") -> None:
        """Initialize the factory with a default service name."""
        self._service_name = service_name

    def create(self, config: dict[str, Any] | None = None) -> SecurityAuditor:
        """Create a new SecurityAuditor instance."""
        service_name = self._service_name
        if config and "service_name" in config:
            service_name = config["service_name"]

        auditor = SecurityAuditor(service_name)
        if config:
            # Apply any additional configuration to the auditor
            pass
        return auditor

    def get_service_type(self) -> type[SecurityAuditor]:
        """Get the service type this factory creates."""
        return SecurityAuditor


# Convenience functions for registering security services
def register_security_services(service_name: str = "unknown") -> None:
    """Register all security services with the DI container."""

    register_factory(ConsolidatedSecurityManagerService, SecurityManagerServiceFactory())
    register_factory(ConsolidatedSecurityManager, SecurityManagerFactory())
    register_factory(SecurityAuditor, SecurityAuditorFactory(service_name))
