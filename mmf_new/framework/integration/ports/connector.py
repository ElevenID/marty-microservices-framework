"""
Integration Connector Ports
"""

from abc import ABC, abstractmethod

from mmf_new.framework.integration.domain.models import (
    IntegrationRequest,
    IntegrationResponse,
)


class ExternalSystemPort(ABC):
    """Port for communicating with external systems."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to external system."""

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from external system."""

    @abstractmethod
    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute request against external system."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check health of external system."""
