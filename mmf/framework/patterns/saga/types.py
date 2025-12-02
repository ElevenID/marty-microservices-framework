"""
Saga Pattern Types

This module defines the data structures and types used in the Saga pattern.
"""

import builtins
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SagaState(Enum):
    """Saga execution states."""

    CREATED = "created"
    EXECUTING = "executing"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Individual step in a saga."""

    step_id: str
    step_name: str
    service_name: str
    action: str
    compensation_action: str
    parameters: builtins.dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30
    retry_count: int = 3
    is_critical: bool = True  # If false, failure doesn't abort saga


@dataclass
class SagaTransaction:
    """Saga transaction definition."""

    saga_id: str
    saga_type: str
    steps: builtins.list[SagaStep]
    state: SagaState = SagaState.CREATED
    current_step: int = 0
    completed_steps: builtins.list[str] = field(default_factory=list)
    compensated_steps: builtins.list[str] = field(default_factory=list)
    context: builtins.dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
