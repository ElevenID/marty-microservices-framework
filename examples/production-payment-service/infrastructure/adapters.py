import uuid

from domain.models import Payment
from domain.ports import BankServicePort, PaymentRepository

from mmf.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf.framework.integration.domain.models import IntegrationRequest


class InMemoryPaymentRepository(PaymentRepository):
    def __init__(self):
        self._payments: dict[str, Payment] = {}

    async def save(self, payment: Payment) -> Payment:
        self._payments[payment.payment_id] = payment
        return payment

    async def get_by_id(self, payment_id: str) -> Payment | None:
        return self._payments.get(payment_id)


class ExternalBankAdapter(BankServicePort):
    def __init__(self, adapter: RESTAPIAdapter):
        self.adapter = adapter

    async def process_payment(self, amount: float, currency: str, payment_method_id: str) -> str:
        """
        Call external bank system to process payment.
        POST /transactions
        """
        request = IntegrationRequest(
            system_id=self.adapter.config.system_id,
            operation="POST",
            data={
                "path": "/transactions",
                "amount": amount,
                "currency": currency,
                "payment_method_id": payment_method_id
            },
        )

        # In a real scenario, we would await self.adapter.execute(request)
        # For this example, we'll mock the response if the adapter isn't actually connected to a real service
        # But let's try to use the adapter structure.

        # Since we don't have a real bank service running, let's just simulate success
        # unless the amount is negative (just for logic)
        if amount < 0:
             raise Exception("Invalid amount")

        return str(uuid.uuid4())
