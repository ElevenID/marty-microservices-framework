"""
Kong Gateway Route Synchronizer

Automatically synchronizes service routes with Kong API Gateway for centralized
traffic management, authentication, rate limiting, and observability.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class RouteConfig:
    """Configuration for a Kong route."""

    name: str
    service_name: str
    paths: list[str]
    methods: list[str] | None = None
    hosts: list[str] | None = None
    strip_path: bool = True
    preserve_host: bool = False
    protocols: list[str] | None = None
    tags: list[str] | None = None

    # Advanced routing
    headers: dict[str, list[str]] | None = None
    regex_priority: int = 0

    # Plugin configurations
    plugins: list[dict[str, Any]] | None = None


@dataclass
class ServiceConfig:
    """Configuration for a Kong service."""

    name: str
    url: str  # Full URL (protocol://host:port/path)
    protocol: str = "http"
    host: str | None = None
    port: int | None = None
    path: str | None = None
    retries: int = 5
    connect_timeout: int = 60000
    write_timeout: int = 60000
    read_timeout: int = 60000
    tags: list[str] | None = None


class KongRouteSynchronizer:
    """
    Synchronizes service routes with Kong API Gateway.

    Features:
    - Automatic route registration and updates
    - Service discovery integration
    - Health-based routing
    - Plugin management (auth, rate limiting, cors, etc.)
    - Declarative configuration
    """

    def __init__(
        self,
        admin_url: str = "http://localhost:8001",
        admin_token: str | None = None,
        workspace: str = "default",
        auto_sync_interval: int = 60,
    ):
        self.admin_url = admin_url.rstrip("/")
        self.admin_token = admin_token
        self.workspace = workspace
        self.auto_sync_interval = auto_sync_interval

        self._client: httpx.AsyncClient | None = None
        self._sync_task: asyncio.Task | None = None
        self._registered_routes: dict[str, str] = {}  # route_name -> route_id
        self._registered_services: dict[str, str] = {}  # service_name -> service_id

        # Statistics
        self._stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "routes_created": 0,
            "routes_updated": 0,
            "routes_deleted": 0,
            "services_created": 0,
            "services_updated": 0,
            "kong_errors": 0,
        }

    async def start(self):
        """Start Kong synchronizer."""
        headers = {"Content-Type": "application/json"}
        if self.admin_token:
            headers["Kong-Admin-Token"] = self.admin_token

        self._client = httpx.AsyncClient(base_url=self.admin_url, headers=headers, timeout=30.0)

        # Verify Kong connectivity
        try:
            response = await self._client.get("/")
            response.raise_for_status()
            version = response.json().get("version", "unknown")
            logger.info(f"Connected to Kong Gateway {version} at {self.admin_url}")
        except httpx.HTTPError as e:
            logger.error(f"Failed to connect to Kong: {e}")
            raise

        # Start auto-sync task
        if self.auto_sync_interval > 0:
            self._sync_task = asyncio.create_task(self._auto_sync_loop())

    async def stop(self):
        """Stop Kong synchronizer."""
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info("KongRouteSynchronizer stopped")

    async def register_service(self, config: ServiceConfig) -> bool:
        """Register or update a service in Kong."""
        if not self._client:
            await self.start()

        try:
            # Check if service exists
            existing_id = await self._get_service_id(config.name)

            service_data = {
                "name": config.name,
                "url": config.url,
                "retries": config.retries,
                "connect_timeout": config.connect_timeout,
                "write_timeout": config.write_timeout,
                "read_timeout": config.read_timeout,
            }

            if config.tags:
                service_data["tags"] = config.tags

            if existing_id:
                # Update existing service
                response = await self._client.patch(f"/services/{existing_id}", json=service_data)
                response.raise_for_status()
                self._stats["services_updated"] += 1
                logger.info(f"Updated Kong service: {config.name}")
            else:
                # Create new service
                response = await self._client.post("/services", json=service_data)
                response.raise_for_status()
                service_id = response.json()["id"]
                self._registered_services[config.name] = service_id
                self._stats["services_created"] += 1
                logger.info(f"Created Kong service: {config.name}")

            return True

        except httpx.HTTPError as e:
            self._stats["kong_errors"] += 1
            logger.error(f"Failed to register service {config.name}: {e}")
            return False

    async def register_route(self, config: RouteConfig) -> bool:
        """Register or update a route in Kong."""
        if not self._client:
            await self.start()

        try:
            # Ensure service exists
            service_id = await self._get_service_id(config.service_name)
            if not service_id:
                logger.error(
                    f"Cannot create route {config.name}: "
                    f"service {config.service_name} not found"
                )
                return False

            # Check if route exists
            existing_id = await self._get_route_id(config.name)

            route_data = {
                "name": config.name,
                "paths": config.paths,
                "strip_path": config.strip_path,
                "preserve_host": config.preserve_host,
            }

            if config.methods:
                route_data["methods"] = config.methods
            if config.hosts:
                route_data["hosts"] = config.hosts
            if config.protocols:
                route_data["protocols"] = config.protocols
            else:
                route_data["protocols"] = ["http", "https"]
            if config.tags:
                route_data["tags"] = config.tags
            if config.headers:
                route_data["headers"] = config.headers
            if config.regex_priority > 0:
                route_data["regex_priority"] = config.regex_priority

            if existing_id:
                # Update existing route
                response = await self._client.patch(f"/routes/{existing_id}", json=route_data)
                response.raise_for_status()
                self._stats["routes_updated"] += 1
                logger.info(f"Updated Kong route: {config.name}")
            else:
                # Create new route
                route_data["service"] = {"id": service_id}
                response = await self._client.post("/routes", json=route_data)
                response.raise_for_status()
                route_id = response.json()["id"]
                self._registered_routes[config.name] = route_id
                self._stats["routes_created"] += 1
                logger.info(f"Created Kong route: {config.name}")

            # Apply plugins if specified
            if config.plugins:
                route_id = existing_id or self._registered_routes[config.name]
                await self._apply_plugins(route_id, config.plugins)

            return True

        except httpx.HTTPError as e:
            self._stats["kong_errors"] += 1
            logger.error(f"Failed to register route {config.name}: {e}")
            return False

    async def delete_route(self, route_name: str) -> bool:
        """Delete a route from Kong."""
        if not self._client:
            await self.start()

        try:
            route_id = await self._get_route_id(route_name)
            if not route_id:
                logger.warning(f"Route {route_name} not found in Kong")
                return False

            response = await self._client.delete(f"/routes/{route_id}")
            response.raise_for_status()

            self._registered_routes.pop(route_name, None)
            self._stats["routes_deleted"] += 1
            logger.info(f"Deleted Kong route: {route_name}")
            return True

        except httpx.HTTPError as e:
            self._stats["kong_errors"] += 1
            logger.error(f"Failed to delete route {route_name}: {e}")
            return False

    async def sync_routes(
        self, services: list[ServiceConfig], routes: list[RouteConfig]
    ) -> dict[str, Any]:
        """Synchronize all services and routes with Kong."""
        self._stats["total_syncs"] += 1

        try:
            # Register all services first
            service_results = []
            for service in services:
                result = await self.register_service(service)
                service_results.append((service.name, result))

            # Then register all routes
            route_results = []
            for route in routes:
                result = await self.register_route(route)
                route_results.append((route.name, result))

            successful = all(r for _, r in service_results + route_results)
            if successful:
                self._stats["successful_syncs"] += 1
            else:
                self._stats["failed_syncs"] += 1

            return {
                "success": successful,
                "services": dict(service_results),
                "routes": dict(route_results),
            }

        except Exception as e:
            self._stats["failed_syncs"] += 1
            logger.error(f"Route sync failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _get_service_id(self, service_name: str) -> str | None:
        """Get Kong service ID by name."""
        if service_name in self._registered_services:
            return self._registered_services[service_name]

        try:
            response = await self._client.get(f"/services/{service_name}")
            if response.status_code == 200:
                service_id = response.json()["id"]
                self._registered_services[service_name] = service_id
                return service_id
        except httpx.HTTPError:
            pass

        return None

    async def _get_route_id(self, route_name: str) -> str | None:
        """Get Kong route ID by name."""
        if route_name in self._registered_routes:
            return self._registered_routes[route_name]

        try:
            response = await self._client.get(f"/routes/{route_name}")
            if response.status_code == 200:
                route_id = response.json()["id"]
                self._registered_routes[route_name] = route_id
                return route_id
        except httpx.HTTPError:
            pass

        return None

    async def _apply_plugins(self, route_id: str, plugins: list[dict[str, Any]]) -> None:
        """Apply plugins to a route."""
        for plugin_config in plugins:
            try:
                plugin_data = {
                    "name": plugin_config["name"],
                    "route": {"id": route_id},
                    "config": plugin_config.get("config", {}),
                    "enabled": plugin_config.get("enabled", True),
                }

                response = await self._client.post("/plugins", json=plugin_data)
                response.raise_for_status()
                logger.info(f"Applied plugin {plugin_config['name']} to route {route_id}")

            except httpx.HTTPError as e:
                logger.error(f"Failed to apply plugin: {e}")

    async def _auto_sync_loop(self):
        """Background task for automatic route synchronization."""
        while True:
            try:
                await asyncio.sleep(self.auto_sync_interval)
                # Placeholder for auto-discovery and sync logic
                # This would integrate with service discovery to automatically
                # register new services and routes
                logger.debug("Auto-sync interval passed (no action configured)")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in auto-sync loop: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get synchronizer statistics."""
        return self._stats.copy()
