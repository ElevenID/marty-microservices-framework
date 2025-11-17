"""
Basic Authentication Provider Infrastructure Adapter.

This module implements the BasicAuthenticationProvider port using bcrypt
for secure password hashing and an in-memory user store for demonstration.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt

from mmf_new.services.identity.application.ports_out import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationProvider,
    AuthenticationResult,
    BasicAuthenticationProvider,
    CredentialValidationError,
)
from mmf_new.services.identity.domain.models import AuthenticatedUser

logger = logging.getLogger(__name__)


class BasicAuthConfig:
    """Configuration for basic authentication provider."""

    def __init__(
        self,
        password_min_length: int = 8,
        password_require_uppercase: bool = True,
        password_require_lowercase: bool = True,
        password_require_digits: bool = True,
        password_require_special: bool = False,
        bcrypt_rounds: int = 12,
        enable_user_registration: bool = False,
    ) -> None:
        """
        Initialize basic authentication configuration.

        Args:
            password_min_length: Minimum password length
            password_require_uppercase: Require uppercase letters
            password_require_lowercase: Require lowercase letters
            password_require_digits: Require digits
            password_require_special: Require special characters
            bcrypt_rounds: BCrypt hash rounds (higher = more secure but slower)
            enable_user_registration: Allow new user registration
        """
        self.password_min_length = password_min_length
        self.password_require_uppercase = password_require_uppercase
        self.password_require_lowercase = password_require_lowercase
        self.password_require_digits = password_require_digits
        self.password_require_special = password_require_special
        self.bcrypt_rounds = bcrypt_rounds
        self.enable_user_registration = enable_user_registration


class BasicAuthAdapter(BasicAuthenticationProvider):
    """
    Basic authentication provider implementation using bcrypt.

    This adapter implements username/password authentication with secure
    password hashing using bcrypt. For production use, replace the in-memory
    user store with a proper database.
    """

    def __init__(self, config: BasicAuthConfig) -> None:
        """
        Initialize basic authentication adapter.

        Args:
            config: Basic authentication configuration
        """
        self._config = config
        self._users = {}  # In production, use a proper user repository

        # Create default admin user for demonstration
        self._create_default_users()

    @property
    def supported_methods(self) -> list[AuthenticationMethod]:
        """Get list of authentication methods supported by this provider."""
        return [AuthenticationMethod.BASIC]

    def supports_method(self, method: AuthenticationMethod) -> bool:
        """Check if this provider supports the given authentication method."""
        return method == AuthenticationMethod.BASIC

    async def authenticate(
        self, credentials: AuthenticationCredentials, context: AuthenticationContext | None = None
    ) -> AuthenticationResult:
        """
        Authenticate user with username/password credentials.

        Args:
            credentials: Authentication credentials containing username/password
            context: Optional authentication context

        Returns:
            Authentication result with user information if successful
        """
        try:
            if not self.supports_method(credentials.method):
                return AuthenticationResult.failure_result(
                    error_message=f"Authentication method '{credentials.method.value}' not supported",
                    method=credentials.method,
                    error_code="METHOD_NOT_SUPPORTED",
                )

            username = credentials.get_credential("username")
            password = credentials.get_credential("password")

            if not username or not password:
                return AuthenticationResult.failure_result(
                    error_message="Username and password are required",
                    method=credentials.method,
                    error_code="MISSING_CREDENTIALS",
                )

            # Verify password
            if await self.verify_password(username, password, context):
                user_data = self._users.get(username)
                if user_data:
                    user = AuthenticatedUser(
                        user_id=user_data["user_id"],
                        username=username,
                        email=user_data.get("email"),
                        roles=set(user_data.get("roles", [])),
                        permissions=set(user_data.get("permissions", [])),
                        auth_method="basic",
                        created_at=datetime.now(timezone.utc),
                        expires_at=datetime.now(timezone.utc)
                        + timedelta(hours=8),  # 8 hour session
                        metadata={
                            "auth_provider": "basic",
                            "last_login": datetime.now(timezone.utc).isoformat(),
                            "client_ip": context.client_ip if context else None,
                        },
                    )

                    logger.info(f"Basic authentication successful for user: {username}")

                    return AuthenticationResult.success_result(
                        user=user,
                        method=AuthenticationMethod.BASIC,
                        expires_at=user.expires_at,
                        metadata={
                            "provider": "basic_auth",
                            "authentication_time": datetime.now(timezone.utc).isoformat(),
                        },
                    )

            logger.warning(f"Basic authentication failed for user: {username}")
            return AuthenticationResult.failure_result(
                error_message="Invalid username or password",
                method=credentials.method,
                error_code="INVALID_CREDENTIALS",
            )

        except Exception as error:
            logger.error(f"Basic authentication error: {error}")
            return AuthenticationResult.failure_result(
                error_message="Authentication service error",
                method=credentials.method,
                error_code="INTERNAL_ERROR",
            )

    async def validate_credentials(
        self, credentials: AuthenticationCredentials, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Validate credentials format without full authentication.

        Args:
            credentials: Credentials to validate
            context: Optional authentication context

        Returns:
            True if credentials are valid format, False otherwise
        """
        try:
            username = credentials.get_credential("username")
            password = credentials.get_credential("password")

            if not username or not password:
                return False

            if not isinstance(username, str) or not isinstance(password, str):
                return False

            # Basic format validation
            if len(username.strip()) == 0 or len(password) < self._config.password_min_length:
                return False

            return True

        except Exception:
            return False

    async def refresh_authentication(
        self, user: AuthenticatedUser, context: AuthenticationContext | None = None
    ) -> AuthenticationResult:
        """
        Refresh authentication for an already authenticated user.

        For basic auth, this extends the session lifetime.

        Args:
            user: Currently authenticated user
            context: Optional authentication context

        Returns:
            New authentication result with updated expiration
        """
        try:
            # Verify user still exists
            if user.username and user.username in self._users:
                # Create new user with extended expiration
                refreshed_user = AuthenticatedUser(
                    user_id=user.user_id,
                    username=user.username,
                    email=user.email,
                    roles=user.roles,
                    permissions=user.permissions,
                    auth_method=user.auth_method,
                    created_at=user.created_at,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
                    metadata={
                        **user.metadata,
                        "refreshed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

                return AuthenticationResult.success_result(
                    user=refreshed_user,
                    method=AuthenticationMethod.BASIC,
                    expires_at=refreshed_user.expires_at,
                    metadata={"refreshed": True},
                )

            return AuthenticationResult.failure_result(
                error_message="User no longer exists",
                method=AuthenticationMethod.BASIC,
                error_code="USER_NOT_FOUND",
            )

        except Exception as error:
            logger.error(f"Authentication refresh error: {error}")
            return AuthenticationResult.failure_result(
                error_message="Authentication refresh failed",
                method=AuthenticationMethod.BASIC,
                error_code="REFRESH_FAILED",
            )

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
        try:
            user_data = self._users.get(username)
            if not user_data:
                # Hash a dummy password to prevent timing attacks
                bcrypt.checkpw(b"dummy", b"$2b$12$dummy.hash.to.prevent.timing.attacks.here")
                return False

            stored_hash = user_data.get("password_hash")
            if not stored_hash:
                return False

            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))

        except Exception as error:
            logger.error(f"Password verification error: {error}")
            return False

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
            CredentialValidationError: If old password is invalid or new password doesn't meet requirements
        """
        try:
            # Verify old password
            if not await self.verify_password(username, old_password, context):
                raise CredentialValidationError("Current password is incorrect")

            # Validate new password
            if not self._validate_password_policy(new_password):
                raise CredentialValidationError("New password does not meet policy requirements")

            # Hash new password
            new_hash = bcrypt.hashpw(
                new_password.encode("utf-8"), bcrypt.gensalt(rounds=self._config.bcrypt_rounds)
            )

            # Update user password
            if username in self._users:
                self._users[username]["password_hash"] = new_hash.decode("utf-8")
                self._users[username]["password_changed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()

                logger.info(f"Password changed successfully for user: {username}")
                return True

            return False

        except CredentialValidationError:
            # Re-raise validation errors
            raise
        except Exception as error:
            logger.error(f"Password change error: {error}")
            return False

    def _create_default_users(self) -> None:
        """Create default users for demonstration."""
        default_users = [
            {
                "username": "admin",
                "password": "admin123",  # In production, never hardcode passwords  # pragma: allowlist secret
                "email": "admin@example.com",
                "roles": ["admin", "user"],
                "permissions": ["read", "write", "admin"],
            },
            {
                "username": "user",
                "password": "user123",  # pragma: allowlist secret
                "email": "user@example.com",
                "roles": ["user"],
                "permissions": ["read"],
            },
        ]

        for user_data in default_users:
            password = user_data["password"]
            password_hash = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt(rounds=self._config.bcrypt_rounds)
            )

            self._users[user_data["username"]] = {
                "user_id": f"user_{user_data['username']}",
                "email": user_data["email"],
                "roles": user_data["roles"],
                "permissions": user_data["permissions"],
                "password_hash": password_hash.decode("utf-8"),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "password_changed_at": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
            }

    def _validate_password_policy(self, password: str) -> bool:
        """
        Validate password against policy requirements.

        Args:
            password: Password to validate

        Returns:
            True if password meets policy, False otherwise
        """
        if len(password) < self._config.password_min_length:
            return False

        if self._config.password_require_uppercase and not any(c.isupper() for c in password):
            return False

        if self._config.password_require_lowercase and not any(c.islower() for c in password):
            return False

        if self._config.password_require_digits and not any(c.isdigit() for c in password):
            return False

        if self._config.password_require_special and not any(
            c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password
        ):
            return False

        return True
