"""
Enterprise Configuration Management System.

Provides centralized configuration management with environment-specific settings,
secrets management, validation, and integration with various configuration sources.

Features:
- Environment-specific configuration loading
- Type-safe configuration with validation
- Secrets management with secure storage
- Configuration hot-reloading
- Integration with external config services
- Caching and performance optimization
"""

import builtins
import json
import logging
import os
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Generic, TypeVar

import yaml
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class Environment(Enum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ConfigSource(Enum):
    """Configuration source types."""

    ENV_VARS = "environment_variables"
    FILE_YAML = "yaml_file"
    FILE_JSON = "json_file"
    CONSUL = "consul"
    VAULT = "vault"
    KUBERNETES = "kubernetes_secrets"


@dataclass
class ConfigMetadata:
    """Configuration metadata and tracking."""

    source: ConfigSource
    last_loaded: str | None = None
    checksum: str | None = None
    version: str | None = None
    tags: builtins.list[str] = field(default_factory=list)


class ConfigProvider(ABC):
    """Abstract configuration provider interface."""

    @abstractmethod
    async def load_config(self, key: str) -> builtins.dict[str, Any]:
        """Load configuration for the given key."""

    @abstractmethod
    async def save_config(self, key: str, config: builtins.dict[str, Any]) -> bool:
        """Save configuration for the given key."""

    @abstractmethod
    async def watch_config(self, key: str, callback) -> None:
        """Watch configuration changes for the given key."""


class FileConfigProvider(ConfigProvider):
    """File-based configuration provider."""

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)

    async def load_config(self, key: str) -> builtins.dict[str, Any]:
        """Load configuration from file."""
        yaml_file = self.config_dir / f"{key}.yaml"
        json_file = self.config_dir / f"{key}.json"

        if yaml_file.exists():
            with open(yaml_file) as f:
                return yaml.safe_load(f) or {}
        elif json_file.exists():
            with open(json_file) as f:
                return json.load(f)
        else:
            return {}

    async def save_config(self, key: str, config: builtins.dict[str, Any]) -> bool:
        """Save configuration to file."""
        try:
            yaml_file = self.config_dir / f"{key}.yaml"
            with open(yaml_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save config {key}: {e}")
            return False

    async def watch_config(self, key: str, callback) -> None:
        """Watch for file changes (simplified implementation)."""
        # In a real implementation, use file system watching


class EnvVarConfigProvider(ConfigProvider):
    """Environment variable configuration provider."""

    def __init__(self, prefix: str = ""):
        self.prefix = prefix.upper() + "_" if prefix else ""

    async def load_config(self, key: str) -> builtins.dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        env_key = f"{self.prefix}{key.upper()}"

        for env_var, value in os.environ.items():
            if env_var.startswith(env_key):
                # Convert ENV_KEY__NESTED__VALUE to nested dict
                key_parts = env_var[len(self.prefix) :].lower().split("__")
                current = config

                for part in key_parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]

                # Try to parse as JSON, fall back to string
                try:
                    current[key_parts[-1]] = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    current[key_parts[-1]] = value

        return config

    async def save_config(self, key: str, config: builtins.dict[str, Any]) -> bool:
        """Environment variables are read-only."""
        return False

    async def watch_config(self, key: str, callback) -> None:
        """Environment variables don't support watching."""


class BaseServiceConfig(BaseSettings):
    """Base configuration for all services."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="allow"
    )

    # Service identification
    service_name: str = Field(..., description="Name of the service")
    service_version: str = Field(default="1.0.0", description="Version of the service")
    environment: Environment = Field(
        default=Environment.DEVELOPMENT, description="Deployment environment"
    )

    # Server configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")

    # Database configuration
    database_url: str = Field(..., description="Database connection URL")
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(
        default=30, description="Maximum database overflow connections"
    )

    # Observability
    otlp_endpoint: str | None = Field(default=None, description="OpenTelemetry OTLP endpoint")
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    tracing_enabled: bool = Field(default=True, description="Enable distributed tracing")

    # Security
    secret_key: str = Field(..., description="Application secret key")
    cors_origins: builtins.list[str] = Field(
        default_factory=list, description="CORS allowed origins"
    )

    # Performance
    worker_processes: int = Field(default=1, description="Number of worker processes")
    max_requests: int = Field(default=1000, description="Maximum requests per worker")

    # Feature flags
    features: builtins.dict[str, bool] = Field(default_factory=dict, description="Feature flags")


class ConfigManager(Generic[T]):
    """Enterprise configuration manager with validation and caching."""

    def __init__(
        self,
        config_class: builtins.type[T],
        providers: builtins.list[ConfigProvider],
        cache_ttl: int = 300,  # 5 minutes
        auto_reload: bool = True,
    ):
        self.config_class = config_class
        self.providers = providers
        self.cache_ttl = cache_ttl
        self.auto_reload = auto_reload
        self._cache: builtins.dict[str, Any] = {}
        self._metadata: builtins.dict[str, ConfigMetadata] = {}
        self._watchers: builtins.dict[str, builtins.list] = {}

    async def get_config(self, key: str) -> T:
        """Get validated configuration for the given key."""
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Load from providers
        merged_config = {}

        for provider in self.providers:
            try:
                provider_config = await provider.load_config(key)
                merged_config.update(provider_config)
            except Exception as e:
                logger.warning(f"Provider {provider.__class__.__name__} failed for key {key}: {e}")

        # Validate and create config instance
        try:
            config_instance = self.config_class(**merged_config)
            self._cache[key] = config_instance

            # Setup watching if auto_reload is enabled
            if self.auto_reload:
                await self._setup_watching(key)

            return config_instance

        except ValidationError as e:
            logger.error(f"Configuration validation failed for key {key}: {e}")
            raise

    async def reload_config(self, key: str) -> T:
        """Force reload configuration from providers."""
        if key in self._cache:
            del self._cache[key]
        return await self.get_config(key)

    async def _setup_watching(self, key: str) -> None:
        """Setup configuration watching for hot-reloading."""
        if key not in self._watchers:
            self._watchers[key] = []

        async def reload_callback():
            try:
                await self.reload_config(key)
                logger.info(f"Configuration reloaded for key: {key}")
            except Exception as e:
                logger.error(f"Failed to reload configuration for key {key}: {e}")

        for provider in self.providers:
            try:
                await provider.watch_config(key, reload_callback)
                self._watchers[key].append(reload_callback)
            except Exception as e:
                logger.warning(
                    f"Failed to setup watching for provider {provider.__class__.__name__}: {e}"
                )


class SecretManager:
    """Secure secrets management."""

    def __init__(self, provider: ConfigProvider):
        self.provider = provider
        self._secret_cache: builtins.dict[str, Any] = {}

    async def get_secret(self, key: str) -> str | None:
        """Get secret value securely."""
        if key in self._secret_cache:
            return self._secret_cache[key]

        try:
            secrets = await self.provider.load_config("secrets")
            secret_value = secrets.get(key)

            if secret_value:
                self._secret_cache[key] = secret_value

            return secret_value

        except Exception as e:
            logger.error(f"Failed to retrieve secret {key}: {e}")
            return None

    async def set_secret(self, key: str, value: str) -> bool:
        """Set secret value securely."""
        try:
            secrets = await self.provider.load_config("secrets")
            secrets[key] = value

            success = await self.provider.save_config("secrets", secrets)
            if success:
                self._secret_cache[key] = value

            return success

        except Exception as e:
            logger.error(f"Failed to set secret {key}: {e}")
            return False

    def clear_cache(self) -> None:
        """Clear secrets cache for security."""
        self._secret_cache.clear()


# Global configuration instances
_config_managers: builtins.dict[str, ConfigManager] = {}
_secret_manager: SecretManager | None = None


def create_config_manager(
    service_name: str,
    config_class: builtins.type[T] = BaseServiceConfig,
    config_dir: str | None = None,
    env_prefix: str | None = None,
) -> ConfigManager[T]:
    """Create a configuration manager for a service."""

    # Setup providers
    providers = []

    # Environment variables provider
    env_provider = EnvVarConfigProvider(prefix=env_prefix or service_name)
    providers.append(env_provider)

    # File provider
    if config_dir:
        file_provider = FileConfigProvider(Path(config_dir))
        providers.append(file_provider)
    else:
        # Default config directory
        default_config_dir = Path.cwd() / "config"
        if default_config_dir.exists():
            file_provider = FileConfigProvider(default_config_dir)
            providers.append(file_provider)

    # Create manager
    manager = ConfigManager(
        config_class=config_class,
        providers=providers,
        cache_ttl=300,
        auto_reload=True,
    )

    _config_managers[service_name] = manager
    return manager


def get_config_manager(service_name: str) -> ConfigManager | None:
    """Get existing configuration manager."""
    return _config_managers.get(service_name)


async def get_service_config(
    service_name: str,
    config_class: builtins.type[T] = BaseServiceConfig,
) -> T:
    """Get service configuration with automatic manager creation."""
    manager = get_config_manager(service_name)

    if not manager:
        manager = create_config_manager(service_name, config_class)

    return await manager.get_config(service_name)


def create_secret_manager(provider: ConfigProvider) -> SecretManager:
    """Create global secret manager."""
    global _secret_manager
    _secret_manager = SecretManager(provider)
    return _secret_manager


def get_secret_manager() -> SecretManager | None:
    """Get global secret manager."""
    return _secret_manager


@asynccontextmanager
async def config_context(service_name: str, config_class: builtins.type[T] = BaseServiceConfig):
    """Context manager for configuration lifecycle."""
    manager = create_config_manager(service_name, config_class)
    config = await manager.get_config(service_name)

    try:
        yield config
    finally:
        # Cleanup if needed
        if hasattr(manager, "cleanup"):
            await manager.cleanup()


# Utility functions
def detect_environment() -> Environment:
    """Auto-detect deployment environment."""
    env_name = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()

    try:
        return Environment(env_name)
    except ValueError:
        logger.warning(f"Unknown environment '{env_name}', defaulting to development")
        return Environment.DEVELOPMENT


def load_config_schema(schema_path: str) -> builtins.dict[str, Any]:
    """Load configuration schema for validation."""
    try:
        with open(schema_path) as f:
            if schema_path.endswith(".yaml") or schema_path.endswith(".yml"):
                return yaml.safe_load(f)
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config schema from {schema_path}: {e}")
        return {}


class FrameworkConfig(BaseServiceConfig):
    """
    Framework-level configuration for the Marty Microservices Framework.

    This provides default configuration settings for the entire framework
    and can be used by tests and applications that need framework-wide settings.
    """

    # Framework identification
    framework_name: str = Field(
        default="marty-microservices-framework", description="Name of the framework"
    )
    framework_version: str = Field(default="1.0.0", description="Version of the framework")

    # Default service settings
    default_service_timeout: float = Field(
        default=30.0, description="Default service timeout in seconds"
    )
    default_retry_attempts: int = Field(default=3, description="Default number of retry attempts")

    # Messaging configuration
    messaging_enabled: bool = Field(default=True, description="Enable messaging system")
    default_message_broker: str = Field(default="in-memory", description="Default message broker")

    # Discovery configuration
    discovery_enabled: bool = Field(default=True, description="Enable service discovery")
    default_discovery_backend: str = Field(
        default="in-memory", description="Default discovery backend"
    )

    # Observability configuration
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    tracing_enabled: bool = Field(default=False, description="Enable distributed tracing")
    logging_level: str = Field(default="INFO", description="Default logging level")

    # Security configuration
    security_enabled: bool = Field(default=False, description="Enable security features")
    auth_required: bool = Field(default=False, description="Require authentication")

    # Database configuration
    database_enabled: bool = Field(default=False, description="Enable database support")
    default_database_url: str | None = Field(default=None, description="Default database URL")
