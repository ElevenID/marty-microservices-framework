"""Authenticate with JWT use case implementation."""

from dataclasses import dataclass

from mmf_new.core.application.base import UnauthorizedError, UseCase, ValidationError
from mmf_new.services.identity.domain.models.authenticated_user import AuthenticatedUser
from mmf_new.services.identity.domain.models.authentication_result import (
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)


@dataclass
class AuthenticateWithJWTRequest:
    """Request for JWT authentication."""

    jwt_token: str


class AuthenticateWithJWTUseCase(
    UseCase[AuthenticateWithJWTRequest, AuthenticationResult]
):
    """Use case for authenticating users with JWT tokens."""

    async def execute(
        self, request: AuthenticateWithJWTRequest
    ) -> AuthenticationResult:
        """Execute the JWT authentication.

        Args:
            request: The authentication request containing the JWT token

        Returns:
            AuthenticationResult with user information if successful

        Raises:
            ValidationError: If the JWT token is invalid
            UnauthorizedError: If authentication fails
        """
        if not request.jwt_token:
            raise ValidationError("JWT token is required")

        if not request.jwt_token.strip():
            raise ValidationError("JWT token cannot be empty")

        # For demonstration purposes, this is a simple implementation
        # In a real implementation, you would:
        # 1. Validate the JWT signature
        # 2. Check expiration
        # 3. Extract user claims
        # 4. Verify user exists and is active

        try:
            # Mock JWT validation - in reality this would use a proper JWT library
            if request.jwt_token.startswith("valid-"):
                # Extract user information from token (mock)
                user_id = request.jwt_token.replace("valid-", "")

                user = AuthenticatedUser(
                    user_id=user_id, username=f"user_{user_id}", roles={"user"}
                )

                return AuthenticationResult(
                    status=AuthenticationStatus.SUCCESS, authenticated_user=user
                )
            else:
                return AuthenticationResult(
                    status=AuthenticationStatus.INVALID_CREDENTIALS,
                    error_message="Invalid JWT token",
                    error_code=AuthenticationErrorCode.TOKEN_INVALID,
                )

        except Exception as e:
            raise UnauthorizedError(f"JWT authentication failed: {str(e)}") from e
