from contextlib import asynccontextmanager

from application.service import PaymentService
from domain.models import Payment, PaymentRequest
from fastapi import Depends, FastAPI, HTTPException
from infrastructure.adapters import ExternalBankAdapter, InMemoryPaymentRepository
from pydantic import BaseModel

from mmf.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf.framework.integration.domain.models import ConnectionConfig, ConnectorType

# Configuration
BANK_CONFIG = ConnectionConfig(
    system_id="bank-service",
    name="Bank Service",
    connector_type=ConnectorType.REST_API,
    endpoint_url="http://localhost:8002",  # Mock URL
    timeout=10,
)

# Global dependencies
bank_adapter = RESTAPIAdapter(BANK_CONFIG)
bank_service = ExternalBankAdapter(bank_adapter)
payment_repo = InMemoryPaymentRepository()
payment_service = PaymentService(payment_repo, bank_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    # await bank_adapter.connect() # Commented out as we are mocking the adapter logic
    yield
    # Shutdown
    # await bank_adapter.disconnect()


app = FastAPI(title="Payment Service", lifespan=lifespan)


class PaymentCreateRequest(BaseModel):
    order_id: str
    amount: float
    currency: str
    payment_method_id: str
    description: str = ""


@app.post("/payments", response_model=Payment)
async def create_payment(request: PaymentCreateRequest):
    payment = Payment(
        order_id=request.order_id,
        amount=request.amount,
        currency=request.currency,
        payment_method_id=request.payment_method_id,
    )
    return await payment_service.process_payment(payment)


@app.get("/payments/{payment_id}", response_model=Payment)
async def get_payment(payment_id: str):
    payment = await payment_service.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
