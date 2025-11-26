from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

@dataclass
class OrderItem:
    product_id: str
    quantity: int
    price: float

@dataclass
class Order:
    customer_id: str
    items: list[OrderItem]
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "PENDING"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_amount: float = 0.0

    def calculate_total(self) -> None:
        self.total_amount = sum(item.price * item.quantity for item in self.items)

    def to_timestamp(self) -> int:
        """Convert created_at to Unix timestamp for gRPC."""
        return int(self.created_at.timestamp())

    def to_dict(self) -> dict:
        """Convert to dictionary for REST API responses."""
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "status": self.status,
            "total_amount": self.total_amount,
            "created_at": self.created_at.isoformat(),
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "price": item.price
                }
                for item in self.items
            ]
        }