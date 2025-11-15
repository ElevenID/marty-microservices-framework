"""
Event Sourcing Implementation

Provides aggregate root, repository, and snapshot capabilities
for event sourcing pattern implementation.
"""

import asyncio
import builtins
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from .core import DomainEvent, EventMetadata, EventStore

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="AggregateRoot")


@dataclass
class Snapshot:
    """Aggregate snapshot for performance optimization."""

    aggregate_id: str
    aggregate_type: str
    version: int
    timestamp: datetime
    data: builtins.dict[str, Any]

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "Snapshot":
        """Create snapshot from dictionary."""
        return cls(
            aggregate_id=data["aggregate_id"],
            aggregate_type=data["aggregate_type"],
            version=data["version"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data["data"],
        )


class SnapshotStore(ABC):
    """Abstract snapshot store interface."""

    @abstractmethod
    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save aggregate snapshot."""
        raise NotImplementedError

    @abstractmethod
    async def get_snapshot(self, aggregate_id: str) -> Snapshot | None:
        """Get latest snapshot for aggregate."""
        raise NotImplementedError

    @abstractmethod
    async def delete_snapshot(self, aggregate_id: str) -> None:
        """Delete snapshot for aggregate."""
        raise NotImplementedError


class InMemorySnapshotStore(SnapshotStore):
    """In-memory snapshot store implementation."""

    def __init__(self):
        self._snapshots: builtins.dict[str, Snapshot] = {}
        self._lock = asyncio.Lock()

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save snapshot."""
        async with self._lock:
            self._snapshots[snapshot.aggregate_id] = snapshot

    async def get_snapshot(self, aggregate_id: str) -> Snapshot | None:
        """Get snapshot."""
        async with self._lock:
            return self._snapshots.get(aggregate_id)

    async def delete_snapshot(self, aggregate_id: str) -> None:
        """Delete snapshot."""
        async with self._lock:
            if aggregate_id in self._snapshots:
                del self._snapshots[aggregate_id]


class AggregateRoot(ABC):
    """Base aggregate root for event sourcing."""

    def __init__(self, aggregate_id: str = None):
        self._aggregate_id = aggregate_id or str(uuid.uuid4())
        self._version = 0
        self._uncommitted_events: builtins.list[DomainEvent] = []
        self._created_at = datetime.utcnow()
        self._updated_at = datetime.utcnow()

    @property
    def aggregate_id(self) -> str:
        """Get aggregate ID."""
        return self._aggregate_id

    @property
    def version(self) -> int:
        """Get current version."""
        return self._version

    @property
    def uncommitted_events(self) -> builtins.list[DomainEvent]:
        """Get uncommitted events."""
        return self._uncommitted_events.copy()

    @property
    def has_uncommitted_events(self) -> bool:
        """Check if aggregate has uncommitted events."""
        return len(self._uncommitted_events) > 0

    @property
    def created_at(self) -> datetime:
        """Get creation timestamp."""
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        """Get last update timestamp."""
        return self._updated_at

    def mark_events_as_committed(self) -> None:
        """Mark all uncommitted events as committed."""
        self._uncommitted_events.clear()

    def replay_events(self, events: builtins.list[DomainEvent]) -> None:
        """Replay events to rebuild aggregate state."""
        for event in events:
            self._apply_event(event, is_new=False)
            self._version += 1

    def _apply_event(self, event: DomainEvent, is_new: bool = True) -> None:
        """Apply event to aggregate state."""
        # Update timestamps
        if is_new:
            self._updated_at = datetime.utcnow()

        # Apply event to state
        self._when(event)

        # Add to uncommitted events if new
        if is_new:
            self._uncommitted_events.append(event)

    @abstractmethod
    def _when(self, event: DomainEvent) -> None:
        """Apply event to aggregate state (implement in subclasses)."""
        raise NotImplementedError

    def _raise_event(
        self,
        event_type: str,
        event_data: builtins.dict[str, Any],
        metadata: EventMetadata = None,
    ) -> None:
        """Raise a new domain event."""
        if metadata is None:
            metadata = EventMetadata()

        event = DomainEvent(
            aggregate_id=self._aggregate_id,
            event_type=event_type,
            event_data=event_data,
            metadata=metadata,
        )
        event.aggregate_type = self.__class__.__name__

        self._apply_event(event, is_new=True)
        self._version += 1

    @abstractmethod
    def to_snapshot(self) -> builtins.dict[str, Any]:
        """Create snapshot data from current state."""
        raise NotImplementedError

    @abstractmethod
    def from_snapshot(self, snapshot_data: builtins.dict[str, Any]) -> None:
        """Restore state from snapshot data."""
        raise NotImplementedError

    def create_snapshot(self) -> Snapshot:
        """Create snapshot of current state."""
        return Snapshot(
            aggregate_id=self._aggregate_id,
            aggregate_type=self.__class__.__name__,
            version=self._version,
            timestamp=datetime.utcnow(),
            data=self.to_snapshot(),
        )

    def restore_from_snapshot(self, snapshot: Snapshot) -> None:
        """Restore aggregate from snapshot."""
        self._version = snapshot.version
        self._updated_at = snapshot.timestamp
        self.from_snapshot(snapshot.data)


class Aggregate(AggregateRoot):
    """Basic aggregate implementation with common patterns."""

    def __init__(self, aggregate_id: str = None):
        super().__init__(aggregate_id)
        self._state_data: builtins.dict[str, Any] = {}

    def _when(self, event: DomainEvent) -> None:
        """Default event handler - stores event data in state."""
        method_name = f"_apply_{event.event_type.lower().replace('.', '_')}"
        if hasattr(self, method_name):
            getattr(self, method_name)(event)
        else:
            # Default behavior: merge event data into state
            self._state_data.update(event.event_data)

    def to_snapshot(self) -> builtins.dict[str, Any]:
        """Create snapshot from state data."""
        return {
            "state_data": self._state_data,
            "created_at": self._created_at.isoformat(),
            "updated_at": self._updated_at.isoformat(),
        }

    def from_snapshot(self, snapshot_data: builtins.dict[str, Any]) -> None:
        """Restore from snapshot data."""
        self._state_data = snapshot_data.get("state_data", {})
        if "created_at" in snapshot_data:
            self._created_at = datetime.fromisoformat(snapshot_data["created_at"])
        if "updated_at" in snapshot_data:
            self._updated_at = datetime.fromisoformat(snapshot_data["updated_at"])

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state value."""
        return self._state_data.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        """Set state value (for internal use)."""
        self._state_data[key] = value


class EventSourcedRepository(ABC, Generic[T]):
    """Abstract repository for event sourced aggregates."""

    def __init__(
        self,
        event_store: EventStore,
        snapshot_store: SnapshotStore | None = None,
        snapshot_frequency: int = 10,
    ):
        self.event_store = event_store
        self.snapshot_store = snapshot_store
        self.snapshot_frequency = snapshot_frequency

    @abstractmethod
    def _create_aggregate(self) -> T:
        """Create new aggregate instance."""
        raise NotImplementedError

    @abstractmethod
    def _get_aggregate_type(self) -> str:
        """Get aggregate type name."""
        raise NotImplementedError

    async def get_by_id(self, aggregate_id: str) -> T | None:
        """Get aggregate by ID."""
        try:
            aggregate = self._create_aggregate()
            aggregate._aggregate_id = aggregate_id

            # Try to load from snapshot first
            snapshot = None
            from_version = 0

            if self.snapshot_store:
                snapshot = await self.snapshot_store.get_snapshot(aggregate_id)
                if snapshot:
                    aggregate.restore_from_snapshot(snapshot)
                    from_version = snapshot.version + 1

            # Load events after snapshot
            events = await self.event_store.get_events(
                f"{self._get_aggregate_type()}-{aggregate_id}", from_version
            )

            if not events and snapshot is None:
                return None

            # Apply events
            if events:
                domain_events = [e for e in events if isinstance(e, DomainEvent)]
                aggregate.replay_events(domain_events)

            return aggregate

        except Exception as e:
            logger.error(f"Error loading aggregate {aggregate_id}: {e}")
            return None

    async def save(self, aggregate: T) -> None:
        """Save aggregate."""
        if not aggregate.has_uncommitted_events:
            return

        stream_id = f"{self._get_aggregate_type()}-{aggregate.aggregate_id}"
        uncommitted_events = aggregate.uncommitted_events

        # Calculate expected version
        expected_version = aggregate.version - len(uncommitted_events)

        try:
            # Save events
            await self.event_store.append_events(stream_id, uncommitted_events, expected_version)

            # Mark events as committed
            aggregate.mark_events_as_committed()

            # Create snapshot if needed
            if (
                self.snapshot_store
                and self.snapshot_frequency > 0
                and aggregate.version % self.snapshot_frequency == 0
            ):
                snapshot = aggregate.create_snapshot()
                await self.snapshot_store.save_snapshot(snapshot)

        except Exception as e:
            logger.error(f"Error saving aggregate {aggregate.aggregate_id}: {e}")
            raise


class AggregateRepository(EventSourcedRepository[T]):
    """Generic aggregate repository implementation."""

    def __init__(
        self,
        aggregate_class: builtins.type[T],
        event_store: EventStore,
        snapshot_store: SnapshotStore | None = None,
        snapshot_frequency: int = 10,
    ):
        super().__init__(event_store, snapshot_store, snapshot_frequency)
        self.aggregate_class = aggregate_class

    def _create_aggregate(self) -> T:
        """Create new aggregate instance."""
        return self.aggregate_class()

    def _get_aggregate_type(self) -> str:
        """Get aggregate type name."""
        return self.aggregate_class.__name__


class EventSourcingError(Exception):
    """Event sourcing specific error."""


class ConcurrencyError(EventSourcingError):
    """Raised when concurrent modification is detected."""

    def __init__(self, aggregate_id: str, expected_version: int, actual_version: int):
        super().__init__(
            f"Concurrency conflict for aggregate {aggregate_id}. "
            f"Expected version {expected_version}, but actual version is {actual_version}"
        )
        self.aggregate_id = aggregate_id
        self.expected_version = expected_version
        self.actual_version = actual_version


class AggregateNotFoundError(EventSourcingError):
    """Raised when aggregate is not found."""

    def __init__(self, aggregate_id: str):
        super().__init__(f"Aggregate {aggregate_id} not found")
        self.aggregate_id = aggregate_id


# Event sourcing patterns and utilities


class EventSourcedProjection(ABC):
    """Base class for event sourced projections."""

    def __init__(self):
        self._version = 0
        self._last_processed_event = None

    @property
    def version(self) -> int:
        """Get projection version."""
        return self._version

    @abstractmethod
    async def handle_event(self, event: DomainEvent) -> None:
        """Handle domain event."""
        raise NotImplementedError

    def _update_version(self, event: DomainEvent) -> None:
        """Update projection version."""
        self._version += 1
        self._last_processed_event = event.event_id


class AggregateFactory:
    """Factory for creating aggregate instances."""

    def __init__(self):
        self._aggregate_types: builtins.dict[str, builtins.type[AggregateRoot]] = {}

    def register_aggregate(
        self, aggregate_type: str, aggregate_class: builtins.type[AggregateRoot]
    ) -> None:
        """Register aggregate type."""
        self._aggregate_types[aggregate_type] = aggregate_class

    def create_aggregate(self, aggregate_type: str, aggregate_id: str = None) -> AggregateRoot:
        """Create aggregate instance."""
        if aggregate_type not in self._aggregate_types:
            raise ValueError(f"Unknown aggregate type: {aggregate_type}")

        aggregate_class = self._aggregate_types[aggregate_type]
        return aggregate_class(aggregate_id)

    def get_registered_types(self) -> builtins.list[str]:
        """Get list of registered aggregate types."""
        return list(self._aggregate_types.keys())


# Convenience functions


def create_repository(
    aggregate_class: builtins.type[T],
    event_store: EventStore,
    snapshot_store: SnapshotStore | None = None,
    snapshot_frequency: int = 10,
) -> AggregateRepository[T]:
    """Create repository for aggregate class."""
    return AggregateRepository(
        aggregate_class=aggregate_class,
        event_store=event_store,
        snapshot_store=snapshot_store,
        snapshot_frequency=snapshot_frequency,
    )


async def rebuild_aggregate_from_events(
    aggregate: AggregateRoot, event_store: EventStore, aggregate_type: str
) -> AggregateRoot:
    """Rebuild aggregate from all events."""
    stream_id = f"{aggregate_type}-{aggregate.aggregate_id}"
    events = await event_store.get_events(stream_id)

    domain_events = [e for e in events if isinstance(e, DomainEvent)]
    aggregate.replay_events(domain_events)

    return aggregate
