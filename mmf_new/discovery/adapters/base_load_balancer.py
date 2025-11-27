"""
Base Load Balancer Adapter

Common implementation for load balancers.
"""

import time
from typing import Any

from mmf_new.discovery.domain.models import ServiceInstance
from mmf_new.discovery.ports.load_balancer import ILoadBalancer, LoadBalancingConfig


class BaseLoadBalancer(ILoadBalancer):
    """Base load balancer implementation with common logic."""

    def __init__(self, config: LoadBalancingConfig):
        self.config = config
        self._instances: list[ServiceInstance] = []
        self._last_update = 0.0

        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "instance_selections": {},
            "strategy_switches": 0,
        }

    async def update_instances(self, instances: list[ServiceInstance]) -> None:
        """Update the list of available instances."""
        # Filter healthy instances if health checking is enabled
        if self.config.health_check_enabled:
            instances = [instance for instance in instances if instance.is_healthy()]

        self._instances = instances
        self._last_update = time.time()

        # Reset selection counters for new instances
        for instance in instances:
            if instance.instance_id not in self._stats["instance_selections"]:
                self._stats["instance_selections"][instance.instance_id] = 0

    def record_request(
        self, instance: ServiceInstance, success: bool, response_time: float
    ) -> None:
        """Record request result for metrics."""
        self._stats["total_requests"] += 1

        if success:
            self._stats["successful_requests"] += 1
        else:
            self._stats["failed_requests"] += 1

        self._stats["total_response_time"] += response_time

        # Initialize if not present (though update_instances should handle it)
        if instance.instance_id not in self._stats["instance_selections"]:
            self._stats["instance_selections"][instance.instance_id] = 0

        self._stats["instance_selections"][instance.instance_id] += 1

        # Update instance statistics
        instance.record_request(response_time, success)

    def get_stats(self) -> dict[str, Any]:
        """Get load balancer statistics."""
        avg_response_time = 0.0
        if self._stats["total_requests"] > 0:
            avg_response_time = self._stats["total_response_time"] / self._stats["total_requests"]

        success_rate = 0.0
        if self._stats["total_requests"] > 0:
            success_rate = self._stats["successful_requests"] / self._stats["total_requests"]

        return {
            **self._stats,
            "average_response_time": avg_response_time,
            "success_rate": success_rate,
            "instance_count": len(self._instances),
            "healthy_instances": len([i for i in self._instances if i.is_healthy()]),
            "last_update": self._last_update,
        }
