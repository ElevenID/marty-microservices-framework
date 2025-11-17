"""
OAuth2 Client domain models.

This module contains domain models for OAuth2 client applications
including client registration, configuration, and metadata.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from mmf_new.core.domain.entity import ValueObject


class OAuth2ClientType(Enum):
    """OAuth2 client types as defined in RFC 6749."""

    PUBLIC = "public"  # Cannot maintain confidentiality of credentials
    CONFIDENTIAL = "confidential"  # Can maintain confidentiality of credentials


class OAuth2ApplicationType(Enum):
    """OAuth2 application types."""

    WEB = "web"  # Web application
    NATIVE = "native"  # Native application (mobile app, desktop app)
    SPA = "spa"  # Single Page Application
    SERVICE = "service"  # Machine-to-machine / service


class OAuth2TokenEndpointAuthMethod(Enum):
    """OAuth2 client authentication methods at token endpoint."""

    CLIENT_SECRET_POST = "client_secret_post"  # pragma: allowlist secret
    CLIENT_SECRET_BASIC = "client_secret_basic"  # pragma: allowlist secret
    CLIENT_SECRET_JWT = "client_secret_jwt"  # pragma: allowlist secret
    PRIVATE_KEY_JWT = "private_key_jwt"  # pragma: allowlist secret
    NONE = "none"  # For public clients


@dataclass(frozen=True)
class OAuth2Client(ValueObject):
    """
    OAuth2 client domain model.

    Represents a registered OAuth2 client application that can
    request authorization and access tokens.
    """

    client_id: str
    client_secret: str | None = None
    client_name: str = ""
    client_type: OAuth2ClientType = OAuth2ClientType.PUBLIC
    application_type: OAuth2ApplicationType = OAuth2ApplicationType.WEB
    redirect_uris: set[str] = field(default_factory=set)
    allowed_scopes: set[str] = field(default_factory=set)
    allowed_grant_types: set[str] = field(default_factory=lambda: {"authorization_code"})
    allowed_response_types: set[str] = field(default_factory=lambda: {"code"})
    token_endpoint_auth_method: OAuth2TokenEndpointAuthMethod = (
        OAuth2TokenEndpointAuthMethod.CLIENT_SECRET_BASIC
    )

    # Client metadata
    client_uri: str | None = None
    logo_uri: str | None = None
    tos_uri: str | None = None
    policy_uri: str | None = None

    # Security settings
    require_pkce: bool = False
    allow_refresh_tokens: bool = True
    access_token_lifetime_seconds: int = 3600  # 1 hour
    refresh_token_lifetime_seconds: int = 2592000  # 30 days
    authorization_code_lifetime_seconds: int = 600  # 10 minutes

    # Registration metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the OAuth2 client."""
        if not self.client_id or not self.client_id.strip():
            raise ValueError("Client ID cannot be empty")

        # Confidential clients must have a secret
        if self.client_type == OAuth2ClientType.CONFIDENTIAL and not self.client_secret:
            raise ValueError("Confidential clients must have a client secret")

        # Public clients should not have a secret
        if self.client_type == OAuth2ClientType.PUBLIC and self.client_secret:
            raise ValueError("Public clients should not have a client secret")

        # Validate redirect URIs
        if not self.redirect_uris:
            raise ValueError("At least one redirect URI must be specified")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.updated_at.tzinfo is None:
            object.__setattr__(self, "updated_at", self.updated_at.replace(tzinfo=timezone.utc))

        # Validate PKCE requirement for public clients
        if self.application_type in (OAuth2ApplicationType.SPA, OAuth2ApplicationType.NATIVE):
            object.__setattr__(self, "require_pkce", True)

    @classmethod
    def create_web_client(
        cls,
        client_name: str,
        redirect_uris: set[str],
        allowed_scopes: set[str] | None = None,
        **kwargs,
    ) -> OAuth2Client:
        """Create a confidential web client."""
        client_id = generate_client_id()
        client_secret = generate_client_secret()

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            client_name=client_name,
            client_type=OAuth2ClientType.CONFIDENTIAL,
            application_type=OAuth2ApplicationType.WEB,
            redirect_uris=redirect_uris,
            allowed_scopes=allowed_scopes or {"openid", "profile", "email"},
            **kwargs,
        )

    @classmethod
    def create_spa_client(
        cls,
        client_name: str,
        redirect_uris: set[str],
        allowed_scopes: set[str] | None = None,
        **kwargs,
    ) -> OAuth2Client:
        """Create a public SPA client."""
        client_id = generate_client_id()

        return cls(
            client_id=client_id,
            client_secret=None,
            client_name=client_name,
            client_type=OAuth2ClientType.PUBLIC,
            application_type=OAuth2ApplicationType.SPA,
            redirect_uris=redirect_uris,
            allowed_scopes=allowed_scopes or {"openid", "profile", "email"},
            require_pkce=True,
            token_endpoint_auth_method=OAuth2TokenEndpointAuthMethod.NONE,
            **kwargs,
        )

    @classmethod
    def create_native_client(
        cls,
        client_name: str,
        redirect_uris: set[str],
        allowed_scopes: set[str] | None = None,
        **kwargs,
    ) -> OAuth2Client:
        """Create a public native client."""
        client_id = generate_client_id()

        return cls(
            client_id=client_id,
            client_secret=None,
            client_name=client_name,
            client_type=OAuth2ClientType.PUBLIC,
            application_type=OAuth2ApplicationType.NATIVE,
            redirect_uris=redirect_uris,
            allowed_scopes=allowed_scopes or {"openid", "profile", "email"},
            require_pkce=True,
            token_endpoint_auth_method=OAuth2TokenEndpointAuthMethod.NONE,
            **kwargs,
        )

    @classmethod
    def create_service_client(
        cls, client_name: str, allowed_scopes: set[str] | None = None, **kwargs
    ) -> OAuth2Client:
        """Create a confidential service client for client credentials flow."""
        client_id = generate_client_id()
        client_secret = generate_client_secret()

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            client_name=client_name,
            client_type=OAuth2ClientType.CONFIDENTIAL,
            application_type=OAuth2ApplicationType.SERVICE,
            redirect_uris=set(),  # Not used for client credentials
            allowed_scopes=allowed_scopes or {"read", "write"},
            allowed_grant_types={"client_credentials"},
            allowed_response_types=set(),  # Not used for client credentials
            allow_refresh_tokens=False,  # Not needed for client credentials
            **kwargs,
        )

    def is_redirect_uri_allowed(self, redirect_uri: str) -> bool:
        """Check if a redirect URI is allowed for this client."""
        return redirect_uri in self.redirect_uris

    def is_scope_allowed(self, scope: str) -> bool:
        """Check if a scope is allowed for this client."""
        return scope in self.allowed_scopes

    def are_scopes_allowed(self, scopes: set[str]) -> bool:
        """Check if all scopes are allowed for this client."""
        return scopes.issubset(self.allowed_scopes)

    def is_grant_type_allowed(self, grant_type: str) -> bool:
        """Check if a grant type is allowed for this client."""
        return grant_type in self.allowed_grant_types

    def is_response_type_allowed(self, response_type: str) -> bool:
        """Check if a response type is allowed for this client."""
        return response_type in self.allowed_response_types

    def verify_client_secret(self, provided_secret: str) -> bool:
        """Verify the client secret."""
        if self.client_type == OAuth2ClientType.PUBLIC:
            # Public clients don't have secrets
            return True

        if not self.client_secret:
            return False

        return secrets.compare_digest(self.client_secret, provided_secret)

    def can_use_pkce(self) -> bool:
        """Check if client can use PKCE."""
        # All clients can use PKCE, some require it
        return True

    def requires_pkce(self) -> bool:
        """Check if client requires PKCE."""
        return self.require_pkce

    def can_use_refresh_tokens(self) -> bool:
        """Check if client can use refresh tokens."""
        return self.allow_refresh_tokens

    def regenerate_secret(self) -> OAuth2Client:
        """Create a new client with regenerated secret."""
        if self.client_type == OAuth2ClientType.PUBLIC:
            raise ValueError("Cannot regenerate secret for public client")

        return self._replace(
            client_secret=generate_client_secret(), updated_at=datetime.now(timezone.utc)
        )

    def update_redirect_uris(self, redirect_uris: set[str]) -> OAuth2Client:
        """Create a new client with updated redirect URIs."""
        if not redirect_uris:
            raise ValueError("At least one redirect URI must be specified")

        return self._replace(redirect_uris=redirect_uris, updated_at=datetime.now(timezone.utc))

    def update_scopes(self, allowed_scopes: set[str]) -> OAuth2Client:
        """Create a new client with updated allowed scopes."""
        return self._replace(allowed_scopes=allowed_scopes, updated_at=datetime.now(timezone.utc))

    def deactivate(self) -> OAuth2Client:
        """Create a new client marked as inactive."""
        return self._replace(is_active=False, updated_at=datetime.now(timezone.utc))

    def activate(self) -> OAuth2Client:
        """Create a new client marked as active."""
        return self._replace(is_active=True, updated_at=datetime.now(timezone.utc))

    def _replace(self, **changes) -> OAuth2Client:
        """Create a new client with specified changes."""
        kwargs = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "client_name": self.client_name,
            "client_type": self.client_type,
            "application_type": self.application_type,
            "redirect_uris": self.redirect_uris,
            "allowed_scopes": self.allowed_scopes,
            "allowed_grant_types": self.allowed_grant_types,
            "allowed_response_types": self.allowed_response_types,
            "token_endpoint_auth_method": self.token_endpoint_auth_method,
            "client_uri": self.client_uri,
            "logo_uri": self.logo_uri,
            "tos_uri": self.tos_uri,
            "policy_uri": self.policy_uri,
            "require_pkce": self.require_pkce,
            "allow_refresh_tokens": self.allow_refresh_tokens,
            "access_token_lifetime_seconds": self.access_token_lifetime_seconds,
            "refresh_token_lifetime_seconds": self.refresh_token_lifetime_seconds,
            "authorization_code_lifetime_seconds": self.authorization_code_lifetime_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }
        kwargs.update(changes)
        return OAuth2Client(**kwargs)


@dataclass(frozen=True)
class OAuth2ClientRegistration(ValueObject):
    """
    OAuth2 client registration request.

    Represents a request to register a new OAuth2 client.
    """

    client_name: str
    application_type: OAuth2ApplicationType
    redirect_uris: set[str]
    allowed_scopes: set[str] = field(default_factory=set)
    client_uri: str | None = None
    logo_uri: str | None = None
    tos_uri: str | None = None
    policy_uri: str | None = None
    require_pkce: bool | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the client registration."""
        if not self.client_name or not self.client_name.strip():
            raise ValueError("Client name cannot be empty")

        if not self.redirect_uris:
            raise ValueError("At least one redirect URI must be specified")

    def to_client(self) -> OAuth2Client:
        """Convert registration to a client."""
        if self.application_type == OAuth2ApplicationType.WEB:
            return OAuth2Client.create_web_client(
                client_name=self.client_name,
                redirect_uris=self.redirect_uris,
                allowed_scopes=self.allowed_scopes,
                client_uri=self.client_uri,
                logo_uri=self.logo_uri,
                tos_uri=self.tos_uri,
                policy_uri=self.policy_uri,
                require_pkce=self.require_pkce or False,
                metadata=self.metadata,
            )
        elif self.application_type == OAuth2ApplicationType.SPA:
            return OAuth2Client.create_spa_client(
                client_name=self.client_name,
                redirect_uris=self.redirect_uris,
                allowed_scopes=self.allowed_scopes,
                client_uri=self.client_uri,
                logo_uri=self.logo_uri,
                tos_uri=self.tos_uri,
                policy_uri=self.policy_uri,
                metadata=self.metadata,
            )
        elif self.application_type == OAuth2ApplicationType.NATIVE:
            return OAuth2Client.create_native_client(
                client_name=self.client_name,
                redirect_uris=self.redirect_uris,
                allowed_scopes=self.allowed_scopes,
                client_uri=self.client_uri,
                logo_uri=self.logo_uri,
                tos_uri=self.tos_uri,
                policy_uri=self.policy_uri,
                metadata=self.metadata,
            )
        elif self.application_type == OAuth2ApplicationType.SERVICE:
            return OAuth2Client.create_service_client(
                client_name=self.client_name,
                allowed_scopes=self.allowed_scopes,
                client_uri=self.client_uri,
                logo_uri=self.logo_uri,
                tos_uri=self.tos_uri,
                policy_uri=self.policy_uri,
                metadata=self.metadata,
            )
        else:
            raise ValueError(f"Unsupported application type: {self.application_type}")


def generate_client_id(length: int = 32) -> str:
    """Generate a secure client ID."""
    return secrets.token_urlsafe(length)


def generate_client_secret(length: int = 64) -> str:
    """Generate a secure client secret."""
    return secrets.token_urlsafe(length)
