"""
Load Balancing Implementation for Marty Microservices Framework

This module implements load balancing algorithms and traffic distribution
for service mesh orchestration.
"""

import builtins
import hashlib
import logging
import random
import threading
from collections import defaultdict
from typing import Any

from .service_mesh import LoadBalancingConfig, ServiceEndpoint, TrafficPolicy


class LoadBalancer:
    """Load balancer for service endpoints."""

    def __init__(self, config: LoadBalancingConfig):
        """Initialize load balancer."""
        self.config = config
        self.endpoint_stats: builtins.dict[str, builtins.dict[str, Any]] = defaultdict(
            lambda: {"connections": 0, "requests": 0, "errors": 0}
        )
        self.round_robin_counters: builtins.dict[str, int] = defaultdict(int)
        self.lock = threading.RLock()

    def select_endpoint(
        self,
        service_name: str,
        endpoints: builtins.list[ServiceEndpoint],
        request_context: builtins.dict[str, Any] | None = None,
    ) -> ServiceEndpoint | None:
        """Select an endpoint using the configured load balancing policy."""
        if not endpoints:
            return None

        if len(endpoints) == 1:
            return endpoints[0]

        policy = self.config.policy

        if policy == TrafficPolicy.ROUND_ROBIN:
            return self._round_robin_select(service_name, endpoints)
        elif policy == TrafficPolicy.WEIGHTED_ROUND_ROBIN:
            return self._weighted_round_robin_select(endpoints)
        elif policy == TrafficPolicy.LEAST_CONN:
            return self._least_connections_select(endpoints)
        elif policy == TrafficPolicy.RANDOM:
            return self._random_select(endpoints)
        elif policy == TrafficPolicy.CONSISTENT_HASH:
            return self._consistent_hash_select(endpoints, request_context)
        elif policy == TrafficPolicy.LOCALITY_AWARE:
            return self._locality_aware_select(endpoints, request_context)
        else:
            # Default to round robin
            return self._round_robin_select(service_name, endpoints)

    def _round_robin_select(
        self, service_name: str, endpoints: builtins.list[ServiceEndpoint]
    ) -> ServiceEndpoint:
        """Round robin selection."""
        with self.lock:
            counter = self.round_robin_counters[service_name]
            selected_endpoint = endpoints[counter % len(endpoints)]
            self.round_robin_counters[service_name] = (counter + 1) % len(endpoints)
            return selected_endpoint

    def _weighted_round_robin_select(
        self, endpoints: builtins.list[ServiceEndpoint]
    ) -> ServiceEndpoint:
        """Weighted round robin selection."""
        total_weight = sum(endpoint.weight for endpoint in endpoints)
        if total_weight == 0:
            return random.choice(endpoints)

        # Use a simple weighted random selection
        rand_weight = random.randint(1, total_weight)
        cumulative_weight = 0

        for endpoint in endpoints:
            cumulative_weight += endpoint.weight
            if rand_weight <= cumulative_weight:
                return endpoint

        return endpoints[-1]  # Fallback

    def _least_connections_select(
        self, endpoints: builtins.list[ServiceEndpoint]
    ) -> ServiceEndpoint:
        """Least connections selection."""
        min_connections = float("inf")
        selected_endpoint = endpoints[0]

        for endpoint in endpoints:
            endpoint_key = f"{endpoint.host}:{endpoint.port}"
            connections = self.endpoint_stats[endpoint_key]["connections"]

            if connections < min_connections:
                min_connections = connections
                selected_endpoint = endpoint

        return selected_endpoint

    def _random_select(self, endpoints: builtins.list[ServiceEndpoint]) -> ServiceEndpoint:
        """Random selection."""
        return random.choice(endpoints)

    def _consistent_hash_select(
        self,
        endpoints: builtins.list[ServiceEndpoint],
        request_context: builtins.dict[str, Any] | None,
    ) -> ServiceEndpoint:
        """Consistent hash selection."""
        if not request_context or not self.config.hash_policy:
            return self._random_select(endpoints)

        # Build hash key from request context
        hash_parts = []
        for key in self.config.hash_policy.get("hash_on", []):
            if key in request_context:
                hash_parts.append(str(request_context[key]))

        if not hash_parts:
            return self._random_select(endpoints)

        hash_key = "|".join(hash_parts)
        hash_value = int(hashlib.sha256(hash_key.encode()).hexdigest(), 16)

        return endpoints[hash_value % len(endpoints)]

    def _locality_aware_select(
        self,
        endpoints: builtins.list[ServiceEndpoint],
        request_context: builtins.dict[str, Any] | None,
    ) -> ServiceEndpoint:
        """Locality-aware selection."""
        if not request_context:
            return self._round_robin_select("default", endpoints)

        # Prefer endpoints in the same region/zone
        client_region = request_context.get("region", "default")
        client_zone = request_context.get("zone", "default")

        # First try same zone
        same_zone_endpoints = [
            ep for ep in endpoints if ep.region == client_region and ep.zone == client_zone
        ]
        if same_zone_endpoints:
            return self._round_robin_select("same_zone", same_zone_endpoints)

        # Then try same region
        same_region_endpoints = [ep for ep in endpoints if ep.region == client_region]
        if same_region_endpoints:
            return self._round_robin_select("same_region", same_region_endpoints)

        # Fall back to any endpoint
        return self._round_robin_select("any", endpoints)

    def record_request_start(self, endpoint: ServiceEndpoint):
        """Record the start of a request to an endpoint."""
        endpoint_key = f"{endpoint.host}:{endpoint.port}"
        with self.lock:
            self.endpoint_stats[endpoint_key]["connections"] += 1
            self.endpoint_stats[endpoint_key]["requests"] += 1

    def record_request_end(self, endpoint: ServiceEndpoint, success: bool = True):
        """Record the end of a request to an endpoint."""
        endpoint_key = f"{endpoint.host}:{endpoint.port}"
        with self.lock:
            self.endpoint_stats[endpoint_key]["connections"] -= 1
            if not success:
                self.endpoint_stats[endpoint_key]["errors"] += 1

    def get_endpoint_stats(self, endpoint: ServiceEndpoint) -> builtins.dict[str, Any]:
        """Get statistics for an endpoint."""
        endpoint_key = f"{endpoint.host}:{endpoint.port}"
        return self.endpoint_stats[endpoint_key].copy()

    def get_all_stats(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get statistics for all endpoints."""
        with self.lock:
            return {
                endpoint_key: stats.copy() for endpoint_key, stats in self.endpoint_stats.items()
            }

    def reset_stats(self):
        """Reset all endpoint statistics."""
        with self.lock:
            self.endpoint_stats.clear()
            self.round_robin_counters.clear()

        logging.info("Load balancer statistics reset")


class TrafficSplitter:
    """Splits traffic between different service versions."""

    def __init__(self):
        """Initialize traffic splitter."""
        self.split_rules: builtins.dict[str, builtins.list[builtins.dict[str, Any]]] = {}

    def add_split_rule(self, service_name: str, version_weights: builtins.dict[str, int]):
        """Add traffic split rule for a service."""
        total_weight = sum(version_weights.values())
        if total_weight == 0:
            raise ValueError("Total weight cannot be zero")

        rules = []
        cumulative_weight = 0

        for version, weight in version_weights.items():
            cumulative_weight += weight
            rules.append(
                {
                    "version": version,
                    "weight": weight,
                    "cumulative_percentage": (cumulative_weight * 100) // total_weight,
                }
            )

        self.split_rules[service_name] = rules

    def select_version_endpoints(
        self, service_name: str, all_endpoints: builtins.list[ServiceEndpoint]
    ) -> builtins.list[ServiceEndpoint]:
        """Select endpoints based on traffic split rules."""
        if service_name not in self.split_rules:
            return all_endpoints

        # Determine target version based on split rules
        rand_percentage = random.randint(1, 100)
        target_version = None

        for rule in self.split_rules[service_name]:
            if rand_percentage <= rule["cumulative_percentage"]:
                target_version = rule["version"]
                break

        if target_version is None:
            return all_endpoints

        # Filter endpoints by version
        version_endpoints = [ep for ep in all_endpoints if ep.version == target_version]

        return version_endpoints if version_endpoints else all_endpoints

    def remove_split_rule(self, service_name: str):
        """Remove traffic split rule."""
        self.split_rules.pop(service_name, None)

    def get_split_rules(self) -> builtins.dict[str, builtins.list[builtins.dict[str, Any]]]:
        """Get all traffic split rules."""
        return self.split_rules.copy()
