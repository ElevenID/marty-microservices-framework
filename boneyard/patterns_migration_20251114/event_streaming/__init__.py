"""
Event Streaming Framework Module

Advanced event streaming capabilities with event sourcing, CQRS patterns,
saga orchestration, and comprehensive event management for microservices.
"""

# Core event abstractions
from .core import (
    DomainEvent,
    Event,
    EventBus,
    EventDispatcher,
    EventHandler,
    EventMetadata,
    EventProcessingError,
    EventSerializer,
    EventStore,
    EventStream,
    EventSubscription,
    EventType,
    InMemoryEventBus,
    InMemoryEventStore,
    IntegrationEvent,
    JSONEventSerializer,
)

# CQRS components
from .cqrs import (
    Command,
    CommandBus,
    CommandHandler,
    CommandResult,
    CommandStatus,
    CommandValidationError,
    CQRSError,
    InMemoryReadModelStore,
    Projection,
    ProjectionManager,
    Query,
    QueryBus,
    QueryHandler,
    QueryResult,
    QueryType,
    QueryValidationError,
    ReadModelStore,
)

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
    # Core event abstractions
    "DomainEvent",
    "Event",
    "EventBus",
    "EventDispatcher",
    "EventHandler",
    "EventMetadata",
    "EventProcessingError",
    "EventSerializer",
    "EventStore",
    "EventStream",
    "EventSubscription",
    "EventType",
    "InMemoryEventBus",
    "InMemoryEventStore",
    "IntegrationEvent",
    "JSONEventSerializer",
    # CQRS components
    "Command",
    "CommandBus",
    "CommandHandler",
    "CommandResult",
    "CommandStatus",
    "CommandValidationError",
    "CQRSError",
    "InMemoryReadModelStore",
    "Projection",
    "ProjectionManager",
    "Query",
    "QueryBus",
    "QueryHandler",
    "QueryResult",
    "QueryType",
    "QueryValidationError",
    "ReadModelStore",
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
