"""List Orders Use Case.

This use case handles retrieving all orders from the system.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.domain.entities import Order


@dataclass
class PaginationQuery:
    """Query parameters for pagination."""

    limit: int = 20
    offset: int = 0


@dataclass
class ListOrdersResult:
    """Result of listing orders."""

    orders: list[Order]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class ListOrdersUseCase:
    """Use case for listing all orders."""

    def __init__(self, order_repository: OrderRepositoryPort) -> None:
        """Initialize the use case with required dependencies.

        Args:
            order_repository: Port for order persistence operations
        """
        self._order_repository = order_repository

    def execute(self, pagination: Optional[PaginationQuery] = None) -> ListOrdersResult:
        """Execute the list orders use case.

        Args:
            pagination: Optional pagination parameters

        Returns:
            Result containing the list of orders, total count, and pagination info
        """
        if pagination is None:
            pagination = PaginationQuery()

        orders, total_count = self._order_repository.find_all(
            limit=pagination.limit, offset=pagination.offset
        )

        has_more = (pagination.offset + len(orders)) < total_count

        return ListOrdersResult(
            orders=orders,
            total_count=total_count,
            limit=pagination.limit,
            offset=pagination.offset,
            has_more=has_more,
        )
