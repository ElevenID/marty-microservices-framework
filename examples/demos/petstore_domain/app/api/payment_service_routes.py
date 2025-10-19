"""
API routes for payment-service service.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services.payment_service_service import PaymentServiceService

router = APIRouter(prefix="/payment-service", tags=["payment-service"])

class RequestModel(BaseModel):
    """Request model for payment-service."""
    data: Dict[str, Any]

class ResponseModel(BaseModel):
    """Response model for payment-service."""
    message: str
    data: Dict[str, Any]
    service: str

@router.get("/health")
async def get_health():
    """Get service health."""
    return {
        "status": "healthy",
        "service": "payment-service",
        "features": ('database', 'monitoring')
    }

@router.post("/process", response_model=ResponseModel)
async def process_request(request: RequestModel):
    """Process a service request."""
    # Import service here to avoid circular imports

    service = PaymentServiceService()
    result = await service.process_request(request.data)

    return ResponseModel(
        message=result["message"],
        data=result["data"],
        service=result["service"]
    )
