"""
Service Registry Port

Defines the interface for service registry implementations.
"""

import builtins
from abc import ABC, abstractmethod

from mmf_new.discovery.domain.models import ServiceInstance, HealthStatus


class IServiceRegistry(ABC):
    """Abstract service registry interface."""

    @abstractmethod
    async def register(self, instance: ServiceInstance) -> bool:
        """Register a service instance."""

    @abstractmethod
    async def deregister(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance."""

    @abstractmethod
    async def discover(self, service_name: str) -> builtins.list[ServiceInstance]:
        """Discover all instances of a service."""

    @abstractmethod
    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance."""

    @abstractmethod
    async def update_instance(self, instance: ServiceInstance) -> bool:
        """Update a service instance."""

    @abstractmethod
    async def list_services(self) -> builtins.list[str]:
        """List all registered services."""

    @abstractmethod
    async def get_healthy_instances(self, service_name: str) -> builtins.list[ServiceInstance]:
        """Get healthy instances of a service."""

    @abstractmethod
    async def update_health_status(
        self, service_name: str, instance_id: str, status: HealthStatus
    ) -> bool:
        """Update health status of an instance."""
