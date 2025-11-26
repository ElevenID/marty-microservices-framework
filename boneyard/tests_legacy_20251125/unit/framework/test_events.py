"""
Unit tests for framework event bus.

Tests the EventBus class and event handling without external dependencies.
"""

import asyncio
from unittest.mock import patch

import pytest

from marty_msf.framework.events import Event, EventBus, EventHandler


# Mock EventSubscription for testing since it doesn't exist yet
class EventSubscription:
    """Mock EventSubscription for testing."""

    def __init__(self, subscriber_id: str, event_type: str, handler, priority: int = 0):
        self.subscriber_id = subscriber_id
        self.event_type = event_type
        self.handler = handler
        self.priority = priority
        self.active = True

    def deactivate(self):
        self.active = False

    def reactivate(self):
        self.active = True


@pytest.mark.unit
@pytest.mark.asyncio
class TestEvent:
    """Test suite for Event class."""

    def test_event_creation(self):
        """Test event creation with required fields."""
        event = Event(
            id="event-123",
            type="user.registered",
            data={"user_id": 123, "email": "test@example.com"},
        )

        assert event.id == "event-123"
        assert event.type == "user.registered"
        assert event.data == {"user_id": 123, "email": "test@example.com"}
        assert event.timestamp is not None
        assert event.version == 1

    def test_event_creation_with_optional_fields(self):
        """Test event creation with optional fields."""
        event = Event(
            id="event-456",
            type="order.placed",
            data={"order_id": 456},
            source="order-service",
            correlation_id="corr-789",
            version=2,
        )

        assert event.source == "order-service"
        assert event.correlation_id == "corr-789"
        assert event.version == 2

    def test_event_to_dict(self):
        """Test event serialization to dictionary."""
        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        event_dict = event.to_dict()

        assert event_dict["id"] == "event-123"
        assert event_dict["type"] == "user.registered"
        assert event_dict["data"] == {"user_id": 123}
        assert "timestamp" in event_dict
        assert event_dict["version"] == 1

    def test_event_from_dict(self):
        """Test event creation from dictionary."""
        event_dict = {
            "id": "event-456",
            "type": "order.placed",
            "data": {"order_id": 456},
            "timestamp": "2024-01-01T12:00:00Z",
            "version": 2,
        }

        event = Event.from_dict(event_dict)

        assert event.id == "event-456"
        assert event.type == "order.placed"
        assert event.data == {"order_id": 456}
        assert event.version == 2

    def test_event_equality(self):
        """Test event equality comparison."""
        event1 = Event(id="event-123", type="user.registered", data={"user_id": 123})

        event2 = Event(id="event-123", type="user.registered", data={"user_id": 123})

        event3 = Event(id="event-456", type="user.registered", data={"user_id": 123})

        assert event1 == event2
        assert event1 != event3

    def test_event_repr(self):
        """Test event string representation."""
        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        repr_str = repr(event)
        assert "Event" in repr_str
        assert "event-123" in repr_str
        assert "user.registered" in repr_str


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventHandler:
    """Test suite for EventHandler class."""

    async def test_event_handler_creation(self):
        """Test event handler creation."""
        executed_events = []

        async def handler_func(event: Event) -> None:
            executed_events.append(event)

        handler = EventHandler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        assert handler.name == "test-handler"
        assert handler.event_type == "user.registered"
        assert handler.handler_func == handler_func
        assert handler.priority == 0
        assert handler.is_async is True

    async def test_event_handler_with_priority(self):
        """Test event handler with custom priority."""

        async def handler_func(event: Event) -> None:
            pass

        handler = EventHandler(
            name="priority-handler",
            event_type="user.registered",
            handler_func=handler_func,
            priority=10,
        )

        assert handler.priority == 10

    async def test_event_handler_execution(self):
        """Test event handler execution."""
        executed_events = []

        async def handler_func(event: Event) -> None:
            executed_events.append(event)

        handler = EventHandler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await handler.execute(event)

        assert len(executed_events) == 1
        assert executed_events[0] == event

    async def test_event_handler_execution_with_error(self):
        """Test event handler execution with error handling."""

        async def failing_handler(event: Event) -> None:
            raise ValueError("Handler failed")

        handler = EventHandler(
            name="failing-handler", event_type="user.registered", handler_func=failing_handler
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        # Should not raise exception, error should be handled
        await handler.execute(event)

    async def test_event_handler_matches_type(self):
        """Test event handler type matching."""

        async def handler_func(event: Event) -> None:
            pass

        handler = EventHandler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        matching_event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        non_matching_event = Event(id="event-456", type="order.placed", data={"order_id": 456})

        assert handler.matches(matching_event) is True
        assert handler.matches(non_matching_event) is False

    async def test_event_handler_pattern_matching(self):
        """Test event handler pattern matching."""

        async def handler_func(event: Event) -> None:
            pass

        # Handler that matches all user events
        handler = EventHandler(name="user-handler", event_type="user.*", handler_func=handler_func)

        user_registered = Event(id="event-123", type="user.registered", data={"user_id": 123})

        user_updated = Event(id="event-456", type="user.updated", data={"user_id": 123})

        order_placed = Event(id="event-789", type="order.placed", data={"order_id": 789})

        assert handler.matches(user_registered) is True
        assert handler.matches(user_updated) is True
        assert handler.matches(order_placed) is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventSubscription:
    """Test suite for EventSubscription class."""

    def test_subscription_creation(self):
        """Test event subscription creation."""

        async def handler_func(event: Event) -> None:
            pass

        subscription = EventSubscription(
            subscriber_id="service-123", event_type="user.registered", handler_func=handler_func
        )

        assert subscription.subscriber_id == "service-123"
        assert subscription.event_type == "user.registered"
        assert subscription.handler_func == handler_func
        assert subscription.is_active is True

    def test_subscription_deactivation(self):
        """Test subscription deactivation."""

        async def handler_func(event: Event) -> None:
            pass

        subscription = EventSubscription(
            subscriber_id="service-123", event_type="user.registered", handler_func=handler_func
        )

        assert subscription.is_active is True

        subscription.deactivate()
        assert subscription.is_active is False

    def test_subscription_reactivation(self):
        """Test subscription reactivation."""

        async def handler_func(event: Event) -> None:
            pass

        subscription = EventSubscription(
            subscriber_id="service-123", event_type="user.registered", handler_func=handler_func
        )

        subscription.deactivate()
        assert subscription.is_active is False

        subscription.activate()
        assert subscription.is_active is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventBus:
    """Test suite for EventBus class."""

    def test_event_bus_creation(self):
        """Test event bus creation."""
        bus = EventBus(service_name="test-service")

        assert bus.service_name == "test-service"
        assert len(bus.handlers) == 0
        assert len(bus.subscriptions) == 0
        assert bus.is_running is False

    def test_event_bus_register_handler(self):
        """Test registering event handlers."""
        bus = EventBus(service_name="test-service")

        async def handler_func(event: Event) -> None:
            pass

        handler = bus.register_handler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        assert len(bus.handlers) == 1
        assert handler.name == "test-handler"
        assert handler.event_type == "user.registered"

    def test_event_bus_register_duplicate_handler(self):
        """Test registering duplicate handler names."""
        bus = EventBus(service_name="test-service")

        async def handler_func(event: Event) -> None:
            pass

        bus.register_handler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        with pytest.raises(ValueError, match="Handler 'test-handler' already registered"):
            bus.register_handler(
                name="test-handler", event_type="order.placed", handler_func=handler_func
            )

    def test_event_bus_unregister_handler(self):
        """Test unregistering event handlers."""
        bus = EventBus(service_name="test-service")

        async def handler_func(event: Event) -> None:
            pass

        bus.register_handler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        assert len(bus.handlers) == 1

        bus.unregister_handler("test-handler")
        assert len(bus.handlers) == 0

    async def test_event_bus_publish_event(self):
        """Test publishing events to the bus."""
        bus = EventBus(service_name="test-service")
        executed_events = []

        async def handler_func(event: Event) -> None:
            executed_events.append(event)

        bus.register_handler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)

        # Give some time for async processing
        await asyncio.sleep(0.1)

        assert len(executed_events) == 1
        assert executed_events[0] == event

    async def test_event_bus_publish_multiple_handlers(self):
        """Test publishing event to multiple handlers."""
        bus = EventBus(service_name="test-service")
        handler1_events = []
        handler2_events = []

        async def handler1_func(event: Event) -> None:
            handler1_events.append(event)

        async def handler2_func(event: Event) -> None:
            handler2_events.append(event)

        bus.register_handler(
            name="handler-1", event_type="user.registered", handler_func=handler1_func, priority=1
        )

        bus.register_handler(
            name="handler-2", event_type="user.registered", handler_func=handler2_func, priority=2
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)
        await asyncio.sleep(0.1)

        assert len(handler1_events) == 1
        assert len(handler2_events) == 1
        assert handler1_events[0] == event
        assert handler2_events[0] == event

    async def test_event_bus_handler_priority_ordering(self):
        """Test event handler execution order based on priority."""
        bus = EventBus(service_name="test-service")
        execution_order = []

        async def high_priority_handler(event: Event) -> None:
            execution_order.append("high")

        async def low_priority_handler(event: Event) -> None:
            execution_order.append("low")

        async def medium_priority_handler(event: Event) -> None:
            execution_order.append("medium")

        # Register handlers in random order
        bus.register_handler(
            name="low-handler",
            event_type="user.registered",
            handler_func=low_priority_handler,
            priority=1,
        )

        bus.register_handler(
            name="high-handler",
            event_type="user.registered",
            handler_func=high_priority_handler,
            priority=10,
        )

        bus.register_handler(
            name="medium-handler",
            event_type="user.registered",
            handler_func=medium_priority_handler,
            priority=5,
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)
        await asyncio.sleep(0.1)

        # Should execute in priority order (high to low)
        assert execution_order == ["high", "medium", "low"]

    async def test_event_bus_subscription_management(self):
        """Test event subscription management."""
        bus = EventBus(service_name="test-service")
        executed_events = []

        async def handler_func(event: Event) -> None:
            executed_events.append(event)

        subscription = bus.subscribe(
            subscriber_id="service-123", event_type="user.registered", handler_func=handler_func
        )

        assert len(bus.subscriptions) == 1
        assert subscription.subscriber_id == "service-123"

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)
        await asyncio.sleep(0.1)

        assert len(executed_events) == 1

        # Unsubscribe
        bus.unsubscribe("service-123", "user.registered")
        assert len(bus.subscriptions) == 0

    async def test_event_bus_subscription_deactivation(self):
        """Test subscription deactivation without removal."""
        bus = EventBus(service_name="test-service")
        executed_events = []

        async def handler_func(event: Event) -> None:
            executed_events.append(event)

        subscription = bus.subscribe(
            subscriber_id="service-123", event_type="user.registered", handler_func=handler_func
        )

        # Deactivate subscription
        subscription.deactivate()

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)
        await asyncio.sleep(0.1)

        # Should not execute because subscription is deactivated
        assert len(executed_events) == 0

    async def test_event_bus_error_handling(self):
        """Test event bus error handling."""
        bus = EventBus(service_name="test-service")
        successful_executions = []

        async def failing_handler(event: Event) -> None:
            raise ValueError("Handler failed")

        async def successful_handler(event: Event) -> None:
            successful_executions.append(event)

        bus.register_handler(
            name="failing-handler", event_type="user.registered", handler_func=failing_handler
        )

        bus.register_handler(
            name="successful-handler", event_type="user.registered", handler_func=successful_handler
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)
        await asyncio.sleep(0.1)

        # Successful handler should still execute despite failing handler
        assert len(successful_executions) == 1

    async def test_event_bus_middleware(self):
        """Test event bus middleware functionality."""
        bus = EventBus(service_name="test-service")
        middleware_calls = []

        async def test_middleware(event: Event, next_handler):
            middleware_calls.append(f"before:{event.id}")
            await next_handler(event)
            middleware_calls.append(f"after:{event.id}")

        async def handler_func(event: Event) -> None:
            middleware_calls.append(f"handler:{event.id}")

        bus.add_middleware(test_middleware)
        bus.register_handler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)
        await asyncio.sleep(0.1)

        assert "before:event-123" in middleware_calls
        assert "handler:event-123" in middleware_calls
        assert "after:event-123" in middleware_calls

    async def test_event_bus_start_stop(self):
        """Test starting and stopping the event bus."""
        bus = EventBus(service_name="test-service")

        assert bus.is_running is False

        await bus.start()
        assert bus.is_running is True

        await bus.stop()
        assert bus.is_running is False

    async def test_event_bus_metrics_collection(self):
        """Test event bus metrics collection."""
        bus = EventBus(service_name="test-service")

        async def handler_func(event: Event) -> None:
            pass

        bus.register_handler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)
        await asyncio.sleep(0.1)

        metrics = bus.get_metrics()

        assert "events_published" in metrics
        assert "events_processed" in metrics
        assert "handler_execution_time" in metrics
        assert metrics["events_published"] >= 1

    async def test_event_bus_event_filtering(self):
        """Test event filtering functionality."""
        bus = EventBus(service_name="test-service")
        filtered_events = []

        def event_filter(event: Event) -> bool:
            # Only allow events from specific source
            return event.source == "trusted-service"

        async def handler_func(event: Event) -> None:
            filtered_events.append(event)

        bus.add_filter(event_filter)
        bus.register_handler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        # Event from trusted source
        trusted_event = Event(
            id="event-123", type="user.registered", data={"user_id": 123}, source="trusted-service"
        )

        # Event from untrusted source
        untrusted_event = Event(
            id="event-456",
            type="user.registered",
            data={"user_id": 456},
            source="untrusted-service",
        )

        await bus.publish(trusted_event)
        await bus.publish(untrusted_event)
        await asyncio.sleep(0.1)

        # Only trusted event should be processed
        assert len(filtered_events) == 1
        assert filtered_events[0].id == "event-123"

    @patch("src.framework.events.logger")
    async def test_event_bus_logging(self, mock_logger):
        """Test event bus logging functionality."""
        bus = EventBus(service_name="test-service")

        async def handler_func(event: Event) -> None:
            pass

        bus.register_handler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        event = Event(id="event-123", type="user.registered", data={"user_id": 123})

        await bus.publish(event)
        await asyncio.sleep(0.1)

        # Verify logging calls were made
        mock_logger.info.assert_called()
        mock_logger.debug.assert_called()
