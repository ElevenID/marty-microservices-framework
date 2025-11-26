"""
Performance Application Services.
"""

import logging
from collections.abc import Callable
from typing import Any

from mmf_new.framework.performance.domain.entities import (
    OptimizationRecommendation,
    OptimizationType,
    PerformanceProfile,
    ResourceMetrics,
)
from mmf_new.framework.performance.domain.ports import (
    MetricsProviderPort,
    OptimizationStrategyPort,
    ProfilerPort,
)
from mmf_new.framework.performance.infrastructure.adapters.metrics import SystemMetricsAdapter
from mmf_new.framework.performance.infrastructure.adapters.profiling import CProfileAdapter

logger = logging.getLogger(__name__)


class OptimizationAnalyzer(OptimizationStrategyPort):
    """Analyzes performance data to generate optimization recommendations."""

    def analyze(
        self, profile: PerformanceProfile | None = None, metrics: ResourceMetrics | None = None
    ) -> list[OptimizationRecommendation]:
        """Analyze performance data and generate recommendations."""
        recommendations: list[OptimizationRecommendation] = []

        if profile:
            recommendations.extend(self._analyze_profile(profile))

        if metrics:
            recommendations.extend(self._analyze_metrics(metrics))

        return recommendations

    def _analyze_profile(self, profile: PerformanceProfile) -> list[OptimizationRecommendation]:
        recommendations = []

        # Check for CPU hotspots
        if profile.hotspots:
            top_hotspot = profile.hotspots[0]
            stats = profile.function_stats.get(top_hotspot, {})

            if stats.get("cumulative_time", 0) > 1.0:  # If takes more than 1s
                recommendations.append(OptimizationRecommendation(
                    optimization_type=OptimizationType.CPU_OPTIMIZATION,
                    title=f"Optimize CPU Hotspot: {top_hotspot}",
                    description=f"Function {top_hotspot} is consuming significant CPU time ({stats.get('cumulative_time'):.2f}s).",
                    priority=8,
                    estimated_impact=0.2,
                    implementation_effort="medium",
                    code_location=top_hotspot,
                    specific_actions=["Review algorithm complexity", "Cache results if pure function"]
                ))

        return recommendations

    def _analyze_metrics(self, metrics: ResourceMetrics) -> list[OptimizationRecommendation]:
        recommendations = []

        # High CPU usage
        if metrics.cpu_percent > 80:
            recommendations.append(OptimizationRecommendation(
                optimization_type=OptimizationType.CPU_OPTIMIZATION,
                title="High CPU Usage Detected",
                description=f"System CPU usage is at {metrics.cpu_percent}%.",
                priority=9,
                estimated_impact=0.3,
                implementation_effort="high",
                specific_actions=["Scale out instances", "Optimize compute-heavy tasks"]
            ))

        # High Memory usage
        if metrics.memory_percent > 85:
            recommendations.append(OptimizationRecommendation(
                optimization_type=OptimizationType.MEMORY_OPTIMIZATION,
                title="High Memory Usage Detected",
                description=f"System memory usage is at {metrics.memory_percent}%.",
                priority=9,
                estimated_impact=0.3,
                implementation_effort="medium",
                specific_actions=["Check for memory leaks", "Increase container memory limit"]
            ))

        return recommendations


class PerformanceService:
    """
    Service for managing performance profiling and optimization.
    """

    def __init__(
        self,
        profiler: ProfilerPort | None = None,
        metrics_provider: MetricsProviderPort | None = None,
        analyzer: OptimizationStrategyPort | None = None,
    ):
        self.profiler = profiler or CProfileAdapter()
        self.metrics_provider = metrics_provider or SystemMetricsAdapter()
        self.analyzer = analyzer or OptimizationAnalyzer()

    async def profile_and_analyze_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[Any, PerformanceProfile, list[OptimizationRecommendation]]:
        """
        Execute an async function with profiling and return result, profile, and recommendations.
        """
        result, profile = await self.profiler.profile_async(func, *args, **kwargs)

        # Get current metrics for context
        metrics = self.metrics_provider.get_current_metrics()

        # Analyze
        recommendations = self.analyzer.analyze(profile=profile, metrics=metrics)

        # Update profile with recommendations
        profile.recommendations = [r.title for r in recommendations]

        return result, profile, recommendations

    def profile_and_analyze(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> tuple[Any, PerformanceProfile, list[OptimizationRecommendation]]:
        """
        Execute a sync function with profiling and return result, profile, and recommendations.
        """
        result, profile = self.profiler.profile(func, *args, **kwargs)

        metrics = self.metrics_provider.get_current_metrics()
        recommendations = self.analyzer.analyze(profile=profile, metrics=metrics)

        profile.recommendations = [r.title for r in recommendations]

        return result, profile, recommendations

    def get_system_health(self) -> tuple[ResourceMetrics, list[OptimizationRecommendation]]:
        """Get current system metrics and any immediate recommendations."""
        metrics = self.metrics_provider.get_current_metrics()
        recommendations = self.analyzer.analyze(metrics=metrics)
        return metrics, recommendations
