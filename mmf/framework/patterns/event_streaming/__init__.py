"""
Event Streaming Framework Module

Advanced event streaming capabilities with event sourcing, CQRS patterns,
saga orchestration, and comprehensive event management for microservices.
"""

# Event sourcing components
from mmf.core.application.base import Command, CommandStatus
from mmf.core.application.handlers import CommandHandler
from mmf.core.domain.entity import DomainEvent
from mmf.framework.events.enhanced_event_bus import (
    EventBus,
    EventHandler,
    EventMetadata,
)
from mmf.framework.infrastructure.messaging import CommandBus

from .event_sourcing import (
    Aggregate,
    AggregateFactory,
    AggregateNotFoundError,
    AggregateRepository,
    AggregateRoot,
    ConcurrencyError,
    EventSourcedProjection,
    EventSourcedRepository,
    EventSourcingError,
    InMemorySnapshotStore,
    Snapshot,
    SnapshotStore,
)

# Saga components
from .saga import (
    CompensationAction,
    CompensationStrategy,
    Saga,
    SagaCompensationError,
    SagaContext,
    SagaError,
    SagaManager,
    SagaOrchestrator,
    SagaRepository,
    SagaStatus,
    SagaStep,
    SagaTimeoutError,
    StepStatus,
)

# Export all components for public API
__all__ = [
    # Event sourcing components
    "Aggregate",
    "AggregateFactory",
    "AggregateNotFoundError",
    "AggregateRepository",
    "AggregateRoot",
    "ConcurrencyError",
    "EventSourcedProjection",
    "EventSourcedRepository",
    "EventSourcingError",
    "InMemorySnapshotStore",
    "Snapshot",
    "SnapshotStore",
    # Saga components
    "CompensationAction",
    "CompensationStrategy",
    "Saga",
    "SagaCompensationError",
    "SagaContext",
    "SagaError",
    "SagaManager",
    "SagaOrchestrator",
    "SagaRepository",
    "SagaStatus",
    "SagaStep",
    "SagaTimeoutError",
    "StepStatus",
]


# Import core components

# Alias DomainEvent as Event for compatibility
Event = DomainEvent
