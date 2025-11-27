"""Use cases for the identity service application layer."""

# Existing JWT authentication use cases
# Multi-method authentication use cases
from .authenticate_user import AuthenticateUserRequest, AuthenticateUserUseCase

# API Key authentication use cases
from .authenticate_with_api_key import (
    APIKeyAuthenticationRequest,
    AuthenticateWithAPIKeyUseCase,
    CreateAPIKeyRequest,
    CreateAPIKeyResult,
    CreateAPIKeyUseCase,
    RevokeAPIKeyRequest,
    RevokeAPIKeyResult,
    RevokeAPIKeyUseCase,
)

# Basic authentication use cases
from .authenticate_with_basic import (
    AuthenticateWithBasicUseCase,
    BasicAuthenticationRequest,
    ChangePasswordRequest,
    ChangePasswordResult,
    ChangePasswordUseCase,
)
from .authenticate_with_jwt import (
    AuthenticateWithJWTRequest,
    AuthenticateWithJWTUseCase,
)
from .validate_token import (
    TokenValidationResult,
    ValidateTokenRequest,
    ValidateTokenUseCase,
)

__all__ = [
    # Existing JWT use cases
    "AuthenticateWithJWTRequest",
    "AuthenticateWithJWTUseCase",
    "ValidateTokenRequest",
    "ValidateTokenUseCase",
    "TokenValidationResult",
    # Multi-method authentication
    "AuthenticateUserRequest",
    "AuthenticateUserUseCase",
    # Basic authentication
    "BasicAuthenticationRequest",
    "AuthenticateWithBasicUseCase",
    "ChangePasswordRequest",
    "ChangePasswordResult",
    "ChangePasswordUseCase",
    # API Key authentication
    "APIKeyAuthenticationRequest",
    "AuthenticateWithAPIKeyUseCase",
    "CreateAPIKeyRequest",
    "CreateAPIKeyResult",
    "CreateAPIKeyUseCase",
    "RevokeAPIKeyRequest",
    "RevokeAPIKeyResult",
    "RevokeAPIKeyUseCase",
]
