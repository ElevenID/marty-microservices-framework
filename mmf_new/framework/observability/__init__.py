"""
Observability Framework Public API.

This module exports the core components of the observability framework,
following the Hexagonal Architecture pattern.
"""

from mmf_new.framework.observability.adapters.monitoring import HealthCheck
from mmf_new.framework.observability.adapters.monitoring import (
    ServiceMonitor as ObservabilityService,
)
from mmf_new.framework.observability.adapters.tracing import OTEL_ENABLED
from mmf_new.framework.observability.domain.protocols import (
    HealthStatus,
    IMetricsCollector,
    ITracer,
    MetricType,
)

# Legacy exports (to be removed or refactored)
from .correlation import (
    CorrelationContext,
    CorrelationHTTPClient,
    CorrelationInterceptor,
    CorrelationManager,
    CorrelationMiddleware,
    EnhancedCorrelationFilter,
    get_correlation_id,
    get_request_id,
    get_session_id,
    get_user_id,
    set_correlation_id,
    set_request_id,
    set_user_id,
    with_correlation,
)
from .correlation_middleware import (
    CorrelationIdMiddleware,
    add_correlation_id_middleware,
)
from .unified import ObservabilityConfig, UnifiedObservability

__all__ = [
    "HealthStatus",
    "MetricType",
    "IMetricsCollector",
    "ITracer",
    "HealthCheck",
    "ObservabilityService",
    "OTEL_ENABLED",
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
