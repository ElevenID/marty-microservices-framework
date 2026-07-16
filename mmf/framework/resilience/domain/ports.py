"""
Resilience Domain Ports.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class ResilienceMetrics:
    """Resilience operation metrics."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    circuit_breaker_open_count: int = 0
    retry_count: int = 0
    timeout_count: int = 0
    bulkhead_rejected_count: int = 0
    average_response_time: float = 0.0
    last_failure_time: float | None = None
    last_success_time: float | None = None


@dataclass
class ResilienceResult:
    """Result of a resilience operation."""

    success: bool
    result: Any = None
    error: Exception | None = None
    execution_time: float = 0.0
    retries_attempted: int = 0
    circuit_breaker_triggered: bool = False
    timeout_occurred: bool = False
    bulkhead_rejected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ResilienceManagerPort(ABC):
    """Abstract interface for resilience managers."""

    @abstractmethod
    async def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with resilience patterns applied."""
