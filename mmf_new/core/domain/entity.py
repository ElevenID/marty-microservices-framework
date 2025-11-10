"""Base entity class for domain entities."""

from abc import ABC
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


class DomainEvent:
    """Base class for domain events."""

    def __init__(
        self, event_id: str | None = None, timestamp: datetime | None = None, **kwargs
    ):
        self.event_id = event_id or str(uuid4())
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.data = kwargs


class Entity(ABC):
    """Base class for all domain entities.

    Provides basic entity functionality including:
    - Unique identifier generation
    - Equality comparison based on ID
    - Timestamp tracking
    """

    def __init__(
        self,
        entity_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        """Initialize entity with ID and timestamps.

        Args:
            entity_id: Unique identifier. If None, a new UUID will be generated.
            created_at: Creation timestamp. If None, current UTC time will be used.
            updated_at: Last update timestamp. If None, current UTC time will be used.
        """
        self.id = entity_id or uuid4()
        now = datetime.now(timezone.utc)
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def __eq__(self, other: Any) -> bool:
        """Check equality based on entity ID."""
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on entity ID."""
        return hash(self.id)

    def __repr__(self) -> str:
        """String representation of the entity."""
        return f"<{self.__class__.__name__}(id={self.id})>"

    def mark_updated(self) -> None:
        """Mark the entity as updated with current timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary representation."""
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AggregateRoot(Entity):
    """Base class for aggregate root entities.

    Aggregate roots are the only entities that can be referenced from outside
    the aggregate boundary. They are responsible for maintaining consistency
    within their aggregate.
    """

    def __init__(
        self,
        entity_id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        """Initialize aggregate root."""
        super().__init__(entity_id, created_at, updated_at)
        self._domain_events: list = []

    def add_domain_event(self, event: Any) -> None:
        """Add a domain event to be published."""
        self._domain_events.append(event)

    def raise_event(self, event_name: str, event_data: dict[str, Any]) -> None:
        """Raise a domain event.

        Args:
            event_name: The name of the event
            event_data: The event data
        """
        event = {
            "event_name": event_name,
            "event_data": event_data,
            "aggregate_id": self.id,
            "timestamp": datetime.now(timezone.utc),
        }
        self._domain_events.append(event)

    def clear_domain_events(self) -> None:
        """Clear all domain events."""
        self._domain_events.clear()

    @property
    def domain_events(self) -> list:
        """Get all domain events."""
        return self._domain_events.copy()


class ValueObject(ABC):
    """Base class for value objects.

    Value objects are immutable and are compared by their values
    rather than their identity.
    """

    def __eq__(self, other: Any) -> bool:
        """Check equality based on all attributes."""
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        """Hash based on all attributes."""
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self) -> str:
        """String representation of the value object."""
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{self.__class__.__name__}({attrs})"
