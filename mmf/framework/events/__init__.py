"""
Event-driven architecture components for enterprise microservices.

This package provides:
- Event bus with transactional outbox pattern
- Event handlers and subscription management
- Domain and system events
- Event registry and serialization
- Unified event publishing utilities for audit, notification, and domain events
"""

# Decorators
from .decorators import audit_event, domain_event, publish_on_error, publish_on_success

# Enhanced event bus - the primary event system
from .enhanced_event_bus import (
    BaseEvent,
    DeadLetterEvent,
    DeliveryGuarantee,
    EnhancedEventBus,
    EventBackendType,
    EventBus,
    EventFilter,
    EventHandler,
    EventMetadata,
    EventPriority,
    EventStatus,
    KafkaConfig,
    OutboxConfig,
    OutboxEvent,
    PluginEventHandler,
)

# Enhanced event types
from .enhanced_events import EVENT_REGISTRY, DomainEvent, EventRegistry
from .enhanced_events import GenericEvent as Event
from .enhanced_events import SystemEvent, register_event
from .exceptions import EventPublishingError
from .types import AuditEventType, NotificationEventType

# Create aliases for commonly used types
# Event class is now concrete and exported directly

__all__ = [
    # Enhanced event bus components
    "BaseEvent",
    "EventBus",
    "EnhancedEventBus",
    "EventHandler",
    "EventMetadata",
    "EventStatus",
    "EventPriority",
    "DeliveryGuarantee",
    "EventFilter",
    "PluginEventHandler",
    "OutboxEvent",
    "DeadLetterEvent",
    "KafkaConfig",
    "OutboxConfig",
    "EventBackendType",
    # Enhanced event types
    "EVENT_REGISTRY",
    "DomainEvent",
    "Event",
    "EventRegistry",
    "SystemEvent",
    "register_event",
    # Decorators
    "audit_event",
    "domain_event",
    "publish_on_success",
    "publish_on_error",
    # Types and exceptions
    "AuditEventType",
    "NotificationEventType",
    "EventPublishingError",
]
