"""
API Key authentication use case.

This use case handles API key-based authentication following
the hexagonal architecture pattern.
"""

from dataclasses import dataclass
from datetime import datetime

from mmf_new.core.application.base import UseCase, ValidationError
from mmf_new.services.identity.application.ports_out import (
    APIKeyAuthenticationProvider,
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationResult,
)


@dataclass
class APIKeyAuthenticationRequest:
    """Request for API key authentication."""

    api_key: str
    context: AuthenticationContext | None = None

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.api_key:
            raise ValidationError("API key is required")

        if not isinstance(self.api_key, str):
            raise ValidationError("API key must be a string")


class AuthenticateWithAPIKeyUseCase(UseCase[APIKeyAuthenticationRequest, AuthenticationResult]):
    """
    Use case for API key authentication.

    This use case orchestrates API key authentication using the configured
    API key authentication provider.
    """

    def __init__(self, provider: APIKeyAuthenticationProvider) -> None:
        """
        Initialize use case with API key authentication provider.

        Args:
            provider: API key authentication provider implementation
        """
        self._provider = provider

    async def execute(self, request: APIKeyAuthenticationRequest) -> AuthenticationResult:
        """
        Execute API key authentication.

        Args:
            request: Authentication request with API key

        Returns:
            Authentication result with user information if successful
        """
        try:
            # Create credentials for the provider

            credentials = AuthenticationCredentials(
                method=AuthenticationMethod.API_KEY,
                credentials={"api_key": request.api_key},
                metadata={"auth_method": "api_key"},
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
                error_message="Unexpected error during API key authentication",
                method=AuthenticationMethod.API_KEY,
                error_code="INTERNAL_ERROR",
                metadata={"original_error": str(error)},
            )


@dataclass
class CreateAPIKeyRequest:
    """Request for creating an API key."""

    user_id: str
    key_name: str | None = None
    expires_at: datetime | None = None
    permissions: list[str] | None = None
    context: AuthenticationContext | None = None

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.user_id:
            raise ValidationError("User ID is required")

        if self.key_name and not isinstance(self.key_name, str):
            raise ValidationError("Key name must be a string")

        if self.permissions and not isinstance(self.permissions, list):
            raise ValidationError("Permissions must be a list")


@dataclass
class CreateAPIKeyResult:
    """Result of API key creation."""

    success: bool
    api_key: str | None = None
    message: str | None = None
    error_code: str | None = None


class CreateAPIKeyUseCase(UseCase[CreateAPIKeyRequest, CreateAPIKeyResult]):
    """
    Use case for creating API keys.

    This use case handles API key creation with proper validation
    and security controls.
    """

    def __init__(self, provider: APIKeyAuthenticationProvider) -> None:
        """
        Initialize use case with API key authentication provider.

        Args:
            provider: API key authentication provider implementation
        """
        self._provider = provider

    async def execute(self, request: CreateAPIKeyRequest) -> CreateAPIKeyResult:
        """
        Execute API key creation.

        Args:
            request: API key creation request

        Returns:
            Create API key result with the new API key if successful
        """
        try:
            # Use the provider to create API key
            api_key = await self._provider.create_api_key(
                user_id=request.user_id,
                key_name=request.key_name,
                expires_at=request.expires_at,
                permissions=request.permissions,
                context=request.context,
            )

            return CreateAPIKeyResult(
                success=True, api_key=api_key, message="API key created successfully"
            )

        except ValidationError as error:
            return CreateAPIKeyResult(
                success=False, message=str(error), error_code="VALIDATION_ERROR"
            )

        except Exception:
            return CreateAPIKeyResult(
                success=False,
                message="Unexpected error during API key creation",
                error_code="INTERNAL_ERROR",
            )


@dataclass
class RevokeAPIKeyRequest:
    """Request for revoking an API key."""

    api_key: str
    context: AuthenticationContext | None = None

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.api_key:
            raise ValidationError("API key is required")


@dataclass
class RevokeAPIKeyResult:
    """Result of API key revocation."""

    success: bool
    message: str | None = None
    error_code: str | None = None


class RevokeAPIKeyUseCase(UseCase[RevokeAPIKeyRequest, RevokeAPIKeyResult]):
    """
    Use case for revoking API keys.

    This use case handles API key revocation with proper
    security controls and audit logging.
    """

    def __init__(self, provider: APIKeyAuthenticationProvider) -> None:
        """
        Initialize use case with API key authentication provider.

        Args:
            provider: API key authentication provider implementation
        """
        self._provider = provider

    async def execute(self, request: RevokeAPIKeyRequest) -> RevokeAPIKeyResult:
        """
        Execute API key revocation.

        Args:
            request: API key revocation request

        Returns:
            Revoke API key result
        """
        try:
            # Use the provider to revoke API key
            success = await self._provider.revoke_api_key(
                api_key=request.api_key, context=request.context
            )

            if success:
                return RevokeAPIKeyResult(success=True, message="API key revoked successfully")
            else:
                return RevokeAPIKeyResult(
                    success=False,
                    message="API key not found or already revoked",
                    error_code="KEY_NOT_FOUND",
                )

        except ValidationError as error:
            return RevokeAPIKeyResult(
                success=False, message=str(error), error_code="VALIDATION_ERROR"
            )

        except Exception:
            return RevokeAPIKeyResult(
                success=False,
                message="Unexpected error during API key revocation",
                error_code="INTERNAL_ERROR",
            )
