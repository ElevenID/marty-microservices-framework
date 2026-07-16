from abc import ABC, abstractmethod
from typing import Optional

from domain.models import Payment


class PaymentRepository(ABC):
    @abstractmethod
    async def save(self, payment: Payment) -> Payment:
        """Save a payment."""

    @abstractmethod
    async def get_by_id(self, payment_id: str) -> Payment | None:
        """Get a payment by ID."""


class BankServicePort(ABC):
    @abstractmethod
    async def process_payment(self, amount: float, currency: str, payment_method_id: str) -> str:
        """Process payment with bank. Returns transaction ID."""
