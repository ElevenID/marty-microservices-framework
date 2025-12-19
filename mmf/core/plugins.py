"""
Core Plugin Interfaces.

This module defines the standard interfaces and models for the plugin system.
It is the single source of truth for plugin contracts in the Marty Microservices Framework.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

# --- Core Enums ---


class PluginStatus(Enum):
    """Plugin lifecycle status."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    ERROR = "error"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ServiceStatus(Enum):
    """Service status within a plugin."""

    INACTIVE = "inactive"
    STARTING = "starting"
    ACTIVE = "active"
    STOPPING = "stopping"
    FAILED = "failed"


class RouteMethod(Enum):
    """HTTP methods supported by service routes."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


# --- Core Data Models ---


@dataclass
class PluginMetadata:
    """Plugin metadata and configuration."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)
    api_version: str = "1.0"
    min_mmf_version: str = "1.0.0"
    keywords: list[str] = field(default_factory=list)
    homepage: str = ""
    license: str = ""


@dataclass
class PluginContext:
    """Context passed to plugins during initialization."""

    plugin_id: str
    config: dict[str, Any] = field(default_factory=dict)
    logger: Any = None
    registry: Any = None
    event_bus: Any = None
    metrics: Any = None
    security: Any = None

    def __post_init__(self):
        """Post-initialization setup."""
        if self.logger is None:
            self.logger = logging.getLogger(f"plugin.{self.plugin_id}")


@dataclass
class ServiceDefinition:
    """Definition of a service provided by a plugin."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    endpoint: str = ""
    handler_class: type | None = None
    routes: dict[str, Any] = field(default_factory=dict)
    middleware: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    health_check_path: str = "/health"
    metrics_enabled: bool = True
    database_required: bool = True
    methods: list[RouteMethod] = field(default_factory=list)
    auth_required: bool = True
    rate_limit: int = 0  # requests per minute, 0 = no limit
    timeout: int = 30  # seconds
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate service definition."""
        if not self.name:
            raise ValueError("Service name is required")


@dataclass
class RouteDefinition:
    """HTTP route definition for plugin services."""

    path: str
    method: RouteMethod
    handler_name: str
    description: str = ""
    auth_required: bool = True
    rate_limit: int = 0
    timeout: int = 30
    tags: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    response_model: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginSubscriptionBase:
    """Base class for plugin event subscriptions."""

    plugin_name: str
    event_type: str
    handler: Callable[[Any], Any]
    active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class PluginError(Exception):
    """Plugin-related errors."""

    def __init__(self, message: str, plugin_name: str | None = None):
        super().__init__(message)
        self.plugin_name = plugin_name


# --- Core Interfaces ---


@runtime_checkable
class PluginInterface(Protocol):
    """Protocol for all plugins."""

    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        ...

    def get_service_definitions(self) -> list[ServiceDefinition]:
        """Get list of services provided by this plugin."""
        ...

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the plugin."""
        ...

    async def start(self) -> None:
        """Start the plugin."""
        ...

    async def stop(self) -> None:
        """Stop the plugin."""
        ...

    async def cleanup(self) -> None:
        """Clean up plugin resources."""
        ...


class IPluginManager(ABC):
    """Interface for plugin management."""

    @abstractmethod
    async def discover_plugins(self, paths: list[str]) -> list[str]:
        """Discover available plugins in the given paths."""

    @abstractmethod
    async def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin."""

    @abstractmethod
    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin."""

    @abstractmethod
    async def start_plugin(self, plugin_name: str) -> bool:
        """Start a specific plugin."""

    @abstractmethod
    async def stop_plugin(self, plugin_name: str) -> bool:
        """Stop a specific plugin."""

    @abstractmethod
    def get_plugin_status(self, plugin_name: str) -> PluginStatus:
        """Get the status of a specific plugin."""

    @abstractmethod
    def list_plugins(self) -> dict[str, PluginStatus]:
        """List all plugins and their statuses."""

    @abstractmethod
    def get_plugin_metadata(self, plugin_name: str) -> PluginMetadata | None:
        """Get metadata for a specific plugin."""


class IServiceManager(ABC):
    """Interface for service management within plugins."""

    @abstractmethod
    async def register_service(
        self, plugin_name: str, service_definition: ServiceDefinition
    ) -> bool:
        """Register a service with the plugin system."""

    @abstractmethod
    async def unregister_service(self, plugin_name: str, service_name: str) -> bool:
        """Unregister a service from the plugin system."""

    @abstractmethod
    async def get_service(self, plugin_name: str, service_name: str) -> ServiceDefinition | None:
        """Get a registered service definition."""

    @abstractmethod
    async def list_services(
        self, plugin_name: str | None = None
    ) -> dict[str, list[ServiceDefinition]]:
        """List all registered services, optionally filtered by plugin."""

    @abstractmethod
    async def get_service_status(self, plugin_name: str, service_name: str) -> ServiceStatus:
        """Get the status of a specific service."""


class IPluginDiscovery(ABC):
    """Interface for plugin discovery mechanisms."""

    @abstractmethod
    async def discover(self, discovery_paths: list[str]) -> list[str]:
        """Discover plugins in the specified paths."""

    @abstractmethod
    def validate_plugin(self, plugin_path: str) -> bool:
        """Validate that a discovered item is a valid plugin."""

    @abstractmethod
    def get_plugin_info(self, plugin_path: str) -> PluginMetadata | None:
        """Extract plugin metadata from a plugin path."""


class IPluginLoader(ABC):
    """Interface for plugin loading mechanisms."""

    @abstractmethod
    async def load(self, plugin_name: str, plugin_path: str) -> PluginInterface:
        """Load a plugin from the specified path."""

    @abstractmethod
    async def unload(self, plugin_name: str) -> bool:
        """Unload a previously loaded plugin."""

    @abstractmethod
    def is_loaded(self, plugin_name: str) -> bool:
        """Check if a plugin is currently loaded."""


class IPluginRegistry(ABC):
    """Interface for plugin registry operations."""

    @abstractmethod
    def register(self, plugin_name: str, plugin: PluginInterface, metadata: PluginMetadata) -> bool:
        """Register a plugin instance."""

    @abstractmethod
    def unregister(self, plugin_name: str) -> bool:
        """Unregister a plugin."""

    @abstractmethod
    def get_plugin(self, plugin_name: str) -> PluginInterface | None:
        """Get a registered plugin instance."""

    @abstractmethod
    def get_metadata(self, plugin_name: str) -> PluginMetadata | None:
        """Get plugin metadata."""

    @abstractmethod
    def get_all_plugins(self) -> dict[str, PluginInterface]:
        """Get all registered plugins."""

    @abstractmethod
    def get_all_metadata(self) -> dict[str, PluginMetadata]:
        """Get metadata for all registered plugins."""


class IPluginEventSubscriptionManager(ABC):
    """Interface for plugin event subscription management."""

    @abstractmethod
    async def subscribe(
        self, plugin_name: str, event_type: str, handler: Callable[[Any], Any]
    ) -> bool:
        """Subscribe plugin to an event type."""

    @abstractmethod
    async def unsubscribe(self, plugin_name: str, event_type: str) -> bool:
        """Unsubscribe plugin from an event type."""

    @abstractmethod
    async def publish_event(self, event_type: str, event_data: Any) -> None:
        """Publish event to subscribed plugins."""


# --- Plugin Base Classes ---


class PluginService(ABC):
    """Base class for plugin services.

    Plugin services are the actual implementation of business logic
    that plugins provide. They have access to the MMF context and
    can use all infrastructure services.
    """

    def __init__(self, context: PluginContext | None = None):
        self.context: PluginContext | None = context
        self._logger = logging.getLogger(f"service.{self.__class__.__name__}")

    @property
    def logger(self) -> logging.Logger:
        """Service-specific logger."""
        return self._logger

    async def initialize(self) -> None:
        """Initialize the service.

        Override this method to perform service-specific initialization.
        Called after the service is registered but before it starts
        handling requests.
        """

    async def shutdown(self) -> None:
        """Shutdown the service and cleanup resources.

        Override this method to perform service-specific cleanup.
        """

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for this service.

        Returns:
            Dictionary with health status information
        """
        return {
            "status": "healthy",
            "service": self.__class__.__name__,
            "timestamp": time.time(),
        }


class BasePlugin(ABC):
    """Abstract base class for all plugins."""

    def __init__(self):
        self._status = PluginStatus.UNLOADED
        self._context: PluginContext | None = None
        # Logger will be initialized properly when metadata is available or context is set
        self._logger = logging.getLogger("plugin.base")

    @property
    def status(self) -> PluginStatus:
        """Get current plugin status."""
        return self._status

    @property
    def context(self) -> PluginContext:
        """Get plugin context (only available after initialization)."""
        if not self._context:
            # Try to get name safely
            try:
                name = self.get_metadata().name
            except Exception:
                name = "unknown"

            raise PluginError("Plugin context not available before initialization", name)
        return self._context

    @property
    def logger(self) -> logging.Logger:
        """Plugin-specific logger."""
        return self._logger

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""

    @abstractmethod
    def get_service_definitions(self) -> list[ServiceDefinition]:
        """Get list of services provided by this plugin."""

    async def initialize(self, context: PluginContext) -> None:
        """Initialize the plugin with context."""
        self._context = context
        self._logger = context.logger or logging.getLogger(f"plugin.{self.get_metadata().name}")
        self._status = PluginStatus.INITIALIZING

        try:
            await self._do_initialize()
            self._status = PluginStatus.LOADED
            self.logger.info(f"Plugin {self.get_metadata().name} initialized successfully")
        except Exception as e:
            self._status = PluginStatus.ERROR
            self.logger.error(f"Plugin {self.get_metadata().name} initialization failed: {e}")
            raise PluginError(f"Failed to initialize plugin: {e}", self.get_metadata().name)

    async def start(self) -> None:
        """Start the plugin."""
        if self._status != PluginStatus.LOADED:
            raise RuntimeError(
                f"Plugin must be loaded before starting. Current status: {self._status}"
            )

        await self._do_start()
        self._status = PluginStatus.ACTIVE

    async def stop(self) -> None:
        """Stop the plugin."""
        if self._status == PluginStatus.ACTIVE:
            self._status = PluginStatus.STOPPING
            await self._do_stop()
            self._status = PluginStatus.STOPPED

    async def cleanup(self) -> None:
        """Clean up plugin resources."""
        await self._do_cleanup()
        self._status = PluginStatus.UNLOADED
        self._context = None

    @abstractmethod
    async def _do_initialize(self) -> None:
        """Plugin-specific initialization logic."""

    @abstractmethod
    async def _do_start(self) -> None:
        """Plugin-specific startup logic."""

    @abstractmethod
    async def _do_stop(self) -> None:
        """Plugin-specific shutdown logic."""

    @abstractmethod
    async def _do_cleanup(self) -> None:
        """Plugin-specific cleanup logic."""

    def get_configuration_schema(self) -> dict[str, Any]:
        """Return configuration schema for this plugin.

        Override this method to define the configuration structure
        that this plugin expects.
        """
        return {}


# Compatibility Alias
MMFPlugin = BasePlugin

__all__ = [
    "PluginStatus",
    "ServiceStatus",
    "RouteMethod",
    "PluginMetadata",
    "PluginContext",
    "ServiceDefinition",
    "RouteDefinition",
    "PluginSubscriptionBase",
    "PluginError",
    "PluginInterface",
    "IPluginManager",
    "IServiceManager",
    "IPluginDiscovery",
    "IPluginLoader",
    "IPluginRegistry",
    "IPluginEventSubscriptionManager",
    "PluginService",
    "BasePlugin",
    "MMFPlugin",
]
