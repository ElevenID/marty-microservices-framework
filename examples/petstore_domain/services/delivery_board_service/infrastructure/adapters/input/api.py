"""FastAPI HTTP Adapter for Delivery Board Service.

This is a driving (input) adapter that handles HTTP requests and
translates them into application use case calls.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from examples.petstore_domain.services.delivery_board_service.application.use_cases.cancel_delivery import (
    CancelDeliveryCommand,
    CancelDeliveryUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.complete_delivery import (
    CompleteDeliveryUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.create_delivery import (
    CreateDeliveryCommand,
    CreateDeliveryUseCase,
    DeliveryItemCommand,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.get_delivery import (
    GetDeliveryQuery,
    GetDeliveryUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.list_deliveries import (
    ListDeliveriesUseCase,
    PaginationQuery,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.list_trucks import (
    ListTrucksUseCase,
)
from examples.petstore_domain.services.delivery_board_service.application.use_cases.update_truck import (
    UpdateTruckCommand,
    UpdateTruckUseCase,
)
from examples.petstore_domain.services.delivery_board_service.domain.exceptions import (
    DeliveryNotFoundError,
    NoAvailableTruckError,
)

# =============================================================================
# Request/Response DTOs
# =============================================================================


class DeliveryItemRequest(BaseModel):
    """HTTP request body for a delivery item."""

    description: str = Field(..., min_length=1)
    quantity: int = Field(default=1, gt=0)


class CreateDeliveryRequest(BaseModel):
    """HTTP request body for creating a delivery."""

    order_id: str = Field(..., min_length=1)
    address: str = Field(..., min_length=1)
    items: list[DeliveryItemRequest] = Field(..., min_length=1)
    priority: str = Field(default="standard")


class DeliveryItemResponse(BaseModel):
    """HTTP response body for a delivery item."""

    description: str
    quantity: int


class DeliveryResponse(BaseModel):
    """HTTP response body for a delivery."""

    id: str
    order_id: str
    address: str
    items: list[DeliveryItemResponse]
    status: str
    truck_id: str
    eta_minutes: int
    priority: str
    created_at: datetime
    updated_at: datetime


class DeliveryListResponse(BaseModel):
    """HTTP response body for listing deliveries."""

    deliveries: list[DeliveryResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class CreateDeliveryResponse(BaseModel):
    """HTTP response body for creating a delivery."""

    id: str
    order_id: str
    truck_id: str
    status: str
    eta_minutes: int
    priority: str


class TruckResponse(BaseModel):
    """HTTP response body for a truck."""

    id: str
    name: str
    capacity: int
    current_load: int
    region: Optional[str]
    auto_scaled: bool
    available: bool


class TruckListResponse(BaseModel):
    """HTTP response body for listing trucks."""

    trucks: list[TruckResponse]
    total_count: int
    total_capacity: int
    total_load: int


class CancelDeliveryRequest(BaseModel):
    """HTTP request body for cancelling a delivery."""

    reason: str = Field(default="", description="Reason for cancellation")


class CancelDeliveryResponse(BaseModel):
    """HTTP response body for cancelling a delivery."""

    delivery_id: str
    order_id: str
    status: str
    cancelled: bool
    error_message: Optional[str] = None


class UpdateTruckRequest(BaseModel):
    """HTTP request body for updating a truck."""

    name: Optional[str] = Field(None, min_length=1, description="New truck name")
    capacity: Optional[int] = Field(None, gt=0, description="New truck capacity")
    region: Optional[str] = Field(None, description="New truck region")


class UpdateTruckResponse(BaseModel):
    """HTTP response body for updating a truck."""

    truck_id: str
    name: str
    capacity: int
    region: Optional[str]
    current_load: int
    success: bool
    error_message: Optional[str] = None


# =============================================================================
# Router Factory
# =============================================================================


def create_delivery_router(
    create_delivery_use_case: CreateDeliveryUseCase,
    get_delivery_use_case: GetDeliveryUseCase,
    list_deliveries_use_case: ListDeliveriesUseCase,
    complete_delivery_use_case: CompleteDeliveryUseCase,
    cancel_delivery_use_case: CancelDeliveryUseCase,
    list_trucks_use_case: ListTrucksUseCase,
    update_truck_use_case: UpdateTruckUseCase,
) -> APIRouter:
    """Create a FastAPI router with all delivery endpoints.

    Args:
        create_delivery_use_case: Use case for creating deliveries
        get_delivery_use_case: Use case for retrieving a delivery
        list_deliveries_use_case: Use case for listing deliveries
        complete_delivery_use_case: Use case for completing a delivery
        cancel_delivery_use_case: Use case for cancelling a delivery
        list_trucks_use_case: Use case for listing trucks
        update_truck_use_case: Use case for updating a truck

    Returns:
        Configured APIRouter with all delivery endpoints
    """
    router = APIRouter(tags=["delivery"])

    @router.get(
        "/trucks",
        response_model=TruckListResponse,
        summary="List all trucks",
    )
    async def list_trucks() -> TruckListResponse:
        """Retrieve all trucks in the fleet."""
        result = list_trucks_use_case.execute()

        return TruckListResponse(
            trucks=[
                TruckResponse(
                    id=truck.truck_id,
                    name=truck.name,
                    capacity=truck.capacity,
                    current_load=truck.current_load,
                    region=truck.region,
                    auto_scaled=truck.auto_scaled,
                    available=truck.available,
                )
                for truck in result.trucks
            ],
            total_count=result.total_count,
            total_capacity=result.total_capacity,
            total_load=result.total_load,
        )

    @router.post(
        "/deliveries",
        response_model=CreateDeliveryResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a new delivery",
    )
    async def create_delivery(request: CreateDeliveryRequest) -> CreateDeliveryResponse:
        """Create a new delivery and assign a truck."""
        command = CreateDeliveryCommand(
            order_id=request.order_id,
            address=request.address,
            items=[
                DeliveryItemCommand(description=item.description, quantity=item.quantity)
                for item in request.items
            ],
            priority=request.priority,
        )

        try:
            result = await create_delivery_use_case.execute(command)
        except NoAvailableTruckError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            ) from e

        return CreateDeliveryResponse(
            id=result.delivery_id,
            order_id=result.order_id,
            truck_id=result.truck_id,
            status=result.status,
            eta_minutes=result.eta_minutes,
            priority=result.priority,
        )

    @router.get(
        "/deliveries",
        response_model=DeliveryListResponse,
        summary="List all deliveries",
    )
    async def list_deliveries(
        limit: int = Query(20, ge=1, le=100, description="Maximum number of deliveries to return"),
        offset: int = Query(0, ge=0, description="Number of deliveries to skip"),
    ) -> DeliveryListResponse:
        """Retrieve all deliveries with pagination."""
        pagination = PaginationQuery(limit=limit, offset=offset)
        result = list_deliveries_use_case.execute(pagination)
        return DeliveryListResponse(
            deliveries=[
                DeliveryResponse(
                    id=delivery.id.value,
                    order_id=delivery.order_id,
                    address=delivery.address,
                    items=[
                        DeliveryItemResponse(
                            description=item.description, quantity=item.quantity
                        )
                        for item in delivery.items
                    ],
                    status=delivery.status.value,
                    truck_id=delivery.truck_id.value,
                    eta_minutes=delivery.eta_minutes,
                    priority=delivery.priority,
                    created_at=delivery.created_at,
                    updated_at=delivery.updated_at,
                )
                for delivery in result.deliveries
            ],
            total_count=result.total_count,
            limit=result.limit,
            offset=result.offset,
            has_more=result.has_more,
        )

    @router.get(
        "/deliveries/{delivery_id}",
        response_model=DeliveryResponse,
        summary="Get a delivery by ID",
    )
    async def get_delivery(delivery_id: str) -> DeliveryResponse:
        """Retrieve a delivery by its unique identifier."""
        query = GetDeliveryQuery(delivery_id=delivery_id)

        try:
            result = get_delivery_use_case.execute(query)
        except DeliveryNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        return DeliveryResponse(
            id=result.delivery_id,
            order_id=result.order_id,
            address=result.address,
            items=[
                DeliveryItemResponse(description=item.description, quantity=item.quantity)
                for item in result.items
            ],
            status=result.status,
            truck_id=result.truck_id,
            eta_minutes=result.eta_minutes,
            priority=result.priority,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )

    @router.post(
        "/deliveries/{delivery_id}/complete",
        response_model=DeliveryResponse,
        summary="Complete a delivery",
    )
    async def complete_delivery(delivery_id: str) -> DeliveryResponse:
        """Mark a delivery as complete."""
        result = await complete_delivery_use_case.execute(delivery_id)

        if not result.success:
            if "not found" in (result.error_message or "").lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result.error_message,
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message,
            )

        delivery = result.delivery
        # Should not happen if success is True
        if not delivery:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Delivery not returned after completion",
            )

        return DeliveryResponse(
            id=delivery.id.value,
            order_id=delivery.order_id,
            address=delivery.address,
            items=[
                DeliveryItemResponse(description=item.description, quantity=item.quantity)
                for item in delivery.items
            ],
            status=delivery.status.value,
            truck_id=delivery.truck_id.value,
            eta_minutes=delivery.eta_minutes,
            priority=delivery.priority,
            created_at=delivery.created_at,
            updated_at=delivery.updated_at,
        )

    @router.delete(
        "/deliveries/{delivery_id}",
        response_model=CancelDeliveryResponse,
        summary="Cancel a delivery",
    )
    async def cancel_delivery(
        delivery_id: str,
        request: CancelDeliveryRequest = CancelDeliveryRequest(),
    ) -> CancelDeliveryResponse:
        """Cancel a delivery by its unique identifier."""
        command = CancelDeliveryCommand(
            delivery_id=delivery_id,
            reason=request.reason,
        )
        result = await cancel_delivery_use_case.execute(command)

        if not result.cancelled:
            if "not found" in (result.error_message or "").lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result.error_message,
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message,
            )

        return CancelDeliveryResponse(
            delivery_id=result.delivery_id,
            order_id=result.order_id,
            status=result.status,
            cancelled=result.cancelled,
        )

    @router.patch(
        "/trucks/{truck_id}",
        response_model=UpdateTruckResponse,
        summary="Update a truck",
    )
    async def update_truck(
        truck_id: str, request: UpdateTruckRequest
    ) -> UpdateTruckResponse:
        """Update a truck's properties."""
        command = UpdateTruckCommand(
            truck_id=truck_id,
            name=request.name,
            capacity=request.capacity,
            region=request.region,
        )
        result = update_truck_use_case.execute(command)

        if not result.success:
            if "not found" in (result.error_message or "").lower():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=result.error_message,
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error_message,
            )

        return UpdateTruckResponse(
            truck_id=result.truck_id,
            name=result.name,
            capacity=result.capacity,
            region=result.region,
            current_load=result.current_load,
            success=result.success,
        )

    return router
