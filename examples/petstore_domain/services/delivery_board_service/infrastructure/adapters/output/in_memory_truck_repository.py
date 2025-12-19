"""In-Memory Truck Repository Adapter.

This is a driven (output) adapter that implements the TruckRepositoryPort
interface using an in-memory dictionary.
"""

from typing import Optional

from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Truck,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    TruckId,
)


class InMemoryTruckRepository(TruckRepositoryPort):
    """In-memory implementation of the truck repository."""

    def __init__(self) -> None:
        """Initialize the in-memory storage."""
        self._storage: dict[str, Truck] = {}

    def save(self, truck: Truck) -> None:
        """Persist a truck entity."""
        self._storage[str(truck.id)] = truck

    def find_by_id(self, truck_id: TruckId) -> Optional[Truck]:
        """Find a truck by its unique identifier."""
        return self._storage.get(str(truck_id))

    def find_all(self) -> list[Truck]:
        """Retrieve all trucks."""
        return list(self._storage.values())

    def find_available(self) -> list[Truck]:
        """Retrieve all available trucks (with capacity)."""
        return [truck for truck in self._storage.values() if truck.is_available()]

    def update(self, truck: Truck) -> None:
        """Update an existing truck."""
        self._storage[str(truck.id)] = truck

    def clear(self) -> None:
        """Clear all trucks from memory."""
        self._storage.clear()
