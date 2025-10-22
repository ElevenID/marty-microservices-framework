"""Plugin system for dynamic service extension."""

# Import from API layer (contracts and interfaces)
from .api import (
    BasePlugin,
    IPluginDiscovery,
    IPluginEventSubscriptionManager,
    IPluginLoader,
    IPluginManager,
    IPluginRegistry,
    IServiceManager,
    MMFPlugin,
    PluginContext,
    PluginError,
    PluginInterface,
    PluginMetadata,
    PluginService,
    PluginStatus,
    PluginSubscriptionBase,
    RouteDefinition,
    RouteMethod,
    ServiceDefinition,
    ServiceStatus,
)

# Import from bootstrap layer (concrete implementations)
from .bootstrap import (
    PluginDiscovery,
    PluginEventSubscriptionManager,
    PluginLoader,
    PluginManager,
    PluginRegistry,
    ServiceManager,
    create_event_filter,
    create_plugin_manager,
    plugin_subscription_manager_context,
    register_plugin_with_events,
    setup_plugin_system,
)

# Import decorators
from .decorators import (
    cache_result,
    event_handler,
    plugin_service,
    rate_limit,
    requires_auth,
    trace_operation,
    track_metrics,
)

__all__ = [
    # API Layer - Interfaces and Contracts
    "BasePlugin",
    "MMFPlugin",
    "IPluginDiscovery",
    "IPluginEventSubscriptionManager",
    "IPluginLoader",
    "IPluginManager",
    "IPluginRegistry",
    "IServiceManager",
    "PluginContext",
    "PluginError",
    "PluginInterface",
    "PluginMetadata",
    "PluginService",
    "PluginStatus",
    "PluginSubscriptionBase",
    "RouteDefinition",
    "RouteMethod",
    "ServiceDefinition",
    "ServiceStatus",

    # Bootstrap Layer - Concrete Implementations
    "PluginDiscovery",
    "PluginEventSubscriptionManager",
    "PluginLoader",
    "PluginManager",
    "PluginRegistry",
    "ServiceManager",
    "create_event_filter",
    "create_plugin_manager",
    "plugin_subscription_manager_context",
    "register_plugin_with_events",
    "setup_plugin_system",
    # Decorators
    "cache_result",
    "event_handler",
    "plugin_service",
    "rate_limit",
    "requires_auth",
    "track_metrics",
    "trace_operation",
]
