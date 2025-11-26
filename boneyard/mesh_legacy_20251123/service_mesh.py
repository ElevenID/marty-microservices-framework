"""
Service Mesh Configuration and Types for Marty Microservices Framework

This module defines service mesh types, configurations, and base classes
for service mesh integration.
"""

import builtins
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ServiceMeshType(Enum):
    """Supported service mesh types."""

    ISTIO = "istio"
    LINKERD = "linkerd"
    CONSUL_CONNECT = "consul_connect"
    ENVOY = "envoy"
    CUSTOM = "custom"


class TrafficPolicy(Enum):
    """Traffic management policies."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONN = "least_conn"
    RANDOM = "random"
    CONSISTENT_HASH = "consistent_hash"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LOCALITY_AWARE = "locality_aware"


class CircuitBreakerPolicy(Enum):
    """Circuit breaker policies for service mesh."""

    CONSECUTIVE_ERRORS = "consecutive_errors"
    ERROR_RATE = "error_rate"
    SLOW_CALL_RATE = "slow_call_rate"
    COMBINED = "combined"


class SecurityPolicy(Enum):
    """Security policies for service communication."""

    MTLS_STRICT = "mtls_strict"
    MTLS_PERMISSIVE = "mtls_permissive"
    PLAINTEXT = "plaintext"
    CUSTOM_TLS = "custom_tls"


class ServiceDiscoveryProvider(Enum):
    """Service discovery providers."""

    KUBERNETES = "kubernetes"
    CONSUL = "consul"
    ETCD = "etcd"
    EUREKA = "eureka"
    CUSTOM = "custom"


@dataclass
class ServiceEndpoint:
    """Service endpoint configuration."""

    service_name: str
    host: str
    port: int
    protocol: str = "http"
    health_check_path: str = "/health"
    version: str = "v1"
    region: str = "default"
    zone: str = "default"
    metadata: builtins.dict[str, str] = field(default_factory=dict)
    weight: int = 100
    is_healthy: bool = True


@dataclass
class TrafficRule:
    """Traffic routing rule."""

    rule_id: str
    service_name: str
    match_conditions: builtins.list[builtins.dict[str, Any]]
    destination_rules: builtins.list[builtins.dict[str, Any]]
    weight: int = 100
    timeout_seconds: int = 30
    retry_policy: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceMeshConfig:
    """Service mesh configuration."""

    mesh_type: ServiceMeshType = ServiceMeshType.ISTIO
    namespace: str = "default"
    control_plane_namespace: str = "istio-system"
    enable_mutual_tls: bool = True
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_access_logs: bool = True
    ingress_gateway_enabled: bool = True
    egress_gateway_enabled: bool = False
    mesh_config_options: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceDiscoveryConfig:
    """Service discovery configuration."""

    provider: ServiceDiscoveryProvider = ServiceDiscoveryProvider.KUBERNETES
    endpoint_url: str = ""
    namespace: str = "default"
    health_check_interval: int = 30
    healthy_threshold: int = 2
    unhealthy_threshold: int = 3
    timeout_seconds: int = 5
    discovery_options: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration for service mesh."""

    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_seconds: float = 60.0
    evaluation_window: int = 100
    policy: CircuitBreakerPolicy = CircuitBreakerPolicy.CONSECUTIVE_ERRORS
    config_options: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class LoadBalancingConfig:
    """Load balancing configuration."""

    policy: TrafficPolicy = TrafficPolicy.ROUND_ROBIN
    hash_policy: builtins.dict[str, str] | None = None
    locality_lb_setting: builtins.dict[str, Any] | None = None
    outlier_detection: CircuitBreakerConfig | None = None


@dataclass
class ServiceCommunication:
    """Service-to-service communication tracking."""

    source_service: str
    destination_service: str
    protocol: str
    success_count: int = 0
    error_count: int = 0
    total_latency: float = 0.0
    last_communication: datetime | None = None
    circuit_breaker_state: str = "closed"
