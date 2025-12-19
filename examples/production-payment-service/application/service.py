from domain.models import Payment, PaymentStatus
from domain.ports import BankServicePort, PaymentRepository


class PaymentService:
    def __init__(self, repo: PaymentRepository, bank: BankServicePort):
        self.repo = repo
        self.bank = bank

    async def process_payment(self, payment: Payment) -> Payment:
        """Process a new payment."""
        try:
            # Process with bank
            transaction_id = await self.bank.process_payment(
                payment.amount, payment.currency, payment.payment_method_id
            )

            payment.transaction_id = transaction_id
            payment.status = PaymentStatus.COMPLETED

        except Exception as e:
            payment.status = PaymentStatus.FAILED
            payment.error_message = str(e)

        # Save payment
        return await self.repo.save(payment)

    async def get_payment(self, payment_id: str) -> Payment | None:
        """Get payment by ID."""
        return await self.repo.get_by_id(payment_id)
