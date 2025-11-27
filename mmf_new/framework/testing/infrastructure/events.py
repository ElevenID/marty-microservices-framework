import builtins

from mmf_new.framework.events import BaseEvent, EventHandler


class TestEventCollector(EventHandler):
    """Test event handler that collects events for assertion."""

    def __init__(self, event_types: list[str] | None = None):
        self.events: list[BaseEvent] = []
        self._event_types = event_types or []

    async def handle(self, event: BaseEvent) -> None:
        """Collect events."""
        self.events.append(event)

    async def can_handle(self, event: BaseEvent) -> bool:
        """Check if this handler can handle the event."""
        return not self._event_types or event.event_type in self._event_types

    @property
    def event_types(self) -> list[str]:
        """Return event types this handler processes."""
        return self._event_types

    def get_events_of_type(self, event_type: str) -> list[BaseEvent]:
        """Get events of specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def assert_event_published(self, event_type: str, count: int = 1) -> None:
        """Assert that an event was published."""
        events = self.get_events_of_type(event_type)
        assert len(events) == count, f"Expected {count} {event_type} events, got {len(events)}"

    def clear(self) -> None:
        """Clear collected events."""
        self.events.clear()
