"""
Core plugin system for the Marty Microservices Framework.

This module provides the foundation for a plugin-based architecture that allows
external applications to integrate with MMF infrastructure while maintaining
clean separation of concerns.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

from marty_msf.framework.config import PluginConfigManager

from .services import ServiceDefinition

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin lifecycle status."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


class PluginError(Exception):
    """Plugin-related errors."""

    def __init__(self, message: str, plugin_name: str | None = None):
        super().__init__(message)
        self.plugin_name = plugin_name


@dataclass
class PluginMetadata:
    """Plugin metadata and configuration."""

    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: list[str] = field(default_factory=list)
    optional_dependencies: list[str] = field(default_factory=list)
    mmf_version_required: str = "1.0.0"
    python_version_required: str = "3.10"
    tags: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate metadata after creation."""
        if not self.name:
            raise ValueError("Plugin name is required")
        if not self.version:
            raise ValueError("Plugin version is required")


class PluginContext:
    """Context provided by MMF to plugins during initialization.

    This context gives plugins access to all MMF infrastructure components
    while maintaining proper abstraction and lifecycle management.
    """

    def __init__(
        self,
        config,
        config_manager: Optional["PluginConfigManager"] = None,
        database_manager=None,
        event_bus=None,
        security_manager=None,
        observability_manager=None,
        cache_manager=None,
        http_client=None,
        workflow_engine=None,
        resilience_manager=None,
    ):
        self.config = config
        self.config_manager = config_manager
        self.database = database_manager
        self.event_bus = event_bus
        self.security = security_manager
        self.observability = observability_manager
        self.cache = cache_manager
        self.http_client = http_client
        self.workflow_engine = workflow_engine
        self.resilience = resilience_manager

        # Plugin-specific storage
        self._plugin_data: dict[str, Any] = {}

    async def get_plugin_config(self, plugin_name: str, config_key: str = "default") -> Any:
        """Get configuration specific to a plugin using the config manager."""
        if self.config_manager:
            return await self.config_manager.get_plugin_config(plugin_name, config_key)

        # No config manager available
        return {}

    async def get_base_config(self, config_key: str = "default") -> Any:
        """Get base MMF configuration."""
        if self.config_manager:
            return await self.config_manager.get_base_config(config_key)
        return self.config

    def set_plugin_data(self, plugin_name: str, key: str, value: Any) -> None:
        """Store plugin-specific data."""
        if plugin_name not in self._plugin_data:
            self._plugin_data[plugin_name] = {}
        self._plugin_data[plugin_name][key] = value

    def get_plugin_data(self, plugin_name: str, key: str, default: Any = None) -> Any:
        """Retrieve plugin-specific data."""
        return self._plugin_data.get(plugin_name, {}).get(key, default)


class MMFPlugin(ABC):
    """Base class for all MMF plugins.

    Plugins extend MMF with domain-specific functionality while using
    MMF's infrastructure for cross-cutting concerns like database access,
    security, observability, etc.
    """

    def __init__(self):
        self._context: PluginContext | None = None
        self._status = PluginStatus.UNLOADED
        self._logger = logging.getLogger(f"plugin.{self.metadata.name}")

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Plugin metadata including name, version, and dependencies."""
        pass

    @property
    def context(self) -> PluginContext:
        """Access to MMF context (only available after initialization)."""
        if not self._context:
            raise PluginError(
                "Plugin context not available before initialization", self.metadata.name
            )
        return self._context

    @property
    def status(self) -> PluginStatus:
        """Current plugin status."""
        return self._status

    @property
    def logger(self) -> logging.Logger:
        """Plugin-specific logger."""
        return self._logger

    async def initialize(self, context: PluginContext) -> None:
        """Initialize plugin with MMF context.

        This method is called by the PluginManager after the plugin is loaded.
        Override this method to perform plugin-specific initialization.

        Args:
            context: MMF context with access to infrastructure components
        """
        self._context = context
        self._status = PluginStatus.INITIALIZING

        try:
            await self._initialize_plugin()
            self._status = PluginStatus.ACTIVE
            self.logger.info(f"Plugin {self.metadata.name} initialized successfully")
        except Exception as e:
            self._status = PluginStatus.ERROR
            self.logger.error(f"Plugin {self.metadata.name} initialization failed: {e}")
            raise PluginError(f"Failed to initialize plugin: {e}", self.metadata.name)

    async def _initialize_plugin(self) -> None:
        """Override this method for plugin-specific initialization logic."""
        pass

    async def shutdown(self) -> None:
        """Shutdown plugin and cleanup resources."""
        try:
            await self._shutdown_plugin()
            self._status = PluginStatus.UNLOADED
            self.logger.info(f"Plugin {self.metadata.name} shutdown successfully")
        except Exception as e:
            self.logger.error(f"Plugin {self.metadata.name} shutdown failed: {e}")
            raise PluginError(f"Failed to shutdown plugin: {e}", self.metadata.name)

    async def _shutdown_plugin(self) -> None:
        """Override this method for plugin-specific cleanup logic."""
        pass

    def get_service_definitions(self) -> list["ServiceDefinition"]:
        """Return list of services provided by this plugin.

        Override this method to register services that should be
        exposed by the plugin.
        """
        return []

    def get_configuration_schema(self) -> dict[str, Any]:
        """Return configuration schema for this plugin.

        Override this method to define the configuration structure
        that this plugin expects.
        """
        return {}


class PluginManager:
    """Manages plugin lifecycle, dependencies, and coordination."""

    def __init__(self, context: PluginContext):
        self.context = context
        self.plugins: dict[str, MMFPlugin] = {}
        self.plugin_metadata: dict[str, PluginMetadata] = {}
        self.plugin_order: list[str] = []
        self._logger = logging.getLogger("plugin.manager")

    async def load_plugin(self, plugin_class: type[MMFPlugin]) -> None:
        """Load and initialize a plugin.

        Args:
            plugin_class: Plugin class to instantiate and load
        """
        plugin = plugin_class()
        plugin_name = plugin.metadata.name

        self._logger.info(f"Loading plugin: {plugin_name}")

        # Check dependencies
        await self._check_dependencies(plugin)

        # Initialize plugin
        try:
            await plugin.initialize(self.context)
            self.plugins[plugin_name] = plugin
            self.plugin_order.append(plugin_name)

            self._logger.info(f"Plugin {plugin_name} loaded successfully")

        except Exception as e:
            self._logger.error(f"Failed to load plugin {plugin_name}: {e}")
            raise PluginError(f"Failed to load plugin {plugin_name}: {e}")

    async def register_plugin(
        self, plugin_name: str, plugin: MMFPlugin, metadata: PluginMetadata | None = None
    ) -> None:
        """Register a plugin instance.

        Args:
            plugin_name: Name to register plugin under
            plugin: Plugin instance to register
            metadata: Optional metadata (will use plugin.metadata if not provided)
        """
        if plugin_name in self.plugins:
            raise PluginError(f"Plugin {plugin_name} is already registered")

        self._logger.info(f"Registering plugin: {plugin_name}")

        # Use provided metadata or plugin's own metadata
        if metadata is not None:
            # Override plugin metadata if provided
            plugin._metadata = metadata
            self.plugin_metadata[plugin_name] = metadata
        else:
            self.plugin_metadata[plugin_name] = plugin.metadata

        # Check dependencies
        await self._check_dependencies(plugin)

        # Initialize plugin
        try:
            await plugin.initialize(self.context)
            self.plugins[plugin_name] = plugin
            self.plugin_order.append(plugin_name)

            self._logger.info(f"Plugin {plugin_name} registered successfully")

        except Exception as e:
            self._logger.error(f"Failed to register plugin {plugin_name}: {e}")
            # Clean up metadata if registration failed
            if plugin_name in self.plugin_metadata:
                del self.plugin_metadata[plugin_name]
            raise PluginError(f"Failed to register plugin {plugin_name}: {e}")

    async def start_all_plugins(self) -> None:
        """Start all registered plugins."""
        for plugin_name in self.plugin_order:
            plugin = self.plugins[plugin_name]
            try:
                await plugin.start()
                self._logger.info(f"Plugin {plugin_name} started successfully")
            except Exception as e:
                self._logger.error(f"Failed to start plugin {plugin_name}: {e}")
                raise PluginError(f"Failed to start plugin {plugin_name}: {e}")

    async def stop_all_plugins(self) -> None:
        """Stop all registered plugins."""
        # Stop in reverse order to handle dependencies
        for plugin_name in reversed(self.plugin_order):
            plugin = self.plugins[plugin_name]
            try:
                await plugin.stop()
                self._logger.info(f"Plugin {plugin_name} stopped successfully")
            except Exception as e:
                self._logger.error(f"Failed to stop plugin {plugin_name}: {e}")
                # Continue stopping other plugins even if one fails

    async def get_health_status(self) -> dict[str, Any]:
        """Get health status of all plugins.

        Returns:
            Dictionary with plugin health information
        """
        health_status = {}
        for plugin_name, plugin in self.plugins.items():
            try:
                health_status[plugin_name] = await plugin.get_health_status()
            except Exception as e:
                health_status[plugin_name] = {"status": "error", "error": str(e)}
        return health_status

    async def unload_plugin(self, plugin_name: str) -> None:
        """Unload a plugin and cleanup resources.

        Args:
            plugin_name: Name of plugin to unload
        """
        if plugin_name not in self.plugins:
            raise PluginError(f"Plugin {plugin_name} not loaded")

        plugin = self.plugins[plugin_name]

        try:
            await plugin.shutdown()
            del self.plugins[plugin_name]
            if plugin_name in self.plugin_metadata:
                del self.plugin_metadata[plugin_name]
            self.plugin_order.remove(plugin_name)

            self._logger.info(f"Plugin {plugin_name} unloaded successfully")

        except Exception as e:
            self._logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            raise PluginError(f"Failed to unload plugin {plugin_name}: {e}")

    async def reload_plugin(self, plugin_name: str, plugin_class: type[MMFPlugin]) -> None:
        """Reload a plugin with new implementation.

        Args:
            plugin_name: Name of plugin to reload
            plugin_class: New plugin class implementation
        """
        if plugin_name in self.plugins:
            await self.unload_plugin(plugin_name)

        await self.load_plugin(plugin_class)

    def get_plugin(self, plugin_name: str) -> MMFPlugin | None:
        """Get a loaded plugin by name.

        Args:
            plugin_name: Name of plugin to retrieve

        Returns:
            Plugin instance or None if not found
        """
        return self.plugins.get(plugin_name)

    def get_loaded_plugins(self) -> list[str]:
        """Get list of loaded plugin names."""
        return list(self.plugins.keys())

    def get_plugin_info(self) -> list[dict[str, Any]]:
        """Get information about all loaded plugins.

        Returns:
            List of plugin information dictionaries
        """
        info = []
        for _plugin_name, plugin in self.plugins.items():
            metadata = plugin.metadata
            info.append(
                {
                    "name": metadata.name,
                    "version": metadata.version,
                    "description": metadata.description,
                    "author": metadata.author,
                    "status": plugin.status.value,
                    "dependencies": metadata.dependencies,
                    "optional_dependencies": metadata.optional_dependencies,
                }
            )
        return info

    def get_plugin_status(self, plugin_name: str) -> PluginStatus | None:
        """Get status of a plugin.

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin status or None if not found
        """
        plugin = self.get_plugin(plugin_name)
        return plugin.status if plugin else None

    async def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        # Shutdown in reverse order to handle dependencies
        for plugin_name in reversed(self.plugin_order):
            try:
                await self.unload_plugin(plugin_name)
            except Exception as e:
                self._logger.error(f"Error shutting down plugin {plugin_name}: {e}")

    async def _check_dependencies(self, plugin: MMFPlugin) -> None:
        """Check if plugin dependencies are satisfied.

        Args:
            plugin: Plugin to check dependencies for
        """
        missing_deps = []

        for dep in plugin.metadata.dependencies:
            if dep not in self.plugins:
                missing_deps.append(dep)

        if missing_deps:
            raise PluginError(
                f"Plugin {plugin.metadata.name} has missing dependencies: {missing_deps}",
                plugin.metadata.name,
            )


def create_plugin_context(config, **services) -> PluginContext:
    """Create a plugin context with provided services.

    Args:
        config: Configuration object
        **services: Named service instances

    Returns:
        Configured PluginContext
    """
    return PluginContext(
        config=config,
        database_manager=services.get("database"),
        event_bus=services.get("event_bus"),
        security_manager=services.get("security"),
        observability_manager=services.get("observability"),
        cache_manager=services.get("cache"),
        http_client=services.get("http_client"),
        workflow_engine=services.get("workflow_engine"),
        resilience_manager=services.get("resilience"),
    )
