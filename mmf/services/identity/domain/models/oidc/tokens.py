"""
OIDC token validation and JWKS domain models.

This module contains domain models for OpenID Connect token validation
including JWT token models, JWKS handling, and token verification.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from mmf.core.domain.entity import DomainEntity, ValueObject
from mmf.services.identity.domain.models.user import UserId


class TokenType(Enum):
    """Types of OIDC tokens."""

    ID_TOKEN = "id_token"
    ACCESS_TOKEN = "access_token"
    REFRESH_TOKEN = "refresh_token"


class TokenStatus(Enum):
    """Status of token validation."""

    VALID = "valid"
    EXPIRED = "expired"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_ISSUER = "invalid_issuer"
    INVALID_AUDIENCE = "invalid_audience"
    INVALID_FORMAT = "invalid_format"
    NOT_YET_VALID = "not_yet_valid"
    REVOKED = "revoked"
    UNKNOWN_KID = "unknown_kid"


class JWKType(Enum):
    """JSON Web Key types."""

    RSA = "RSA"
    EC = "EC"
    OCT = "oct"  # Symmetric key
    OKP = "OKP"  # Octet key pair


class JWKUse(Enum):
    """JSON Web Key usage."""

    SIGNATURE = "sig"
    ENCRYPTION = "enc"


@dataclass(frozen=True)
class JWK(ValueObject):
    """JSON Web Key representation."""

    # Key identification
    kid: str  # Key ID
    kty: JWKType  # Key type

    # Key usage
    use: JWKUse | None = None
    key_ops: set[str] = field(default_factory=set)  # Key operations
    alg: str | None = None  # Algorithm

    # RSA public key components
    n: str | None = None  # Modulus
    e: str | None = None  # Exponent

    # EC public key components
    crv: str | None = None  # Curve
    x: str | None = None  # X coordinate
    y: str | None = None  # Y coordinate

    # Symmetric key
    k: str | None = None  # Key value

    # Certificate chain
    x5c: list[str] = field(default_factory=list)  # X.509 certificate chain
    x5t: str | None = None  # X.509 thumbprint
    x5t_s256: str | None = None  # X.509 thumbprint SHA-256
    x5u: str | None = None  # X.509 URL

    # Additional properties
    additional_properties: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate JWK."""
        if not self.kid.strip():
            raise ValueError("Key ID (kid) cannot be empty")

        if self.kty == JWKType.RSA:
            if not self.n or not self.e:
                raise ValueError("RSA key must have modulus (n) and exponent (e)")
        elif self.kty == JWKType.EC:
            if not self.crv or not self.x or not self.y:
                raise ValueError("EC key must have curve (crv), x, and y coordinates")
        elif self.kty == JWKType.OCT:
            if not self.k:
                raise ValueError("Symmetric key must have key value (k)")

    def is_for_signature(self) -> bool:
        """Check if key is for signature verification."""
        if self.use:
            return self.use == JWKUse.SIGNATURE

        # If no use is specified, check key operations
        if self.key_ops:
            return "verify" in self.key_ops or "sign" in self.key_ops

        # Default to signature if no use/key_ops specified
        return True

    def supports_algorithm(self, algorithm: str) -> bool:
        """Check if key supports a specific algorithm."""
        if self.alg:
            return self.alg == algorithm

        # Check compatibility based on key type
        if self.kty == JWKType.RSA:
            return algorithm in ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512"]
        elif self.kty == JWKType.EC:
            curve_alg_mapping = {
                "P-256": ["ES256"],
                "P-384": ["ES384"],
                "P-521": ["ES512"],
                "secp256k1": ["ES256K"],
            }
            return algorithm in curve_alg_mapping.get(self.crv, [])
        elif self.kty == JWKType.OCT:
            return algorithm in ["HS256", "HS384", "HS512"]

        return False


@dataclass(frozen=True)
class JWKS(ValueObject):
    """JSON Web Key Set representation."""

    keys: list[JWK]

    # Cache metadata
    retrieved_at: datetime = field(default_factory=datetime.utcnow)
    cache_control: str | None = None
    etag: str | None = None

    def __post_init__(self):
        """Validate JWKS."""
        if not self.keys:
            raise ValueError("JWKS must contain at least one key")

        # Check for duplicate key IDs
        key_ids = [key.kid for key in self.keys]
        if len(key_ids) != len(set(key_ids)):
            raise ValueError("JWKS cannot contain duplicate key IDs")

    def get_key_by_id(self, kid: str) -> JWK | None:
        """Get key by key ID."""
        for key in self.keys:
            if key.kid == kid:
                return key
        return None

    def get_keys_for_algorithm(self, algorithm: str) -> list[JWK]:
        """Get all keys that support a specific algorithm."""
        return [key for key in self.keys if key.supports_algorithm(algorithm)]

    def get_signature_keys(self) -> list[JWK]:
        """Get all keys that can be used for signature verification."""
        return [key for key in self.keys if key.is_for_signature()]


@dataclass(frozen=True)
class JWTHeader(ValueObject):
    """JWT header representation."""

    # Algorithm and key identification
    alg: str  # Algorithm
    kid: str | None = None  # Key ID
    typ: str = "JWT"  # Token type

    # Additional header parameters
    jku: str | None = None  # JWK Set URL
    jwk: dict[str, Any] | None = None  # JSON Web Key
    x5u: str | None = None  # X.509 URL
    x5c: list[str] = field(default_factory=list)  # X.509 certificate chain
    x5t: str | None = None  # X.509 thumbprint
    x5t_s256: str | None = None  # X.509 thumbprint SHA-256
    cty: str | None = None  # Content type
    crit: list[str] = field(default_factory=list)  # Critical headers

    # Additional header claims
    additional_claims: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate JWT header."""
        if not self.alg.strip():
            raise ValueError("Algorithm (alg) cannot be empty")

        if self.alg == "none":
            raise ValueError("Algorithm 'none' is not allowed for security reasons")


@dataclass(frozen=True)
class JWTPayload(ValueObject):
    """JWT payload representation."""

    # Standard JWT claims
    iss: str | None = None  # Issuer
    sub: str | None = None  # Subject
    aud: str | list[str] | None = None  # Audience
    exp: int | None = None  # Expiration time
    nbf: int | None = None  # Not before
    iat: int | None = None  # Issued at
    jti: str | None = None  # JWT ID

    # OIDC specific claims
    nonce: str | None = None  # Nonce
    at_hash: str | None = None  # Access token hash
    c_hash: str | None = None  # Code hash
    s_hash: str | None = None  # State hash

    # User information claims
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    middle_name: str | None = None
    nickname: str | None = None
    preferred_username: str | None = None
    profile: str | None = None
    picture: str | None = None
    website: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    gender: str | None = None
    birthdate: str | None = None
    zoneinfo: str | None = None
    locale: str | None = None
    phone_number: str | None = None
    phone_number_verified: bool | None = None
    address: dict[str, Any] | None = None
    updated_at: int | None = None

    # Authorization claims
    scope: str | None = None
    groups: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    # Additional custom claims
    custom_claims: dict[str, Any] = field(default_factory=dict)

    def get_audiences(self) -> list[str]:
        """Get audience as list."""
        if isinstance(self.aud, str):
            return [self.aud]
        elif isinstance(self.aud, list):
            return self.aud
        else:
            return []

    def is_expired(self, clock_skew: timedelta = timedelta(0)) -> bool:
        """Check if token is expired."""
        if not self.exp:
            return False

        current_time = datetime.utcnow().timestamp()
        return current_time > (self.exp + clock_skew.total_seconds())

    def is_not_yet_valid(self, clock_skew: timedelta = timedelta(0)) -> bool:
        """Check if token is not yet valid."""
        if not self.nbf:
            return False

        current_time = datetime.utcnow().timestamp()
        return current_time < (self.nbf - clock_skew.total_seconds())

    def get_claim(self, claim_name: str) -> Any:
        """Get claim value by name."""
        # Check standard claims first
        if hasattr(self, claim_name):
            return getattr(self, claim_name)

        # Check custom claims
        return self.custom_claims.get(claim_name)


@dataclass
class OIDCToken(DomainEntity):
    """OIDC token representation."""

    # Token content
    token_type: TokenType
    raw_token: str
    header: JWTHeader
    payload: JWTPayload
    signature: str

    # Validation status
    validation_status: TokenStatus = TokenStatus.VALID
    validation_error: str | None = None
    validation_details: dict[str, Any] = field(default_factory=dict)

    # Metadata
    validated_at: datetime | None = None
    validated_with_key: str | None = None  # Key ID used for validation
    issuer_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate token."""
        if not self.raw_token.strip():
            raise ValueError("Raw token cannot be empty")

        if self.token_type == TokenType.ID_TOKEN:
            # ID tokens must have subject
            if not self.payload.sub:
                raise ValueError("ID token must have subject (sub) claim")

    def is_valid(self) -> bool:
        """Check if token is valid."""
        return self.validation_status == TokenStatus.VALID

    def is_expired(self, clock_skew: timedelta = timedelta(minutes=5)) -> bool:
        """Check if token is expired."""
        return self.payload.is_expired(clock_skew)

    def get_subject(self) -> str | None:
        """Get token subject."""
        return self.payload.sub

    def get_user_id(self) -> UserId | None:
        """Get user ID from token."""
        if self.payload.sub:
            return UserId(self.payload.sub)
        return None

    def get_claim(self, claim_name: str) -> Any:
        """Get claim value."""
        return self.payload.get_claim(claim_name)

    def has_scope(self, scope: str) -> bool:
        """Check if token has a specific scope."""
        token_scope = self.payload.scope
        if not token_scope:
            return False

        scopes = token_scope.split()
        return scope in scopes

    def has_role(self, role: str) -> bool:
        """Check if token has a specific role."""
        return role in self.payload.roles

    def has_permission(self, permission: str) -> bool:
        """Check if token has a specific permission."""
        return permission in self.payload.permissions


@dataclass(frozen=True)
class TokenValidationRequest(ValueObject):
    """Request for token validation."""

    # Token to validate
    raw_token: str
    token_type: TokenType

    # Validation parameters
    expected_issuer: str | None = None
    expected_audience: str | list[str] | None = None
    expected_nonce: str | None = None

    # Validation options
    verify_signature: bool = True
    verify_expiration: bool = True
    verify_not_before: bool = True
    verify_issuer: bool = True
    verify_audience: bool = True

    # Clock skew tolerance
    clock_skew_tolerance: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    # JWKS for validation
    jwks: JWKS | None = None
    jwks_uri: str | None = None

    def __post_init__(self):
        """Validate token validation request."""
        if not self.raw_token.strip():
            raise ValueError("Token cannot be empty")

        if self.verify_issuer and not self.expected_issuer:
            raise ValueError("Expected issuer must be provided when verifying issuer")

        if self.verify_audience and not self.expected_audience:
            raise ValueError("Expected audience must be provided when verifying audience")

    def get_expected_audiences(self) -> list[str]:
        """Get expected audiences as list."""
        if isinstance(self.expected_audience, str):
            return [self.expected_audience]
        elif isinstance(self.expected_audience, list):
            return self.expected_audience
        else:
            return []


@dataclass(frozen=True)
class TokenValidationResult(ValueObject):
    """Result of token validation."""

    # Validation outcome
    success: bool
    token: OIDCToken | None = None

    # Error information
    error_code: str | None = None
    error_message: str | None = None
    validation_errors: list[str] = field(default_factory=list)

    # Validation metadata
    validation_duration_ms: int = 0
    key_used: str | None = None  # Key ID used for validation
    algorithm_used: str | None = None

    # Security information
    signature_valid: bool = False
    expiration_valid: bool = False
    issuer_valid: bool = False
    audience_valid: bool = False
    nonce_valid: bool = False

    @classmethod
    def create_success(
        cls,
        token: OIDCToken,
        key_id: str | None = None,
        algorithm: str | None = None,
        duration_ms: int = 0,
    ) -> TokenValidationResult:
        """Create successful validation result."""
        return cls(
            success=True,
            token=token,
            validation_duration_ms=duration_ms,
            key_used=key_id,
            algorithm_used=algorithm,
            signature_valid=True,
            expiration_valid=not token.is_expired(),
            issuer_valid=True,
            audience_valid=True,
            nonce_valid=True,
        )

    @classmethod
    def create_failure(
        cls,
        error_code: str,
        error_message: str,
        validation_errors: list[str] | None = None,
        duration_ms: int = 0,
    ) -> TokenValidationResult:
        """Create failed validation result."""
        return cls(
            success=False,
            error_code=error_code,
            error_message=error_message,
            validation_errors=validation_errors or [],
            validation_duration_ms=duration_ms,
        )


@dataclass
class JWKSCache(DomainEntity):
    """JWKS cache for performance optimization."""

    # Cache identification
    issuer: str
    jwks_uri: str

    # Cached data
    jwks: JWKS

    # Cache metadata
    cached_at: datetime = field(default_factory=datetime.utcnow)
    cache_ttl: timedelta = field(default_factory=lambda: timedelta(hours=1))
    etag: str | None = None
    last_modified: str | None = None

    # Cache statistics
    hit_count: int = 0
    miss_count: int = 0
    refresh_count: int = 0

    def is_expired(self) -> bool:
        """Check if cache is expired."""
        expiry_time = self.cached_at + self.cache_ttl
        return datetime.utcnow() > expiry_time

    def is_refresh_needed(self) -> bool:
        """Check if cache needs refreshing."""
        return self.is_expired()

    def record_hit(self) -> None:
        """Record cache hit."""
        self.hit_count += 1

    def record_miss(self) -> None:
        """Record cache miss."""
        self.miss_count += 1

    def record_refresh(self) -> None:
        """Record cache refresh."""
        self.refresh_count += 1

    def update_jwks(self, new_jwks: JWKS, etag: str | None = None) -> None:
        """Update cached JWKS."""
        self.jwks = new_jwks
        self.cached_at = datetime.utcnow()
        self.etag = etag
        self.record_refresh()

    def get_cache_efficiency(self) -> float:
        """Get cache hit ratio."""
        total_requests = self.hit_count + self.miss_count
        if total_requests == 0:
            return 0.0
        return self.hit_count / total_requests


# Utility functions


def parse_jwt_header(header_b64: str) -> JWTHeader:
    """Parse JWT header from base64 encoded string."""

    # Add padding if needed
    header_b64 += "=" * (4 - len(header_b64) % 4)

    # Decode and parse
    header_bytes = base64.urlsafe_b64decode(header_b64)
    header_dict = json.loads(header_bytes.decode("utf-8"))

    # Extract known fields and additional claims
    known_fields = {
        "alg",
        "kid",
        "typ",
        "jku",
        "jwk",
        "x5u",
        "x5c",
        "x5t",
        "x5t_s256",
        "cty",
        "crit",
    }
    additional_claims = {k: v for k, v in header_dict.items() if k not in known_fields}

    return JWTHeader(
        alg=header_dict["alg"],
        kid=header_dict.get("kid"),
        typ=header_dict.get("typ", "JWT"),
        jku=header_dict.get("jku"),
        jwk=header_dict.get("jwk"),
        x5u=header_dict.get("x5u"),
        x5c=header_dict.get("x5c", []),
        x5t=header_dict.get("x5t"),
        x5t_s256=header_dict.get("x5t_s256"),
        cty=header_dict.get("cty"),
        crit=header_dict.get("crit", []),
        additional_claims=additional_claims,
    )


def parse_jwt_payload(payload_b64: str) -> JWTPayload:
    """Parse JWT payload from base64 encoded string."""

    # Add padding if needed
    payload_b64 += "=" * (4 - len(payload_b64) % 4)

    # Decode and parse
    payload_bytes = base64.urlsafe_b64decode(payload_b64)
    payload_dict = json.loads(payload_bytes.decode("utf-8"))

    # Extract known fields and custom claims
    known_fields = {
        "iss",
        "sub",
        "aud",
        "exp",
        "nbf",
        "iat",
        "jti",
        "nonce",
        "at_hash",
        "c_hash",
        "s_hash",
        "name",
        "given_name",
        "family_name",
        "middle_name",
        "nickname",
        "preferred_username",
        "profile",
        "picture",
        "website",
        "email",
        "email_verified",
        "gender",
        "birthdate",
        "zoneinfo",
        "locale",
        "phone_number",
        "phone_number_verified",
        "address",
        "updated_at",
        "scope",
        "groups",
        "roles",
        "permissions",
    }
    custom_claims = {k: v for k, v in payload_dict.items() if k not in known_fields}

    return JWTPayload(
        iss=payload_dict.get("iss"),
        sub=payload_dict.get("sub"),
        aud=payload_dict.get("aud"),
        exp=payload_dict.get("exp"),
        nbf=payload_dict.get("nbf"),
        iat=payload_dict.get("iat"),
        jti=payload_dict.get("jti"),
        nonce=payload_dict.get("nonce"),
        at_hash=payload_dict.get("at_hash"),
        c_hash=payload_dict.get("c_hash"),
        s_hash=payload_dict.get("s_hash"),
        name=payload_dict.get("name"),
        given_name=payload_dict.get("given_name"),
        family_name=payload_dict.get("family_name"),
        middle_name=payload_dict.get("middle_name"),
        nickname=payload_dict.get("nickname"),
        preferred_username=payload_dict.get("preferred_username"),
        profile=payload_dict.get("profile"),
        picture=payload_dict.get("picture"),
        website=payload_dict.get("website"),
        email=payload_dict.get("email"),
        email_verified=payload_dict.get("email_verified"),
        gender=payload_dict.get("gender"),
        birthdate=payload_dict.get("birthdate"),
        zoneinfo=payload_dict.get("zoneinfo"),
        locale=payload_dict.get("locale"),
        phone_number=payload_dict.get("phone_number"),
        phone_number_verified=payload_dict.get("phone_number_verified"),
        address=payload_dict.get("address"),
        updated_at=payload_dict.get("updated_at"),
        scope=payload_dict.get("scope"),
        groups=payload_dict.get("groups", []),
        roles=payload_dict.get("roles", []),
        permissions=payload_dict.get("permissions", []),
        custom_claims=custom_claims,
    )
