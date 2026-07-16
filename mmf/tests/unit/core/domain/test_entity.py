from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from mmf.core.domain.entity import AggregateRoot, DomainEvent, Entity, ValueObject


class ConcreteEntity(Entity):
    pass


class ConcreteAggregateRoot(AggregateRoot):
    pass


class PlainValueObject(ValueObject):
    def __init__(self, value: str, count: int):
        self.value = value
        self.count = count


class TestDomainEvent:
    def test_init_defaults(self):
        event = DomainEvent(data="test")
        assert event.event_id is not None
        assert isinstance(event.timestamp, datetime)
        assert event.data == {"data": "test"}

    def test_init_custom(self):
        event_id = "custom-id"
        timestamp = datetime.now(timezone.utc)
        event = DomainEvent(event_id=event_id, timestamp=timestamp, key="value")

        assert event.event_id == event_id
        assert event.timestamp == timestamp
        assert event.data == {"key": "value"}


class TestEntity:
    def test_init_defaults(self):
        entity = ConcreteEntity()
        assert isinstance(entity.id, UUID)
        assert isinstance(entity.created_at, datetime)
        assert isinstance(entity.updated_at, datetime)
        assert entity.created_at == entity.updated_at

    def test_init_custom(self):
        uid = uuid4()
        now = datetime.now(timezone.utc)
        entity = ConcreteEntity(entity_id=uid, created_at=now, updated_at=now)

        assert entity.id == uid
        assert entity.created_at == now
        assert entity.updated_at == now

    def test_equality(self):
        uid = uuid4()
        entity1 = ConcreteEntity(entity_id=uid)
        entity2 = ConcreteEntity(entity_id=uid)
        entity3 = ConcreteEntity(entity_id=uuid4())

        assert entity1 == entity2
        assert entity1 != entity3
        assert entity1 != "not-an-entity"

    def test_hash(self):
        uid = uuid4()
        entity1 = ConcreteEntity(entity_id=uid)
        entity2 = ConcreteEntity(entity_id=uid)

        assert hash(entity1) == hash(entity2)
        assert hash(entity1) == hash(uid)

    def test_repr(self):
        uid = uuid4()
        entity = ConcreteEntity(entity_id=uid)
        assert repr(entity) == f"<ConcreteEntity(id={uid})>"

    def test_mark_updated(self):
        entity = ConcreteEntity()
        original_updated_at = entity.updated_at

        # Ensure time passes
        import time

        time.sleep(0.001)

        entity.mark_updated()
        assert entity.updated_at > original_updated_at

    def test_to_dict(self):
        uid = uuid4()
        now = datetime.now(timezone.utc)
        entity = ConcreteEntity(entity_id=uid, created_at=now, updated_at=now)

        data = entity.to_dict()
        assert data["id"] == str(uid)
        assert data["created_at"] == now.isoformat()
        assert data["updated_at"] == now.isoformat()


class TestAggregateRoot:
    def test_init(self):
        agg = ConcreteAggregateRoot()
        assert isinstance(agg, Entity)
        assert agg.domain_events == []

    def test_add_domain_event(self):
        agg = ConcreteAggregateRoot()
        event = DomainEvent(name="test")
        agg.add_domain_event(event)

        assert len(agg.domain_events) == 1
        assert agg.domain_events[0] == event

    def test_raise_event(self):
        agg = ConcreteAggregateRoot()
        agg.raise_event("test_event", {"key": "value"})

        assert len(agg.domain_events) == 1
        event = agg.domain_events[0]
        assert event["event_name"] == "test_event"
        assert event["event_data"] == {"key": "value"}
        assert event["aggregate_id"] == agg.id
        assert isinstance(event["timestamp"], datetime)

    def test_clear_domain_events(self):
        agg = ConcreteAggregateRoot()
        agg.add_domain_event("event")
        agg.clear_domain_events()
        assert len(agg.domain_events) == 0

    def test_domain_events_property_is_copy(self):
        agg = ConcreteAggregateRoot()
        agg.add_domain_event("event")

        events = agg.domain_events
        events.append("new_event")

        assert len(agg.domain_events) == 1


class TestValueObject:
    def test_equality(self):
        vo1 = PlainValueObject(value="test", count=1)
        vo2 = PlainValueObject(value="test", count=1)
        vo3 = PlainValueObject(value="other", count=1)

        assert vo1 == vo2
        assert vo1 != vo3
        assert vo1 != "not-a-vo"

    def test_hash(self):
        vo1 = PlainValueObject(value="test", count=1)
        vo2 = PlainValueObject(value="test", count=1)

        assert hash(vo1) == hash(vo2)

    def test_repr(self):
        vo = PlainValueObject(value="test", count=1)
        # The order of items in __dict__ is insertion order in recent Python versions
        # But to be safe, we can check if the string contains the expected parts
        r = repr(vo)
        assert "PlainValueObject" in r
        assert "value='test'" in r
        assert "count=1" in r
