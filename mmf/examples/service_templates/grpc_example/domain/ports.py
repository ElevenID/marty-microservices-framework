from abc import ABC, abstractmethod
from typing import Optional

from mmf.examples.service_templates.grpc_example.domain.models import Order


class OrderRepository(ABC):
    @abstractmethod
    async def save(self, order: Order) -> Order:
        """Save an order."""

    @abstractmethod
    async def get_by_id(self, order_id: str) -> Order | None:
        """Get an order by ID."""


class InventoryServicePort(ABC):
    @abstractmethod
    async def check_availability(self, product_id: str, quantity: int) -> bool:
        """Check if product is available."""
