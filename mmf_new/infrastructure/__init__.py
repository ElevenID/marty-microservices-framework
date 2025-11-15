"""
Infrastructure layer for MMF framework.

This package contains cross-cutting infrastructure concerns:
- Configuration management (YAML + multi-cloud secrets)
- Dependency injection container
- Service discovery and registry
- Platform integration utilities
"""

from .config import (
    ConfigurationLoader,
    ConfigurationPaths,
    MMFConfiguration,
    SecretResolver,
    load_platform_configuration,
    load_service_configuration,
)
from .config_manager import (
    BaseServiceConfig,
    ConfigManager,
    Environment,
    SecretManager,
    create_config_manager,
    create_secret_manager,
    get_secret_manager,
)
from .dependency_injection import DIContainer, get_container, get_service

__all__ = [
    "ConfigurationLoader",
    "ConfigurationPaths",
    "MMFConfiguration",
    "SecretResolver",
    "load_platform_configuration",
    "load_service_configuration",
    "BaseServiceConfig",
    "ConfigManager",
    "Environment",
    "SecretManager",
    "create_config_manager",
    "create_secret_manager",
    "get_secret_manager",
    "DIContainer",
    "get_service",
    "get_container",
]
