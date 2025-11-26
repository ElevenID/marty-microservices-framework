"""
Event Streaming Tests - Working with Real APIs
Tests using the actual API signatures from the framework.
"""

from dataclasses import dataclass
from typing import Any

import pytest

from marty_msf.framework.event_streaming import (
    AggregateRoot,
    Command,
    CommandBus,
    CommandHandler,
    CommandResult,
    CommandStatus,
    Event,
    EventBus,
    EventHandler,
    EventMetadata,
    InMemoryEventBus,
    InMemoryEventStore,
    Query,
    QueryBus,
    QueryHandler,
    QueryResult,
    Saga,
    SagaManager,
    SagaOrchestrator,
    SagaStatus,
    SagaStep,
)


class TestEvent:
    """Test Event core functionality."""

    def test_event_creation(self):
        """Test basic event creation."""
        event = Event(
            aggregate_id="user-123",
            event_type="user.created",
            event_data={"user_id": "123", "name": "Alice"},
            metadata=EventMetadata(correlation_id="corr-123"),
        )

        assert event.aggregate_id == "user-123"
        assert event.event_type == "user.created"
        assert event.event_data["user_id"] == "123"
        assert event.metadata.correlation_id == "corr-123"

    def test_event_equality(self):
        """Test event equality and uniqueness."""
        event1 = Event(
            aggregate_id="user-123",
            event_type="user.created",
            event_data={"user_id": "123"},
            metadata=EventMetadata(event_id="event1", correlation_id="corr-123"),
        )

        event2 = Event(
            aggregate_id="user-123",
            event_type="user.created",
            event_data={"user_id": "123"},
            metadata=EventMetadata(
                event_id="event2",  # Different event ID
                correlation_id="corr-123",
            ),
        )

        # Events should be different due to different event IDs
        assert event1.metadata.event_id != event2.metadata.event_id


class TestEventBus:
    """Test Event Bus functionality."""

    def test_event_bus_creation(self):
        """Test creating an event bus."""
        event_bus = InMemoryEventBus()
        assert isinstance(event_bus, EventBus)

    @pytest.fixture
    def user_handler(self):
        """Create a test event handler."""

        class UserEventHandler(EventHandler):
            def __init__(self):
                self.handled_events = []

            async def handle(self, event: Event) -> None:
                self.handled_events.append(event)

            def can_handle(self, event: Event) -> bool:
                return event.event_type.startswith("user.")

        return UserEventHandler()

    @pytest.mark.asyncio
    async def test_event_subscription_and_publishing(self, user_handler):
        """Test event subscription and publishing."""
        event_bus = InMemoryEventBus()

        # Subscribe handler
        event_bus.subscribe("user.created", user_handler)

        # Create and publish event
        event = Event(
            aggregate_id="user-123",
            event_type="user.created",
            event_data={"user_id": "123", "name": "Alice"},
        )

        await event_bus.publish(event)

        # Verify handler received event
        assert len(user_handler.handled_events) == 1
        assert user_handler.handled_events[0].aggregate_id == "user-123"


class TestEventSourcing:
    """Test Event Sourcing patterns."""

    def test_aggregate_creation(self):
        """Test creating an aggregate root."""

        class TestUser(AggregateRoot):
            def __init__(self, user_id: str = None):
                super().__init__(user_id)
                self.name = None

            def _when(self, event: Event) -> None:
                if event.event_type == "user.created":
                    self.name = event.event_data.get("name")

            def to_snapshot(self) -> dict[str, Any]:
                return {"name": self.name}

            def from_snapshot(self, snapshot_data: dict[str, Any]) -> None:
                self.name = snapshot_data.get("name")

            def create_user(self, name: str) -> None:
                self._raise_event("user.created", {"name": name})

        user_aggregate = TestUser("user-123")
        assert user_aggregate.aggregate_id == "user-123"
        assert user_aggregate.version == 0

    @pytest.mark.asyncio
    async def test_aggregate_event_application(self):
        """Test applying events to aggregate."""

        class TestUser(AggregateRoot):
            def __init__(self, user_id: str = None):
                super().__init__(user_id)
                self.name = None

            def _when(self, event: Event) -> None:
                if event.event_type == "user.created":
                    self.name = event.event_data.get("name")

            def to_snapshot(self) -> dict[str, Any]:
                return {"name": self.name}

            def from_snapshot(self, snapshot_data: dict[str, Any]) -> None:
                self.name = snapshot_data.get("name")

            def create_user(self, name: str) -> None:
                self._raise_event("user.created", {"name": name})

        user_aggregate = TestUser("user-456")
        user_aggregate.create_user("Bob")

        assert user_aggregate.name == "Bob"
        assert user_aggregate.version == 1

    @pytest.mark.asyncio
    async def test_event_store_append_and_read(self):
        """Test event store operations."""
        event_store = InMemoryEventStore()
        stream_id = "user-789"

        # Create events
        events = [
            Event(aggregate_id=stream_id, event_type="user.created", event_data={"name": "Charlie"})
        ]

        # Store events - start with empty stream (version 0)
        await event_store.append_events(stream_id, events, expected_version=0)

        # Retrieve events
        retrieved_events = await event_store.get_events(stream_id)

        assert len(retrieved_events) == 1
        assert retrieved_events[0].event_type == "user.created"


class TestCQRS:
    """Test CQRS patterns."""

    @pytest.fixture
    def command_handler(self):
        """Create a test command handler."""

        class UserCommandHandler(CommandHandler):
            def __init__(self):
                pass

            async def handle(self, command: Command) -> CommandResult:
                return CommandResult(
                    command_id=command.command_id,
                    status=CommandStatus.COMPLETED,
                    result_data={"user_id": "123"},
                )

            def can_handle(self, command: Command) -> bool:
                return command.command_type == "CreateUser"

        return UserCommandHandler()

    @pytest.fixture
    def query_handler(self):
        """Create a test query handler."""

        class UserQueryHandler(QueryHandler):
            def __init__(self):
                pass

            async def handle(self, query: Query) -> QueryResult:
                return QueryResult(
                    query_id=query.query_id, data={"user_id": "123", "name": "Alice"}, total_count=1
                )

            def can_handle(self, query: Query) -> bool:
                return query.query_type == "GetUser"

        return UserQueryHandler()

    @pytest.mark.asyncio
    async def test_command_bus_execution(self, command_handler):
        """Test command bus execution."""
        command_bus = CommandBus()
        command_bus.register_handler("CreateUser", command_handler)

        # Create command with proper field ordering
        @dataclass
        class CreateUser(Command):
            name: str = ""
            email: str = ""

            def __post_init__(self):
                super().__post_init__()

        command = CreateUser(name="Alice", email="alice@example.com")

        # Execute command
        result = await command_bus.send(command)

        assert result.status == CommandStatus.COMPLETED
        assert result.result_data["user_id"] == "123"

    @pytest.mark.asyncio
    async def test_query_bus_execution(self, query_handler):
        """Test query bus execution."""
        query_bus = QueryBus()
        query_bus.register_handler("GetUser", query_handler)

        # Create query with proper field ordering
        @dataclass
        class GetUser(Query):
            user_id: str = ""

            def __post_init__(self):
                super().__post_init__()

        query = GetUser(user_id="123")

        # Execute query using send method
        result = await query_bus.send(query)

        assert result.data["user_id"] == "123"
        assert result.data["name"] == "Alice"


class TestSagaPatterns:
    """Test Saga patterns."""

    def test_saga_creation(self):
        """Test creating a saga."""

        class OrderSaga(Saga):
            def __init__(self, saga_id: str = None):
                super().__init__(saga_id)

            def _initialize_steps(self) -> None:
                # Create saga steps with minimal required fields
                self.steps = [
                    SagaStep(step_name="reserve_inventory", step_order=1),
                    SagaStep(step_name="process_payment", step_order=2),
                    SagaStep(step_name="ship_order", step_order=3),
                ]

        saga = OrderSaga(saga_id="order-123")
        assert saga.saga_id == "order-123"
        assert saga.status == SagaStatus.CREATED
        assert len(saga.steps) == 3

    @pytest.mark.asyncio
    async def test_saga_manager_workflow(self):
        """Test saga manager workflow."""

        class OrderSaga(Saga):
            def __init__(self, saga_id: str = None):
                super().__init__(saga_id)

            def _initialize_steps(self) -> None:
                self.steps = [SagaStep(step_name="test_step", step_order=1)]

        command_bus = CommandBus()
        event_bus = InMemoryEventBus()
        orchestrator = SagaOrchestrator(command_bus, event_bus)
        saga_manager = SagaManager(orchestrator)

        # Register saga type
        orchestrator.register_saga_type("order_processing", OrderSaga)

        # Create and start saga
        saga_id = await saga_manager.create_and_start_saga(
            "order_processing", {"order_id": "order-789"}
        )

        assert saga_id is not None


class TestEventStreamingIntegration:
    """Test end-to-end event streaming integration."""

    @pytest.mark.asyncio
    async def test_event_replay_and_projections(self):
        """Test event replay and projection building."""
        event_store = InMemoryEventStore()

        # Store events
        events = [
            Event(
                aggregate_id="user-replay",
                event_type="user.created",
                event_data={"name": "Alice", "email": "alice@example.com"},
            ),
            Event(
                aggregate_id="user-replay",
                event_type="user.updated",
                event_data={"email": "alice.smith@example.com"},
            ),
        ]

        await event_store.append_events("user-replay", events, expected_version=0)

        # Replay events
        stored_events = await event_store.get_events("user-replay")

        # Build projection
        projection = {"user_id": "user-replay"}
        for event in stored_events:
            if event.event_type == "user.created":
                projection.update(event.event_data)
            elif event.event_type == "user.updated":
                projection.update(event.event_data)

        assert projection["name"] == "Alice"
        assert projection["email"] == "alice.smith@example.com"
        assert len(stored_events) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
