import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

@dataclass
class PaymentRequest:
    order_id: str
    amount: float
    currency: str
    payment_method_id: str
    description: str = ""

@dataclass
class Payment:
    order_id: str
    amount: float
    currency: str
    payment_method_id: str
    payment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    transaction_id: str = ""
    error_message: str = ""
