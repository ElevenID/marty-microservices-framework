"""
Traffic Manager Port.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from mmf.discovery.domain.models import ServiceInstance
from mmf.framework.mesh.domain.models import TrafficRule


class TrafficManagerPort(ABC):
    """Interface for traffic management."""

    @abstractmethod
    def add_routing_rule(self, service_name: str, rule: TrafficRule) -> None:
        """Add a routing rule."""

    @abstractmethod
    def remove_routing_rule(self, service_name: str, rule_id: str) -> None:
        """Remove a routing rule."""

    @abstractmethod
    def route_request(
        self,
        service_name: str,
        request_context: dict[str, Any],
        available_instances: list[ServiceInstance],
    ) -> ServiceInstance | None:
        """Route a request to a service instance."""
