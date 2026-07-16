import asyncio
import logging
from contextlib import asynccontextmanager

import grpc
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from mmf.examples.service_templates.hybrid_example.application.service import (
    OrderService,
)
from mmf.examples.service_templates.hybrid_example.domain.models import Order, OrderItem
from mmf.examples.service_templates.hybrid_example.infrastructure.adapters import (
    ExternalInventoryAdapter,
    InMemoryOrderRepository,
)
from mmf.examples.service_templates.hybrid_example.proto import (
    hybrid_order_service_pb2,
    hybrid_order_service_pb2_grpc,
)
from mmf.framework.grpc import (
    ObservableGrpcServiceMixin,
    ServiceDefinition,
    UnifiedGrpcServer,
)
from mmf.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf.framework.integration.domain.models import ConnectionConfig, ConnectorType

# Configuration
INVENTORY_CONFIG = ConnectionConfig(
    system_id="inventory-service",
    name="Inventory Service",
    connector_type=ConnectorType.REST_API,
    endpoint_url="http://localhost:8001",
    timeout=5,
)

# Global dependencies
inventory_adapter = RESTAPIAdapter(INVENTORY_CONFIG)
order_repo = InMemoryOrderRepository()
inventory_service = ExternalInventoryAdapter(inventory_adapter)
order_service = OrderService(order_repo, inventory_service)


# FastAPI Models
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


class BatchOrderRequest(BaseModel):
    order_ids: list[str]


class BatchOrderResponse(BaseModel):
    orders: list[OrderResponse]


def _order_to_pb(order: Order) -> hybrid_order_service_pb2.Order:
    """Convert a domain Order to its protobuf representation."""
    pb = hybrid_order_service_pb2.Order(
        order_id=order.order_id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
        created_at=order.to_timestamp(),
    )
    for item in order.items:
        pb.items.append(
            hybrid_order_service_pb2.OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.price,
            )
        )
    return pb


# FastAPI App
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await inventory_adapter.connect()
    yield
    # Shutdown
    await inventory_adapter.disconnect()


app = FastAPI(title="Hybrid Order Service", lifespan=lifespan)


# REST API Endpoints
@app.post("/orders", response_model=OrderResponse)
async def create_order_rest(request: OrderRequest):
    """REST endpoint to create order."""
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
async def get_order_rest(order_id: str):
    """REST endpoint to get order."""
    order = await order_service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderResponse(
        order_id=order.order_id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
    )


@app.post("/orders/batch", response_model=BatchOrderResponse)
async def get_orders_batch_rest(request: BatchOrderRequest):
    """REST endpoint to get multiple orders."""
    orders = await order_service.get_orders_batch(request.order_ids)

    return BatchOrderResponse(
        orders=[
            OrderResponse(
                order_id=order.order_id,
                customer_id=order.customer_id,
                status=order.status,
                total_amount=order.total_amount,
            )
            for order in orders
        ]
    )


@app.get("/health")
async def health_check_rest():
    """REST health check endpoint."""
    inventory_health = await inventory_adapter.health_check()
    return {
        "status": "healthy",
        "dependencies": {"inventory_service": "healthy" if inventory_health else "unhealthy"},
    }


# gRPC Service Implementation
class HybridOrderServiceImpl(
    hybrid_order_service_pb2_grpc.HybridOrderServiceServicer,
    ObservableGrpcServiceMixin,
):
    """gRPC service implementation using generated protobuf stubs."""

    def __init__(
        self, order_service_instance: OrderService, inventory_adapter_instance: RESTAPIAdapter
    ):
        super().__init__()
        self.order_service = order_service_instance
        self.inventory_adapter = inventory_adapter_instance

    async def CreateOrder(self, request, context):
        """gRPC endpoint to create order."""
        try:
            items = [
                OrderItem(product_id=item.product_id, quantity=item.quantity, price=item.price)
                for item in request.items
            ]
            order = Order(customer_id=request.customer_id, items=items)
            created_order = await self.order_service.create_order(order)

            return hybrid_order_service_pb2.CreateOrderResponse(
                order=_order_to_pb(created_order),
                success=True,
            )
        except ValueError as e:
            return hybrid_order_service_pb2.CreateOrderResponse(
                success=False,
                error_message=str(e),
            )
        except Exception as e:
            logging.exception("Failed to create order: %s", e)
            return hybrid_order_service_pb2.CreateOrderResponse(
                success=False,
                error_message="Internal server error",
            )

    async def GetOrder(self, request, context):
        """gRPC endpoint to get order."""
        try:
            order = await self.order_service.get_order(request.order_id)
            if order:
                return hybrid_order_service_pb2.GetOrderResponse(
                    order=_order_to_pb(order),
                    success=True,
                )
            return hybrid_order_service_pb2.GetOrderResponse(
                success=False,
                error_message="Order not found",
            )
        except Exception as e:
            logging.exception("Failed to get order: %s", e)
            return hybrid_order_service_pb2.GetOrderResponse(
                success=False,
                error_message="Internal server error",
            )

    async def BatchGetOrders(self, request, context):
        """gRPC endpoint to get multiple orders."""
        try:
            orders = await self.order_service.get_orders_batch(list(request.order_ids))
            pb_orders = [_order_to_pb(order) for order in orders]
            return hybrid_order_service_pb2.BatchGetOrdersResponse(
                orders=pb_orders,
                success=True,
            )
        except Exception as e:
            logging.exception("Failed to get orders batch: %s", e)
            return hybrid_order_service_pb2.BatchGetOrdersResponse(
                success=False,
                error_message="Internal server error",
            )

    async def HealthCheck(self, request, context):
        """gRPC health check endpoint."""
        inventory_health = await self.inventory_adapter.health_check()
        return hybrid_order_service_pb2.HealthCheckResponse(
            status="healthy",
            dependencies={"inventory_service": "healthy" if inventory_health else "unhealthy"},
        )


# Server runner functions
async def run_grpc_server():
    """Run the gRPC server using the framework's UnifiedGrpcServer."""
    server = UnifiedGrpcServer(port=50051, service_name="hybrid-order-service")

    server.register_service(
        ServiceDefinition(
            name="hybrid-order-service",
            servicer_factory=lambda: HybridOrderServiceImpl(order_service, inventory_adapter),
            registration_func=hybrid_order_service_pb2_grpc.add_HybridOrderServiceServicer_to_server,
        )
    )

    await server.serve()


def run_fastapi_server():
    """Run the FastAPI server."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


async def run_hybrid_servers():
    """Run both servers concurrently."""
    await inventory_adapter.connect()

    try:
        # Run both servers concurrently
        await asyncio.gather(
            run_grpc_server(), asyncio.create_task(asyncio.to_thread(run_fastapi_server))
        )
    finally:
        await inventory_adapter.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Choose how to run:
    # 1. Both servers (hybrid mode)
    # asyncio.run(run_hybrid_servers())

    # 2. Just FastAPI (for development)
    run_fastapi_server()

    # 3. Just gRPC (uncomment below)
    # asyncio.run(run_grpc_server())
