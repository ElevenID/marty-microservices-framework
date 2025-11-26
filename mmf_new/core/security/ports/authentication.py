"""
Authentication Ports

This module defines interfaces for authentication providers.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..domain.models.result import AuthenticationResult
from ..domain.models.user import SecurityPrincipal
from ..domain.enums import IdentityProviderType


@runtime_checkable
class IAuthenticator(Protocol):
    """Interface for authentication providers."""

    async def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """
        Authenticate a user based on provided credentials.

        Args:
            credentials: A dictionary containing authentication credentials.

        Returns:
            AuthenticationResult: The result of the authentication attempt.
        """
        ...

    async def validate_token(self, token: str) -> AuthenticationResult:
        """
        Validate an authentication token.

        Args:
            token: The token string to validate.

        Returns:
            AuthenticationResult: The result of the token validation.
        """
        ...


@runtime_checkable
class IIdentityProvider(Protocol):
    """Interface for identity providers."""

    def authenticate(self, credentials: dict[str, Any]) -> SecurityPrincipal | None:
        """
        Authenticate credentials with this provider.

        Args:
            credentials: Authentication credentials

        Returns:
            SecurityPrincipal if authenticated, None otherwise
        """
        ...

    def get_provider_type(self) -> IdentityProviderType:
        """
        Get the provider type.

        Returns:
            IdentityProviderType enum value
        """
        ...
