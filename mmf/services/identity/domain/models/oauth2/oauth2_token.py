"""
OAuth2 Token domain models.

This module contains domain models for OAuth2 tokens including
access tokens, refresh tokens, and token responses.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from mmf.core.domain.entity import ValueObject


class OAuth2TokenType(Enum):
    """OAuth2 token types."""

    BEARER = "Bearer"
    MAC = "MAC"


class OAuth2GrantType(Enum):
    """OAuth2 grant types."""

    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"
    PASSWORD = "password"  # pragma: allowlist secret
    IMPLICIT = "implicit"
    DEVICE_CODE = "device_code"
    JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"


@dataclass(frozen=True)
class OAuth2AccessToken(ValueObject):
    """
    OAuth2 access token domain model.

    Represents an access token that can be used to access protected resources.
    """

    token_id: str
    access_token: str
    token_type: OAuth2TokenType = OAuth2TokenType.BEARER
    client_id: str = ""
    user_id: str | None = None
    scopes: set[str] = field(default_factory=set)
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1)
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the access token."""
        if not self.token_id or not self.token_id.strip():
            raise ValueError("Token ID cannot be empty")

        if not self.access_token or not self.access_token.strip():
            raise ValueError("Access token cannot be empty")

        if not self.client_id or not self.client_id.strip():
            raise ValueError("Client ID cannot be empty")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=timezone.utc))

        if self.revoked_at and self.revoked_at.tzinfo is None:
            object.__setattr__(self, "revoked_at", self.revoked_at.replace(tzinfo=timezone.utc))

    @classmethod
    def create(
        cls,
        client_id: str,
        scopes: set[str] | None = None,
        user_id: str | None = None,
        expires_in_seconds: int = 3600,
        **kwargs,
    ) -> OAuth2AccessToken:
        """Create a new access token."""
        token_id = str(uuid4())
        access_token = generate_access_token()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

        return cls(
            token_id=token_id,
            access_token=access_token,
            client_id=client_id,
            user_id=user_id,
            scopes=scopes or set(),
            expires_at=expires_at,
            **kwargs,
        )

    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    def is_revoked(self) -> bool:
        """Check if the token has been revoked."""
        return self.revoked_at is not None

    def is_active(self) -> bool:
        """Check if the token is active (not expired and not revoked)."""
        return not self.is_expired() and not self.is_revoked()

    def has_scope(self, scope: str) -> bool:
        """Check if token has a specific scope."""
        return scope in self.scopes

    def has_any_scope(self, scopes: set[str]) -> bool:
        """Check if token has any of the specified scopes."""
        return bool(self.scopes & scopes)

    def has_all_scopes(self, scopes: set[str]) -> bool:
        """Check if token has all of the specified scopes."""
        return scopes.issubset(self.scopes)

    def get_scope_string(self) -> str:
        """Get space-separated scope string."""
        return " ".join(sorted(self.scopes))

    def time_to_expiry(self) -> timedelta:
        """Get time remaining until expiry."""
        return self.expires_at - datetime.now(timezone.utc)

    def expires_in_seconds(self) -> int:
        """Get seconds until expiry."""
        delta = self.time_to_expiry()
        return max(0, int(delta.total_seconds()))

    def revoke(self) -> OAuth2AccessToken:
        """Create a new token marked as revoked."""
        return self._replace(revoked_at=datetime.now(timezone.utc))

    def _replace(self, **changes) -> OAuth2AccessToken:
        """Create a new token with specified changes."""
        kwargs = {
            "token_id": self.token_id,
            "access_token": self.access_token,
            "token_type": self.token_type,
            "client_id": self.client_id,
            "user_id": self.user_id,
            "scopes": self.scopes,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
            "metadata": self.metadata,
        }
        kwargs.update(changes)
        return OAuth2AccessToken(**kwargs)


@dataclass(frozen=True)
class OAuth2RefreshToken(ValueObject):
    """
    OAuth2 refresh token domain model.

    Represents a refresh token that can be used to obtain new access tokens.
    """

    token_id: str
    refresh_token: str
    access_token_id: str
    client_id: str
    user_id: str | None = None
    scopes: set[str] = field(default_factory=set)
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=30)
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    used_at: datetime | None = None
    revoked_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the refresh token."""
        if not self.token_id or not self.token_id.strip():
            raise ValueError("Token ID cannot be empty")

        if not self.refresh_token or not self.refresh_token.strip():
            raise ValueError("Refresh token cannot be empty")

        if not self.access_token_id or not self.access_token_id.strip():
            raise ValueError("Access token ID cannot be empty")

        if not self.client_id or not self.client_id.strip():
            raise ValueError("Client ID cannot be empty")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=timezone.utc))

        if self.used_at and self.used_at.tzinfo is None:
            object.__setattr__(self, "used_at", self.used_at.replace(tzinfo=timezone.utc))

        if self.revoked_at and self.revoked_at.tzinfo is None:
            object.__setattr__(self, "revoked_at", self.revoked_at.replace(tzinfo=timezone.utc))

    @classmethod
    def create(
        cls,
        access_token_id: str,
        client_id: str,
        scopes: set[str] | None = None,
        user_id: str | None = None,
        expires_in_seconds: int = 2592000,  # 30 days
        **kwargs,
    ) -> OAuth2RefreshToken:
        """Create a new refresh token."""
        token_id = str(uuid4())
        refresh_token = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

        return cls(
            token_id=token_id,
            refresh_token=refresh_token,
            access_token_id=access_token_id,
            client_id=client_id,
            user_id=user_id,
            scopes=scopes or set(),
            expires_at=expires_at,
            **kwargs,
        )

    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    def is_used(self) -> bool:
        """Check if the token has been used."""
        return self.used_at is not None

    def is_revoked(self) -> bool:
        """Check if the token has been revoked."""
        return self.revoked_at is not None

    def is_active(self) -> bool:
        """Check if the token is active (not expired, not used, and not revoked)."""
        return not self.is_expired() and not self.is_used() and not self.is_revoked()

    def can_be_used(self) -> bool:
        """Check if the token can be used."""
        return self.is_active()

    def mark_used(self) -> OAuth2RefreshToken:
        """Create a new token marked as used."""
        return self._replace(used_at=datetime.now(timezone.utc))

    def revoke(self) -> OAuth2RefreshToken:
        """Create a new token marked as revoked."""
        return self._replace(revoked_at=datetime.now(timezone.utc))

    def get_scope_string(self) -> str:
        """Get space-separated scope string."""
        return " ".join(sorted(self.scopes))

    def _replace(self, **changes) -> OAuth2RefreshToken:
        """Create a new token with specified changes."""
        kwargs = {
            "token_id": self.token_id,
            "refresh_token": self.refresh_token,
            "access_token_id": self.access_token_id,
            "client_id": self.client_id,
            "user_id": self.user_id,
            "scopes": self.scopes,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "used_at": self.used_at,
            "revoked_at": self.revoked_at,
            "metadata": self.metadata,
        }
        kwargs.update(changes)
        return OAuth2RefreshToken(**kwargs)


@dataclass(frozen=True)
class OAuth2TokenRequest(ValueObject):
    """
    OAuth2 token request domain model.

    Represents a request to the token endpoint.
    """

    grant_type: OAuth2GrantType
    client_id: str
    client_secret: str | None = None

    # Authorization code flow
    code: str | None = None
    redirect_uri: str | None = None
    code_verifier: str | None = None  # PKCE

    # Refresh token flow
    refresh_token: str | None = None

    # Client credentials flow
    scope: str | None = None

    # Resource owner password flow (discouraged)
    username: str | None = None
    password: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the token request."""
        if not self.client_id or not self.client_id.strip():
            raise ValueError("Client ID cannot be empty")

        # Validate required fields per grant type
        if self.grant_type == OAuth2GrantType.AUTHORIZATION_CODE:
            if not self.code:
                raise ValueError("Authorization code required for authorization_code grant")
            if not self.redirect_uri:
                raise ValueError("Redirect URI required for authorization_code grant")
        elif self.grant_type == OAuth2GrantType.REFRESH_TOKEN:
            if not self.refresh_token:
                raise ValueError("Refresh token required for refresh_token grant")
        elif self.grant_type == OAuth2GrantType.PASSWORD:
            if not self.username or not self.password:
                raise ValueError("Username and password required for password grant")

    @classmethod
    def authorization_code_request(
        cls,
        client_id: str,
        code: str,
        redirect_uri: str,
        client_secret: str | None = None,
        code_verifier: str | None = None,
        **kwargs,
    ) -> OAuth2TokenRequest:
        """Create authorization code token request."""
        return cls(
            grant_type=OAuth2GrantType.AUTHORIZATION_CODE,
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
            **kwargs,
        )

    @classmethod
    def refresh_token_request(
        cls,
        client_id: str,
        refresh_token: str,
        client_secret: str | None = None,
        scope: str | None = None,
        **kwargs,
    ) -> OAuth2TokenRequest:
        """Create refresh token request."""
        return cls(
            grant_type=OAuth2GrantType.REFRESH_TOKEN,
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            scope=scope,
            **kwargs,
        )

    @classmethod
    def client_credentials_request(
        cls, client_id: str, client_secret: str, scope: str | None = None, **kwargs
    ) -> OAuth2TokenRequest:
        """Create client credentials token request."""
        return cls(
            grant_type=OAuth2GrantType.CLIENT_CREDENTIALS,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            **kwargs,
        )

    def get_requested_scopes(self) -> set[str]:
        """Get the requested scopes as a set."""
        if not self.scope:
            return set()
        return set(self.scope.split())


@dataclass(frozen=True)
class OAuth2TokenResponse(ValueObject):
    """
    OAuth2 token response domain model.

    Represents the response from the token endpoint.
    """

    access_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    scope: str | None = None

    # Error response
    error: str | None = None
    error_description: str | None = None
    error_uri: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success_response(
        cls,
        access_token: str,
        token_type: str = "Bearer",
        expires_in: int | None = None,
        refresh_token: str | None = None,
        scope: str | None = None,
        **kwargs,
    ) -> OAuth2TokenResponse:
        """Create a successful token response."""
        return cls(
            access_token=access_token,
            token_type=token_type,
            expires_in=expires_in,
            refresh_token=refresh_token,
            scope=scope,
            **kwargs,
        )

    @classmethod
    def error_response(
        cls,
        error: str,
        error_description: str | None = None,
        error_uri: str | None = None,
        **kwargs,
    ) -> OAuth2TokenResponse:
        """Create an error token response."""
        return cls(error=error, error_description=error_description, error_uri=error_uri, **kwargs)

    def is_success(self) -> bool:
        """Check if the response indicates success."""
        return self.error is None and self.access_token is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {}

        if self.access_token:
            result["access_token"] = self.access_token
        if self.token_type:
            result["token_type"] = self.token_type
        if self.expires_in is not None:
            result["expires_in"] = self.expires_in
        if self.refresh_token:
            result["refresh_token"] = self.refresh_token
        if self.scope:
            result["scope"] = self.scope

        if self.error:
            result["error"] = self.error
        if self.error_description:
            result["error_description"] = self.error_description
        if self.error_uri:
            result["error_uri"] = self.error_uri

        return result


@dataclass(frozen=True)
class OAuth2TokenIntrospection(ValueObject):
    """
    OAuth2 token introspection response as defined in RFC 7662.

    Represents the result of introspecting an access token.
    """

    active: bool
    client_id: str | None = None
    username: str | None = None
    scope: str | None = None
    token_type: str | None = None
    exp: int | None = None  # Expiration time (Unix timestamp)
    iat: int | None = None  # Issued at time (Unix timestamp)
    nbf: int | None = None  # Not before time (Unix timestamp)
    sub: str | None = None  # Subject identifier
    aud: str | None = None  # Audience
    iss: str | None = None  # Issuer
    jti: str | None = None  # JWT ID

    @classmethod
    def from_access_token(cls, token: OAuth2AccessToken) -> OAuth2TokenIntrospection:
        """Create introspection response from access token."""
        active = token.is_active()

        return cls(
            active=active,
            client_id=token.client_id if active else None,
            username=token.user_id if active else None,
            scope=token.get_scope_string() if active and token.scopes else None,
            token_type=token.token_type.value if active else None,
            exp=int(token.expires_at.timestamp()) if active else None,
            iat=int(token.created_at.timestamp()) if active else None,
            sub=token.user_id if active else None,
            jti=token.token_id if active else None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"active": self.active}

        if self.active:
            if self.client_id:
                result["client_id"] = self.client_id
            if self.username:
                result["username"] = self.username
            if self.scope:
                result["scope"] = self.scope
            if self.token_type:
                result["token_type"] = self.token_type
            if self.exp:
                result["exp"] = self.exp
            if self.iat:
                result["iat"] = self.iat
            if self.nbf:
                result["nbf"] = self.nbf
            if self.sub:
                result["sub"] = self.sub
            if self.aud:
                result["aud"] = self.aud
            if self.iss:
                result["iss"] = self.iss
            if self.jti:
                result["jti"] = self.jti

        return result


def generate_access_token(length: int = 32) -> str:
    """Generate a secure access token."""
    return secrets.token_urlsafe(length)


def generate_refresh_token(length: int = 32) -> str:
    """Generate a secure refresh token."""
    return secrets.token_urlsafe(length)
