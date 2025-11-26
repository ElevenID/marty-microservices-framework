"""
Advanced Data Management Patterns for Marty Microservices Framework

This module re-exports all classes from the decomposed modules to maintain
backward compatibility while improving code organization.
"""

# Re-export all classes from decomposed modules

# Data consistency patterns
from .consistency_patterns import (
    ConsistencyLevel,
    DataConsistencyManager,
    DistributedCache,
)

# CQRS patterns
from .cqrs_patterns import (
    Command,
    CommandHandler,
    CQRSBus,
    ProjectionManager,
    Query,
    QueryHandler,
)

# Event Sourcing patterns
from .event_sourcing_patterns import (
    AggregateRoot,
    DomainEvent,
    EventSourcingRepository,
    EventStore,
    EventStream,
    EventType,
    InMemoryEventStore,
    Repository,
    Snapshot,
)

# Saga patterns
from .saga_patterns import (
    SagaBuilder,
    SagaOrchestrator,
    SagaState,
    SagaStep,
    SagaTransaction,
)

# Distributed transaction patterns
from .transaction_patterns import (
    DistributedTransaction,
    DistributedTransactionCoordinator,
    TransactionManager,
    TransactionParticipant,
    TransactionState,
)

# Maintain compatibility with original import structure
__all__ = [
    # Event Sourcing
    "EventType",
    "DomainEvent",
    "EventStream",
    "Snapshot",
    "EventStore",
    "InMemoryEventStore",
    "AggregateRoot",
    "Repository",
    "EventSourcingRepository",
    # CQRS
    "Command",
    "Query",
    "CommandHandler",
    "QueryHandler",
    "ProjectionManager",
    "CQRSBus",
    # Transactions
    "TransactionState",
    "TransactionParticipant",
    "DistributedTransaction",
    "DistributedTransactionCoordinator",
    "TransactionManager",
    # Sagas
    "SagaState",
    "SagaStep",
    "SagaTransaction",
    "SagaOrchestrator",
    "SagaBuilder",
    # Consistency
    "ConsistencyLevel",
    "DistributedCache",
    "DataConsistencyManager",
]
