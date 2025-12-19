"""Delivery Repository Port (Interface).

This is an output port defining how the application layer expects to
interact with delivery persistence.
"""

from abc import ABC, abstractmethod
from typing import Optional

from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Delivery,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
)


class DeliveryRepositoryPort(ABC):
    """Abstract interface for delivery persistence operations."""

    @abstractmethod
    def save(self, delivery: Delivery) -> None:
        """Persist a delivery entity.

        Args:
            delivery: The delivery entity to save
        """
        pass

    @abstractmethod
    def find_by_id(self, delivery_id: DeliveryId) -> Optional[Delivery]:
        """Find a delivery by its unique identifier.

        Args:
            delivery_id: The delivery's unique identifier

        Returns:
            The delivery if found, None otherwise
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def update(self, delivery: Delivery) -> None:
        """Update an existing delivery.

        Args:
            delivery: The delivery entity to update
        """
        pass
