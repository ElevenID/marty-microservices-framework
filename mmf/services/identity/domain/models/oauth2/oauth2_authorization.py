"""
OAuth2 Authorization domain models.

This module contains domain models for OAuth2 authorization flow
including authorization requests, responses, and codes.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import uuid4

from mmf.core.domain.entity import ValueObject


class OAuth2Flow(Enum):
    """OAuth2 authorization flows."""

    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    IMPLICIT = "implicit"
    RESOURCE_OWNER_PASSWORD = "password"  # pragma: allowlist secret
    DEVICE_CODE = "device_code"
    REFRESH_TOKEN = "refresh_token"


class OAuth2ResponseType(Enum):
    """OAuth2 response types for authorization requests."""

    CODE = "code"  # Authorization code flow
    TOKEN = "token"  # Implicit flow
    ID_TOKEN = "id_token"  # OIDC implicit flow
    CODE_ID_TOKEN = "code id_token"  # OIDC hybrid flow
    CODE_TOKEN = "code token"  # OAuth2 hybrid flow
    CODE_TOKEN_ID_TOKEN = "code token id_token"  # OIDC hybrid flow


class OAuth2Scope(Enum):
    """Standard OAuth2 and OIDC scopes."""

    # OAuth2 standard scopes
    READ = "read"
    WRITE = "write"

    # OIDC standard scopes
    OPENID = "openid"
    PROFILE = "profile"
    EMAIL = "email"
    ADDRESS = "address"
    PHONE = "phone"
    OFFLINE_ACCESS = "offline_access"

    # Custom application scopes
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    ADMIN = "admin"


@dataclass(frozen=True)
class OAuth2AuthorizationRequest(ValueObject):
    """
    OAuth2 authorization request domain model.

    Represents an incoming authorization request from a client application.
    """

    client_id: str
    redirect_uri: str
    response_type: OAuth2ResponseType
    scopes: set[OAuth2Scope] = field(default_factory=set)
    state: str | None = None
    code_challenge: str | None = None  # PKCE
    code_challenge_method: str | None = None  # PKCE
    nonce: str | None = None  # OIDC
    request_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the authorization request."""
        if not self.client_id or not self.client_id.strip():
            raise ValueError("Client ID cannot be empty")

        if not self.redirect_uri or not self.redirect_uri.strip():
            raise ValueError("Redirect URI cannot be empty")

        # Validate redirect URI format
        parsed = urlparse(self.redirect_uri)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid redirect URI format")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        # Validate PKCE parameters
        if self.code_challenge and not self.code_challenge_method:
            raise ValueError("code_challenge_method required when code_challenge is provided")

        if self.code_challenge_method and self.code_challenge_method not in ("S256", "plain"):
            raise ValueError("Unsupported code_challenge_method")

    @classmethod
    def from_query_params(cls, params: dict[str, str]) -> OAuth2AuthorizationRequest:
        """Create authorization request from query parameters."""
        # Parse response type
        response_type = OAuth2ResponseType(params.get("response_type", "code"))

        # Parse scopes
        scope_str = params.get("scope", "")
        scopes = set()
        if scope_str:
            for scope in scope_str.split():
                try:
                    scopes.add(OAuth2Scope(scope))
                except ValueError:
                    # Skip unknown scopes
                    pass

        return cls(
            client_id=params["client_id"],
            redirect_uri=params["redirect_uri"],
            response_type=response_type,
            scopes=scopes,
            state=params.get("state"),
            code_challenge=params.get("code_challenge"),
            code_challenge_method=params.get("code_challenge_method"),
            nonce=params.get("nonce"),
            metadata={"original_params": params},
        )

    def has_scope(self, scope: OAuth2Scope) -> bool:
        """Check if request includes a specific scope."""
        return scope in self.scopes

    def is_pkce_request(self) -> bool:
        """Check if this is a PKCE request."""
        return self.code_challenge is not None

    def is_oidc_request(self) -> bool:
        """Check if this is an OIDC request."""
        return OAuth2Scope.OPENID in self.scopes

    def get_scope_string(self) -> str:
        """Get space-separated scope string."""
        return " ".join(scope.value for scope in self.scopes)


@dataclass(frozen=True)
class OAuth2Authorization(ValueObject):
    """
    OAuth2 authorization domain model.

    Represents a granted authorization that can be exchanged for tokens.
    """

    authorization_id: str
    client_id: str
    user_id: str
    scopes: set[OAuth2Scope]
    redirect_uri: str
    code: str
    state: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str | None = None
    nonce: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    used_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the authorization."""
        if not self.authorization_id or not self.authorization_id.strip():
            raise ValueError("Authorization ID cannot be empty")

        if not self.client_id or not self.client_id.strip():
            raise ValueError("Client ID cannot be empty")

        if not self.user_id or not self.user_id.strip():
            raise ValueError("User ID cannot be empty")

        if not self.code or not self.code.strip():
            raise ValueError("Authorization code cannot be empty")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=timezone.utc))

        if self.used_at and self.used_at.tzinfo is None:
            object.__setattr__(self, "used_at", self.used_at.replace(tzinfo=timezone.utc))

    @classmethod
    def create_from_request(
        cls, request: OAuth2AuthorizationRequest, user_id: str, expires_in_minutes: int = 10
    ) -> OAuth2Authorization:
        """Create authorization from an authorization request."""
        authorization_id = str(uuid4())
        code = generate_authorization_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

        return cls(
            authorization_id=authorization_id,
            client_id=request.client_id,
            user_id=user_id,
            scopes=request.scopes,
            redirect_uri=request.redirect_uri,
            code=code,
            state=request.state,
            code_challenge=request.code_challenge,
            code_challenge_method=request.code_challenge_method,
            nonce=request.nonce,
            expires_at=expires_at,
            metadata={"request_id": request.request_id},
        )

    def is_expired(self) -> bool:
        """Check if the authorization has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    def is_used(self) -> bool:
        """Check if the authorization has been used."""
        return self.used_at is not None

    def can_be_used(self) -> bool:
        """Check if the authorization can be used."""
        return not self.is_expired() and not self.is_used()

    def mark_used(self) -> OAuth2Authorization:
        """Create a new authorization marked as used."""
        return self._replace(used_at=datetime.now(timezone.utc))

    def verify_pkce(self, code_verifier: str) -> bool:
        """Verify PKCE code verifier against challenge."""
        if not self.code_challenge or not self.code_challenge_method:
            # No PKCE challenge, so verification passes
            return True

        if self.code_challenge_method == "plain":
            return self.code_challenge == code_verifier
        elif self.code_challenge_method == "S256":
            # Generate challenge from verifier
            digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
            challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
            return self.code_challenge == challenge

        return False

    def has_scope(self, scope: OAuth2Scope) -> bool:
        """Check if authorization includes a specific scope."""
        return scope in self.scopes

    def get_scope_string(self) -> str:
        """Get space-separated scope string."""
        return " ".join(scope.value for scope in self.scopes)

    def _replace(self, **changes) -> OAuth2Authorization:
        """Create a new authorization with specified changes."""
        kwargs = {
            "authorization_id": self.authorization_id,
            "client_id": self.client_id,
            "user_id": self.user_id,
            "scopes": self.scopes,
            "redirect_uri": self.redirect_uri,
            "code": self.code,
            "state": self.state,
            "code_challenge": self.code_challenge,
            "code_challenge_method": self.code_challenge_method,
            "nonce": self.nonce,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "used_at": self.used_at,
            "metadata": self.metadata,
        }
        kwargs.update(changes)
        return OAuth2Authorization(**kwargs)


@dataclass(frozen=True)
class OAuth2AuthorizationResponse(ValueObject):
    """
    OAuth2 authorization response domain model.

    Represents the response sent back to the client after authorization.
    """

    redirect_uri: str
    code: str | None = None
    access_token: str | None = None  # For implicit flow
    token_type: str | None = None  # For implicit flow
    expires_in: int | None = None  # For implicit flow
    state: str | None = None
    error: str | None = None
    error_description: str | None = None
    error_uri: str | None = None

    def __post_init__(self):
        """Validate the authorization response."""
        if not self.redirect_uri or not self.redirect_uri.strip():
            raise ValueError("Redirect URI cannot be empty")

    @classmethod
    def success_response(
        cls, redirect_uri: str, code: str, state: str | None = None
    ) -> OAuth2AuthorizationResponse:
        """Create a successful authorization response."""
        return cls(redirect_uri=redirect_uri, code=code, state=state)

    @classmethod
    def error_response(
        cls,
        redirect_uri: str,
        error: str,
        error_description: str | None = None,
        error_uri: str | None = None,
        state: str | None = None,
    ) -> OAuth2AuthorizationResponse:
        """Create an error authorization response."""
        return cls(
            redirect_uri=redirect_uri,
            error=error,
            error_description=error_description,
            error_uri=error_uri,
            state=state,
        )

    def is_success(self) -> bool:
        """Check if the response indicates success."""
        return self.error is None

    def build_redirect_url(self) -> str:
        """Build the complete redirect URL with parameters."""
        params = {}

        if self.code:
            params["code"] = self.code
        if self.access_token:
            params["access_token"] = self.access_token
        if self.token_type:
            params["token_type"] = self.token_type
        if self.expires_in is not None:
            params["expires_in"] = str(self.expires_in)
        if self.state:
            params["state"] = self.state
        if self.error:
            params["error"] = self.error
        if self.error_description:
            params["error_description"] = self.error_description
        if self.error_uri:
            params["error_uri"] = self.error_uri

        if params:
            separator = "&" if "?" in self.redirect_uri else "?"
            return f"{self.redirect_uri}{separator}{urlencode(params)}"
        else:
            return self.redirect_uri


def generate_authorization_code(length: int = 32) -> str:
    """Generate a secure authorization code."""
    return secrets.token_urlsafe(length)


def generate_state(length: int = 16) -> str:
    """Generate a secure state parameter."""
    return secrets.token_urlsafe(length)


def generate_code_verifier(length: int = 128) -> str:
    """Generate a PKCE code verifier."""
    if length < 43 or length > 128:
        raise ValueError("PKCE code verifier length must be between 43 and 128")
    return secrets.token_urlsafe(length)


def generate_code_challenge(code_verifier: str) -> str:
    """Generate a PKCE code challenge from verifier using S256."""

    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
