"""Delivery Service Port.

This port defines the interface for interacting with the Delivery Board Service.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class DeliveryRequest:
    """Request to create a delivery."""

    order_id: str
    address: str
    items: list[dict]
    priority: str = "standard"


class DeliveryServicePort(ABC):
    """Abstract interface for delivery service operations."""

    @abstractmethod
    async def create_delivery(self, request: DeliveryRequest) -> Optional[str]:
        """Create a delivery for an order.

        Args:
            request: The delivery request details

        Returns:
            The ID of the created delivery, or None if creation failed
        """
        pass
