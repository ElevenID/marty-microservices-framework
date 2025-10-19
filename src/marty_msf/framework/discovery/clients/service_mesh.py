from __future__ import annotations

from ..core import ServiceEndpoint, ServiceInstanceType, ServiceMetadata

"""
Service mesh discovery client that integrates with mesh control planes.
"""

import builtins
import logging
import time
from typing import Any

from ..config import DiscoveryConfig, ServiceQuery
from ..core import HealthStatus, ServiceInstance
from ..results import DiscoveryResult
from .base import ServiceDiscoveryClient
from .mesh_client import MockKubernetesClient

logger = logging.getLogger(__name__)


class ServiceMeshDiscovery(ServiceDiscoveryClient):
    """Service mesh integration for discovery."""

    def __init__(self, mesh_config: builtins.dict[str, Any], config: DiscoveryConfig):
        super().__init__(config)
        self.mesh_config = mesh_config
        self.mesh_type = mesh_config.get("type", "istio").lower()
        self.namespace = mesh_config.get("namespace", "default")
        self._k8s_client = None
        self._allow_stub = mesh_config.get("allow_stub", False)

        if self.mesh_type == "istio":
            self.control_plane_namespace = mesh_config.get("istio_namespace", "istio-system")
        elif self.mesh_type == "linkerd":
            self.control_plane_namespace = mesh_config.get("linkerd_namespace", "linkerd")
        else:
            logger.warning(
                "Unsupported mesh type: %s, using generic implementation", self.mesh_type
            )

    async def _get_k8s_client(self):
        """Get Kubernetes client for service mesh integration."""
        if self._k8s_client is None:
            try:
                client_factory = self.mesh_config.get("client_factory")
                if client_factory:
                    self._k8s_client = client_factory(self.mesh_config)
                else:
                    if not self._allow_stub:
                        raise RuntimeError(
                            "Service mesh discovery requires a real Kubernetes client. "
                            "Provide 'client_factory' in mesh_config or set "
                            "'allow_stub': True for development-only usage."
                        )
                    self._k8s_client = MockKubernetesClient(self.mesh_config)
            except Exception as exc:
                logger.error("Failed to initialize Kubernetes client: %s", exc)
                raise
        return self._k8s_client

    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover instances through the service mesh."""
        start_time = time.time()

        try:
            cached_instances = await self.cache.get(query)
            if cached_instances is not None:
                self._stats["cache_hits"] += 1
                resolution_time = time.time() - start_time
                cache_key = self.cache._generate_cache_key(query)
                cache_entry = self.cache._cache.get(cache_key)
                cache_age = time.time() - cache_entry.created_at if cache_entry else 0.0

                return DiscoveryResult(
                    instances=cached_instances,
                    query=query,
                    source="cache",
                    cached=True,
                    cache_age=cache_age,
                    resolution_time=resolution_time,
                )

            self._stats["cache_misses"] += 1
            instances = await self._discover_from_mesh(query)

            await self.cache.put(query, instances)

            resolution_time = time.time() - start_time
            self.record_resolution(True, resolution_time)

            return DiscoveryResult(
                instances=instances,
                query=query,
                source="service_mesh",
                cached=False,
                resolution_time=resolution_time,
            )

        except Exception as exc:
            resolution_time = time.time() - start_time
            self.record_resolution(False, resolution_time)
            logger.error("Service mesh discovery failed for %s: %s", query.service_name, exc)
            raise

    async def _discover_from_mesh(self, query: ServiceQuery) -> builtins.list[ServiceInstance]:
        """Discover instances from the service mesh control plane."""
        k8s_client = await self._get_k8s_client()

        try:
            endpoints = await k8s_client.get_service_endpoints(query.service_name, self.namespace)

            instances = []
            for endpoint in endpoints:
                try:

                    service_endpoint = ServiceEndpoint(
                        host=endpoint.get("host", "localhost"),
                        port=endpoint.get("port", 80),
                        protocol=ServiceInstanceType(endpoint.get("protocol", "http")),
                    )

                    metadata = ServiceMetadata(
                        version=endpoint.get("version", "1.0.0"),
                        environment=query.environment or "production",
                        region=query.region or "default",
                        availability_zone=query.zone or "default",
                    )

                    if "labels" in endpoint:
                        metadata.labels.update(endpoint["labels"])

                    instance = ServiceInstance(
                        service_name=query.service_name,
                        instance_id=endpoint.get("instance_id"),
                        endpoint=service_endpoint,
                        metadata=metadata,
                    )

                    if endpoint.get("healthy", True):
                        instance.update_health_status(HealthStatus.HEALTHY)
                    else:
                        instance.update_health_status(HealthStatus.UNHEALTHY)

                    instances.append(instance)

                except Exception as parse_error:
                    logger.warning("Failed to parse mesh endpoint %s: %s", endpoint, parse_error)
                    continue

            return [instance for instance in instances if query.matches_instance(instance)]

        except Exception as exc:
            logger.error("Error querying service mesh: %s", exc)
            return []
