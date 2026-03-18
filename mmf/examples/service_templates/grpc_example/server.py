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
from mmf.examples.service_templates.grpc_example.proto import (
    order_service_pb2,
    order_service_pb2_grpc,
)
from mmf.framework.grpc import (
    ObservableGrpcServiceMixin,
    ServiceDefinition,
    UnifiedGrpcServer,
)
from mmf.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf.framework.integration.domain.models import ConnectionConfig, ConnectorType


def _order_to_pb(order: Order) -> order_service_pb2.Order:
    """Convert a domain Order to its protobuf representation."""
    pb = order_service_pb2.Order(
        order_id=order.order_id,
        customer_id=order.customer_id,
        status=order.status,
        total_amount=order.total_amount,
        created_at=order.to_timestamp(),
    )
    for item in order.items:
        pb.items.append(
            order_service_pb2.OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.price,
            )
        )
    return pb


# gRPC Service Implementation
class OrderServiceImpl(
    order_service_pb2_grpc.OrderServiceServicer,
    ObservableGrpcServiceMixin,
):
    """gRPC service implementation using generated protobuf stubs."""

    def __init__(self, order_service: OrderService, inventory_adapter: RESTAPIAdapter):
        super().__init__()
        self.order_service = order_service
        self.inventory_adapter = inventory_adapter

    async def CreateOrder(self, request, context):
        """Create a new order."""
        try:
            items = [
                OrderItem(product_id=item.product_id, quantity=item.quantity, price=item.price)
                for item in request.items
            ]
            order = Order(customer_id=request.customer_id, items=items)
            created_order = await self.order_service.create_order(order)

            return order_service_pb2.CreateOrderResponse(
                order=_order_to_pb(created_order),
                success=True,
            )
        except ValueError as e:
            return order_service_pb2.CreateOrderResponse(
                success=False,
                error_message=str(e),
            )
        except Exception as e:
            logging.exception("Failed to create order: %s", e)
            return order_service_pb2.CreateOrderResponse(
                success=False,
                error_message="Internal server error",
            )

    async def GetOrder(self, request, context):
        """Get an order by ID."""
        try:
            order = await self.order_service.get_order(request.order_id)
            if order:
                return order_service_pb2.GetOrderResponse(
                    order=_order_to_pb(order),
                    success=True,
                )
            return order_service_pb2.GetOrderResponse(
                success=False,
                error_message="Order not found",
            )
        except Exception as e:
            logging.exception("Failed to get order: %s", e)
            return order_service_pb2.GetOrderResponse(
                success=False,
                error_message="Internal server error",
            )

    async def HealthCheck(self, request, context):
        """Check service health."""
        inventory_health = await self.inventory_adapter.health_check()
        return order_service_pb2.HealthCheckResponse(
            status="healthy",
            dependencies={"inventory_service": "healthy" if inventory_health else "unhealthy"},
        )


# Server setup
async def serve():
    """Start the gRPC server using the framework's UnifiedGrpcServer."""
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
    order_svc = OrderService(order_repo, inventory_service)

    # Connect to external services
    await inventory_adapter.connect()

    try:
        # Create server using the framework
        server = UnifiedGrpcServer(port=50051, service_name="order-service")

        # Register service using ServiceDefinition
        server.register_service(
            ServiceDefinition(
                name="order-service",
                servicer_factory=lambda: OrderServiceImpl(order_svc, inventory_adapter),
                registration_func=order_service_pb2_grpc.add_OrderServiceServicer_to_server,
            )
        )

        await server.serve()
    finally:
        await inventory_adapter.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
