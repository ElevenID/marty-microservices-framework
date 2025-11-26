"""
Event Sourcing Implementation for Marty Microservices Framework

This module implements event sourcing patterns including domain events,
event stores, aggregate roots, and repositories.
"""

import builtins
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar


class EventType(Enum):
    """Event types for event sourcing."""

    DOMAIN_EVENT = "domain_event"
    INTEGRATION_EVENT = "integration_event"
    SYSTEM_EVENT = "system_event"
    FAILURE_EVENT = "failure_event"
    COMPENSATION_EVENT = "compensation_event"


T = TypeVar("T")


@dataclass
class DomainEvent:
    """Domain event for event sourcing."""

    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    version: int
    data: builtins.dict[str, Any]
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None
    causation_id: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert event to dictionary."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "DomainEvent":
        """Create event from dictionary."""
        data = data.copy()
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class EventStream:
    """Event stream for aggregate."""

    aggregate_id: str
    aggregate_type: str
    events: builtins.list[DomainEvent] = field(default_factory=list)
    version: int = 0


@dataclass
class Snapshot:
    """Aggregate snapshot for performance optimization."""

    snapshot_id: str
    aggregate_id: str
    aggregate_type: str
    version: int
    data: builtins.dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventStore(ABC):
    """Abstract event store interface."""

    @abstractmethod
    async def append_events(
        self,
        aggregate_id: str,
        events: builtins.list[DomainEvent],
        expected_version: int,
    ) -> bool:
        """Append events to aggregate stream."""

    @abstractmethod
    async def get_events(
        self, aggregate_id: str, from_version: int = 0
    ) -> builtins.list[DomainEvent]:
        """Get events for aggregate."""

    @abstractmethod
    async def get_events_by_type(
        self, event_type: str, from_timestamp: datetime | None = None
    ) -> builtins.list[DomainEvent]:
        """Get events by type."""

    @abstractmethod
    async def save_snapshot(self, snapshot: Snapshot) -> bool:
        """Save aggregate snapshot."""

    @abstractmethod
    async def get_snapshot(self, aggregate_id: str) -> Snapshot | None:
        """Get latest snapshot for aggregate."""


class InMemoryEventStore(EventStore):
    """In-memory event store implementation."""

    def __init__(self):
        """Initialize in-memory event store."""
        self.events: builtins.dict[str, builtins.list[DomainEvent]] = {}
        self.snapshots: builtins.dict[str, Snapshot] = {}
        self.version_map: builtins.dict[str, int] = {}

    async def append_events(
        self,
        aggregate_id: str,
        events: builtins.list[DomainEvent],
        expected_version: int,
    ) -> bool:
        """Append events to aggregate stream."""
        current_version = self.version_map.get(aggregate_id, 0)

        # Check for concurrency conflicts
        if current_version != expected_version:
            return False

        if aggregate_id not in self.events:
            self.events[aggregate_id] = []

        # Assign version numbers to events
        for i, event in enumerate(events):
            event.version = current_version + i + 1

        self.events[aggregate_id].extend(events)
        self.version_map[aggregate_id] = current_version + len(events)

        return True

    async def get_events(
        self, aggregate_id: str, from_version: int = 0
    ) -> builtins.list[DomainEvent]:
        """Get events for aggregate."""
        if aggregate_id not in self.events:
            return []

        all_events = self.events[aggregate_id]
        return [event for event in all_events if event.version > from_version]

    async def get_events_by_type(
        self, event_type: str, from_timestamp: datetime | None = None
    ) -> builtins.list[DomainEvent]:
        """Get events by type."""
        result = []

        for events in self.events.values():
            for event in events:
                if event.event_type == event_type:
                    if from_timestamp is None or event.timestamp >= from_timestamp:
                        result.append(event)

        # Sort by timestamp
        result.sort(key=lambda e: e.timestamp)
        return result

    async def save_snapshot(self, snapshot: Snapshot) -> bool:
        """Save aggregate snapshot."""
        self.snapshots[snapshot.aggregate_id] = snapshot
        return True

    async def get_snapshot(self, aggregate_id: str) -> Snapshot | None:
        """Get latest snapshot for aggregate."""
        return self.snapshots.get(aggregate_id)


class AggregateRoot(ABC):
    """Base class for aggregate roots in event sourcing."""

    def __init__(self, aggregate_id: str):
        """Initialize aggregate root."""
        self.aggregate_id = aggregate_id
        self.version = 0
        self._uncommitted_events: builtins.list[DomainEvent] = []

    @abstractmethod
    def create_snapshot(self) -> builtins.dict[str, Any]:
        """Create snapshot data for the aggregate."""

    @abstractmethod
    def restore_from_snapshot(self, snapshot_data: builtins.dict[str, Any]):
        """Restore aggregate state from snapshot."""

    def apply_event(self, event: DomainEvent):
        """Apply event to aggregate state."""
        self.version = event.version
        self._handle_event(event)

    @abstractmethod
    def _handle_event(self, event: DomainEvent):
        """Handle specific event type (to be implemented by subclasses)."""

    def raise_event(
        self,
        event_type: str,
        data: builtins.dict[str, Any],
        metadata: builtins.dict[str, Any] = None,
    ):
        """Raise a new domain event."""
        event = DomainEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_id=self.aggregate_id,
            aggregate_type=self.__class__.__name__,
            version=self.version + 1,
            data=data,
            metadata=metadata or {},
        )

        # Apply event to current state
        self.apply_event(event)

        # Add to uncommitted events
        self._uncommitted_events.append(event)

    def get_uncommitted_events(self) -> builtins.list[DomainEvent]:
        """Get uncommitted events."""
        return self._uncommitted_events.copy()

    def mark_events_as_committed(self):
        """Mark events as committed."""
        self._uncommitted_events.clear()


class Repository(ABC, Generic[T]):
    """Abstract repository interface."""

    @abstractmethod
    async def get_by_id(self, aggregate_id: str) -> T | None:
        """Get aggregate by ID."""

    @abstractmethod
    async def save(self, aggregate: T) -> bool:
        """Save aggregate."""

    @abstractmethod
    async def delete(self, aggregate_id: str) -> bool:
        """Delete aggregate."""


class EventSourcingRepository(Repository[T]):
    """Event sourcing repository implementation."""

    def __init__(
        self,
        event_store: EventStore,
        aggregate_factory: callable,
        snapshot_frequency: int = 10,
    ):
        """Initialize event sourcing repository."""
        self.event_store = event_store
        self.aggregate_factory = aggregate_factory
        self.snapshot_frequency = snapshot_frequency

    async def get_by_id(self, aggregate_id: str) -> T | None:
        """Get aggregate by ID."""
        # Try to get latest snapshot
        snapshot = await self.event_store.get_snapshot(aggregate_id)

        if snapshot:
            # Create aggregate from snapshot
            aggregate = self.aggregate_factory(aggregate_id)
            aggregate.restore_from_snapshot(snapshot.data)
            aggregate.version = snapshot.version

            # Get events after snapshot
            events = await self.event_store.get_events(aggregate_id, snapshot.version)
        else:
            # Create new aggregate
            aggregate = self.aggregate_factory(aggregate_id)

            # Get all events
            events = await self.event_store.get_events(aggregate_id)

        # Apply events to rebuild state
        for event in events:
            aggregate.apply_event(event)

        return aggregate if events or snapshot else None

    async def save(self, aggregate: T) -> bool:
        """Save aggregate."""
        uncommitted_events = aggregate.get_uncommitted_events()

        if not uncommitted_events:
            return True  # Nothing to save

        # Save events
        success = await self.event_store.append_events(
            aggregate.aggregate_id,
            uncommitted_events,
            aggregate.version - len(uncommitted_events),
        )

        if success:
            aggregate.mark_events_as_committed()

            # Create snapshot if needed
            if aggregate.version % self.snapshot_frequency == 0:
                snapshot = Snapshot(
                    snapshot_id=str(uuid.uuid4()),
                    aggregate_id=aggregate.aggregate_id,
                    aggregate_type=aggregate.__class__.__name__,
                    version=aggregate.version,
                    data=aggregate.create_snapshot(),
                )
                await self.event_store.save_snapshot(snapshot)

        return success

    async def delete(self, aggregate_id: str) -> bool:
        """Delete aggregate (not supported in event sourcing)."""
        # In event sourcing, we don't delete but mark as deleted
        # This would be implemented by raising a "deleted" event
        raise NotImplementedError("Direct deletion not supported in event sourcing")
