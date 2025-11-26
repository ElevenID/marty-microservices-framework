from __future__ import annotations

"""
Factory helpers for constructing discovery clients.
"""

from .clients import (
    ClientSideDiscovery,
    HybridDiscovery,
    ServerSideDiscovery,
    ServiceDiscoveryClient,
    ServiceMeshDiscovery,
)
from .config import DiscoveryConfig, DiscoveryPattern


def create_discovery_client(
    pattern: DiscoveryPattern, config: DiscoveryConfig, **kwargs
) -> ServiceDiscoveryClient:
    """Factory function to create a discovery client based on the pattern."""
    if pattern == DiscoveryPattern.CLIENT_SIDE:
        registry = kwargs.get("registry")
        if not registry:
            raise ValueError("Registry required for client-side discovery")
        return ClientSideDiscovery(registry, config)

    if pattern == DiscoveryPattern.SERVER_SIDE:
        discovery_url = kwargs.get("discovery_service_url")
        if not discovery_url:
            raise ValueError("Discovery service URL required for server-side discovery")
        return ServerSideDiscovery(discovery_url, config)

    if pattern == DiscoveryPattern.HYBRID:
        client_side = kwargs.get("client_side")
        server_side = kwargs.get("server_side")
        if not client_side or not server_side:
            raise ValueError(
                "Both client-side and server-side clients required for hybrid discovery"
            )
        return HybridDiscovery(client_side, server_side, config)

    if pattern == DiscoveryPattern.SERVICE_MESH:
        mesh_config = kwargs.get("mesh_config", {})
        return ServiceMeshDiscovery(mesh_config, config)

    raise ValueError(f"Unsupported discovery pattern: {pattern}")
