"""
Complete E-commerce Order Processing Example

Demonstrates a real-world e-commerce order processing workflow using:
- Multiple messaging patterns (pub/sub, request/response, saga)
- Different backends for different requirements
- Distributed transaction coordination with Saga pattern
- Error handling and compensation logic
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from mmf.core.application.base import Command
from mmf.core.messaging import BackendType as MessageBackendType
from mmf.framework.messaging.application.saga import create_distributed_saga_manager
from mmf.framework.messaging.domain.extended import MessageMetadata
from mmf.framework.patterns.event_streaming.saga import (
    Saga,
    SagaManager,
    SagaOrchestrator,
    SagaStep,
    create_compensation_action,
    create_saga_step,
)


# --- MOCK CLASSES FOR MISSING COMPONENTS ---
# These components were removed or refactored.
# This example is kept for reference but will not run as-is.
class NATSBackend: pass
class NATSConfig: pass
def create_unified_event_bus(*args): pass
# -------------------------------------------

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderSaga(Saga):
    """Order processing saga with compensation logic."""

    def _initialize_steps(self) -> None:
        """Initialize saga steps."""
        self.create_step(
            step_name="validate_order",
            command=Command(type="validate_order", data={}),
            compensation_action=create_compensation_action(
                action_type="cancel_order_validation",
                command=Command(type="cancel_order_validation", data={})
            )
        )

        self.create_step(
            step_name="reserve_inventory",
            command=Command(type="reserve_items", data={}),
            compensation_action=create_compensation_action(
                action_type="release_reservation",
                command=Command(type="release_reservation", data={})
            )
        )

        self.create_step(
            step_name="process_payment",
            command=Command(type="charge_payment", data={}),
            compensation_action=create_compensation_action(
                action_type="refund_payment",
                command=Command(type="refund_payment", data={})
            )
        )

        self.create_step(
            step_name="ship_order",
            command=Command(type="create_shipment", data={}),
            compensation_action=create_compensation_action(
                action_type="cancel_shipment",
                command=Command(type="cancel_shipment", data={})
            )
        )

    def get_saga_state(self):
        return {
            "saga_id": self.saga_id,
            "status": self.status.value,
            "context": self.context.to_dict(),
            "steps": [s.step_name for s in self.steps]
        }


class OrderService:
    """Order service handling order validation and management."""

    def __init__(self, event_bus):
        self.event_bus = event_bus

    async def start(self):
        """Start order service."""
        # Handle order commands
        await self.event_bus.handle_commands(
            command_types=["validate_order", "cancel_order_validation"],
            handler=self.handle_order_command,
            service_name="order_service"
        )

        # Handle order queries
        await self.event_bus.handle_queries(
            query_types=["get_order_status"],
            handler=self.handle_order_query,
            service_name="order_service"
        )

        logger.info("Order service started")

    async def handle_order_command(self, command_type: str, data: Any, metadata: MessageMetadata) -> bool:
        """Handle order-related commands."""
        try:
            if command_type == "validate_order":
                return await self.validate_order(data)
            elif command_type == "cancel_order_validation":
                return await self.cancel_order_validation(data)
            return False
        except Exception as e:
            logger.error(f"Error handling order command {command_type}: {e}")
            return False

    async def handle_order_query(self, query_type: str, data: Any, metadata: MessageMetadata) -> Any:
        """Handle order-related queries."""
        try:
            if query_type == "get_order_status":
                return await self.get_order_status(data)
            return None
        except Exception as e:
            logger.error(f"Error handling order query {query_type}: {e}")
            return None

    async def validate_order(self, data: dict) -> bool:
        """Validate order details."""
        order_data = data.get("context", {})
        logger.info(f"Validating order: {order_data.get('order_id')}")

        # Simulate validation logic
        await asyncio.sleep(1)

        # Publish order validated event
        await self.event_bus.publish_event(
            event_type="order_validated",
            data={
                "order_id": order_data.get("order_id"),
                "customer_id": order_data.get("customer_id"),
                "validated_at": datetime.utcnow().isoformat()
            }
        )

        return {"success": True, "validation_id": "val-123"}

    async def cancel_order_validation(self, data: dict) -> bool:
        """Cancel order validation (compensation)."""
        logger.info(f"Cancelling order validation for saga: {data.get('saga_id')}")

        # Publish compensation event
        await self.event_bus.publish_event(
            event_type="order_validation_cancelled",
            data={"saga_id": data.get("saga_id")}
        )

        return True

    async def get_order_status(self, data: dict) -> dict:
        """Get order status."""
        return {
            "order_id": data.get("order_id"),
            "status": "processing",
            "updated_at": datetime.utcnow().isoformat()
        }


class InventoryService:
    """Inventory service handling stock management."""

    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.inventory = {"item-1": 100, "item-2": 50}  # Simple inventory

    async def start(self):
        """Start inventory service."""
        await self.event_bus.handle_commands(
            command_types=["reserve_items", "release_reservation"],
            handler=self.handle_inventory_command,
            service_name="inventory_service"
        )
        logger.info("Inventory service started")

    async def handle_inventory_command(self, command_type: str, data: Any, metadata: MessageMetadata) -> bool:
        """Handle inventory commands."""
        try:
            if command_type == "reserve_items":
                return await self.reserve_items(data)
            elif command_type == "release_reservation":
                return await self.release_reservation(data)
            return False
        except Exception as e:
            logger.error(f"Error handling inventory command {command_type}: {e}")
            return False

    async def reserve_items(self, data: dict) -> bool:
        """Reserve inventory items."""
        order_data = data.get("context", {})
        items = order_data.get("items", [])

        logger.info(f"Reserving items: {items}")

        # Check availability
        for item in items:
            item_id = item.get("id")
            quantity = item.get("quantity", 0)

            if self.inventory.get(item_id, 0) < quantity:
                logger.error(f"Insufficient inventory for item: {item_id}")
                return {"success": False, "error": "Insufficient inventory"}

        # Reserve items
        for item in items:
            item_id = item.get("id")
            quantity = item.get("quantity", 0)
            self.inventory[item_id] -= quantity

        # Publish inventory reserved event
        await self.event_bus.publish_event(
            event_type="inventory_reserved",
            data={
                "order_id": order_data.get("order_id"),
                "items": items,
                "reserved_at": datetime.utcnow().isoformat()
            }
        )

        return {"success": True, "reservation_id": "res-456"}

    async def release_reservation(self, data: dict) -> bool:
        """Release inventory reservation (compensation)."""
        logger.info(f"Releasing inventory reservation for saga: {data.get('saga_id')}")

        # In real implementation, would restore reserved quantities
        await self.event_bus.publish_event(
            event_type="inventory_reservation_released",
            data={"saga_id": data.get("saga_id")}
        )

        return True


class PaymentService:
    """Payment service handling payment processing."""

    def __init__(self, event_bus):
        self.event_bus = event_bus

    async def start(self):
        """Start payment service."""
        await self.event_bus.handle_commands(
            command_types=["charge_payment", "refund_payment"],
            handler=self.handle_payment_command,
            service_name="payment_service"
        )
        logger.info("Payment service started")

    async def handle_payment_command(self, command_type: str, data: Any, metadata: MessageMetadata) -> bool:
        """Handle payment commands."""
        try:
            if command_type == "charge_payment":
                return await self.charge_payment(data)
            elif command_type == "refund_payment":
                return await self.refund_payment(data)
            return False
        except Exception as e:
            logger.error(f"Error handling payment command {command_type}: {e}")
            return False

    async def charge_payment(self, data: dict) -> bool:
        """Process payment charge."""
        order_data = data.get("context", {})
        logger.info(f"Processing payment for order: {order_data.get('order_id')}")

        # Simulate payment processing
        await asyncio.sleep(2)

        # Publish payment processed event
        await self.event_bus.publish_event(
            event_type="payment_processed",
            data={
                "order_id": order_data.get("order_id"),
                "amount": order_data.get("total_amount"),
                "transaction_id": "txn-789",
                "processed_at": datetime.utcnow().isoformat()
            }
        )

        return {"success": True, "transaction_id": "txn-789"}

    async def refund_payment(self, data: dict) -> bool:
        """Refund payment (compensation)."""
        logger.info(f"Processing refund for saga: {data.get('saga_id')}")

        await self.event_bus.publish_event(
            event_type="payment_refunded",
            data={"saga_id": data.get("saga_id")}
        )

        return True


class ShippingService:
    """Shipping service handling order shipment."""

    def __init__(self, event_bus):
        self.event_bus = event_bus

    async def start(self):
        """Start shipping service."""
        await self.event_bus.handle_commands(
            command_types=["create_shipment", "cancel_shipment"],
            handler=self.handle_shipping_command,
            service_name="shipping_service"
        )
        logger.info("Shipping service started")

    async def handle_shipping_command(self, command_type: str, data: Any, metadata: MessageMetadata) -> bool:
        """Handle shipping commands."""
        try:
            if command_type == "create_shipment":
                return await self.create_shipment(data)
            elif command_type == "cancel_shipment":
                return await self.cancel_shipment(data)
            return False
        except Exception as e:
            logger.error(f"Error handling shipping command {command_type}: {e}")
            return False

    async def create_shipment(self, data: dict) -> bool:
        """Create shipment for order."""
        order_data = data.get("context", {})
        logger.info(f"Creating shipment for order: {order_data.get('order_id')}")

        # Simulate shipment creation
        await asyncio.sleep(1)

        # Publish order shipped event
        await self.event_bus.publish_event(
            event_type="order_shipped",
            data={
                "order_id": order_data.get("order_id"),
                "tracking_number": "TRK-999",
                "shipped_at": datetime.utcnow().isoformat()
            }
        )

        return {"success": True, "tracking_number": "TRK-999"}

    async def cancel_shipment(self, data: dict) -> bool:
        """Cancel shipment (compensation)."""
        logger.info(f"Cancelling shipment for saga: {data.get('saga_id')}")

        await self.event_bus.publish_event(
            event_type="shipment_cancelled",
            data={"saga_id": data.get("saga_id")}
        )

        return True


class NotificationService:
    """Notification service for order events."""

    def __init__(self, event_bus):
        self.event_bus = event_bus

    async def start(self):
        """Start notification service."""
        await self.event_bus.subscribe_to_events(
            event_types=[
                "order_validated",
                "inventory_reserved",
                "payment_processed",
                "order_shipped",
                "saga.SagaCompleted",
                "saga.SagaFailed"
            ],
            handler=self.handle_notification_event
        )
        logger.info("Notification service started")

    async def handle_notification_event(self, event_type: str, data: Any, metadata: MessageMetadata) -> bool:
        """Handle notification events."""
        try:
            logger.info(f"Sending notification for event: {event_type}")
            logger.info(f"Event data: {data}")

            # In real implementation, would send email/SMS/push notifications

            return True
        except Exception as e:
            logger.error(f"Error handling notification event {event_type}: {e}")
            return False


async def run_ecommerce_example():
    """Run the complete e-commerce example."""
    logger.info("Starting E-commerce Order Processing Example")

    # Setup event bus with Memory backend (simulating NATS/Kafka)
    # In a real scenario, you would use FastStreamBackend with Kafka/NATS
    from mmf.core.messaging import BackendType
    from mmf.framework.events.enhanced_event_bus import EnhancedEventBus
    from mmf.framework.infrastructure.messaging import CommandBus

    # Mock backend for example purposes if FastStreamBackend requires real broker
    # For now we assume we can instantiate components

    command_bus = CommandBus()
    event_bus = EnhancedEventBus() # This would need configuration

    orchestrator = SagaOrchestrator(command_bus, event_bus)
    saga_manager = SagaManager(orchestrator)

    # Register saga
    orchestrator.register_saga_type("order_processing", OrderSaga)

    try:
        # Start services (mocked start)
        order_service = OrderService(event_bus)
        inventory_service = InventoryService(event_bus)
        payment_service = PaymentService(event_bus)
        shipping_service = ShippingService(event_bus)
        notification_service = NotificationService(event_bus)

        await asyncio.gather(
            order_service.start(),
            inventory_service.start(),
            payment_service.start(),
            shipping_service.start(),
            notification_service.start()
        )

        # Give services time to start
        await asyncio.sleep(2)

        # Create and start order processing saga
        order_context = {
            "order_id": "ORD-12345",
            "customer_id": "CUST-67890",
            "items": [
                {"id": "item-1", "quantity": 2, "price": 29.99},
                {"id": "item-2", "quantity": 1, "price": 49.99}
            ],
            "total_amount": 109.97,
            "shipping_address": {
                "street": "123 Main St",
                "city": "Springfield",
                "state": "IL",
                "zip": "62701"
            }
        }

        logger.info("Starting order processing saga...")
        saga_id = await saga_manager.create_and_start_saga(
            saga_type="order_processing",
            initial_data=order_context
        )

        # Monitor saga progress
        for i in range(30):  # Wait up to 30 seconds
            await asyncio.sleep(1)

            # In a real system we would query the orchestrator/repository
            # Here we just wait as the saga runs in background
            logger.info("Saga running...")
            # status = await saga_manager.get_saga_status(saga_id)
            # if status and status.get('status') in ['completed', 'failed', 'compensated']:
            #    break

        logger.info("E-commerce example completed successfully!")

    except Exception as e:
        logger.error(f"Error in e-commerce example: {e}")
        # raise # Don't raise to allow example to finish gracefully if backend missing

    finally:
        # Cleanup
        pass
        await event_bus.stop()


if __name__ == "__main__":
    # Run the example
    asyncio.run(run_ecommerce_example())
