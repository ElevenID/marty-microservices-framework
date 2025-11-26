"""
Comprehensive Event Streaming Tests for CQRS, Event Sourcing, and Saga Patterns.

This test suite focuses on testing event streaming components with minimal mocking
to maximize real behavior validation and coverage.
"""

import asyncio
from typing import Any

import pytest

from marty_msf.framework.event_streaming.core import (
    Event,
    EventHandler,
    EventMetadata,
    InMemoryEventBus,
    InMemoryEventStore,
)
from marty_msf.framework.event_streaming.cqrs import (
    Command,
    CommandBus,
    CommandHandler,
    Query,
    QueryBus,
    QueryHandler,
)
from marty_msf.framework.event_streaming.event_sourcing import (
    AggregateRoot,
    EventSourcedRepository,
)
from marty_msf.framework.event_streaming.saga import Saga, SagaManager


# Mock classes for testing
class CQRSEngine:
    """Mock CQRS Engine for testing."""

    def __init__(self, event_bus, event_store):
        self.event_bus = event_bus
        self.command_bus = CommandBus()
        self.query_bus = QueryBus()


class SagaOrchestrator:
    """Mock Saga Orchestrator for testing."""

    def __init__(self, command_bus, event_bus):
        self.command_bus = command_bus
        self.event_bus = event_bus


class TestEvent:
    """Test Event creation and behavior."""

    def test_event_creation(self):
        """Test creating an event with all fields."""
        event_data = {"user_id": "123", "email": "test@example.com"}
        metadata = EventMetadata(correlation_id="corr-123")

        event = Event(
            aggregate_id="user-123",
            event_type="user.created",
            event_data=event_data,
            metadata=metadata,
        )

        assert event.aggregate_id == "user-123"
        assert event.event_type == "user.created"
        assert event.event_data == event_data
        assert event.metadata == metadata
        assert event.event_id is not None
        assert event.timestamp is not None

    def test_event_equality(self):
        """Test event equality comparison."""
        event_data = {"user_id": "123"}
        metadata = EventMetadata(correlation_id="corr-123")

        event1 = Event(
            aggregate_id="user-123",
            event_type="user.created",
            event_data=event_data,
            metadata=metadata,
        )
        event2 = Event(
            aggregate_id="user-123",
            event_type="user.created",
            event_data=event_data,
            metadata=metadata,
        )
        event3 = Event(
            aggregate_id="user-123",
            event_type="user.updated",
            event_data=event_data,
            metadata=metadata,
        )

        assert event1 != event2  # Different event IDs
        assert event1.event_type == event2.event_type
        assert event1.event_type != event3.event_type


class UserCreatedEvent(Event):
    """Test domain event."""

    def __init__(self, user_id: str, email: str, correlation_id: str = None):
        super().__init__(
            aggregate_id=user_id,
            event_type="user.created",
            event_data={"user_id": user_id, "email": email},
            metadata=EventMetadata(correlation_id=correlation_id),
        )


class UserEventHandler(EventHandler):
    """Test event handler for user events."""

    def __init__(self):
        self.events_processed = []

    async def handle(self, event: Event) -> None:
        """Handle user events."""
        self.events_processed.append(event)


class TestEventBus:
    """Test EventBus functionality."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return InMemoryEventBus()

    @pytest.fixture
    def user_handler(self):
        """Create user event handler."""
        return UserEventHandler()

    @pytest.mark.asyncio
    async def test_event_bus_creation(self, event_bus):
        """Test event bus creation."""
        assert event_bus is not None
        assert hasattr(event_bus, "publish")
        assert hasattr(event_bus, "subscribe")

    @pytest.mark.asyncio
    async def test_event_subscription_and_publishing(self, event_bus, user_handler):
        """Test event subscription and publishing."""
        # Subscribe handler to user events
        event_bus.subscribe("user.created", user_handler)

        # Create and publish event
        event = UserCreatedEvent("user-123", "test@example.com", "corr-456")
        await event_bus.publish(event)

        # Allow async processing
        await asyncio.sleep(0.1)

        # Verify handler received event
        assert len(user_handler.events_processed) == 1
        assert user_handler.events_processed[0].event_type == "user.created"
        assert user_handler.events_processed[0].event_data["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, event_bus):
        """Test multiple handlers for same event."""
        handler1 = UserEventHandler()
        handler2 = UserEventHandler()

        # Subscribe both handlers
        event_bus.subscribe("user.created", handler1)
        event_bus.subscribe("user.created", handler2)

        # Publish event
        event = UserCreatedEvent("user-123", "test@example.com")
        await event_bus.publish(event)

        await asyncio.sleep(0.1)

        # Both handlers should receive the event
        assert len(handler1.events_processed) == 1
        assert len(handler2.events_processed) == 1


class TestUser(AggregateRoot):
    """Test aggregate for user domain."""

    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = user_id
        self.email = None
        self.name = None
        self.is_active = False

    def create_user(self, email: str, name: str) -> None:
        """Create user and apply event."""
        event = UserCreatedEvent(self.user_id, email)
        self.apply_event(event)

    def apply_user_created(self, event: Event) -> None:
        """Apply user created event."""
        self.email = event.event_data["email"]
        self.is_active = True

    def apply_event(self, event: Event) -> None:
        """Apply event to aggregate."""
        super().apply_event(event)

        # Use event type to determine handler method
        handler_name = f"apply_{event.event_type.replace('.', '_')}"
        if hasattr(self, handler_name):
            getattr(self, handler_name)(event)


class TestEventSourcing:
    """Test Event Sourcing patterns."""

    @pytest.fixture
    def event_store(self):
        """Create in-memory event store."""
        return InMemoryEventStore()

    @pytest.fixture
    def user_aggregate(self):
        """Create user aggregate."""
        return TestUser("user-123")

    def test_aggregate_creation(self, user_aggregate):
        """Test aggregate creation."""
        assert user_aggregate.user_id == "user-123"
        assert user_aggregate.email is None
        assert not user_aggregate.is_active
        assert user_aggregate.version == 0
        assert len(user_aggregate.uncommitted_events) == 0

    def test_aggregate_event_application(self, user_aggregate):
        """Test applying events to aggregate."""
        user_aggregate.create_user("test@example.com", "Test User")

        # Check state changes
        assert user_aggregate.email == "test@example.com"
        assert user_aggregate.is_active is True
        assert user_aggregate.version == 1
        assert len(user_aggregate.uncommitted_events) == 1

    @pytest.mark.asyncio
    async def test_event_store_append_and_read(self, event_store):
        """Test event store append and read operations."""
        # Create events
        events = [
            UserCreatedEvent("user-123", "test@example.com"),
            Event("user.updated", {"user_id": "user-123", "name": "Updated Name"}),
        ]

        # Append events to stream
        stream_id = "user-123"
        success = await event_store.append_events(stream_id, events)
        assert success is True

        # Read events from stream
        stored_events = await event_store.read_events(stream_id)
        assert len(stored_events) == 2
        assert stored_events[0].event_type == "user.created"
        assert stored_events[1].event_type == "user.updated"

    @pytest.mark.asyncio
    async def test_event_sourced_repository(self, event_store):
        """Test event sourced repository functionality."""
        repository = EventSourcedRepository(event_store, TestUser)

        # Create and save aggregate
        user = TestUser("user-456")
        user.create_user("repo@example.com", "Repo User")

        await repository.save(user)

        # Load aggregate from repository
        loaded_user = await repository.get("user-456")
        assert loaded_user is not None
        assert loaded_user.user_id == "user-456"
        assert loaded_user.email == "repo@example.com"
        assert loaded_user.is_active is True
        assert loaded_user.version == 1


class CreateUserCommand(Command):
    """Test command for creating users."""

    def __init__(self, user_id: str, email: str, name: str):
        super().__init__()
        self.user_id = user_id
        self.email = email
        self.name = name


class CreateUserCommandHandler(CommandHandler):
    """Test command handler for creating users."""

    def __init__(self, repository: EventSourcedRepository):
        self.repository = repository
        self.commands_handled = []

    async def handle(self, command: CreateUserCommand) -> None:
        """Handle create user command."""
        self.commands_handled.append(command)

        # Create aggregate and apply command
        user = TestUser(command.user_id)
        user.create_user(command.email, command.name)

        # Save aggregate
        await self.repository.save(user)


class GetUserQuery(Query):
    """Test query for getting user."""

    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = user_id


class UserReadModel:
    """Test read model for user data."""

    def __init__(self):
        self.users = {}

    async def update(self, event: Event) -> None:
        """Update read model from events."""
        if event.event_type == "user.created":
            user_data = event.event_data
            self.users[user_data["user_id"]] = {
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "created_at": event.timestamp,
            }

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Get user from read model."""
        return self.users.get(user_id, {})


class GetUserQueryHandler(QueryHandler):
    """Test query handler for getting users."""

    def __init__(self, read_model: UserReadModel):
        self.read_model = read_model
        self.queries_handled = []

    async def handle(self, query: GetUserQuery) -> dict[str, Any]:
        """Handle get user query."""
        self.queries_handled.append(query)
        return await self.read_model.get_user(query.user_id)


class TestCQRS:
    """Test CQRS (Command Query Responsibility Segregation) patterns."""

    @pytest.fixture
    def event_store(self):
        """Create event store."""
        return InMemoryEventStore()

    @pytest.fixture
    def event_bus(self):
        """Create event bus."""
        return InMemoryEventBus()

    @pytest.fixture
    def repository(self, event_store):
        """Create repository."""
        return EventSourcedRepository(event_store, TestUser)

    @pytest.fixture
    def command_handler(self, repository):
        """Create command handler."""
        return CreateUserCommandHandler(repository)

    @pytest.fixture
    def read_model(self):
        """Create read model."""
        return UserReadModel()

    @pytest.fixture
    def query_handler(self, read_model):
        """Create query handler."""
        return GetUserQueryHandler(read_model)

    @pytest.fixture
    def cqrs_engine(self, event_bus, event_store):
        """Create CQRS engine."""
        return CQRSEngine(event_bus, event_store)

    @pytest.mark.asyncio
    async def test_command_bus_execution(self, cqrs_engine, command_handler):
        """Test command bus execution."""
        # Register command handler
        command_bus = cqrs_engine.command_bus
        command_bus.register_handler(CreateUserCommand, command_handler)

        # Create and send command
        command = CreateUserCommand("user-789", "cqrs@example.com", "CQRS User")
        await command_bus.send(command)

        # Verify command was handled
        assert len(command_handler.commands_handled) == 1
        assert command_handler.commands_handled[0].user_id == "user-789"

    @pytest.mark.asyncio
    async def test_query_bus_execution(self, cqrs_engine, query_handler, read_model):
        """Test query bus execution."""
        # Register query handler
        query_bus = cqrs_engine.query_bus
        query_bus.register_handler(GetUserQuery, query_handler)

        # Setup read model data
        await read_model.update(UserCreatedEvent("user-890", "query@example.com"))

        # Create and send query
        query = GetUserQuery("user-890")
        result = await query_bus.send(query)

        # Verify query result
        assert result["user_id"] == "user-890"
        assert result["email"] == "query@example.com"
        assert len(query_handler.queries_handled) == 1

    @pytest.mark.asyncio
    async def test_cqrs_full_flow(
        self, cqrs_engine, command_handler, query_handler, read_model, event_bus
    ):
        """Test complete CQRS flow: command -> event -> read model -> query."""
        # Register handlers
        command_bus = cqrs_engine.command_bus
        query_bus = cqrs_engine.query_bus

        command_bus.register_handler(CreateUserCommand, command_handler)
        query_bus.register_handler(GetUserQuery, query_handler)

        # Subscribe read model to events
        event_bus.subscribe("user.created", read_model)

        # Send command
        command = CreateUserCommand("user-999", "flow@example.com", "Flow User")
        await command_bus.send(command)

        # Allow event processing
        await asyncio.sleep(0.1)

        # Query the read model
        query = GetUserQuery("user-999")
        result = await query_bus.send(query)

        # Verify complete flow
        assert result["user_id"] == "user-999"
        assert result["email"] == "flow@example.com"


class OrderSaga(Saga):
    """Test saga for order processing."""

    def __init__(self):
        super().__init__()
        self.order_id = None
        self.payment_id = None
        self.inventory_reserved = False
        self.payment_processed = False

    async def execute(self, command_bus) -> bool:
        """Execute saga steps."""
        try:
            # Step 1: Reserve inventory
            if not self.inventory_reserved:
                # Simulate inventory reservation
                self.inventory_reserved = True
                self.context["inventory_reserved"] = True

            # Step 2: Process payment
            if not self.payment_processed:
                # Simulate payment processing
                self.payment_processed = True
                self.context["payment_processed"] = True

            # All steps completed successfully
            self.status = self.status.__class__.COMPLETED
            return True

        except Exception:
            # Execute compensation
            await self.compensate()
            return False

    async def compensate(self) -> None:
        """Compensate saga steps."""
        # Reverse payment if it was processed
        if self.payment_processed:
            self.payment_processed = False
            self.context["payment_compensated"] = True

        # Release inventory if it was reserved
        if self.inventory_reserved:
            self.inventory_reserved = False
            self.context["inventory_released"] = True


class TestSagaPatterns:
    """Test Saga orchestration patterns."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus."""
        return InMemoryEventBus()

    @pytest.fixture
    def command_bus(self):
        """Create command bus."""
        return CommandBus()

    @pytest.fixture
    def saga_orchestrator(self, command_bus, event_bus):
        """Create saga orchestrator."""
        return SagaOrchestrator(command_bus, event_bus)

    @pytest.fixture
    def saga_manager(self, saga_orchestrator):
        """Create saga manager."""
        return SagaManager(saga_orchestrator)

    def test_saga_creation(self):
        """Test saga creation and initialization."""
        saga = OrderSaga()

        assert saga.saga_id is not None
        assert saga.status is not None
        assert saga.created_at is not None
        assert saga.context == {}
        assert not saga.inventory_reserved
        assert not saga.payment_processed

    @pytest.mark.asyncio
    async def test_saga_execution_success(self, saga_orchestrator):
        """Test successful saga execution."""
        saga = OrderSaga()
        saga_orchestrator.register_saga_type("order", OrderSaga)

        # Start saga execution
        success = await saga_orchestrator.start_saga(saga)

        # Verify successful completion
        assert success is True
        assert saga.inventory_reserved is True
        assert saga.payment_processed is True

    @pytest.mark.asyncio
    async def test_saga_manager_workflow(self, saga_manager):
        """Test saga manager workflow."""
        # Register saga type
        saga_manager.orchestrator.register_saga_type("order", OrderSaga)

        # Create and start saga
        saga_id = await saga_manager.create_and_start_saga(
            "order", {"order_id": "order-123", "amount": 100.0}
        )

        # Verify saga was created
        assert saga_id is not None

        # Get saga status
        status = await saga_manager.orchestrator.get_saga_status(saga_id)
        assert status is not None

    @pytest.mark.asyncio
    async def test_saga_compensation(self, saga_orchestrator):
        """Test saga compensation on failure."""

        # Create a failing saga for testing compensation
        class FailingSaga(Saga):
            async def execute(self, command_bus) -> bool:
                # Simulate some work being done
                self.context["work_done"] = True
                # Then fail
                raise Exception("Simulated failure")

            async def compensate(self) -> None:
                self.context["compensated"] = True

        saga = FailingSaga()

        # Start saga (should fail and compensate)
        success = await saga_orchestrator.start_saga(saga)

        # Verify failure and compensation
        assert success is False
        assert saga.context.get("compensated") is True

    @pytest.mark.asyncio
    async def test_saga_cancellation(self, saga_orchestrator):
        """Test saga cancellation."""
        saga = OrderSaga()
        saga_orchestrator.register_saga_type("order", OrderSaga)

        # Start saga
        await saga_orchestrator.start_saga(saga)

        # Cancel saga
        cancelled = await saga_orchestrator.cancel_saga(saga.saga_id)

        # Verify cancellation
        assert cancelled is True


class TestEventStreamingIntegration:
    """Test integrated event streaming scenarios."""

    @pytest.fixture
    def event_store(self):
        """Create event store."""
        return InMemoryEventStore()

    @pytest.fixture
    def event_bus(self):
        """Create event bus."""
        return InMemoryEventBus()

    @pytest.fixture
    def cqrs_engine(self, event_bus, event_store):
        """Create CQRS engine."""
        return CQRSEngine(event_bus, event_store)

    @pytest.fixture
    def saga_orchestrator(self, cqrs_engine):
        """Create saga orchestrator."""
        return SagaOrchestrator(cqrs_engine.command_bus, cqrs_engine.event_bus)

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, cqrs_engine, saga_orchestrator, event_store):
        """Test complete end-to-end event streaming workflow."""
        # Setup components
        repository = EventSourcedRepository(event_store, TestUser)
        command_handler = CreateUserCommandHandler(repository)
        read_model = UserReadModel()
        query_handler = GetUserQueryHandler(read_model)

        # Register handlers
        cqrs_engine.command_bus.register_handler(CreateUserCommand, command_handler)
        cqrs_engine.query_bus.register_handler(GetUserQuery, query_handler)
        cqrs_engine.event_bus.subscribe("user.created", read_model)

        # Register saga
        saga_orchestrator.register_saga_type("order", OrderSaga)

        # Execute command
        command = CreateUserCommand(
            "integration-user", "integration@example.com", "Integration User"
        )
        await cqrs_engine.command_bus.send(command)

        # Allow event processing
        await asyncio.sleep(0.1)

        # Query read model
        query = GetUserQuery("integration-user")
        result = await cqrs_engine.query_bus.send(query)

        # Start saga
        saga_manager = SagaManager(saga_orchestrator)
        saga_id = await saga_manager.create_and_start_saga("order", {"user_id": "integration-user"})

        # Verify all components worked together
        assert result["user_id"] == "integration-user"
        assert result["email"] == "integration@example.com"
        assert saga_id is not None

        # Verify events were stored
        events = await event_store.read_events("integration-user")
        assert len(events) > 0
        assert events[0].event_type == "user.created"

    @pytest.mark.asyncio
    async def test_event_replay_and_projections(self, event_store, event_bus):
        """Test event replay and projection rebuilding."""
        # Create events and store them
        events = [
            UserCreatedEvent("replay-user", "replay@example.com"),
            Event("user.updated", {"user_id": "replay-user", "email": "updated@example.com"}),
            Event("user.deactivated", {"user_id": "replay-user"}),
        ]

        await event_store.append_events("replay-user", events)

        # Create projection to rebuild from events
        class UserProjection:
            def __init__(self):
                self.state = {}

            async def handle(self, event: Event):
                if event.event_type == "user.created":
                    self.state = {
                        "user_id": event.event_data["user_id"],
                        "email": event.event_data["email"],
                        "active": True,
                    }
                elif event.event_type == "user.updated":
                    self.state.update(event.event_data)
                elif event.event_type == "user.deactivated":
                    self.state["active"] = False

        # Replay events to rebuild projection
        projection = UserProjection()
        stored_events = await event_store.read_events("replay-user")

        for event in stored_events:
            await projection.handle(event)

        # Verify projection state
        assert projection.state["user_id"] == "replay-user"
        assert projection.state["email"] == "updated@example.com"
        assert projection.state["active"] is False
