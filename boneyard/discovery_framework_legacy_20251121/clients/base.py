from __future__ import annotations

"""
Abstract base for discovery clients.

Client implementations share statistics collection, cache integration, and load
balancer interaction. Extracting the base class keeps each concrete strategy
focused on its network concerns.
"""

import builtins
import random
from abc import ABC, abstractmethod
from typing import Any

from ..cache import ServiceCache
from ..config import DiscoveryConfig, ServiceQuery
from ..core import ServiceInstance
from ..load_balancing import (
    LoadBalancer,
    LoadBalancingConfig,
    LoadBalancingContext,
    create_load_balancer,
)
from ..results import DiscoveryResult


class ServiceDiscoveryClient(ABC):
    """Abstract service discovery client."""

    def __init__(self, config: DiscoveryConfig):
        self.config = config
        self.cache = ServiceCache(config)
        self._load_balancer: LoadBalancer | None = None

        if config.load_balancing_enabled:
            lb_config = config.load_balancing_config or LoadBalancingConfig()
            self._load_balancer = create_load_balancer(lb_config)

        self._stats = {
            "resolutions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "failures": 0,
            "average_resolution_time": 0.0,
            "total_resolution_time": 0.0,
        }

    @abstractmethod
    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover service instances."""

    async def resolve_service(
        self, query: ServiceQuery, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Resolve service to a single instance using load balancing."""
        result = await self.discover_instances(query)

        if not result.instances:
            return None

        if self._load_balancer:
            await self._load_balancer.update_instances(result.instances)
            selected = await self._load_balancer.select_with_fallback(context)

            if selected:
                result.selected_instance = selected
                result.load_balancer_used = True
                return selected

        return self._simple_instance_selection(result.instances, query)

    def _simple_instance_selection(
        self, instances: builtins.list[ServiceInstance], query: ServiceQuery
    ) -> ServiceInstance:
        """Simple instance selection without load balancer."""
        preferred_instances = instances

        if self.config.zone_aware and query.prefer_zone:
            zone_instances = [
                i for i in instances if i.metadata.availability_zone == query.prefer_zone
            ]
            if zone_instances:
                preferred_instances = zone_instances

        elif self.config.region_aware and query.prefer_region:
            region_instances = [i for i in instances if i.metadata.region == query.prefer_region]
            if region_instances:
                preferred_instances = region_instances

        if query.max_instances and len(preferred_instances) > query.max_instances:
            preferred_instances = preferred_instances[: query.max_instances]

        return random.choice(preferred_instances)

    def record_resolution(self, success: bool, resolution_time: float) -> None:
        """Record resolution statistics."""
        self._stats["resolutions"] += 1

        if success:
            self._stats["total_resolution_time"] += resolution_time
            self._stats["average_resolution_time"] = (
                self._stats["total_resolution_time"] / self._stats["resolutions"]
            )
        else:
            self._stats["failures"] += 1

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get discovery client statistics."""
        cache_stats = self.cache.get_stats()

        failure_rate = 0.0
        if self._stats["resolutions"] > 0:
            failure_rate = self._stats["failures"] / self._stats["resolutions"]

        stats = {**self._stats, "failure_rate": failure_rate, "cache": cache_stats}

        if self._load_balancer:
            stats["load_balancer"] = self._load_balancer.get_stats()

        return stats
