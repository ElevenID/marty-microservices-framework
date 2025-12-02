"""
JWT Token Validation Use Case Implementation.

This module implements standalone token validation without full authentication,
useful for middleware and authorization checks.
"""

from dataclasses import dataclass

from mmf.services.identity.application.ports_out import (
    TokenProvider,
    TokenValidationError,
)
from mmf.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
)


@dataclass
class ValidateTokenRequest:
    """Request object for token validation."""

    token: str

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.token:
            raise ValueError("Token is required")

        if not isinstance(self.token, str):
            raise TypeError("Token must be a string")


@dataclass
class TokenValidationResult:
    """Result of token validation operation."""

    is_valid: bool
    user: AuthenticatedUser | None = None
    error_message: str | None = None
    error_code: AuthenticationErrorCode | None = None

    @classmethod
    def success(cls, user: AuthenticatedUser) -> "TokenValidationResult":
        """Create successful validation result."""
        return cls(is_valid=True, user=user)

    @classmethod
    def failure(cls, message: str, code: AuthenticationErrorCode) -> "TokenValidationResult":
        """Create failed validation result."""
        return cls(is_valid=False, error_message=message, error_code=code)


class ValidateTokenUseCase:
    """
    Use case for validating JWT tokens without full authentication.

    This is useful for middleware, authorization checks, and other
    scenarios where you need to verify a token and extract user
    information without going through a full authentication flow.
    """

    def __init__(self, token_provider: TokenProvider) -> None:
        """
        Initialize use case with required dependencies.

        Args:
            token_provider: Service for JWT token operations
        """
        self._token_provider = token_provider

    async def execute(self, request: ValidateTokenRequest) -> TokenValidationResult:
        """
        Execute token validation.

        Args:
            request: Validation request containing JWT token

        Returns:
            TokenValidationResult with validation outcome
        """
        try:
            # Validate and extract user from token
            authenticated_user = await self._token_provider.validate_token(request.token)

            # Return successful validation
            return TokenValidationResult.success(user=authenticated_user)

        except TokenValidationError as error:
            # Handle token validation failures
            return TokenValidationResult.failure(
                message=f"Token validation failed: {error}",
                code=AuthenticationErrorCode.TOKEN_INVALID,
            )

        except (ValueError, TypeError) as error:
            # Handle request validation errors
            return TokenValidationResult.failure(
                message=f"Invalid request: {error}",
                code=AuthenticationErrorCode.TOKEN_INVALID,
            )

        except Exception:
            # Handle unexpected errors
            return TokenValidationResult.failure(
                message="Unexpected error during token validation",
                code=AuthenticationErrorCode.INTERNAL_ERROR,
            )
