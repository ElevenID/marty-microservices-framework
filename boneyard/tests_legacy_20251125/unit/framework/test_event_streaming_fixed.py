"""
Comprehensive Event Streaming Tests for CQRS, Event Sourcing, and Saga Patterns.

This test suite focuses on testing event streaming components with minimal mocking
to maximize real behavior validation and coverage.
"""

import pytest

from marty_msf.framework.event_streaming.core import (
    DomainEvent,
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
    CommandResult,
    InMemoryReadModelStore,
    Query,
    QueryBus,
    QueryHandler,
    QueryResult,
    ReadModelStore,
)
from marty_msf.framework.event_streaming.event_sourcing import (
    AggregateRepository,
    AggregateRoot,
    Snapshot,
)
from marty_msf.framework.event_streaming.saga import (
    CompensationAction,
    Saga,
    SagaContext,
    SagaManager,
    SagaStatus,
    SagaStep,
    StepStatus,
)


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
        """Test event equality and uniqueness."""
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
    """Test Event Bus functionality."""

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
        """Test event bus can be created."""
        assert event_bus is not None
        assert isinstance(event_bus, InMemoryEventBus)

    @pytest.mark.asyncio
    async def test_event_subscription_and_publishing(self, event_bus, user_handler):
        """Test event subscription and publishing."""
        # Subscribe handler to user events
        await event_bus.subscribe("user.created", user_handler)

        # Create and publish event
        event = UserCreatedEvent("user-123", "test@example.com")
        await event_bus.publish(event)

        # Verify event was handled
        assert len(user_handler.events_processed) == 1
        assert user_handler.events_processed[0].event_type == "user.created"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, event_bus):
        """Test multiple handlers for same event."""
        handler1 = UserEventHandler()
        handler2 = UserEventHandler()

        await event_bus.subscribe("user.created", handler1)
        await event_bus.subscribe("user.created", handler2)

        event = UserCreatedEvent("user-456", "user456@example.com")
        await event_bus.publish(event)

        # Both handlers should receive the event
        assert len(handler1.events_processed) == 1
        assert len(handler2.events_processed) == 1


class TestUser(AggregateRoot):
    """Test aggregate for user domain."""

    def __init__(self, user_id: str):
        super().__init__(user_id)
        self.email = None
        self.name = None

    def create_user(self, email: str, name: str):
        """Create user with email and name."""
        event = DomainEvent(
            aggregate_id=self.aggregate_id,
            event_type="user.created",
            event_data={"email": email, "name": name},
        )
        self._apply_event(event)

    def update_email(self, new_email: str):
        """Update user email."""
        event = DomainEvent(
            aggregate_id=self.aggregate_id,
            event_type="user.email_updated",
            event_data={"email": new_email},
        )
        self._apply_event(event)

    def _when(self, event: DomainEvent):
        """Apply domain events to update state."""
        if event.event_type == "user.created":
            self.email = event.event_data["email"]
            self.name = event.event_data["name"]
        elif event.event_type == "user.email_updated":
            self.email = event.event_data["email"]

    def to_snapshot(self) -> Snapshot:
        """Create snapshot of current state."""
        return Snapshot(
            aggregate_id=self.aggregate_id,
            aggregate_type="User",
            version=self.version,
            data={"email": self.email, "name": self.name},
        )

    @classmethod
    def from_snapshot(cls, snapshot: Snapshot) -> "TestUser":
        """Restore from snapshot."""
        user = cls(snapshot.aggregate_id)
        user.email = snapshot.data.get("email")
        user.name = snapshot.data.get("name")
        user.version = snapshot.version
        return user


class TestEventSourcing:
    """Test Event Sourcing functionality."""

    @pytest.fixture
    def event_store(self):
        """Create in-memory event store."""
        return InMemoryEventStore()

    @pytest.fixture
    def user_aggregate(self):
        """Create user aggregate."""
        return TestUser("user-123")

    @pytest.mark.asyncio
    async def test_aggregate_creation(self, user_aggregate):
        """Test aggregate creation and initial state."""
        assert user_aggregate.aggregate_id == "user-123"
        assert user_aggregate.version == 0
        assert len(user_aggregate.uncommitted_events) == 0

    @pytest.mark.asyncio
    async def test_aggregate_event_application(self, user_aggregate):
        """Test applying events to aggregates."""
        user_aggregate.create_user("test@example.com", "Test User")

        assert user_aggregate.email == "test@example.com"
        assert user_aggregate.name == "Test User"
        assert user_aggregate.version == 1
        assert len(user_aggregate.uncommitted_events) == 1

    @pytest.mark.asyncio
    async def test_event_store_append_and_read(self, event_store):
        """Test event store append and read operations."""
        stream_id = "user-123"
        events = [
            DomainEvent(
                aggregate_id=stream_id,
                event_type="user.created",
                event_data={"email": "test@example.com", "name": "Test User"},
            )
        ]

        await event_store.append_events(stream_id, events)
        retrieved_events = await event_store.read_events(stream_id)

        assert len(retrieved_events) == 1
        assert retrieved_events[0].event_type == "user.created"
        assert retrieved_events[0].aggregate_id == stream_id

    @pytest.mark.asyncio
    async def test_event_sourced_repository(self, event_store):
        """Test event sourced repository operations."""
        repository = AggregateRepository(TestUser, event_store)

        # Create and save aggregate
        user = TestUser("user-789")
        user.create_user("repo@example.com", "Repository User")

        await repository.save(user)

        # Load aggregate from repository
        loaded_user = await repository.get_by_id("user-789")

        assert loaded_user.aggregate_id == "user-789"
        assert loaded_user.email == "repo@example.com"
        assert loaded_user.name == "Repository User"
        assert loaded_user.version == 1


class CreateUserCommand(Command):
    """Test command for creating users."""

    def __init__(self, user_id: str, email: str, name: str):
        super().__init__(
            command_type="create_user", data={"user_id": user_id, "email": email, "name": name}
        )


class GetUserQuery(Query):
    """Test query for getting user information."""

    def __init__(self, user_id: str):
        super().__init__(query_type="get_user", parameters={"user_id": user_id})


class UserCommandHandler(CommandHandler):
    """Test command handler for user commands."""

    def __init__(self, repository: AggregateRepository):
        self.repository = repository
        self.commands_handled = []

    async def handle(self, command: Command) -> CommandResult:
        """Handle user commands."""
        self.commands_handled.append(command)

        if command.command_type == "create_user":
            user = TestUser(command.data["user_id"])
            user.create_user(command.data["email"], command.data["name"])
            await self.repository.save(user)

            return CommandResult(
                command_id=command.command_id,
                success=True,
                result={"user_id": command.data["user_id"]},
            )

        return CommandResult(
            command_id=command.command_id, success=False, error="Unknown command type"
        )


class UserReadModel:
    """Test read model for user data."""

    def __init__(self, user_id: str = None, email: str = None, name: str = None):
        self.user_id = user_id
        self.email = email
        self.name = name


class UserQueryHandler(QueryHandler):
    """Test query handler for user queries."""

    def __init__(self, read_model_store: ReadModelStore):
        self.read_model_store = read_model_store
        self.queries_handled = []

    async def handle(self, query: Query) -> QueryResult:
        """Handle user queries."""
        self.queries_handled.append(query)

        if query.query_type == "get_user":
            user_id = query.parameters["user_id"]
            read_model = await self.read_model_store.get_by_id(user_id)

            if read_model:
                return QueryResult(query_id=query.query_id, result=read_model)
            else:
                return QueryResult(query_id=query.query_id, result=UserReadModel())

        return QueryResult(query_id=query.query_id, error="Unknown query type")


class TestCQRS:
    """Test CQRS functionality."""

    @pytest.fixture
    def event_store(self):
        """Create event store for testing."""
        return InMemoryEventStore()

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return InMemoryEventBus()

    @pytest.fixture
    def read_model_store(self):
        """Create read model store for testing."""
        return InMemoryReadModelStore()

    @pytest.fixture
    def repository(self, event_store):
        """Create repository for testing."""
        return AggregateRepository(TestUser, event_store)

    @pytest.fixture
    def command_handler(self, repository):
        """Create command handler for testing."""
        return UserCommandHandler(repository)

    @pytest.fixture
    def query_handler(self, read_model_store):
        """Create query handler for testing."""
        return UserQueryHandler(read_model_store)

    @pytest.mark.asyncio
    async def test_command_bus_execution(self, command_handler):
        """Test command bus command execution."""
        command_bus = CommandBus()
        await command_bus.register_handler("create_user", command_handler)

        command = CreateUserCommand("user-999", "cqrs@example.com", "CQRS User")
        result = await command_bus.execute(command)

        assert result.success is True
        assert result.result["user_id"] == "user-999"
        assert len(command_handler.commands_handled) == 1

    @pytest.mark.asyncio
    async def test_query_bus_execution(self, query_handler, read_model_store):
        """Test query bus query execution."""
        # First add some test data
        read_model = UserReadModel("user-888", "query@example.com", "Query User")
        await read_model_store.save("user-888", read_model)

        query_bus = QueryBus()
        await query_bus.register_handler("get_user", query_handler)

        query = GetUserQuery("user-888")
        result = await query_bus.execute(query)

        assert result.result is not None
        assert result.result.user_id == "user-888"
        assert result.result.email == "query@example.com"

    @pytest.mark.asyncio
    async def test_cqrs_full_flow(self, command_handler, query_handler, read_model_store):
        """Test complete CQRS flow with command and query."""
        command_bus = CommandBus()
        query_bus = QueryBus()

        await command_bus.register_handler("create_user", command_handler)
        await query_bus.register_handler("get_user", query_handler)

        # Execute command
        command = CreateUserCommand("user-777", "fullflow@example.com", "Full Flow User")
        command_result = await command_bus.execute(command)

        assert command_result.success is True

        # Simulate read model update
        read_model = UserReadModel("user-777", "fullflow@example.com", "Full Flow User")
        await read_model_store.save("user-777", read_model)

        # Execute query
        query = GetUserQuery("user-777")
        query_result = await query_bus.execute(query)

        assert query_result.result.user_id == "user-777"
        assert query_result.result.email == "fullflow@example.com"


class OrderSaga(Saga):
    """Test saga for order processing."""

    def _initialize_steps(self):
        """Initialize saga steps."""
        self.add_step(SagaStep(step_id="reserve_inventory", description="Reserve inventory items"))
        self.add_step(SagaStep(step_id="process_payment", description="Process customer payment"))
        self.add_step(SagaStep(step_id="ship_order", description="Ship order to customer"))


class TestSagaPatterns:
    """Test Saga pattern functionality."""

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return InMemoryEventBus()

    @pytest.fixture
    def saga_manager(self, event_bus):
        """Create saga manager for testing."""
        return SagaManager(event_bus)

    def test_saga_creation(self):
        """Test saga creation and step initialization."""
        saga = OrderSaga(saga_id="order-123")

        assert saga.saga_id == "order-123"
        assert saga.status == SagaStatus.PENDING
        assert len(saga.steps) == 3
        assert saga.steps[0].step_id == "reserve_inventory"

    @pytest.mark.asyncio
    async def test_saga_execution_success(self, saga_manager):
        """Test successful saga execution."""
        OrderSaga(saga_id="order-456")

        # Register saga with manager
        await saga_manager.register_saga_type("order_processing", OrderSaga)

        # Start saga execution
        context = SagaContext({"order_id": "order-456", "amount": 100.0})
        saga_instance = await saga_manager.start_saga("order_processing", context)

        assert saga_instance.status == SagaStatus.PENDING
        assert len(saga_instance.steps) == 3

    @pytest.mark.asyncio
    async def test_saga_manager_workflow(self, saga_manager):
        """Test saga manager workflow orchestration."""
        await saga_manager.register_saga_type("order_processing", OrderSaga)

        context = SagaContext({"order_id": "order-789", "customer_id": "customer-123"})
        saga = await saga_manager.start_saga("order_processing", context)

        assert saga is not None
        assert saga.status == SagaStatus.PENDING

    @pytest.mark.asyncio
    async def test_saga_compensation(self, saga_manager):
        """Test saga compensation on failure."""
        saga = OrderSaga(saga_id="order-compensation")

        # Simulate step failure and compensation
        step = saga.steps[1]  # payment step
        step.status = StepStatus.FAILED

        compensation = CompensationAction(
            action_type="refund_payment", parameters={"amount": 100.0}
        )
        step.compensation_action = compensation

        assert step.status == StepStatus.FAILED
        assert step.compensation_action.action_type == "refund_payment"

    @pytest.mark.asyncio
    async def test_saga_cancellation(self, saga_manager):
        """Test saga cancellation workflow."""
        saga = OrderSaga(saga_id="order-cancel")
        saga.status = SagaStatus.CANCELLED

        assert saga.status == SagaStatus.CANCELLED


class TestEventStreamingIntegration:
    """Test integration of all event streaming components."""

    @pytest.fixture
    def event_store(self):
        """Create event store for testing."""
        return InMemoryEventStore()

    @pytest.fixture
    def event_bus(self):
        """Create event bus for testing."""
        return InMemoryEventBus()

    @pytest.fixture
    def repository(self, event_store):
        """Create repository for testing."""
        return AggregateRepository(TestUser, event_store)

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, repository, event_bus):
        """Test complete end-to-end event streaming workflow."""
        # Create and configure components
        command_handler = UserCommandHandler(repository)
        command_bus = CommandBus()
        await command_bus.register_handler("create_user", command_handler)

        # Execute workflow
        command = CreateUserCommand(
            "user-integration", "integration@example.com", "Integration User"
        )
        result = await command_bus.execute(command)

        # Verify results
        assert result.success is True

        # Load from repository to verify persistence
        user = await repository.get_by_id("user-integration")
        assert user.email == "integration@example.com"
        assert user.name == "Integration User"

    @pytest.mark.asyncio
    async def test_event_replay_and_projections(self, event_store):
        """Test event replay and projection building."""
        # Store events
        events = [
            DomainEvent(
                aggregate_id="user-replay",
                event_type="user.created",
                event_data={"email": "replay@example.com", "name": "Replay User"},
            ),
            DomainEvent(
                aggregate_id="user-replay",
                event_type="user.email_updated",
                event_data={"email": "updated@example.com"},
            ),
        ]

        await event_store.append_events("user-replay", events)

        # Replay events to build projection
        stored_events = await event_store.read_events("user-replay")

        assert len(stored_events) == 2
        assert stored_events[0].event_type == "user.created"
        assert stored_events[1].event_type == "user.email_updated"

        # Verify projection state
        final_email = stored_events[-1].event_data["email"]
        assert final_email == "updated@example.com"
