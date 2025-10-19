"""
MMF Plugin System

This module provides a comprehensive plugin system for the Marty Microservices Framework.
It allows external applications like Marty to integrate as plugins while leveraging
MMF's infrastructure capabilities including security, database, messaging, observability,
and deployment.

Key Components:
- Plugin base classes and context management
- Service registration and lifecycle management
- Plugin discovery mechanisms
- Decorators for service integration

Example Usage:
from marty_msf.framework.plugins import MMFPlugin, PluginContext, plugin_service

    @plugin_service(name="MyService", version="1.0.0")
    class MyPlugin(MMFPlugin):
        async def initialize(self, context: PluginContext):
            # Plugin initialization
            pass
"""

# Core plugin infrastructure
from .core import MMFPlugin, PluginContext, PluginError, PluginManager, PluginMetadata

# Service decorators
from .decorators import (
    cache_result,
    event_handler,
    plugin_service,
    rate_limit,
    requires_auth,
    trace_operation,
    track_metrics,
)

# Plugin discovery
from .discovery import (
    CompositePluginDiscoverer,
    DirectoryPluginDiscoverer,
    PackagePluginDiscoverer,
    PluginDiscoverer,
    PluginInfo,
)

# Service management
from .services import PluginService, Route, ServiceDefinition, ServiceRegistry

__all__ = [
    # Core plugin classes
    "MMFPlugin",
    "PluginContext",
    "PluginManager",
    "PluginMetadata",
    "PluginError",
    # Service management
    "ServiceDefinition",
    "PluginService",
    "ServiceRegistry",
    "Route",
    # Plugin discovery
    "PluginDiscoverer",
    "DirectoryPluginDiscoverer",
    "PackagePluginDiscoverer",
    "CompositePluginDiscoverer",
    "PluginInfo",
    # Decorators
    "plugin_service",
    "requires_auth",
    "track_metrics",
    "trace_operation",
    "event_handler",
    "cache_result",
    "rate_limit",
]

__version__ = "1.0.0"
__author__ = "Marty Microservices Framework"
