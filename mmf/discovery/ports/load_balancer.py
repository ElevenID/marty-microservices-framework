"""
Load Balancer Port

Defines the interface for load balancing strategies.
"""

import builtins
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mmf.discovery.domain.models import ServiceInstance


class LoadBalancingStrategy(Enum):
    """Load balancing strategy types."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED_LEAST_CONNECTIONS = "weighted_least_connections"
    RANDOM = "random"
    WEIGHTED_RANDOM = "weighted_random"
    CONSISTENT_HASH = "consistent_hash"
    IP_HASH = "ip_hash"
    HEALTH_BASED = "health_based"
    ADAPTIVE = "adaptive"
    CUSTOM = "custom"


class StickySessionType(Enum):
    """Sticky session types."""

    NONE = "none"
    SOURCE_IP = "source_ip"
    COOKIE = "cookie"
    HEADER = "header"
    CUSTOM = "custom"


@dataclass
class LoadBalancingConfig:
    """Configuration for load balancing."""

    # Strategy configuration
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN
    fallback_strategy: LoadBalancingStrategy = LoadBalancingStrategy.RANDOM

    # Health checking
    health_check_enabled: bool = True
    health_check_interval: float = 30.0
    unhealthy_threshold: int = 3
    healthy_threshold: int = 2

    # Sticky sessions
    sticky_sessions: StickySessionType = StickySessionType.NONE
    session_timeout: float = 3600.0  # 1 hour

    # Circuit breaker integration
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    circuit_breaker_half_open_max_calls: int = 3

    # Adaptive behavior
    adaptive_enabled: bool = False
    adaptive_window_size: int = 100
    adaptive_adjustment_factor: float = 0.1

    # Performance settings
    max_retries: int = 3
    retry_delay: float = 1.0
    connection_timeout: float = 5.0

    # Consistent hashing
    virtual_nodes: int = 150
    hash_function: str = "md5"  # md5, sha1, sha256

    # Monitoring
    enable_metrics: bool = True
    metrics_window_size: int = 1000


@dataclass
class LoadBalancingContext:
    """Context for load balancing decisions."""

    # Request information
    client_ip: str | None = None
    session_id: str | None = None
    request_headers: builtins.dict[str, str] = field(default_factory=dict)
    request_path: str | None = None
    request_method: str | None = None

    # Load balancing hints
    preferred_zone: str | None = None
    preferred_region: str | None = None
    exclude_instances: builtins.set[str] = field(default_factory=set)

    # Custom data
    custom_data: builtins.dict[str, Any] = field(default_factory=dict)


class ILoadBalancer(ABC):
    """Abstract load balancer interface."""

    @abstractmethod
    async def update_instances(self, instances: builtins.list[ServiceInstance]) -> None:
        """Update the list of available instances."""

    @abstractmethod
    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select an instance using the load balancing strategy."""

    @abstractmethod
    def record_request(
        self, instance: ServiceInstance, success: bool, response_time: float
    ) -> None:
        """Record request result for metrics."""

    @abstractmethod
    def get_stats(self) -> builtins.dict[str, Any]:
        """Get load balancer statistics."""
