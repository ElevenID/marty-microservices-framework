"""
Authentication Provider outbound port for multiple authentication methods.

This port defines the interface for authenticating users using different methods
such as basic authentication, API keys, OAuth2, etc.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from ...domain.models import AuthenticatedUser


class AuthenticationMethod(Enum):
    """Supported authentication methods."""

    BASIC = "basic"  # Username/password
    API_KEY = "api_key"  # API key authentication  # pragma: allowlist secret
    JWT = "jwt"  # JWT token (existing)
    OAUTH2 = "oauth2"  # OAuth2 provider
    OIDC = "oidc"  # OpenID Connect
    SAML = "saml"  # SAML federation
    MTLS = "mtls"  # Mutual TLS
    MFA = "mfa"  # Multi-factor authentication
    SESSION = "session"  # Session-based
    ENVIRONMENT = "environment"  # Environment-based


class AuthenticationError(Exception):
    """Base exception for authentication-related errors."""


class CredentialValidationError(AuthenticationError):
    """Raised when credential validation fails."""


class AuthenticationMethodNotSupportedError(AuthenticationError):
    """Raised when authentication method is not supported."""


class AuthenticationProviderError(AuthenticationError):
    """Raised when authentication provider encounters an error."""


@dataclass
class AuthenticationCredentials:
    """
    Container for authentication credentials.

    Supports multiple types of credentials through a flexible dictionary approach.
    """

    method: AuthenticationMethod
    credentials: dict[str, Any]
    metadata: dict[str, Any] | None = None

    def get_credential(self, key: str, default: Any = None) -> Any:
        """Get a credential value safely."""
        return self.credentials.get(key, default)

    def has_credential(self, key: str) -> bool:
        """Check if a credential exists."""
        return key in self.credentials


@dataclass
class AuthenticationContext:
    """
    Context information for authentication operations.

    Provides additional context that may be needed for authentication decisions.
    """

    client_ip: str | None = None
    user_agent: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    timestamp: datetime | None = None
    additional_context: dict[str, Any] | None = None


@dataclass
class AuthenticationResult:
    """
    Result of an authentication operation.

    Contains the authenticated user and additional metadata about the authentication.
    """

    success: bool
    user: AuthenticatedUser | None = None
    method_used: AuthenticationMethod | None = None
    error_message: str | None = None
    error_code: str | None = None
    session_id: str | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def success_result(
        cls,
        user: AuthenticatedUser,
        method: AuthenticationMethod,
        session_id: str | None = None,
        expires_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AuthenticationResult":
        """Create a successful authentication result."""
        return cls(
            success=True,
            user=user,
            method_used=method,
            session_id=session_id,
            expires_at=expires_at,
            metadata=metadata or {},
        )

    @classmethod
    def failure_result(
        cls,
        error_message: str,
        method: AuthenticationMethod | None = None,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AuthenticationResult":
        """Create a failed authentication result."""
        return cls(
            success=False,
            method_used=method,
            error_message=error_message,
            error_code=error_code,
            metadata=metadata or {},
        )


class AuthenticationProvider(ABC):
    """
    Outbound port for authentication operations.

    This interface abstracts authentication using different methods,
    allowing the application layer to authenticate users without being
    coupled to specific authentication implementations.
    """

    @property
    @abstractmethod
    def supported_methods(self) -> list[AuthenticationMethod]:
        """Get list of authentication methods supported by this provider."""
        pass

    @abstractmethod
    def supports_method(self, method: AuthenticationMethod) -> bool:
        """Check if this provider supports the given authentication method."""
        pass

    @abstractmethod
    async def authenticate(
        self, credentials: AuthenticationCredentials, context: AuthenticationContext | None = None
    ) -> AuthenticationResult:
        """
        Authenticate user with provided credentials.

        Args:
            credentials: Authentication credentials and method
            context: Optional authentication context

        Returns:
            Authentication result with user information if successful

        Raises:
            AuthenticationMethodNotSupportedError: If method not supported
            AuthenticationProviderError: If provider encounters an error
        """
        pass

    @abstractmethod
    async def validate_credentials(
        self, credentials: AuthenticationCredentials, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Validate credentials without full authentication.

        Useful for credential format validation or basic checks.

        Args:
            credentials: Credentials to validate
            context: Optional authentication context

        Returns:
            True if credentials are valid format, False otherwise
        """
        pass

    @abstractmethod
    async def refresh_authentication(
        self, user: AuthenticatedUser, context: AuthenticationContext | None = None
    ) -> AuthenticationResult:
        """
        Refresh authentication for an already authenticated user.

        This is useful for extending session lifetime or refreshing tokens.

        Args:
            user: Currently authenticated user
            context: Optional authentication context

        Returns:
            New authentication result with updated credentials

        Raises:
            AuthenticationProviderError: If refresh fails
        """
        pass


class BasicAuthenticationProvider(AuthenticationProvider):
    """
    Provider interface for username/password authentication.

    Extends the base authentication provider with specific methods
    for password-based authentication.
    """

    @abstractmethod
    async def verify_password(
        self, username: str, password: str, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Verify username and password combination.

        Args:
            username: Username to verify
            password: Plain text password
            context: Optional authentication context

        Returns:
            True if credentials are valid, False otherwise
        """
        pass

    @abstractmethod
    async def change_password(
        self,
        username: str,
        old_password: str,
        new_password: str,
        context: AuthenticationContext | None = None,
    ) -> bool:
        """
        Change user password.

        Args:
            username: Username
            old_password: Current password
            new_password: New password
            context: Optional authentication context

        Returns:
            True if password changed successfully, False otherwise

        Raises:
            CredentialValidationError: If old password is invalid
        """
        pass


class APIKeyAuthenticationProvider(AuthenticationProvider):
    """
    Provider interface for API key authentication.

    Extends the base authentication provider with specific methods
    for API key-based authentication.
    """

    @abstractmethod
    async def verify_api_key(
        self, api_key: str, context: AuthenticationContext | None = None
    ) -> AuthenticatedUser | None:
        """
        Verify API key and return associated user.

        Args:
            api_key: API key to verify
            context: Optional authentication context

        Returns:
            Authenticated user if key is valid, None otherwise
        """
        pass

    @abstractmethod
    async def create_api_key(
        self,
        user_id: str,
        key_name: str | None = None,
        expires_at: datetime | None = None,
        permissions: list[str] | None = None,
        context: AuthenticationContext | None = None,
    ) -> str:
        """
        Create a new API key for a user.

        Args:
            user_id: User ID to create key for
            key_name: Optional name for the key
            expires_at: Optional expiration time
            permissions: Optional list of permissions
            context: Optional authentication context

        Returns:
            Generated API key string

        Raises:
            AuthenticationProviderError: If key creation fails
        """
        pass

    @abstractmethod
    async def revoke_api_key(
        self, api_key: str, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Revoke an API key.

        Args:
            api_key: API key to revoke
            context: Optional authentication context

        Returns:
            True if key was revoked, False if not found

        Raises:
            AuthenticationProviderError: If revocation fails
        """
        pass
