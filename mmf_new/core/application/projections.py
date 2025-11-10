"""Projection system for CQRS read models."""

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime

from ..domain.entity import DomainEvent
from ..infrastructure.persistence import ReadModelStore


class Projection(ABC):
    """Abstract projection for read models."""

    def __init__(self, projection_name: str):
        self.projection_name = projection_name
        self._version = 0
        self._last_processed_event = None
        self._last_updated = datetime.now()

    @property
    def version(self) -> int:
        """Get projection version."""
        return self._version

    @property
    def last_processed_event(self) -> str | None:
        """Get last processed event ID."""
        return self._last_processed_event

    @property
    def last_updated(self) -> datetime:
        """Get last update timestamp."""
        return self._last_updated

    @abstractmethod
    async def handle_event(self, event: DomainEvent) -> None:
        """Handle event and update projection."""
        raise NotImplementedError

    @abstractmethod
    async def reset(self) -> None:
        """Reset projection to initial state."""
        raise NotImplementedError

    def _update_metadata(self, event: DomainEvent) -> None:
        """Update projection metadata."""
        self._version += 1
        self._last_processed_event = getattr(event, "event_id", None)
        self._last_updated = datetime.now()


class ProjectionManager:
    """Manages projections and their event handling."""

    def __init__(self, read_model_store: ReadModelStore):
        self.read_model_store = read_model_store
        self._projections: dict[str, Projection] = {}
        self._event_handlers: dict[str, list[Projection]] = defaultdict(list)

    def register_projection(self, projection: Projection) -> None:
        """Register projection."""
        self._projections[projection.projection_name] = projection

    def subscribe_to_event(self, event_type: str, projection: Projection) -> None:
        """Subscribe projection to event type."""
        if projection.projection_name not in self._projections:
            self.register_projection(projection)

        self._event_handlers[event_type].append(projection)

    async def handle_event(self, event: DomainEvent) -> None:
        """Handle event across all subscribed projections."""
        event_type = type(event).__name__
        projections = self._event_handlers.get(event_type, [])

        tasks = []
        for projection in projections:
            tasks.append(asyncio.create_task(projection.handle_event(event)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def rebuild_projection(
        self, projection_name: str, events: list[DomainEvent]
    ) -> None:
        """Rebuild projection from events."""
        projection = self._projections.get(projection_name)
        if not projection:
            raise ValueError(f"Projection {projection_name} not found")

        # Reset projection
        await projection.reset()

        # Replay events
        for event in events:
            await projection.handle_event(event)
