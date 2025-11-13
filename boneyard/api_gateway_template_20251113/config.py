"""
API Gateway Service Configuration

Environment-specific configuration for the API Gateway service with support for:
- Service discovery backends
- Load balancing strategies
- Circuit breaker settings
- Rate limiting configuration
- Authentication providers
- Route definitions
"""

import builtins
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, list


class GatewayEnvironment(Enum):
    """Gateway deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ServiceDiscoveryType(Enum):
    """Service discovery backend types."""

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


@dataclass
class ServiceDiscoveryConfig:
    """Service discovery configuration."""

    type: ServiceDiscoveryType = ServiceDiscoveryType.CONSUL
    consul_host: str = "localhost"
    consul_port: int = 8500
    consul_token: str | None = None
    etcd_host: str = "localhost"
    etcd_port: int = 2379
    kubernetes_namespace: str = "default"
    health_check_interval: int = 30
    service_ttl: int = 60


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    timeout_seconds: int = 30
    half_open_max_calls: int = 3
    min_request_threshold: int = 20
    failure_rate_threshold: float = 0.5


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    requests_per_second: float = 100.0
    burst_size: int = 200
    window_size: int = 60
    enable_per_ip: bool = True
    enable_per_user: bool = True


@dataclass
class AuthenticationConfig:
    """Authentication configuration."""

    jwt_secret: str = "your-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600
    api_key_header: str = "X-API-Key"
    oauth2_provider_url: str | None = None
    oauth2_client_id: str | None = None
    oauth2_client_secret: str | None = None


@dataclass
class CachingConfig:
    """Response caching configuration."""

    enabled: bool = True
    default_ttl: int = 300
    max_size: int = 10000
    redis_host: str | None = None
    redis_port: int = 6379
    redis_db: int = 0


@dataclass
class RouteDefinition:
    """Route definition configuration."""

    name: str
    path_pattern: str
    target_service: str
    methods: builtins.list[str] = field(default_factory=lambda: ["GET"])
    require_auth: bool = True
    rate_limit: RateLimitConfig | None = None
    circuit_breaker: CircuitBreakerConfig | None = None
    load_balancing: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    enable_caching: bool = False
    cache_ttl: int = 300
    priority: int = 100
    timeout: int = 30
    retries: int = 3
    tags: builtins.list[str] = field(default_factory=list)


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""

    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = True
    jaeger_endpoint: str | None = None
    enable_logging: bool = True
    log_level: str = "INFO"
    log_format: str = "json"


@dataclass
class GatewayConfig:
    """Main API Gateway configuration."""

    # Basic settings
    environment: GatewayEnvironment = GatewayEnvironment.DEVELOPMENT
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1

    # Core components
    service_discovery: ServiceDiscoveryConfig = field(
        default_factory=ServiceDiscoveryConfig
    )
    authentication: AuthenticationConfig = field(default_factory=AuthenticationConfig)
    caching: CachingConfig = field(default_factory=CachingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # Default policies
    default_circuit_breaker: CircuitBreakerConfig = field(
        default_factory=CircuitBreakerConfig
    )
    default_rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    # Routes
    routes: builtins.list[RouteDefinition] = field(default_factory=list)

    # Advanced settings
    max_concurrent_requests: int = 1000
    default_timeout: int = 30
    enable_cors: bool = True
    cors_origins: builtins.list[str] = field(default_factory=lambda: ["*"])
    enable_compression: bool = True

    # Security
    enable_security_headers: bool = True
    enable_request_validation: bool = True
    max_request_size: int = 10485760  # 10MB

    def get_environment_config(self) -> builtins.dict[str, Any]:
        """Get environment-specific configuration."""
        base_config = {
            "service_discovery": {
                "type": self.service_discovery.type.value,
                "health_check_interval": self.service_discovery.health_check_interval,
                "service_ttl": self.service_discovery.service_ttl,
            },
            "monitoring": {
                "enable_metrics": self.monitoring.enable_metrics,
                "enable_tracing": self.monitoring.enable_tracing,
                "log_level": self.monitoring.log_level,
            },
        }

        if self.environment == GatewayEnvironment.DEVELOPMENT:
            return {
                **base_config,
                "service_discovery": {
                    **base_config["service_discovery"],
                    "consul_host": "localhost",
                    "consul_port": 8500,
                },
                "authentication": {
                    "jwt_secret": "dev-secret-key",
                    "jwt_expiration": 7200,
                },
                "monitoring": {**base_config["monitoring"], "log_level": "DEBUG"},
            }

        elif self.environment == GatewayEnvironment.PRODUCTION:
            return {
                **base_config,
                "service_discovery": {
                    **base_config["service_discovery"],
                    "consul_host": "consul.internal",
                    "consul_port": 8500,
                    "health_check_interval": 15,
                },
                "authentication": {
                    "jwt_secret": "${JWT_SECRET}",
                    "jwt_expiration": 3600,
                },
                "monitoring": {
                    **base_config["monitoring"],
                    "log_level": "INFO",
                    "jaeger_endpoint": "http://jaeger:14268/api/traces",
                },
            }

        return base_config


# Predefined route configurations
DEFAULT_ROUTES = [
    RouteDefinition(
        name="user_service_v1",
        path_pattern="/api/v1/users/**",
        target_service="user-service",
        methods=["GET", "POST", "PUT", "DELETE"],
        require_auth=True,
        rate_limit=RateLimitConfig(requests_per_second=100),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=5),
        enable_caching=True,
        cache_ttl=300,
        priority=100,
        tags=["user", "v1", "crud"],
    ),
    RouteDefinition(
        name="order_service_v1",
        path_pattern="/api/v1/orders/**",
        target_service="order-service",
        methods=["GET", "POST", "PUT"],
        require_auth=True,
        rate_limit=RateLimitConfig(requests_per_second=50),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=3),
        load_balancing=LoadBalancingStrategy.LEAST_CONNECTIONS,
        priority=90,
        tags=["order", "v1", "business"],
    ),
    RouteDefinition(
        name="product_catalog_public",
        path_pattern="/api/v1/products/**",
        target_service="product-service",
        methods=["GET"],
        require_auth=False,
        rate_limit=RateLimitConfig(requests_per_second=200),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=10),
        enable_caching=True,
        cache_ttl=600,
        priority=80,
        tags=["product", "v1", "public"],
    ),
    RouteDefinition(
        name="health_check",
        path_pattern="/health/**",
        target_service="health-service",
        methods=["GET"],
        require_auth=False,
        priority=200,
        tags=["health", "monitoring"],
    ),
    RouteDefinition(
        name="admin_api",
        path_pattern="/admin/**",
        target_service="admin-service",
        methods=["GET", "POST", "PUT", "DELETE"],
        require_auth=True,
        rate_limit=RateLimitConfig(requests_per_second=10),
        circuit_breaker=CircuitBreakerConfig(failure_threshold=2),
        priority=150,
        tags=["admin", "management"],
    ),
]


def create_development_config() -> GatewayConfig:
    """Create development environment configuration."""
    return GatewayConfig(
        environment=GatewayEnvironment.DEVELOPMENT,
        routes=DEFAULT_ROUTES,
        service_discovery=ServiceDiscoveryConfig(
            type=ServiceDiscoveryType.CONSUL, consul_host="localhost", consul_port=8500
        ),
        authentication=AuthenticationConfig(
            jwt_secret="dev-secret-key", jwt_expiration=7200
        ),
        monitoring=MonitoringConfig(log_level="DEBUG", enable_tracing=False),
    )


def create_production_config() -> GatewayConfig:
    """Create production environment configuration."""
    return GatewayConfig(
        environment=GatewayEnvironment.PRODUCTION,
        routes=DEFAULT_ROUTES,
        workers=4,
        service_discovery=ServiceDiscoveryConfig(
            type=ServiceDiscoveryType.CONSUL,
            consul_host="consul.internal",
            consul_port=8500,
            health_check_interval=15,
        ),
        authentication=AuthenticationConfig(
            jwt_secret="${JWT_SECRET}", jwt_expiration=3600
        ),
        monitoring=MonitoringConfig(
            log_level="INFO",
            enable_tracing=True,
            jaeger_endpoint="http://jaeger:14268/api/traces",
        ),
        cors_origins=["https://app.example.com", "https://admin.example.com"],
        max_concurrent_requests=5000,
    )


def load_gateway_config(environment: str = "development") -> GatewayConfig:
    """Load gateway configuration for the specified environment."""
    if environment == "development":
        return create_development_config()
    elif environment == "production":
        return create_production_config()
    else:
        # Default to development
        return create_development_config()
