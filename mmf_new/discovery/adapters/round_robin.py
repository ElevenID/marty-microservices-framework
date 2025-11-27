"""
Round Robin Load Balancer Adapter

Implementation of round-robin load balancing strategy.
"""

import hashlib

from mmf_new.discovery.adapters.base_load_balancer import BaseLoadBalancer
from mmf_new.discovery.domain.models import ServiceInstance
from mmf_new.discovery.ports.load_balancer import (
    LoadBalancingConfig,
    LoadBalancingContext,
    StickySessionType,
)


class RoundRobinBalancer(BaseLoadBalancer):
    """Round-robin load balancer."""

    def __init__(self, config: LoadBalancingConfig):
        super().__init__(config)
        self._current_index = 0

    async def select_instance(
        self, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Select next instance in round-robin order."""
        if not self._instances:
            return None

        # Handle sticky sessions
        if context and self.config.sticky_sessions != StickySessionType.NONE:
            sticky_instance = await self._get_sticky_instance(context)
            if sticky_instance:
                return sticky_instance

        # Select next instance
        instance = self._instances[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._instances)

        return instance

    async def _get_sticky_instance(self, context: LoadBalancingContext) -> ServiceInstance | None:
        """Get instance based on sticky session configuration."""
        if self.config.sticky_sessions == StickySessionType.SOURCE_IP and context.client_ip:
            # Hash client IP to instance
            hash_value = hashlib.sha256(context.client_ip.encode()).hexdigest()
            index = int(hash_value, 16) % len(self._instances)
            return self._instances[index]

        if self.config.sticky_sessions == StickySessionType.COOKIE and context.session_id:
            # Hash session ID to instance
            hash_value = hashlib.sha256(context.session_id.encode()).hexdigest()
            index = int(hash_value, 16) % len(self._instances)
            return self._instances[index]

        return None
