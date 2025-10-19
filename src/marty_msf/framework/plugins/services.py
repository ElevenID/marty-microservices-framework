"""
Service management for MMF plugins.

This module provides the infrastructure for plugins to define and register
services, routes, and endpoints that integrate with MMF's web framework
and service discovery mechanisms.
"""

import asyncio
import logging
from abc import ABC
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from .core import PluginContext, PluginManager

logger = logging.getLogger(__name__)


class RouteMethod(Enum):
    """HTTP methods supported by service routes."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


@dataclass
class Route:
    """Service route definition."""

    path: str
    methods: list[RouteMethod] = field(default_factory=lambda: [RouteMethod.GET])
    handler: Callable | None = None
    middleware: list[str] = field(default_factory=list)
    auth_required: bool = True
    rate_limit: dict[str, Any] | None = None
    description: str = ""

    def __post_init__(self):
        """Validate route configuration."""
        if not self.path.startswith("/"):
            self.path = f"/{self.path}"


@dataclass
class ServiceMountInfo:
    """Information about mounted service routes."""

    plugin_name: str
    service_name: str
    routes: dict[str, Any]


@dataclass
class ServiceDefinition:
    """Definition of a service provided by a plugin."""

    name: str
    handler_class: type = None
    routes: dict[str, Any] = field(default_factory=dict)
    middleware: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    health_check_path: str = "/health"
    metrics_enabled: bool = True
    database_required: bool = True
    description: str = ""
    version: str = "1.0.0"

    def __post_init__(self):
        """Validate service definition."""
        if not self.name:
            raise ValueError("Service name is required")
        # handler_class is optional for testing but required for actual service registration


class PluginService(ABC):
    """Base class for plugin services.

    Plugin services are the actual implementation of business logic
    that plugins provide. They have access to the MMF context and
    can use all infrastructure services.
    """

    def __init__(self, context: "PluginContext" = None):

        self.context: PluginContext = context
        self.logger = logging.getLogger(f"service.{self.__class__.__name__}")

    async def initialize(self) -> None:
        """Initialize the service.

        Override this method to perform service-specific initialization.
        Called after the service is registered but before it starts
        handling requests.
        """
        pass

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources.

        Override this method to perform service-specific cleanup.
        """
        pass

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for this service.

        Returns:
            Dictionary with health status information
        """
        return {
            "status": "healthy",
            "service": self.__class__.__name__,
            "timestamp": asyncio.get_event_loop().time(),
        }


class ServiceRegistry:
    """Registry for managing plugin services."""

    def __init__(self, plugin_manager: "PluginManager"):

        self.plugin_manager: PluginManager = plugin_manager
        self.services: dict[str, ServiceDefinition] = {}
        self.service_instances: dict[str, PluginService] = {}
        self.service_definitions: dict[str, ServiceDefinition] = {}
        self.plugin_services: dict[str, str] = {}
        self._logger = logging.getLogger("service.registry")

    async def register_plugin_services(self, plugin_name: str) -> None:
        """Register all services provided by a plugin.

        Args:
            plugin_name: Name of the plugin whose services to register
        """
        plugin = self.plugin_manager.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin {plugin_name} not found")

        service_definitions = plugin.get_service_definitions()

        for service_def in service_definitions:
            await self._register_service(service_def, plugin_name)

    async def register_service(
        self, plugin_name: str, service_def: ServiceDefinition, service_instance: PluginService
    ) -> None:
        """Register a service with provided instance (mainly for testing).

        Args:
            plugin_name: Name of the plugin providing the service
            service_def: Service definition
            service_instance: Service instance to register

        Raises:
            ValueError: If service is already registered or dependency not found
        """
        # Check for duplicate registration
        if service_def.name in self.services:
            raise ValueError(f"Service '{service_def.name}' is already registered")

        # Validate dependencies
        for dep in service_def.dependencies:
            if dep not in self.services:
                raise ValueError(f"Service dependency not found: {dep}")

        # Set context if available
        if hasattr(service_instance, "context") and service_instance.context is None:
            plugin = self.plugin_manager.get_plugin(plugin_name)
            if plugin and hasattr(plugin, "context"):
                service_instance.context = plugin.context

        # Initialize service
        await service_instance.initialize()

        # Register service
        self.services[service_def.name] = service_def
        self.service_instances[service_def.name] = service_instance
        self.service_definitions[service_def.name] = service_def
        self.plugin_services[service_def.name] = plugin_name

        self._logger.info(f"Registered service: {service_def.name} from plugin {plugin_name}")

    async def _register_service(self, service_def: ServiceDefinition, plugin_name: str) -> None:
        """Register a single service.

        Args:
            service_def: Service definition to register
            plugin_name: Name of the plugin providing the service
        """
        # Validate dependencies
        for dep in service_def.dependencies:
            if dep not in self.services:
                raise ValueError(f"Service dependency not found: {dep}")

        # Create service instance
        plugin = self.plugin_manager.get_plugin(plugin_name)
        service_instance = service_def.handler_class(plugin.context)

        # Initialize service
        await service_instance.initialize()

        # Register service
        self.services[service_def.name] = service_def
        self.service_instances[service_def.name] = service_instance

        self._logger.info(f"Registered service: {service_def.name} from plugin {plugin_name}")

    async def unregister_service(self, service_name: str) -> None:
        """Unregister a service.

        Args:
            service_name: Name of service to unregister
        """
        if service_name not in self.services:
            raise ValueError(f"Service {service_name} not registered")

        # Shutdown service instance
        service_instance = self.service_instances.get(service_name)
        if service_instance:
            await service_instance.shutdown()

        # Remove from registry
        del self.services[service_name]
        if service_name in self.service_instances:
            del self.service_instances[service_name]

        self._logger.info(f"Unregistered service: {service_name}")

    def get_service(self, service_name: str) -> PluginService | None:
        """Get a service instance by name.

        Args:
            service_name: Name of service to retrieve

        Returns:
            Service instance or None if not found
        """
        return self.service_instances.get(service_name)

    def get_service_definition(self, service_name: str) -> ServiceDefinition | None:
        """Get a service definition by name.

        Args:
            service_name: Name of service

        Returns:
            Service definition or None if not found
        """
        return self.services.get(service_name)

    def get_all_services(self) -> dict[str, ServiceDefinition]:
        """Get all registered services."""
        return self.services.copy()

    def get_service_info(self) -> list[dict[str, Any]]:
        """Get detailed information about all registered services.

        Returns:
            List of dictionaries with service information
        """
        service_info = []

        for service_name, service_def in self.services.items():
            service_instance = self.service_instances.get(service_name)

            service_info.append(
                {
                    "name": service_def.name,
                    "version": service_def.version,
                    "description": service_def.description,
                    "routes": service_def.routes,
                    "health_check_path": service_def.health_check_path,
                    "metrics_enabled": service_def.metrics_enabled,
                    "database_required": service_def.database_required,
                    "dependencies": service_def.dependencies,
                    "middleware": service_def.middleware,
                    "instance_available": service_instance is not None,
                    "plugin": self.plugin_services.get(service_name, "unknown"),
                }
            )

        return service_info

    def get_services_by_plugin(self, plugin_name: str) -> list[str]:
        """Get list of service names provided by a plugin.

        Args:
            plugin_name: Name of plugin

        Returns:
            List of service names
        """
        plugin = self.plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return []

        service_definitions = plugin.get_service_definitions()
        return [service_def.name for service_def in service_definitions]

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        """Perform health check on all services.

        Returns:
            Dictionary mapping service names to health check results
        """
        health_results = {}

        for service_name, service_instance in self.service_instances.items():
            try:
                health_result = await service_instance.health_check()
                health_results[service_name] = health_result
            except Exception as e:
                health_results[service_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "service": service_name,
                }

        return health_results

    async def start_all_services(self) -> None:
        """Start all registered services."""
        for service_name, service_instance in self.service_instances.items():
            try:
                await service_instance.start()
                self._logger.info(f"Started service: {service_name}")
            except Exception as e:
                self._logger.error(f"Failed to start service {service_name}: {e}")
                raise

    async def stop_all_services(self) -> None:
        """Stop all registered services."""
        for service_name, service_instance in self.service_instances.items():
            try:
                await service_instance.stop()
                self._logger.info(f"Stopped service: {service_name}")
            except Exception as e:
                self._logger.error(f"Failed to stop service {service_name}: {e}")
                # Continue stopping other services even if one fails

    def get_mount_info(self) -> list[ServiceMountInfo]:
        """Get mount information for all registered services.

        Returns:
            List of ServiceMountInfo objects with plugin and route information
        """
        mount_info = []

        for service_name, service_def in self.services.items():
            plugin_name = self.plugin_services.get(service_name, "unknown")

            mount_info.append(
                ServiceMountInfo(
                    plugin_name=plugin_name, service_name=service_name, routes=service_def.routes
                )
            )

        return mount_info

    async def get_health_status(self) -> dict[str, Any]:
        """Get health status for all services.

        Returns:
            Dictionary mapping service names to their health status
        """
        return await self.health_check_all()

    async def shutdown_all(self) -> None:
        """Shutdown all registered services."""
        for service_name in list(self.service_instances.keys()):
            try:
                await self.unregister_service(service_name)
            except Exception as e:
                self._logger.error(f"Error shutting down service {service_name}: {e}")


def create_route(
    path: str,
    methods: list[str | RouteMethod] = None,
    handler: Callable = None,
    middleware: list[str] = None,
    auth_required: bool = True,
    rate_limit: dict[str, Any] = None,
    description: str = "",
) -> Route:
    """Create a route definition.

    Args:
        path: Route path
        methods: HTTP methods (defaults to GET)
        handler: Route handler function
        middleware: List of middleware names
        auth_required: Whether authentication is required
        rate_limit: Rate limiting configuration
        description: Route description

    Returns:
        Route definition
    """
    if methods is None:
        methods = [RouteMethod.GET]
    else:
        # Convert string methods to RouteMethod enum
        methods = [RouteMethod(m) if isinstance(m, str) else m for m in methods]

    return Route(
        path=path,
        methods=methods,
        handler=handler,
        middleware=middleware or [],
        auth_required=auth_required,
        rate_limit=rate_limit,
        description=description,
    )
