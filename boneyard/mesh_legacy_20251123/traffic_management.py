"""
Traffic Management for Marty Microservices Framework

This module implements traffic management including routing rules,
traffic policies, and request routing.
"""

import builtins
import logging
from dataclasses import dataclass, field
from typing import Any

# Import from current package
from .service_mesh import (
    LoadBalancingConfig,
    ServiceEndpoint,
    TrafficPolicy,
    TrafficRule,
)


@dataclass
class RouteMatch:
    """Route matching criteria."""

    headers: builtins.dict[str, str] = field(default_factory=dict)
    path_prefix: str = ""
    path_exact: str = ""
    path_regex: str = ""
    method: str = ""
    query_params: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class RouteDestination:
    """Route destination configuration."""

    service_name: str
    weight: int = 100
    headers_to_add: builtins.dict[str, str] = field(default_factory=dict)
    headers_to_remove: builtins.list[str] = field(default_factory=list)


class TrafficSplitter:
    """Simple traffic splitter implementation."""

    def __init__(self):
        """Initialize traffic splitter."""
        self.split_rules: builtins.dict[str, builtins.dict[str, int]] = {}

    def select_version_endpoints(
        self, service_name: str, available_endpoints: builtins.list[ServiceEndpoint]
    ) -> builtins.list[ServiceEndpoint]:
        """Select endpoints based on version."""
        return available_endpoints  # Simplified implementation


class TrafficManager:
    """Manages traffic routing and policies."""

    def __init__(self):
        """Initialize traffic manager."""
        self.routing_rules: builtins.dict[str, builtins.list[TrafficRule]] = {}
        # Create a default load balancing config
        self.lb_config = LoadBalancingConfig(policy=TrafficPolicy.ROUND_ROBIN)
        self.traffic_splitter = TrafficSplitter()

    def add_routing_rule(self, service_name: str, rule: TrafficRule):
        """Add routing rule for a service."""
        if service_name not in self.routing_rules:
            self.routing_rules[service_name] = []

        self.routing_rules[service_name].append(rule)
        logging.info("Added routing rule %s for service %s", rule.rule_id, service_name)

    def remove_routing_rule(self, service_name: str, rule_id: str):
        """Remove routing rule."""
        if service_name in self.routing_rules:
            self.routing_rules[service_name] = [
                rule for rule in self.routing_rules[service_name] if rule.rule_id != rule_id
            ]

    def route_request(
        self,
        service_name: str,
        request_context: builtins.dict[str, Any],
        available_endpoints: builtins.list[ServiceEndpoint],
    ) -> ServiceEndpoint | None:
        """Route request based on rules and load balancing."""
        # Apply traffic splitting first
        endpoints = self.traffic_splitter.select_version_endpoints(
            service_name, available_endpoints
        )

        if not endpoints:
            return None

        # Apply routing rules
        matching_rules = self._find_matching_rules(service_name, request_context)

        if matching_rules:
            # Use first matching rule for simplified implementation
            logging.debug("Applied routing rule: %s", matching_rules[0].rule_id)

        # Simple endpoint selection (would integrate with load balancer)
        return endpoints[0] if endpoints else None

    def _find_matching_rules(
        self, service_name: str, request_context: builtins.dict[str, Any]
    ) -> builtins.list[TrafficRule]:
        """Find matching routing rules for request."""
        if service_name not in self.routing_rules:
            return []

        matching_rules = []
        for rule in self.routing_rules[service_name]:
            if self._rule_matches(rule, request_context):
                matching_rules.append(rule)

        return matching_rules

    def _rule_matches(self, rule: TrafficRule, request_context: builtins.dict[str, Any]) -> bool:
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

    def get_traffic_statistics(self) -> builtins.dict[str, Any]:
        """Get traffic management statistics."""
        return {
            "routing_rules": {service: len(rules) for service, rules in self.routing_rules.items()},
            "traffic_split_rules": self.traffic_splitter.split_rules,
        }
