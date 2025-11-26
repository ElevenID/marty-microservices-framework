"""
Enhanced Default Observability Configuration for MMF Services

This module provides standardized observability defaults that will be automatically
applied to all MMF-generated services. It ensures consistent instrumentation,
correlation tracking, and monitoring across the entire microservices framework.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from mmf_new.framework.observability.unified import ObservabilityConfig


@dataclass
class MMFObservabilityDefaults:
    """
    Default observability configuration for MMF services.

    These defaults ensure consistent observability across all service types
    while allowing for environment-specific customization.
    """

    # Standard resource attributes for all MMF services
    STANDARD_RESOURCE_ATTRIBUTES: dict[str, str] = field(
        default_factory=lambda: {
            "mmf.framework.version": "2.0.0",
            "mmf.observability.mode": "unified",
            "deployment.environment": os.getenv("DEPLOYMENT_ENVIRONMENT", "development"),
            "kubernetes.cluster.name": os.getenv("K8S_CLUSTER_NAME", "default"),
            "kubernetes.namespace.name": os.getenv("K8S_NAMESPACE", "default"),
        }
    )

    # Environment-specific sampling rates
    ENVIRONMENT_SAMPLING_RATES: dict[str, float] = field(
        default_factory=lambda: {
            "development": 1.0,  # 100% sampling in development
            "testing": 1.0,  # 100% sampling in testing
            "staging": 0.5,  # 50% sampling in staging
            "production": 0.1,  # 10% sampling in production
        }
    )

    # Standard correlation headers
    CORRELATION_HEADERS: list[str] = field(
        default_factory=lambda: [
            "x-mmf-correlation-id",  # Primary correlation ID
            "x-mmf-request-id",  # Request-specific ID
            "x-mmf-user-id",  # User context
            "x-mmf-session-id",  # Session context
            "x-mmf-operation-id",  # Operation context
            "x-mmf-plugin-id",  # Plugin context for debugging
        ]
    )

    # Standard Prometheus metrics
    STANDARD_METRICS: list[dict[str, str]] = field(
        default_factory=lambda: [
            {
                "name": "mmf_requests_total",
                "description": "Total number of requests processed",
                "type": "counter",
                "labels": ["method", "endpoint", "status_code", "service_type"],
            },
            {
                "name": "mmf_request_duration_seconds",
                "description": "Request processing duration",
                "type": "histogram",
                "labels": ["method", "endpoint", "service_type"],
            },
            {
                "name": "mmf_active_connections",
                "description": "Number of active connections",
                "type": "gauge",
                "labels": ["service_type", "connection_type"],
            },
            {
                "name": "mmf_plugin_operations_total",
                "description": "Total plugin operations",
                "type": "counter",
                "labels": ["plugin_id", "operation", "status"],
            },
            {
                "name": "mmf_cache_operations_total",
                "description": "Total cache operations",
                "type": "counter",
                "labels": ["operation", "backend", "status"],
            },
            {
                "name": "mmf_database_operations_total",
                "description": "Total database operations",
                "type": "counter",
                "labels": ["operation", "table", "status"],
            },
        ]
    )


def create_default_observability_config(
    service_name: str,
    service_version: str = "1.0.0",
    service_type: str = "unknown",
    environment: str | None = None,
    **overrides,
) -> ObservabilityConfig:
    """
    Create a standardized observability configuration for MMF services.

    Args:
        service_name: Unique identifier for the service
        service_version: Semantic version of the service
        service_type: Type of service (fastapi, grpc, hybrid)
        environment: Deployment environment (auto-detected if not provided)
        **overrides: Any configuration overrides

    Returns:
        Configured ObservabilityConfig with MMF defaults
    """
    defaults = MMFObservabilityDefaults()

    # Auto-detect environment if not provided
    if environment is None:
        environment = os.getenv("DEPLOYMENT_ENVIRONMENT", "development")

    # Get environment-specific sampling rate
    sample_rate = defaults.ENVIRONMENT_SAMPLING_RATES.get(environment, 0.1)

    # Build resource attributes
    resource_attributes = defaults.STANDARD_RESOURCE_ATTRIBUTES.copy()
    resource_attributes.update(
        {
            "service.name": service_name,
            "service.version": service_version,
            "mmf.service.type": service_type,
        }
    )

    # Create base configuration
    config = ObservabilityConfig(
        # Service identification
        service_name=service_name,
        service_version=service_version,
        environment=environment,
        # Tracing configuration with environment-specific sampling
        tracing_enabled=True,
        trace_sample_rate=sample_rate,
        jaeger_endpoint=os.getenv(
            "OTEL_EXPORTER_JAEGER_ENDPOINT", "http://jaeger:14268/api/traces"
        ),
        otlp_trace_endpoint=os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector:4317"
        ),
        # Metrics configuration
        metrics_enabled=True,
        prometheus_enabled=True,
        prometheus_port=int(os.getenv("OTEL_EXPORTER_PROMETHEUS_PORT", "8000")),
        otlp_metrics_endpoint=os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://opentelemetry-collector:4317"
        ),
        # Enhanced logging configuration
        structured_logging=True,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        correlation_id_enabled=True,
        trace_context_in_logs=True,
        # Auto-instrumentation
        auto_instrument_fastapi=True,
        auto_instrument_grpc=True,
        auto_instrument_http_clients=True,
        auto_instrument_databases=True,
        auto_instrument_redis=True,
        # Custom resource attributes
        custom_resource_attributes=resource_attributes,
        # Apply any overrides
        **overrides,
    )

    return config


def get_default_dashboard_configs() -> dict[str, dict]:
    """
    Get default Grafana dashboard configurations for MMF services.

    Returns:
        Dictionary of dashboard configurations keyed by dashboard name
    """
    return {
        "mmf-service-overview": {
            "title": "MMF Service Overview",
            "description": "High-level metrics for MMF microservices",
            "tags": ["mmf", "microservices", "overview"],
            "templating": {
                "variables": [
                    {
                        "name": "service",
                        "query": "label_values(mmf_requests_total, service_name)",
                        "type": "query",
                    },
                    {
                        "name": "environment",
                        "query": "label_values(mmf_requests_total, deployment_environment)",
                        "type": "query",
                    },
                ]
            },
        },
        "mmf-distributed-tracing": {
            "title": "MMF Distributed Tracing",
            "description": "Trace analysis and service dependency mapping",
            "tags": ["mmf", "tracing", "distributed"],
            "datasources": ["jaeger", "prometheus"],
        },
        "mmf-plugin-debugging": {
            "title": "MMF Plugin Debugging",
            "description": "Plugin interaction analysis and troubleshooting",
            "tags": ["mmf", "plugins", "debugging"],
            "templating": {
                "variables": [
                    {
                        "name": "plugin",
                        "query": "label_values(mmf_plugin_operations_total, plugin_id)",
                        "type": "query",
                    }
                ]
            },
        },
        "mmf-performance-analysis": {
            "title": "MMF Performance Analysis",
            "description": "Performance metrics and bottleneck analysis",
            "tags": ["mmf", "performance", "analysis"],
        },
    }


def get_default_alert_rules() -> list[dict]:
    """
    Get default Prometheus alert rules for MMF services.

    Returns:
        List of alert rule configurations
    """
    return [
        {
            "alert": "MMFHighErrorRate",
            "expr": 'rate(mmf_requests_total{status_code=~"5.."}[5m]) > 0.1',
            "for": "5m",
            "labels": {"severity": "warning", "component": "mmf-service"},
            "annotations": {
                "summary": "MMF service {{ $labels.service_name }} has high error rate",
                "description": "Error rate is {{ $value | humanizePercentage }} for service {{ $labels.service_name }}",
            },
        },
        {
            "alert": "MMFHighLatency",
            "expr": "histogram_quantile(0.95, rate(mmf_request_duration_seconds_bucket[5m])) > 1.0",
            "for": "5m",
            "labels": {"severity": "warning", "component": "mmf-service"},
            "annotations": {
                "summary": "MMF service {{ $labels.service_name }} has high latency",
                "description": "95th percentile latency is {{ $value }}s for service {{ $labels.service_name }}",
            },
        },
        {
            "alert": "MMFPluginErrors",
            "expr": 'rate(mmf_plugin_operations_total{status="error"}[5m]) > 0.05',
            "for": "2m",
            "labels": {"severity": "warning", "component": "mmf-plugin"},
            "annotations": {
                "summary": "MMF plugin {{ $labels.plugin_id }} has errors",
                "description": "Plugin error rate is {{ $value | humanizePercentage }} for plugin {{ $labels.plugin_id }}",
            },
        },
        {
            "alert": "MMFServiceDown",
            "expr": 'up{job=~"mmf-.*"} == 0',
            "for": "1m",
            "labels": {"severity": "critical", "component": "mmf-service"},
            "annotations": {
                "summary": "MMF service {{ $labels.job }} is down",
                "description": "Service {{ $labels.job }} has been down for more than 1 minute",
            },
        },
    ]
