"""
Architectural Patterns Module

This module provides advanced architectural patterns for building robust,
scalable microservices including Event Sourcing and Saga patterns.
"""

# Event Streaming (Event Sourcing, Saga)
from .event_streaming import (  # Event Sourcing; Saga
    AggregateRepository,
    AggregateRoot,
    CompensationAction,
    EventSourcedRepository,
    Saga,
    SagaManager,
    SagaOrchestrator,
    SagaStatus,
    SagaStep,
    Snapshot,
    SnapshotStore,
)

__all__ = [
    # Event Sourcing
    "AggregateRoot",
    "AggregateRepository",
    "EventSourcedRepository",
    "Snapshot",
    "SnapshotStore",
    # Saga
    "Saga",
    "SagaManager",
    "SagaOrchestrator",
    "SagaStatus",
    "SagaStep",
    "CompensationAction",
]
