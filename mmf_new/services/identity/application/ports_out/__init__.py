"""Outbound ports for external dependencies."""

from abc import ABC, abstractmethod

from mmf_new.services.identity.domain.models import Credentials, UserId

from .authentication_provider import (
    APIKeyAuthenticationProvider,
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationError,
    AuthenticationMethod,
    AuthenticationMethodNotSupportedError,
    AuthenticationProvider,
    AuthenticationProviderError,
    AuthenticationResult,
    BasicAuthenticationProvider,
    CredentialValidationError,
)
from .token_provider import (
    TokenCreationError,
    TokenError,
    TokenProvider,
    TokenValidationError,
)


class UserRepository(ABC):
    """Port for user data persistence."""

    @abstractmethod
    def find_by_username(self, username: str) -> UserId | None:
        """Find a user by username."""

    @abstractmethod
    def verify_credentials(self, credentials: Credentials) -> bool:
        """Verify user credentials."""


class EventBus(ABC):
    """Port for publishing domain events."""

    @abstractmethod
    def publish(self, event: dict[str, any]) -> None:
        """Publish an event."""


__all__ = [
    "UserRepository",
    "EventBus",
    "TokenProvider",
    "TokenError",
    "TokenCreationError",
    "TokenValidationError",
]

# Authentication provider interfaces

__all__ = [
    # Existing exports
    "TokenProvider",
    "TokenError",
    "TokenCreationError",
    "TokenValidationError",
    "UserRepository",
    # New authentication provider exports
    "AuthenticationProvider",
    "BasicAuthenticationProvider",
    "APIKeyAuthenticationProvider",
    "AuthenticationMethod",
    "AuthenticationCredentials",
    "AuthenticationContext",
    "AuthenticationResult",
    "AuthenticationError",
    "CredentialValidationError",
    "AuthenticationMethodNotSupportedError",
    "AuthenticationProviderError",
]
