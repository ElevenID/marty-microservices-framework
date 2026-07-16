"""Domain value objects for Store Service.

Value objects are immutable and defined by their attributes rather than identity.
They have no external dependencies - only standard library types.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Self


class OrderStatus(str, Enum):
    """Valid order statuses in the system."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

    def can_transition_to(self, new_status: "OrderStatus") -> bool:
        """Check if transition to new status is valid."""
        valid_transitions = {
            OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
            OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
            OrderStatus.PROCESSING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
            OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
            OrderStatus.DELIVERED: set(),
            OrderStatus.CANCELLED: set(),
        }
        return new_status in valid_transitions.get(self, set())


@dataclass(frozen=True)
class OrderId:
    """Unique identifier for an Order.

    This is a value object wrapping the raw ID to provide type safety
    and domain-specific validation.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the ID format."""
        if not self.value:
            msg = "OrderId cannot be empty"
            raise ValueError(msg)

    @classmethod
    def generate(cls) -> Self:
        """Generate a new unique OrderId."""
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Money:
    """Value object representing a monetary amount.

    Uses Decimal for precise financial calculations.
    """

    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        """Validate money invariants."""
        if self.amount < 0:
            msg = "Money amount cannot be negative"
            raise ValueError(msg)

    @classmethod
    def from_float(cls, amount: float, currency: str = "USD") -> Self:
        """Create Money from a float value."""
        return cls(amount=Decimal(str(amount)), currency=currency)

    def __add__(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            msg = f"Cannot add {self.currency} and {other.currency}"
            raise ValueError(msg)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __mul__(self, quantity: int) -> "Money":
        return Money(amount=self.amount * quantity, currency=self.currency)

    def to_float(self) -> float:
        """Convert to float for serialization."""
        return float(self.amount)
