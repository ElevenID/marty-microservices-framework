from __future__ import annotations

from ..core import ServiceEndpoint, ServiceInstanceType, ServiceMetadata

"""
Server-side discovery client that calls an external discovery endpoint.
"""

import builtins
import logging
import time

import aiohttp

from ..config import DiscoveryConfig, ServiceQuery
from ..core import HealthStatus, ServiceInstance
from ..results import DiscoveryResult
from .base import ServiceDiscoveryClient

logger = logging.getLogger(__name__)


class ServerSideDiscovery(ServiceDiscoveryClient):
    """Server-side service discovery implementation using a discovery service."""

    def __init__(self, discovery_service_url: str, config: DiscoveryConfig):
        super().__init__(config)
        self.discovery_service_url = discovery_service_url
        self._http_session: aiohttp.ClientSession | None = None
        self._timeout = aiohttp.ClientTimeout(total=30)

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create the shared HTTP session."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                timeout=self._timeout,
                connector=aiohttp.TCPConnector(limit=100, limit_per_host=30),
            )
        return self._http_session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None

    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover instances using the external discovery service."""
        start_time = time.time()

        try:
            cached_instances = await self.cache.get(query)
            if cached_instances is not None:
                self._stats["cache_hits"] += 1
                resolution_time = time.time() - start_time

                return DiscoveryResult(
                    instances=cached_instances,
                    query=query,
                    source="cache",
                    cached=True,
                    resolution_time=resolution_time,
                )

            self._stats["cache_misses"] += 1
            instances = await self._query_discovery_service(query)

            await self.cache.put(query, instances)

            resolution_time = time.time() - start_time
            self.record_resolution(True, resolution_time)

            return DiscoveryResult(
                instances=instances,
                query=query,
                source="discovery_service",
                cached=False,
                resolution_time=resolution_time,
            )

        except Exception as e:
            resolution_time = time.time() - start_time
            self.record_resolution(False, resolution_time)
            logger.error("Server-side discovery failed for %s: %s", query.service_name, e)
            raise

    async def _query_discovery_service(self, query: ServiceQuery) -> builtins.list[ServiceInstance]:
        """Query the external discovery service."""
        session = await self._get_http_session()

        params = {"service": query.service_name}
        if query.version:
            params["version"] = query.version
        if query.environment:
            params["environment"] = query.environment
        if query.zone:
            params["zone"] = query.zone
        if query.region:
            params["region"] = query.region
        if not query.include_unhealthy:
            params["healthy"] = "true"
        if query.max_instances:
            params["limit"] = str(query.max_instances)

        for key, value in query.tags.items():
            params[f"tag.{key}"] = value
        for key, value in query.labels.items():
            params[f"label.{key}"] = value

        url = f"{self.discovery_service_url.rstrip('/')}/services/discover"
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_discovery_response(data)
                if response.status == 404:
                    return []
                error_text = await response.text()
                raise RuntimeError(f"Discovery service error {response.status}: {error_text}")

        except aiohttp.ClientError as e:
            logger.error("HTTP client error querying discovery service: %s", e)
            raise
        except Exception as e:
            logger.error("Error querying discovery service: %s", e)
            raise

    def _parse_discovery_response(self, data: dict) -> builtins.list[ServiceInstance]:
        """Parse discovery service response into ServiceInstance objects."""

        instances = []

        for item in data.get("instances", []):
            try:
                endpoint = ServiceEndpoint(
                    host=item["host"],
                    port=item["port"],
                    protocol=ServiceInstanceType(item.get("protocol", "http")),
                    path=item.get("path", ""),
                    ssl_enabled=item.get("ssl_enabled", False),
                )

                metadata = ServiceMetadata(
                    version=item.get("version", "1.0.0"),
                    environment=item.get("environment", "production"),
                    region=item.get("region", "default"),
                    availability_zone=item.get("zone", "default"),
                )

                if "labels" in item:
                    metadata.labels.update(item["labels"])
                if "tags" in item:
                    metadata.tags.update(item["tags"])

                instance = ServiceInstance(
                    service_name=item["service_name"],
                    instance_id=item.get("instance_id"),
                    endpoint=endpoint,
                    metadata=metadata,
                )

                if "health_status" in item:
                    health_status = HealthStatus(item["health_status"])
                    instance.update_health_status(health_status)

                instances.append(instance)

            except (KeyError, ValueError) as e:
                logger.warning("Failed to parse discovery response item %s: %s", item, e)
                continue

        return instances
