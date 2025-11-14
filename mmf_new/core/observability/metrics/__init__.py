"""
Framework metrics module.

This module provides a convenient interface to the framework's metrics collection
capabilities. It re-exports the main metrics classes from the observability module.
"""

from ..observability.monitoring import (
    HealthCheck,
    HealthStatus,
    Metric,
    MetricsCollector,
    MetricType,
    SystemMetrics,
)

__all__ = [
    "MetricsCollector",
    "Metric",
    "MetricType",
    "HealthCheck",
    "HealthStatus",
    "SystemMetrics",
]
