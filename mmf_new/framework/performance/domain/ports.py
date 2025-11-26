"""
Performance Domain Ports.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from mmf_new.framework.performance.domain.entities import (
    OptimizationRecommendation,
    PerformanceProfile,
    ResourceMetrics,
)

T = TypeVar("T")

class ProfilerPort(ABC):
    """Interface for performance profilers."""

    @abstractmethod
    async def profile_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[Any, PerformanceProfile]:
        """Profile an async function execution."""

    @abstractmethod
    def profile(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[Any, PerformanceProfile]:
        """Profile a synchronous function execution."""

class MetricsProviderPort(ABC):
    """Interface for system metrics providers."""

    @abstractmethod
    def get_current_metrics(self) -> ResourceMetrics:
        """Get current system resource metrics."""

class OptimizationStrategyPort(ABC):
    """Interface for optimization strategies."""

    @abstractmethod
    def analyze(
        self, profile: PerformanceProfile | None = None, metrics: ResourceMetrics | None = None
    ) -> list[OptimizationRecommendation]:
        """Analyze performance data and generate recommendations."""

