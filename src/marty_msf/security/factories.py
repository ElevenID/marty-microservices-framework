"""
Security Service Factory for Dependency Injection

This module provides factory classes for creating security-related services
with proper dependency injection and type safety. Uses interfaces to avoid
circular dependencies.
"""

from __future__ import annotations

from typing import Any

from ..core.di_container import ServiceFactory, get_service
from .audit import SecurityAuditor
from .interfaces import ConsolidatedSecurityManager, ConsolidatedSecurityManagerService


class SecurityManagerServiceFactory(ServiceFactory):
    """Factory for creating ConsolidatedSecurityManagerService instances."""

    def create(self, config: dict[str, Any] | None = None):
        """Create a new ConsolidatedSecurityManagerService instance."""
        service = ConsolidatedSecurityManagerService()
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
