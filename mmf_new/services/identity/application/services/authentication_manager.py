"""
Authentication Manager Service.

This service coordinates multiple authentication providers and provides a unified
interface for authentication operations across the system.
"""

import logging
from typing import Any

from mmf_new.services.identity.application.ports_out import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationProvider,
    AuthenticationProviderError,
    AuthenticationResult,
)
from mmf_new.services.identity.domain.models import AuthenticatedUser

logger = logging.getLogger(__name__)


class AuthenticationManagerError(Exception):
    """Raised when authentication manager operations fail."""

    pass


class AuthenticationManager:
    """
    Central authentication manager that coordinates multiple authentication providers.

    This service implements a strategy pattern where different authentication methods
    are handled by specific providers while maintaining a unified interface.
    """

    def __init__(self) -> None:
        """Initialize authentication manager with empty provider registry."""
        self._providers: dict[AuthenticationMethod, AuthenticationProvider] = {}
        self._default_provider: AuthenticationProvider | None = None

    def register_provider(
        self,
        method: AuthenticationMethod,
        provider: AuthenticationProvider,
        is_default: bool = False,
    ) -> None:
        """
        Register an authentication provider for a specific method.

        Args:
            method: Authentication method this provider handles
            provider: Provider implementation
            is_default: Whether this should be the default provider

        Raises:
            AuthenticationManagerError: If provider registration fails
        """
        try:
            if not provider.supports_method(method):
                raise AuthenticationManagerError(
                    f"Provider {provider.__class__.__name__} does not support method {method.value}"
                )

            self._providers[method] = provider

            if is_default or self._default_provider is None:
                self._default_provider = provider

            logger.info(f"Registered authentication provider for method: {method.value}")

        except Exception as error:
            raise AuthenticationManagerError(f"Failed to register provider: {error}") from error

    def unregister_provider(self, method: AuthenticationMethod) -> None:
        """
        Unregister an authentication provider.

        Args:
            method: Authentication method to unregister
        """
        if method in self._providers:
            provider = self._providers.pop(method)

            # Update default provider if needed
            if self._default_provider == provider:
                self._default_provider = (
                    next(iter(self._providers.values())) if self._providers else None
                )

            logger.info(f"Unregistered authentication provider for method: {method.value}")

    def get_provider(self, method: AuthenticationMethod) -> AuthenticationProvider | None:
        """
        Get the authentication provider for a specific method.

        Args:
            method: Authentication method

        Returns:
            Provider implementation or None if not found
        """
        return self._providers.get(method)

    def get_supported_methods(self) -> list[AuthenticationMethod]:
        """
        Get list of all supported authentication methods.

        Returns:
            list of supported authentication methods
        """
        return list(self._providers.keys())

    def has_provider(self, method: AuthenticationMethod) -> bool:
        """
        Check if a provider is registered for the given method.

        Args:
            method: Authentication method to check

        Returns:
            True if provider is registered, False otherwise
        """
        return method in self._providers

    async def authenticate(
        self, credentials: AuthenticationCredentials, context: AuthenticationContext | None = None
    ) -> AuthenticationResult:
        """
        Authenticate user using the appropriate provider for the credential method.

        Args:
            credentials: Authentication credentials
            context: Optional authentication context

        Returns:
            Authentication result
        """
        try:
            method = credentials.method
            provider = self.get_provider(method)

            if not provider:
                logger.warning(f"No provider registered for authentication method: {method.value}")
                return AuthenticationResult.failure_result(
                    error_message=f"Authentication method '{method.value}' not supported",
                    method=method,
                    error_code="METHOD_NOT_SUPPORTED",
                )

            logger.debug(f"Authenticating with method: {method.value}")
            result = await provider.authenticate(credentials, context)

            if result.success:
                logger.info(
                    f"Authentication successful for user: {result.user.user_id if result.user else 'unknown'}"
                )
            else:
                logger.warning(f"Authentication failed with method: {method.value}")

            return result

        except Exception as error:
            logger.error(f"Authentication error: {error}")
            return AuthenticationResult.failure_result(
                error_message="Authentication service error",
                method=credentials.method,
                error_code="INTERNAL_ERROR",
            )

    async def validate_credentials(
        self, credentials: AuthenticationCredentials, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Validate credentials format using the appropriate provider.

        Args:
            credentials: Credentials to validate
            context: Optional authentication context

        Returns:
            True if credentials are valid format, False otherwise
        """
        try:
            method = credentials.method
            provider = self.get_provider(method)

            if not provider:
                return False

            return await provider.validate_credentials(credentials, context)

        except Exception as error:
            logger.error(f"Credential validation error: {error}")
            return False

    async def refresh_authentication(
        self, user: AuthenticatedUser, context: AuthenticationContext | None = None
    ) -> AuthenticationResult:
        """
        Refresh authentication for a user using the appropriate provider.

        Args:
            user: Currently authenticated user
            context: Optional authentication context

        Returns:
            Refreshed authentication result
        """
        try:
            # Determine the authentication method from user metadata
            auth_method_str = user.auth_method

            # Map string to enum
            method_mapping = {
                "jwt": AuthenticationMethod.JWT,
                "basic": AuthenticationMethod.BASIC,
                "api_key": AuthenticationMethod.API_KEY,
                "oauth2": AuthenticationMethod.OAUTH2,
                "saml": AuthenticationMethod.SAML,
            }

            method = method_mapping.get(auth_method_str)
            if not method:
                return AuthenticationResult.failure_result(
                    error_message=f"Unknown authentication method: {auth_method_str}",
                    method=AuthenticationMethod.JWT,  # Default fallback
                    error_code="UNKNOWN_AUTH_METHOD",
                )

            provider = self.get_provider(method)

            if not provider:
                return AuthenticationResult.failure_result(
                    error_message=f"No provider for authentication method: {method.value}",
                    method=method,
                    error_code="PROVIDER_NOT_FOUND",
                )

            return await provider.refresh_authentication(user, context)

        except Exception as error:
            logger.error(f"Authentication refresh error: {error}")
            return AuthenticationResult.failure_result(
                error_message="Authentication refresh failed",
                method=AuthenticationMethod.JWT,  # Default fallback
                error_code="REFRESH_FAILED",
            )

    async def try_multiple_methods(
        self,
        credentials_list: list[AuthenticationCredentials],
        context: AuthenticationContext | None = None,
    ) -> AuthenticationResult:
        """
        Try authentication with multiple credential sets in order.

        This is useful for fallback authentication scenarios or when
        supporting legacy authentication alongside new methods.

        Args:
            credentials_list: list of credentials to try in order
            context: Optional authentication context

        Returns:
            First successful authentication result or final failure
        """
        try:
            if not credentials_list:
                return AuthenticationResult.failure_result(
                    error_message="No credentials provided",
                    method=AuthenticationMethod.JWT,  # Default
                    error_code="NO_CREDENTIALS",
                )

            last_result = None

            for credentials in credentials_list:
                result = await self.authenticate(credentials, context)

                if result.success:
                    logger.info(
                        f"Multi-method authentication succeeded with: {credentials.method.value}"
                    )
                    return result

                last_result = result
                logger.debug(
                    f"Authentication failed with {credentials.method.value}, trying next method"
                )

            logger.warning("All authentication methods failed")
            return last_result or AuthenticationResult.failure_result(
                error_message="All authentication methods failed",
                method=credentials_list[-1].method,
                error_code="ALL_METHODS_FAILED",
            )

        except Exception as error:
            logger.error(f"Multi-method authentication error: {error}")
            return AuthenticationResult.failure_result(
                error_message="Authentication service error",
                method=credentials_list[0].method if credentials_list else AuthenticationMethod.JWT,
                error_code="INTERNAL_ERROR",
            )

    def get_provider_info(self) -> dict[str, dict[str, any]]:
        """
        Get information about all registered providers.

        Returns:
            Dictionary with provider information
        """
        return {
            method.value: {
                "provider_class": provider.__class__.__name__,
                "supported_methods": [m.value for m in provider.supported_methods],
                "is_default": provider == self._default_provider,
            }
            for method, provider in self._providers.items()
        }


# Singleton instance for global use
authentication_manager = AuthenticationManager()
