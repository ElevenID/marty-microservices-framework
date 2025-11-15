"""
Unified Configuration and Secret Management System.

This package provides cloud-agnostic configuration management including:
- Multi-cloud secret backends (AWS, GCP, Azure, Vault, K8s)
- Environment-specific configuration loading
- Type-safe configuration with validation
- Automatic environment detection
- Secret references with ${SECRET:key} syntax
- Configuration hot-reloading
- Plugin configuration management
"""

from .manager import BaseServiceConfig, Environment  # Keep for compatibility
from .plugin_config import (
    PluginConfig,
    PluginConfigManager,
    PluginConfigProvider,
    PluginConfigSection,
    create_plugin_config_manager,
)
from .unified import (
    AWSSecretsManagerBackend,
    AzureKeyVaultBackend,
    ConfigurationStrategy,
    EnvironmentDetector,
    EnvironmentSecretBackend,
    FileSecretBackend,
    GCPSecretManagerBackend,
    HostingEnvironment,
    SecretBackend,
    SecretBackendInterface,
    UnifiedConfigurationManager,
    VaultSecretBackend,
    create_unified_config_manager,
    get_unified_config,
)

__all__ = [
    # Core unified configuration system
    "UnifiedConfigurationManager",
    "create_unified_config_manager",
    "get_unified_config",
    # Enums and configuration
    "Environment",
    "BaseServiceConfig",
    "SecretBackend",
    "HostingEnvironment",
    "ConfigurationStrategy",
    # Backend implementations
    "SecretBackendInterface",
    "EnvironmentDetector",
    "VaultSecretBackend",
    "AWSSecretsManagerBackend",
    "GCPSecretManagerBackend",
    "AzureKeyVaultBackend",
    "EnvironmentSecretBackend",
    "FileSecretBackend",
    # Plugin configuration
    "PluginConfig",
    "PluginConfigSection",
    "PluginConfigProvider",
    "PluginConfigManager",
    "create_plugin_config_manager",
]
