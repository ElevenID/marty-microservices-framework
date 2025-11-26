from dataclasses import dataclass, field
from typing import List
from datetime import datetime
import uuid

@dataclass
class OrderItem:
    product_id: str
    quantity: int
    price: float

@dataclass
class Order:
    customer_id: str
    items: List[OrderItem]
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "PENDING"
    created_at: datetime = field(default_factory=datetime.now)
    total_amount: float = 0.0

    def calculate_total(self) -> None:
        self.total_amount = sum(item.price * item.quantity for item in self.items)
