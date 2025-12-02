import asyncio
import logging
from concurrent import futures
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


# Mock gRPC classes (in production, these would be generated)
class MockOrderItemPb:
    def __init__(self, product_id: str = "", quantity: int = 0, price: float = 0.0):
        self.product_id = product_id
        self.quantity = quantity
        self.price = price


class MockOrderPb:
    def __init__(self):
        self.order_id = ""
        self.customer_id = ""
        self.items = []
        self.status = ""
        self.total_amount = 0.0
        self.created_at = 0


class MockCreateOrderRequest:
    def __init__(self):
        self.customer_id = ""
        self.items = []


class MockCreateOrderResponse:
    def __init__(self):
        self.order = MockOrderPb()
        self.success = False
        self.error_message = ""


class MockGetOrderRequest:
    def __init__(self):
        self.order_id = ""


class MockGetOrderResponse:
    def __init__(self):
        self.order = MockOrderPb()
        self.success = False
        self.error_message = ""


class MockBatchGetOrdersRequest:
    def __init__(self):
        self.order_ids = []


class MockBatchGetOrdersResponse:
    def __init__(self):
        self.orders = []
        self.success = False
        self.error_message = ""


class MockHealthCheckRequest:
    pass


class MockHealthCheckResponse:
    def __init__(self):
        self.status = ""
        self.dependencies = {}


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
class HybridOrderServiceImpl:
    """gRPC service implementation."""

    def __init__(
        self, order_service_instance: OrderService, inventory_adapter_instance: RESTAPIAdapter
    ):
        self.order_service = order_service_instance
        self.inventory_adapter = inventory_adapter_instance

    async def CreateOrder(
        self, request: MockCreateOrderRequest, context
    ) -> MockCreateOrderResponse:
        """gRPC endpoint to create order."""
        try:
            items = [
                OrderItem(product_id=item.product_id, quantity=item.quantity, price=item.price)
                for item in request.items
            ]

            order = Order(customer_id=request.customer_id, items=items)

            created_order = await self.order_service.create_order(order)

            response = MockCreateOrderResponse()
            response.success = True
            response.order.order_id = created_order.order_id
            response.order.customer_id = created_order.customer_id
            response.order.status = created_order.status
            response.order.total_amount = created_order.total_amount
            response.order.created_at = created_order.to_timestamp()

            for item in created_order.items:
                grpc_item = MockOrderItemPb(
                    product_id=item.product_id, quantity=item.quantity, price=item.price
                )
                response.order.items.append(grpc_item)

            return response

        except ValueError as e:
            response = MockCreateOrderResponse()
            response.success = False
            response.error_message = str(e)
            return response
        except Exception as e:
            logging.exception("Failed to create order: %s", e)
            response = MockCreateOrderResponse()
            response.success = False
            response.error_message = "Internal server error"
            return response

    async def GetOrder(self, request: MockGetOrderRequest, context) -> MockGetOrderResponse:
        """gRPC endpoint to get order."""
        try:
            order = await self.order_service.get_order(request.order_id)
            response = MockGetOrderResponse()

            if order:
                response.success = True
                response.order.order_id = order.order_id
                response.order.customer_id = order.customer_id
                response.order.status = order.status
                response.order.total_amount = order.total_amount
                response.order.created_at = order.to_timestamp()

                for item in order.items:
                    grpc_item = MockOrderItemPb(
                        product_id=item.product_id, quantity=item.quantity, price=item.price
                    )
                    response.order.items.append(grpc_item)
            else:
                response.success = False
                response.error_message = "Order not found"

            return response

        except Exception as e:
            logging.exception("Failed to get order: %s", e)
            response = MockGetOrderResponse()
            response.success = False
            response.error_message = "Internal server error"
            return response

    async def BatchGetOrders(
        self, request: MockBatchGetOrdersRequest, context
    ) -> MockBatchGetOrdersResponse:
        """gRPC endpoint to get multiple orders."""
        try:
            orders = await self.order_service.get_orders_batch(list(request.order_ids))
            response = MockBatchGetOrdersResponse()
            response.success = True

            for order in orders:
                grpc_order = MockOrderPb()
                grpc_order.order_id = order.order_id
                grpc_order.customer_id = order.customer_id
                grpc_order.status = order.status
                grpc_order.total_amount = order.total_amount
                grpc_order.created_at = order.to_timestamp()

                for item in order.items:
                    grpc_item = MockOrderItemPb(
                        product_id=item.product_id, quantity=item.quantity, price=item.price
                    )
                    grpc_order.items.append(grpc_item)

                response.orders.append(grpc_order)

            return response

        except Exception as e:
            logging.exception("Failed to get orders batch: %s", e)
            response = MockBatchGetOrdersResponse()
            response.success = False
            response.error_message = "Internal server error"
            return response

    async def HealthCheck(
        self, request: MockHealthCheckRequest, context
    ) -> MockHealthCheckResponse:
        """gRPC health check endpoint."""
        response = MockHealthCheckResponse()
        response.status = "healthy"

        inventory_health = await self.inventory_adapter.health_check()
        response.dependencies["inventory_service"] = "healthy" if inventory_health else "unhealthy"

        return response


# Server runner functions
async def run_grpc_server():
    """Run the gRPC server."""
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add service implementation
    HybridOrderServiceImpl(order_service, inventory_adapter)

    # In production: hybrid_order_service_pb2_grpc.add_HybridOrderServiceServicer_to_server(service_impl, server)

    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)

    logging.info("Starting gRPC server on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


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
