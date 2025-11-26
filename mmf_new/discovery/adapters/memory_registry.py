"""
In-Memory Service Registry Adapter

Implementation of IServiceRegistry using in-memory storage.
"""

import asyncio
import logging
import time

from mmf_new.discovery.domain.models import (
    ServiceInstance,
    HealthStatus,
    ServiceStatus,
    ServiceRegistryConfig,
)
from mmf_new.discovery.ports.registry import IServiceRegistry

logger = logging.getLogger(__name__)


class MemoryRegistry(IServiceRegistry):
    """In-memory service registry for development and testing."""

    def __init__(self, config: ServiceRegistryConfig):
        self.config = config
        self._services: dict[str, dict[str, ServiceInstance]] = {}  # service_name -> {instance_id -> instance}

        # Background tasks
        self._cleanup_task: asyncio.Task | None = None

        # Statistics
        self._stats = {
            "total_registrations": 0,
            "total_deregistrations": 0,
            "total_health_updates": 0,
            "current_services": 0,
            "current_instances": 0,
        }

    async def start(self):
        """Start background tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("MemoryRegistry started")

    async def stop(self):
        """Stop background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("MemoryRegistry stopped")

    async def register(self, instance: ServiceInstance) -> bool:
        """Register a service instance."""
        try:
            service_name = instance.service_name
            instance_id = instance.instance_id

            # Initialize service if not exists
            if service_name not in self._services:
                self._services[service_name] = {}

            # Check instance limit
            if len(self._services[service_name]) >= self.config.max_instances_per_service:
                logger.warning(
                    "Cannot register instance %s for service %s: instance limit reached",
                    instance_id,
                    service_name,
                )
                return False

            # Check service limit
            if len(self._services) >= self.config.max_services:
                logger.warning("Cannot register service %s: service limit reached", service_name)
                return False

            # Update instance status
            instance.status = ServiceStatus.STARTING
            instance.registration_time = time.time()
            instance.last_seen = time.time()

            # Store instance
            self._services[service_name][instance_id] = instance

            # Update statistics
            self._stats["total_registrations"] += 1
            self._update_counts()

            logger.info("Registered service instance: %s", instance)
            return True

        except Exception as e:
            logger.error("Failed to register instance %s: %s", instance, e)
            return False

    async def deregister(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance."""
        try:
            if service_name not in self._services:
                return False

            if instance_id not in self._services[service_name]:
                return False

            # Remove instance
            del self._services[service_name][instance_id]

            # Remove service if no instances
            if not self._services[service_name]:
                del self._services[service_name]

            # Update statistics
            self._stats["total_deregistrations"] += 1
            self._update_counts()

            logger.info("Deregistered service instance: %s[%s]", service_name, instance_id)
            return True

        except Exception as e:
            logger.error("Failed to deregister instance %s[%s]: %s", service_name, instance_id, e)
            return False

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Discover all instances of a service."""
        if service_name not in self._services:
            return []

        instances = list(self._services[service_name].values())

        # Filter out terminated instances
        instances = [
            instance for instance in instances if instance.status != ServiceStatus.TERMINATED
        ]

        return instances

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance."""
        if service_name not in self._services:
            return None

        return self._services[service_name].get(instance_id)

    async def update_instance(self, instance: ServiceInstance) -> bool:
        """Update a service instance."""
        service_name = instance.service_name
        instance_id = instance.instance_id

        if service_name not in self._services:
            return False

        if instance_id not in self._services[service_name]:
            return False

        # Update instance
        instance.last_seen = time.time()
        self._services[service_name][instance_id] = instance

        logger.debug("Updated service instance: %s", instance)
        return True

    async def list_services(self) -> list[str]:
        """List all registered services."""
        return list(self._services.keys())

    async def get_healthy_instances(self, service_name: str) -> list[ServiceInstance]:
        """Get healthy instances of a service."""
        instances = await self.discover(service_name)
        return [i for i in instances if i.is_healthy()]

    async def update_health_status(
        self, service_name: str, instance_id: str, status: HealthStatus
    ) -> bool:
        """Update health status of an instance."""
        instance = await self.get_instance(service_name, instance_id)
        if not instance:
            return False

        instance.update_health_status(status)
        self._stats["total_health_updates"] += 1
        return True

    def _update_counts(self):
        """Update current counts."""
        self._stats["current_services"] = len(self._services)
        self._stats["current_instances"] = sum(len(instances) for instances in self._services.values())

    async def _cleanup_loop(self):
        """Background loop to clean up expired instances."""
        while True:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                await self._cleanup_expired_instances()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop: %s", e)

    async def _cleanup_expired_instances(self):
        """Clean up instances that haven't been seen recently."""
        now = time.time()
        ttl = self.config.instance_ttl

        for service_name in list(self._services.keys()):
            for instance_id, instance in list(self._services[service_name].items()):
                if now - instance.last_seen > ttl:
                    logger.warning(
                        "Instance %s expired (last seen %.1fs ago)",
                        instance_id,
                        now - instance.last_seen,
                    )
                    await self.deregister(service_name, instance_id)
