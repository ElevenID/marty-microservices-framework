"""Order Repository Port (Interface).

This is an output port defining how the application layer expects to
interact with order persistence.
"""

from abc import ABC, abstractmethod
from typing import Optional

from examples.petstore_domain.services.store_service.domain.entities import Order
from examples.petstore_domain.services.store_service.domain.value_objects import OrderId


class OrderRepositoryPort(ABC):
    """Abstract interface for order persistence operations.

    This port defines the contract that any order repository implementation
    must fulfill.
    """

    @abstractmethod
    def save(self, order: Order) -> None:
        """Persist an order entity.

        Args:
            order: The order entity to save
        """
        pass

    @abstractmethod
    def find_by_id(self, order_id: OrderId) -> Optional[Order]:
        """Find an order by its unique identifier.

        Args:
            order_id: The order's unique identifier

        Returns:
            The order if found, None otherwise
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def update(self, order: Order) -> None:
        """Update an existing order.

        Args:
            order: The order entity to update
        """
        pass
