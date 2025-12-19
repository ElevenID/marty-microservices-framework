"""Domain entities for Store Service.

Entities are objects with a distinct identity that persists over time.
They have no external dependencies - only standard library types and
domain value objects.
"""

from dataclasses import dataclass, field
from typing import Optional

from examples.petstore_domain.services.store_service.domain.value_objects import (
    Money,
    OrderId,
    OrderStatus,
)


@dataclass
class CatalogItem:
    """Domain entity representing an item in the store catalog.

    This is the Store's own view of a "pet" - it's NOT the same as
    Pet from pet_service (bounded context isolation).

    Attributes:
        pet_id: Unique identifier for the catalog item
        name: Display name
        species: Type of animal
        price: Price per unit
        quantity: Available stock
        delivery_lead_days: Days required for delivery
    """

    pet_id: str
    name: str
    species: str
    price: Money
    quantity: int
    delivery_lead_days: int = 1

    def __post_init__(self) -> None:
        """Validate entity invariants."""
        if not self.pet_id:
            msg = "CatalogItem pet_id cannot be empty"
            raise ValueError(msg)
        if not self.name:
            msg = "CatalogItem name cannot be empty"
            raise ValueError(msg)
        if self.quantity < 0:
            msg = "CatalogItem quantity cannot be negative"
            raise ValueError(msg)
        if self.delivery_lead_days < 0:
            msg = "CatalogItem delivery_lead_days cannot be negative"
            raise ValueError(msg)

    def is_in_stock(self) -> bool:
        """Check if item is available."""
        return self.quantity > 0

    def reduce_stock(self, amount: int) -> None:
        """Reduce stock by the given amount."""
        if amount > self.quantity:
            msg = f"Insufficient stock: requested {amount}, available {self.quantity}"
            raise ValueError(msg)
        self.quantity -= amount

    def add_stock(self, amount: int) -> None:
        """Add stock by the given amount."""
        if amount <= 0:
            msg = "Stock addition must be positive"
            raise ValueError(msg)
        self.quantity += amount


@dataclass
class Order:
    """Domain entity representing a customer order.

    Attributes:
        id: Unique order identifier
        pet_id: Reference to catalog item
        quantity: Number of items ordered
        customer_name: Customer's name
        status: Current order status
        total_price: Total price of the order
        delivery_requested: Whether delivery was requested
        delivery_address: Optional delivery address
    """

    id: OrderId
    pet_id: str
    quantity: int
    customer_name: str
    status: OrderStatus
    total_price: Money
    delivery_requested: bool = True
    delivery_address: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate entity invariants."""
        if not self.pet_id:
            msg = "Order pet_id cannot be empty"
            raise ValueError(msg)
        if self.quantity <= 0:
            msg = "Order quantity must be positive"
            raise ValueError(msg)
        if not self.customer_name:
            msg = "Order customer_name cannot be empty"
            raise ValueError(msg)

    def confirm(self) -> None:
        """Confirm the order."""
        if not self.status.can_transition_to(OrderStatus.CONFIRMED):
            msg = f"Cannot confirm order in status {self.status}"
            raise ValueError(msg)
        self.status = OrderStatus.CONFIRMED

    def cancel(self) -> None:
        """Cancel the order."""
        if not self.status.can_transition_to(OrderStatus.CANCELLED):
            msg = f"Cannot cancel order in status {self.status}"
            raise ValueError(msg)
        self.status = OrderStatus.CANCELLED

    def ship(self) -> None:
        """Mark order as shipped."""
        if not self.status.can_transition_to(OrderStatus.SHIPPED):
            msg = f"Cannot ship order in status {self.status}"
            raise ValueError(msg)
        self.status = OrderStatus.SHIPPED

    def deliver(self) -> None:
        """Mark order as delivered."""
        if not self.status.can_transition_to(OrderStatus.DELIVERED):
            msg = f"Cannot deliver order in status {self.status}"
            raise ValueError(msg)
        self.status = OrderStatus.DELIVERED
