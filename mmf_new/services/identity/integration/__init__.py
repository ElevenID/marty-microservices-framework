"""
JWT Authentication Integration Layer.

This module provides FastAPI integration components for JWT authentication,
including HTTP endpoints, middleware, and configuration management.
"""

# Configuration management
from .configuration import (
    CONFIG_REGISTRY,
    JWTAuthConfig,
    create_development_config,
    create_production_config,
    create_testing_config,
    get_config_for_environment,
    load_config_from_env,
    load_config_from_file,
)

# HTTP endpoints for FastAPI integration
from .http_endpoints import (
    AuthenticatedUserResponse,
    AuthenticateJWTRequestModel,
    AuthenticationResponse,
    TokenValidationResponse,
    ValidateTokenRequestModel,
    get_authenticate_use_case,
    get_jwt_config,
    get_jwt_token_provider,
    get_validate_token_use_case,
    router,
)

# Middleware for automatic authentication
from .middleware import (
    JWTAuthenticationMiddleware,
    JWTBearer,
    get_current_user,
    require_authenticated_user,
    require_permission,
    require_role,
)

__all__ = [
    # HTTP endpoints
    "router",
    "AuthenticateJWTRequestModel",
    "ValidateTokenRequestModel",
    "AuthenticatedUserResponse",
    "AuthenticationResponse",
    "TokenValidationResponse",
    "get_jwt_config",
    "get_jwt_token_provider",
    "get_authenticate_use_case",
    "get_validate_token_use_case",
    # Middleware
    "JWTAuthenticationMiddleware",
    "JWTBearer",
    "get_current_user",
    "require_authenticated_user",
    "require_permission",
    "require_role",
    # Configuration
    "JWTAuthConfig",
    "create_development_config",
    "create_testing_config",
    "create_production_config",
    "load_config_from_env",
    "load_config_from_file",
    "get_config_for_environment",
    "CONFIG_REGISTRY",
]
