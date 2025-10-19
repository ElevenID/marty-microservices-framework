"""
Extended Messaging Service for Petstore Domain

This service integrates the extended messaging capabilities (NATS, AWS SNS, Unified Event Bus)
with the petstore domain for enhanced communication patterns and distributed transactions.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any

from marty_msf.framework.messaging.extended import (
    AWSSNSBackend,
    AWSSNSConfig,
    DistributedSagaManager,
    MessageBackendType,
    MessagingPattern,
    NATSBackend,
    NATSConfig,
    UnifiedEventBus,
    create_distributed_saga_manager,
    create_unified_event_bus,
)

try:
    EXTENDED_MESSAGING_AVAILABLE = True
except ImportError:
    EXTENDED_MESSAGING_AVAILABLE = False
    print("Extended messaging not available, using fallback")

logger = logging.getLogger(__name__)


class PetstoreEventType(Enum):
    """Petstore-specific event types for extended messaging"""
    # Inventory events (pub/sub pattern)
    PET_ADDED = "pet_added"
    PET_UPDATED = "pet_updated"
    PET_SOLD = "pet_sold"
    INVENTORY_LOW = "inventory_low"

    # Order events (streaming pattern)
    ORDER_CREATED = "order_created"
    ORDER_CONFIRMED = "order_confirmed"
    ORDER_SHIPPED = "order_shipped"
    ORDER_DELIVERED = "order_delivered"
    ORDER_CANCELLED = "order_cancelled"

    # Customer events (pub/sub pattern)
    CUSTOMER_REGISTERED = "customer_registered"
    CUSTOMER_UPDATED = "customer_updated"
    LOYALTY_POINTS_EARNED = "loyalty_points_earned"

    # System events (point-to-point pattern)
    PAYMENT_PROCESSED = "payment_processed"
    SHIPPING_ARRANGED = "shipping_arranged"
    NOTIFICATION_SENT = "notification_sent"


class PetstoreMessagingPattern(Enum):
    """Messaging patterns specific to petstore operations"""
    INVENTORY_BROADCAST = "inventory_broadcast"  # pub/sub for inventory updates
    ORDER_PROCESSING = "order_processing"        # streaming for order lifecycle
    CUSTOMER_NOTIFICATIONS = "customer_notifications"  # pub/sub for notifications
    PAYMENT_COMMANDS = "payment_commands"        # point-to-point for payments
    ANALYTICS_STREAM = "analytics_stream"        # streaming for analytics


class PetstoreExtendedMessagingService:
    """Extended messaging service for petstore domain operations"""

    def __init__(self):
        self.event_bus: UnifiedEventBus | None = None
        self.saga_manager: DistributedSagaManager | None = None
        self._running = False
        self._backends_configured = False

    async def start(self, config: dict[str, Any] | None = None) -> None:
        """Initialize the extended messaging service"""
        if not EXTENDED_MESSAGING_AVAILABLE:
            logger.warning("Extended messaging not available, service disabled")
            return

        try:
            # Create unified event bus
            self.event_bus = create_unified_event_bus()

            # Configure backends based on config
            await self._configure_backends(config or {})

            # Start event bus
            await self.event_bus.start()

            # Create saga manager
            self.saga_manager = create_distributed_saga_manager(self.event_bus)

            # Register petstore sagas
            await self._register_petstore_sagas()

            self._running = True
            logger.info("Petstore extended messaging service started")

        except Exception as e:
            logger.error(f"Failed to start extended messaging service: {e}")
            raise

    async def stop(self) -> None:
        """Stop the extended messaging service"""
        self._running = False

        if self.event_bus:
            await self.event_bus.stop()

        logger.info("Petstore extended messaging service stopped")

    async def _configure_backends(self, config: dict[str, Any]) -> None:
        """Configure messaging backends based on environment/config"""
        backends_added = 0

        # Configure NATS backend if available
        nats_config = config.get("nats", {})
        if nats_config.get("enabled", True):
            try:
                nats_backend_config = NATSConfig(
                    servers=nats_config.get("servers", ["nats://localhost:4222"]),
                    jetstream_enabled=nats_config.get("jetstream_enabled", True)
                )
                nats_backend = NATSBackend(nats_backend_config)
                self.event_bus.register_backend(MessageBackendType.NATS, nats_backend)
                backends_added += 1
                logger.info("NATS backend configured for petstore messaging")
            except Exception as e:
                logger.warning(f"Failed to configure NATS backend: {e}")

        # Configure AWS SNS backend if available
        sns_config = config.get("aws_sns", {})
        if sns_config.get("enabled", False):
            try:
                sns_backend_config = AWSSNSConfig(
                    region_name=sns_config.get("region_name", "us-east-1"),
                    fifo_topics=sns_config.get("fifo_topics", True)
                )
                sns_backend = AWSSNSBackend(sns_backend_config)
                self.event_bus.register_backend(MessageBackendType.AWS_SNS, sns_backend)
                backends_added += 1
                logger.info("AWS SNS backend configured for petstore messaging")
            except Exception as e:
                logger.warning(f"Failed to configure AWS SNS backend: {e}")

        self._backends_configured = backends_added > 0
        if not self._backends_configured:
            logger.warning("No extended messaging backends configured")

    async def _register_petstore_sagas(self) -> None:
        """Register petstore-specific sagas"""
        if not self.saga_manager:
            return

        # Order processing saga
        order_saga_definition = {
            "name": "petstore_order_processing",
            "steps": [
                {
                    "name": "validate_inventory",
                    "service": "inventory_service",
                    "command": "reserve_pet",
                    "compensation": "release_pet_reservation"
                },
                {
                    "name": "process_payment",
                    "service": "payment_service",
                    "command": "charge_customer",
                    "compensation": "refund_payment"
                },
                {
                    "name": "arrange_shipping",
                    "service": "shipping_service",
                    "command": "schedule_delivery",
                    "compensation": "cancel_shipping"
                },
                {
                    "name": "update_inventory",
                    "service": "inventory_service",
                    "command": "mark_pet_sold",
                    "compensation": "restore_pet_availability"
                },
                {
                    "name": "send_confirmation",
                    "service": "notification_service",
                    "command": "send_order_confirmation",
                    "compensation": "send_cancellation_notice"
                }
            ]
        }

        self.saga_manager.register_saga_definition("petstore_order_processing", order_saga_definition)
        logger.info("Registered petstore order processing saga")

    # Event Publishing Methods

    async def publish_inventory_event(self, event_type: PetstoreEventType, pet_data: dict[str, Any]) -> bool:
        """Publish inventory-related events using pub/sub pattern"""
        if not self._is_ready():
            return False

        try:
            await self.event_bus.publish_event(
                event_type=event_type.value,
                data={
                    "pet_id": pet_data.get("pet_id"),
                    "category": pet_data.get("category"),
                    "availability": pet_data.get("availability"),
                    **pet_data
                },
                metadata={
                    "domain": "petstore",
                    "pattern": PetstoreMessagingPattern.INVENTORY_BROADCAST.value,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Published inventory event: {event_type.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish inventory event {event_type.value}: {e}")
            return False

    async def publish_order_event(self, event_type: PetstoreEventType, order_data: dict[str, Any]) -> bool:
        """Publish order events using streaming pattern for analytics"""
        if not self._is_ready():
            return False

        try:
            await self.event_bus.stream_events(
                stream_name="petstore_order_events",
                events=[{
                    "event_type": event_type.value,
                    "order_id": order_data.get("order_id"),
                    "customer_id": order_data.get("customer_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": order_data
                }]
            )
            logger.info(f"Streamed order event: {event_type.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to stream order event {event_type.value}: {e}")
            return False

    async def send_payment_command(self, payment_data: dict[str, Any]) -> bool:
        """Send payment command using point-to-point pattern"""
        if not self._is_ready():
            return False

        try:
            await self.event_bus.send_command(
                command_type="process_payment",
                data=payment_data,
                target_service="payment_service"
            )
            logger.info("Sent payment processing command")
            return True
        except Exception as e:
            logger.error(f"Failed to send payment command: {e}")
            return False

    async def query_inventory_status(self, pet_id: str) -> dict[str, Any] | None:
        """Query inventory status using request/response pattern"""
        if not self._is_ready():
            return None

        try:
            response = await self.event_bus.query(
                query_type="get_pet_availability",
                data={"pet_id": pet_id},
                target_service="inventory_service",
                timeout=5.0
            )
            logger.info(f"Queried inventory for pet {pet_id}")
            return response
        except Exception as e:
            logger.error(f"Failed to query inventory for pet {pet_id}: {e}")
            return None

    async def notify_customer(self, customer_id: str, notification_data: dict[str, Any]) -> bool:
        """Send customer notification using pub/sub pattern"""
        if not self._is_ready():
            return False

        try:
            await self.event_bus.publish_event(
                event_type="customer_notification",
                data={
                    "customer_id": customer_id,
                    "notification_type": notification_data.get("type"),
                    "message": notification_data.get("message"),
                    "channels": notification_data.get("channels", ["email"])
                },
                metadata={
                    "domain": "petstore",
                    "pattern": PetstoreMessagingPattern.CUSTOMER_NOTIFICATIONS.value
                }
            )
            logger.info(f"Sent customer notification to {customer_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send customer notification: {e}")
            return False

    # Saga Operations

    async def start_order_processing_saga(self, order_data: dict[str, Any]) -> str | None:
        """Start the order processing saga for distributed transaction handling"""
        if not self.saga_manager:
            logger.warning("Saga manager not available")
            return None

        try:
            saga_id = await self.saga_manager.create_and_start_saga(
                "petstore_order_processing",
                {
                    "order_id": order_data.get("order_id"),
                    "customer_id": order_data.get("customer_id"),
                    "pet_id": order_data.get("pet_id"),
                    "payment_amount": order_data.get("total_amount"),
                    "shipping_address": order_data.get("shipping_address"),
                    **order_data
                }
            )
            logger.info(f"Started order processing saga: {saga_id}")
            return saga_id
        except Exception as e:
            logger.error(f"Failed to start order processing saga: {e}")
            return None

    async def get_saga_status(self, saga_id: str) -> dict[str, Any] | None:
        """Get the status of a running saga"""
        if not self.saga_manager:
            return None

        try:
            status = await self.saga_manager.get_saga_status(saga_id)
            return status
        except Exception as e:
            logger.error(f"Failed to get saga status for {saga_id}: {e}")
            return None

    def _is_ready(self) -> bool:
        """Check if the service is ready to handle requests"""
        return (
            EXTENDED_MESSAGING_AVAILABLE and
            self._running and
            self.event_bus is not None and
            self._backends_configured
        )

    # High-level Domain Operations

    async def handle_pet_purchase(self, purchase_data: dict[str, Any]) -> dict[str, Any]:
        """Handle a complete pet purchase with extended messaging patterns"""
        if not self._is_ready():
            return {"success": False, "error": "Extended messaging not available"}

        try:
            # 1. Check inventory availability
            pet_id = purchase_data["pet_id"]
            inventory_status = await self.query_inventory_status(pet_id)

            if not inventory_status or not inventory_status.get("available"):
                return {"success": False, "error": "Pet not available"}

            # 2. Start order processing saga
            saga_id = await self.start_order_processing_saga(purchase_data)

            if not saga_id:
                return {"success": False, "error": "Failed to start order processing"}

            # 3. Publish order created event
            await self.publish_order_event(
                PetstoreEventType.ORDER_CREATED,
                purchase_data
            )

            # 4. Send customer notification
            await self.notify_customer(
                purchase_data["customer_id"],
                {
                    "type": "order_confirmation",
                    "message": f"Your order for pet {pet_id} has been received",
                    "channels": ["email", "sms"]
                }
            )

            return {
                "success": True,
                "saga_id": saga_id,
                "order_id": purchase_data["order_id"]
            }

        except Exception as e:
            logger.error(f"Failed to handle pet purchase: {e}")
            return {"success": False, "error": str(e)}

    async def handle_inventory_update(self, pet_data: dict[str, Any]) -> bool:
        """Handle inventory updates with extended messaging"""
        if not self._is_ready():
            return False

        # Publish inventory update event
        await self.publish_inventory_event(
            PetstoreEventType.PET_UPDATED,
            pet_data
        )

        # Check for low inventory and alert if needed
        if pet_data.get("quantity", 0) < 5:
            await self.publish_inventory_event(
                PetstoreEventType.INVENTORY_LOW,
                {
                    "pet_id": pet_data["pet_id"],
                    "current_quantity": pet_data.get("quantity", 0),
                    "threshold": 5
                }
            )

        return True


# Factory function for easy integration
def create_petstore_extended_messaging_service(config: dict[str, Any] | None = None) -> PetstoreExtendedMessagingService:
    """Create and configure a petstore extended messaging service"""
    service = PetstoreExtendedMessagingService()
    return service
