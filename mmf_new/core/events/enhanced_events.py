"""
Enhanced Event Types and Registry

Provides comprehensive event types for the enhanced event bus system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .enhanced_event_bus import BaseEvent, EventMetadata, EventPriority


class EventRegistry:
    """Enhanced registry for event types with plugin support."""

    def __init__(self):
        self._events: dict[str, type[BaseEvent]] = {}
        self._plugin_events: dict[str, dict[str, type[BaseEvent]]] = {}

    def register(self, event_class: type[BaseEvent]) -> None:
        """Register an event class."""
        self._events[event_class.__name__] = event_class

    def register_plugin_event(self, plugin_id: str, event_class: type[BaseEvent]) -> None:
        """Register an event class for a specific plugin."""
        if plugin_id not in self._plugin_events:
            self._plugin_events[plugin_id] = {}
        self._plugin_events[plugin_id][event_class.__name__] = event_class
        # Also register globally
        self.register(event_class)

    def get(self, event_type: str) -> type[BaseEvent] | None:
        """Get event class by type name."""
        return self._events.get(event_type)

    def get_plugin_events(self, plugin_id: str) -> dict[str, type[BaseEvent]]:
        """Get all events registered by a plugin."""
        return self._plugin_events.get(plugin_id, {})

    def list_types(self) -> list[str]:
        """List all registered event types."""
        return list(self._events.keys())

    def unregister_plugin_events(self, plugin_id: str) -> None:
        """Unregister all events for a plugin."""
        if plugin_id in self._plugin_events:
            for event_type in self._plugin_events[plugin_id]:
                if event_type in self._events:
                    del self._events[event_type]
            del self._plugin_events[plugin_id]


# Global event registry
EVENT_REGISTRY = EventRegistry()


def register_event(event_class: type[BaseEvent]) -> type[BaseEvent]:
    """Decorator to register an event class."""
    EVENT_REGISTRY.register(event_class)
    return event_class


def register_plugin_event(plugin_id: str):
    """Decorator to register an event class for a plugin."""

    def decorator(event_class: type[BaseEvent]) -> type[BaseEvent]:
        EVENT_REGISTRY.register_plugin_event(plugin_id, event_class)
        return event_class

    return decorator


# Core event types
@register_event
class GenericEvent(BaseEvent):
    """Generic event for simple use cases."""

    def __init__(self, event_type: str | None = None, data: dict[str, Any] | None = None, **kwargs):
        super().__init__(**kwargs)
        if event_type:
            self.event_type = event_type
        self.data = data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata.__dict__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenericEvent:
        metadata_data = data.get("metadata", {})
        metadata = EventMetadata(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            **metadata_data,
        )

        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=data["event_type"],
            data=data.get("data", {}),
            metadata=metadata,
        )


@register_event
class DomainEvent(BaseEvent):
    """Base class for domain events."""

    def __init__(
        self, aggregate_id: str, aggregate_type: str, aggregate_version: int = 1, **kwargs
    ):
        super().__init__(**kwargs)
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type
        self.aggregate_version = aggregate_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "aggregate_id": self.aggregate_id,
            "aggregate_type": self.aggregate_type,
            "aggregate_version": self.aggregate_version,
            "metadata": self.metadata.__dict__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        metadata_data = data.get("metadata", {})
        metadata = EventMetadata(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            **metadata_data,
        )

        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            aggregate_id=data["aggregate_id"],
            aggregate_type=data["aggregate_type"],
            aggregate_version=data.get("aggregate_version", 1),
            metadata=metadata,
        )


@register_event
class IntegrationEvent(BaseEvent):
    """Base class for integration events between services."""

    def __init__(
        self,
        source_service: str,
        target_service: str | None = None,
        payload: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.source_service = source_service
        self.target_service = target_service
        self.payload = payload or {}

        # Set source service in metadata
        if self.metadata:
            self.metadata.source_service = source_service

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "source_service": self.source_service,
            "target_service": self.target_service,
            "payload": self.payload,
            "metadata": self.metadata.__dict__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntegrationEvent:
        metadata_data = data.get("metadata", {})
        metadata = EventMetadata(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            **metadata_data,
        )

        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source_service=data["source_service"],
            target_service=data.get("target_service"),
            payload=data.get("payload", {}),
            metadata=metadata,
        )


@register_event
class SystemEvent(BaseEvent):
    """System-level events for infrastructure and operational concerns."""

    def __init__(
        self,
        component: str,
        action: str,
        status: str,
        details: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.component = component
        self.action = action
        self.status = status
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "action": self.action,
            "status": self.status,
            "details": self.details,
            "metadata": self.metadata.__dict__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemEvent:
        metadata_data = data.get("metadata", {})
        metadata = EventMetadata(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            **metadata_data,
        )

        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            component=data["component"],
            action=data["action"],
            status=data["status"],
            details=data.get("details", {}),
            metadata=metadata,
        )


@register_event
class PluginEvent(BaseEvent):
    """Events specifically for plugin system communication."""

    def __init__(
        self,
        plugin_id: str,
        plugin_action: str,
        plugin_data: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.plugin_id = plugin_id
        self.plugin_action = plugin_action
        self.plugin_data = plugin_data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "plugin_id": self.plugin_id,
            "plugin_action": self.plugin_action,
            "plugin_data": self.plugin_data,
            "metadata": self.metadata.__dict__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginEvent:
        metadata_data = data.get("metadata", {})
        metadata = EventMetadata(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            **metadata_data,
        )

        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            plugin_id=data["plugin_id"],
            plugin_action=data["plugin_action"],
            plugin_data=data.get("plugin_data", {}),
            metadata=metadata,
        )


@register_event
class WorkflowEvent(BaseEvent):
    """Events for workflow and saga system."""

    def __init__(
        self,
        workflow_id: str,
        workflow_type: str,
        workflow_step: str | None = None,
        workflow_status: str | None = None,
        workflow_data: dict[str, Any] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.workflow_step = workflow_step
        self.workflow_status = workflow_status
        self.workflow_data = workflow_data or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "workflow_id": self.workflow_id,
            "workflow_type": self.workflow_type,
            "workflow_step": self.workflow_step,
            "workflow_status": self.workflow_status,
            "workflow_data": self.workflow_data,
            "metadata": self.metadata.__dict__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowEvent:
        metadata_data = data.get("metadata", {})
        metadata = EventMetadata(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            **metadata_data,
        )

        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            workflow_id=data["workflow_id"],
            workflow_type=data["workflow_type"],
            workflow_step=data.get("workflow_step"),
            workflow_status=data.get("workflow_status"),
            workflow_data=data.get("workflow_data", {}),
            metadata=metadata,
        )


# Convenience functions for creating specific event types
def create_domain_event(
    aggregate_id: str,
    aggregate_type: str,
    event_type: str | None = None,
    aggregate_version: int = 1,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> DomainEvent:
    """Create a domain event with metadata."""
    metadata = EventMetadata(
        event_id=str(uuid4()),
        event_type=event_type or "DomainEvent",
        timestamp=datetime.now(timezone.utc),
        correlation_id=correlation_id,
        causation_id=causation_id,
        user_id=user_id,
        tenant_id=tenant_id,
    )

    event = DomainEvent(
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        aggregate_version=aggregate_version,
        metadata=metadata,
    )

    if event_type:
        event.event_type = event_type

    return event


def create_integration_event(
    source_service: str,
    target_service: str | None = None,
    event_type: str | None = None,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
    priority: EventPriority = EventPriority.NORMAL,
) -> IntegrationEvent:
    """Create an integration event with metadata."""
    metadata = EventMetadata(
        event_id=str(uuid4()),
        event_type=event_type or "IntegrationEvent",
        timestamp=datetime.now(timezone.utc),
        correlation_id=correlation_id,
        source_service=source_service,
        priority=priority,
    )

    event = IntegrationEvent(
        source_service=source_service,
        target_service=target_service,
        payload=payload,
        metadata=metadata,
    )

    if event_type:
        event.event_type = event_type

    return event


def create_plugin_event(
    plugin_id: str,
    plugin_action: str,
    event_type: str | None = None,
    plugin_data: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> PluginEvent:
    """Create a plugin event with metadata."""
    metadata = EventMetadata(
        event_id=str(uuid4()),
        event_type=event_type or "PluginEvent",
        timestamp=datetime.now(timezone.utc),
        correlation_id=correlation_id,
    )

    event = PluginEvent(
        plugin_id=plugin_id, plugin_action=plugin_action, plugin_data=plugin_data, metadata=metadata
    )

    if event_type:
        event.event_type = event_type

    return event


def create_workflow_event(
    workflow_id: str,
    workflow_type: str,
    event_type: str | None = None,
    workflow_step: str | None = None,
    workflow_status: str | None = None,
    workflow_data: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> WorkflowEvent:
    """Create a workflow event with metadata."""
    metadata = EventMetadata(
        event_id=str(uuid4()),
        event_type=event_type or "WorkflowEvent",
        timestamp=datetime.now(timezone.utc),
        correlation_id=correlation_id,
    )

    event = WorkflowEvent(
        workflow_id=workflow_id,
        workflow_type=workflow_type,
        workflow_step=workflow_step,
        workflow_status=workflow_status,
        workflow_data=workflow_data,
        metadata=metadata,
    )

    if event_type:
        event.event_type = event_type

    return event
