"""
CQRS (Command Query Responsibility Segregation) Implementation for Marty Microservices Framework

This module implements CQRS patterns including commands, queries, read models,
handlers, and projection management.
"""

import asyncio
import builtins
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# Temporarily define these here until we resolve imports
class DomainEvent:
    """Placeholder for DomainEvent from event_sourcing module."""

    pass


class EventStore:
    """Placeholder for EventStore from event_sourcing module."""

    pass


@dataclass
class Command:
    """Command for CQRS."""

    command_id: str
    command_type: str
    aggregate_id: str
    data: builtins.dict[str, Any]
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Query:
    """Query for CQRS."""

    query_id: str
    query_type: str
    parameters: builtins.dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ReadModel:
    """Read model for CQRS projections."""

    model_id: str
    model_type: str
    data: builtins.dict[str, Any]
    version: int = 1
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CommandHandler(ABC):
    """Abstract command handler."""

    @abstractmethod
    async def handle(self, command: Command) -> bool:
        """Handle command."""


class QueryHandler(ABC):
    """Abstract query handler."""

    @abstractmethod
    async def handle(self, query: Query) -> Any:
        """Handle query."""


class EventHandler(ABC):
    """Abstract event handler."""

    @abstractmethod
    async def handle(self, event: DomainEvent) -> bool:
        """Handle event."""


class ProjectionManager:
    """Manages read model projections."""

    def __init__(self, event_store: EventStore):
        """Initialize projection manager."""
        self.event_store = event_store
        self.projections: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.projection_handlers: builtins.dict[str, builtins.list[Callable]] = defaultdict(list)
        self.projection_checkpoints: builtins.dict[str, datetime] = {}

        # Projection tasks
        self.projection_tasks: builtins.dict[str, asyncio.Task] = {}

    def register_projection_handler(
        self,
        event_type: str,
        projection_name: str,
        handler: Callable[[DomainEvent], builtins.dict[str, Any]],
    ):
        """Register projection handler for event type."""
        handler_info = {"projection_name": projection_name, "handler": handler}
        self.projection_handlers[event_type].append(handler_info)

    async def start_projection(self, projection_name: str):
        """Start projection processing."""
        if projection_name in self.projection_tasks:
            return  # Already running

        task = asyncio.create_task(self._projection_loop(projection_name))
        self.projection_tasks[projection_name] = task

        logging.info(f"Started projection: {projection_name}")

    async def stop_projection(self, projection_name: str):
        """Stop projection processing."""
        if projection_name in self.projection_tasks:
            task = self.projection_tasks[projection_name]
            task.cancel()
            del self.projection_tasks[projection_name]

            logging.info(f"Stopped projection: {projection_name}")

    async def _projection_loop(self, projection_name: str):
        """Projection processing loop."""
        while True:
            try:
                await self._process_projection(projection_name)
                await asyncio.sleep(5)  # Process every 5 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception(f"Projection error for {projection_name}: {e}")
                await asyncio.sleep(10)

    async def _process_projection(self, projection_name: str):
        """Process projection for new events."""
        checkpoint = self.projection_checkpoints.get(projection_name)

        # Get all event types this projection handles
        relevant_event_types = [
            event_type
            for event_type, handlers in self.projection_handlers.items()
            if any(h["projection_name"] == projection_name for h in handlers)
        ]

        for event_type in relevant_event_types:
            events = await self.event_store.get_events_by_type(event_type, checkpoint)

            for event in events:
                await self._apply_event_to_projection(projection_name, event)

                # Update checkpoint
                self.projection_checkpoints[projection_name] = event.timestamp

    async def _apply_event_to_projection(self, projection_name: str, event: DomainEvent):
        """Apply event to specific projection."""
        handlers = self.projection_handlers.get(event.event_type, [])

        for handler_info in handlers:
            if handler_info["projection_name"] == projection_name:
                try:
                    projection_data = handler_info["handler"](event)

                    # Update projection
                    if projection_name not in self.projections:
                        self.projections[projection_name] = {}

                    self.projections[projection_name].update(projection_data)

                except Exception as e:
                    logging.exception(f"Projection handler error: {e}")

    def get_projection(self, projection_name: str) -> builtins.dict[str, Any]:
        """Get projection data."""
        return self.projections.get(projection_name, {})

    def get_all_projections(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get all projection data."""
        return self.projections.copy()

    async def rebuild_projection(self, projection_name: str):
        """Rebuild projection from all events."""
        # Clear existing projection
        if projection_name in self.projections:
            del self.projections[projection_name]

        # Clear checkpoint
        if projection_name in self.projection_checkpoints:
            del self.projection_checkpoints[projection_name]

        # Process all events
        await self._process_projection(projection_name)

        logging.info(f"Rebuilt projection: {projection_name}")


class CQRSBus:
    """CQRS command and query bus."""

    def __init__(self):
        """Initialize CQRS bus."""
        self.command_handlers: builtins.dict[str, CommandHandler] = {}
        self.query_handlers: builtins.dict[str, QueryHandler] = {}
        self.event_handlers: builtins.dict[str, builtins.list[EventHandler]] = defaultdict(list)

    def register_command_handler(self, command_type: str, handler: CommandHandler):
        """Register command handler."""
        self.command_handlers[command_type] = handler

    def register_query_handler(self, query_type: str, handler: QueryHandler):
        """Register query handler."""
        self.query_handlers[query_type] = handler

    def register_event_handler(self, event_type: str, handler: EventHandler):
        """Register event handler."""
        self.event_handlers[event_type].append(handler)

    async def send_command(self, command: Command) -> bool:
        """Send command for processing."""
        handler = self.command_handlers.get(command.command_type)
        if not handler:
            raise ValueError(f"No handler registered for command type: {command.command_type}")

        return await handler.handle(command)

    async def send_query(self, query: Query) -> Any:
        """Send query for processing."""
        handler = self.query_handlers.get(query.query_type)
        if not handler:
            raise ValueError(f"No handler registered for query type: {query.query_type}")

        return await handler.handle(query)

    async def publish_event(self, event: DomainEvent) -> builtins.list[bool]:
        """Publish event to all registered handlers."""
        handlers = self.event_handlers.get(event.event_type, [])
        results = []

        for handler in handlers:
            try:
                result = await handler.handle(event)
                results.append(result)
            except Exception as e:
                logging.exception(f"Event handler error: {e}")
                results.append(False)

        return results


class ReadModelStore:
    """Store for read models."""

    def __init__(self):
        """Initialize read model store."""
        self.models: builtins.dict[str, ReadModel] = {}

    async def save_read_model(self, model: ReadModel):
        """Save read model."""
        self.models[model.model_id] = model

    async def get_read_model(self, model_id: str) -> ReadModel | None:
        """Get read model by ID."""
        return self.models.get(model_id)

    async def get_read_models_by_type(self, model_type: str) -> builtins.list[ReadModel]:
        """Get read models by type."""
        return [model for model in self.models.values() if model.model_type == model_type]

    async def delete_read_model(self, model_id: str) -> bool:
        """Delete read model."""
        if model_id in self.models:
            del self.models[model_id]
            return True
        return False

    async def query_read_models(
        self, model_type: str | None = None, filters: builtins.dict[str, Any] | None = None
    ) -> builtins.list[ReadModel]:
        """Query read models with filters."""
        models = self.models.values()

        if model_type:
            models = [model for model in models if model.model_type == model_type]

        if filters:
            filtered_models = []
            for model in models:
                match = True
                for key, value in filters.items():
                    if key not in model.data or model.data[key] != value:
                        match = False
                        break
                if match:
                    filtered_models.append(model)
            models = filtered_models

        return list(models)
