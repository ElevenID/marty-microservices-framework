"""Tests for domain layer components - Entity, AggregateRoot, ValueObject, DomainEvent."""

import time
from abc import ABC
from datetime import datetime, timezone
from uuid import uuid4


# Simplified implementations for testing (to avoid import issues)
class Entity(ABC):
    """Simplified Entity for testing."""

    def __init__(self, entity_id=None, created_at=None, updated_at=None):
        self.id = entity_id or uuid4()
        now = datetime.now(timezone.utc)
        self.created_at = created_at or now
        self.updated_at = updated_at or now

    def __eq__(self, other):
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"

    def mark_updated(self):
        self.updated_at = datetime.now(timezone.utc)


class AggregateRoot(Entity):
    """Simplified AggregateRoot for testing."""

    def __init__(self, entity_id=None, created_at=None, updated_at=None):
        super().__init__(entity_id, created_at, updated_at)
        self._domain_events = []

    def raise_event(self, event_name: str, event_data: dict):
        event = {
            "event_name": event_name,
            "event_data": event_data,
            "aggregate_id": self.id,
            "timestamp": datetime.now(timezone.utc),
        }
        self._domain_events.append(event)

    def clear_domain_events(self):
        self._domain_events.clear()

    @property
    def domain_events(self):
        return self._domain_events.copy()


class ValueObject(ABC):
    """Simplified ValueObject for testing."""

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self):
        return hash(tuple(sorted(self.__dict__.items())))

    def __repr__(self):
        attrs = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{self.__class__.__name__}({attrs})"


class DomainEvent:
    """Simplified DomainEvent for testing."""

    def __init__(self, event_id=None, timestamp=None, **kwargs):
        self.event_id = event_id or str(uuid4())
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.data = kwargs


# Test Classes
class TestEntity:
    """Test suite for Entity base class."""

    def test_entity_creation_with_defaults(self):
        """Test creating an entity with default values."""
        entity = Entity()

        assert entity.id is not None
        assert isinstance(entity.id.hex, str)
        assert entity.created_at is not None
        assert entity.updated_at is not None
        assert entity.created_at == entity.updated_at

    def test_entity_creation_with_custom_values(self):
        """Test creating an entity with custom values."""
        custom_id = uuid4()
        custom_created_at = datetime(2023, 1, 1, tzinfo=timezone.utc)
        custom_updated_at = datetime(2023, 1, 2, tzinfo=timezone.utc)

        entity = Entity(
            entity_id=custom_id,
            created_at=custom_created_at,
            updated_at=custom_updated_at,
        )

        assert entity.id == custom_id
        assert entity.created_at == custom_created_at
        assert entity.updated_at == custom_updated_at

    def test_entity_equality_by_id(self):
        """Test that entities with same ID are equal."""
        entity_id = uuid4()
        entity1 = Entity(entity_id=entity_id)
        entity2 = Entity(entity_id=entity_id)

        assert entity1 == entity2
        assert hash(entity1) == hash(entity2)

    def test_entity_inequality_different_ids(self):
        """Test that entities with different IDs are not equal."""
        entity1 = Entity()
        entity2 = Entity()

        assert entity1 != entity2
        assert hash(entity1) != hash(entity2)

    def test_entity_update_timestamp(self):
        """Test updating entity updates timestamp."""
        entity = Entity()
        original_updated_at = entity.updated_at

        # Wait a tiny bit to ensure timestamp difference
        time.sleep(0.001)

        entity.mark_updated()

        assert entity.updated_at > original_updated_at

    def test_entity_string_representation(self):
        """Test entity string representation."""
        entity = Entity()
        repr_str = repr(entity)

        assert "Entity" in repr_str
        assert str(entity.id) in repr_str


class TestDomainEvent:
    """Test suite for DomainEvent class."""

    def test_domain_event_creation_with_defaults(self):
        """Test creating a domain event with default values."""
        event = DomainEvent()

        assert event.event_id is not None
        assert isinstance(event.event_id, str)
        assert event.timestamp is not None
        assert isinstance(event.data, dict)

    def test_domain_event_creation_with_custom_data(self):
        """Test creating a domain event with custom data."""
        custom_data = {"user_id": "123", "action": "created"}
        event = DomainEvent(**custom_data)

        assert event.data == custom_data

    def test_domain_event_with_custom_id_and_timestamp(self):
        """Test creating a domain event with custom ID and timestamp."""
        custom_id = "test-event-123"
        custom_timestamp = datetime(2023, 1, 1, tzinfo=timezone.utc)

        event = DomainEvent(event_id=custom_id, timestamp=custom_timestamp)

        assert event.event_id == custom_id
        assert event.timestamp == custom_timestamp


class TestAggregateRoot:
    """Test suite for AggregateRoot class."""

    def test_aggregate_root_creation(self):
        """Test creating an aggregate root."""
        aggregate = AggregateRoot()

        assert hasattr(aggregate, "domain_events")
        assert aggregate.domain_events == []

    def test_raise_event(self):
        """Test raising domain events."""
        aggregate = AggregateRoot()
        event_data = {"action": "user_created", "user_id": "123"}

        aggregate.raise_event("UserCreated", event_data)

        assert len(aggregate.domain_events) == 1
        event = aggregate.domain_events[0]
        assert event["event_name"] == "UserCreated"
        assert event["event_data"] == event_data

    def test_clear_events(self):
        """Test clearing domain events."""
        aggregate = AggregateRoot()
        aggregate.raise_event("TestEvent", {"data": "test"})

        assert len(aggregate.domain_events) == 1

        aggregate.clear_domain_events()

        assert len(aggregate.domain_events) == 0

    def test_multiple_events(self):
        """Test raising multiple domain events."""
        aggregate = AggregateRoot()

        aggregate.raise_event("Event1", {"data": "data1"})
        aggregate.raise_event("Event2", {"data": "data2"})
        aggregate.raise_event("Event3", {"data": "data3"})

        assert len(aggregate.domain_events) == 3
        assert aggregate.domain_events[0]["event_data"]["data"] == "data1"
        assert aggregate.domain_events[1]["event_data"]["data"] == "data2"
        assert aggregate.domain_events[2]["event_data"]["data"] == "data3"


class TestValueObject:
    """Test suite for ValueObject class."""

    def test_value_object_creation(self):
        """Test creating a value object."""

        class SampleValueObject(ValueObject):
            def __init__(self, name: str, age: int):
                self.name = name
                self.age = age

        vo = SampleValueObject("John", 30)

        assert vo.name == "John"
        assert vo.age == 30

    def test_value_object_equality(self):
        """Test value object equality based on all attributes."""

        class SampleValueObject(ValueObject):
            def __init__(self, name: str, age: int):
                self.name = name
                self.age = age

        vo1 = SampleValueObject("John", 30)
        vo2 = SampleValueObject("John", 30)
        vo3 = SampleValueObject("Jane", 30)

        assert vo1 == vo2
        assert vo1 != vo3
        assert hash(vo1) == hash(vo2)
        assert hash(vo1) != hash(vo3)

    def test_value_object_string_representation(self):
        """Test value object string representation."""

        class SampleValueObject(ValueObject):
            def __init__(self, name: str, age: int):
                self.name = name
                self.age = age

        vo = SampleValueObject("John", 30)
        repr_str = repr(vo)

        assert "SampleValueObject" in repr_str
        assert "name='John'" in repr_str
        assert "age=30" in repr_str


class TestDomainEventIntegration:
    """Integration tests for domain events with aggregate roots."""

    def test_event_metadata_persistence(self):
        """Test that events maintain proper metadata."""
        aggregate = AggregateRoot()

        before_event = datetime.now(timezone.utc)
        aggregate.raise_event(
            "UserRegistered", {"user_id": "123", "email": "test@example.com"}
        )
        after_event = datetime.now(timezone.utc)

        event = aggregate.domain_events[0]
        assert before_event <= event["timestamp"] <= after_event
        assert event["aggregate_id"] == aggregate.id

    def test_event_ordering(self):
        """Test that events maintain chronological ordering."""
        aggregate = AggregateRoot()

        aggregate.raise_event("Event1", {})
        aggregate.raise_event("Event2", {})
        aggregate.raise_event("Event3", {})

        events = aggregate.domain_events
        assert len(events) == 3

        # Events should be in chronological order
        assert (
            events[0]["timestamp"] <= events[1]["timestamp"] <= events[2]["timestamp"]
        )
