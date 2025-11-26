"""
Service Mesh Framework Module
Provides Python integration for service mesh deployment capabilities
and real-time security policy enforcement

DEPRECATION NOTICE: The old ServiceMeshManager has been deprecated and removed.
All functionality is now provided by EnhancedServiceMeshManager which includes
real-time security policy enforcement and unified security framework integration.
"""

import logging
from typing import Any, Optional

from .enhanced_manager import EnhancedServiceMeshManager

logger = logging.getLogger(__name__)


def create_service_mesh_manager(
    service_mesh_type: str = "istio",
    config: dict[str, Any] | None = None,
    security_manager: Any | None = None,
) -> EnhancedServiceMeshManager:
    """
    Factory function to create a service mesh manager

    DEPRECATION NOTICE: This function now returns an EnhancedServiceMeshManager
    instead of the old ServiceMeshManager. The API remains compatible.

    Args:
        service_mesh_type: Type of service mesh (istio, linkerd)
        config: Service mesh configuration
        security_manager: Unified security framework manager for policy enforcement

    Returns:
        EnhancedServiceMeshManager instance
    """
    logger.warning(
        "create_service_mesh_manager is deprecated. "
        "Use create_enhanced_service_mesh_manager instead."
    )
    return EnhancedServiceMeshManager(
        service_mesh_type=service_mesh_type, config=config, security_manager=security_manager
    )


def create_enhanced_service_mesh_manager(
    service_mesh_type: str = "istio",
    config: dict[str, Any] | None = None,
    security_manager: Any | None = None,
) -> EnhancedServiceMeshManager:
    """
    Factory function to create an EnhancedServiceMeshManager instance with security integration

    Args:
        service_mesh_type: Type of service mesh (istio, linkerd)
        config: Service mesh configuration
        security_manager: Unified security framework manager for policy enforcement

    Returns:
        EnhancedServiceMeshManager instance
    """
    return EnhancedServiceMeshManager(
        service_mesh_type=service_mesh_type, config=config, security_manager=security_manager
    )


# Export unified service mesh manager
__all__ = [
    "EnhancedServiceMeshManager",
    "create_service_mesh_manager",  # Deprecated, but kept for compatibility
    "create_enhanced_service_mesh_manager",
]
