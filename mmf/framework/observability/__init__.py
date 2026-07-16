"""
Observability Framework Public API.

This module exports the core components of the observability framework,
following the Hexagonal Architecture pattern.

Note: This module uses lazy imports to avoid loading heavy dependencies
(opentelemetry, psutil, requests) when only lightweight components like
CacheMetrics are needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Only import protocol definitions eagerly (no heavy dependencies)
from mmf.framework.observability.domain.protocols import (
    HealthStatus,
    IMetricsCollector,
    ITracer,
    MetricType,
)

# Cache metrics has minimal dependencies (just prometheus_client)
from .cache_metrics import CacheMetrics, NullCacheMetrics, get_cache_metrics

if TYPE_CHECKING:
    # Type hints only - not imported at runtime
    from mmf.framework.observability.adapters.monitoring import (
        HealthCheck,
        ServiceMonitor,
    )
    from mmf.framework.observability.adapters.tracing import OTEL_ENABLED
    from mmf.framework.observability.unified import (
        ObservabilityConfig,
        UnifiedObservability,
    )

    from .correlation import (
        CorrelationContext,
        CorrelationHTTPClient,
        CorrelationInterceptor,
        CorrelationManager,
        CorrelationMiddleware,
        EnhancedCorrelationFilter,
    )
    from .correlation_middleware import CorrelationIdMiddleware


# Lazy import mapping for heavy dependencies
_LAZY_IMPORTS = {
    # Monitoring (requires psutil, requests)
    "HealthCheck": "mmf.framework.observability.adapters.monitoring",
    "ObservabilityService": "mmf.framework.observability.adapters.monitoring",
    # Tracing (requires opentelemetry)
    "OTEL_ENABLED": "mmf.framework.observability.adapters.tracing",
    # Unified (requires all)
    "ObservabilityConfig": "mmf.framework.observability.unified",
    "UnifiedObservability": "mmf.framework.observability.unified",
    # Correlation (lightweight)
    "CorrelationContext": "mmf.framework.observability.correlation",
    "CorrelationHTTPClient": "mmf.framework.observability.correlation",
    "CorrelationInterceptor": "mmf.framework.observability.correlation",
    "CorrelationManager": "mmf.framework.observability.correlation",
    "CorrelationMiddleware": "mmf.framework.observability.correlation",
    "EnhancedCorrelationFilter": "mmf.framework.observability.correlation",
    "get_correlation_id": "mmf.framework.observability.correlation",
    "get_request_id": "mmf.framework.observability.correlation",
    "get_session_id": "mmf.framework.observability.correlation",
    "get_user_id": "mmf.framework.observability.correlation",
    "set_correlation_id": "mmf.framework.observability.correlation",
    "set_request_id": "mmf.framework.observability.correlation",
    "set_user_id": "mmf.framework.observability.correlation",
    "with_correlation": "mmf.framework.observability.correlation",
    "CorrelationIdMiddleware": "mmf.framework.observability.correlation_middleware",
    "add_correlation_id_middleware": "mmf.framework.observability.correlation_middleware",
}

# Special case for aliased import
_LAZY_ALIASES = {
    "ObservabilityService": ("mmf.framework.observability.adapters.monitoring", "ServiceMonitor"),
}


def __getattr__(name: str):
    """Lazy import for heavy dependencies."""
    if name in _LAZY_ALIASES:
        module_path, attr_name = _LAZY_ALIASES[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, attr_name)

    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "HealthStatus",
    "MetricType",
    "IMetricsCollector",
    "ITracer",
    "HealthCheck",
    "ObservabilityService",
    "OTEL_ENABLED",
    # Cache metrics
    "CacheMetrics",
    "NullCacheMetrics",
    "get_cache_metrics",
    # Legacy
    "CorrelationContext",
    "CorrelationHTTPClient",
    "CorrelationInterceptor",
    "CorrelationManager",
    "CorrelationMiddleware",
    "EnhancedCorrelationFilter",
    "get_correlation_id",
    "get_request_id",
    "get_session_id",
    "get_user_id",
    "set_correlation_id",
    "set_request_id",
    "set_user_id",
    "with_correlation",
    "CorrelationIdMiddleware",
    "add_correlation_id_middleware",
    "ObservabilityConfig",
    "UnifiedObservability",
]
