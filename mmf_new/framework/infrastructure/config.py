"""
Configuration management for the new MMF hexagonal architecture.

This module provides unified configuration loading with support for:
- Hierarchical configuration inheritance
- Environment-specific overrides
- Service-specific configurations
- Secret management integration
- Platform configuration
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ConfigurationPaths:
    """Configuration file paths for the MMF configuration system."""

    base_config: Path
    environment_config: Path | None = None
    service_config: Path | None = None
    platform_config: Path | None = None

    @classmethod
    def from_config_dir(
        cls,
        config_dir: Path,
        environment: str = "development",
        service_name: str | None = None,
    ) -> ConfigurationPaths:
        """Create configuration paths from a config directory."""
        base_config = config_dir / "base.yaml"

        environment_config = None
        if environment:
            env_config_path = config_dir / "environments" / f"{environment}.yaml"
            if env_config_path.exists():
                environment_config = env_config_path

        service_config = None
        if service_name:
            svc_config_path = config_dir / "services" / f"{service_name}.yaml"
            if svc_config_path.exists():
                service_config = svc_config_path

        platform_config = config_dir / "platform" / "core.yaml"
        if not platform_config.exists():
            platform_config = None

        return cls(
            base_config=base_config,
            environment_config=environment_config,
            service_config=service_config,
            platform_config=platform_config,
        )


@dataclass
class SecretReference:
    """Represents a secret reference in configuration."""

    key: str
    backend: str = "environment"
    default: str | None = None

    @classmethod
    def parse(cls, value: str) -> SecretReference | None:
        """Parse a secret reference from string format: ${SECRET:key} or ${SECRET:key:default}."""
        if not value.startswith("${SECRET:") or not value.endswith("}"):
            return None

        content = value[9:-1]  # Remove ${SECRET: and }
        parts = content.split(":", 1)  # Split only on first colon

        key = parts[0]
        default = parts[1] if len(parts) > 1 else None

        return cls(key=key, backend="environment", default=default)


class SecretResolver:
    """Resolves secret references in configuration."""

    def __init__(self, backends: list[str] = None):
        """Initialize secret resolver with available backends."""
        self.backends = backends or ["environment", "file"]

    def resolve_secret(self, secret_ref: SecretReference) -> str:
        """Resolve a secret reference to its actual value."""
        if secret_ref.backend == "environment" or "environment" in self.backends:
            value = os.environ.get(secret_ref.key)
            if value is not None:
                return value

        # Add other backend implementations here (vault, k8s secrets, etc.)

        if secret_ref.default is not None:
            return secret_ref.default

        raise ValueError(f"Secret '{secret_ref.key}' not found in any backend")

    def resolve_config_secrets(self, config: dict[str, Any]) -> dict[str, Any]:
        """Recursively resolve all secret references in a configuration dictionary."""
        if isinstance(config, dict):
            resolved = {}
            for key, value in config.items():
                resolved[key] = self.resolve_config_secrets(value)
            return resolved
        elif isinstance(config, list):
            return [self.resolve_config_secrets(item) for item in config]
        elif isinstance(config, str):
            secret_ref = SecretReference.parse(config)
            if secret_ref:
                return self.resolve_secret(secret_ref)
            return config
        else:
            return config


class ConfigurationLoader:
    """Loads and merges configuration from multiple sources."""

    def __init__(self, secret_resolver: SecretResolver | None = None):
        """Initialize configuration loader."""
        self.secret_resolver = secret_resolver or SecretResolver()

    def load_yaml_file(self, path: Path) -> dict[str, Any]:
        """Load a YAML configuration file."""
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, encoding="utf-8") as file:
            content = yaml.safe_load(file)
            return content if content is not None else {}

    def merge_configurations(self, *configs: dict[str, Any]) -> dict[str, Any]:
        """Deep merge multiple configuration dictionaries."""
        result = {}

        for config in configs:
            if not config:
                continue

            result = self._deep_merge(result, config)

        return result

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def load_configuration(self, paths: ConfigurationPaths) -> dict[str, Any]:
        """Load and merge configuration from all sources."""
        configs = []

        # Load base configuration
        if paths.base_config.exists():
            base_config = self.load_yaml_file(paths.base_config)
            configs.append(base_config)

        # Load platform configuration
        if paths.platform_config and paths.platform_config.exists():
            platform_config = self.load_yaml_file(paths.platform_config)
            configs.append(platform_config)

        # Load environment-specific configuration
        if paths.environment_config and paths.environment_config.exists():
            env_config = self.load_yaml_file(paths.environment_config)
            configs.append(env_config)

        # Load service-specific configuration
        if paths.service_config and paths.service_config.exists():
            service_config = self.load_yaml_file(paths.service_config)
            configs.append(service_config)

        # Merge all configurations
        merged_config = self.merge_configurations(*configs)

        # Resolve secrets
        resolved_config = self.secret_resolver.resolve_config_secrets(merged_config)

        return resolved_config


@dataclass
class MMFConfiguration:
    """Complete configuration for an MMF service."""

    service: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    database: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)
    resilience: dict[str, Any] = field(default_factory=dict)
    messaging: dict[str, Any] = field(default_factory=dict)
    cache: dict[str, Any] = field(default_factory=dict)
    platform: dict[str, Any] = field(default_factory=dict)
    raw_config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        config_dir: Path | str,
        environment: str = None,
        service_name: str = None,
    ) -> MMFConfiguration:
        """Load MMF configuration from directory."""
        if isinstance(config_dir, str):
            config_dir = Path(config_dir)

        # Detect environment from env var if not specified
        if environment is None:
            environment = os.environ.get("MMF_ENVIRONMENT", "development")

        # Create configuration paths
        paths = ConfigurationPaths.from_config_dir(
            config_dir=config_dir,
            environment=environment,
            service_name=service_name,
        )

        # Load configuration
        loader = ConfigurationLoader()
        config = loader.load_configuration(paths)

        # Extract major sections
        return cls(
            service=config.get("service", {}),
            environment=config.get("environment", {}),
            database=config.get("database", {}),
            security=config.get("security", {}),
            observability=config.get("observability", {}),
            resilience=config.get("resilience", {}),
            messaging=config.get("messaging", {}),
            cache=config.get("cache", {}),
            platform=config.get("platform", {}),
            raw_config=config,
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation (e.g., 'database.host')."""
        keys = key.split(".")
        value = self.raw_config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_service_name(self) -> str:
        """Get the service name from configuration."""
        return self.service.get("name", "unknown-service")

    def get_service_version(self) -> str:
        """Get the service version from configuration."""
        return self.service.get("version", "1.0.0")

    def get_environment_name(self) -> str:
        """Get the environment name from configuration."""
        return self.environment.get("name", "development")

    def is_debug_enabled(self) -> bool:
        """Check if debug mode is enabled."""
        return self.environment.get("debug", False)


# Configuration factory functions
def load_service_configuration(
    service_name: str,
    environment: str = None,
    config_dir: Path | str = None,
) -> MMFConfiguration:
    """Load configuration for a specific service."""
    if config_dir is None:
        # Auto-detect config directory
        current_dir = Path(__file__).parent
        config_dir = current_dir / "config"
        if not config_dir.exists():
            # Try relative to project root
            config_dir = current_dir.parent / "config"

    return MMFConfiguration.load(
        config_dir=config_dir,
        environment=environment,
        service_name=service_name,
    )


def load_platform_configuration(
    environment: str = None,
    config_dir: Path | str = None,
) -> MMFConfiguration:
    """Load platform-wide configuration."""
    return MMFConfiguration.load(
        config_dir=config_dir or Path(__file__).parent / "config",
        environment=environment,
        service_name=None,
    )

