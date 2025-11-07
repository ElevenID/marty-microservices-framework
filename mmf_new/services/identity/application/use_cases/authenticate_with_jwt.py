"""
JWT Authentication Use Case Implementation.

This module implements the business logic for JWT authentication,
orchestrating domain models and external services through ports.
"""

from dataclasses import dataclass

from mmf_new.services.identity.application.ports_out.token_provider import (
    TokenProvider,
    TokenValidationError,
)
from mmf_new.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
    AuthenticationResult,
)


@dataclass
class AuthenticateWithJWTRequest:
    """Request object for JWT authentication."""

    token: str

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.token:
            raise ValueError("Token is required")

        if not isinstance(self.token, str):
            raise TypeError("Token must be a string")


class AuthenticateWithJWTUseCase:
    """
    Use case for authenticating users with JWT tokens.

    This implements the core business logic for JWT authentication
    following hexagonal architecture principles.
    """

    def __init__(self, token_provider: TokenProvider) -> None:
        """
        Initialize use case with required dependencies.

        Args:
            token_provider: Service for JWT token operations
        """
        self._token_provider = token_provider

    async def execute(self, request: AuthenticateWithJWTRequest) -> AuthenticationResult:
        """
        Execute JWT authentication for a user.

        Args:
            request: Authentication request containing JWT token

        Returns:
            AuthenticationResult with success/failure details
        """
        try:
            # Validate and extract user from token
            authenticated_user = await self._token_provider.validate_token(request.token)

            # Return successful authentication
            return AuthenticationResult.create_success(
                user=authenticated_user,
                metadata={"token": request.token, "auth_method": "JWT"}
            )

        except (TokenValidationError, ValueError) as error:
            # Handle token validation failures
            return AuthenticationResult.failure(
                message=f"Token validation failed: {error}",
                code=AuthenticationErrorCode.TOKEN_INVALID,
                metadata={"original_error": str(error)}
            )

        except Exception as error:
            # Handle unexpected errors
            return AuthenticationResult.failure(
                message="Unexpected error during JWT authentication",
                code=AuthenticationErrorCode.INTERNAL_ERROR,
                metadata={"original_error": str(error)}
            )
