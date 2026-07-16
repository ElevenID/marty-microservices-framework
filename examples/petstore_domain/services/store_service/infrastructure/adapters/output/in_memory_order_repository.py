"""In-Memory Order Repository Adapter.

This is a driven (output) adapter that implements the OrderRepositoryPort
interface using an in-memory dictionary.
"""

from typing import Optional

from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.domain.entities import Order
from examples.petstore_domain.services.store_service.domain.value_objects import OrderId


class InMemoryOrderRepository(OrderRepositoryPort):
    """In-memory implementation of the order repository.

    This adapter stores orders in a dictionary.
    """

    def __init__(self) -> None:
        """Initialize the in-memory storage."""
        self._storage: dict[str, Order] = {}

    def save(self, order: Order) -> None:
        """Persist an order entity.

        Args:
            order: The order entity to save
        """
        self._storage[str(order.id)] = order

    def find_by_id(self, order_id: OrderId) -> Optional[Order]:
        """Find an order by its unique identifier.

        Args:
            order_id: The order's unique identifier

        Returns:
            The order if found, None otherwise
        """
        return self._storage.get(str(order_id))

    def find_all(
        self, *, limit: int | None = None, offset: int = 0
    ) -> tuple[list[Order], int]:
        """Retrieve all orders with optional pagination.

        Args:
            limit: Maximum number of orders to return (None for all)
            offset: Number of orders to skip

        Returns:
            Tuple of (list of order entities, total count)
        """
        all_orders = list(self._storage.values())
        total_count = len(all_orders)

        # Apply pagination
        if offset:
            all_orders = all_orders[offset:]
        if limit is not None:
            all_orders = all_orders[:limit]

        return all_orders, total_count

    def update(self, order: Order) -> None:
        """Update an existing order.

        Args:
            order: The order entity to update
        """
        self._storage[str(order.id)] = order

    def clear(self) -> None:
        """Clear all orders from memory."""
        self._storage.clear()
