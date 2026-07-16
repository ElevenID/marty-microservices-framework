"""
Discovery Service

Orchestrates service registration, discovery, and load balancing.
"""

import logging

from mmf.discovery.domain.models import ServiceInstance, ServiceQuery
from mmf.discovery.ports.load_balancer import ILoadBalancer, LoadBalancingContext
from mmf.discovery.ports.registry import IServiceRegistry

logger = logging.getLogger(__name__)


class DiscoveryService:
    """Service for managing service discovery and load balancing."""

    def __init__(self, registry: IServiceRegistry, load_balancer: ILoadBalancer):
        self.registry = registry
        self.load_balancer = load_balancer

    async def register_service(self, instance: ServiceInstance) -> bool:
        """Register a service instance."""
        return await self.registry.register(instance)

    async def deregister_service(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance."""
        return await self.registry.deregister(service_name, instance_id)

    async def discover_service(
        self, query: ServiceQuery, context: LoadBalancingContext | None = None
    ) -> ServiceInstance | None:
        """Discover and select a service instance."""
        # 1. Get instances from registry
        instances = await self.registry.discover(query.service_name)

        # 2. Filter by query
        filtered_instances = self._filter_instances(instances, query)

        if not filtered_instances:
            logger.warning("No instances found for service: %s", query.service_name)
            return None

        # 3. Update load balancer
        await self.load_balancer.update_instances(filtered_instances)

        # 4. Select instance
        return await self.load_balancer.select_instance(context)

    def _filter_instances(
        self, instances: list[ServiceInstance], query: ServiceQuery
    ) -> list[ServiceInstance]:
        """Filter instances based on query parameters."""
        filtered = instances

        if query.version:
            filtered = [i for i in filtered if i.metadata.version == query.version]

        if query.environment:
            filtered = [i for i in filtered if i.metadata.environment == query.environment]

        if query.region:
            filtered = [i for i in filtered if i.metadata.region == query.region]

        if query.zone:
            filtered = [i for i in filtered if i.metadata.availability_zone == query.zone]

        # Filter by tags
        for key, value in query.tags.items():
            filtered = [i for i in filtered if i.metadata.has_tag(f"{key}={value}")]

        # Filter by labels
        for key, value in query.labels.items():
            filtered = [i for i in filtered if i.metadata.get_label(key) == value]

        return filtered
