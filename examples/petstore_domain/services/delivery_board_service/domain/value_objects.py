"""Domain value objects for Delivery Board Service.

Value objects are immutable and defined by their attributes rather than identity.
They have no external dependencies - only standard library types.
"""

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Self


class DeliveryStatus(str, Enum):
    """Valid delivery statuses in the system."""

    QUEUED = "queued"
    ASSIGNED = "assigned"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    def can_transition_to(self, new_status: "DeliveryStatus") -> bool:
        """Check if transition to new status is valid."""
        valid_transitions = {
            DeliveryStatus.QUEUED: {DeliveryStatus.ASSIGNED, DeliveryStatus.CANCELLED},
            DeliveryStatus.ASSIGNED: {DeliveryStatus.IN_TRANSIT, DeliveryStatus.CANCELLED},
            DeliveryStatus.IN_TRANSIT: {DeliveryStatus.DELIVERED},
            DeliveryStatus.DELIVERED: set(),
            DeliveryStatus.CANCELLED: set(),
        }
        return new_status in valid_transitions.get(self, set())


class DeliveryPriority(str, Enum):
    """Delivery priority levels."""

    STANDARD = "standard"
    EXPRESS = "express"
    URGENT = "urgent"


@dataclass(frozen=True)
class DeliveryId:
    """Unique identifier for a Delivery."""

    value: str

    def __post_init__(self) -> None:
        """Validate the ID format."""
        if not self.value:
            msg = "DeliveryId cannot be empty"
            raise ValueError(msg)

    @classmethod
    def generate(cls) -> Self:
        """Generate a new unique DeliveryId."""
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class TruckId:
    """Unique identifier for a Truck."""

    value: str

    def __post_init__(self) -> None:
        """Validate the ID format."""
        if not self.value:
            msg = "TruckId cannot be empty"
            raise ValueError(msg)

    @classmethod
    def generate(cls) -> Self:
        """Generate a new unique TruckId."""
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value
