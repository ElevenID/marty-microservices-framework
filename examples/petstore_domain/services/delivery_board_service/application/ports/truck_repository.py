"""Truck Repository Port (Interface).

This is an output port defining how the application layer expects to
interact with truck persistence.
"""

from abc import ABC, abstractmethod
from typing import Optional

from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Truck,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    TruckId,
)


class TruckRepositoryPort(ABC):
    """Abstract interface for truck persistence operations."""

    @abstractmethod
    def save(self, truck: Truck) -> None:
        """Persist a truck entity.

        Args:
            truck: The truck entity to save
        """
        pass

    @abstractmethod
    def find_by_id(self, truck_id: TruckId) -> Optional[Truck]:
        """Find a truck by its unique identifier.

        Args:
            truck_id: The truck's unique identifier

        Returns:
            The truck if found, None otherwise
        """
        pass

    @abstractmethod
    def find_all(self) -> list[Truck]:
        """Retrieve all trucks.

        Returns:
            List of all truck entities
        """
        pass

    @abstractmethod
    def find_available(self) -> list[Truck]:
        """Retrieve all available trucks (with capacity).

        Returns:
            List of trucks with available capacity
        """
        pass

    @abstractmethod
    def update(self, truck: Truck) -> None:
        """Update an existing truck.

        Args:
            truck: The truck entity to update
        """
        pass
