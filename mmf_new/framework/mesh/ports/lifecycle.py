"""
Mesh Lifecycle Port

Interface for service mesh lifecycle management functionality.
"""

from abc import ABC, abstractmethod
from typing import Any

class MeshLifecyclePort(ABC):
    """Interface for service mesh lifecycle operations."""

    @abstractmethod
    async def check_installation(self) -> bool:
        """
        Check if the service mesh CLI tools are installed and available.

        Returns:
            bool: True if installed, False otherwise.
        """

    @abstractmethod
    async def deploy(self, namespace: str = "istio-system", config: dict[str, Any] | None = None) -> bool:
        """
        Deploy the service mesh to the cluster.

        Args:
            namespace: Kubernetes namespace to deploy to.
            config: Optional configuration for the deployment.

        Returns:
            bool: True if deployment was successful.
        """

    @abstractmethod
    async def get_status(self) -> dict[str, Any]:
        """
        Get the current status of the service mesh.

        Returns:
            Dict[str, Any]: Status information.
        """

    @abstractmethod
    async def verify_prerequisites(self) -> bool:
        """
        Verify that the environment meets the prerequisites for deployment.

        Returns:
            bool: True if prerequisites are met.
        """

    @abstractmethod
    async def generate_deployment_script(self, service_name: str, config: dict[str, Any] | None = None) -> str:
        """
        Generate a deployment script for the service mesh.

        Args:
            service_name: Name of the service.
            config: Optional configuration.

        Returns:
            str: The generated deployment script.
        """
