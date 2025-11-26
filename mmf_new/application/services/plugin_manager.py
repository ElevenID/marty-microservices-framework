"""
Plugin Manager Service

This module provides the high-level service for managing plugins,
orchestrating discovery, loading, and registration.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any
from collections.abc import Callable

from mmf_new.framework.plugins.ports import (
    IPluginManager,
    IServiceManager,
    IPluginDiscovery,
    IPluginLoader,
    IPluginRegistry,
    IPluginEventSubscriptionManager,
)
from mmf_new.framework.plugins.models import (
    PluginStatus,
    ServiceStatus,
    PluginMetadata,
    PluginContext,
    ServiceDefinition,
    PluginSubscriptionBase,
)
from mmf_new.framework.infrastructure.plugins.discovery import PluginDiscovery
from mmf_new.framework.infrastructure.plugins.loader import PluginLoader
from mmf_new.framework.infrastructure.plugins.registry import PluginRegistry


class ServiceManager(IServiceManager):
    """Default service manager implementation."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)
        self._services: dict[str, dict[str, ServiceDefinition]] = {}
        self._service_status: dict[str, dict[str, ServiceStatus]] = {}

    async def register_service(self, plugin_name: str, service_definition: ServiceDefinition) -> bool:
        """Register a service with the plugin system."""
        try:
            if plugin_name not in self._services:
                self._services[plugin_name] = {}
                self._service_status[plugin_name] = {}
            
            service_name = service_definition.name
            self._services[plugin_name][service_name] = service_definition
            self._service_status[plugin_name][service_name] = ServiceStatus.INACTIVE
            
            self.logger.info(f"Registered service {service_name} for plugin {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register service {service_definition.name} for plugin {plugin_name}: {e}")
            return False

    async def unregister_service(self, plugin_name: str, service_name: str) -> bool:
        """Unregister a service from the plugin system."""
        try:
            if plugin_name in self._services and service_name in self._services[plugin_name]:
                del self._services[plugin_name][service_name]
                del self._service_status[plugin_name][service_name]
                
                self.logger.info(f"Unregistered service {service_name} for plugin {plugin_name}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to unregister service {service_name} for plugin {plugin_name}: {e}")
            return False

    async def get_service(self, plugin_name: str, service_name: str) -> ServiceDefinition | None:
        """Get a registered service definition."""
        return self._services.get(plugin_name, {}).get(service_name)

    async def list_services(self, plugin_name: str | None = None) -> dict[str, list[ServiceDefinition]]:
        """List all registered services, optionally filtered by plugin."""
        if plugin_name:
            plugin_services = self._services.get(plugin_name, {})
            return {plugin_name: list(plugin_services.values())}
        
        result = {}
        for plugin, services in self._services.items():
            result[plugin] = list(services.values())
        
        return result

    async def get_service_status(self, plugin_name: str, service_name: str) -> ServiceStatus:
        """Get the status of a specific service."""
        return self._service_status.get(plugin_name, {}).get(service_name, ServiceStatus.INACTIVE)


class PluginEventSubscriptionManager(IPluginEventSubscriptionManager):
    """Plugin event subscription management implementation."""
    
    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)
        self.subscriptions: dict[str, list[PluginSubscriptionBase]] = {}  # event_type -> list of subscriptions
        self.plugin_subscriptions: dict[str, list[str]] = {}  # plugin_name -> list of event_types
    
    async def subscribe(self, plugin_name: str, event_type: str, handler: Callable[[Any], Any]) -> bool:
        """Subscribe plugin to an event type."""
        
        subscription = PluginSubscriptionBase(
            plugin_name=plugin_name,
            event_type=event_type,
            handler=handler
        )
        
        if event_type not in self.subscriptions:
            self.subscriptions[event_type] = []
        self.subscriptions[event_type].append(subscription)
        
        if plugin_name not in self.plugin_subscriptions:
            self.plugin_subscriptions[plugin_name] = []
        self.plugin_subscriptions[plugin_name].append(event_type)
        
        self.logger.info(f"Plugin {plugin_name} subscribed to event {event_type}")
        return True
    
    async def unsubscribe(self, plugin_name: str, event_type: str) -> bool:
        """Unsubscribe plugin from an event type."""
        if event_type in self.subscriptions:
            self.subscriptions[event_type] = [
                sub for sub in self.subscriptions[event_type] 
                if sub.plugin_name != plugin_name
            ]
        
        if plugin_name in self.plugin_subscriptions and event_type in self.plugin_subscriptions[plugin_name]:
            self.plugin_subscriptions[plugin_name].remove(event_type)
        
        self.logger.info(f"Plugin {plugin_name} unsubscribed from event {event_type}")
        return True
    
    async def publish_event(self, event_type: str, event_data: Any) -> None:
        """Publish event to subscribed plugins."""
        if event_type not in self.subscriptions:
            return
        
        for subscription in self.subscriptions[event_type]:
            if subscription.active:
                try:
                    await subscription.handler(event_data)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {subscription.plugin_name}: {e}")


class PluginManager(IPluginManager):
    """Default plugin manager implementation."""

    def __init__(
        self,
        discovery: IPluginDiscovery | None = None,
        loader: IPluginLoader | None = None,
        registry: IPluginRegistry | None = None,
        service_manager: IServiceManager | None = None,
        event_manager: IPluginEventSubscriptionManager | None = None,
        logger: logging.Logger | None = None
    ):
        self.logger = logger or logging.getLogger(__name__)
        self.discovery = discovery or PluginDiscovery(self.logger)
        self.loader = loader or PluginLoader(self.logger)
        self.registry = registry or PluginRegistry(self.logger)
        self.service_manager = service_manager or ServiceManager(self.logger)
        self.event_manager = event_manager or PluginEventSubscriptionManager(self.logger)
        
        self._plugin_status: dict[str, PluginStatus] = {}
        self._plugin_paths: dict[str, str] = {}

    async def discover_plugins(self, paths: list[str]) -> list[str]:
        """Discover available plugins in the given paths."""
        return await self.discovery.discover(paths)

    async def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin."""
        try:
            if plugin_name in self._plugin_status:
                self.logger.warning(f"Plugin {plugin_name} is already loaded")
                return False
            
            plugin_path = self._plugin_paths.get(plugin_name)
            if not plugin_path:
                self.logger.error(f"Plugin path not found for {plugin_name}")
                return False
            
            self._plugin_status[plugin_name] = PluginStatus.LOADING
            
            # Load the plugin
            plugin = await self.loader.load(plugin_name, plugin_path)
            metadata = plugin.get_metadata()
            
            # Register the plugin
            if not self.registry.register(plugin_name, plugin, metadata):
                self._plugin_status[plugin_name] = PluginStatus.ERROR
                return False
            
            # Register services
            services = plugin.get_service_definitions()
            for service in services:
                await self.service_manager.register_service(plugin_name, service)
            
            self._plugin_status[plugin_name] = PluginStatus.LOADED
            self.logger.info(f"Successfully loaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load plugin {plugin_name}: {e}")
            self._plugin_status[plugin_name] = PluginStatus.ERROR
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin."""
        try:
            if plugin_name not in self._plugin_status:
                return False
            
            # Stop plugin if running
            if self._plugin_status[plugin_name] == PluginStatus.ACTIVE:
                await self.stop_plugin(plugin_name)
            
            # Unregister services
            services = await self.service_manager.list_services(plugin_name)
            for service in services.get(plugin_name, []):
                await self.service_manager.unregister_service(plugin_name, service.name)
            
            # Unload from loader
            await self.loader.unload(plugin_name)
            
            # Unregister from registry
            self.registry.unregister(plugin_name)
            
            # Clean up status
            del self._plugin_status[plugin_name]
            
            self.logger.info(f"Successfully unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False

    async def start_plugin(self, plugin_name: str) -> bool:
        """Start a specific plugin."""
        try:
            if self._plugin_status.get(plugin_name) != PluginStatus.LOADED:
                self.logger.error(f"Plugin {plugin_name} must be loaded before starting")
                return False
            
            plugin = self.registry.get_plugin(plugin_name)
            if not plugin:
                return False
            
            # Initialize if needed
            # Note: In the new architecture, context should be provided by the application layer
            # For now, we create a basic context
            if not hasattr(plugin, 'context') or (hasattr(plugin, 'context') and plugin.context is None):
                context = PluginContext(
                    plugin_id=plugin_name,
                    registry=self.registry,
                    event_bus=self.event_manager
                )
                await plugin.initialize(context)
            
            # Start the plugin
            await plugin.start()
            self._plugin_status[plugin_name] = PluginStatus.ACTIVE
            
            self.logger.info(f"Successfully started plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start plugin {plugin_name}: {e}")
            self._plugin_status[plugin_name] = PluginStatus.ERROR
            return False

    async def stop_plugin(self, plugin_name: str) -> bool:
        """Stop a specific plugin."""
        try:
            if self._plugin_status.get(plugin_name) != PluginStatus.ACTIVE:
                return False
            
            plugin = self.registry.get_plugin(plugin_name)
            if not plugin:
                return False
            
            self._plugin_status[plugin_name] = PluginStatus.STOPPING
            await plugin.stop()
            self._plugin_status[plugin_name] = PluginStatus.STOPPED
            
            self.logger.info(f"Successfully stopped plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop plugin {plugin_name}: {e}")
            self._plugin_status[plugin_name] = PluginStatus.ERROR
            return False

    def get_plugin_status(self, plugin_name: str) -> PluginStatus:
        """Get the status of a specific plugin."""
        return self._plugin_status.get(plugin_name, PluginStatus.UNLOADED)

    def list_plugins(self) -> dict[str, PluginStatus]:
        """List all plugins and their statuses."""
        return self._plugin_status.copy()

    def get_plugin_metadata(self, plugin_name: str) -> PluginMetadata | None:
        """Get metadata for a specific plugin."""
        return self.registry.get_metadata(plugin_name)

    def add_plugin_path(self, plugin_name: str, plugin_path: str) -> None:
        """Add a plugin path mapping."""
        self._plugin_paths[plugin_name] = plugin_path


# --- Bootstrap Functions ---

def create_plugin_manager(
    config: dict[str, Any] | None = None,
    logger: logging.Logger | None = None
) -> PluginManager:
    """Create a fully configured plugin manager."""
    if config is None:
        config = {}
    
    if logger is None:
        logger = logging.getLogger("marty_msf.plugins")
    
    # Create components
    discovery = PluginDiscovery(logger)
    loader = PluginLoader(logger)
    registry = PluginRegistry(logger)
    service_manager = ServiceManager(logger)
    event_manager = PluginEventSubscriptionManager(logger)
    
    # Create and configure plugin manager
    manager = PluginManager(
        discovery=discovery,
        loader=loader,
        registry=registry,
        service_manager=service_manager,
        event_manager=event_manager,
        logger=logger
    )
    
    return manager


def setup_plugin_system(
    plugin_paths: list[str] | None = None,
    config: dict[str, Any] | None = None,
    logger: logging.Logger | None = None
) -> PluginManager:
    """Set up the complete plugin system."""
    if plugin_paths is None:
        plugin_paths = []
    
    # Create plugin manager
    manager = create_plugin_manager(config, logger)
    
    # Discover plugins if paths provided
    if plugin_paths:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        discovered = loop.run_until_complete(manager.discover_plugins(plugin_paths))
        
        # Add plugin paths to manager
        for plugin_path in discovered:
            plugin_name = Path(plugin_path).stem
            manager.add_plugin_path(plugin_name, plugin_path)
    
    return manager
