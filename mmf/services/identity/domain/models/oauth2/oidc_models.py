"""
OpenID Connect (OIDC) domain models.

This module contains domain models for OIDC identity tokens,
user info, and OIDC-specific flows extending OAuth2.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from mmf.core.domain.entity import ValueObject


class OIDCClaimType(Enum):
    """Standard OIDC claims."""

    # Essential claims
    SUB = "sub"  # Subject identifier
    ISS = "iss"  # Issuer
    AUD = "aud"  # Audience
    EXP = "exp"  # Expiration time
    IAT = "iat"  # Issued at time
    AUTH_TIME = "auth_time"  # Authentication time
    NONCE = "nonce"  # Nonce

    # Standard profile claims
    NAME = "name"
    GIVEN_NAME = "given_name"
    FAMILY_NAME = "family_name"
    MIDDLE_NAME = "middle_name"
    NICKNAME = "nickname"
    PREFERRED_USERNAME = "preferred_username"
    PROFILE = "profile"
    PICTURE = "picture"
    WEBSITE = "website"
    GENDER = "gender"
    BIRTHDATE = "birthdate"
    ZONEINFO = "zoneinfo"
    LOCALE = "locale"
    UPDATED_AT = "updated_at"

    # Email claims
    EMAIL = "email"
    EMAIL_VERIFIED = "email_verified"

    # Phone claims
    PHONE_NUMBER = "phone_number"
    PHONE_NUMBER_VERIFIED = "phone_number_verified"

    # Address claims
    ADDRESS = "address"


class OIDCResponseMode(Enum):
    """OIDC response modes."""

    QUERY = "query"
    FRAGMENT = "fragment"
    FORM_POST = "form_post"


class OIDCPrompt(Enum):
    """OIDC prompt parameter values."""

    NONE = "none"  # No authentication UI should be shown
    LOGIN = "login"  # Force re-authentication
    CONSENT = "consent"  # Force consent screen
    SELECT_ACCOUNT = "select_account"  # Show account selection


@dataclass(frozen=True)
class OIDCIdToken(ValueObject):
    """
    OIDC ID Token domain model.

    Represents an OIDC ID Token containing identity claims about the user.
    """

    token_id: str
    subject: str  # User identifier
    issuer: str  # Identity provider
    audience: str  # Client ID
    expires_at: datetime
    issued_at: datetime
    auth_time: datetime | None = None
    nonce: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate the ID token."""
        if not self.token_id or not self.token_id.strip():
            raise ValueError("Token ID cannot be empty")

        if not self.subject or not self.subject.strip():
            raise ValueError("Subject cannot be empty")

        if not self.issuer or not self.issuer.strip():
            raise ValueError("Issuer cannot be empty")

        if not self.audience or not self.audience.strip():
            raise ValueError("Audience cannot be empty")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.issued_at.tzinfo is None:
            object.__setattr__(self, "issued_at", self.issued_at.replace(tzinfo=timezone.utc))

        if self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=timezone.utc))

        if self.auth_time and self.auth_time.tzinfo is None:
            object.__setattr__(self, "auth_time", self.auth_time.replace(tzinfo=timezone.utc))

    @classmethod
    def create(
        cls,
        subject: str,
        issuer: str,
        audience: str,
        claims: dict[str, Any] | None = None,
        nonce: str | None = None,
        auth_time: datetime | None = None,
        expires_in_seconds: int = 3600,  # 1 hour
        **kwargs,
    ) -> OIDCIdToken:
        """Create a new ID token."""
        now = datetime.now(timezone.utc)
        token_id = str(uuid4())

        return cls(
            token_id=token_id,
            subject=subject,
            issuer=issuer,
            audience=audience,
            issued_at=now,
            expires_at=now + timedelta(seconds=expires_in_seconds),
            auth_time=auth_time or now,
            nonce=nonce,
            claims=claims or {},
            **kwargs,
        )

    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    def get_claim(self, claim_name: str) -> Any:
        """Get a specific claim value."""
        # Check standard claims first
        if claim_name == OIDCClaimType.SUB.value:
            return self.subject
        elif claim_name == OIDCClaimType.ISS.value:
            return self.issuer
        elif claim_name == OIDCClaimType.AUD.value:
            return self.audience
        elif claim_name == OIDCClaimType.EXP.value:
            return int(self.expires_at.timestamp())
        elif claim_name == OIDCClaimType.IAT.value:
            return int(self.issued_at.timestamp())
        elif claim_name == OIDCClaimType.AUTH_TIME.value and self.auth_time:
            return int(self.auth_time.timestamp())
        elif claim_name == OIDCClaimType.NONCE.value:
            return self.nonce
        else:
            # Check additional claims
            return self.claims.get(claim_name)

    def to_payload(self) -> dict[str, Any]:
        """Convert to JWT payload format."""
        payload = {
            "sub": self.subject,
            "iss": self.issuer,
            "aud": self.audience,
            "exp": int(self.expires_at.timestamp()),
            "iat": int(self.issued_at.timestamp()),
            "jti": self.token_id,
        }

        if self.auth_time:
            payload["auth_time"] = int(self.auth_time.timestamp())

        if self.nonce:
            payload["nonce"] = self.nonce

        # Add additional claims
        payload.update(self.claims)

        return payload


@dataclass(frozen=True)
class OIDCUserInfo(ValueObject):
    """
    OIDC UserInfo domain model.

    Represents user information returned from the UserInfo endpoint.
    """

    subject: str
    claims: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the user info."""
        if not self.subject or not self.subject.strip():
            raise ValueError("Subject cannot be empty")

    def get_claim(self, claim_name: str) -> Any:
        """Get a specific claim value."""
        if claim_name == OIDCClaimType.SUB.value:
            return self.subject
        return self.claims.get(claim_name)

    def has_claim(self, claim_name: str) -> bool:
        """Check if a claim exists."""
        if claim_name == OIDCClaimType.SUB.value:
            return True
        return claim_name in self.claims

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"sub": self.subject}
        result.update(self.claims)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OIDCUserInfo:
        """Create from dictionary."""
        subject = data.pop("sub")
        return cls(subject=subject, claims=data)


@dataclass(frozen=True)
class OIDCAuthenticationRequest(ValueObject):
    """
    OIDC authentication request domain model.

    Extends OAuth2 authorization request with OIDC-specific parameters.
    """

    client_id: str
    redirect_uri: str
    response_type: str = "code"
    scope: str = "openid"
    state: str | None = None
    response_mode: OIDCResponseMode | None = None
    nonce: str | None = None
    display: str | None = None
    prompt: set[OIDCPrompt] = field(default_factory=set)
    max_age: int | None = None
    ui_locales: list[str] = field(default_factory=list)
    id_token_hint: str | None = None
    login_hint: str | None = None
    acr_values: list[str] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate the OIDC authentication request."""
        if not self.client_id or not self.client_id.strip():
            raise ValueError("Client ID cannot be empty")

        if not self.redirect_uri or not self.redirect_uri.strip():
            raise ValueError("Redirect URI cannot be empty")

        # OIDC requires openid scope
        scopes = set(self.scope.split())
        if "openid" not in scopes:
            raise ValueError("OIDC requests must include 'openid' scope")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

    @classmethod
    def from_query_params(cls, params: dict[str, str]) -> OIDCAuthenticationRequest:
        """Create OIDC request from query parameters."""
        # Parse prompt parameter
        prompt_str = params.get("prompt", "")
        prompts = set()
        if prompt_str:
            for prompt in prompt_str.split():
                try:
                    prompts.add(OIDCPrompt(prompt))
                except ValueError:
                    # Skip unknown prompts
                    pass

        # Parse response mode
        response_mode = None
        if "response_mode" in params:
            try:
                response_mode = OIDCResponseMode(params["response_mode"])
            except ValueError:
                # Invalid response mode
                pass

        # Parse claims parameter (JSON)
        claims = {}
        if "claims" in params:
            try:
                claims = json.loads(params["claims"])
            except (json.JSONDecodeError, TypeError):
                # Invalid claims parameter
                pass

        # Parse ui_locales
        ui_locales = []
        if "ui_locales" in params:
            ui_locales = params["ui_locales"].split()

        # Parse acr_values
        acr_values = []
        if "acr_values" in params:
            acr_values = params["acr_values"].split()

        return cls(
            client_id=params["client_id"],
            redirect_uri=params["redirect_uri"],
            response_type=params.get("response_type", "code"),
            scope=params.get("scope", "openid"),
            state=params.get("state"),
            response_mode=response_mode,
            nonce=params.get("nonce"),
            display=params.get("display"),
            prompt=prompts,
            max_age=int(params["max_age"]) if params.get("max_age") else None,
            ui_locales=ui_locales,
            id_token_hint=params.get("id_token_hint"),
            login_hint=params.get("login_hint"),
            acr_values=acr_values,
            claims=claims,
        )

    def get_scopes(self) -> set[str]:
        """Get requested scopes as a set."""
        return set(self.scope.split())

    def requires_id_token(self) -> bool:
        """Check if request requires an ID token in response."""
        response_types = set(self.response_type.split())
        return "id_token" in response_types

    def has_prompt(self, prompt: OIDCPrompt) -> bool:
        """Check if request has a specific prompt."""
        return prompt in self.prompt


@dataclass(frozen=True)
class OIDCDiscoveryDocument(ValueObject):
    """
    OIDC Provider Configuration Document.

    Represents the well-known configuration document that describes
    the OIDC provider's capabilities and endpoints.
    """

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    registration_endpoint: str | None = None
    scopes_supported: list[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    response_types_supported: list[str] = field(
        default_factory=lambda: ["code", "id_token", "token id_token"]
    )
    response_modes_supported: list[str] = field(
        default_factory=lambda: ["query", "fragment", "form_post"]
    )
    grant_types_supported: list[str] = field(
        default_factory=lambda: ["authorization_code", "refresh_token"]
    )
    subject_types_supported: list[str] = field(default_factory=lambda: ["public"])
    id_token_signing_alg_values_supported: list[str] = field(default_factory=lambda: ["RS256"])
    token_endpoint_auth_methods_supported: list[str] = field(
        default_factory=lambda: ["client_secret_basic", "client_secret_post"]
    )
    claims_supported: list[str] = field(
        default_factory=lambda: [
            "sub",
            "iss",
            "aud",
            "exp",
            "iat",
            "auth_time",
            "nonce",
            "name",
            "given_name",
            "family_name",
            "email",
            "email_verified",
        ]
    )
    code_challenge_methods_supported: list[str] = field(default_factory=lambda: ["S256", "plain"])

    def __post_init__(self):
        """Validate the discovery document."""
        if not self.issuer or not self.issuer.strip():
            raise ValueError("Issuer cannot be empty")

        if not self.authorization_endpoint or not self.authorization_endpoint.strip():
            raise ValueError("Authorization endpoint cannot be empty")

        if not self.token_endpoint or not self.token_endpoint.strip():
            raise ValueError("Token endpoint cannot be empty")

        if not self.userinfo_endpoint or not self.userinfo_endpoint.strip():
            raise ValueError("UserInfo endpoint cannot be empty")

        if not self.jwks_uri or not self.jwks_uri.strip():
            raise ValueError("JWKS URI cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "issuer": self.issuer,
            "authorization_endpoint": self.authorization_endpoint,
            "token_endpoint": self.token_endpoint,
            "userinfo_endpoint": self.userinfo_endpoint,
            "jwks_uri": self.jwks_uri,
            "scopes_supported": self.scopes_supported,
            "response_types_supported": self.response_types_supported,
            "response_modes_supported": self.response_modes_supported,
            "grant_types_supported": self.grant_types_supported,
            "subject_types_supported": self.subject_types_supported,
            "id_token_signing_alg_values_supported": self.id_token_signing_alg_values_supported,
            "token_endpoint_auth_methods_supported": self.token_endpoint_auth_methods_supported,
            "claims_supported": self.claims_supported,
            "code_challenge_methods_supported": self.code_challenge_methods_supported,
        }

        if self.registration_endpoint:
            result["registration_endpoint"] = self.registration_endpoint

        return result


def generate_nonce(length: int = 32) -> str:
    """Generate a secure nonce for OIDC requests."""
    return secrets.token_urlsafe(length)


def extract_claims_for_scope(scope: str) -> list[str]:
    """Extract standard claims for a given OIDC scope."""
    scope_claims = {
        "profile": [
            "name",
            "family_name",
            "given_name",
            "middle_name",
            "nickname",
            "preferred_username",
            "profile",
            "picture",
            "website",
            "gender",
            "birthdate",
            "zoneinfo",
            "locale",
            "updated_at",
        ],
        "email": ["email", "email_verified"],
        "address": ["address"],
        "phone": ["phone_number", "phone_number_verified"],
    }

    return scope_claims.get(scope, [])
