"""
Enhanced Monitoring and Observability Framework

This module provides comprehensive monitoring capabilities including:
- Custom metrics collection with Prometheus integration
- Distributed tracing with OpenTelemetry
- Advanced health checks
- Business metrics and SLA monitoring
- Alert management and notifications
- Automatic middleware integration

Key Features:
- Prometheus metrics collection
- Distributed tracing (Jaeger)
- Health check framework
- Custom business metrics
- SLA monitoring and alerting
- FastAPI/gRPC middleware integration

Usage:
    from mmf.framework.observability.monitoring import (
        initialize_monitoring,
        setup_fastapi_monitoring,
        MonitoringManager,
        BusinessMetric,
        AlertRule
    )

    # Initialize monitoring
    manager = initialize_monitoring("my-service", use_prometheus=True)

    # Add health checks
    manager.add_health_check(DatabaseHealthCheck("database", db_session))

    # Setup middleware
    setup_fastapi_monitoring(app)
"""

from .core import (
    DatabaseHealthCheck,
    DistributedTracer,
    ExternalServiceHealthCheck,
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    InMemoryCollector,
    MetricDefinition,
    MetricsCollector,
    MetricType,
    MonitoringManager,
    PrometheusCollector,
    RedisHealthCheck,
    ServiceMetrics,
    SimpleHealthCheck,
    get_monitoring_manager,
    initialize_monitoring,
    set_monitoring_manager,
)
from .custom_metrics import (
    Alert,
    AlertLevel,
    AlertManager,
    AlertRule,
    BusinessMetric,
    BusinessMetricsCollector,
    CustomMetricsManager,
    MetricAggregation,
    MetricBuffer,
    get_custom_metrics_manager,
    initialize_custom_metrics,
    record_error_rate,
    record_response_time_sla,
    record_revenue,
    record_transaction_result,
    record_user_registration,
)
from .middleware import (
    MonitoringMiddlewareConfig,
    monitor_async_function,
    monitor_function,
    setup_fastapi_monitoring,
    setup_grpc_monitoring,
)

__all__ = [
    "Alert",
    "AlertLevel",
    "AlertManager",
    "AlertRule",
    "BusinessMetric",
    "BusinessMetricsCollector",
    # Custom metrics and alerting
    "CustomMetricsManager",
    "DatabaseHealthCheck",
    # Distributed tracing
    "DistributedTracer",
    "ExternalServiceHealthCheck",
    # Health checks
    "HealthCheck",
    "HealthCheckResult",
    "HealthStatus",
    "InMemoryCollector",
    "MetricAggregation",
    "MetricBuffer",
    "MetricDefinition",
    "MetricType",
    "MetricsCollector",
    # Core monitoring
    "MonitoringManager",
    # Middleware
    "MonitoringMiddlewareConfig",
    "PrometheusCollector",
    "RedisHealthCheck",
    "ServiceMetrics",
    "SimpleHealthCheck",
    "get_custom_metrics_manager",
    "get_monitoring_manager",
    "initialize_custom_metrics",
    "initialize_monitoring",
    "monitor_async_function",
    "monitor_function",
    "record_error_rate",
    "record_response_time_sla",
    "record_revenue",
    "record_transaction_result",
    # Business metric helpers
    "record_user_registration",
    "set_monitoring_manager",
    "setup_fastapi_monitoring",
    "setup_grpc_monitoring",
]

__version__ = "1.0.0"
