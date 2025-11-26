"""
Deployment port interface.
"""

from abc import ABC, abstractmethod
from typing import Any

from mmf_new.framework.deployment.domain.models import Deployment


class DeploymentPort(ABC):
    """Abstract base class for deployment providers."""

    @abstractmethod
    async def deploy(self, deployment: Deployment) -> bool:
        """Deploy service to target environment."""

    @abstractmethod
    async def rollback(self, deployment: Deployment) -> bool:
        """Rollback deployment to previous version."""

    @abstractmethod
    async def scale(self, deployment: Deployment, replicas: int) -> bool:
        """Scale deployment."""

    @abstractmethod
    async def get_status(self, deployment: Deployment) -> dict[str, Any]:
        """Get deployment status."""
