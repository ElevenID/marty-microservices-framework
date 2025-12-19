"""Get Order Use Case.

This use case handles retrieving a single order by ID.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.domain.exceptions import (
    OrderNotFoundError,
)
from examples.petstore_domain.services.store_service.domain.value_objects import OrderId


@dataclass
class GetOrderQuery:
    """Query object for retrieving an order."""

    order_id: str


@dataclass
class GetOrderResult:
    """Result of retrieving an order."""

    order_id: str
    pet_id: str
    quantity: int
    customer_name: str
    status: str
    total_price: float
    delivery_requested: bool
    delivery_address: Optional[str]


class GetOrderUseCase:
    """Use case for retrieving an order by ID.

    This use case:
    1. Validates the order ID
    2. Looks up the order in the repository
    3. Returns the order's details or raises an error
    """

    def __init__(self, order_repository: OrderRepositoryPort) -> None:
        """Initialize the use case with required dependencies.

        Args:
            order_repository: Port for order persistence operations
        """
        self._order_repository = order_repository

    def execute(self, query: GetOrderQuery) -> GetOrderResult:
        """Execute the get order use case.

        Args:
            query: The query containing the order ID

        Returns:
            Result containing the order's information

        Raises:
            OrderNotFoundError: If no order exists with the given ID
            ValueError: If the order ID is invalid
        """
        # Create value object (validates format)
        order_id = OrderId(value=query.order_id)

        # Look up in repository
        order = self._order_repository.find_by_id(order_id)

        if order is None:
            raise OrderNotFoundError(query.order_id)

        return GetOrderResult(
            order_id=str(order.id),
            pet_id=order.pet_id,
            quantity=order.quantity,
            customer_name=order.customer_name,
            status=order.status.value,
            total_price=order.total_price.to_float(),
            delivery_requested=order.delivery_requested,
            delivery_address=order.delivery_address,
        )
