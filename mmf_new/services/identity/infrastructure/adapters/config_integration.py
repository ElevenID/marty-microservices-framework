"""
JWT Configuration Integration.

Integrates JWT authentication with the project's unified configuration system,
loading JWT settings from YAML configuration files using MMFConfiguration.
"""

from pathlib import Path

from mmf_new.core.infrastructure.config import MMFConfiguration
from mmf_new.services.identity.infrastructure.adapters import JWTConfig


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""

    pass


class JWTConfigurationManager:
    """
    Manages JWT configuration loading from the unified configuration system.

    Uses MMFConfiguration for hierarchical configuration loading with
    environment-specific overrides and secret resolution.
    """

    def __init__(self, service_name: str = "identity-service", environment: str | None = None):
        """
        Initialize JWT configuration manager.

        Args:
            service_name: Name of the service for configuration loading
            environment: Environment name (development, production, etc.)
        """
        # Find config directory relative to project root
        current_dir = Path(__file__).parent
        for parent in current_dir.parents:
            config_path = parent / "mmf_new" / "config"
            if config_path.exists() and config_path.is_dir():
                self.config = MMFConfiguration.load(
                    config_dir=config_path,
                    environment=environment or "development",
                    service_name=service_name,
                )
                return

        raise ConfigurationError("Could not find MMF configuration directory")

    def get_jwt_config(self) -> JWTConfig:
        """
        Get JWT configuration from unified configuration system.

        Returns:
            JWTConfig object with settings from configuration files

        Raises:
            ConfigurationError: If configuration is invalid or missing
        """
        try:
            # Get JWT configuration using the new hierarchical system
            # The path matches the new structure: security.authentication.jwt
            jwt_config = self.config.get("security.authentication.jwt", {})

            # Extract JWT settings with defaults
            secret_key = jwt_config.get("secret")
            if not secret_key:
                # Try legacy path for backward compatibility
                legacy_jwt = self.config.get("security.auth.jwt", {})
                secret_key = legacy_jwt.get("secret")

            if not secret_key:
                raise ConfigurationError("JWT secret is required but not configured")

            algorithm = jwt_config.get("algorithm", "HS256")
            expiration_minutes = jwt_config.get("expiration_minutes", 60)
            issuer = jwt_config.get("issuer")
            audience = jwt_config.get("audience")

            return JWTConfig(
                secret_key=secret_key,
                algorithm=algorithm,
                access_token_expire_minutes=expiration_minutes,
                issuer=issuer,
                audience=audience,
            )

        except Exception as e:
            raise ConfigurationError(f"Failed to load JWT configuration: {e}") from e

    def get_auth_config(self) -> dict:
        """Get complete authentication configuration."""
        return self.config.get("security.authentication", {})

    def get_password_policy_config(self) -> dict:
        """Get password policy configuration."""
        return self.config.get("security.authentication.password_policy", {})

    def get_session_config(self) -> dict:
        """Get session management configuration."""
        return self.config.get("security.authentication.session_management", {})


def get_jwt_config_from_yaml() -> JWTConfig:
    """
    Get JWT configuration from YAML files.

    This is a convenience function that loads JWT configuration
    from the unified configuration system.

    Returns:
        JWTConfig object with settings from configuration files
    """
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
