"""
Unit tests for framework event bus.

Tests the EventBus class and event handling without external dependencies.
"""

import asyncio
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from mmf.framework.events import Event, EventBus, EventHandler
from mmf.framework.events.enhanced_event_bus import (
    BaseEvent,
    DeliveryGuarantee,
    EventFilter,
    EventMetadata,
)


# Concrete EventHandler for testing
class ConcreteEventHandler(EventHandler):
    def __init__(self, name, event_type, handler_func, priority=0):
        super().__init__(handler_id=name, priority=priority)
        self._event_type = event_type
        self.handler_func = handler_func
        self.executed_events = []

    @property
    def event_types(self):
        return [self._event_type]

    async def handle(self, event: BaseEvent) -> None:
        if asyncio.iscoroutinefunction(self.handler_func):
            await self.handler_func(event)
        else:
            self.handler_func(event)
        self.executed_events.append(event)

    def can_handle(self, event: BaseEvent) -> bool:
        return event.event_type == self._event_type


# InMemory EventBus for testing
class InMemoryEventBus(EventBus):
    def __init__(self, service_name="test-service"):
        self.service_name = service_name
        self._running = True
        self._subscriptions = {}  # Map subscription_id to (handler, filter)
        self._handlers_by_type = {}  # Map event_type to list of handlers

    async def publish(
        self,
        event: BaseEvent,
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
        delay: timedelta | None = None,
    ) -> None:
        # Bypass Kafka and dispatch directly
        await self._dispatch_event(event)

    async def publish_batch(
        self,
        events: list[BaseEvent],
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
    ) -> None:
        for event in events:
            await self.publish(event, delivery_guarantee=delivery_guarantee)

    async def subscribe(
        self, handler: EventHandler, event_filter: EventFilter | None = None
    ) -> str:
        subscription_id = str(uuid.uuid4())
        self._subscriptions[subscription_id] = (handler, event_filter)

        for event_type in handler.event_types:
            if event_type not in self._handlers_by_type:
                self._handlers_by_type[event_type] = []
            self._handlers_by_type[event_type].append(handler)

        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        if subscription_id in self._subscriptions:
            handler, _ = self._subscriptions.pop(subscription_id)
            for event_type in handler.event_types:
                if event_type in self._handlers_by_type:
                    if handler in self._handlers_by_type[event_type]:
                        self._handlers_by_type[event_type].remove(handler)
            return True
        return False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def _dispatch_event(self, event: BaseEvent) -> None:
        handlers = self._handlers_by_type.get(event.event_type, [])
        for handler in handlers:
            if handler.can_handle(event):
                await handler.handle(event)


@pytest.mark.unit
@pytest.mark.asyncio
class TestEvent:
    """Test suite for Event class."""

    def test_event_creation(self):
        """Test event creation with required fields."""
        event = Event(
            event_type="user.registered",
            data={"user_id": 123, "email": "test@example.com"},
            event_id="event-123",
        )

        assert event.event_id == "event-123"
        assert event.event_type == "user.registered"
        assert event.data == {"user_id": 123, "email": "test@example.com"}
        assert event.timestamp is not None

    def test_event_creation_with_optional_fields(self):
        """Test event creation with optional fields."""
        event = Event(
            event_type="order.placed",
            data={"order_id": 456},
            event_id="event-456",
            source_service="order-service",
            correlation_id="corr-789",
            version=2,
        )

        assert event.metadata.source_service == "order-service"
        assert event.metadata.correlation_id == "corr-789"
        assert event.metadata.version == 2

    def test_event_to_dict(self):
        """Test event serialization to dictionary."""
        event = Event(event_type="user.registered", data={"user_id": 123}, event_id="event-123")

        event_dict = event.to_dict()

        assert event_dict["event_id"] == "event-123"
        assert event_dict["event_type"] == "user.registered"
        assert event_dict["data"] == {"user_id": 123}
        assert "timestamp" in event_dict

    def test_event_from_dict(self):
        """Test event creation from dictionary."""
        event_dict = {
            "event_id": "event-456",
            "event_type": "order.placed",
            "data": {"order_id": 456},
            "timestamp": "2024-01-01T12:00:00Z",
            "metadata": {"version": 2},
        }

        event = Event.from_dict(event_dict)

        assert event.event_id == "event-456"
        assert event.event_type == "order.placed"
        assert event.data == {"order_id": 456}
        assert event.metadata.version == 2


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventHandler:
    """Test suite for EventHandler class."""

    async def test_event_handler_creation(self):
        """Test event handler creation."""

        async def handler_func(event: Event) -> None:
            pass

        handler = ConcreteEventHandler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        assert handler.handler_id == "test-handler"
        assert "user.registered" in handler.event_types

    async def test_event_handler_execution(self):
        """Test event handler execution."""
        executed_events = []

        async def handler_func(event: Event) -> None:
            executed_events.append(event)

        handler = ConcreteEventHandler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        event = Event(event_type="user.registered", data={"user_id": 123}, event_id="event-123")

        await handler.handle(event)

        assert len(executed_events) == 1
        assert executed_events[0] == event


@pytest.mark.unit
@pytest.mark.asyncio
class TestEventBus:
    """Test suite for EventBus class."""

    def test_event_bus_creation(self):
        """Test event bus creation."""
        bus = InMemoryEventBus(service_name="test-service")
        assert bus.service_name == "test-service"

    async def test_event_bus_subscribe_publish(self):
        """Test subscribing and publishing events."""
        bus = InMemoryEventBus(service_name="test-service")
        executed_events = []

        async def handler_func(event: Event) -> None:
            executed_events.append(event)

        handler = ConcreteEventHandler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        await bus.subscribe(handler)

        event = Event(event_type="user.registered", data={"user_id": 123}, event_id="event-123")

        await bus.publish(event)

        assert len(executed_events) == 1
        assert executed_events[0] == event

    async def test_event_bus_unsubscribe(self):
        """Test unregistering event handlers."""
        bus = InMemoryEventBus(service_name="test-service")

        async def handler_func(event: Event) -> None:
            pass

        handler = ConcreteEventHandler(
            name="test-handler", event_type="user.registered", handler_func=handler_func
        )

        sub_id = await bus.subscribe(handler)

        # Verify subscription
        assert sub_id in bus._subscriptions
        assert handler in bus._handlers_by_type["user.registered"]

        await bus.unsubscribe(sub_id)

        # Verify unsubscription
        assert sub_id not in bus._subscriptions
        assert handler not in bus._handlers_by_type["user.registered"]

    async def test_event_bus_multiple_handlers(self):
        """Test publishing event to multiple handlers."""
        bus = InMemoryEventBus(service_name="test-service")
        handler1_events = []
        handler2_events = []

        async def handler1_func(event: Event) -> None:
            handler1_events.append(event)

        async def handler2_func(event: Event) -> None:
            handler2_events.append(event)

        handler1 = ConcreteEventHandler(
            name="handler-1", event_type="user.registered", handler_func=handler1_func
        )
        handler2 = ConcreteEventHandler(
            name="handler-2", event_type="user.registered", handler_func=handler2_func
        )

        await bus.subscribe(handler1)
        await bus.subscribe(handler2)

        event = Event(event_type="user.registered", data={"user_id": 123}, event_id="event-123")

        await bus.publish(event)

        assert len(handler1_events) == 1
        assert len(handler2_events) == 1
