"""
Mesh Application Services.
"""

import logging
import random
from typing import Any

from mmf.discovery.domain.load_balancing import (
    LoadBalancer,
    LoadBalancingConfig,
    TrafficPolicy,
)
from mmf.discovery.domain.models import ServiceInstance
from mmf.framework.mesh.domain.models import TrafficRule
from mmf.framework.mesh.ports.lifecycle import MeshLifecyclePort
from mmf.framework.mesh.ports.traffic_manager import TrafficManagerPort

logger = logging.getLogger(__name__)


class TrafficSplitter:
    """Splits traffic between different service versions."""

    def __init__(self):
        """Initialize traffic splitter."""
        self.split_rules: dict[str, list[dict[str, Any]]] = {}

    def add_split_rule(self, service_name: str, version_weights: dict[str, int]):
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

    def select_version_instances(
        self, service_name: str, all_instances: list[ServiceInstance]
    ) -> list[ServiceInstance]:
        """Select instances based on traffic split rules."""
        if service_name not in self.split_rules:
            return all_instances

        # Determine target version based on split rules
        rand_percentage = random.randint(1, 100)
        target_version = None

        for rule in self.split_rules[service_name]:
            if rand_percentage <= rule["cumulative_percentage"]:
                target_version = rule["version"]
                break

        if target_version is None:
            return all_instances

        # Filter instances by version
        version_instances = [
            inst for inst in all_instances if inst.metadata.version == target_version
        ]

        return version_instances if version_instances else all_instances

    def remove_split_rule(self, service_name: str):
        """Remove traffic split rule."""
        self.split_rules.pop(service_name, None)

    def get_split_rules(self) -> dict[str, list[dict[str, Any]]]:
        """Get all traffic split rules."""
        return self.split_rules.copy()


class TrafficManager(TrafficManagerPort):
    """Manages traffic routing and policies."""

    def __init__(self):
        """Initialize traffic manager."""
        self.routing_rules: dict[str, list[TrafficRule]] = {}
        # Create a default load balancing config
        self.lb_config = LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN)
        self.load_balancer = LoadBalancer(self.lb_config)
        self.traffic_splitter = TrafficSplitter()

    def add_routing_rule(self, service_name: str, rule: TrafficRule) -> None:
        """Add routing rule for a service."""
        if service_name not in self.routing_rules:
            self.routing_rules[service_name] = []

        self.routing_rules[service_name].append(rule)
        logger.info("Added routing rule %s for service %s", rule.rule_id, service_name)

    def remove_routing_rule(self, service_name: str, rule_id: str) -> None:
        """Remove routing rule."""
        if service_name in self.routing_rules:
            self.routing_rules[service_name] = [
                rule for rule in self.routing_rules[service_name] if rule.rule_id != rule_id
            ]

    def route_request(
        self,
        service_name: str,
        request_context: dict[str, Any],
        available_instances: list[ServiceInstance],
    ) -> ServiceInstance | None:
        """Route request based on rules and load balancing."""
        # Apply traffic splitting first
        instances = self.traffic_splitter.select_version_instances(
            service_name, available_instances
        )

        if not instances:
            return None

        # Apply routing rules
        matching_rules = self._find_matching_rules(service_name, request_context)

        if matching_rules:
            # Use first matching rule for simplified implementation
            logger.debug("Applied routing rule: %s", matching_rules[0].rule_id)
            # In a real implementation, we would use destination_rules to filter instances
            # or modify request headers. For now, we just log it.

        # Use load balancer to select instance
        return self.load_balancer.select_instance(service_name, instances, request_context)

    def _find_matching_rules(
        self, service_name: str, request_context: dict[str, Any]
    ) -> list[TrafficRule]:
        """Find matching routing rules for request."""
        if service_name not in self.routing_rules:
            return []

        matching_rules = []
        for rule in self.routing_rules[service_name]:
            if self._rule_matches(rule, request_context):
                matching_rules.append(rule)

        return matching_rules

    def _rule_matches(self, rule: TrafficRule, request_context: dict[str, Any]) -> bool:
        """Check if rule matches request context."""
        # Simplified matching logic
        for condition in rule.match_conditions:
            # Check headers
            if "headers" in condition:
                for header, value in condition["headers"].items():
                    if request_context.get("headers", {}).get(header) != value:
                        return False

            # Check path
            if "path" in condition:
                request_path = request_context.get("path", "")
                if condition["path"] != request_path:
                    return False

        return True

    def get_traffic_statistics(self) -> dict[str, Any]:
        """Get traffic management statistics."""
        return {
            "routing_rules": {service: len(rules) for service, rules in self.routing_rules.items()},
            "traffic_split_rules": self.traffic_splitter.split_rules,
        }


class MeshManager:
    """Manages service mesh lifecycle."""

    def __init__(self, lifecycle_port: MeshLifecyclePort):
        """Initialize mesh manager."""
        self.lifecycle = lifecycle_port

    async def deploy(
        self, namespace: str = "default", config: dict[str, Any] | None = None
    ) -> bool:
        """Deploy service mesh."""
        if not await self.lifecycle.verify_prerequisites():
            logger.error("Prerequisites not met")
            return False

        if not await self.lifecycle.check_installation():
            logger.error("Service mesh CLI not installed")
            return False

        return await self.lifecycle.deploy(namespace, config)

    async def get_status(self) -> dict[str, Any]:
        """Get service mesh status."""
        return await self.lifecycle.get_status()

    async def generate_deployment_script(
        self, service_name: str, config: dict[str, Any] | None = None
    ) -> str:
        """Generate deployment script."""
        return await self.lifecycle.generate_deployment_script(service_name, config)
