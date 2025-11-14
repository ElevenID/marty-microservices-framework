"""
Event Streaming Framework Module

Advanced event streaming capabilities with event sourcing, CQRS patterns,
saga orchestration, and comprehensive event management for microservices.
"""

# Event sourcing components
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
