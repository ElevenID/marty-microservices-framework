"""
Multi-method user authentication use case.

This use case provides a unified interface for authenticating users using
multiple authentication methods (Basic, API Key, JWT, OAuth2, etc.).
"""

from dataclasses import dataclass

from mmf.core.application.base import UseCase, ValidationError
from mmf.services.identity.application.ports_out import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationProvider,
    AuthenticationResult,
)


@dataclass
class AuthenticateUserRequest:
    """Request for multi-method user authentication."""

    credentials: AuthenticationCredentials
    context: AuthenticationContext | None = None

    def __post_init__(self) -> None:
        """Validate request data."""
        if not self.credentials:
            raise ValidationError("Credentials are required")

        if not isinstance(self.credentials.method, AuthenticationMethod):
            raise ValidationError("Valid authentication method is required")


class AuthenticateUserUseCase(UseCase[AuthenticateUserRequest, AuthenticationResult]):
    """
    Use case for authenticating users with multiple authentication methods.

    This use case coordinates authentication across different providers,
    providing a single entry point for all authentication operations.
    """

    def __init__(self, authentication_providers: list[AuthenticationProvider]) -> None:
        """
        Initialize use case with authentication providers.

        Args:
            authentication_providers: List of authentication providers
        """
        self._providers = authentication_providers
        self._provider_map = {}

        # Build provider lookup map by supported methods
        for provider in authentication_providers:
            for method in provider.supported_methods:
                if method not in self._provider_map:
                    self._provider_map[method] = []
                self._provider_map[method].append(provider)

    async def execute(self, request: AuthenticateUserRequest) -> AuthenticationResult:
        """
        Execute multi-method authentication.

        Args:
            request: Authentication request with credentials and context

        Returns:
            Authentication result with user information if successful
        """
        method = request.credentials.method

        # Find providers that support the requested method
        providers = self._provider_map.get(method, [])

        if not providers:
            return AuthenticationResult.failure_result(
                error_message=f"Authentication method '{method.value}' is not supported",
                method=method,
                error_code="METHOD_NOT_SUPPORTED",
            )

        # Try authentication with each provider that supports the method
        last_error = None

        for provider in providers:
            try:
                # Attempt authentication with this provider
                result = await provider.authenticate(request.credentials, request.context)

                if result.success:
                    return result

                # Store the error for potential reporting
                last_error = result.error_message

            except Exception as error:
                last_error = str(error)
                continue

        # All providers failed
        return AuthenticationResult.failure_result(
            error_message=last_error or f"Authentication failed for method '{method.value}'",
            method=method,
            error_code="AUTHENTICATION_FAILED",
        )

    def get_supported_methods(self) -> list[AuthenticationMethod]:
        """Get all supported authentication methods."""
        return list(self._provider_map.keys())

    def get_providers_for_method(
        self, method: AuthenticationMethod
    ) -> list[AuthenticationProvider]:
        """Get providers that support a specific authentication method."""
        return self._provider_map.get(method, [])
