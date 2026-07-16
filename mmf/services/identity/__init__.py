"""
MMF Identity Service.

This package provides comprehensive identity and authentication services
following hexagonal architecture principles.
"""

# Application Layer
from .application import (  # Use Cases; Services; Ports and Data Structures
    APIKeyAuthenticationProvider,
    AuthenticateUserUseCase,
    AuthenticateWithAPIKeyUseCase,
    AuthenticateWithBasicUseCase,
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationManager,
    AuthenticationMethod,
    AuthenticationProvider,
    AuthenticationProviderError,
    AuthenticationResult,
    BasicAuthenticationProvider,
    ChangePasswordUseCase,
    CreateAPIKeyUseCase,
    RevokeAPIKeyUseCase,
    authentication_manager,
)

# Configuration
from .config import (
    AuthenticationConfig,
    AuthenticationProviderType,
    AuthenticationSettings,
    create_development_config,
    create_production_config,
    create_testing_config,
    get_authentication_settings,
    load_config_from_file,
)

# Domain Layer
from .domain.models import AuthenticatedUser

# Infrastructure Layer
from .infrastructure.adapters import (
    APIKeyAdapter,
    APIKeyConfig,
    BasicAuthAdapter,
    BasicAuthConfig,
)

__all__ = [
    # Configuration
    "AuthenticationConfig",
    "AuthenticationProviderType",
    "AuthenticationSettings",
    "create_development_config",
    "create_production_config",
    "create_testing_config",
    "get_authentication_settings",
    "load_config_from_file",
    # Domain Models
    "AuthenticatedUser",
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
    # Infrastructure Adapters
    "BasicAuthAdapter",
    "BasicAuthConfig",
    "APIKeyAdapter",
    "APIKeyConfig",
]
