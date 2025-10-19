"""
Security-enhanced API routes for the PetStore Domain.

This module provides secure API endpoints with authentication and authorization
using the Marty MSF security framework.
"""
import logging
import uuid
from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.services.security_service import get_security_service
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Create router for secure endpoints
secure_router = APIRouter(prefix="/api/v1", tags=["secure-petstore"])

# Security dependency
security = HTTPBearer()

# Response models
class SecureResponse(BaseModel):
    """Standard secure response model"""
    success: bool
    message: str
    data: Any = None
    user_id: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class Pet(BaseModel):
    """Pet model"""
    id: str
    name: str
    species: str
    breed: str | None = None
    age: int | None = None
    status: str = "available"
    owner_id: str | None = None

class Order(BaseModel):
    """Order model"""
    id: str
    pet_id: str
    customer_id: str
    status: str = "pending"
    total_amount: float
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class CreatePetRequest(BaseModel):
    """Request to create a new pet"""
    name: str
    species: str
    breed: str | None = None
    age: int | None = None

class CreateOrderRequest(BaseModel):
    """Request to create a new order"""
    pet_id: str
    total_amount: float

# Security dependencies
async def get_current_user(request: Request) -> dict[str, Any]:
    """Get current authenticated user from request"""
    principal = getattr(request.state, 'principal', None)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return principal

async def require_admin(request: Request) -> dict[str, Any]:
    """Require admin role"""
    principal = await get_current_user(request)
    user_roles = principal.get("roles", [])

    if "admin" not in user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )

    return principal

async def require_user_or_admin(request: Request) -> dict[str, Any]:
    """Require user or admin role"""
    principal = await get_current_user(request)
    user_roles = principal.get("roles", [])

    if not any(role in user_roles for role in ["user", "admin"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User or admin role required"
        )

    return principal

# Pets endpoints
@secure_router.get("/pets/public", response_model=SecureResponse)
async def get_public_pets():
    """Get publicly available pets (no authentication required)"""
    # This endpoint is public, accessible without authentication
    pets = [
        {"id": "pet-1", "name": "Buddy", "species": "dog", "status": "available"},
        {"id": "pet-2", "name": "Whiskers", "species": "cat", "status": "available"},
        {"id": "pet-3", "name": "Charlie", "species": "bird", "status": "available"}
    ]

    return SecureResponse(
        success=True,
        message="Public pets retrieved successfully",
        data={"pets": pets}
    )

@secure_router.get("/pets", response_model=SecureResponse)
async def get_pets(
    request: Request,
    current_user: dict = Depends(require_user_or_admin)
):
    """Get all pets (requires authentication)"""
    try:
        # In a real implementation, this would fetch from database
        pets = [
            {"id": "pet-1", "name": "Buddy", "species": "dog", "status": "available", "owner_id": None},
            {"id": "pet-2", "name": "Whiskers", "species": "cat", "status": "adopted", "owner_id": "user-123"},
            {"id": "pet-3", "name": "Charlie", "species": "bird", "status": "available", "owner_id": None},
            {"id": "pet-4", "name": "Luna", "species": "cat", "status": "reserved", "owner_id": "user-456"}
        ]

        return SecureResponse(
            success=True,
            message="Pets retrieved successfully",
            data={"pets": pets, "count": len(pets)},
            user_id=current_user.get("user_id")
        )

    except Exception as e:
        logger.error(f"Failed to get pets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pets"
        )

@secure_router.get("/pets/{pet_id}", response_model=SecureResponse)
async def get_pet(
    pet_id: str,
    request: Request,
    current_user: dict = Depends(require_user_or_admin)
):
    """Get a specific pet by ID"""
    # Simulate pet data
    pet_data = {
        "id": pet_id,
        "name": "Buddy",
        "species": "dog",
        "breed": "Golden Retriever",
        "age": 3,
        "status": "available",
        "owner_id": None
    }

    return SecureResponse(
        success=True,
        message=f"Pet {pet_id} retrieved successfully",
        data={"pet": pet_data},
        user_id=current_user.get("user_id")
    )

@secure_router.post("/pets", response_model=SecureResponse, status_code=status.HTTP_201_CREATED)
async def create_pet(
    pet_request: CreatePetRequest,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Create a new pet (admin only)"""
    try:
        # Generate new pet ID
        pet_id = f"pet-{uuid.uuid4().hex[:8]}"

        # Create pet data
        pet_data = {
            "id": pet_id,
            "name": pet_request.name,
            "species": pet_request.species,
            "breed": pet_request.breed,
            "age": pet_request.age,
            "status": "available",
            "created_by": current_user.get("user_id"),
            "created_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Pet {pet_id} created by {current_user.get('user_id')}")

        return SecureResponse(
            success=True,
            message="Pet created successfully",
            data={"pet": pet_data},
            user_id=current_user.get("user_id")
        )

    except Exception as e:
        logger.error(f"Failed to create pet: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create pet"
        )

# Orders endpoints
@secure_router.get("/orders", response_model=SecureResponse)
async def get_orders(
    request: Request,
    current_user: dict = Depends(require_user_or_admin)
):
    """Get orders for the current user"""
    user_id = current_user.get("user_id")
    user_roles = current_user.get("roles", [])

    # Admin can see all orders, users only see their own
    if "admin" in user_roles:
        orders = [
            {"id": "order-1", "pet_id": "pet-1", "customer_id": "user-123", "status": "completed", "total_amount": 250.00},
            {"id": "order-2", "pet_id": "pet-2", "customer_id": "user-456", "status": "pending", "total_amount": 180.00},
            {"id": "order-3", "pet_id": "pet-3", "customer_id": user_id, "status": "processing", "total_amount": 320.00}
        ]
    else:
        # Filter orders for current user only
        orders = [
            {"id": "order-3", "pet_id": "pet-3", "customer_id": user_id, "status": "processing", "total_amount": 320.00}
        ]

    return SecureResponse(
        success=True,
        message="Orders retrieved successfully",
        data={"orders": orders, "count": len(orders)},
        user_id=user_id
    )

@secure_router.post("/orders", response_model=SecureResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_request: CreateOrderRequest,
    request: Request,
    current_user: dict = Depends(require_user_or_admin)
):
    """Create a new order"""
    try:
        # Generate new order ID
        order_id = f"order-{uuid.uuid4().hex[:8]}"

        # Create order data
        order_data = {
            "id": order_id,
            "pet_id": order_request.pet_id,
            "customer_id": current_user.get("user_id"),
            "status": "pending",
            "total_amount": order_request.total_amount,
            "created_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Order {order_id} created by {current_user.get('user_id')}")

        return SecureResponse(
            success=True,
            message="Order created successfully",
            data={"order": order_data},
            user_id=current_user.get("user_id")
        )

    except Exception as e:
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create order"
        )

# Admin endpoints
@secure_router.get("/admin/stats", response_model=SecureResponse)
async def get_admin_stats(
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Get admin statistics (admin only)"""
    try:
        # Get security service for additional stats
        config = get_settings()
        security_service = await get_security_service(config)
        security_health = await security_service.health_check()

        stats = {
            "total_pets": 4,
            "total_orders": 3,
            "pending_orders": 1,
            "total_users": 2,
            "security_status": security_health,
            "generated_at": datetime.utcnow().isoformat()
        }

        return SecureResponse(
            success=True,
            message="Admin statistics retrieved successfully",
            data={"stats": stats},
            user_id=current_user.get("user_id")
        )

    except Exception as e:
        logger.error(f"Failed to get admin stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve admin statistics"
        )

@secure_router.post("/admin/orders/{order_id}/cancel", response_model=SecureResponse)
async def cancel_order(
    order_id: str,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Cancel an order (admin only)"""
    try:
        # Simulate order cancellation
        logger.info(f"Order {order_id} cancelled by admin {current_user.get('user_id')}")

        return SecureResponse(
            success=True,
            message=f"Order {order_id} cancelled successfully",
            data={"order_id": order_id, "status": "cancelled"},
            user_id=current_user.get("user_id")
        )

    except Exception as e:
        logger.error(f"Failed to cancel order {order_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel order"
        )

# Service-to-service endpoints
@secure_router.post("/internal/events", response_model=SecureResponse)
async def handle_internal_event(
    event_data: dict[str, Any],
    request: Request
):
    """Handle internal service events (service authentication required)"""
    # This endpoint expects service-to-service authentication
    principal = getattr(request.state, 'principal', None)

    if not principal or principal.get("type") != "service":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Service authentication required"
        )

    try:
        # Process the event
        logger.info(f"Internal event received from {principal.get('service_name')}: {event_data}")

        return SecureResponse(
            success=True,
            message="Event processed successfully",
            data={"event_id": event_data.get("id"), "processed_at": datetime.utcnow().isoformat()}
        )

    except Exception as e:
        logger.error(f"Failed to process internal event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process event"
        )

# Security test endpoints for demonstration
@secure_router.get("/test/auth", response_model=SecureResponse)
async def test_authentication(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Test authentication (requires valid token)"""
    return SecureResponse(
        success=True,
        message="Authentication successful",
        data={
            "user_info": current_user,
            "timestamp": datetime.utcnow().isoformat()
        },
        user_id=current_user.get("user_id")
    )

@secure_router.get("/test/admin", response_model=SecureResponse)
async def test_admin_authorization(
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Test admin authorization (requires admin role)"""
    return SecureResponse(
        success=True,
        message="Admin authorization successful",
        data={
            "admin_info": current_user,
            "timestamp": datetime.utcnow().isoformat()
        },
        user_id=current_user.get("user_id")
    )
