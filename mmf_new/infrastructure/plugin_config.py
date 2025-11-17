"""
Plugin Configuration System

Extends the MMF configuration system to support plugin-specific configuration
including plugin metadata and dynamic configuration loading.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

from .cache import CacheBackend, CacheConfig, SerializationFormat, create_cache_manager
from .config_manager import (
    BaseServiceConfig,
    ConfigManager,
    ConfigProvider,
    EnvVarConfigProvider,
    FileConfigProvider,
)

logger = logging.getLogger(__name__)


class PluginConfigSection(BaseModel):
    """Base class for plugin configuration sections."""

    enabled: bool = Field(default=True, description="Whether the plugin is enabled")
    version: str = Field(default="1.0.0", description="Plugin version")
    description: str = Field(default="", description="Plugin description")
    dependencies: list[str] = Field(default_factory=list, description="Plugin dependencies")

    class Config:
        extra = "allow"  # Allow additional plugin-specific fields


class GenericPluginConfig(PluginConfigSection):
    """Generic configuration template for plugins."""

    # Service settings
    service_url: str = Field(default="https://localhost:8080", description="Service URL")
    service_timeout: int = Field(default=30, description="Service timeout in seconds")

    # Cache settings
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")
    cache_enabled: bool = Field(default=True, description="Enable caching")

    # Security settings
    enable_tls: bool = Field(default=True, description="Enable TLS")
    require_mutual_tls: bool = Field(default=False, description="Require mutual TLS authentication")

    # Feature flags
    feature_flags: dict[str, bool] = Field(default_factory=dict, description="Feature flags")
    certificate_validation_enabled: bool = Field(
        default=True, description="Enable certificate validation"
    )
    certificate_cache_size: int = Field(default=1000, description="Certificate cache size")

    # Security settings
    require_mutual_tls: bool = Field(default=False, description="Require mutual TLS authentication")
    allowed_cipher_suites: list[str] = Field(
        default_factory=lambda: [
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_128_GCM_SHA256",
        ],
        description="Allowed TLS cipher suites",
    )


class PluginConfig(BaseServiceConfig):
    """Extended service configuration with plugin support."""

    # Plugin system settings
    plugins_enabled: bool = Field(default=True, description="Enable plugin system")
    plugin_discovery_paths: list[str] = Field(
        default_factory=lambda: ["./plugins", "/opt/mmf/plugins"],
        description="Paths to search for plugins",
    )
    plugin_config_dir: str = Field(
        default="./config/plugins", description="Directory for plugin configurations"
    )
    plugin_auto_discovery: bool = Field(
        default=True, description="Automatically discover plugins in discovery paths"
    )
    plugin_isolation_level: str = Field(
        default="process", description="Plugin isolation level: 'thread', 'process', or 'container'"
    )

    # Plugin configurations
    plugins: dict[str, PluginConfigSection] = Field(
        default_factory=dict, description="Plugin-specific configurations"
    )


class PluginConfigProvider(ConfigProvider):
    """Configuration provider for plugin-specific settings."""

    def __init__(self, config_dir: Path, plugin_name: str):
        self.config_dir = Path(config_dir)
        self.plugin_name = plugin_name
        self.config_dir.mkdir(parents=True, exist_ok=True)

    async def load_config(self, key: str) -> dict[str, Any]:
        """Load plugin configuration from dedicated directory."""
        plugin_config_file = self.config_dir / f"{self.plugin_name}.yaml"

        if plugin_config_file.exists():
            with open(plugin_config_file) as f:
                config = yaml.safe_load(f) or {}

            # Return only the section for this key if it exists
            if key in config:
                return config[key]
            return config

        return {}

    async def save_config(self, key: str, config: dict[str, Any]) -> bool:
        """Save plugin configuration to dedicated file."""
        try:
            plugin_config_file = self.config_dir / f"{self.plugin_name}.yaml"

            # Load existing config if it exists
            existing_config = {}
            if plugin_config_file.exists():
                with open(plugin_config_file) as f:
                    existing_config = yaml.safe_load(f) or {}

            # Update with new config
            existing_config[key] = config

            # Save back to file

            with open(plugin_config_file, "w") as f:
                yaml.dump(existing_config, f, default_flow_style=False)

            return True
        except Exception as e:
            logger.error(f"Failed to save plugin config {key} for {self.plugin_name}: {e}")
            return False

    async def watch_config(self, key: str, callback) -> None:
        """Watch for plugin configuration changes."""
        # In a real implementation, use file system watching
        pass


class PluginConfigManager:
    """Manages configurations for multiple plugins."""

    def __init__(
        self, base_config_manager: ConfigManager, plugin_config_dir: str = "./config/plugins"
    ):
        self.base_config_manager = base_config_manager
        self.plugin_config_dir = Path(plugin_config_dir)

        # Initialize enterprise cache for plugin configurations
        plugin_cache_config = CacheConfig(
            backend=CacheBackend.MEMORY,
            serialization=SerializationFormat.PICKLE,  # ConfigManager not JSON serializable
            default_ttl=300,  # 5 minutes
            namespace="plugin_configs",
        )
        self._plugin_configs_cache = create_cache_manager("plugin_configs", plugin_cache_config)

        # Initialize enterprise cache for plugin config classes
        classes_cache_config = CacheConfig(
            backend=CacheBackend.MEMORY,
            serialization=SerializationFormat.PICKLE,  # Classes not JSON serializable
            default_ttl=0,  # Classes persist for app lifetime
            namespace="plugin_classes",
        )
        self._plugin_classes_cache = create_cache_manager("plugin_classes", classes_cache_config)

        # Plugin config classes are registered dynamically by plugins

    async def start(self) -> None:
        """Start the plugin config manager and initialize caches."""
        await self._plugin_configs_cache.start()
        await self._plugin_classes_cache.start()

    async def stop(self) -> None:
        """Stop the plugin config manager and clean up caches."""
        await self._plugin_configs_cache.stop()
        await self._plugin_classes_cache.stop()

    async def register_plugin_config(
        self, plugin_name: str, config_class: type[PluginConfigSection]
    ):
        """Register a configuration class for a plugin."""
        await self._plugin_classes_cache.set(plugin_name, config_class)

        # Create dedicated config manager for this plugin
        plugin_provider = PluginConfigProvider(self.plugin_config_dir, plugin_name)
        config_manager = ConfigManager(
            config_class=config_class, providers=[plugin_provider], cache_ttl=300, auto_reload=True
        )
        await config_manager.start()  # Ensure config manager is started
        await self._plugin_configs_cache.set(plugin_name, config_manager)

    async def get_plugin_config(
        self, plugin_name: str, config_key: str = "default"
    ) -> PluginConfigSection:
        """Get configuration for a specific plugin."""
        config_manager = await self._plugin_configs_cache.get(plugin_name)
        if config_manager is None:
            # Create default config manager for unknown plugins
            await self.register_plugin_config(plugin_name, PluginConfigSection)
            config_manager = await self._plugin_configs_cache.get(plugin_name)
            if config_manager is None:
                raise ValueError(f"Failed to create config manager for plugin: {plugin_name}")

        return await config_manager.get_config(config_key)

    async def load_plugin_config(
        self, plugin_name: str, config_class: type[PluginConfigSection]
    ) -> PluginConfigSection:
        """Load configuration for a specific plugin with a specified config class.

        Args:
            plugin_name: Name of the plugin
            config_class: Configuration class to use

        Returns:
            Plugin configuration instance
        """
        # Check if config class is already registered
        existing_config_class = await self._plugin_classes_cache.get(plugin_name)
        if existing_config_class is None:
            await self.register_plugin_config(plugin_name, config_class)
        elif existing_config_class != config_class:
            # Update to use the specified config class
            await self.register_plugin_config(plugin_name, config_class)

        return await self.get_plugin_config(plugin_name)

    @property
    def base_config_path(self) -> Path:
        """Get the base configuration path."""
        return self.plugin_config_dir

    async def get_base_config(self, config_key: str = "default") -> PluginConfig:
        """Get the base service configuration with plugin support."""
        return await self.base_config_manager.get_config(config_key)

    async def validate_plugin_config(self, plugin_name: str, config_data: dict[str, Any]) -> bool:
        """Validate plugin configuration against its schema."""
        try:
            config_class = await self._plugin_classes_cache.get(plugin_name)
            if config_class is not None:
                config_class(**config_data)
                return True
            else:
                # Validate against base plugin config
                PluginConfigSection(**config_data)
                return True
        except ValidationError as e:
            logger.error("Plugin config validation failed for %s: %s", plugin_name, e)
            return False

    async def update_plugin_config(
        self, plugin_name: str, config_key: str, config_data: dict[str, Any]
    ) -> bool:
        """Update plugin configuration."""
        # Validate first
        if not await self.validate_plugin_config(plugin_name, config_data):
            return False

        # Get the provider and save
        config_manager = await self._plugin_configs_cache.get(plugin_name)
        if config_manager is not None:
            providers = config_manager.providers
            if providers:
                return await providers[0].save_config(config_key, config_data)

        return False

    async def list_plugin_configs(self) -> dict[str, list[str]]:
        """List all available plugin configurations."""
        result = {}

        # For now, we'll return a simple structure since we can't easily iterate cache items
        # In a real implementation, we might need to track plugin names separately
        result["registered_plugins"] = ["default"]

        return result

    async def generate_plugin_config_template(self, plugin_name: str) -> dict[str, Any]:
        """Generate a configuration template for a plugin."""
        config_class = await self._plugin_classes_cache.get(plugin_name)
        if config_class is not None:
            # Create instance with defaults and extract schema
            try:
                instance = config_class()
                return instance.model_dump()
            except Exception:
                # Return schema with field info
                schema = config_class.model_json_schema()
                template = {}

                if "properties" in schema:
                    for field_name, field_info in schema["properties"].items():
                        if "default" in field_info:
                            template[field_name] = field_info["default"]
                        elif field_info.get("type") == "string":
                            template[field_name] = f"<{field_info.get('description', field_name)}>"
                        elif field_info.get("type") == "integer":
                            template[field_name] = 0
                        elif field_info.get("type") == "boolean":
                            template[field_name] = False
                        elif field_info.get("type") == "array":
                            template[field_name] = []
                        elif field_info.get("type") == "object":
                            template[field_name] = {}

                return template

        # Return base template
        return PluginConfigSection().model_dump()


# Factory function for creating plugin-aware config managers
def create_plugin_config_manager(
    config_dir: str = "./config",
    plugin_config_dir: str = "./config/plugins",
    providers: list[ConfigProvider] | None = None,
) -> PluginConfigManager:
    """Create a plugin configuration manager with default providers."""

    if providers is None:
        providers = [FileConfigProvider(Path(config_dir)), EnvVarConfigProvider("MMF")]

    base_config_manager = ConfigManager(
        config_class=PluginConfig, providers=providers, cache_ttl=300, auto_reload=True
    )

    return PluginConfigManager(base_config_manager, plugin_config_dir)
