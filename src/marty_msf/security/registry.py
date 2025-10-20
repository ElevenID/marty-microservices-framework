"""
Security Service Registry for Dependency Injection

This module provides registration functions for security services using interfaces
to avoid circular dependencies between concrete implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.di_container import register_factory
from ..core.services import SecurityService
from .audit import SecurityAuditor
from .factories import (
    SecurityAuditorFactory,
    SecurityManagerFactory,
    SecurityManagerServiceFactory,
)
from .interfaces import (
    ConsolidatedSecurityManager as ConsolidatedSecurityManagerInterface,
)
from .interfaces import (
    ConsolidatedSecurityManagerService as ConsolidatedSecurityManagerServiceInterface,
)
from .interfaces import UnifiedSecurityFramework


def register_security_services(service_name: str = "unknown") -> None:
    """
    Register all security services with the DI container.

    This function uses lazy imports to avoid circular dependencies.
    """
    # Import concrete classes here to avoid circular dependency

    register_factory(
        ConsolidatedSecurityManagerServiceInterface,
        SecurityManagerServiceFactory(),
    )
    register_factory(
        ConsolidatedSecurityManagerInterface,
        SecurityManagerFactory(),
    )
    register_factory(SecurityAuditor, SecurityAuditorFactory(service_name))
