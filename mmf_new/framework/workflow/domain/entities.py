"""
Workflow Domain Entities.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any


class WorkflowStatus(Enum):
    """Workflow execution status."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class StepStatus(Enum):
    """Individual step status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    COMPENSATED = "compensated"


class StepType(Enum):
    """Types of workflow steps."""

    ACTION = "action"
    DECISION = "decision"
    PARALLEL = "parallel"
    LOOP = "loop"
    WAIT = "wait"
    COMPENSATION = "compensation"


@dataclass
class StepResult:
    """Result of step execution."""

    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    should_retry: bool = False
    retry_delay: timedelta | None = None


@dataclass
class WorkflowContext:
    """Workflow execution context."""

    workflow_id: str
    correlation_id: str
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    step_results: dict[str, StepResult] = field(default_factory=dict)
