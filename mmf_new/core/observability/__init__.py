"""
Observability module for the Marty Microservices Framework.

This module provides comprehensive observability features including:
- Unified OpenTelemetry instrumentation
- Enhanced correlation ID tracking and context management
- Prometheus metrics collection
- Distributed tracing with automatic instrumentation
- Structured logging with context propagation
- Monitoring and alerting with Grafana dashboard integration

Core Components:
- UnifiedObservability: Central observability orchestrator
- CorrelationManager: Multi-dimensional correlation tracking
- Enhanced middleware for FastAPI and gRPC services
"""

import logging as _logging

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

logger = _logging.getLogger(__name__)


# Legacy middleware exports (maintained for backward compatibility)

# Import unified observability components

# All exports
__all__ = [
    # Unified observability
    "UnifiedObservability",
    "ObservabilityConfig",
    # Enhanced correlation
    "CorrelationContext",
    "CorrelationManager",
    "with_correlation",
    "get_correlation_id",
    "get_request_id",
    "get_user_id",
    "get_session_id",
    "set_correlation_id",
    "set_request_id",
    "set_user_id",
    "CorrelationHTTPClient",
    "EnhancedCorrelationFilter",
    "CorrelationMiddleware",
    "CorrelationInterceptor",
    # Legacy middleware
    "CorrelationIdMiddleware",
    "add_correlation_id_middleware",
    "MetricsMiddleware",
]

logger.info("Marty MSF observability module fully loaded")
