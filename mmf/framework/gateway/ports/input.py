"""
Gateway Input Ports
"""

from abc import ABC, abstractmethod

from ..domain.models import GatewayRequest, GatewayResponse


class RequestHandlerPort(ABC):
    """Port for handling incoming requests."""

    @abstractmethod
    async def handle_request(self, request: GatewayRequest) -> GatewayResponse:
        """Handle an incoming gateway request."""
