"""
Configuration management for the integration layer.

Handles environment-specific settings and dependency injection
for JWT authentication components.
"""

import os
from dataclasses import dataclass


@dataclass
class IntegrationConfig:
    """Configuration for JWT authentication integration."""

    # JWT Settings
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

    # Path Configuration
    protected_paths: list[str] | None = None
    exclude_paths: list[str] | None = None

    def __post_init__(self):
        """Set default values and validate configuration."""
        if self.protected_paths is None:
            self.protected_paths = ["/api/", "/admin/"]

        if self.exclude_paths is None:
            self.exclude_paths = ["/auth/", "/health", "/docs", "/openapi.json"]

        if not self.jwt_secret_key:
            raise ValueError("JWT secret key is required")

    @classmethod
    def from_environment(cls) -> "IntegrationConfig":
        """Create configuration from environment variables."""
        secret_key = os.getenv("JWT_SECRET_KEY")
        if not secret_key:
            # For development/testing, use a default key
            secret_key = "dev-secret-key-change-in-production"

        return IntegrationConfig(
            jwt_secret_key=secret_key,  # pragma: allowlist secret
            jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            jwt_access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
            jwt_issuer=os.getenv("JWT_ISSUER"),
            jwt_audience=os.getenv("JWT_AUDIENCE"),
            protected_paths=os.getenv("JWT_PROTECTED_PATHS", "/api/,/admin/").split(","),
            exclude_paths=os.getenv(
                "JWT_EXCLUDE_PATHS", "/auth/,/health,/docs,/openapi.json"
            ).split(","),
        )
