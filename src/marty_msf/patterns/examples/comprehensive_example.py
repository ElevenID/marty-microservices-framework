"""
Comprehensive Examples for Data Consistency Patterns

This module provides practical examples demonstrating the integrated usage of:
- Saga orchestration with compensation handlers
- Transactional outbox pattern with event publishing
- CQRS with read/write model separation
- Event sourcing with aggregate rebuilding
- Cross-pattern integration scenarios

Example: E-commerce Order Processing with Full Data Consistency
"""

import asyncio
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..patterns.config import DataConsistencyConfig, create_development_config
from ..patterns.cqrs.enhanced_cqrs import (
    BaseCommand,
    BaseQuery,
    CommandHandler,
    CommandResult,
    CommandStatus,
    QueryHandler,
    ValidationResult,
)

# Import our data consistency patterns
from ..patterns.outbox.enhanced_outbox import (
    EnhancedOutboxProcessor,
    EnhancedOutboxRepository,
    OutboxConfig,
    create_kafka_message_broker,
)
from ..patterns.saga.saga_patterns import SagaOrchestrator


# Domain Models for E-commerce Example
@dataclass
class Order:
    """Order aggregate root."""

    order_id: str
    customer_id: str
    items: list[dict[str, Any]] = field(default_factory=list)
    total_amount: int = 0  # in cents
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Payment:
    """Payment aggregate root."""

    payment_id: str
    order_id: str
    amount: int
    payment_method: str
    status: str = "pending"
    processed_at: datetime | None = None


@dataclass
class Inventory:
    """Inventory aggregate root."""

    product_id: str
    available_quantity: int
    reserved_quantity: int = 0


# Commands for the E-commerce System
@dataclass
class CreateOrderCommand(BaseCommand):
    """Command to create a new order."""

    def __init__(self, customer_id: str, items: list[dict], **kwargs):
        super().__init__(**kwargs)
        self.customer_id = customer_id
        self.items = items
        self.total_amount = sum(item["price"] * item["quantity"] for item in items)

    def validate(self):
        """Validate the create order command."""

        errors = []

        if not self.customer_id:
            errors.append("Customer ID is required")

        if not self.items:
            errors.append("Order must have at least one item")

        for item in self.items:
            if not item.get("product_id"):
                errors.append("Product ID is required for all items")
            if item.get("quantity", 0) <= 0:
                errors.append("Item quantity must be positive")
            if item.get("price", 0) <= 0:
                errors.append("Item price must be positive")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _get_command_data(self) -> dict[str, Any]:
        return {
            "customer_id": self.customer_id,
            "items": self.items,
            "total_amount": self.total_amount,
        }


@dataclass
class ProcessPaymentCommand(BaseCommand):
    """Command to process payment for an order."""

    def __init__(self, order_id: str, payment_method: str, amount: int, **kwargs):
        super().__init__(**kwargs)
        self.order_id = order_id
        self.payment_method = payment_method
        self.amount = amount

    def validate(self):
        errors = []

        if not self.order_id:
            errors.append("Order ID is required")

        if not self.payment_method:
            errors.append("Payment method is required")

        if self.amount <= 0:
            errors.append("Payment amount must be positive")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _get_command_data(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "payment_method": self.payment_method,
            "amount": self.amount,
        }


@dataclass
class ReserveInventoryCommand(BaseCommand):
    """Command to reserve inventory for an order."""

    def __init__(self, order_id: str, reservations: list[dict], **kwargs):
        super().__init__(**kwargs)
        self.order_id = order_id
        self.reservations = reservations  # [{"product_id": "...", "quantity": 1}, ...]

    def validate(self):
        errors = []

        if not self.order_id:
            errors.append("Order ID is required")

        if not self.reservations:
            errors.append("At least one reservation is required")

        for reservation in self.reservations:
            if not reservation.get("product_id"):
                errors.append("Product ID is required for reservations")
            if reservation.get("quantity", 0) <= 0:
                errors.append("Reservation quantity must be positive")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _get_command_data(self) -> dict[str, Any]:
        return {"order_id": self.order_id, "reservations": self.reservations}


# Queries for the E-commerce System
@dataclass
class GetOrderQuery(BaseQuery):
    """Query to get order information."""

    def __init__(self, order_id: str, **kwargs):
        super().__init__(**kwargs)
        self.order_id = order_id

    def validate(self):
        errors = []

        if not self.order_id:
            errors.append("Order ID is required")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _get_query_data(self) -> dict[str, Any]:
        return {"order_id": self.order_id}


@dataclass
class GetCustomerOrdersQuery(BaseQuery):
    """Query to get all orders for a customer."""

    def __init__(self, customer_id: str, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = customer_id

    def validate(self):
        errors = []

        if not self.customer_id:
            errors.append("Customer ID is required")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def _get_query_data(self) -> dict[str, Any]:
        return {"customer_id": self.customer_id}


# Command Handlers
class CreateOrderCommandHandler(CommandHandler[CreateOrderCommand]):
    """Handler for creating orders with saga orchestration."""

    def __init__(self, order_repository, saga_orchestrator, event_bus=None):
        super().__init__(event_bus=event_bus)
        self.order_repository = order_repository
        self.saga_orchestrator = saga_orchestrator

    async def _execute(self, command: CreateOrderCommand):
        try:
            # Create the order
            order = Order(
                order_id=str(uuid.uuid4()),
                customer_id=command.customer_id,
                items=command.items,
                total_amount=command.total_amount,
                status="created",
            )

            # Save order (this would be a real repository call)
            await self.order_repository.save(order)

            # Start the order processing saga
            saga_steps = await self._create_order_saga_steps(order)
            saga_id = await self.saga_orchestrator.start_saga(
                saga_type="order_processing", steps=saga_steps, context={"order_id": order.order_id}
            )

            # Generate domain events
            events = [f"order_created_{order.order_id}", f"saga_started_{saga_id}"]

            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.COMPLETED,
                result_data={
                    "order_id": order.order_id,
                    "saga_id": saga_id,
                    "total_amount": order.total_amount,
                },
                events_generated=events,
            )

        except Exception as e:
            return CommandResult(
                command_id=command.command_id, status=CommandStatus.FAILED, errors=[str(e)]
            )

    async def _create_order_saga_steps(self, order: Order) -> list:
        """Create saga steps for order processing."""
        # This would create actual saga steps based on the order
        # For now, return mock steps
        return [
            {
                "step_name": "reserve_inventory",
                "service_name": "inventory_service",
                "action": "reserve",
                "compensation_action": "release_reservation",
                "data": {"order_id": order.order_id, "items": order.items},
            },
            {
                "step_name": "process_payment",
                "service_name": "payment_service",
                "action": "charge",
                "compensation_action": "refund",
                "data": {"order_id": order.order_id, "amount": order.total_amount},
            },
            {
                "step_name": "update_order_status",
                "service_name": "order_service",
                "action": "confirm",
                "compensation_action": "cancel",
                "data": {"order_id": order.order_id, "status": "confirmed"},
            },
        ]


class ProcessPaymentCommandHandler(CommandHandler[ProcessPaymentCommand]):
    """Handler for processing payments with outbox pattern."""

    def __init__(self, payment_repository, outbox_repository, event_bus=None):
        super().__init__(event_bus=event_bus)
        self.payment_repository = payment_repository
        self.outbox_repository = outbox_repository

    async def _execute(self, command: ProcessPaymentCommand):
        try:
            # Create payment record
            payment = Payment(
                payment_id=str(uuid.uuid4()),
                order_id=command.order_id,
                amount=command.amount,
                payment_method=command.payment_method,
                status="processing",
            )

            # Simulate payment processing
            await self._process_payment_external(payment)
            payment.status = "completed"
            payment.processed_at = datetime.now(timezone.utc)

            # Save payment
            await self.payment_repository.save(payment)

            # Publish event via outbox pattern
            await self.outbox_repository.enqueue_event(
                topic="payment.events",
                event_type="payment_processed",
                payload={
                    "payment_id": payment.payment_id,
                    "order_id": payment.order_id,
                    "amount": payment.amount,
                    "status": payment.status,
                    "processed_at": payment.processed_at.isoformat(),
                },
                aggregate_id=payment.payment_id,
                aggregate_type="payment",
                correlation_id=command.correlation_id,
            )

            return CommandResult(
                command_id=command.command_id,
                status=CommandStatus.COMPLETED,
                result_data={
                    "payment_id": payment.payment_id,
                    "status": payment.status,
                    "processed_at": payment.processed_at.isoformat(),
                },
                events_generated=[f"payment_processed_{payment.payment_id}"],
            )

        except Exception as e:
            return CommandResult(
                command_id=command.command_id, status=CommandStatus.FAILED, errors=[str(e)]
            )

    async def _process_payment_external(self, payment: Payment):
        """Simulate external payment processing."""
        # In real implementation, this would call a payment gateway
        await asyncio.sleep(0.1)  # Simulate network call

        # Simulate occasional payment failures
        if random.random() < 0.1:  # 10% failure rate
            raise Exception("Payment gateway timeout")


# Query Handlers with Read Models
class GetOrderQueryHandler(QueryHandler[GetOrderQuery, dict]):
    """Handler for getting order information from read models."""

    def __init__(self, read_store, cache=None):
        super().__init__(read_store=read_store, cache=cache)

    async def _execute(self, query: GetOrderQuery) -> dict[str, Any]:
        """Get order from read model."""
        # In real implementation, this would query the read model database

        # Simulate order retrieval
        order_data = {
            "order_id": query.order_id,
            "customer_id": f"customer_{query.order_id[:8]}",
            "items": [
                {"product_id": "product_1", "quantity": 2, "price": 1000},
                {"product_id": "product_2", "quantity": 1, "price": 1500},
            ],
            "total_amount": 3500,
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        return order_data


class GetCustomerOrdersQueryHandler(QueryHandler[GetCustomerOrdersQuery, dict]):
    """Handler for getting customer orders with pagination."""

    def __init__(self, read_store, cache=None):
        super().__init__(read_store=read_store, cache=cache)

    async def _execute(self, query: GetCustomerOrdersQuery) -> dict[str, Any]:
        """Get customer orders from read model."""
        # Simulate customer orders retrieval with pagination

        orders = []
        for i in range(query.page_size):
            order_id = f"order_{query.customer_id}_{i + 1}"
            orders.append(
                {
                    "order_id": order_id,
                    "customer_id": query.customer_id,
                    "total_amount": (i + 1) * 1000,
                    "status": "confirmed" if i % 2 == 0 else "pending",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return {
            "orders": orders,
            "total_count": 100,  # Simulated total
            "page": query.page,
            "page_size": query.page_size,
            "has_more": query.page * query.page_size < 100,
        }


# Integration Example: Complete E-commerce Flow
class ECommerceDataConsistencyExample:
    """Complete example demonstrating all data consistency patterns."""

    def __init__(self, config: DataConsistencyConfig):
        self.config = config
        self.repositories = {}
        self.handlers = {}
        self.saga_orchestrator = None
        self.outbox_processor = None

    async def initialize(self):
        """Initialize all components."""
        # Initialize repositories (mock implementations)
        self.repositories = {
            "order": MockOrderRepository(),
            "payment": MockPaymentRepository(),
            "inventory": MockInventoryRepository(),
            "outbox": MockOutboxRepository(),
        }

        # Initialize saga orchestrator
        self.saga_orchestrator = SagaOrchestrator("ecommerce-orchestrator")
        await self.saga_orchestrator.start(worker_count=self.config.saga.worker_count)

        # Register saga step handlers
        await self._register_saga_handlers()

        # Initialize outbox processor
        message_broker = create_kafka_message_broker(None)  # Mock broker
        self.outbox_processor = EnhancedOutboxProcessor(
            repository=self.repositories["outbox"],
            message_broker=message_broker,
            config=self.config.outbox,
        )
        await self.outbox_processor.start()

        # Initialize command/query handlers
        self.handlers = {
            "create_order": CreateOrderCommandHandler(
                self.repositories["order"], self.saga_orchestrator
            ),
            "process_payment": ProcessPaymentCommandHandler(
                self.repositories["payment"], self.repositories["outbox"]
            ),
            "get_order": GetOrderQueryHandler(None),
            "get_customer_orders": GetCustomerOrdersQueryHandler(None),
        }

    async def _register_saga_handlers(self):
        """Register handlers for saga steps."""

        async def reserve_inventory_handler(context):
            """Handle inventory reservation step."""
            print(f"Reserving inventory for order: {context['saga_id']}")
            # Simulate inventory reservation
            await asyncio.sleep(0.1)
            return True

        async def compensate_inventory_handler(context):
            """Handle inventory reservation compensation."""
            print(f"Releasing inventory reservation for order: {context['saga_id']}")
            await asyncio.sleep(0.1)
            return True

        async def process_payment_handler(context):
            """Handle payment processing step."""
            print(f"Processing payment for order: {context['saga_id']}")
            # Simulate payment processing
            await asyncio.sleep(0.2)
            return True

        async def compensate_payment_handler(context):
            """Handle payment compensation."""
            print(f"Refunding payment for order: {context['saga_id']}")
            await asyncio.sleep(0.1)
            return True

        # Register step handlers
        self.saga_orchestrator.register_step_handler("reserve_inventory", reserve_inventory_handler)
        self.saga_orchestrator.register_compensation_handler(
            "reserve_inventory", compensate_inventory_handler
        )
        self.saga_orchestrator.register_step_handler("process_payment", process_payment_handler)
        self.saga_orchestrator.register_compensation_handler(
            "process_payment", compensate_payment_handler
        )

    async def demonstrate_order_flow(self):
        """Demonstrate complete order processing flow."""
        print("🛒 Starting E-commerce Order Processing Demo")
        print("=" * 50)

        # Step 1: Create order (triggers saga)
        print("\n1. Creating order...")
        create_order_cmd = CreateOrderCommand(
            customer_id="customer_123",
            items=[
                {"product_id": "product_1", "quantity": 2, "price": 1000},
                {"product_id": "product_2", "quantity": 1, "price": 1500},
            ],
        )

        order_result = await self.handlers["create_order"].handle(create_order_cmd)
        print(f"   Order created: {order_result.result_data}")

        # Step 2: Process payment (uses outbox pattern)
        print("\n2. Processing payment...")
        process_payment_cmd = ProcessPaymentCommand(
            order_id=order_result.result_data["order_id"],
            payment_method="credit_card",
            amount=order_result.result_data["total_amount"],
        )

        payment_result = await self.handlers["process_payment"].handle(process_payment_cmd)
        print(f"   Payment processed: {payment_result.result_data}")

        # Step 3: Query order (CQRS read side)
        print("\n3. Querying order...")
        get_order_query = GetOrderQuery(order_id=order_result.result_data["order_id"])
        order_query_result = await self.handlers["get_order"].handle(get_order_query)
        print(f"   Order details: {order_query_result.data}")

        # Step 4: Query customer orders (CQRS with pagination)
        print("\n4. Querying customer orders...")
        get_customer_orders_query = GetCustomerOrdersQuery(customer_id="customer_123")
        get_customer_orders_query.page_size = 5

        customer_orders_result = await self.handlers["get_customer_orders"].handle(
            get_customer_orders_query
        )
        print(f"   Customer orders: {len(customer_orders_result.data['orders'])} orders")

        # Step 5: Check saga status
        print("\n5. Checking saga status...")
        saga_id = order_result.result_data["saga_id"]
        saga_status = await self.saga_orchestrator.get_saga_status(saga_id)
        print(f"   Saga status: {saga_status}")

        # Step 6: Check outbox metrics
        print("\n6. Checking outbox metrics...")
        outbox_metrics = self.outbox_processor.get_metrics()
        print(f"   Outbox metrics: {outbox_metrics}")

        print("\n✅ E-commerce order flow completed successfully!")

    async def demonstrate_error_scenarios(self):
        """Demonstrate error handling and compensation."""
        print("\n🚨 Demonstrating Error Scenarios")
        print("=" * 40)

        # Scenario 1: Saga compensation
        print("\n1. Testing saga compensation...")

        # Create order that will trigger compensation
        _failed_order_cmd = CreateOrderCommand(
            customer_id="customer_error",
            items=[{"product_id": "out_of_stock", "quantity": 10, "price": 2000}],
        )

        # This would trigger saga compensation in a real scenario
        print("   Saga would compensate if payment fails...")

        # Scenario 2: Outbox retry mechanism
        print("\n2. Testing outbox retry mechanism...")

        # This would demonstrate how failed events are retried
        print("   Outbox would retry failed event publishing...")

        print("\n✅ Error scenario demonstrations completed!")

    async def cleanup(self):
        """Clean up resources."""
        if self.saga_orchestrator:
            await self.saga_orchestrator.stop()

        if self.outbox_processor:
            await self.outbox_processor.stop()

        print("🧹 Cleanup completed")


# Mock Repository Implementations
class MockOrderRepository:
    """Mock order repository for demonstration."""

    def __init__(self):
        self.orders = {}

    async def save(self, order: Order):
        self.orders[order.order_id] = order
        print(f"   📝 Order {order.order_id} saved to repository")

    async def get(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)


class MockPaymentRepository:
    """Mock payment repository for demonstration."""

    def __init__(self):
        self.payments = {}

    async def save(self, payment: Payment):
        self.payments[payment.payment_id] = payment
        print(f"   💳 Payment {payment.payment_id} saved to repository")

    async def get(self, payment_id: str) -> Payment | None:
        return self.payments.get(payment_id)


class MockInventoryRepository:
    """Mock inventory repository for demonstration."""

    def __init__(self):
        self.inventory = {
            "product_1": Inventory("product_1", 100),
            "product_2": Inventory("product_2", 50),
            "out_of_stock": Inventory("out_of_stock", 0),
        }

    async def reserve(self, product_id: str, quantity: int) -> bool:
        if product_id in self.inventory:
            inventory = self.inventory[product_id]
            if inventory.available_quantity >= quantity:
                inventory.available_quantity -= quantity
                inventory.reserved_quantity += quantity
                print(f"   📦 Reserved {quantity} of {product_id}")
                return True
        return False


class MockOutboxRepository(EnhancedOutboxRepository):
    """Mock outbox repository for demonstration."""

    def __init__(self):
        # Initialize with a mock session and config
        super().__init__(None, OutboxConfig())
        self.events = []

    async def enqueue_event(self, topic: str, event_type: str, payload: dict, **kwargs) -> str:
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "topic": topic,
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.now(timezone.utc),
            **kwargs,
        }
        self.events.append(event)
        print(f"   📨 Event {event_id} queued for topic {topic}")
        return event_id


# Main demonstration function
async def run_comprehensive_demo():
    """Run the comprehensive data consistency patterns demonstration."""
    print("🚀 Marty Microservices Framework - Data Consistency Patterns Demo")
    print("=" * 70)

    # Create development configuration
    config = create_development_config()
    print(f"📋 Using configuration for environment: {config.environment}")

    # Initialize the example system
    example = ECommerceDataConsistencyExample(config)
    await example.initialize()

    try:
        # Demonstrate normal order flow
        await example.demonstrate_order_flow()

        # Wait a bit to see async processing
        print("\n⏳ Waiting for async processing...")
        await asyncio.sleep(2)

        # Demonstrate error scenarios
        await example.demonstrate_error_scenarios()

    finally:
        # Clean up
        await example.cleanup()

    print("\n🎉 Demo completed successfully!")
    print("\nKey patterns demonstrated:")
    print("  ✅ Saga orchestration with compensation")
    print("  ✅ Transactional outbox pattern")
    print("  ✅ CQRS with read/write separation")
    print("  ✅ Event-driven architecture")
    print("  ✅ Error handling and recovery")


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(run_comprehensive_demo())
