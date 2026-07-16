"""Domain entities for Delivery Board Service.

Entities are objects with a distinct identity that persists over time.
They have no external dependencies - only standard library types and
domain value objects.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
    DeliveryStatus,
    TruckId,
)


@dataclass
class DeliveryItem:
    """An item being delivered.

    Attributes:
        description: Description of the item
        quantity: Number of items
    """

    description: str
    quantity: int = 1

    def __post_init__(self) -> None:
        """Validate entity invariants."""
        if not self.description:
            msg = "DeliveryItem description cannot be empty"
            raise ValueError(msg)
        if self.quantity <= 0:
            msg = "DeliveryItem quantity must be positive"
            raise ValueError(msg)


@dataclass
class Truck:
    """Domain entity representing a delivery truck.

    Attributes:
        id: Unique truck identifier
        name: Display name for the truck
        capacity: Maximum delivery capacity
        region: Operating region (optional)
        current_load: Current number of assigned deliveries
        auto_scaled: Whether this truck was auto-provisioned
    """

    id: TruckId
    name: str
    capacity: int
    region: Optional[str] = None
    current_load: int = 0
    auto_scaled: bool = False

    def __post_init__(self) -> None:
        """Validate entity invariants."""
        if not self.name:
            msg = "Truck name cannot be empty"
            raise ValueError(msg)
        if self.capacity <= 0:
            msg = "Truck capacity must be positive"
            raise ValueError(msg)
        if self.current_load < 0:
            msg = "Truck current_load cannot be negative"
            raise ValueError(msg)

    def is_available(self) -> bool:
        """Check if truck has capacity for more deliveries."""
        return self.current_load < self.capacity

    def assign_delivery(self) -> None:
        """Assign a new delivery to this truck."""
        if not self.is_available():
            msg = f"Truck {self.name} is at capacity"
            raise ValueError(msg)
        self.current_load += 1

    def complete_delivery(self) -> None:
        """Mark a delivery as complete, freeing capacity."""
        if self.current_load <= 0:
            msg = f"Truck {self.name} has no active deliveries"
            raise ValueError(msg)
        self.current_load -= 1


@dataclass
class Delivery:
    """Domain entity representing a delivery.

    Attributes:
        id: Unique delivery identifier
        order_id: Reference to the originating order
        address: Delivery address
        items: List of items being delivered
        status: Current delivery status
        truck_id: Assigned truck identifier
        eta_minutes: Estimated time of arrival in minutes
        priority: Delivery priority
        created_at: When the delivery was created
        updated_at: When the delivery was last updated
    """

    id: DeliveryId
    order_id: str
    address: str
    items: list[DeliveryItem]
    status: DeliveryStatus
    truck_id: TruckId
    eta_minutes: int
    priority: str = "standard"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate entity invariants."""
        if not self.order_id:
            msg = "Delivery order_id cannot be empty"
            raise ValueError(msg)
        if not self.address:
            msg = "Delivery address cannot be empty"
            raise ValueError(msg)
        if not self.items:
            msg = "Delivery must have at least one item"
            raise ValueError(msg)
        if self.eta_minutes < 0:
            msg = "Delivery eta_minutes cannot be negative"
            raise ValueError(msg)

    def start_transit(self) -> None:
        """Mark delivery as in transit."""
        if not self.status.can_transition_to(DeliveryStatus.IN_TRANSIT):
            msg = f"Cannot start transit for delivery in status {self.status}"
            raise ValueError(msg)
        self.status = DeliveryStatus.IN_TRANSIT
        self.updated_at = datetime.now(timezone.utc)

    def complete(self) -> None:
        """Mark delivery as delivered."""
        if not self.status.can_transition_to(DeliveryStatus.DELIVERED):
            msg = f"Cannot complete delivery in status {self.status}"
            raise ValueError(msg)
        self.status = DeliveryStatus.DELIVERED
        self.updated_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        """Cancel the delivery."""
        if not self.status.can_transition_to(DeliveryStatus.CANCELLED):
            msg = f"Cannot cancel delivery in status {self.status}"
            raise ValueError(msg)
        self.status = DeliveryStatus.CANCELLED
        self.updated_at = datetime.now(timezone.utc)
