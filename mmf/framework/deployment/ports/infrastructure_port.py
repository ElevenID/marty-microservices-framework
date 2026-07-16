"""
Infrastructure port interface.
"""

from abc import ABC, abstractmethod

from mmf.framework.deployment.domain.models import (
    InfrastructureStack,
    InfrastructureState,
)


class InfrastructurePort(ABC):
    """Abstract base class for infrastructure providers."""

    @abstractmethod
    async def provision(self, stack: InfrastructureStack) -> InfrastructureState:
        """Provision infrastructure stack."""

    @abstractmethod
    async def destroy(self, stack: InfrastructureStack) -> bool:
        """Destroy infrastructure stack."""

    @abstractmethod
    async def get_state(self, stack: InfrastructureStack) -> InfrastructureState:
        """Get infrastructure stack state."""
