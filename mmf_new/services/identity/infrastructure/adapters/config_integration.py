"""
JWT Configuration Integration.

Integrates JWT authentication with the project's unified configuration system,
loading JWT settings from YAML configuration files.
"""

import os
from pathlib import Path
from typing import Any

import yaml

# TODO: Update to new DI container when available
# from marty_msf.core.di_container import get_service
from mmf_new.services.identity.infrastructure.adapters import JWTConfig


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""

    pass


class JWTConfigurationManager:
    """
    Manages JWT configuration loading from the unified configuration system.

    Supports loading configuration from YAML files with environment-specific
    overrides and secret resolution.
    """

    def __init__(self, config_dir: str | None = None, environment: str | None = None):
        """
        Initialize JWT configuration manager.

        Args:
            config_dir: Directory containing configuration files
            environment: Environment name (development, production, etc.)
        """
        self.config_dir = Path(config_dir or self._default_config_dir())
        self.environment = environment or self._detect_environment()
        self._config_cache: dict[str, Any] = {}

    def _default_config_dir(self) -> str:
        """Get default configuration directory."""
        # Try to find config directory relative to project root
        current_dir = Path(__file__).parent

        # Go up until we find a config directory
        for parent in current_dir.parents:
            config_path = parent / "config"
            if config_path.exists() and config_path.is_dir():
                return str(config_path)

        # Fallback to environment variable or current directory
        return os.getenv("CONFIG_DIR", "config")

    def _detect_environment(self) -> str:
        """Detect current environment."""
        return os.getenv("ENVIRONMENT", os.getenv("ENV", "development"))

    def _load_yaml_file(self, filename: str) -> dict[str, Any]:
        """Load YAML configuration file."""
        file_path = self.config_dir / filename

        if not file_path.exists():
            return {}

        try:
            with open(file_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            raise ConfigurationError(f"Failed to load {filename}: {e}") from e

    def _resolve_secret(self, secret_ref: str) -> str:
        """
        Resolve secret reference.

        Supports format: ${SECRET:secret_name}
        """
        if not secret_ref.startswith("${SECRET:") or not secret_ref.endswith("}"):
            return secret_ref

        secret_name = secret_ref[9:-1]  # Remove ${SECRET: and }

        # Try environment variable first
        env_value = os.getenv(secret_name.upper())
        if env_value:
            return env_value

        # Try secrets section in config
        secrets_config = self._get_merged_config().get("secrets", {})
        if secret_name in secrets_config:
            return secrets_config[secret_name]

        # Fallback for development
        if self.environment == "development":
            dev_defaults = {
                "jwt_secret": "dev_jwt_secret_not_secure_change_in_production",
                "service_api_key": "dev_api_key_12345",
            }
            if secret_name in dev_defaults:
                return dev_defaults[secret_name]

        raise ConfigurationError(f"Secret '{secret_name}' not found")

    def _resolve_config_values(self, config: dict[str, Any]) -> dict[str, Any]:
        """Recursively resolve secret references in configuration."""
        if isinstance(config, dict):
            return {
                key: self._resolve_config_values(value) for key, value in config.items()
            }
        elif isinstance(config, str) and config.startswith("${SECRET:"):
            return self._resolve_secret(config)
        elif isinstance(config, list):
            return [self._resolve_config_values(item) for item in config]
        else:
            return config

    def _get_merged_config(self) -> dict[str, Any]:
        """Get merged configuration from base and environment-specific files."""
        if "merged" in self._config_cache:
            return self._config_cache["merged"]

        # Load base configuration
        base_config = self._load_yaml_file("base.yaml")

        # Load environment-specific configuration
        env_config = self._load_yaml_file(f"{self.environment}.yaml")

        # Merge configurations (environment overrides base)
        merged_config = self._deep_merge(base_config, env_config)

        # Resolve secret references
        resolved_config = self._resolve_config_values(merged_config)

        self._config_cache["merged"] = resolved_config
        return resolved_config

    def _deep_merge(
        self, base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def get_jwt_config(self) -> JWTConfig:
        """
        Get JWT configuration from unified configuration system.

        Returns:
            JWTConfig object with settings from configuration files

        Raises:
            ConfigurationError: If configuration is invalid or missing
        """
        config = self._get_merged_config()

        # Navigate to JWT configuration
        security_config = config.get("security", {})
        auth_config = security_config.get("auth", {})
        jwt_config = auth_config.get("jwt", {})

        # Extract JWT settings with defaults
        secret_key = jwt_config.get("secret")
        if not secret_key:
            raise ConfigurationError("JWT secret is required but not configured")

        algorithm = jwt_config.get("algorithm", "HS256")
        expiration_minutes = jwt_config.get("expiration_minutes", 60)
        issuer = jwt_config.get("issuer")
        audience = jwt_config.get("audience")

        # Validate required settings
        if not secret_key:
            raise ConfigurationError("JWT secret key is required")

        return JWTConfig(
            secret_key=secret_key,
            algorithm=algorithm,
            access_token_expire_minutes=expiration_minutes,
            issuer=issuer,
            audience=audience,
        )

    def get_auth_config(self) -> dict[str, Any]:
        """Get complete authentication configuration."""
        config = self._get_merged_config()
        return config.get("security", {}).get("auth", {})

    def refresh_config(self) -> None:
        """Refresh configuration cache."""
        self._config_cache.clear()


def get_jwt_config_from_yaml() -> JWTConfig:
    """
    Get JWT configuration from YAML files.

    This is a convenience function that loads JWT configuration
    from the unified configuration system using dependency injection.

    Returns:
        JWTConfig object with settings from configuration files
    """
    # TODO: Update to use new DI container
    # manager = get_service(JWTConfigurationManager)
    manager = JWTConfigurationManager()
    return manager.get_jwt_config()


def create_jwt_config_for_environment(environment: str) -> JWTConfig:
    """
    Create JWT configuration for specific environment.

    Args:
        environment: Environment name (development, production, etc.)

    Returns:
        JWTConfig object for the specified environment
    """
    manager = JWTConfigurationManager(environment=environment)
    return manager.get_jwt_config()
