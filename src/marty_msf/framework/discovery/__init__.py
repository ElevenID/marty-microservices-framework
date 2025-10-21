"""
Service Discovery & Load Balancing Framework

Enterprise-grade service discovery and load balancing framework providing
dynamic service registration, health monitoring, intelligent routing,
and adaptive load balancing strategies.

Key Components:
- Service Registry: Central registry for service instances with metadata
- Health Monitoring: Continuous health checks and availability tracking
- Load Balancing: Multiple algorithms (round-robin, weighted, least-connections, etc.)
- Service Discovery: Client-side and server-side discovery patterns
- Circuit Breaker Integration: Fault tolerance with circuit breaker patterns
- Dynamic Configuration: Runtime updates and adaptive behaviors
- Metrics & Monitoring: Comprehensive observability and performance tracking

Usage:
    from marty_msf.framework.discovery import ServiceRegistry, LoadBalancer
    from marty_msf.framework.discovery import ServiceInstance, HealthCheck, LoadBalancingStrategy

    # Create service registry
    registry = ServiceRegistry()

    # Register service instance
    instance = ServiceInstance(
        name="user-service",
        host="localhost",
        port=8080,
        health_check_url="/health"
    )
    await registry.register(instance)

    # Create load balancer
    load_balancer = LoadBalancer(
        strategy=LoadBalancingStrategy.ROUND_ROBIN,
        health_check_enabled=True
    )
"""

# Circuit breaker integration
from .circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerMetrics,
    CircuitBreakerState,
)

# Service discovery patterns
from .clients.base import ServiceDiscoveryClient
from .clients.client_side import ClientSideDiscovery
from .clients.server_side import ServerSideDiscovery
from .config import DiscoveryConfig, DiscoveryPattern

# Core service discovery components
from .core import (
    HealthCheck,
    HealthStatus,
    ServiceInstance,
    ServiceMetadata,
    ServiceRegistryConfig,
)

# Health monitoring and checks
from .health import (
    CustomHealthChecker,
    HealthCheckConfig,
    HealthChecker,
    HealthCheckResult,
    HealthCheckType,
    HealthMonitor,
    HTTPHealthChecker,
    TCPHealthChecker,
)

# Load balancing strategies and algorithms
from .load_balancing import (
    AdaptiveBalancer,
    ConsistentHashBalancer,
    HealthBasedBalancer,
    LeastConnectionsBalancer,
    LoadBalancer,
    LoadBalancingConfig,
    LoadBalancingStrategy,
    RandomBalancer,
    RoundRobinBalancer,
    WeightedLeastConnectionsBalancer,
    WeightedRoundRobinBalancer,
)

# Management and orchestration
from .manager import DiscoveryManagerConfig as ManagerConfig
from .manager import DiscoveryManagerState, ServiceDiscoveryManager

# Service mesh integration
from .mesh import ServiceMeshConfig, TrafficPolicy

# Monitoring and metrics
from .monitoring import (
    DiscoveryMetrics,
    LoadBalancingMetrics,
    MetricsCollector,
    ServiceMetrics,
)

# Service registry implementations
from .registry import (
    ConsulServiceRegistry,
    EtcdServiceRegistry,
    InMemoryServiceRegistry,
    KubernetesServiceRegistry,
    ServiceRegistry,
)

__all__ = [
    "AdaptiveBalancer",
    "CircuitBreakerConfig",
    "CircuitBreakerMetrics",
    "CircuitBreakerState",
    "ClientSideDiscovery",
    "ConsistentHashBalancer",
    "ConsulServiceRegistry",
    "CustomHealthChecker",
    "DiscoveryManagerState",
    # Monitoring
    "DiscoveryMetrics",
    "DiscoveryPattern",
    "EtcdServiceRegistry",
    "HTTPHealthChecker",
    "HealthBasedBalancer",
    "HealthCheck",
    "HealthCheckConfig",
    "HealthCheckResult",
    "HealthCheckType",
    "HealthChecker",
    # Health monitoring
    "HealthMonitor",
    "HealthStatus",
    "InMemoryServiceRegistry",
    "KubernetesServiceRegistry",
    "LeastConnectionsBalancer",
    # Load balancing
    "LoadBalancer",
    "LoadBalancingConfig",
    "LoadBalancingMetrics",
    "LoadBalancingStrategy",
    "ManagerConfig",
    "MetricsCollector",
    "RandomBalancer",
    "RoundRobinBalancer",
    "ServerSideDiscovery",
    # Circuit breaker
    "CircuitBreaker",
    # Service discovery
    "ServiceDiscoveryClient",
    "DiscoveryConfig",
    # Management
    "ServiceDiscoveryManager",
    # Core components
    "ServiceInstance",
    # Service mesh
    "ServiceMeshConfig",
    "ServiceMetadata",
    "ServiceMetrics",
    # Service registry
    "ServiceRegistry",
    "ServiceRegistryConfig",
    "TCPHealthChecker",
    "TrafficPolicy",
    "WeightedLeastConnectionsBalancer",
    "WeightedRoundRobinBalancer",
]
