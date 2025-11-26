"""
Traffic Manager Port.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional

from mmf_new.framework.mesh.domain.models import TrafficRule
from mmf_new.discovery.domain.models import ServiceInstance


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
    ) -> Optional[ServiceInstance]:
        """Route a request to a service instance."""
