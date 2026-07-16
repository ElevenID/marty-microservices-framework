"""
Application layer for identity service.

This layer contains the business logic, use cases, and ports that define
the application's behavior, following hexagonal architecture principles.
"""

# Import ports
from .ports_out import (
    APIKeyAuthenticationProvider,
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationProvider,
    AuthenticationProviderError,
    AuthenticationResult,
    BasicAuthenticationProvider,
)

# Import services
from .services import AuthenticationManager, authentication_manager

# Import use cases
from .use_cases import (
    AuthenticateUserUseCase,
    AuthenticateWithAPIKeyUseCase,
    AuthenticateWithBasicUseCase,
    ChangePasswordUseCase,
    CreateAPIKeyUseCase,
    RevokeAPIKeyUseCase,
)

__all__ = [
    # Use Cases
    "AuthenticateUserUseCase",
    "AuthenticateWithBasicUseCase",
    "ChangePasswordUseCase",
    "AuthenticateWithAPIKeyUseCase",
    "CreateAPIKeyUseCase",
    "RevokeAPIKeyUseCase",
    # Services
    "AuthenticationManager",
    "authentication_manager",
    # Ports and Data Structures
    "AuthenticationProvider",
    "BasicAuthenticationProvider",
    "APIKeyAuthenticationProvider",
    "AuthenticationCredentials",
    "AuthenticationContext",
    "AuthenticationResult",
    "AuthenticationMethod",
    "AuthenticationProviderError",
]
