"""FastAPI HTTP Adapter for Store Service.

This is a driving (input) adapter that handles HTTP requests and
translates them into application use case calls.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from examples.petstore_domain.services.store_service.application.use_cases.create_order import (
    CreateOrderCommand,
    CreateOrderUseCase,
)
from examples.petstore_domain.services.store_service.application.use_cases.get_catalog import (
    GetCatalogUseCase,
)
from examples.petstore_domain.services.store_service.application.use_cases.get_order import (
    GetOrderQuery,
    GetOrderUseCase,
)
from examples.petstore_domain.services.store_service.application.use_cases.list_orders import (
    ListOrdersUseCase,
    PaginationQuery,
)
from examples.petstore_domain.services.store_service.domain.exceptions import (
    CatalogItemNotFoundError,
    InsufficientStockError,
    OrderNotFoundError,
)
from mmf.services.identity.integration import require_authenticated_user

# =============================================================================
# Request/Response DTOs
# =============================================================================


class CreateOrderRequest(BaseModel):
    """HTTP request body for creating an order."""

    pet_id: str = Field(..., description="Catalog item ID")
    quantity: int = Field(default=1, gt=0, description="Number of items")
    customer_name: str = Field(..., min_length=1, description="Customer's name")
    delivery_address: Optional[str] = Field(None, description="Delivery address")
    delivery_requested: bool = Field(default=True, description="Whether delivery is requested")


class OrderResponse(BaseModel):
    """HTTP response body for an order."""

    order_id: str
    pet_id: str
    quantity: int
    customer_name: str
    status: str
    total_price: float
    delivery_requested: bool
    delivery_address: Optional[str] = None


class OrderListResponse(BaseModel):
    """HTTP response body for listing orders."""

    orders: list[OrderResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class CatalogItemResponse(BaseModel):
    """HTTP response body for a catalog item."""

    pet_id: str
    name: str
    species: str
    price: float
    quantity: int
    delivery_lead_days: int
    in_stock: bool


class CatalogListResponse(BaseModel):
    """HTTP response body for listing catalog items."""

    items: list[CatalogItemResponse]
    total_count: int


# =============================================================================
# Router Factory
# =============================================================================


def create_store_router(
    create_order_use_case: CreateOrderUseCase,
    get_order_use_case: GetOrderUseCase,
    list_orders_use_case: ListOrdersUseCase,
    get_catalog_use_case: GetCatalogUseCase,
) -> APIRouter:
    """Create a FastAPI router with all store endpoints.

    Args:
        create_order_use_case: Use case for creating orders
        get_order_use_case: Use case for retrieving an order
        list_orders_use_case: Use case for listing all orders
        get_catalog_use_case: Use case for retrieving catalog

    Returns:
        Configured APIRouter with all store endpoints
    """
    router = APIRouter(prefix="/store", tags=["store"])

    @router.get(
        "/catalog",
        response_model=CatalogListResponse,
        summary="Get store catalog",
    )
    async def get_catalog() -> CatalogListResponse:
        """Retrieve all items in the store catalog."""
        result = get_catalog_use_case.execute()

        return CatalogListResponse(
            items=[
                CatalogItemResponse(
                    pet_id=item.pet_id,
                    name=item.name,
                    species=item.species,
                    price=item.price,
                    quantity=item.quantity,
                    delivery_lead_days=item.delivery_lead_days,
                    in_stock=item.in_stock,
                )
                for item in result.items
            ],
            total_count=result.total_count,
        )

    @router.post(
        "/orders",
        response_model=OrderResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create a new order",
    )
    async def create_order(
        request: CreateOrderRequest,
        user: dict = Depends(require_authenticated_user),
    ) -> OrderResponse:
        """Create a new order for a catalog item."""
        command = CreateOrderCommand(
            pet_id=request.pet_id,
            quantity=request.quantity,
            customer_name=request.customer_name,
            delivery_address=request.delivery_address,
            delivery_requested=request.delivery_requested,
        )

        try:
            result = await create_order_use_case.execute(command)
        except CatalogItemNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        except InsufficientStockError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        return OrderResponse(
            order_id=result.order_id,
            pet_id=result.pet_id,
            quantity=result.quantity,
            customer_name=result.customer_name,
            status=result.status,
            total_price=result.total_price,
            delivery_requested=result.delivery_requested,
        )

    @router.get(
        "/orders",
        response_model=OrderListResponse,
        summary="List all orders",
    )
    async def list_orders(
        limit: int = Query(20, ge=1, le=100, description="Maximum number of orders to return"),
        offset: int = Query(0, ge=0, description="Number of orders to skip"),
    ) -> OrderListResponse:
        """Retrieve all orders with pagination."""
        pagination = PaginationQuery(limit=limit, offset=offset)
        result = list_orders_use_case.execute(pagination)
        return OrderListResponse(
            orders=[
                OrderResponse(
                    order_id=str(order.id),
                    pet_id=order.pet_id,
                    quantity=order.quantity,
                    customer_name=order.customer_name,
                    status=order.status.value,
                    total_price=order.total_price.to_float(),
                    delivery_requested=order.delivery_requested,
                    delivery_address=order.delivery_address,
                )
                for order in result.orders
            ],
            total_count=result.total_count,
            limit=result.limit,
            offset=result.offset,
            has_more=result.has_more,
        )

    @router.get(
        "/orders/{order_id}",
        response_model=OrderResponse,
        summary="Get an order by ID",
    )
    async def get_order(order_id: str) -> OrderResponse:
        """Retrieve an order by its unique identifier."""
        query = GetOrderQuery(order_id=order_id)

        try:
            result = get_order_use_case.execute(query)
        except OrderNotFoundError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        return OrderResponse(
            order_id=result.order_id,
            pet_id=result.pet_id,
            quantity=result.quantity,
            customer_name=result.customer_name,
            status=result.status,
            total_price=result.total_price,
            delivery_requested=result.delivery_requested,
            delivery_address=result.delivery_address,
        )

    return router
