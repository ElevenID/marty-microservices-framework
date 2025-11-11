"""
JWT Token Provider Infrastructure Adapter.

This module implements the TokenProvider port using PyJWT library
for JWT token creation and validation.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from mmf_new.services.identity.application.ports_out import (
    TokenCreationError,
    TokenProvider,
    TokenValidationError,
)
from mmf_new.services.identity.domain.models import AuthenticatedUser


class JWTConfig:
    """Configuration for JWT token operations."""

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        issuer: str | None = None,
        audience: str | None = None,
    ) -> None:
        """
        Initialize JWT configuration.

        Args:
            secret_key: Secret key for signing tokens
            algorithm: JWT signing algorithm (default: HS256)
            access_token_expire_minutes: Token expiration time in minutes
            issuer: Token issuer (optional)
            audience: Token audience (optional)
        """
        if not secret_key:
            raise ValueError("Secret key is required")

        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.issuer = issuer
        self.audience = audience


class JWTTokenProvider(TokenProvider):
    """
    JWT implementation of the TokenProvider port.

    This adapter implements JWT token creation and validation
    using the PyJWT library while conforming to the hexagonal
    architecture port interface.
    """

    def __init__(self, config: JWTConfig) -> None:
        """
        Initialize JWT token provider.

        Args:
            config: JWT configuration settings
        """
        self._config = config

    async def create_token(
        self,
        user: AuthenticatedUser,
        expires_at: datetime | None = None,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a JWT token for the authenticated user.

        Args:
            user: Authenticated user to create token for
            expires_at: Custom expiration time (if None, uses default)
            additional_claims: Additional claims to include in token

        Returns:
            JWT token string

        Raises:
            TokenCreationError: If token creation fails
        """
        try:
            now = datetime.now(timezone.utc)

            # Calculate expiration time
            if expires_at is None:
                expires_at = now + timedelta(minutes=self._config.access_token_expire_minutes)

            # Ensure timezone awareness
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            # Build JWT payload
            payload = {
                "sub": user.user_id,
                "username": user.username,
                "iat": now,
                "exp": expires_at,
            }

            # Add optional fields
            if user.email:
                payload["email"] = user.email

            if user.roles:
                payload["roles"] = list(user.roles)

            if user.permissions:
                payload["permissions"] = list(user.permissions)

            # Add issuer and audience if configured
            if self._config.issuer:
                payload["iss"] = self._config.issuer

            if self._config.audience:
                payload["aud"] = self._config.audience

            # Add user metadata
            if user.metadata:
                payload["user_metadata"] = user.metadata

            # Add additional claims
            if additional_claims:
                payload.update(additional_claims)

            # Create and return token
            return jwt.encode(payload, self._config.secret_key, algorithm=self._config.algorithm)

        except Exception as error:
            raise TokenCreationError(f"Failed to create JWT token: {error}") from error

    async def validate_token(self, token: str) -> AuthenticatedUser:
        """
        Validate a JWT token and extract user information.

        Args:
            token: JWT token string to validate

        Returns:
            AuthenticatedUser object from token claims

        Raises:
            TokenValidationError: If token is invalid, expired, or malformed
        """
        try:
            # Prepare decode options
            decode_options = {
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": self._config.audience is not None,
                "verify_iss": self._config.issuer is not None,
            }

            # Decode and validate token
            payload = jwt.decode(
                token,
                self._config.secret_key,
                algorithms=[self._config.algorithm],
                audience=self._config.audience,
                issuer=self._config.issuer,
                options=decode_options,
            )

            # Extract required fields
            user_id = payload.get("sub")
            if not user_id:
                raise TokenValidationError("Token missing 'sub' claim")

            username = payload.get("username")
            if not username:
                raise TokenValidationError("Token missing 'username' claim")

            # Extract optional fields
            email = payload.get("email")
            roles = set(payload.get("roles", []))
            permissions = set(payload.get("permissions", []))
            user_metadata = payload.get("user_metadata", {})

            # Extract token metadata
            issued_at = payload.get("iat")
            expires_at = payload.get("exp")

            # Convert timestamps to datetime objects
            issued_at_dt = None
            if issued_at:
                issued_at_dt = datetime.fromtimestamp(issued_at, tz=timezone.utc)

            expires_at_dt = None
            if expires_at:
                expires_at_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)

            # Create AuthenticatedUser
            return AuthenticatedUser(
                user_id=user_id,
                username=username,
                email=email,
                roles=roles,
                permissions=permissions,
                session_id=None,  # JWT tokens don't have session IDs
                auth_method="jwt",
                created_at=issued_at_dt,
                expires_at=expires_at_dt,
                metadata={
                    **user_metadata,
                    "token_issued_at": issued_at,
                    "token_expires_at": expires_at,
                    "token_issuer": payload.get("iss"),
                    "token_audience": payload.get("aud"),
                },
            )

        except jwt.ExpiredSignatureError as error:
            raise TokenValidationError("JWT token has expired") from error

        except jwt.InvalidTokenError as error:
            raise TokenValidationError(f"Invalid JWT token: {error}") from error

        except Exception as error:
            raise TokenValidationError(f"Token validation failed: {error}") from error

    async def refresh_token(self, token: str, new_expires_at: datetime | None = None) -> str:
        """
        Refresh an existing JWT token with new expiration.

        Args:
            token: Current valid JWT token
            new_expires_at: New expiration time (if None, uses default)

        Returns:
            New JWT token string

        Raises:
            TokenValidationError: If current token is invalid
            TokenCreationError: If new token creation fails
        """
        try:
            # First validate the current token
            user = await self.validate_token(token)

            # Create new token with same user data
            return await self.create_token(user, expires_at=new_expires_at)

        except TokenValidationError:
            # Re-raise validation errors as-is
            raise

        except Exception as error:
            raise TokenCreationError(f"Failed to refresh JWT token: {error}") from error
