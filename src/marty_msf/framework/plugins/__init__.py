"""Plugin system for dynamic service extension."""

# Import from API layer (contracts and interfaces)
from .api import (
    BasePlugin,
    IPluginDiscovery,
    IPluginLoader,
    IPluginManager,
    IPluginRegistry,
    IServiceManager,
    PluginContext,
    PluginInterface,
    PluginMetadata,
    PluginStatus,
    RouteDefinition,
    RouteMethod,
    ServiceDefinition,
    ServiceStatus,
)

# Import from bootstrap layer (concrete implementations)
from .bootstrap import (
    PluginDiscovery,
    PluginLoader,
    PluginManager,
    PluginRegistry,
    ServiceManager,
    create_plugin_manager,
    setup_plugin_system,
)

__all__ = [
    # API Layer - Interfaces and Contracts
    "BasePlugin",
    "IPluginDiscovery",
    "IPluginLoader",
    "IPluginManager",
    "IPluginRegistry",
    "IServiceManager",
    "PluginContext",
    "PluginInterface",
    "PluginMetadata",
    "PluginStatus",
    "RouteDefinition",
    "RouteMethod",
    "ServiceDefinition",
    "ServiceStatus",

    # Bootstrap Layer - Concrete Implementations
    "PluginDiscovery",
    "PluginLoader",
    "PluginManager",
    "PluginRegistry",
    "ServiceManager",
    "create_plugin_manager",
    "setup_plugin_system",
]
