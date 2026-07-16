"""
Load Balancing Domain Models and Logic.
"""

import builtins
import hashlib
import logging
import random
import threading
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import ServiceInstance

logger = logging.getLogger(__name__)


class TrafficPolicy(Enum):
    """Traffic management policies."""

    ROUND_ROBIN = "round_robin"
    LEAST_CONN = "least_conn"
    RANDOM = "random"
    CONSISTENT_HASH = "consistent_hash"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LOCALITY_AWARE = "locality_aware"


@dataclass
class LoadBalancingConfig:
    """Load balancing configuration."""

    policy: TrafficPolicy = TrafficPolicy.ROUND_ROBIN
    hash_policy: builtins.dict[str, Any] | None = None
    locality_lb_setting: builtins.dict[str, Any] | None = None


class LoadBalancer:
    """Load balancer for service instances."""

    def __init__(self, config: LoadBalancingConfig):
        """Initialize load balancer."""
        self.config = config
        self.round_robin_counters: builtins.dict[str, int] = defaultdict(int)
        self.lock = threading.RLock()

    def select_instance(
        self,
        service_name: str,
        instances: builtins.list[ServiceInstance],
        request_context: builtins.dict[str, Any] | None = None,
    ) -> ServiceInstance | None:
        """Select an instance using the configured load balancing policy."""
        if not instances:
            return None

        if len(instances) == 1:
            return instances[0]

        policy = self.config.policy

        if policy == TrafficPolicy.ROUND_ROBIN:
            return self._round_robin_select(service_name, instances)
        elif policy == TrafficPolicy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select(instances)
        elif policy == TrafficPolicy.LEAST_CONN:
            return self._least_connections_select(instances)
        elif policy == TrafficPolicy.RANDOM:
            return self._random_select(instances)
        elif policy == TrafficPolicy.CONSISTENT_HASH:
            return self._consistent_hash_select(instances, request_context)
        elif policy == TrafficPolicy.LOCALITY_AWARE:
            return self._locality_aware_select(instances, request_context)
        else:
            # Default to round robin
            return self._round_robin_select(service_name, instances)

    def _round_robin_select(
        self, service_name: str, instances: builtins.list[ServiceInstance]
    ) -> ServiceInstance:
        """Round robin selection."""
        with self.lock:
            counter = self.round_robin_counters[service_name]
            selected_instance = instances[counter % len(instances)]
            self.round_robin_counters[service_name] = (counter + 1) % len(instances)
            return selected_instance

    def _weighted_round_robin_select(
        self, instances: builtins.list[ServiceInstance]
    ) -> ServiceInstance:
        """Weighted round robin selection."""
        total_weight = sum(instance.metadata.weight for instance in instances)
        if total_weight == 0:
            return random.choice(instances)

        # Use a simple weighted random selection
        rand_weight = random.randint(1, total_weight)
        cumulative_weight = 0

        for instance in instances:
            cumulative_weight += instance.metadata.weight
            if rand_weight <= cumulative_weight:
                return instance

        return instances[-1]  # Fallback

    def _least_connections_select(
        self, instances: builtins.list[ServiceInstance]
    ) -> ServiceInstance:
        """Least connections selection."""
        min_connections = float("inf")
        selected_instance = instances[0]

        for instance in instances:
            connections = instance.active_connections
            if connections < min_connections:
                min_connections = connections
                selected_instance = instance

        return selected_instance

    def _random_select(self, instances: builtins.list[ServiceInstance]) -> ServiceInstance:
        """Random selection."""
        return random.choice(instances)

    def _consistent_hash_select(
        self,
        instances: builtins.list[ServiceInstance],
        request_context: builtins.dict[str, Any] | None,
    ) -> ServiceInstance:
        """Consistent hash selection."""
        if not request_context or not self.config.hash_policy:
            return self._random_select(instances)

        # Build hash key from request context
        hash_parts = []
        for key in self.config.hash_policy.get("hash_on", []):
            if key in request_context:
                hash_parts.append(str(request_context[key]))

        if not hash_parts:
            return self._random_select(instances)

        hash_key = "|".join(hash_parts)
        hash_value = int(hashlib.sha256(hash_key.encode()).hexdigest(), 16)

        return instances[hash_value % len(instances)]

    def _locality_aware_select(
        self,
        instances: builtins.list[ServiceInstance],
        request_context: builtins.dict[str, Any] | None,
    ) -> ServiceInstance:
        """Locality-aware selection."""
        if not request_context:
            return self._round_robin_select("default", instances)

        # Prefer instances in the same region/zone
        client_region = request_context.get("region", "default")
        client_zone = request_context.get("zone", "default")

        # First try same zone
        same_zone_instances = [
            inst
            for inst in instances
            if inst.metadata.region == client_region
            and inst.metadata.availability_zone == client_zone
        ]
        if same_zone_instances:
            return self._round_robin_select("same_zone", same_zone_instances)

        # Then try same region
        same_region_instances = [
            inst for inst in instances if inst.metadata.region == client_region
        ]
        if same_region_instances:
            return self._round_robin_select("same_region", same_region_instances)

        # Fall back to any instance
        return self._round_robin_select("any", instances)
