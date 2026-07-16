"""
Service Mesh Port

Interface for service mesh management functionality.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..domain.models.service_mesh import (
    NetworkSegment,
    PolicySyncResult,
    ServiceMeshMetrics,
    ServiceMeshPolicy,
    ServiceMeshStatus,
)


class IServiceMeshManager(ABC):
    """Interface for service mesh management implementations."""

    @abstractmethod
    async def apply_policy(self, policy: ServiceMeshPolicy) -> bool:
        """
        Apply a security policy to the service mesh.

        Args:
            policy: Service mesh policy to apply

        Returns:
            True if policy was applied successfully
        """
        pass

    @abstractmethod
    async def apply_policies(self, policies: list[ServiceMeshPolicy]) -> PolicySyncResult:
        """
        Apply multiple security policies to the service mesh.

        Args:
            policies: List of policies to apply

        Returns:
            PolicySyncResult with application results
        """
        pass

    @abstractmethod
    async def remove_policy(self, policy_name: str, namespace: str) -> bool:
        """
        Remove a policy from the service mesh.

        Args:
            policy_name: Name of policy to remove
            namespace: Kubernetes namespace

        Returns:
            True if removal was successful
        """
        pass

    @abstractmethod
    async def get_policy(self, policy_name: str, namespace: str) -> ServiceMeshPolicy | None:
        """
        Get a policy from the service mesh.

        Args:
            policy_name: Name of policy to retrieve
            namespace: Kubernetes namespace

        Returns:
            ServiceMeshPolicy if found, None otherwise
        """
        pass

    @abstractmethod
    async def list_policies(self, namespace: str | None = None) -> list[ServiceMeshPolicy]:
        """
        List all policies in the service mesh.

        Args:
            namespace: Kubernetes namespace to filter by (None for all)

        Returns:
            List of ServiceMeshPolicy objects
        """
        pass

    @abstractmethod
    async def enforce_mtls(
        self,
        namespace: str,
        services: list[str] | None = None,
        strict_mode: bool = True,
    ) -> bool:
        """
        Enforce mTLS for services.

        Args:
            namespace: Kubernetes namespace
            services: List of services (None for all services in namespace)
            strict_mode: Use STRICT mTLS mode if True, PERMISSIVE if False

        Returns:
            True if mTLS enforcement was successful
        """
        pass

    @abstractmethod
    async def create_network_segment(self, segment: NetworkSegment) -> PolicySyncResult:
        """
        Create a network segment with associated policies.

        Args:
            segment: Network segment definition

        Returns:
            PolicySyncResult with creation results
        """
        pass

    @abstractmethod
    async def sync_authorization_policies(
        self,
        app_policies: list[dict[str, Any]],
    ) -> PolicySyncResult:
        """
        Sync application-level authorization policies to service mesh.

        Args:
            app_policies: List of application authorization policies

        Returns:
            PolicySyncResult with sync results
        """
        pass

    @abstractmethod
    async def get_mesh_status(self) -> ServiceMeshStatus:
        """
        Get service mesh status information.

        Returns:
            ServiceMeshStatus with current mesh state
        """
        pass

    @abstractmethod
    async def get_metrics(self) -> ServiceMeshMetrics:
        """
        Get service mesh metrics.

        Returns:
            ServiceMeshMetrics with current statistics
        """
        pass

    @abstractmethod
    async def supports_feature(self, feature: str) -> bool:
        """
        Check if service mesh supports a specific feature.

        Args:
            feature: Feature name to check

        Returns:
            True if feature is supported
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if service mesh is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass
