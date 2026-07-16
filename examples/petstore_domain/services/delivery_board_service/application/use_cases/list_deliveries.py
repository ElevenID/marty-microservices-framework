"""List Deliveries Use Case.

This use case handles retrieving all deliveries from the system.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Delivery,
)


@dataclass
class PaginationQuery:
    """Query parameters for pagination."""

    limit: int = 20
    offset: int = 0


@dataclass
class ListDeliveriesResult:
    """Result of listing deliveries."""

    deliveries: list[Delivery]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class ListDeliveriesUseCase:
    """Use case for listing all deliveries."""

    def __init__(self, delivery_repository: DeliveryRepositoryPort) -> None:
        """Initialize the use case with required dependencies.

        Args:
            delivery_repository: Port for delivery persistence operations
        """
        self._delivery_repository = delivery_repository

    def execute(
        self, pagination: Optional[PaginationQuery] = None
    ) -> ListDeliveriesResult:
        """Execute the list deliveries use case.

        Args:
            pagination: Optional pagination parameters

        Returns:
            Result containing the list of deliveries, total count, and pagination info
        """
        if pagination is None:
            pagination = PaginationQuery()

        deliveries, total_count = self._delivery_repository.find_all(
            limit=pagination.limit, offset=pagination.offset
        )

        has_more = (pagination.offset + len(deliveries)) < total_count

        return ListDeliveriesResult(
            deliveries=deliveries,
            total_count=total_count,
            limit=pagination.limit,
            offset=pagination.offset,
            has_more=has_more,
        )
