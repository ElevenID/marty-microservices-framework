import asyncio
import logging
from concurrent import futures

import grpc

from mmf.examples.service_templates.grpc_example.application.service import OrderService
from mmf.examples.service_templates.grpc_example.domain.models import Order, OrderItem
from mmf.examples.service_templates.grpc_example.infrastructure.adapters import (
    ExternalInventoryAdapter,
    InMemoryOrderRepository,
)
from mmf.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf.framework.integration.domain.models import ConnectionConfig, ConnectorType

# Generated gRPC imports would go here
# from proto import order_service_pb2
# from proto import order_service_pb2_grpc


# Mock protobuf message classes (normally generated from .proto files)
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


class MockHealthCheckRequest:
    pass


class MockHealthCheckResponse:
    def __init__(self):
        self.status = ""
        self.dependencies = {}


# gRPC Service Implementation
class OrderServiceImpl:
    """gRPC service implementation."""

    def __init__(self, order_service: OrderService, inventory_adapter: RESTAPIAdapter):
        self.order_service = order_service
        self.inventory_adapter = inventory_adapter

    async def CreateOrder(
        self, request: MockCreateOrderRequest, context
    ) -> MockCreateOrderResponse:
        """Create a new order."""
        try:
            # Convert gRPC request to domain model
            items = [
                OrderItem(product_id=item.product_id, quantity=item.quantity, price=item.price)
                for item in request.items
            ]

            order = Order(customer_id=request.customer_id, items=items)

            # Process through application service
            created_order = await self.order_service.create_order(order)

            # Convert to gRPC response
            response = MockCreateOrderResponse()
            response.success = True
            response.order.order_id = created_order.order_id
            response.order.customer_id = created_order.customer_id
            response.order.status = created_order.status
            response.order.total_amount = created_order.total_amount
            response.order.created_at = created_order.to_timestamp()

            # Convert items
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
        """Get an order by ID."""
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

                # Convert items
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

    async def HealthCheck(
        self, request: MockHealthCheckRequest, context
    ) -> MockHealthCheckResponse:
        """Check service health."""
        response = MockHealthCheckResponse()
        response.status = "healthy"

        # Check dependencies
        inventory_health = await self.inventory_adapter.health_check()
        response.dependencies["inventory_service"] = "healthy" if inventory_health else "unhealthy"

        return response


# Server setup
async def serve():
    """Start the gRPC server."""
    # Configuration
    inventory_config = ConnectionConfig(
        system_id="inventory-service",
        name="Inventory Service",
        connector_type=ConnectorType.REST_API,
        endpoint_url="http://localhost:8001",
        timeout=5,
    )

    # Dependencies
    inventory_adapter = RESTAPIAdapter(inventory_config)
    order_repo = InMemoryOrderRepository()
    inventory_service = ExternalInventoryAdapter(inventory_adapter)
    order_service = OrderService(order_repo, inventory_service)

    # Connect to external services
    await inventory_adapter.connect()

    try:
        # Create gRPC server
        server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

        # Add service implementation
        OrderServiceImpl(order_service, inventory_adapter)

        # In a real implementation, you would do:
        # order_service_pb2_grpc.add_OrderServiceServicer_to_server(service_impl, server)

        # Configure server
        listen_addr = "[::]:50051"
        server.add_insecure_port(listen_addr)

        logging.info("Starting gRPC server on %s", listen_addr)
        await server.start()
        await server.wait_for_termination()

    finally:
        await inventory_adapter.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
