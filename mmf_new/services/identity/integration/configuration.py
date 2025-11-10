"""
Configuration integration for JWT authentication using the new core framework.

This module provides configuration classes and factory functions
for setting up JWT authentication in different environments using
the hexagonal architecture core framework.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from mmf_new.core.infrastructure.database import CoreDatabaseManager, DatabaseConfig
from mmf_new.services.identity.application.use_cases.authenticate_with_jwt import (
    AuthenticateWithJWTUseCase,
)
from mmf_new.services.identity.infrastructure.adapters import JWTConfig
from mmf_new.services.identity.infrastructure.adapters.user_repository_impl import (
    AuthenticatedUserRepository,
)


@dataclass
class JWTAuthConfig:
    """
    Complete JWT authentication configuration.

    Combines JWT token configuration with authentication middleware settings
    for easy application setup using the new core framework.
    """

    # JWT Token Configuration
    secret_key: str
    algorithm: str = "HS256"
    issuer: str = "marty-microservices"
    audience: str = "marty-services"
    expires_delta_minutes: int = 30

    # Middleware Configuration
    excluded_paths: list[str] | None = None
    optional_paths: list[str] | None = None

    # Environment-specific settings
    verify_signature: bool = True
    verify_expiration: bool = True
    verify_issuer: bool = True
    verify_audience: bool = True

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.secret_key:
            raise ValueError("JWT secret_key is required")

        if self.expires_delta_minutes <= 0:
            raise ValueError("expires_delta_minutes must be positive")

        # Set default excluded paths if not provided
        if self.excluded_paths is None:
            self.excluded_paths = [
                "/health",
                "/docs",
                "/openapi.json",
                "/redoc",
                "/auth/jwt/health",
            ]

        # Set default optional paths if not provided
        if self.optional_paths is None:
            self.optional_paths = []

    def to_jwt_config(self) -> JWTConfig:
        """
        Convert to infrastructure JWTConfig.

        Returns:
            JWTConfig instance for token operations
        """
        return JWTConfig(
            secret_key=self.secret_key,
            algorithm=self.algorithm,
            issuer=self.issuer,
            audience=self.audience,
            access_token_expire_minutes=self.expires_delta_minutes,
        )


def create_development_config(secret_key: str | None = None) -> JWTAuthConfig:
    """
    Create JWT configuration for development environment.

    Args:
        secret_key: Optional custom secret key

    Returns:
        Development JWT configuration with relaxed security
    """
    return JWTAuthConfig(
        secret_key=secret_key or "dev-secret-key-change-in-production",
        algorithm="HS256",
        issuer="marty-dev",
        audience="marty-dev-services",
        expires_delta_minutes=120,  # Longer expiration for development
        excluded_paths=[
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/auth/jwt/health",
            "/dev/*",  # Development-specific paths
        ],
        optional_paths=[
            "/admin/debug",
            "/metrics",
        ],
        verify_signature=True,
        verify_expiration=True,
        verify_issuer=False,  # Relaxed for development
        verify_audience=False,  # Relaxed for development
    )


def create_testing_config(secret_key: str | None = None) -> JWTAuthConfig:
    """
    Create JWT configuration for testing environment.

    Args:
        secret_key: Optional custom secret key

    Returns:
        Testing JWT configuration with minimal verification
    """
    return JWTAuthConfig(
        secret_key=secret_key or "test-secret-key",
        algorithm="HS256",
        issuer="marty-test",
        audience="marty-test-services",
        expires_delta_minutes=60,
        excluded_paths=[
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/auth/jwt/health",
            "/test/*",  # Test-specific paths
        ],
        optional_paths=[],
        verify_signature=True,
        verify_expiration=False,  # Relaxed for testing
        verify_issuer=False,  # Relaxed for testing
        verify_audience=False,  # Relaxed for testing
    )


def create_production_config(
    secret_key: str, issuer: str | None = None, audience: str | None = None
) -> JWTAuthConfig:
    """
    Create JWT configuration for production environment.

    Args:
        secret_key: Production secret key (required)
        issuer: Optional custom issuer
        audience: Optional custom audience

    Returns:
        Production JWT configuration with full security
    """
    if not secret_key:
        raise ValueError("Production secret_key is required")

    return JWTAuthConfig(
        secret_key=secret_key,
        algorithm="HS256",
        issuer=issuer or "marty-microservices",
        audience=audience or "marty-services",
        expires_delta_minutes=30,  # Short expiration for security
        excluded_paths=[
            "/health",
            "/docs",
            "/openapi.json",
            "/auth/jwt/health",
        ],
        optional_paths=[],  # No optional authentication in production
        verify_signature=True,
        verify_expiration=True,
        verify_issuer=True,
        verify_audience=True,
    )


def load_config_from_env() -> JWTAuthConfig:
    """
    Load JWT configuration from environment variables.

    Expected environment variables:
    - JWT_SECRET_KEY: Secret key for signing tokens
    - JWT_ALGORITHM: Algorithm for signing (default: HS256)
    - JWT_ISSUER: Token issuer (default: marty-microservices)
    - JWT_AUDIENCE: Token audience (default: marty-services)
    - JWT_EXPIRES_MINUTES: Token expiration in minutes (default: 30)
    - ENVIRONMENT: Environment name (development, testing, production)

    Returns:
        JWT configuration loaded from environment

    Raises:
        ValueError: If required environment variables are missing
    """

    # Get environment
    env = os.getenv("ENVIRONMENT", "development").lower()

    # Get secret key
    secret_key = os.getenv("JWT_SECRET_KEY")

    # Use environment-specific defaults if secret key is provided
    if secret_key:
        # Get optional overrides
        algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        issuer = os.getenv("JWT_ISSUER")
        audience = os.getenv("JWT_AUDIENCE")
        expires_minutes = int(os.getenv("JWT_EXPIRES_MINUTES", "30"))

        if env == "production":
            return JWTAuthConfig(
                secret_key=secret_key,
                algorithm=algorithm,
                issuer=issuer or "marty-microservices",
                audience=audience or "marty-services",
                expires_delta_minutes=expires_minutes,
            )
        elif env == "testing":
            config = create_testing_config(secret_key)
            config.algorithm = algorithm
            if issuer:
                config.issuer = issuer
            if audience:
                config.audience = audience
            config.expires_delta_minutes = expires_minutes
            return config
        else:  # development
            config = create_development_config(secret_key)
            config.algorithm = algorithm
            if issuer:
                config.issuer = issuer
            if audience:
                config.audience = audience
            config.expires_delta_minutes = expires_minutes
            return config

    # Fall back to environment-specific defaults
    if env == "production":
        raise ValueError(
            "JWT_SECRET_KEY environment variable is required for production"
        )
    elif env == "testing":
        return create_testing_config()
    else:  # development
        return create_development_config()


def load_config_from_file(config_file: str | Path) -> JWTAuthConfig:
    """
    Load JWT configuration from YAML file.

    Args:
        config_file: Path to YAML configuration file

    Returns:
        JWT configuration loaded from file

    Raises:
        FileNotFoundError: If configuration file doesn't exist
        ValueError: If configuration is invalid
    """

    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    jwt_config = data.get("jwt", {})

    return JWTAuthConfig(
        secret_key=jwt_config.get("secret_key", ""),
        algorithm=jwt_config.get("algorithm", "HS256"),
        issuer=jwt_config.get("issuer", "marty-microservices"),
        audience=jwt_config.get("audience", "marty-services"),
        expires_delta_minutes=jwt_config.get("expires_delta_minutes", 30),
        excluded_paths=jwt_config.get("excluded_paths"),
        optional_paths=jwt_config.get("optional_paths"),
        verify_signature=jwt_config.get("verify_signature", True),
        verify_expiration=jwt_config.get("verify_expiration", True),
        verify_issuer=jwt_config.get("verify_issuer", True),
        verify_audience=jwt_config.get("verify_audience", True),
    )


# Configuration registry for different environments
CONFIG_REGISTRY: dict[str, Any] = {
    "development": create_development_config,
    "testing": create_testing_config,
    "production": create_production_config,
}


def get_config_for_environment(environment: str, **kwargs) -> JWTAuthConfig:
    """
    Get JWT configuration for specified environment.

    Args:
        environment: Environment name (development, testing, production)
        **kwargs: Additional configuration parameters

    Returns:
        JWT configuration for environment

    Raises:
        ValueError: If environment is not supported
    """
    if environment not in CONFIG_REGISTRY:
        raise ValueError(
            f"Unsupported environment: {environment}. "
            f"Supported: {list(CONFIG_REGISTRY.keys())}"
        )

    config_factory = CONFIG_REGISTRY[environment]
    return config_factory(**kwargs)
