"""
OIDC (OpenID Connect) client domain models.

This package contains domain models for OpenID Connect client integration
including discovery, token validation, and JWKS handling.
"""

# Discovery models
from .discovery import (
    OIDCCapability,
    OIDCDiscoveryResult,
    OIDCEndpoints,
    OIDCProviderConfiguration,
    OIDCProviderMetadata,
    create_discovery_url,
    parse_provider_metadata,
)

# Token and JWKS models
from .tokens import (
    JWK,
    JWKS,
    JWKSCache,
    JWKType,
    JWKUse,
    JWTHeader,
    JWTPayload,
    OIDCToken,
    TokenStatus,
    TokenType,
    TokenValidationRequest,
    TokenValidationResult,
    parse_jwt_header,
    parse_jwt_payload,
)

__all__ = [
    # Discovery models
    "OIDCCapability",
    "OIDCEndpoints",
    "OIDCProviderMetadata",
    "OIDCProviderConfiguration",
    "OIDCDiscoveryResult",
    "create_discovery_url",
    "parse_provider_metadata",
    # Token and JWKS models
    "TokenType",
    "TokenStatus",
    "JWKType",
    "JWKUse",
    "JWK",
    "JWKS",
    "JWTHeader",
    "JWTPayload",
    "OIDCToken",
    "TokenValidationRequest",
    "TokenValidationResult",
    "JWKSCache",
    "parse_jwt_header",
    "parse_jwt_payload",
]
