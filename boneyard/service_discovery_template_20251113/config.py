"""
Service Discovery Configuration

Configuration management for service discovery with support for:
- Multiple registry backends (Consul, etcd, Kubernetes)
- Health monitoring settings
- Load balancing strategies
- Service metadata management
- Failover and clustering
"""

import builtins
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, dict, list, set


class RegistryType(Enum):
    """Service registry backend types."""

    CONSUL = "consul"
    ETCD = "etcd"
    KUBERNETES = "kubernetes"
    MEMORY = "memory"


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    RANDOM = "random"
    CONSISTENT_HASH = "consistent_hash"
    HEALTH_BASED = "health_based"


class HealthCheckStrategy(Enum):
    """Health check strategies."""

    HTTP = "http"
    TCP = "tcp"
    GRPC = "grpc"
    CUSTOM = "custom"


@dataclass
class ConsulConfig:
    """Consul registry configuration."""

    host: str = "localhost"
    port: int = 8500
    scheme: str = "http"
    token: str | None = None
    datacenter: str | None = None
    verify_ssl: bool = True
    timeout: int = 30
    connect_timeout: int = 5
    retry_attempts: int = 3
    retry_delay: float = 1.0

    # Consul-specific settings
    session_ttl: int = 60
    lock_delay: int = 15
    enable_sessions: bool = True

    # Service registration settings
    enable_tag_override: bool = False
    enable_service_checks: bool = True
    check_interval: str = "30s"
    check_timeout: str = "10s"
    deregister_critical_after: str = "1m"


@dataclass
class EtcdConfig:
    """etcd registry configuration."""

    host: str = "localhost"
    port: int = 2379
    ca_cert: str | None = None
    cert_key: str | None = None
    cert_cert: str | None = None
    user: str | None = None
    password: str | None = None
    timeout: int = 30
    connect_timeout: int = 5
    retry_attempts: int = 3
    retry_delay: float = 1.0

    # etcd-specific settings
    lease_ttl: int = 60
    key_prefix: str = "/services/"
    enable_watch: bool = True
    compact_revision: int | None = None


@dataclass
class KubernetesConfig:
    """Kubernetes registry configuration."""

    namespace: str = "default"
    kubeconfig_path: str | None = None
    in_cluster: bool = True
    api_server_url: str | None = None
    token: str | None = None
    ca_cert_path: str | None = None

    # Service discovery settings
    watch_endpoints: bool = True
    watch_services: bool = True
    enable_annotations: bool = True
    service_port_name: str = "http"

    # Labels and annotations
    service_label_selector: str | None = None
    discovery_annotation: str = "marty-framework/discovery"
    metadata_annotation_prefix: str = "marty-framework/"


@dataclass
class HealthCheckConfig:
    """Health check configuration."""

    enabled: bool = True
    strategy: HealthCheckStrategy = HealthCheckStrategy.HTTP
    interval: int = 30
    timeout: int = 10
    retries: int = 3
    failure_threshold: int = 3
    success_threshold: int = 1

    # HTTP health check settings
    http_path: str = "/health"
    http_method: str = "GET"
    http_expected_status: int = 200
    http_expected_body: str | None = None

    # TCP health check settings
    tcp_port: int | None = None

    # gRPC health check settings
    grpc_service: str | None = None

    # Custom health check
    custom_command: str | None = None
    custom_script: str | None = None


@dataclass
class LoadBalancingConfig:
    """Load balancing configuration."""

    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    health_check_enabled: bool = True
    sticky_sessions: bool = False
    session_affinity_key: str = "client_ip"

    # Weighted round robin settings
    weights: builtins.dict[str, float] = field(default_factory=dict)

    # Health-based settings
    health_weight_factor: float = 0.7
    response_time_weight_factor: float = 0.3

    # Circuit breaker integration
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 30


@dataclass
class ServiceRegistrationConfig:
    """Service registration configuration."""

    auto_register: bool = True
    register_on_startup: bool = True
    deregister_on_shutdown: bool = True
    heartbeat_interval: int = 30
    heartbeat_timeout: int = 10

    # Service metadata
    default_tags: builtins.set[str] = field(default_factory=set)
    default_metadata: builtins.dict[str, str] = field(default_factory=dict)

    # Registration retry settings
    retry_attempts: int = 3
    retry_delay: float = 2.0
    retry_backoff_factor: float = 2.0


@dataclass
class DiscoveryConfig:
    """Service discovery configuration."""

    enabled: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 300
    cache_size: int = 1000

    # Discovery refresh settings
    refresh_interval: int = 60
    background_refresh: bool = True

    # Filtering and selection
    default_tags: builtins.set[str] = field(default_factory=set)
    prefer_local_instances: bool = False
    exclude_unhealthy: bool = True

    # Discovery strategies
    discovery_strategies: builtins.list[str] = field(default_factory=lambda: ["registry", "dns"])
    dns_domain: str | None = None


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""

    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"

    # Tracing
    tracing_enabled: bool = False
    jaeger_endpoint: str | None = None
    trace_sample_rate: float = 0.1

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    log_discovery_events: bool = True
    log_health_checks: bool = False

    # Alerting
    alerting_enabled: bool = False
    alert_webhook_url: str | None = None


@dataclass
class SecurityConfig:
    """Security configuration for service discovery."""

    authentication_enabled: bool = False
    authorization_enabled: bool = False

    # TLS settings
    tls_enabled: bool = False
    tls_cert_path: str | None = None
    tls_key_path: str | None = None
    tls_ca_path: str | None = None
    tls_verify: bool = True

    # API security
    api_key_enabled: bool = False
    api_key_header: str = "X-API-Key"
    api_keys: builtins.set[str] = field(default_factory=set)

    # JWT settings
    jwt_enabled: bool = False
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600


@dataclass
class ServiceDiscoveryConfig:
    """Main service discovery configuration."""

    # Basic settings
    service_name: str = "service-discovery"
    host: str = "0.0.0.0"
    port: int = 8090
    environment: str = "development"

    # Registry configuration
    registry_type: RegistryType = RegistryType.CONSUL
    consul: ConsulConfig = field(default_factory=ConsulConfig)
    etcd: EtcdConfig = field(default_factory=EtcdConfig)
    kubernetes: KubernetesConfig = field(default_factory=KubernetesConfig)

    # Core components
    health_check: HealthCheckConfig = field(default_factory=HealthCheckConfig)
    load_balancing: LoadBalancingConfig = field(default_factory=LoadBalancingConfig)
    registration: ServiceRegistrationConfig = field(
        default_factory=ServiceRegistrationConfig
    )
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # Clustering and failover
    cluster_enabled: bool = False
    cluster_nodes: builtins.list[str] = field(default_factory=list)
    failover_enabled: bool = True
    backup_registries: builtins.list[str] = field(default_factory=list)

    def get_registry_config(self) -> builtins.dict[str, Any]:
        """Get configuration for the selected registry type."""
        if self.registry_type == RegistryType.CONSUL:
            return {
                "type": "consul",
                "config": {
                    "host": self.consul.host,
                    "port": self.consul.port,
                    "scheme": self.consul.scheme,
                    "token": self.consul.token,
                    "datacenter": self.consul.datacenter,
                    "verify_ssl": self.consul.verify_ssl,
                    "timeout": self.consul.timeout,
                    "session_ttl": self.consul.session_ttl,
                    "enable_sessions": self.consul.enable_sessions,
                },
            }
        elif self.registry_type == RegistryType.ETCD:
            return {
                "type": "etcd",
                "config": {
                    "host": self.etcd.host,
                    "port": self.etcd.port,
                    "ca_cert": self.etcd.ca_cert,
                    "cert_key": self.etcd.cert_key,
                    "cert_cert": self.etcd.cert_cert,
                    "user": self.etcd.user,
                    "password": self.etcd.password,
                    "timeout": self.etcd.timeout,
                    "lease_ttl": self.etcd.lease_ttl,
                    "key_prefix": self.etcd.key_prefix,
                },
            }
        elif self.registry_type == RegistryType.KUBERNETES:
            return {
                "type": "kubernetes",
                "config": {
                    "namespace": self.kubernetes.namespace,
                    "kubeconfig_path": self.kubernetes.kubeconfig_path,
                    "in_cluster": self.kubernetes.in_cluster,
                    "api_server_url": self.kubernetes.api_server_url,
                    "token": self.kubernetes.token,
                    "ca_cert_path": self.kubernetes.ca_cert_path,
                    "watch_endpoints": self.kubernetes.watch_endpoints,
                    "watch_services": self.kubernetes.watch_services,
                },
            }
        else:
            return {"type": "memory", "config": {}}


# Predefined configurations for different environments
def create_development_config() -> ServiceDiscoveryConfig:
    """Create development environment configuration."""
    return ServiceDiscoveryConfig(
        environment="development",
        registry_type=RegistryType.CONSUL,
        consul=ConsulConfig(host="localhost", port=8500, check_interval="10s"),
        health_check=HealthCheckConfig(interval=10, timeout=5),
        discovery=DiscoveryConfig(refresh_interval=30, cache_ttl=60),
        monitoring=MonitoringConfig(log_level="DEBUG", log_health_checks=True),
    )


def create_production_config() -> ServiceDiscoveryConfig:
    """Create production environment configuration."""
    return ServiceDiscoveryConfig(
        environment="production",
        registry_type=RegistryType.CONSUL,
        consul=ConsulConfig(
            host="consul.internal",
            port=8500,
            token="${CONSUL_TOKEN}",
            verify_ssl=True,
            session_ttl=30,
            check_interval="30s",
            deregister_critical_after="5m",
        ),
        health_check=HealthCheckConfig(interval=30, timeout=10, failure_threshold=5),
        load_balancing=LoadBalancingConfig(
            strategy=LoadBalancingStrategy.HEALTH_BASED, circuit_breaker_enabled=True
        ),
        discovery=DiscoveryConfig(
            refresh_interval=60, cache_ttl=300, background_refresh=True
        ),
        monitoring=MonitoringConfig(
            metrics_enabled=True,
            tracing_enabled=True,
            jaeger_endpoint="http://jaeger:14268/api/traces",
            log_level="INFO",
            alerting_enabled=True,
        ),
        security=SecurityConfig(
            tls_enabled=True, api_key_enabled=True, jwt_enabled=True
        ),
        cluster_enabled=True,
        failover_enabled=True,
    )


def create_kubernetes_config() -> ServiceDiscoveryConfig:
    """Create Kubernetes environment configuration."""
    return ServiceDiscoveryConfig(
        environment="kubernetes",
        registry_type=RegistryType.KUBERNETES,
        kubernetes=KubernetesConfig(
            namespace="marty-framework",
            in_cluster=True,
            watch_endpoints=True,
            watch_services=True,
        ),
        health_check=HealthCheckConfig(
            strategy=HealthCheckStrategy.HTTP, http_path="/health"
        ),
        load_balancing=LoadBalancingConfig(
            strategy=LoadBalancingStrategy.ROUND_ROBIN, health_check_enabled=True
        ),
        monitoring=MonitoringConfig(metrics_enabled=True, log_level="INFO"),
    )


def load_service_discovery_config(
    environment: str = "development",
) -> ServiceDiscoveryConfig:
    """Load service discovery configuration for the specified environment."""
    if environment == "development":
        return create_development_config()
    elif environment == "production":
        return create_production_config()
    elif environment == "kubernetes":
        return create_kubernetes_config()
    else:
        return create_development_config()
