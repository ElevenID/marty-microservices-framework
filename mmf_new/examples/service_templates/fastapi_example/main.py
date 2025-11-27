from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from mmf_new.examples.service_templates.fastapi_example.application.service import (
    OrderService,
)
from mmf_new.examples.service_templates.fastapi_example.domain.models import (
    Order,
    OrderItem,
)
from mmf_new.examples.service_templates.fastapi_example.infrastructure.adapters import (
    ExternalInventoryAdapter,
    InMemoryOrderRepository,
)
from mmf_new.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf_new.framework.integration.domain.models import ConnectionConfig, ConnectorType

# Configuration
INVENTORY_CONFIG = ConnectionConfig(
    system_id="inventory-service",
    name="Inventory Service",
    connector_type=ConnectorType.REST_API,
    endpoint_url="http://localhost:8001",  # Mock URL
    timeout=5,
)

# Global dependencies
inventory_adapter = RESTAPIAdapter(INVENTORY_CONFIG)
order_repo = InMemoryOrderRepository()
inventory_service = ExternalInventoryAdapter(inventory_adapter)
order_service = OrderService(order_repo, inventory_service)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await inventory_adapter.connect()
    yield
    # Shutdown
    await inventory_adapter.disconnect()


app = FastAPI(title="Order Service Example", lifespan=lifespan)


# API Models
class OrderItemRequest(BaseModel):
    product_id: str
    quantity: int
    price: float


class OrderRequest(BaseModel):
    customer_id: str
    items: list[OrderItemRequest]


class OrderResponse(BaseModel):
    order_id: str
    customer_id: str
    status: str
    total_amount: float


@app.post("/orders", response_model=OrderResponse)
async def create_order(request: OrderRequest):
    # Map request to domain model
    items = [
        OrderItem(product_id=item.product_id, quantity=item.quantity, price=item.price)
        for item in request.items
    ]

    order = Order(customer_id=request.customer_id, items=items)

    try:
        created_order = await order_service.create_order(order)
        return OrderResponse(
            order_id=created_order.order_id,
            customer_id=created_order.customer_id,
            status=created_order.status,
            total_amount=created_order.total_amount,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str):
    order = await order_service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderResponse(
        order_id=order.order_id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
    )


@app.get("/health")
async def health_check():
    inventory_health = await inventory_adapter.health_check()
    return {
        "status": "healthy",
        "dependencies": {"inventory_service": "healthy" if inventory_health else "unhealthy"},
    }
