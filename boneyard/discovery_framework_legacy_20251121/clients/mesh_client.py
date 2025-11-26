from __future__ import annotations

"""
Stub Kubernetes client used by the service mesh discovery adapter.

This remains a lightweight adapter so that production deployments can swap in a
real Kubernetes client without pulling in heavy dependencies at import time.
"""

import logging

logger = logging.getLogger(__name__)


class MockKubernetesClient:
    """
    Mock Kubernetes client for service mesh integration.

    WARNING: This is a stub implementation that always returns empty results.
    Service mesh discovery will silently behave as "no instances found" until
    a real Kubernetes client implementation is provided. Set
    `allow_stub=True` in `mesh_config` only for local testing when you
    intentionally want this behaviour.
    """

    def __init__(self, mesh_config: dict):
        self.mesh_config = mesh_config
        self._warn_about_stub = True

    async def get_service_endpoints(self, service_name: str, namespace: str) -> list:
        """
        Get service endpoints from Kubernetes.

        WARNING: This mock implementation always returns an empty list.
        Service mesh callers will behave as if no service instances were found.
        """
        if self._warn_about_stub:
            logger.warning(
                "MockKubernetesClient is a stub implementation. "
                "Service mesh discovery for '%s' in namespace '%s' will return no instances. "
                "Replace with real Kubernetes client for production use.",
                service_name,
                namespace,
            )
            self._warn_about_stub = False

        logger.debug(
            "MockKubernetesClient: Querying service mesh for service: %s in namespace: %s",
            service_name,
            namespace,
        )
        return []
