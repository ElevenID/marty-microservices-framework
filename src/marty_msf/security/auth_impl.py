"""
Authentication Module

This module contains concrete implementations of authentication providers.
It depends only on the security.api layer, following the level contract principle.

Key Features:
- Multiple authentication methods (password, token, OAuth2, etc.)
- Pluggable authentication providers
- Session management
- Token validation
"""

import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from .api import (
    AuthenticationError,
    AuthenticationMethod,
    AuthenticationResult,
    ISecretManager,
    User,
)

logger = logging.getLogger(__name__)


class BasicAuthenticator:
    """
    Simple authenticator that verifies username/password credentials.

    This authenticator uses a secret manager for secure credential storage
    and supports basic password authentication.
    """

    def __init__(self, secret_manager: ISecretManager):
        """
        Initialize the basic authenticator.

        Args:
            secret_manager: Secret manager for retrieving stored credentials
        """
        self.secret_manager = secret_manager
        self.auth_method = AuthenticationMethod.PASSWORD

    def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """
        Authenticate user with username/password credentials.

        Args:
            credentials: Dictionary containing 'username' and 'password'

        Returns:
            AuthenticationResult indicating success/failure
        """
        try:
            username = credentials.get("username")
            password = credentials.get("password")

            if not username or not password:
                return AuthenticationResult(
                    success=False,
                    error_message="Username and password are required"
                )

            # Retrieve expected password hash from secret manager
            stored_hash = self.secret_manager.get_secret(f"user.{username}.password_hash")
            if not stored_hash:
                logger.warning(f"Authentication failed - unknown user: {username}")
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid credentials"
                )

            # Verify password hash
            password_hash = self._hash_password(password)
            if password_hash != stored_hash:
                logger.warning(f"Authentication failed - invalid password for user: {username}")
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid credentials"
                )

            # Retrieve user attributes
            user_data = self._get_user_data(username)
            user = User(
                id=user_data.get("id", username),
                username=username,
                email=user_data.get("email"),
                roles=user_data.get("roles", []),
                attributes=user_data.get("attributes", {}),
                metadata={"auth_method": self.auth_method.value}
            )

            logger.info(f"Authentication successful for user: {username}")
            return AuthenticationResult(
                success=True,
                user=user,
                session_data={"auth_method": self.auth_method.value}
            )

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return AuthenticationResult(
                success=False,
                error_message="Authentication failed"
            )

    def validate_token(self, token: str) -> AuthenticationResult:
        """
        Validate an authentication token (not implemented for basic auth).

        Args:
            token: Token to validate

        Returns:
            AuthenticationResult indicating failure (basic auth doesn't use tokens)
        """
        return AuthenticationResult(
            success=False,
            error_message="Token validation not supported by BasicAuthenticator"
        )

    def _hash_password(self, password: str) -> str:
        """
        Hash a password using SHA-256 (in production, use bcrypt or similar).

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()

    def _get_user_data(self, username: str) -> dict[str, Any]:
        """
        Retrieve user data from secret manager.

        Args:
            username: Username to get data for

        Returns:
            Dictionary containing user data
        """
        try:
            user_id = self.secret_manager.get_secret(f"user.{username}.id") or username
            email = self.secret_manager.get_secret(f"user.{username}.email")
            roles_str = self.secret_manager.get_secret(f"user.{username}.roles")
            roles = roles_str.split(",") if roles_str else []

            return {
                "id": user_id,
                "email": email,
                "roles": roles,
                "attributes": {}
            }
        except Exception as e:
            logger.warning(f"Could not retrieve user data for {username}: {e}")
            return {"id": username, "roles": []}


class JwtAuthenticator:
    """
    JWT-based authenticator for token validation.

    This authenticator validates JWT tokens and extracts user information
    from token claims.
    """

    def __init__(self, secret_manager: ISecretManager):
        """
        Initialize the JWT authenticator.

        Args:
            secret_manager: Secret manager for retrieving JWT signing keys
        """
        self.secret_manager = secret_manager
        self.auth_method = AuthenticationMethod.TOKEN

    def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """
        Authenticate using a JWT token.

        Args:
            credentials: Dictionary containing 'token'

        Returns:
            AuthenticationResult indicating success/failure
        """
        token = credentials.get("token")
        if not token:
            return AuthenticationResult(
                success=False,
                error_message="Token is required"
            )

        return self.validate_token(token)

    def validate_token(self, token: str) -> AuthenticationResult:
        """
        Validate a JWT token and extract user information.

        Args:
            token: JWT token to validate

        Returns:
            AuthenticationResult with user information if valid
        """
        try:
            # Get JWT secret from secret manager
            jwt_secret = self.secret_manager.get_secret("jwt.secret")
            if not jwt_secret:
                return AuthenticationResult(
                    success=False,
                    error_message="JWT secret not configured"
                )

            # Decode and validate token
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )

            # Extract user information from token claims
            user = User(
                id=payload.get("sub", "unknown"),
                username=payload.get("username", payload.get("sub", "unknown")),
                email=payload.get("email"),
                roles=payload.get("roles", []),
                attributes=payload.get("attributes", {}),
                metadata={
                    "auth_method": self.auth_method.value,
                    "token_issued_at": payload.get("iat"),
                    "token_expires_at": payload.get("exp")
                }
            )

            logger.info(f"JWT validation successful for user: {user.username}")
            return AuthenticationResult(
                success=True,
                user=user,
                session_data={
                    "auth_method": self.auth_method.value,
                    "token_claims": payload
                }
            )

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return AuthenticationResult(
                success=False,
                error_message="Token has expired"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return AuthenticationResult(
                success=False,
                error_message="Invalid token"
            )
        except Exception as e:
            logger.error(f"JWT validation error: {e}")
            return AuthenticationResult(
                success=False,
                error_message="Token validation failed"
            )


class EnvironmentAuthenticator:
    """
    Development/testing authenticator that uses environment variables.

    This authenticator is useful for development and testing scenarios
    where you need simple, environment-based authentication.
    """

    def __init__(self, secret_manager: ISecretManager | None = None):
        """
        Initialize the environment authenticator.

        Args:
            secret_manager: Optional secret manager (not used by this authenticator)
        """
        self.secret_manager = secret_manager
        self.auth_method = AuthenticationMethod.PASSWORD

    def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """
        Authenticate using environment variables.

        Args:
            credentials: Dictionary containing 'username' and 'password'

        Returns:
            AuthenticationResult indicating success/failure
        """
        try:
            username = credentials.get("username")
            password = credentials.get("password")

            if not username or not password:
                return AuthenticationResult(
                    success=False,
                    error_message="Username and password are required"
                )

            # Check against environment variables
            expected_username = os.getenv("AUTH_USERNAME")
            expected_password = os.getenv("AUTH_PASSWORD")

            if not expected_username or not expected_password:
                return AuthenticationResult(
                    success=False,
                    error_message="Authentication not configured"
                )

            if username != expected_username or password != expected_password:
                return AuthenticationResult(
                    success=False,
                    error_message="Invalid credentials"
                )

            # Create user with default attributes
            user = User(
                id=username,
                username=username,
                email=os.getenv("AUTH_EMAIL"),
                roles=os.getenv("AUTH_ROLES", "").split(",") if os.getenv("AUTH_ROLES") else ["user"],
                metadata={"auth_method": self.auth_method.value}
            )

            return AuthenticationResult(
                success=True,
                user=user,
                session_data={"auth_method": self.auth_method.value}
            )

        except Exception as e:
            logger.error(f"Environment authentication error: {e}")
            return AuthenticationResult(
                success=False,
                error_message="Authentication failed"
            )

    def validate_token(self, token: str) -> AuthenticationResult:
        """
        Validate a token (not implemented for environment auth).

        Args:
            token: Token to validate

        Returns:
            AuthenticationResult indicating failure
        """
        return AuthenticationResult(
            success=False,
            error_message="Token validation not supported by EnvironmentAuthenticator"
        )
