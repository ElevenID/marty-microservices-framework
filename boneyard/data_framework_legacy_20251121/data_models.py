"""
Data Management Models and Data Structures

This module contains all the data models, enums, and data classes used
throughout the advanced data management framework components.
"""

import builtins
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(Enum):
    """Event types for event sourcing."""

    DOMAIN_EVENT = "domain_event"
    INTEGRATION_EVENT = "integration_event"
    SYSTEM_EVENT = "system_event"
    FAILURE_EVENT = "failure_event"
    COMPENSATION_EVENT = "compensation_event"


class TransactionState(Enum):
    """Distributed transaction states."""

    STARTED = "started"
    PREPARING = "preparing"
    PREPARED = "prepared"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ABORTING = "aborting"
    ABORTED = "aborted"
    FAILED = "failed"
    TIMEOUT = "timeout"


class SagaState(Enum):
    """Saga execution states."""

    CREATED = "created"
    EXECUTING = "executing"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


class ConsistencyLevel(Enum):
    """Data consistency levels."""

    STRONG = "strong"
    EVENTUAL = "eventual"
    WEAK = "weak"
    SESSION = "session"
    BOUNDED_STALENESS = "bounded_staleness"


@dataclass
class DomainEvent:
    """Domain event for event sourcing."""

    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    version: int
    data: builtins.dict[str, Any]
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str | None = None
    causation_id: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert event to dictionary."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "DomainEvent":
        """Create event from dictionary."""
        data = data.copy()
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class EventStream:
    """Event stream for aggregate events."""

    aggregate_id: str
    aggregate_type: str
    events: builtins.list[DomainEvent] = field(default_factory=list)
    version: int = 0


@dataclass
class Snapshot:
    """Aggregate snapshot for performance optimization."""

    aggregate_id: str
    aggregate_type: str
    version: int
    data: builtins.dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Command:
    """Command for CQRS pattern."""

    command_id: str
    command_type: str
    aggregate_id: str
    data: builtins.dict[str, Any]
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Query:
    """Query for CQRS pattern."""

    query_id: str
    query_type: str
    parameters: builtins.dict[str, Any]
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ReadModel:
    """Read model for query side."""

    model_id: str
    model_type: str
    data: builtins.dict[str, Any]
    version: int = 1
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TransactionParticipant:
    """Participant in distributed transaction."""

    participant_id: str
    service_name: str
    endpoint: str
    transaction_data: builtins.dict[str, Any]
    state: TransactionState = TransactionState.STARTED


@dataclass
class DistributedTransaction:
    """Distributed transaction coordinator."""

    transaction_id: str
    coordinator_id: str
    participants: builtins.list[TransactionParticipant] = field(default_factory=list)
    state: TransactionState = TransactionState.STARTED
    timeout_seconds: int = 30
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SagaStep:
    """Step in saga transaction."""

    step_id: str
    step_name: str
    service_name: str
    action: str
    compensation_action: str
    data: builtins.dict[str, Any]
    completed: bool = False
    compensated: bool = False


@dataclass
class SagaTransaction:
    """Saga transaction pattern implementation."""

    saga_id: str
    saga_type: str
    steps: builtins.list[SagaStep] = field(default_factory=list)
    state: SagaState = SagaState.CREATED
    current_step: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
