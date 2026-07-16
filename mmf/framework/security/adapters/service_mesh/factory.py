"""
Service Mesh Factory

Factory for creating service mesh components.
"""

from __future__ import annotations

from mmf.core.security.domain.config import ServiceMeshConfig
from mmf.core.security.ports.service_mesh import IServiceMeshManager
from mmf.framework.security.adapters.service_mesh.istio_mesh_manager import (
    IstioMeshManager,
)


class ServiceMeshFactory:
    """Factory for service mesh components."""

    @staticmethod
    def create_manager(config: ServiceMeshConfig) -> IServiceMeshManager | None:
        """Create service mesh manager if enabled."""
        if config.enabled:
            return IstioMeshManager(config)
        return None
