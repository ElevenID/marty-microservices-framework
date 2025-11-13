"""
Integration tests for MMF framework components.

Tests complete workflows with real services and minimal mocking.
"""

import asyncio
import json
import time

import pytest

from marty_msf.framework.events import Event
from marty_msf.framework.messaging import Message


@pytest.mark.integration
@pytest.mark.asyncio
class TestFrameworkIntegration:
    """Integration tests for complete framework workflows."""

    async def test_message_to_event_flow(
        self, real_message_bus, real_event_bus, real_metrics_collector
    ):
        """Test message processing that triggers events."""
        processed_events = []
        processed_messages = []

        # Set up event handler
        async def user_created_handler(event: Event) -> None:
            processed_events.append(event)

        real_event_bus.register_handler(
            name="user-created-handler",
            event_type="user.created",
            handler_func=user_created_handler,
        )

        # Set up message handler that publishes events
        async def create_user_handler(message: Message) -> bool:
            processed_messages.append(message)

            # Create user and publish event
            user_data = message.data
            event = Event(
                id=f"event-{message.id}",
                type="user.created",
                data=user_data,
                correlation_id=message.correlation_id,
            )

            await real_event_bus.publish(event)
            return True

        real_message_bus.register_handler(
            name="create-user-handler", message_type="user.create", handler_func=create_user_handler
        )

        # Start buses
        await real_message_bus.start()
        await real_event_bus.start()

        # Publish message
        message = Message(
            id="msg-123",
            type="user.create",
            data={"name": "John Doe", "email": "john@example.com"},
            correlation_id="correlation-123",
        )

        await real_message_bus.publish(message)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Verify flow
        assert len(processed_messages) == 1
        assert processed_messages[0].id == "msg-123"

        assert len(processed_events) == 1
        assert processed_events[0].type == "user.created"
        assert processed_events[0].correlation_id == "correlation-123"

        # Verify metrics were collected
        message_metrics = real_message_bus.get_metrics()
        event_metrics = real_event_bus.get_metrics()

        assert message_metrics["messages_processed"] >= 1
        assert event_metrics["events_published"] >= 1

        # Cleanup
        await real_message_bus.stop()
        await real_event_bus.stop()

    async def test_database_transaction_with_events(self, real_database_connection, real_event_bus):
        """Test database operations with event publishing."""
        published_events = []

        async def order_placed_handler(event: Event) -> None:
            published_events.append(event)

        real_event_bus.register_handler(
            name="order-placed-handler",
            event_type="order.placed",
            handler_func=order_placed_handler,
        )

        await real_event_bus.start()

        # Start a database transaction
        async with real_database_connection.transaction() as tx:
            # Insert order
            order_id = await tx.execute(
                "INSERT INTO orders (customer_id, total) VALUES ($1, $2) RETURNING id", 123, 99.99
            )

            # Insert order items
            await tx.execute(
                "INSERT INTO order_items (order_id, product_id, quantity) VALUES ($1, $2, $3)",
                order_id,
                456,
                2,
            )

            # Publish event within transaction
            event = Event(
                id=f"order-{order_id}",
                type="order.placed",
                data={"order_id": order_id, "customer_id": 123, "total": 99.99},
            )

            await real_event_bus.publish(event)

        # Wait for event processing
        await asyncio.sleep(0.3)

        # Verify database state
        order = await real_database_connection.fetch_one(
            "SELECT * FROM orders WHERE id = $1", order_id
        )
        assert order is not None
        assert order["customer_id"] == 123

        # Verify event was published
        assert len(published_events) == 1
        assert published_events[0].data["order_id"] == order_id

        await real_event_bus.stop()

    async def test_saga_pattern_implementation(
        self, real_message_bus, real_event_bus, real_database_connection
    ):
        """Test saga pattern implementation with compensation."""
        saga_steps = []
        compensation_steps = []

        # Saga coordinator
        class OrderSaga:
            def __init__(self, message_bus, event_bus, db):
                self.message_bus = message_bus
                self.event_bus = event_bus
                self.db = db
                self.saga_state = {}

            async def handle_order_requested(self, event: Event):
                saga_steps.append("order_requested")
                order_data = event.data

                # Step 1: Reserve inventory
                try:
                    await self._reserve_inventory(order_data)
                    saga_steps.append("inventory_reserved")

                    # Step 2: Process payment
                    await self._process_payment(order_data)
                    saga_steps.append("payment_processed")

                    # Step 3: Create order
                    await self._create_order(order_data)
                    saga_steps.append("order_created")

                except Exception:
                    # Start compensation
                    await self._compensate(order_data)

            async def _reserve_inventory(self, order_data):
                # Simulate inventory reservation
                if order_data.get("product_id") == 999:  # Out of stock
                    raise ValueError("Product out of stock")

            async def _process_payment(self, order_data):
                # Simulate payment processing
                if order_data.get("payment_method") == "invalid":
                    raise ValueError("Invalid payment method")

            async def _create_order(self, order_data):
                # Create order in database
                await self.db.execute(
                    "INSERT INTO orders (customer_id, total, status) VALUES ($1, $2, $3)",
                    order_data["customer_id"],
                    order_data["total"],
                    "completed",
                )

            async def _compensate(self, order_data):
                compensation_steps.append("compensation_started")
                # Compensate in reverse order
                if "payment_processed" in saga_steps:
                    await self._refund_payment(order_data)
                    compensation_steps.append("payment_refunded")

                if "inventory_reserved" in saga_steps:
                    await self._release_inventory(order_data)
                    compensation_steps.append("inventory_released")

            async def _refund_payment(self, order_data):
                # Simulate payment refund
                pass

            async def _release_inventory(self, order_data):
                # Simulate inventory release
                pass

        # Set up saga
        saga = OrderSaga(real_message_bus, real_event_bus, real_database_connection)

        real_event_bus.register_handler(
            name="saga-handler",
            event_type="order.requested",
            handler_func=saga.handle_order_requested,
        )

        await real_event_bus.start()

        # Test successful saga
        success_event = Event(
            id="order-success",
            type="order.requested",
            data={
                "customer_id": 123,
                "product_id": 456,
                "total": 99.99,
                "payment_method": "credit_card",
            },
        )

        await real_event_bus.publish(success_event)
        await asyncio.sleep(0.5)

        assert "order_requested" in saga_steps
        assert "inventory_reserved" in saga_steps
        assert "payment_processed" in saga_steps
        assert "order_created" in saga_steps
        assert len(compensation_steps) == 0

        # Reset for failure test
        saga_steps.clear()
        compensation_steps.clear()

        # Test failed saga with compensation
        failure_event = Event(
            id="order-failure",
            type="order.requested",
            data={
                "customer_id": 123,
                "product_id": 999,  # Out of stock
                "total": 99.99,
                "payment_method": "credit_card",
            },
        )

        await real_event_bus.publish(failure_event)
        await asyncio.sleep(0.5)

        assert "order_requested" in saga_steps
        assert "compensation_started" in compensation_steps

        await real_event_bus.stop()

    async def test_circuit_breaker_pattern(self, real_message_bus, real_event_bus):
        """Test circuit breaker pattern for resilience."""
        call_attempts = []
        circuit_states = []

        class CircuitBreaker:
            def __init__(self, failure_threshold=3, timeout=5.0):
                self.failure_threshold = failure_threshold
                self.timeout = timeout
                self.failure_count = 0
                self.last_failure_time = None
                self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

            async def call(self, func, *args, **kwargs):
                call_attempts.append(self.state)
                circuit_states.append(self.state)

                if self.state == "OPEN":
                    if self._should_attempt_reset():
                        self.state = "HALF_OPEN"
                        circuit_states.append("HALF_OPEN")
                    else:
                        raise Exception("Circuit breaker is OPEN")

                try:
                    result = await func(*args, **kwargs)
                    self._on_success()
                    return result
                except Exception:
                    self._on_failure()
                    raise

            def _should_attempt_reset(self):
                return (
                    self.last_failure_time and time.time() - self.last_failure_time >= self.timeout
                )

            def _on_success(self):
                self.failure_count = 0
                self.state = "CLOSED"

            def _on_failure(self):
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    circuit_states.append("OPEN")

        # Service that fails sometimes
        call_count = 0

        async def unreliable_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:  # First 3 calls fail
                raise Exception("Service unavailable")
            return {"status": "success"}

        circuit_breaker = CircuitBreaker(failure_threshold=3)

        # Test circuit breaker opening
        for _i in range(5):
            try:
                await circuit_breaker.call(unreliable_service)
            except Exception:
                pass
            await asyncio.sleep(0.1)

        # Verify circuit opened after 3 failures
        assert "OPEN" in circuit_states
        assert circuit_states.count("CLOSED") >= 3

        # Test circuit breaker half-open and recovery
        await asyncio.sleep(5.1)  # Wait for timeout

        try:
            result = await circuit_breaker.call(unreliable_service)
            assert result["status"] == "success"
        except Exception:
            pass

        assert "HALF_OPEN" in circuit_states

    async def test_cqrs_pattern_implementation(
        self, real_database_connection, real_event_bus, real_message_bus
    ):
        """Test CQRS pattern with command/query separation."""
        command_results = []
        query_results = []
        events_published = []

        # Command handlers
        class UserCommands:
            def __init__(self, db, event_bus):
                self.db = db
                self.event_bus = event_bus

            async def create_user(self, command_data):
                # Write to command store
                user_id = await self.db.execute(
                    "INSERT INTO users (name, email) VALUES ($1, $2) RETURNING id",
                    command_data["name"],
                    command_data["email"],
                )

                # Publish event
                event = Event(
                    id=f"user-created-{user_id}",
                    type="user.created",
                    data={
                        "user_id": user_id,
                        "name": command_data["name"],
                        "email": command_data["email"],
                    },
                )

                await self.event_bus.publish(event)
                command_results.append({"user_id": user_id})
                return user_id

        # Query handlers
        class UserQueries:
            def __init__(self, db):
                self.db = db

            async def get_user(self, user_id):
                # Read from query store (could be different from command store)
                user = await self.db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
                query_results.append(user)
                return user

            async def get_users_by_email_domain(self, domain):
                users = await self.db.fetch_all(
                    "SELECT * FROM users WHERE email LIKE $1", f"%@{domain}"
                )
                query_results.extend(users)
                return users

        # Event handlers for read model updates
        async def update_read_model(event: Event):
            events_published.append(event)
            # Update read models, projections, etc.

        # Set up components
        commands = UserCommands(real_database_connection, real_event_bus)
        queries = UserQueries(real_database_connection)

        real_event_bus.register_handler(
            name="read-model-updater", event_type="user.created", handler_func=update_read_model
        )

        await real_event_bus.start()

        # Execute commands
        user_id1 = await commands.create_user({"name": "John Doe", "email": "john@example.com"})

        user_id2 = await commands.create_user({"name": "Jane Smith", "email": "jane@example.com"})

        await asyncio.sleep(0.3)

        # Execute queries
        user1 = await queries.get_user(user_id1)
        user2 = await queries.get_user(user_id2)
        example_users = await queries.get_users_by_email_domain("example.com")

        # Verify results
        assert len(command_results) == 2
        assert len(query_results) == 4  # 2 single user queries + 2 users from domain query
        assert len(events_published) == 2

        assert user1["name"] == "John Doe"
        assert user2["name"] == "Jane Smith"
        assert len(example_users) == 2

        await real_event_bus.stop()

    async def test_event_sourcing_pattern(self, real_database_connection, real_event_bus):
        """Test event sourcing pattern implementation."""
        stored_events = []

        class EventStore:
            def __init__(self, db):
                self.db = db

            async def save_events(self, aggregate_id, events, expected_version):
                async with self.db.transaction() as tx:
                    # Check version for optimistic concurrency
                    current_version = (
                        await tx.fetch_val(
                            "SELECT COALESCE(MAX(version), 0) FROM events WHERE aggregate_id = $1",
                            aggregate_id,
                        )
                        or 0
                    )

                    if current_version != expected_version:
                        raise Exception("Concurrency conflict")

                    # Save events
                    for i, event in enumerate(events):
                        version = expected_version + i + 1
                        await tx.execute(
                            "INSERT INTO events (aggregate_id, version, event_type, event_data, timestamp) VALUES ($1, $2, $3, $4, NOW())",
                            aggregate_id,
                            version,
                            event.type,
                            json.dumps(event.data),
                        )
                        stored_events.append(event)

            async def load_events(self, aggregate_id, from_version=0):
                rows = await self.db.fetch_all(
                    "SELECT * FROM events WHERE aggregate_id = $1 AND version > $2 ORDER BY version",
                    aggregate_id,
                    from_version,
                )

                events = []
                for row in rows:
                    event = Event(
                        id=f"event-{row['id']}",
                        type=row["event_type"],
                        data=json.loads(row["event_data"]),
                    )
                    events.append(event)

                return events

        # Aggregate
        class BankAccount:
            def __init__(self, account_id):
                self.account_id = account_id
                self.balance = 0
                self.version = 0
                self.uncommitted_events = []

            def deposit(self, amount):
                if amount <= 0:
                    raise ValueError("Amount must be positive")

                event = Event(
                    id=f"deposit-{self.account_id}-{len(self.uncommitted_events)}",
                    type="money.deposited",
                    data={"account_id": self.account_id, "amount": amount},
                )

                self._apply_event(event)
                self.uncommitted_events.append(event)

            def withdraw(self, amount):
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                if amount > self.balance:
                    raise ValueError("Insufficient funds")

                event = Event(
                    id=f"withdraw-{self.account_id}-{len(self.uncommitted_events)}",
                    type="money.withdrawn",
                    data={"account_id": self.account_id, "amount": amount},
                )

                self._apply_event(event)
                self.uncommitted_events.append(event)

            def _apply_event(self, event):
                if event.type == "money.deposited":
                    self.balance += event.data["amount"]
                elif event.type == "money.withdrawn":
                    self.balance -= event.data["amount"]

            def load_from_events(self, events):
                for event in events:
                    self._apply_event(event)
                    self.version += 1

            def mark_committed(self):
                self.version += len(self.uncommitted_events)
                self.uncommitted_events.clear()

        # Set up event store
        event_store = EventStore(real_database_connection)

        # Create aggregate and perform operations
        account = BankAccount("account-123")
        account.deposit(100.0)
        account.deposit(50.0)
        account.withdraw(25.0)

        # Save events
        await event_store.save_events(
            account.account_id, account.uncommitted_events, account.version
        )
        account.mark_committed()

        # Verify state
        assert account.balance == 125.0
        assert len(stored_events) == 3

        # Load new aggregate from events
        new_account = BankAccount("account-123")
        events = await event_store.load_events("account-123")
        new_account.load_from_events(events)

        # Verify reconstruction
        assert new_account.balance == 125.0
        assert new_account.version == 3

    async def test_full_microservice_workflow(
        self,
        real_database_connection,
        real_redis_client,
        real_message_bus,
        real_event_bus,
        real_metrics_collector,
    ):
        """Test complete microservice workflow with all components."""
        workflow_steps = []

        # Step 1: API request handler
        async def handle_create_order_request(message: Message) -> bool:
            workflow_steps.append("api_request_received")

            # Validate request
            order_data = message.data
            if not order_data.get("customer_id"):
                return False

            # Cache customer data
            await real_redis_client.set(
                f"customer:{order_data['customer_id']}", json.dumps({"status": "active"}), ex=3600
            )

            # Publish domain event
            event = Event(
                id=f"order-requested-{message.id}",
                type="order.requested",
                data=order_data,
                correlation_id=message.correlation_id,
            )

            await real_event_bus.publish(event)
            return True

        # Step 2: Business logic handler
        async def handle_order_requested(event: Event) -> None:
            workflow_steps.append("business_logic_executed")

            order_data = event.data

            # Check inventory (simulate)
            inventory_key = f"inventory:{order_data['product_id']}"
            current_stock = await real_redis_client.get(inventory_key)
            if current_stock is None:
                await real_redis_client.set(inventory_key, "10")  # Default stock
                current_stock = "10"

            stock = int(current_stock)
            quantity = order_data.get("quantity", 1)

            if stock >= quantity:
                # Reserve inventory
                await real_redis_client.decrby(inventory_key, quantity)

                # Save order to database
                order_id = await real_database_connection.execute(
                    "INSERT INTO orders (customer_id, product_id, quantity, status) VALUES ($1, $2, $3, $4) RETURNING id",
                    order_data["customer_id"],
                    order_data["product_id"],
                    quantity,
                    "confirmed",
                )

                # Publish order confirmed event
                confirmed_event = Event(
                    id=f"order-confirmed-{order_id}",
                    type="order.confirmed",
                    data={**order_data, "order_id": order_id},
                    correlation_id=event.correlation_id,
                )

                await real_event_bus.publish(confirmed_event)
            else:
                # Publish order rejected event
                rejected_event = Event(
                    id=f"order-rejected-{event.id}",
                    type="order.rejected",
                    data={**order_data, "reason": "insufficient_inventory"},
                    correlation_id=event.correlation_id,
                )

                await real_event_bus.publish(rejected_event)

        # Step 3: Notification handler
        async def handle_order_confirmed(event: Event) -> None:
            workflow_steps.append("notification_sent")

            # Simulate sending notification
            notification_data = {
                "customer_id": event.data["customer_id"],
                "order_id": event.data["order_id"],
                "message": "Your order has been confirmed",
            }

            # Store notification in cache
            await real_redis_client.lpush(
                f"notifications:{event.data['customer_id']}", json.dumps(notification_data)
            )

        # Step 4: Metrics handler
        async def handle_order_events(event: Event) -> None:
            workflow_steps.append("metrics_recorded")

            # Record metrics
            real_metrics_collector.increment_counter(f"orders.{event.type.split('.')[1]}")
            real_metrics_collector.record_histogram(
                "order.processing_time",
                0.5,  # Simulated processing time
                {"order_type": "standard"},
            )

        # Register all handlers
        real_message_bus.register_handler(
            name="create-order-handler",
            message_type="order.create",
            handler_func=handle_create_order_request,
        )

        real_event_bus.register_handler(
            name="order-requested-handler",
            event_type="order.requested",
            handler_func=handle_order_requested,
        )

        real_event_bus.register_handler(
            name="order-confirmed-handler",
            event_type="order.confirmed",
            handler_func=handle_order_confirmed,
        )

        real_event_bus.register_handler(
            name="metrics-handler", event_type="order.*", handler_func=handle_order_events
        )

        # Start all components
        await real_message_bus.start()
        await real_event_bus.start()

        # Execute workflow
        order_message = Message(
            id="order-msg-123",
            type="order.create",
            data={"customer_id": 123, "product_id": 456, "quantity": 2},
            correlation_id="workflow-123",
        )

        await real_message_bus.publish(order_message)

        # Wait for complete processing
        await asyncio.sleep(1.0)

        # Verify workflow completion
        expected_steps = [
            "api_request_received",
            "business_logic_executed",
            "notification_sent",
            "metrics_recorded",
        ]

        for step in expected_steps:
            assert step in workflow_steps

        # Verify database state
        order = await real_database_connection.fetch_one(
            "SELECT * FROM orders WHERE customer_id = $1", 123
        )
        assert order is not None
        assert order["status"] == "confirmed"

        # Verify cache state
        inventory = await real_redis_client.get("inventory:456")
        assert int(inventory) == 8  # 10 - 2

        notifications = await real_redis_client.lrange("notifications:123", 0, -1)
        assert len(notifications) >= 1

        # Verify metrics
        metrics = real_metrics_collector.get_metrics()
        assert "orders.confirmed" in str(metrics)

        # Cleanup
        await real_message_bus.stop()
        await real_event_bus.stop()
