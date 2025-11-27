"""
Gateway Output Ports
"""

from abc import ABC, abstractmethod

from ..domain.models import GatewayRequest, GatewayResponse, UpstreamServer


class UpstreamClientPort(ABC):
    """Port for communicating with upstream services."""

    @abstractmethod
    async def send_request(
        self, server: UpstreamServer, request: GatewayRequest
    ) -> GatewayResponse:
        """Send request to upstream server."""


class ServiceRegistryPort(ABC):
    """Port for service discovery."""

    @abstractmethod
    async def get_service_instances(self, service_name: str) -> list[UpstreamServer]:
        """Get available instances for a service."""


class RateLimitStoragePort(ABC):
    """Port for rate limit storage."""

    @abstractmethod
    async def get_usage(self, key: str) -> int:
        """Get current usage for a key."""

    @abstractmethod
    async def increment_usage(self, key: str, amount: int = 1, ttl: int = 60) -> int:
        """Increment usage and return new value."""
