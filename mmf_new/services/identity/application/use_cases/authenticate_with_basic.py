"""
Basic authentication use case.

This use case handles username/password authentication following
the hexagonal architecture pattern.
"""

from dataclasses import dataclass

from mmf_new.core.application.base import UseCase, ValidationError
from mmf_new.services.identity.application.ports_out import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationResult,
    BasicAuthenticationProvider,
)


@dataclass
class BasicAuthenticationRequest:
    """Request for basic username/password authentication."""

    username: str
    password: str
    context: AuthenticationContext | None = None

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.username:
            raise ValidationError("Username is required")

        if not self.password:
            raise ValidationError("Password is required")

        if not isinstance(self.username, str):
            raise ValidationError("Username must be a string")

        if not isinstance(self.password, str):
            raise ValidationError("Password must be a string")


class AuthenticateWithBasicUseCase(UseCase[BasicAuthenticationRequest, AuthenticationResult]):
    """
    Use case for basic username/password authentication.

    This use case orchestrates basic authentication using the configured
    basic authentication provider.
    """

    def __init__(self, provider: BasicAuthenticationProvider) -> None:
        """
        Initialize use case with basic authentication provider.

        Args:
            provider: Basic authentication provider implementation
        """
        self._provider = provider

    async def execute(self, request: BasicAuthenticationRequest) -> AuthenticationResult:
        """
        Execute basic authentication.

        Args:
            request: Authentication request with username and password

        Returns:
            Authentication result with user information if successful
        """
        try:
            # Create credentials for the provider

            credentials = AuthenticationCredentials(
                method=AuthenticationMethod.BASIC,
                credentials={"username": request.username, "password": request.password},
                metadata={"auth_method": "basic"},
            )

            # Use the provider to authenticate
            result = await self._provider.authenticate(credentials, request.context)

            return result

        except ValidationError:
            # Re-raise validation errors as-is
            raise

        except Exception as error:
            # Handle unexpected errors
            return AuthenticationResult.failure_result(
                error_message="Unexpected error during basic authentication",
                method=AuthenticationMethod.BASIC,
                error_code="INTERNAL_ERROR",
                metadata={"original_error": str(error)},
            )


@dataclass
class ChangePasswordRequest:
    """Request for changing user password."""

    username: str
    current_password: str
    new_password: str
    context: AuthenticationContext | None = None

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.username:
            raise ValidationError("Username is required")

        if not self.current_password:
            raise ValidationError("Current password is required")

        if not self.new_password:
            raise ValidationError("New password is required")

        if len(self.new_password) < 8:
            raise ValidationError("New password must be at least 8 characters long")


@dataclass
class ChangePasswordResult:
    """Result of password change operation."""

    success: bool
    message: str | None = None
    error_code: str | None = None


class ChangePasswordUseCase(UseCase[ChangePasswordRequest, ChangePasswordResult]):
    """
    Use case for changing user password.

    This use case handles password changes with proper validation
    and security checks.
    """

    def __init__(self, provider: BasicAuthenticationProvider) -> None:
        """
        Initialize use case with basic authentication provider.

        Args:
            provider: Basic authentication provider implementation
        """
        self._provider = provider

    async def execute(self, request: ChangePasswordRequest) -> ChangePasswordResult:
        """
        Execute password change.

        Args:
            request: Password change request

        Returns:
            Change password result
        """
        try:
            # Use the provider to change password
            success = await self._provider.change_password(
                username=request.username,
                old_password=request.current_password,
                new_password=request.new_password,
                context=request.context,
            )

            if success:
                return ChangePasswordResult(success=True, message="Password changed successfully")
            else:
                return ChangePasswordResult(
                    success=False, message="Password change failed", error_code="CHANGE_FAILED"
                )

        except ValidationError as error:
            return ChangePasswordResult(
                success=False, message=str(error), error_code="VALIDATION_ERROR"
            )

        except Exception:
            return ChangePasswordResult(
                success=False,
                message="Unexpected error during password change",
                error_code="INTERNAL_ERROR",
            )
