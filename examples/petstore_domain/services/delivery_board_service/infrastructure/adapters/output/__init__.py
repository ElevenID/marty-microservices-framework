"""Driven adapters (Secondary/Output adapters) for Delivery Board Service."""

from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.output.in_memory_delivery_repository import (
    InMemoryDeliveryRepository,
)
from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.output.in_memory_truck_repository import (
    InMemoryTruckRepository,
)

__all__ = ["InMemoryDeliveryRepository", "InMemoryTruckRepository"]
