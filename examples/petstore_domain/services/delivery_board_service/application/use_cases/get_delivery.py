"""Get Delivery Use Case.

This use case handles retrieving a single delivery by ID.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.exceptions import (
    DeliveryNotFoundError,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
)


@dataclass
class DeliveryItemResult:
    """Item in a delivery result."""

    description: str
    quantity: int


@dataclass
class GetDeliveryQuery:
    """Query object for retrieving a delivery."""

    delivery_id: str


@dataclass
class GetDeliveryResult:
    """Result of retrieving a delivery."""

    delivery_id: str
    order_id: str
    address: str
    items: list[DeliveryItemResult]
    status: str
    truck_id: str
    eta_minutes: int
    priority: str
    created_at: datetime
    updated_at: datetime


class GetDeliveryUseCase:
    """Use case for retrieving a delivery by ID."""

    def __init__(self, delivery_repository: DeliveryRepositoryPort) -> None:
        """Initialize the use case with required dependencies."""
        self._delivery_repository = delivery_repository

    def execute(self, query: GetDeliveryQuery) -> GetDeliveryResult:
        """Execute the get delivery use case.

        Args:
            query: The query containing the delivery ID

        Returns:
            Result containing the delivery's information

        Raises:
            DeliveryNotFoundError: If no delivery exists with the given ID
        """
        delivery_id = DeliveryId(value=query.delivery_id)
        delivery = self._delivery_repository.find_by_id(delivery_id)

        if delivery is None:
            raise DeliveryNotFoundError(query.delivery_id)

        return GetDeliveryResult(
            delivery_id=str(delivery.id),
            order_id=delivery.order_id,
            address=delivery.address,
            items=[
                DeliveryItemResult(description=item.description, quantity=item.quantity)
                for item in delivery.items
            ],
            status=delivery.status.value,
            truck_id=str(delivery.truck_id),
            eta_minutes=delivery.eta_minutes,
            priority=delivery.priority,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )
