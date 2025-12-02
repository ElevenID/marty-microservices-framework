"""
Token Provider outbound port for JWT authentication.

This port defines the interface for creating and validating JWT tokens.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from ...domain.models import AuthenticatedUser


class TokenError(Exception):
    """Base exception for token-related errors."""


class TokenCreationError(TokenError):
    """Raised when token creation fails."""


class TokenValidationError(TokenError):
    """Raised when token validation fails."""


class TokenProvider(ABC):
    """
    Outbound port for JWT token operations.

    This interface abstracts token creation and validation,
    allowing different JWT implementations to be plugged in.
    """

    @abstractmethod
    async def create_token(
        self,
        user: AuthenticatedUser,
        expires_at: datetime | None = None,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a JWT token for the authenticated user.

        Args:
            user: The authenticated user to create token for
            expires_at: Optional custom expiration time
            additional_claims: Optional additional JWT claims

        Returns:
            JWT token string

        Raises:
            TokenCreationError: If token creation fails
        """
        raise NotImplementedError

    @abstractmethod
    async def validate_token(self, token: str) -> AuthenticatedUser:
        """
        Validate a JWT token and extract user information.

        Args:
            token: JWT token string to validate

        Returns:
            AuthenticatedUser object from token claims

        Raises:
            TokenValidationError: If token is invalid, expired, or malformed
        """
        raise NotImplementedError

    @abstractmethod
    async def refresh_token(self, token: str, new_expires_at: datetime | None = None) -> str:
        """
        Refresh an existing JWT token with new expiration.

        Args:
            token: Current valid JWT token
            new_expires_at: New expiration time (if None, uses default)

        Returns:
            New JWT token string

        Raises:
            TokenValidationError: If current token is invalid
            TokenCreationError: If new token creation fails
        """
        raise NotImplementedError
