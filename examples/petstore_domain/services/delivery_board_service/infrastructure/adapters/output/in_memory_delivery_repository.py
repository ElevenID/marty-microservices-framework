"""In-Memory Delivery Repository Adapter.

This is a driven (output) adapter that implements the DeliveryRepositoryPort
interface using an in-memory dictionary.
"""

from typing import Optional

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Delivery,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
)


class InMemoryDeliveryRepository(DeliveryRepositoryPort):
    """In-memory implementation of the delivery repository."""

    def __init__(self) -> None:
        """Initialize the in-memory storage."""
        self._storage: dict[str, Delivery] = {}

    def save(self, delivery: Delivery) -> None:
        """Persist a delivery entity."""
        self._storage[str(delivery.id)] = delivery

    def find_by_id(self, delivery_id: DeliveryId) -> Optional[Delivery]:
        """Find a delivery by its unique identifier."""
        return self._storage.get(str(delivery_id))

    def find_all(
        self, *, limit: int | None = None, offset: int = 0
    ) -> tuple[list[Delivery], int]:
        """Retrieve all deliveries with optional pagination.

        Args:
            limit: Maximum number of deliveries to return (None for all)
            offset: Number of deliveries to skip

        Returns:
            Tuple of (list of delivery entities, total count)
        """
        all_deliveries = list(self._storage.values())
        total_count = len(all_deliveries)

        # Apply pagination
        if offset:
            all_deliveries = all_deliveries[offset:]
        if limit is not None:
            all_deliveries = all_deliveries[:limit]

        return all_deliveries, total_count

    def update(self, delivery: Delivery) -> None:
        """Update an existing delivery."""
        self._storage[str(delivery.id)] = delivery

    def clear(self) -> None:
        """Clear all deliveries from memory."""
        self._storage.clear()
