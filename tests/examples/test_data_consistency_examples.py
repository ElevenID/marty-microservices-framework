"""
Test file to demonstrate data consistency patterns.
Run with: python -m pytest tests/examples/test_data_consistency_examples.py -v
"""

import asyncio
import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest


@dataclass
class ExampleOrder:
    """Simple order for testing."""
    order_id: str
    customer_id: str
    total_amount: int
    status: str = "pending"


@dataclass
class ExamplePayment:
    """Simple payment for testing."""
    payment_id: str
    order_id: str
    amount: int
    status: str = "pending"


class TestDataConsistencyPatterns:
    """Test the integrated data consistency patterns."""

    @pytest.mark.asyncio
    async def test_saga_pattern_example(self):
        """Test saga orchestration with compensation."""
        # Simulate saga steps
        steps_completed = []
        compensation_executed = False

        async def step_1():
            steps_completed.append("inventory_reserved")
            return True

        async def step_2():
            # Simulate failure
            return False

        async def compensate_1():
            nonlocal compensation_executed
            compensation_executed = True
            return True

        # Execute saga
        if await step_1():
            if not await step_2():
                # Compensation needed
                await compensate_1()

        assert "inventory_reserved" in steps_completed
        assert compensation_executed

    @pytest.mark.asyncio
    async def test_outbox_pattern_example(self):
        """Test transactional outbox pattern."""
        # Simulate outbox events
        outbox_events = []

        async def save_order_and_event(order: ExampleOrder, event_data: dict):
            # In a real implementation, this would be in a transaction
            outbox_events.append({
                "event_id": str(uuid.uuid4()),
                "aggregate_id": order.order_id,
                "event_type": "order_created",
                "payload": event_data,
                "created_at": datetime.now(timezone.utc)
            })
            return True

        # Create order with event
        order = ExampleOrder(
            order_id=str(uuid.uuid4()),
            customer_id="customer_123",
            total_amount=5000
        )

        event_data = {
            "order_id": order.order_id,
            "customer_id": order.customer_id,
            "total_amount": order.total_amount
        }

        await save_order_and_event(order, event_data)

        assert len(outbox_events) == 1
        assert outbox_events[0]["event_type"] == "order_created"
        assert outbox_events[0]["payload"]["order_id"] == order.order_id

    @pytest.mark.asyncio
    async def test_cqrs_pattern_example(self):
        """Test CQRS command/query separation."""
        # Command side (write model)
        orders_write = {}

        async def handle_create_order_command(customer_id: str, amount: int):
            order_id = str(uuid.uuid4())
            order = ExampleOrder(
                order_id=order_id,
                customer_id=customer_id,
                total_amount=amount,
                status="created"
            )
            orders_write[order_id] = order
            return order_id

        # Query side (read model)
        orders_read = {}

        async def handle_get_order_query(order_id: str):
            return orders_read.get(order_id)

        async def update_read_model(order_id: str):
            if order_id in orders_write:
                order = orders_write[order_id]
                orders_read[order_id] = {
                    "order_id": order.order_id,
                    "customer_id": order.customer_id,
                    "total_amount": order.total_amount,
                    "status": order.status,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

        # Execute command
        order_id = await handle_create_order_command("customer_456", 3000)

        # Update read model
        await update_read_model(order_id)

        # Execute query
        order_data = await handle_get_order_query(order_id)

        assert order_data is not None
        assert order_data["customer_id"] == "customer_456"
        assert order_data["total_amount"] == 3000

    @pytest.mark.asyncio
    async def test_integrated_patterns_example(self):
        """Test all patterns working together."""
        # State storage
        orders = {}
        events = []
        saga_state = {}
        read_models = {}

        async def process_order_with_all_patterns(customer_id: str, amount: int):
            """Integrate saga, outbox, and CQRS patterns."""
            order_id = str(uuid.uuid4())
            saga_id = str(uuid.uuid4())

            # 1. Create order (Command side)
            order = ExampleOrder(
                order_id=order_id,
                customer_id=customer_id,
                total_amount=amount,
                status="processing"
            )
            orders[order_id] = order

            # 2. Start saga
            saga_state[saga_id] = {
                "order_id": order_id,
                "steps": ["reserve_inventory", "process_payment"],
                "current_step": 0,
                "status": "running"
            }

            # 3. Add outbox event
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_type": "order_processing_started",
                "aggregate_id": order_id,
                "saga_id": saga_id,
                "payload": {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "amount": amount
                },
                "created_at": datetime.now(timezone.utc)
            })

            # 4. Update read model (Query side)
            read_models[order_id] = {
                "order_id": order_id,
                "customer_id": customer_id,
                "total_amount": amount,
                "status": "processing",
                "saga_id": saga_id,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }

            return order_id, saga_id

        # Execute integrated flow
        order_id, saga_id = await process_order_with_all_patterns("customer_789", 7500)

        # Verify all patterns were applied
        assert order_id in orders
        assert saga_id in saga_state
        assert len(events) == 1
        assert order_id in read_models

        # Verify data consistency
        order = orders[order_id]
        saga = saga_state[saga_id]
        event = events[0]
        read_model = read_models[order_id]

        assert order.order_id == saga["order_id"] == event["aggregate_id"] == read_model["order_id"]
        assert order.customer_id == event["payload"]["customer_id"] == read_model["customer_id"]
        assert order.total_amount == event["payload"]["amount"] == read_model["total_amount"]

    def test_configuration_example(self):
        """Test configuration structure for data consistency patterns."""
        config = {
            "saga": {
                "orchestrator_name": "test-orchestrator",
                "worker_count": 2,
                "retry_attempts": 3,
                "timeout_seconds": 30
            },
            "outbox": {
                "batch_size": 100,
                "polling_interval_ms": 1000,
                "max_retry_attempts": 5,
                "dead_letter_threshold": 10
            },
            "cqrs": {
                "enable_caching": True,
                "cache_ttl_seconds": 300,
                "enable_read_model_validation": True
            },
            "event_store": {
                "connection_string": "test_connection",
                "table_name": "events",
                "enable_snapshots": True
            }
        }

        # Verify configuration structure
        assert "saga" in config
        assert "outbox" in config
        assert "cqrs" in config
        assert "event_store" in config

        # Verify saga config
        assert config["saga"]["worker_count"] == 2
        assert config["saga"]["retry_attempts"] == 3

        # Verify outbox config
        assert config["outbox"]["batch_size"] == 100
        assert config["outbox"]["max_retry_attempts"] == 5

        # Verify CQRS config
        assert config["cqrs"]["enable_caching"] is True
        assert config["cqrs"]["cache_ttl_seconds"] == 300

    @pytest.mark.asyncio
    async def test_error_handling_example(self):
        """Test error handling and compensation scenarios."""
        error_log = []
        compensation_log = []

        async def unreliable_operation(success_rate: float = 0.5):
            """Simulate an operation that might fail."""
            if random.random() < success_rate:
                return True
            else:
                error_log.append("Operation failed")
                return False

        async def compensation_action():
            """Compensate for failed operation."""
            compensation_log.append("Compensation executed")
            return True

        # Test with high failure rate
        success = await unreliable_operation(success_rate=0.1)

        if not success:
            await compensation_action()

        # Verify error handling
        if not success:
            assert len(error_log) > 0
            assert len(compensation_log) > 0
            assert "Operation failed" in error_log
            assert "Compensation executed" in compensation_log


if __name__ == "__main__":
    # Run a simple demonstration
    async def run_simple_demo():
        print("🚀 Data Consistency Patterns - Simple Demo")
        print("=" * 50)

        # Create test instance
        test_instance = TestDataConsistencyPatterns()

        print("\n1. Testing Saga Pattern...")
        await test_instance.test_saga_pattern_example()
        print("   ✅ Saga with compensation completed")

        print("\n2. Testing Outbox Pattern...")
        await test_instance.test_outbox_pattern_example()
        print("   ✅ Transactional outbox completed")

        print("\n3. Testing CQRS Pattern...")
        await test_instance.test_cqrs_pattern_example()
        print("   ✅ Command/Query separation completed")

        print("\n4. Testing Integrated Patterns...")
        await test_instance.test_integrated_patterns_example()
        print("   ✅ All patterns integration completed")

        print("\n5. Testing Configuration...")
        test_instance.test_configuration_example()
        print("   ✅ Configuration validation completed")

        print("\n6. Testing Error Handling...")
        await test_instance.test_error_handling_example()
        print("   ✅ Error handling and compensation completed")

        print("\n🎉 All tests completed successfully!")
        print("\nThis demonstrates:")
        print("  ✅ Saga orchestration with compensation handlers")
        print("  ✅ Transactional outbox pattern for event publishing")
        print("  ✅ CQRS with read/write model separation")
        print("  ✅ Integrated usage of all patterns")
        print("  ✅ Error handling and recovery mechanisms")

    # Run the demo
    asyncio.run(run_simple_demo())
