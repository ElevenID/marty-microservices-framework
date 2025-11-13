"""
Extended Messaging System Examples.

This module demonstrates how to use the extended messaging capabilities
including unified event bus, multiple backends, and enhanced Saga integration.
"""

import asyncio

from .aws_sns_backend import AWSSNSBackend, AWSSNSConfig
from .extended_architecture import MessageBackendType, MessagingPattern
from .nats_backend import NATSBackend, NATSConfig
from .saga_integration import create_distributed_saga_manager
from .unified_event_bus import create_unified_event_bus


async def unified_event_bus_example():
    """Demonstrate unified event bus with multiple backends."""
    print("=== Unified Event Bus Example ===")

    # Create unified event bus
    event_bus = create_unified_event_bus()

    # Configure NATS backend
    nats_config = NATSConfig(servers=["nats://localhost:4222"], jetstream_enabled=True)
    nats_backend = NATSBackend(nats_config)

    # Configure AWS SNS backend
    sns_config = AWSSNSConfig(region_name="us-east-1", fifo_topics=True)
    sns_backend = AWSSNSBackend(sns_config)

    # Register backends
    event_bus.register_backend(MessageBackendType.NATS, nats_backend)
    event_bus.register_backend(MessageBackendType.AWS_SNS, sns_backend)

    # Start event bus
    await event_bus.start()

    try:
        # Publish event (pub/sub pattern)
        await event_bus.publish_event(
            event_type="user_registered",
            data={"user_id": "123", "email": "user@example.com"},
            metadata={"source": "user_service"},
        )
        print("✓ Published user_registered event")

        # Send command (point-to-point pattern)
        await event_bus.send_command(
            command_type="process_payment",
            data={"order_id": "456", "amount": 99.99},
            target_service="payment_service",
        )
        print("✓ Sent process_payment command")

        # Query with response (request/response pattern)
        try:
            response = await event_bus.query(
                query_type="get_user_profile",
                data={"user_id": "123"},
                target_service="user_service",
                timeout=5.0,
            )
            print(f"✓ Received query response: {response}")
        except Exception as e:
            print(f"Query timeout (expected in demo): {e}")

        # Stream events (streaming pattern)
        await event_bus.stream_events(
            stream_name="order_events",
            events=[
                {"event_type": "order_created", "order_id": "789"},
                {"event_type": "order_confirmed", "order_id": "789"},
            ],
        )
        print("✓ Streamed order events")

    finally:
        await event_bus.stop()
        print("✓ Event bus stopped")


async def enhanced_saga_example():
    """Demonstrate enhanced Saga integration with distributed transactions."""
    print("\n=== Enhanced Saga Integration Example ===")

    # Create unified event bus
    event_bus = create_unified_event_bus()

    # Configure NATS backend for saga coordination
    nats_config = NATSConfig(servers=["nats://localhost:4222"], jetstream_enabled=True)
    nats_backend = NATSBackend(nats_config)
    event_bus.register_backend(MessageBackendType.NATS, nats_backend)

    await event_bus.start()

    try:
        # Create distributed saga manager
        saga_manager = create_distributed_saga_manager(event_bus)

        # Define saga steps
        saga_definition = {
            "name": "order_processing",
            "steps": [
                {
                    "name": "validate_payment",
                    "service": "payment_service",
                    "command": "validate_payment_method",
                    "compensation": "release_payment_hold",
                },
                {
                    "name": "reserve_inventory",
                    "service": "inventory_service",
                    "command": "reserve_items",
                    "compensation": "release_items",
                },
                {
                    "name": "create_order",
                    "service": "order_service",
                    "command": "create_order",
                    "compensation": "cancel_order",
                },
            ],
        }

        # Register saga
        saga_manager.register_saga_definition("order_processing", saga_definition)

        # Start distributed saga
        saga_data = {
            "order_id": "ORD-123",
            "customer_id": "CUST-456",
            "items": [{"sku": "ITEM-1", "quantity": 2}],
            "payment_method": "credit_card",
            "total_amount": 199.99,
        }

        saga_id = await saga_manager.create_and_start_saga("order_processing", saga_data)
        print(f"✓ Started distributed saga: {saga_id}")

        # Simulate saga step completion
        await saga_manager.handle_step_completion(
            saga_id, "validate_payment", {"status": "success", "payment_id": "PAY-789"}
        )
        print("✓ Payment validation completed")

        # Check saga status
        status = await saga_manager.get_saga_status(saga_id)
        print(f"✓ Saga status: {status}")

    finally:
        await event_bus.stop()
        print("✓ Saga demonstration completed")


async def backend_specific_examples():
    """Demonstrate backend-specific features."""
    print("\n=== Backend-Specific Examples ===")

    # NATS JetStream example
    print("\n--- NATS JetStream Features ---")
    nats_config = NATSConfig(
        servers=["nats://localhost:4222"],
        jetstream_enabled=True,
        stream_config={
            "max_msgs": 10000,
            "max_bytes": 1024 * 1024,  # 1MB
            "retention": "workqueue",
        },
    )

    # Backend would be used with unified event bus
    print("✓ NATS backend configured with JetStream")
    print(f"  - Servers: {nats_config.servers}")
    print(f"  - JetStream: {nats_config.jetstream_enabled}")

    # AWS SNS FIFO example
    print("\n--- AWS SNS FIFO Features ---")
    sns_config = AWSSNSConfig(region_name="us-east-1", fifo_topics=True)

    # Backend would be used with unified event bus
    print("✓ AWS SNS backend configured")
    print(f"  - Region: {sns_config.region_name}")
    print(f"  - FIFO topics: {sns_config.fifo_topics}")


async def pattern_selection_example():
    """Demonstrate pattern selection and optimization."""
    print("\n=== Pattern Selection Example ===")

    print("✓ Extended messaging supports multiple patterns:")
    print("  - PUB_SUB: Event broadcasting")
    print("  - POINT_TO_POINT: Direct messaging")
    print("  - REQUEST_RESPONSE: Query/reply")
    print("  - STREAMING: High-throughput data")


async def main():
    """Run all examples."""
    print("Extended Messaging System Examples")
    print("=" * 50)

    try:
        await unified_event_bus_example()
        await enhanced_saga_example()
        await backend_specific_examples()
        await pattern_selection_example()

        print("\n" + "=" * 50)
        print("✅ All examples completed successfully!")
        print("\nNote: Some examples may show timeouts for services")
        print("that are not running - this is expected in demo mode.")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("Make sure NATS server is running for full functionality.")


if __name__ == "__main__":
    asyncio.run(main())
