"""
Event Sourcing Module

Event sourcing implementation including event store, aggregate root base class,
and event stream management for the data management framework.
"""

import builtins
import threading
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any

from marty_msf.framework.data.data_models import DomainEvent, EventStream, Snapshot


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
        self.event_streams: builtins.dict[str, EventStream] = {}
        self.snapshots: builtins.dict[str, Snapshot] = {}
        self.event_index: builtins.dict[str, builtins.list[DomainEvent]] = defaultdict(list)
        self._lock = threading.RLock()

    async def append_events(
        self,
        aggregate_id: str,
        events: builtins.list[DomainEvent],
        expected_version: int,
    ) -> bool:
        """Append events to aggregate stream."""
        with self._lock:
            if aggregate_id not in self.event_streams:
                self.event_streams[aggregate_id] = EventStream(
                    aggregate_id=aggregate_id,
                    aggregate_type=events[0].aggregate_type if events else "unknown",
                )

            stream = self.event_streams[aggregate_id]

            # Check expected version
            if stream.version != expected_version:
                return False

            # Append events
            for event in events:
                event.version = stream.version + 1
                stream.events.append(event)
                stream.version += 1

                # Update event index
                self.event_index[event.event_type].append(event)

            return True

    async def get_events(
        self, aggregate_id: str, from_version: int = 0
    ) -> builtins.list[DomainEvent]:
        """Get events for aggregate."""
        with self._lock:
            if aggregate_id not in self.event_streams:
                return []

            stream = self.event_streams[aggregate_id]
            return [event for event in stream.events if event.version > from_version]

    async def get_events_by_type(
        self, event_type: str, from_timestamp: datetime | None = None
    ) -> builtins.list[DomainEvent]:
        """Get events by type."""
        with self._lock:
            events = self.event_index.get(event_type, [])

            if from_timestamp:
                events = [event for event in events if event.timestamp >= from_timestamp]

            return events

    async def save_snapshot(self, snapshot: Snapshot) -> bool:
        """Save aggregate snapshot."""
        with self._lock:
            self.snapshots[snapshot.aggregate_id] = snapshot
            return True

    async def get_snapshot(self, aggregate_id: str) -> Snapshot | None:
        """Get latest snapshot for aggregate."""
        with self._lock:
            return self.snapshots.get(aggregate_id)


class AggregateRoot(ABC):
    """Base class for aggregate roots."""

    def __init__(self, aggregate_id: str):
        """Initialize aggregate root."""
        self.aggregate_id = aggregate_id
        self.version = 0
        self.uncommitted_events: builtins.list[DomainEvent] = []

    def apply_event(self, event: DomainEvent):
        """Apply event to aggregate."""
        self._apply_event(event)
        self.version = event.version

    def raise_event(
        self,
        event_type: str,
        data: builtins.dict[str, Any],
        metadata: builtins.dict[str, Any] = None,
    ):
        """Raise new domain event."""
        event = DomainEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            aggregate_id=self.aggregate_id,
            aggregate_type=self.__class__.__name__,
            version=self.version + 1,
            data=data,
            metadata=metadata or {},
        )

        self.uncommitted_events.append(event)
        self.apply_event(event)

    def get_uncommitted_events(self) -> builtins.list[DomainEvent]:
        """Get uncommitted events."""
        return self.uncommitted_events.copy()

    def mark_events_as_committed(self):
        """Mark events as committed."""
        self.uncommitted_events.clear()

    @abstractmethod
    def _apply_event(self, event: DomainEvent):
        """Apply specific event to aggregate state."""

    @abstractmethod
    def create_snapshot(self) -> builtins.dict[str, Any]:
        """Create snapshot of aggregate state."""

    @abstractmethod
    def restore_from_snapshot(self, snapshot_data: builtins.dict[str, Any]):
        """Restore aggregate from snapshot."""
