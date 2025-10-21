"""
Service Registry Implementations

Multiple service registry backends including in-memory, Consul, etcd,
and Kubernetes with automatic failover and clustering support.
"""

import asyncio
import builtins
import json
import logging
import time
from typing import Any

import aiohttp
import consul.aio
import etcd3
from kubernetes import client
from kubernetes import config as k8s_config

from .core import (
    HealthStatus,
    ServiceEndpoint,
    ServiceEvent,
    ServiceInstance,
    ServiceInstanceType,
    ServiceMetadata,
    ServiceRegistry,
    ServiceRegistryConfig,
    ServiceStatus,
    ServiceWatcher,
)

logger = logging.getLogger(__name__)


class InMemoryServiceRegistry(ServiceRegistry):
    """In-memory service registry for development and testing."""

    def __init__(self, config: ServiceRegistryConfig):
        self.config = config
        self._services: dict[
            str, dict[str, ServiceInstance]
        ] = {}  # service_name -> {instance_id -> instance}
        self._watchers: list[ServiceWatcher] = []
        self._event_queue: list[ServiceEvent] = []

        # Background tasks
        self._cleanup_task: asyncio.Task | None = None
        self._health_check_task: asyncio.Task | None = None

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
        if self.config.enable_health_checks:
            self._health_check_task = asyncio.create_task(self._health_check_loop())

        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("InMemoryServiceRegistry started")

    async def stop(self):
        """Stop background tasks."""
        if self._health_check_task:
            self._health_check_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Wait for tasks to complete
        tasks = [t for t in [self._health_check_task, self._cleanup_task] if t]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("InMemoryServiceRegistry stopped")

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

            # Notify watchers
            event = ServiceEvent("register", service_name, instance_id, instance)
            await self._notify_watchers(event)

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

            instance = self._services[service_name][instance_id]
            instance.status = ServiceStatus.TERMINATING

            # Remove instance
            del self._services[service_name][instance_id]

            # Remove service if no instances
            if not self._services[service_name]:
                del self._services[service_name]

            # Update statistics
            self._stats["total_deregistrations"] += 1
            self._update_counts()

            # Notify watchers
            event = ServiceEvent("deregister", service_name, instance_id, instance)
            await self._notify_watchers(event)

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
        return [instance for instance in instances if instance.is_healthy()]

    async def update_health_status(
        self, service_name: str, instance_id: str, status: HealthStatus
    ) -> bool:
        """Update health status of an instance."""
        instance = await self.get_instance(service_name, instance_id)
        if not instance:
            return False

        old_status = instance.health_status
        instance.update_health_status(status)

        # Update statistics
        self._stats["total_health_updates"] += 1

        # Notify watchers if status changed
        if old_status != status:
            event = ServiceEvent("health_change", service_name, instance_id, instance)
            await self._notify_watchers(event)

        return True

    def add_watcher(self, watcher: ServiceWatcher):
        """Add a service watcher."""
        self._watchers.append(watcher)

    def remove_watcher(self, watcher: ServiceWatcher):
        """Remove a service watcher."""
        if watcher in self._watchers:
            self._watchers.remove(watcher)

    async def _notify_watchers(self, event: ServiceEvent):
        """Notify all watchers of an event."""
        self._event_queue.append(event)

        for watcher in self._watchers:
            try:
                if event.event_type == "register":
                    await watcher.on_service_registered(event)
                elif event.event_type == "deregister":
                    await watcher.on_service_deregistered(event)
                elif event.event_type == "health_change":
                    await watcher.on_health_changed(event)
            except Exception as e:
                logger.error("Error notifying watcher: %s", e)

    async def _health_check_loop(self):
        """Background health check loop."""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check loop error: %s", e)
                await asyncio.sleep(self.config.health_check_interval)

    async def _perform_health_checks(self):
        """Perform health checks on all instances."""
        current_time = time.time()

        for service_name, instances in self._services.items():
            for instance_id, instance in list(instances.items()):
                try:
                    # Check if instance should be health checked
                    if (
                        instance.last_health_check is None
                        or current_time - instance.last_health_check
                        >= instance.health_check.interval
                    ):
                        # Perform health check
                        health_status = await self._check_instance_health(instance)
                        await self.update_health_status(service_name, instance_id, health_status)

                except Exception as e:
                    logger.error("Error checking health for instance %s: %s", instance, e)
                    await self.update_health_status(service_name, instance_id, HealthStatus.ERROR)

    async def _check_instance_health(self, instance: ServiceInstance) -> HealthStatus:
        """Check health of a single instance."""
        health_check = instance.health_check

        if not health_check.is_valid():
            return HealthStatus.UNKNOWN

        try:
            if health_check.url:
                # HTTP health check
                return await self._http_health_check(instance, health_check)
            if health_check.tcp_port:
                # TCP health check
                return await self._tcp_health_check(instance, health_check)
            # Custom health check
            return await self._custom_health_check(instance, health_check)

        except asyncio.TimeoutError:
            return HealthStatus.TIMEOUT
        except Exception as e:
            logger.debug("Health check failed for %s: %s", instance, e)
            return HealthStatus.ERROR

    async def _http_health_check(self, instance: ServiceInstance, health_check) -> HealthStatus:
        """Perform HTTP health check."""
        try:

            url = health_check.url
            if not url.startswith(("http://", "https://")):
                base_url = instance.endpoint.get_url()
                url = f"{base_url.rstrip('/')}/{url.lstrip('/')}"

            timeout = aiohttp.ClientTimeout(total=health_check.timeout)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.request(
                    health_check.method,
                    url,
                    headers=health_check.headers,
                    ssl=health_check.verify_ssl,
                ) as response:
                    if response.status == health_check.expected_status:
                        return HealthStatus.HEALTHY
                    return HealthStatus.UNHEALTHY

        except ImportError:
            logger.warning("aiohttp not available for HTTP health checks")
            return HealthStatus.UNKNOWN
        except Exception:
            return HealthStatus.UNHEALTHY

    async def _tcp_health_check(self, instance: ServiceInstance, health_check) -> HealthStatus:
        """Perform TCP health check."""
        try:
            host = instance.endpoint.host
            port = health_check.tcp_port or instance.endpoint.port

            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=health_check.timeout)

            writer.close()
            await writer.wait_closed()

            return HealthStatus.HEALTHY

        except Exception:
            return HealthStatus.UNHEALTHY

    async def _custom_health_check(self, instance: ServiceInstance, health_check) -> HealthStatus:
        """Perform custom health check."""
        # This would execute a custom health check command or function
        # For now, return unknown
        return HealthStatus.UNKNOWN

    async def _cleanup_loop(self):
        """Background cleanup loop."""
        while True:
            try:
                await self._cleanup_expired_instances()
                await asyncio.sleep(self.config.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Cleanup loop error: %s", e)
                await asyncio.sleep(self.config.cleanup_interval)

    async def _cleanup_expired_instances(self):
        """Clean up expired instances."""
        current_time = time.time()
        expired_instances = []

        for service_name, instances in self._services.items():
            for instance_id, instance in list(instances.items()):
                # Check if instance has expired
                if current_time - instance.last_seen > self.config.instance_ttl:
                    expired_instances.append((service_name, instance_id))

        # Remove expired instances
        for service_name, instance_id in expired_instances:
            await self.deregister(service_name, instance_id)
            logger.info("Cleaned up expired instance: %s[%s]", service_name, instance_id)

    def _update_counts(self):
        """Update service and instance counts."""
        self._stats["current_services"] = len(self._services)
        self._stats["current_instances"] = sum(
            len(instances) for instances in self._services.values()
        )

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        return {
            **self._stats,
            "watchers": len(self._watchers),
            "events_queued": len(self._event_queue),
        }


class ConsulServiceRegistry(ServiceRegistry):
    """Consul-based service registry implementation."""

    def __init__(
        self,
        config: ServiceRegistryConfig,
        consul_config: dict[str, Any] | None = None,
    ):
        self.config = config
        self.consul_config = consul_config or {}
        self._consul = None
        self._session_id: str | None = None

    async def _get_consul_client(self):
        """Get Consul client."""
        if self._consul is None:
            self._consul = consul.aio.Consul(
                host=self.consul_config.get("host", "localhost"),
                port=self.consul_config.get("port", 8500),
                token=self.consul_config.get("token"),
                scheme=self.consul_config.get("scheme", "http"),
                verify=self.consul_config.get("verify", True),
            )

            # Create session for TTL
            if self.config.instance_ttl > 0:
                self._session_id = await self._consul.session.create(
                    ttl=int(self.config.instance_ttl)
                )

        return self._consul

    async def register(self, instance: ServiceInstance) -> bool:
        """Register a service instance in Consul."""
        try:
            consul = await self._get_consul_client()

            service_id = f"{instance.service_name}-{instance.instance_id}"

            # Build service definition
            service_def = {
                "ID": service_id,
                "Name": instance.service_name,
                "Tags": list(instance.metadata.tags),
                "Address": instance.endpoint.host,
                "Port": instance.endpoint.port,
                "Meta": {
                    "instance_id": instance.instance_id,
                    "version": instance.metadata.version,
                    "environment": instance.metadata.environment,
                    "region": instance.metadata.region,
                    **instance.metadata.labels,
                },
            }

            # Add health check if configured
            if instance.health_check.is_valid():
                if instance.health_check.url:
                    service_def["Check"] = {
                        "HTTP": instance.health_check.url,
                        "Method": instance.health_check.method,
                        "Header": instance.health_check.headers,
                        "Interval": f"{int(instance.health_check.interval)}s",
                        "Timeout": f"{int(instance.health_check.timeout)}s",
                    }
                elif instance.health_check.tcp_port:
                    service_def["Check"] = {
                        "TCP": f"{instance.endpoint.host}:{instance.health_check.tcp_port}",
                        "Interval": f"{int(instance.health_check.interval)}s",
                        "Timeout": f"{int(instance.health_check.timeout)}s",
                    }

            # Register service
            success = await consul.agent.service.register(**service_def)

            if success:
                logger.info("Registered service in Consul: %s", instance)
                return True
            logger.error("Failed to register service in Consul: %s", instance)
            return False

        except Exception as e:
            logger.error("Error registering service in Consul: %s", e)
            return False

    async def deregister(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance from Consul."""
        try:
            consul = await self._get_consul_client()
            service_id = f"{service_name}-{instance_id}"

            success = await consul.agent.service.deregister(service_id)

            if success:
                logger.info(
                    "Deregistered service from Consul: %s[%s]",
                    service_name,
                    instance_id,
                )
                return True
            logger.error(
                "Failed to deregister service from Consul: %s[%s]",
                service_name,
                instance_id,
            )
            return False

        except Exception as e:
            logger.error("Error deregistering service from Consul: %s", e)
            return False

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Discover all instances of a service from Consul."""
        try:
            consul = await self._get_consul_client()
            _, services = await consul.health.service(service_name, passing=False)

            instances = []
            for service_data in services:
                instance = self._consul_service_to_instance(service_data)
                if instance:
                    instances.append(instance)

            return instances

        except Exception as e:
            logger.error("Error discovering services from Consul: %s", e)
            return []

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance from Consul."""
        instances = await self.discover(service_name)

        for instance in instances:
            if instance.instance_id == instance_id:
                return instance

        return None

    async def update_instance(self, instance: ServiceInstance) -> bool:
        """Update a service instance in Consul."""
        # Consul updates are typically done by re-registering
        return await self.register(instance)

    async def list_services(self) -> list[str]:
        """List all registered services from Consul."""
        try:
            consul = await self._get_consul_client()
            _, services = await consul.agent.services()

            service_names = set()
            for service in services.values():
                service_names.add(service["Service"])

            return list(service_names)

        except Exception as e:
            logger.error("Error listing services from Consul: %s", e)
            return []

    async def get_healthy_instances(self, service_name: str) -> list[ServiceInstance]:
        """Get healthy instances of a service from Consul."""
        try:
            consul = await self._get_consul_client()
            _, services = await consul.health.service(service_name, passing=True)

            instances = []
            for service_data in services:
                instance = self._consul_service_to_instance(service_data)
                if instance:
                    instances.append(instance)

            return instances

        except Exception as e:
            logger.error("Error getting healthy services from Consul: %s", e)
            return []

    async def update_health_status(
        self, service_name: str, instance_id: str, status: HealthStatus
    ) -> bool:
        """Update health status of an instance in Consul."""
        # Consul manages health status through its own health checks
        # This is mainly for compatibility with the interface
        logger.debug(
            "Health status update for Consul registry: %s[%s] -> %s",
            service_name,
            instance_id,
            status.value,
        )
        return True

    def _consul_service_to_instance(
        self, service_data: dict[str, Any]
    ) -> ServiceInstance | None:
        """Convert Consul service data to ServiceInstance."""
        try:
            service = service_data["Service"]
            checks = service_data.get("Checks", [])

            # Extract instance ID from meta or service ID
            instance_id = service.get("Meta", {}).get("instance_id")
            if not instance_id:
                # Extract from service ID
                service_id = service.get("ID", "")
                if "-" in service_id:
                    instance_id = service_id.split("-", 1)[1]
                else:
                    instance_id = service_id

            # Create service instance

            endpoint = ServiceEndpoint(host=service["Address"], port=service["Port"])

            metadata = ServiceMetadata(
                version=service.get("Meta", {}).get("version", "1.0.0"),
                environment=service.get("Meta", {}).get("environment", "production"),
                region=service.get("Meta", {}).get("region", "default"),
                tags=set(service.get("Tags", [])),
            )

            # Add labels from meta
            for key, value in service.get("Meta", {}).items():
                if key not in ["instance_id", "version", "environment", "region"]:
                    metadata.labels[key] = value

            instance = ServiceInstance(
                service_name=service["Service"],
                instance_id=instance_id,
                endpoint=endpoint,
                metadata=metadata,
            )

            # Set health status based on checks
            if checks:
                healthy_checks = [c for c in checks if c.get("Status") == "passing"]
                if len(healthy_checks) == len(checks):
                    instance.update_health_status(HealthStatus.HEALTHY)
                else:
                    instance.update_health_status(HealthStatus.UNHEALTHY)

            return instance

        except Exception as e:
            logger.error("Error converting Consul service data: %s", e)
            return None


class EtcdServiceRegistry(ServiceRegistry):
    """etcd-based service registry implementation."""

    def __init__(self, config: ServiceRegistryConfig, etcd_config: dict[str, Any] | None = None):
        self.config = config
        self.etcd_config = etcd_config or {}
        self._etcd = None
        self._prefix = "/services/"

    async def _get_etcd_client(self):
        """Get etcd client."""
        if self._etcd is None:
            self._etcd = etcd3.client(
                host=self.etcd_config.get("host", "localhost"),
                port=self.etcd_config.get("port", 2379),
                user=self.etcd_config.get("user"),
                password=self.etcd_config.get("password"),
                ca_cert=self.etcd_config.get("ca_cert"),
                cert_key=self.etcd_config.get("cert_key"),
                cert_cert=self.etcd_config.get("cert_cert"),
            )

        return self._etcd

    async def register(self, instance: ServiceInstance) -> bool:
        """Register a service instance in etcd."""
        try:
            etcd = await self._get_etcd_client()

            key = f"{self._prefix}{instance.service_name}/{instance.instance_id}"
            value = json.dumps(instance.to_dict())

            # Set with TTL if configured
            if self.config.instance_ttl > 0:
                lease = etcd.lease(int(self.config.instance_ttl))
                etcd.put(key, value, lease=lease)
            else:
                etcd.put(key, value)

            logger.info("Registered service in etcd: %s", instance)
            return True

        except Exception as e:
            logger.error("Error registering service in etcd: %s", e)
            return False

    async def deregister(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance from etcd."""
        try:
            etcd = await self._get_etcd_client()
            key = f"{self._prefix}{service_name}/{instance_id}"

            deleted = etcd.delete(key)

            if deleted:
                logger.info("Deregistered service from etcd: %s[%s]", service_name, instance_id)
                return True
            logger.warning("Service not found in etcd: %s[%s]", service_name, instance_id)
            return False

        except Exception as e:
            logger.error("Error deregistering service from etcd: %s", e)
            return False

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Discover all instances of a service from etcd."""
        try:
            etcd = await self._get_etcd_client()
            prefix = f"{self._prefix}{service_name}/"

            instances = []
            for value, _metadata in etcd.get_prefix(prefix):
                try:
                    instance_data = json.loads(value.decode("utf-8"))
                    instance = self._dict_to_instance(instance_data)
                    if instance:
                        instances.append(instance)
                except Exception as e:
                    logger.error("Error parsing instance data from etcd: %s", e)

            return instances

        except Exception as e:
            logger.error("Error discovering services from etcd: %s", e)
            return []

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance from etcd."""
        try:
            etcd = await self._get_etcd_client()
            key = f"{self._prefix}{service_name}/{instance_id}"

            value, metadata = etcd.get(key)
            if value:
                instance_data = json.loads(value.decode("utf-8"))
                return self._dict_to_instance(instance_data)

            return None

        except Exception as e:
            logger.error("Error getting instance from etcd: %s", e)
            return None

    async def update_instance(self, instance: ServiceInstance) -> bool:
        """Update a service instance in etcd."""
        return await self.register(instance)

    async def list_services(self) -> list[str]:
        """List all registered services from etcd."""
        try:
            etcd = await self._get_etcd_client()

            services = set()
            for key, _value in etcd.get_prefix(self._prefix):
                key_str = key.decode("utf-8")
                # Extract service name from key
                relative_key = key_str[len(self._prefix) :]
                if "/" in relative_key:
                    service_name = relative_key.split("/")[0]
                    services.add(service_name)

            return list(services)

        except Exception as e:
            logger.error("Error listing services from etcd: %s", e)
            return []

    async def get_healthy_instances(self, service_name: str) -> list[ServiceInstance]:
        """Get healthy instances of a service from etcd."""
        instances = await self.discover(service_name)
        return [instance for instance in instances if instance.is_healthy()]

    async def update_health_status(
        self, service_name: str, instance_id: str, status: HealthStatus
    ) -> bool:
        """Update health status of an instance in etcd."""
        instance = await self.get_instance(service_name, instance_id)
        if instance:
            instance.update_health_status(status)
            return await self.update_instance(instance)
        return False

    def _dict_to_instance(self, data: dict[str, Any]) -> ServiceInstance | None:
        """Convert dictionary data to ServiceInstance."""
        try:

            # Create endpoint
            endpoint_data = data["endpoint"]
            endpoint = ServiceEndpoint(
                host=endpoint_data["host"],
                port=endpoint_data["port"],
                protocol=getattr(
                    ServiceInstanceType, endpoint_data.get("protocol", "HTTP").upper()
                ),
                path=endpoint_data.get("path", ""),
            )

            # Create metadata
            metadata_data = data["metadata"]
            metadata = ServiceMetadata(
                version=metadata_data.get("version", "1.0.0"),
                environment=metadata_data.get("environment", "production"),
                region=metadata_data.get("region", "default"),
                availability_zone=metadata_data.get("availability_zone", "default"),
                tags=set(metadata_data.get("tags", [])),
                labels=metadata_data.get("labels", {}),
                annotations=metadata_data.get("annotations", {}),
            )

            # Create instance
            instance = ServiceInstance(
                service_name=data["service_name"],
                instance_id=data["instance_id"],
                endpoint=endpoint,
                metadata=metadata,
            )

            # Set status
            instance.status = ServiceStatus(data.get("status", "unknown"))
            instance.health_status = HealthStatus(data.get("health_status", "unknown"))
            instance.last_health_check = data.get("last_health_check")
            instance.registration_time = data.get("registration_time", time.time())
            instance.last_seen = data.get("last_seen", time.time())

            # Set statistics
            stats = data.get("stats", {})
            instance.total_requests = stats.get("total_requests", 0)
            instance.active_connections = stats.get("active_connections", 0)
            instance.total_failures = stats.get("total_failures", 0)

            return instance

        except Exception as e:
            logger.error("Error converting dict to ServiceInstance: %s", e)
            return None


class KubernetesServiceRegistry(ServiceRegistry):
    """Kubernetes-based service registry implementation."""

    def __init__(self, config: ServiceRegistryConfig, k8s_config: dict[str, Any] | None = None):
        self.config = config
        self.k8s_config = k8s_config or {}
        self._k8s_client = None
        self._namespace = self.k8s_config.get("namespace", "default")

    async def _get_k8s_client(self):
        """Get Kubernetes client."""
        if self._k8s_client is None:
            if self.k8s_config.get("in_cluster", False):
                k8s_config.load_incluster_config()
            else:
                k8s_config.load_kube_config(config_file=self.k8s_config.get("config_file"))

            self._k8s_client = client.CoreV1Api()

        return self._k8s_client

    async def register(self, instance: ServiceInstance) -> bool:
        """Register a service instance in Kubernetes."""
        # Kubernetes services are typically managed by controllers
        # This implementation focuses on endpoint management
        logger.info("Kubernetes service registration handled by controller")
        return True

    async def deregister(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance from Kubernetes."""
        logger.info("Kubernetes service deregistration handled by controller")
        return True

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Discover all instances of a service from Kubernetes."""
        try:
            k8s = await self._get_k8s_client()

            # Get service endpoints
            endpoints = k8s.read_namespaced_endpoints(name=service_name, namespace=self._namespace)

            instances = []
            if endpoints.subsets:
                for subset in endpoints.subsets:
                    for address in subset.addresses or []:
                        for port in subset.ports or []:
                            instance = self._k8s_endpoint_to_instance(service_name, address, port)
                            if instance:
                                instances.append(instance)

            return instances

        except Exception as e:
            logger.error("Error discovering services from Kubernetes: %s", e)
            return []

    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance from Kubernetes."""
        instances = await self.discover(service_name)

        for instance in instances:
            if instance.instance_id == instance_id:
                return instance

        return None

    async def update_instance(self, instance: ServiceInstance) -> bool:
        """Update a service instance in Kubernetes."""
        logger.info("Kubernetes instance updates handled by controller")
        return True

    async def list_services(self) -> list[str]:
        """List all registered services from Kubernetes."""
        try:
            k8s = await self._get_k8s_client()

            services = k8s.list_namespaced_service(namespace=self._namespace)

            service_names = []
            for service in services.items:
                service_names.append(service.metadata.name)

            return service_names

        except Exception as e:
            logger.error("Error listing services from Kubernetes: %s", e)
            return []

    async def get_healthy_instances(self, service_name: str) -> list[ServiceInstance]:
        """Get healthy instances of a service from Kubernetes."""
        instances = await self.discover(service_name)
        # In Kubernetes, endpoints are typically only included if healthy
        return instances

    async def update_health_status(
        self, service_name: str, instance_id: str, status: HealthStatus
    ) -> bool:
        """Update health status of an instance in Kubernetes."""
        # Kubernetes manages health through readiness/liveness probes
        logger.debug(
            "Health status update for Kubernetes registry: %s[%s] -> %s",
            service_name,
            instance_id,
            status.value,
        )
        return True

    def _k8s_endpoint_to_instance(
        self, service_name: str, address: Any, port: Any
    ) -> ServiceInstance | None:
        """Convert Kubernetes endpoint to ServiceInstance."""
        try:

            # Create instance ID from IP and port
            instance_id = f"{address.ip}-{port.port}"

            endpoint = ServiceEndpoint(
                host=address.ip,
                port=port.port,
                protocol=ServiceInstanceType.HTTP,  # Default assumption
            )

            metadata = ServiceMetadata(
                environment=self._namespace,
                region=self.k8s_config.get("region", "default"),
            )

            # Add node information if available
            if hasattr(address, "node_name") and address.node_name:
                metadata.labels["node"] = address.node_name

            instance = ServiceInstance(
                service_name=service_name,
                instance_id=instance_id,
                endpoint=endpoint,
                metadata=metadata,
            )

            # Assume healthy if in endpoints
            instance.update_health_status(HealthStatus.HEALTHY)

            return instance

        except Exception as e:
            logger.error("Error converting Kubernetes endpoint: %s", e)
            return None
