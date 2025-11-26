from __future__ import annotations

"""
Client-side discovery implementation that talks directly to a registry.
"""

import builtins
import logging
import time
from collections.abc import Callable

from ..config import DiscoveryConfig, ServiceQuery
from ..core import ServiceInstance, ServiceRegistry, ServiceWatcher
from ..results import DiscoveryResult
from .base import ServiceDiscoveryClient

logger = logging.getLogger(__name__)


class ClientSideDiscovery(ServiceDiscoveryClient):
    """Client-side service discovery implementation."""

    def __init__(self, registry: ServiceRegistry, config: DiscoveryConfig):
        super().__init__(config)
        self.registry = registry
        self._watchers: builtins.dict[str, ServiceWatcher] = {}

    async def discover_instances(self, query: ServiceQuery) -> DiscoveryResult:
        """Discover instances using client-side discovery."""
        start_time = time.time()

        try:
            cached_instances = await self.cache.get(query, lambda: self._fetch_from_registry(query))

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
            instances = await self._fetch_from_registry(query)

            await self.cache.put(query, instances, lambda: self._fetch_from_registry(query))

            resolution_time = time.time() - start_time
            self.record_resolution(True, resolution_time)

            return DiscoveryResult(
                instances=instances,
                query=query,
                source="registry",
                cached=False,
                resolution_time=resolution_time,
            )

        except Exception as e:
            resolution_time = time.time() - start_time
            self.record_resolution(False, resolution_time)
            logger.error("Service discovery failed for %s: %s", query.service_name, e)
            raise

    async def _fetch_from_registry(self, query: ServiceQuery) -> builtins.list[ServiceInstance]:
        """Fetch instances from the service registry."""
        all_instances = await self.registry.discover(query.service_name)
        return [instance for instance in all_instances if query.matches_instance(instance)]

    async def watch_service(
        self,
        service_name: str,
        callback: Callable[[builtins.list[ServiceInstance]], None],
    ):
        """Watch service for changes (stubbed until registries support streaming)."""
        logger.warning("Service watching not fully implemented - callback stored but not activated")
        if service_name not in self._watchers:
            self._watchers[service_name] = callback

        return self._watchers[service_name]

    async def stop_watching(self, service_name: str) -> None:
        """Stop watching service."""
        watcher = self._watchers.pop(service_name, None)
        if watcher:
            logger.info("Stopped watching service: %s", service_name)
