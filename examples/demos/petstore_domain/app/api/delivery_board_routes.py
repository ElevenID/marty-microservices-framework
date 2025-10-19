"""
API routes for delivery-board service.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..services.delivery_board_service import DeliveryBoardService

router = APIRouter(prefix="/delivery-board", tags=["delivery-board"])

class RequestModel(BaseModel):
    """Request model for delivery-board."""
    data: Dict[str, Any]

class ResponseModel(BaseModel):
    """Response model for delivery-board."""
    message: str
    data: Dict[str, Any]
    service: str

@router.get("/health")
async def get_health():
    """Get service health."""
    return {
        "status": "healthy",
        "service": "delivery-board",
        "features": ('database', 'monitoring')
    }

@router.post("/process", response_model=ResponseModel)
async def process_request(request: RequestModel):
    """Process a service request."""
    # Import service here to avoid circular imports

    service = DeliveryBoardService()
    result = await service.process_request(request.data)

    return ResponseModel(
        message=result["message"],
        data=result["data"],
        service=result["service"]
    )
