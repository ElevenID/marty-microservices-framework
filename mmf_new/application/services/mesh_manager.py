"""
Mesh Manager Service

Service for managing service mesh lifecycle and security policies.
"""

import logging
from typing import Any

from mmf_new.core.security.domain.models.service_mesh import (
    PolicySyncResult,
    ServiceMeshPolicy,
)
from mmf_new.core.security.ports.service_mesh import IServiceMeshManager
from mmf_new.framework.mesh.ports.lifecycle import MeshLifecyclePort

logger = logging.getLogger(__name__)


class MeshManager:
    """
    Service for managing service mesh operations.

    This service orchestrates lifecycle management and security policy enforcement
    for the service mesh.
    """

    def __init__(self, lifecycle_port: MeshLifecyclePort, security_port: IServiceMeshManager):
        self.lifecycle = lifecycle_port
        self.security = security_port

    async def deploy_mesh(
        self, namespace: str = "istio-system", config: dict[str, Any] | None = None
    ) -> bool:
        """
        Deploy the service mesh.

        Args:
            namespace: Target namespace.
            config: Deployment configuration.

        Returns:
            bool: True if successful.
        """
        logger.info("Deploying service mesh to namespace %s", namespace)

        if not await self.lifecycle.verify_prerequisites():
            logger.error("Prerequisites not met for mesh deployment")
            return False

        if await self.lifecycle.check_installation():
            logger.info("Service mesh CLI tools are installed")
        else:
            logger.warning("Service mesh CLI tools not found or not working")
            # We might want to fail here or try to continue if deployment handles installation
            # But deploy() usually assumes CLI is present.
            return False

        return await self.lifecycle.deploy(namespace, config)

    async def get_mesh_status(self) -> dict[str, Any]:
        """
        Get the current status of the service mesh.

        Returns:
            dict: Status information.
        """
        return await self.lifecycle.get_status()

    async def apply_security_policy(self, policy: ServiceMeshPolicy) -> bool:
        """
        Apply a security policy to the mesh.

        Args:
            policy: The policy to apply.

        Returns:
            bool: True if successful.
        """
        logger.info("Applying security policy: %s", policy.name)
        return await self.security.apply_policy(policy)

    async def apply_security_policies(self, policies: list[ServiceMeshPolicy]) -> PolicySyncResult:
        """
        Apply multiple security policies.

        Args:
            policies: List of policies to apply.

        Returns:
            PolicySyncResult: Result of the operation.
        """
        logger.info("Applying %d security policies", len(policies))
        return await self.security.apply_policies(policies)

    async def remove_security_policy(self, policy_name: str, namespace: str) -> bool:
        """
        Remove a security policy.

        Args:
            policy_name: Name of the policy.
            namespace: Namespace of the policy.

        Returns:
            bool: True if successful.
        """
        logger.info("Removing security policy: %s", policy_name)
        return await self.security.remove_policy(policy_name, namespace)
