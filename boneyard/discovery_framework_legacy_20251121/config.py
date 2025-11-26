from __future__ import annotations

"""
Configuration primitives for the service discovery subsystem.

The original discovery module mixed configuration, caching utilities, and client
implementations in a single, monolithic file. This module now isolates the enums
and dataclasses that describe discovery behaviour so other components can depend
on them without pulling in unrelated logic.
"""

import builtins
from dataclasses import dataclass, field
from enum import Enum

from .core import HealthStatus, ServiceInstance
from .load_balancing import LoadBalancingConfig


class DiscoveryPattern(Enum):
    """Service discovery pattern types."""

    CLIENT_SIDE = "client_side"
    SERVER_SIDE = "server_side"
    HYBRID = "hybrid"
    SERVICE_MESH = "service_mesh"


class CacheStrategy(Enum):
    """Cache strategy types."""

    NONE = "none"
    TTL = "ttl"
    REFRESH_AHEAD = "refresh_ahead"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"


@dataclass
class DiscoveryConfig:
    """Configuration for service discovery."""

    # Discovery pattern
    pattern: DiscoveryPattern = DiscoveryPattern.CLIENT_SIDE

    # Service resolution
    service_resolution_timeout: float = 5.0
    max_resolution_retries: int = 3
    resolution_retry_delay: float = 1.0

    # Caching configuration
    cache_strategy: CacheStrategy = CacheStrategy.TTL
    cache_ttl: float = 300.0  # 5 minutes
    cache_max_size: int = 1000
    refresh_ahead_factor: float = 0.8  # Refresh when 80% of TTL elapsed

    # Health checking
    health_check_enabled: bool = True
    health_check_interval: float = 30.0
    health_check_timeout: float = 5.0

    # Failover configuration
    enable_failover: bool = True
    failover_timeout: float = 10.0
    backup_registries: builtins.list[str] = field(default_factory=list)

    # Load balancing
    load_balancing_enabled: bool = True
    load_balancing_config: LoadBalancingConfig | None = None

    # Metrics and monitoring
    enable_metrics: bool = True
    metrics_collection_interval: float = 60.0

    # Circuit breaker for registries
    registry_circuit_breaker_enabled: bool = True
    registry_failure_threshold: int = 5
    registry_recovery_timeout: float = 60.0

    # Zone and region awareness
    zone_aware: bool = False
    region_aware: bool = False
    prefer_local_zone: bool = True
    prefer_local_region: bool = True


@dataclass
class ServiceQuery:
    """Query parameters for service discovery."""

    service_name: str
    version: str | None = None
    environment: str | None = None
    zone: str | None = None
    region: str | None = None
    tags: builtins.dict[str, str] = field(default_factory=dict)
    labels: builtins.dict[str, str] = field(default_factory=dict)
    protocols: builtins.list[str] = field(default_factory=list)

    # Query options
    include_unhealthy: bool = False
    max_instances: int | None = None
    prefer_zone: str | None = None
    prefer_region: str | None = None
    exclude_instances: builtins.set[str] = field(default_factory=set)

    def matches_instance(self, instance: ServiceInstance) -> bool:
        """Check if instance matches query criteria."""

        # Check version
        if self.version and instance.metadata.version != self.version:
            return False

        # Check environment
        if self.environment and instance.metadata.environment != self.environment:
            return False

        # Check zone
        if self.zone and instance.metadata.availability_zone != self.zone:
            return False

        # Check region
        if self.region and instance.metadata.region != self.region:
            return False

        # Check health status
        if not self.include_unhealthy and instance.health_status != HealthStatus.HEALTHY:
            return False

        # Check tags
        if self.tags:
            for key, value in self.tags.items():
                if key not in instance.metadata.labels or instance.metadata.labels[key] != value:
                    return False

        # Check labels
        if self.labels:
            for key, value in self.labels.items():
                if key not in instance.metadata.labels or instance.metadata.labels[key] != value:
                    return False

        # Check protocols
        if self.protocols:
            instance_protocols = instance.metadata.labels.get("protocols", "").split(",")
            if not any(protocol in instance_protocols for protocol in self.protocols):
                return False

        return True
