"""
Enhanced Event Bus and Workflow Integration Example

This example demonstrates how to use the enhanced event bus, workflow engine,
and plugin subscription system together in a real application scenario.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Import the enhanced components
from mmf.framework.events.enhanced_event_bus import (
    EnhancedEventBus,
    EventFilter,
    EventPriority,
    PersistenceBase,
    enhanced_event_bus_context,
)
from mmf.framework.events.enhanced_events import (
    DomainEvent,
    IntegrationEvent,
    create_domain_event,
    create_integration_event,
    create_workflow_event,
)
from mmf.framework.infrastructure.plugin_config import PluginConfig

# from mmf.framework.plugins.event_subscription import (
#     PluginConfig,
#     PluginEventSubscriptionManager,
#     PluginSubscriptionBase,
#     create_event_filter,
#     plugin_subscription_manager_context,
#     register_plugin_with_events,
# )
from mmf.framework.workflow.application.engine import WorkflowEngine
from mmf.framework.workflow.domain.entities import StepResult, WorkflowContext

# --- MOCK CLASSES FOR MISSING COMPONENTS ---
# These components were removed or refactored.
# This example is kept for reference but will not run as-is.

class PluginEventSubscriptionManager:
    async def subscribe(self, *args, **kwargs): pass
    async def get_all_plugin_metrics(self): return {'global_metrics': {}, 'plugin_metrics': {}}
class PluginSubscriptionBase:
    metadata = type('Metadata', (), {'create_all': lambda *args: None})()
def create_event_filter(*args, **kwargs): pass
def plugin_subscription_manager_context(*args, **kwargs):
    class Context:
        async def __aenter__(self): return PluginEventSubscriptionManager()
        async def __aexit__(self, *args): pass
    return Context()
async def register_plugin_with_events(*args, **kwargs): pass

class WorkflowBase:
    metadata = type('Metadata', (), {'create_all': lambda *args: None})()

def workflow_engine_context(*args, **kwargs):
    class Context:
        async def __aenter__(self): return WorkflowEngine()
        async def __aexit__(self, *args): pass
    return Context()
# -------------------------------------------

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example Domain Events
class OrderCreatedEvent(DomainEvent):
    """Event published when an order is created."""

    def __init__(self, order_id: str, customer_id: str, total_amount: float, **kwargs):
        super().__init__(
            aggregate_id=order_id,
            aggregate_type="Order",
            **kwargs
        )
        self.customer_id = customer_id
        self.total_amount = total_amount

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "customer_id": self.customer_id,
            "total_amount": self.total_amount
        })
        return base_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderCreatedEvent":
        return cls(
            order_id=data["aggregate_id"],
            customer_id=data["customer_id"],
            total_amount=data["total_amount"],
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class PaymentProcessedEvent(DomainEvent):
    """Event published when payment is processed."""

    def __init__(self, payment_id: str, order_id: str, amount: float, status: str, **kwargs):
        super().__init__(
            aggregate_id=payment_id,
            aggregate_type="Payment",
            **kwargs
        )
        self.order_id = order_id
        self.amount = amount
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "order_id": self.order_id,
            "amount": self.amount,
            "status": self.status
        })
        return base_dict

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaymentProcessedEvent":
        return cls(
            payment_id=data["aggregate_id"],
            order_id=data["order_id"],
            amount=data["amount"],
            status=data["status"],
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


# Example Workflow Steps
async def create_order_step(context: WorkflowContext) -> StepResult:
    """Create an order in the system."""
    logger.info(f"Creating order for workflow {context.workflow_id}")

    # Simulate order creation
    order_id = f"order-{context.workflow_id}"
    customer_id = context.data.get("customer_id", "unknown")
    total_amount = context.data.get("total_amount", 0.0)

    # Store order details in context
    context.data["order_id"] = order_id
    context.data["order_status"] = "created"

    return StepResult(
        success=True,
        data={
            "order_id": order_id,
            "customer_id": customer_id,
            "total_amount": total_amount
        }
    )


async def process_payment_step(context: WorkflowContext) -> StepResult:
    """Process payment for the order."""
    logger.info(f"Processing payment for workflow {context.workflow_id}")

    order_id = context.data.get("order_id")
    total_amount = context.data.get("total_amount", 0.0)

    # Simulate payment processing
    payment_id = f"payment-{context.workflow_id}"

    # Simulate success/failure based on amount
    if total_amount > 1000:
        return StepResult(
            success=False,
            error="Payment amount too high",
            should_retry=True,
            retry_delay=timedelta(seconds=5)
        )

    context.data["payment_id"] = payment_id
    context.data["payment_status"] = "processed"

    return StepResult(
        success=True,
        data={
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": total_amount,
            "status": "processed"
        }
    )


async def fulfill_order_step(context: WorkflowContext) -> StepResult:
    """Fulfill the order."""
    logger.info(f"Fulfilling order for workflow {context.workflow_id}")

    order_id = context.data.get("order_id")

    # Simulate fulfillment
    context.data["fulfillment_status"] = "fulfilled"
    context.data["tracking_number"] = f"track-{context.workflow_id}"

    return StepResult(
        success=True,
        data={
            "order_id": order_id,
            "fulfillment_status": "fulfilled",
            "tracking_number": f"track-{context.workflow_id}"
        }
    )


def payment_decision_logic(context: WorkflowContext) -> str:
    """Decide on payment method based on amount."""
    total_amount = context.data.get("total_amount", 0.0)

    if total_amount > 500:
        return "credit_card"
    elif total_amount > 100:
        return "debit_card"
    else:
        return "digital_wallet"


# Plugin Event Handlers
async def order_notification_handler(event: DomainEvent) -> None:
    """Handle order events for notifications."""
    if isinstance(event, OrderCreatedEvent):
        logger.info(f"📬 Sending order confirmation email for order {event.aggregate_id}")
        logger.info(f"   Customer: {event.customer_id}, Amount: ${event.total_amount}")


async def inventory_management_handler(event: DomainEvent) -> None:
    """Handle order events for inventory management."""
    if isinstance(event, OrderCreatedEvent):
        logger.info(f"📦 Reserving inventory for order {event.aggregate_id}")
        logger.info(f"   Amount: ${event.total_amount}")


async def payment_notification_handler(event: DomainEvent) -> None:
    """Handle payment events for notifications."""
    if isinstance(event, PaymentProcessedEvent):
        logger.info(f"💳 Payment processed notification for payment {event.aggregate_id}")
        logger.info(f"   Order: {event.order_id}, Amount: ${event.amount}, Status: {event.status}")


async def analytics_handler(event: DomainEvent) -> None:
    """Handle all events for analytics."""
    logger.info(f"📊 Analytics: Recording event {event.event_type} for {event.aggregate_type} {event.aggregate_id}")


class OrderProcessingService:
    """Example service that orchestrates order processing using events and workflows."""

    def __init__(
        self,
        event_bus: EnhancedEventBus,
        workflow_engine: WorkflowEngine,
        plugin_manager: PluginEventSubscriptionManager
    ):
        self.event_bus = event_bus
        self.workflow_engine = workflow_engine
        self.plugin_manager = plugin_manager

    async def process_order(self, customer_id: str, total_amount: float) -> str:
        """Start order processing workflow."""
        logger.info(f"🛒 Starting order processing for customer {customer_id}, amount ${total_amount}")

        workflow_id = f"order-workflow-{datetime.now().timestamp()}"

        # Define steps for this workflow
        steps = [
            create_order_step,
            process_payment_step,
            fulfill_order_step
        ]

        # Start workflow
        # Note: The new WorkflowEngine executes steps sequentially immediately
        context = await self.workflow_engine.start_workflow(
            workflow_id=workflow_id,
            steps=steps,
            initial_data={
                "customer_id": customer_id,
                "total_amount": total_amount
            }
        )

        logger.info(f"✅ Completed order processing workflow {workflow_id}")
        return workflow_id

    async def publish_order_created(self, order_id: str, customer_id: str, total_amount: float) -> None:
        """Publish order created event."""
        event = OrderCreatedEvent(
            order_id=order_id,
            customer_id=customer_id,
            total_amount=total_amount
        )

        await self.event_bus.publish(event, priority=EventPriority.HIGH)
        logger.info(f"📢 Published OrderCreatedEvent for order {order_id}")

    async def publish_payment_processed(self, payment_id: str, order_id: str, amount: float, status: str) -> None:
        """Publish payment processed event."""
        event = PaymentProcessedEvent(
            payment_id=payment_id,
            order_id=order_id,
            amount=amount,
            status=status
        )

        await self.event_bus.publish(event, priority=EventPriority.HIGH)
        logger.info(f"📢 Published PaymentProcessedEvent for payment {payment_id}")


async def setup_plugins(plugin_manager: PluginEventSubscriptionManager) -> None:
    """Set up plugin subscriptions."""

    # Register notification plugin
    notification_config = PluginConfig(
        plugin_id="notification-service",
        plugin_name="Notification Service",
        plugin_version="1.0.0",
        description="Handles order and payment notifications",
        author="MMF Team",
        max_concurrent_events=10
    )

    notification_subscriptions = [
        (create_event_filter(event_types=["OrderCreatedEvent"]), order_notification_handler),
        (create_event_filter(event_types=["PaymentProcessedEvent"]), payment_notification_handler)
    ]

    await register_plugin_with_events(plugin_manager, notification_config, notification_subscriptions)

    # Register inventory plugin
    inventory_config = PluginConfig(
        plugin_id="inventory-service",
        plugin_name="Inventory Management Service",
        plugin_version="1.0.0",
        description="Handles inventory reservations and updates",
        author="MMF Team",
        max_concurrent_events=5
    )

    inventory_subscriptions = [
        (create_event_filter(event_types=["OrderCreatedEvent"]), inventory_management_handler)
    ]

    await register_plugin_with_events(plugin_manager, inventory_config, inventory_subscriptions)

    # Register analytics plugin
    analytics_config = PluginConfig(
        plugin_id="analytics-service",
        plugin_name="Analytics Service",
        plugin_version="1.0.0",
        description="Collects analytics data from all events",
        author="MMF Team",
        max_concurrent_events=20,
        tags=["analytics", "reporting"]
    )

    analytics_subscriptions = [
        (create_event_filter(event_types=["*"]), analytics_handler)  # Subscribe to all events
    ]

    await register_plugin_with_events(plugin_manager, analytics_config, analytics_subscriptions)


async def workflow_event_handler(event: DomainEvent) -> None:
    """Handle workflow events."""
    if hasattr(event, 'workflow_id'):
        logger.info(f"🔄 Workflow Event: {event.event_type} for workflow {event.workflow_id}")


async def main():
    """Main example demonstrating the integrated system."""
    logger.info("🚀 Starting Enhanced Event Bus and Workflow Integration Example")

    # Set up database (in-memory for this example)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create all tables

    async with engine.begin() as conn:
        await conn.run_sync(PersistenceBase.metadata.create_all)
        await conn.run_sync(WorkflowBase.metadata.create_all)
        await conn.run_sync(PluginSubscriptionBase.metadata.create_all)

    # Start the integrated system
    async with enhanced_event_bus_context(
        session_factory=async_session_factory,
        processing_interval=1.0,
        batch_size=10
    ) as event_bus:

        async with workflow_engine_context(
            event_bus=event_bus,
            session_factory=async_session_factory,
            processing_interval=2.0
        ) as workflow_engine:

            async with plugin_subscription_manager_context(
                event_bus=event_bus,
                session_factory=async_session_factory,
                health_check_interval=30.0
            ) as plugin_manager:

                # Set up plugins
                await setup_plugins(plugin_manager)

                # Subscribe to workflow events
                workflow_filter = create_event_filter(event_types=["WorkflowStarted", "WorkflowCompleted", "WorkflowFailed"])
                await plugin_manager.subscribe(
                    plugin_id="system",
                    event_filter=workflow_filter,
                    handler_func=workflow_event_handler
                )

                # Create order processing service
                service = OrderProcessingService(event_bus, workflow_engine, plugin_manager)

                # Process multiple orders
                orders = [
                    ("customer-001", 299.99),
                    ("customer-002", 749.50),
                    ("customer-003", 1299.99),  # This will fail due to high amount
                    ("customer-004", 89.99),
                ]

                workflow_ids = []

                for customer_id, amount in orders:
                    try:
                        workflow_id = await service.process_order(customer_id, amount)
                        workflow_ids.append(workflow_id)

                        # Publish additional events
                        order_id = f"order-{workflow_id}"
                        await service.publish_order_created(order_id, customer_id, amount)
                    except Exception as e:
                        logger.error(f"Workflow failed for customer {customer_id}: {e}")

                    # Small delay between orders
                    await asyncio.sleep(1)

                # Get plugin metrics
                logger.info("\n📈 Plugin Metrics:")
                all_metrics = await plugin_manager.get_all_plugin_metrics()

                logger.info(f"Global Metrics: {all_metrics['global_metrics']}")

                for plugin_id, metrics in all_metrics['plugin_metrics'].items():
                    logger.info(f"  {plugin_id}:")
                    logger.info(f"    Events Received: {metrics['events_received']}")
                    logger.info(f"    Events Processed: {metrics['events_processed']}")
                    logger.info(f"    Events Failed: {metrics['events_failed']}")
                    logger.info(f"    Failure Rate: {metrics['failure_rate']:.2%}")

                # Get event bus metrics
                logger.info("\n📊 Event Bus Metrics:")
                bus_metrics = event_bus.get_metrics()
                for key, value in bus_metrics.items():
                    logger.info(f"  {key}: {value}")

                # Demonstrate dead letter queue
                logger.info("\n🔍 Checking Dead Letter Queue:")
                dead_letters = await event_bus.get_dead_letters(limit=5)
                if dead_letters:
                    logger.info(f"Found {len(dead_letters)} dead letter events")
                    for dl in dead_letters:
                        logger.info(f"  Event {dl.original_event_id}: {dl.failure_reason}")
                else:
                    logger.info("No dead letter events found")

                logger.info("\n✅ Example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
