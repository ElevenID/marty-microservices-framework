"""
Plugin Manager Service

This module provides the high-level service for managing plugins.
It is now a facade over the core framework plugin system.
"""

from mmf.framework.plugins import (
    PluginEventSubscriptionManager,
    PluginManager,
    ServiceManager,
    create_plugin_manager,
    setup_plugin_system,
)

__all__ = [
    "PluginManager",
    "ServiceManager",
    "PluginEventSubscriptionManager",
    "create_plugin_manager",
    "setup_plugin_system",
]
