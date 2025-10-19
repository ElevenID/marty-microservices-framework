"""
Event streaming and processing infrastructure.

Provides high-throughput event streaming capabilities with event sourcing,
CQRS patterns, and advanced stream processing features.

Features:
- Event sourcing and replay capabilities
- Stream processing with windowing and aggregations
- Event store abstractions (File, Redis, Kafka)
- Command Query Responsibility Segregation (CQRS)
- Snapshot management for performance
- Event versioning and schema evolution
- Distributed event processing
"""

import asyncio
import builtins
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
E = TypeVar("E", bound="Event")


class EventType(Enum):
    """Event types for categorization."""

    COMMAND = "command"
    DOMAIN = "domain"
    INTEGRATION = "integration"
    SYSTEM = "system"


@dataclass
class Event:
    """Base event class."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_id: str = ""
    event_type: str = ""
    version: int = 1
    timestamp: float = field(default_factory=time.time)
    data: builtins.dict[str, Any] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    causation_id: str | None = None

    def __post_init__(self):
        if not self.event_type:
            self.event_type = self.__class__.__name__

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert event to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "Event":
        """Create event from dictionary."""
        return cls(**data)


@dataclass
class EventStream:
    """Event stream metadata."""

    stream_id: str
    version: int = 0
    position: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class EventStoreRecord:
    """Event store record."""

    stream_id: str
    position: int
    event: Event
    timestamp: float = field(default_factory=time.time)


class EventStore(ABC):
    """Abstract event store interface."""

    @abstractmethod
    async def append_events(
        self,
        stream_id: str,
        events: builtins.list[Event],
        expected_version: int | None = None,
    ) -> bool:
        """Append events to stream."""

    @abstractmethod
    async def read_events(
        self,
        stream_id: str,
        from_position: int = 0,
        max_count: int | None = None,
    ) -> builtins.list[EventStoreRecord]:
        """Read events from stream."""

    @abstractmethod
    async def read_all_events(
        self,
        from_position: int = 0,
        max_count: int | None = None,
    ) -> builtins.list[EventStoreRecord]:
        """Read all events across streams."""

    @abstractmethod
    async def get_stream_version(self, stream_id: str) -> int:
        """Get current stream version."""

    @abstractmethod
    async def delete_stream(self, stream_id: str) -> bool:
        """Delete event stream."""


class InMemoryEventStore(EventStore):
    """In-memory event store for development and testing."""

    def __init__(self):
        self.streams: builtins.dict[str, EventStream] = {}
        self.events: builtins.dict[str, builtins.list[EventStoreRecord]] = {}
        self.global_position = 0

    async def append_events(
        self,
        stream_id: str,
        events: builtins.list[Event],
        expected_version: int | None = None,
    ) -> bool:
        """Append events to stream."""
        try:
            # Get or create stream
            stream = self.streams.get(stream_id)
            if not stream:
                stream = EventStream(stream_id=stream_id)
                self.streams[stream_id] = stream
                self.events[stream_id] = []

            # Check expected version
            if expected_version is not None and stream.version != expected_version:
                logger.warning(
                    f"Version mismatch for stream {stream_id}: expected {expected_version}, got {stream.version}"
                )
                return False

            # Append events
            for event in events:
                record = EventStoreRecord(
                    stream_id=stream_id,
                    position=stream.position,
                    event=event,
                )

                self.events[stream_id].append(record)
                stream.position += 1
                stream.version += 1
                self.global_position += 1

            stream.updated_at = time.time()
            return True

        except Exception as e:
            logger.error(f"Failed to append events to stream {stream_id}: {e}")
            return False

    async def read_events(
        self,
        stream_id: str,
        from_position: int = 0,
        max_count: int | None = None,
    ) -> builtins.list[EventStoreRecord]:
        """Read events from stream."""
        if stream_id not in self.events:
            return []

        events = self.events[stream_id]

        # Filter by position
        filtered = [e for e in events if e.position >= from_position]

        # Limit count
        if max_count:
            filtered = filtered[:max_count]

        return filtered

    async def read_all_events(
        self,
        from_position: int = 0,
        max_count: int | None = None,
    ) -> builtins.list[EventStoreRecord]:
        """Read all events across streams."""
        all_events = []

        for stream_events in self.events.values():
            all_events.extend(stream_events)

        # Sort by timestamp
        all_events.sort(key=lambda e: e.timestamp)

        # Apply position filter (simplified)
        if from_position > 0:
            all_events = all_events[from_position:]

        # Limit count
        if max_count:
            all_events = all_events[:max_count]

        return all_events

    async def get_stream_version(self, stream_id: str) -> int:
        """Get current stream version."""
        stream = self.streams.get(stream_id)
        return stream.version if stream else 0

    async def delete_stream(self, stream_id: str) -> bool:
        """Delete event stream."""
        if stream_id in self.streams:
            del self.streams[stream_id]
            del self.events[stream_id]
            return True
        return False


class EventHandler(ABC):
    """Abstract event handler interface."""

    @abstractmethod
    async def handle(self, event: Event) -> bool:
        """Handle event. Return True if successful."""

    @abstractmethod
    def can_handle(self, event: Event) -> bool:
        """Check if handler can process this event."""


class EventProcessor:
    """Event processor for handling event streams."""

    def __init__(self, event_store: EventStore):
        self.event_store = event_store
        self.handlers: builtins.list[EventHandler] = []
        self.position = 0
        self.batch_size = 100
        self.processing_delay = 0.1
        self._running = False
        self._processor_task: asyncio.Task | None = None

    def add_handler(self, handler: EventHandler) -> None:
        """Add event handler."""
        self.handlers.append(handler)

    def remove_handler(self, handler: EventHandler) -> None:
        """Remove event handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)

    async def start(self) -> None:
        """Start event processor."""
        self._running = True
        self._processor_task = asyncio.create_task(self._process_events())
        logger.info("Event processor started")

    async def stop(self) -> None:
        """Stop event processor."""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("Event processor stopped")

    async def _process_events(self) -> None:
        """Background event processing."""
        while self._running:
            try:
                # Read events from position
                events = await self.event_store.read_all_events(
                    from_position=self.position,
                    max_count=self.batch_size,
                )

                if not events:
                    await asyncio.sleep(self.processing_delay)
                    continue

                # Process each event
                for record in events:
                    for handler in self.handlers:
                        if handler.can_handle(record.event):
                            try:
                                await handler.handle(record.event)
                            except Exception as e:
                                logger.error(f"Handler error for event {record.event.id}: {e}")

                    self.position = max(self.position, record.position + 1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Event processor error: {e}")
                await asyncio.sleep(1.0)

    async def replay_events(
        self,
        stream_id: str,
        from_position: int = 0,
        handler: EventHandler | None = None,
    ) -> None:
        """Replay events from stream."""
        events = await self.event_store.read_events(stream_id, from_position)

        for record in events:
            if handler:
                if handler.can_handle(record.event):
                    await handler.handle(record.event)
            else:
                for h in self.handlers:
                    if h.can_handle(record.event):
                        await h.handle(record.event)


class Aggregate(ABC, Generic[E]):
    """Base aggregate root for event sourcing."""

    def __init__(self, aggregate_id: str):
        self.aggregate_id = aggregate_id
        self.version = 0
        self.uncommitted_events: builtins.list[E] = []

    def apply_event(self, event: E) -> None:
        """Apply event to aggregate."""
        self._apply(event)
        self.version += 1

    def raise_event(self, event: E) -> None:
        """Raise new event."""
        event.aggregate_id = self.aggregate_id
        self.apply_event(event)
        self.uncommitted_events.append(event)

    def mark_committed(self) -> None:
        """Mark events as committed."""
        self.uncommitted_events.clear()

    def load_from_history(self, events: builtins.list[E]) -> None:
        """Load aggregate from event history."""
        for event in events:
            self.apply_event(event)
        self.uncommitted_events.clear()

    @abstractmethod
    def _apply(self, event: E) -> None:
        """Apply event to aggregate state."""


class Repository(ABC, Generic[T]):
    """Abstract repository interface."""

    @abstractmethod
    async def get(self, aggregate_id: str) -> T | None:
        """Get aggregate by ID."""

    @abstractmethod
    async def save(self, aggregate: T) -> bool:
        """Save aggregate."""


class EventSourcedRepository(Repository[T]):
    """Event-sourced repository implementation."""

    def __init__(
        self,
        event_store: EventStore,
        aggregate_factory: Callable[[str], T],
    ):
        self.event_store = event_store
        self.aggregate_factory = aggregate_factory

    async def get(self, aggregate_id: str) -> T | None:
        """Get aggregate by ID."""
        try:
            # Read events for aggregate
            events = await self.event_store.read_events(f"aggregate-{aggregate_id}")

            if not events:
                return None

            # Create aggregate and load history
            aggregate = self.aggregate_factory(aggregate_id)
            event_objects = [record.event for record in events]
            aggregate.load_from_history(event_objects)  # type: ignore

            return aggregate

        except Exception as e:
            logger.error(f"Failed to get aggregate {aggregate_id}: {e}")
            return None

    async def save(self, aggregate: T) -> bool:
        """Save aggregate."""
        try:
            # Get uncommitted events
            uncommitted = getattr(aggregate, "uncommitted_events", [])

            if not uncommitted:
                return True

            # Save events to store
            stream_id = f"aggregate-{aggregate.aggregate_id}"  # type: ignore
            expected_version = getattr(aggregate, "version", 0) - len(uncommitted)

            success = await self.event_store.append_events(
                stream_id,
                uncommitted,
                expected_version,
            )

            if success:
                aggregate.mark_committed()  # type: ignore

            return success

        except Exception as e:
            logger.error(f"Failed to save aggregate: {e}")
            return False


class EventBus:
    """Event bus for publish/subscribe messaging."""

    def __init__(self):
        self.handlers: builtins.dict[str, builtins.list[EventHandler]] = {}
        self.middleware: builtins.list[Callable[[Event], Event]] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe handler to event type."""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe handler from event type."""
        if event_type in self.handlers:
            if handler in self.handlers[event_type]:
                self.handlers[event_type].remove(handler)

    def add_middleware(self, middleware: Callable[[Event], Event]) -> None:
        """Add middleware for event processing."""
        self.middleware.append(middleware)

    async def publish(self, event: Event) -> None:
        """Publish event to subscribers."""
        try:
            # Apply middleware
            processed_event = event
            for middleware in self.middleware:
                processed_event = middleware(processed_event)

            # Send to handlers
            handlers = self.handlers.get(processed_event.event_type, [])

            for handler in handlers:
                try:
                    await handler.handle(processed_event)
                except Exception as e:
                    logger.error(f"Handler error for event {processed_event.id}: {e}")

        except Exception as e:
            logger.error(f"Failed to publish event {event.id}: {e}")


class StreamProjection(ABC):
    """Abstract stream projection for read models."""

    def __init__(self, name: str):
        self.name = name
        self.position = 0

    @abstractmethod
    async def project(self, event: Event) -> None:
        """Project event to read model."""

    @abstractmethod
    def can_handle(self, event: Event) -> bool:
        """Check if projection handles this event."""

    async def reset(self) -> None:
        """Reset projection to initial state."""
        self.position = 0


class EventStreamManager:
    """High-level event streaming manager."""

    def __init__(self, event_store: EventStore | None = None):
        self.event_store = event_store or InMemoryEventStore()
        self.event_bus = EventBus()
        self.processor = EventProcessor(self.event_store)
        self.projections: builtins.list[StreamProjection] = []

    async def start(self) -> None:
        """Start event streaming."""
        await self.processor.start()
        logger.info("Event streaming started")

    async def stop(self) -> None:
        """Stop event streaming."""
        await self.processor.stop()
        logger.info("Event streaming stopped")

    async def append_events(
        self,
        stream_id: str,
        events: builtins.list[Event],
        expected_version: int | None = None,
    ) -> bool:
        """Append events to stream."""
        success = await self.event_store.append_events(stream_id, events, expected_version)

        # Publish to event bus
        if success:
            for event in events:
                await self.event_bus.publish(event)

        return success

    def add_projection(self, projection: StreamProjection) -> None:
        """Add stream projection."""
        self.projections.append(projection)

        # Create handler for projection
        class ProjectionHandler(EventHandler):
            def __init__(self, proj: StreamProjection):
                self.projection = proj

            async def handle(self, event: Event) -> bool:
                await self.projection.project(event)
                return True

            def can_handle(self, event: Event) -> bool:
                return self.projection.can_handle(event)

        handler = ProjectionHandler(projection)
        self.processor.add_handler(handler)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to events."""
        self.event_bus.subscribe(event_type, handler)

    async def replay_stream(
        self,
        stream_id: str,
        from_position: int = 0,
        projection: StreamProjection | None = None,
    ) -> None:
        """Replay events for projection rebuilding."""
        events = await self.event_store.read_events(stream_id, from_position)

        if projection:
            await projection.reset()
            for record in events:
                if projection.can_handle(record.event):
                    await projection.project(record.event)
        else:
            # Replay through all projections
            for proj in self.projections:
                await proj.reset()
                for record in events:
                    if proj.can_handle(record.event):
                        await proj.project(record.event)


# Global event stream manager
_event_manager: EventStreamManager | None = None


def get_event_manager() -> EventStreamManager | None:
    """Get event manager (not supported - use DI container instead)."""
    raise NotImplementedError(
        "get_event_manager is not supported. Use the DI container to access EventStreamManagerService instead."
    )


def create_event_manager(
    event_store: EventStore | None = None,
) -> EventStreamManager:
    """Create and set event manager (not supported - use DI container instead)."""
    raise NotImplementedError(
        "create_event_manager is not supported. Use the DI container to register EventStreamManagerService instead."
    )


@asynccontextmanager
async def event_streaming_context(event_store: EventStore | None = None):
    """Context manager for event streaming lifecycle."""
    manager = create_event_manager(event_store)
    await manager.start()

    try:
        yield manager
    finally:
        await manager.stop()


# Decorators for event handling
def event_handler(event_types: builtins.list[str]):
    """Decorator for event handlers."""

    def decorator(cls):
        if not issubclass(cls, EventHandler):
            raise TypeError(f"Class {cls.__name__} must inherit from EventHandler")

        cls._event_types = event_types
        return cls

    return decorator


def domain_event(event_type: str):
    """Decorator for domain events."""

    def decorator(cls):
        if not issubclass(cls, Event):
            raise TypeError(f"Class {cls.__name__} must inherit from Event")

        # Set default event type
        original_init = cls.__init__

        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            if not self.event_type:
                self.event_type = event_type

        cls.__init__ = new_init
        return cls

    return decorator
