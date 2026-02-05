"""
Consul Service Registry Adapter

Implementation of IServiceRegistry using HashCorp Consul for production service discovery.
"""

import asyncio
import logging
from typing import Any

import httpx

from mmf.discovery.domain.models import (
    HealthStatus,
    ServiceInstance,
    ServiceRegistryConfig,
    ServiceStatus,
)
from mmf.discovery.ports.registry import IServiceRegistry

logger = logging.getLogger(__name__)


class ConsulAdapter(IServiceRegistry):
    """Consul-based service registry for production deployments."""

    def __init__(
        self,
        config: ServiceRegistryConfig,
        consul_host: str = "localhost",
        consul_port: int = 8500,
        consul_token: str | None = None,
        consul_datacenter: str = "dc1",
        consul_scheme: str = "http",
    ):
        self.config = config
        self.consul_host = consul_host
        self.consul_port = consul_port
        self.consul_token = consul_token
        self.consul_datacenter = consul_datacenter
        self.consul_scheme = consul_scheme

        self.base_url = f"{consul_scheme}://{consul_host}:{consul_port}"
        self._client: httpx.AsyncClient | None = None

        # Statistics
        self._stats = {
            "total_registrations": 0,
            "total_deregistrations": 0,
            "total_health_updates": 0,
            "consul_errors": 0,
        }

    async def start(self):
        """Start Consul client."""
        headers = {}
        if self.consul_token:
            headers["X-Consul-Token"] = self.consul_token

        self._client = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=10.0)
        logger.info(f"ConsulAdapter connected to {self.base_url}")

    async def stop(self):
        """Stop Consul client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("ConsulAdapter stopped")

    async def register(self, instance: ServiceInstance) -> bool:
        """Register a service instance with Consul."""
        if not self._client:
            await self.start()

        try:
            # Build Consul service registration payload
            registration = {
                "ID": instance.instance_id,
                "Name": instance.service_name,
                "Address": instance.host,
                "Port": instance.port,
                "Tags": list(instance.tags) if instance.tags else [],
                "Meta": {
                    "version": instance.version,
                    "region": instance.region or "default",
                    "zone": instance.zone or "default",
                    **(instance.metadata or {}),
                },
            }

            # Add health check if enabled
            if self.config.enable_health_checks and instance.health_check_url:
                registration["Check"] = {
                    "HTTP": instance.health_check_url,
                    "Interval": f"{self.config.health_check_interval}s",
                    "Timeout": f"{self.config.health_check_timeout}s",
                    "DeregisterCriticalServiceAfter": f"{self.config.service_ttl}s",
                }

            # Register with Consul
            response = await self._client.put("/v1/agent/service/register", json=registration)
            response.raise_for_status()

            self._stats["total_registrations"] += 1
            logger.info(
                f"Registered service {instance.service_name} "
                f"instance {instance.instance_id} with Consul"
            )
            return True

        except httpx.HTTPError as e:
            self._stats["consul_errors"] += 1
            logger.error(f"Failed to register service with Consul: {e}")
            return False

    async def deregister(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance from Consul."""
        if not self._client:
            await self.start()

        try:
            response = await self._client.put(f"/v1/agent/service/deregister/{instance_id}")
            response.raise_for_status()

            self._stats["total_deregistrations"] += 1
            logger.info(
                f"Deregistered service {service_name} " f"instance {instance_id} from Consul"
            )
            return True

        except httpx.HTTPError as e:
            self._stats["consul_errors"] += 1
            logger.error(f"Failed to deregister service from Consul: {e}")
            return False

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Discover all instances of a service from Consul."""
        if not self._client:
            await self.start()

        try:
            response = await self._client.get(
                f"/v1/health/service/{service_name}", params={"dc": self.consul_datacenter}
            )
            response.raise_for_status()

            services = response.json()
            instances = []

            for svc in services:
                service_data = svc.get("Service", {})
                checks = svc.get("Checks", [])

                # Determine health status from checks
                health_status = HealthStatus.HEALTHY
                for check in checks:
                    status = check.get("Status", "passing")
                    if status == "critical":
                        health_status = HealthStatus.UNHEALTHY
                        break
                    elif status == "warning":
                        health_status = HealthStatus.DEGRADED

                # Build ServiceInstance
                instance = ServiceInstance(
                    service_name=service_data.get("Service", service_name),
                    instance_id=service_data.get("ID", ""),
                    host=service_data.get("Address", ""),
                    port=service_data.get("Port", 0),
                    status=ServiceStatus.RUNNING,
                    health_status=health_status,
                    version=service_data.get("Meta", {}).get("version", "unknown"),
                    region=service_data.get("Meta", {}).get("region"),
                    zone=service_data.get("Meta", {}).get("zone"),
                    tags=set(service_data.get("Tags", [])),
                    metadata=service_data.get("Meta", {}),
                )
                instances.append(instance)

            logger.debug(f"Discovered {len(instances)} instances of {service_name}")
            return instances

        except httpx.HTTPError as e:
            self._stats["consul_errors"] += 1
            logger.error(f"Failed to discover service from Consul: {e}")
            return []

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance from Consul."""
        instances = await self.discover(service_name)
        for instance in instances:
            if instance.instance_id == instance_id:
                return instance
        return None

    async def update_instance(self, instance: ServiceInstance) -> bool:
        """Update a service instance in Consul (re-register)."""
        return await self.register(instance)

    async def list_services(self) -> list[str]:
        """List all registered services in Consul."""
        if not self._client:
            await self.start()

        try:
            response = await self._client.get(
                "/v1/catalog/services", params={"dc": self.consul_datacenter}
            )
            response.raise_for_status()

            services = response.json()
            return list(services.keys())

        except httpx.HTTPError as e:
            self._stats["consul_errors"] += 1
            logger.error(f"Failed to list services from Consul: {e}")
            return []

    async def get_healthy_instances(self, service_name: str) -> list[ServiceInstance]:
        """Get healthy instances of a service from Consul."""
        if not self._client:
            await self.start()

        try:
            response = await self._client.get(
                f"/v1/health/service/{service_name}",
                params={"dc": self.consul_datacenter, "passing": "true"},
            )
            response.raise_for_status()

            services = response.json()
            instances = []

            for svc in services:
                service_data = svc.get("Service", {})

                instance = ServiceInstance(
                    service_name=service_data.get("Service", service_name),
                    instance_id=service_data.get("ID", ""),
                    host=service_data.get("Address", ""),
                    port=service_data.get("Port", 0),
                    status=ServiceStatus.RUNNING,
                    health_status=HealthStatus.HEALTHY,
                    version=service_data.get("Meta", {}).get("version", "unknown"),
                    region=service_data.get("Meta", {}).get("region"),
                    zone=service_data.get("Meta", {}).get("zone"),
                    tags=set(service_data.get("Tags", [])),
                    metadata=service_data.get("Meta", {}),
                )
                instances.append(instance)

            logger.debug(f"Found {len(instances)} healthy instances of {service_name}")
            return instances

        except httpx.HTTPError as e:
            self._stats["consul_errors"] += 1
            logger.error(f"Failed to get healthy instances from Consul: {e}")
            return []

    async def update_health_status(
        self, service_name: str, instance_id: str, status: HealthStatus
    ) -> bool:
        """Update health status of an instance (using TTL check)."""
        if not self._client:
            await self.start()

        try:
            # Consul uses pass/warn/fail for TTL checks
            check_status = "pass"
            if status == HealthStatus.DEGRADED:
                check_status = "warn"
            elif status == HealthStatus.UNHEALTHY:
                check_status = "fail"

            response = await self._client.put(
                f"/v1/agent/check/update/{instance_id}", json={"Status": check_status}
            )
            response.raise_for_status()

            self._stats["total_health_updates"] += 1
            return True

        except httpx.HTTPError as e:
            self._stats["consul_errors"] += 1
            logger.error(f"Failed to update health status in Consul: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get adapter statistics."""
        return self._stats.copy()
