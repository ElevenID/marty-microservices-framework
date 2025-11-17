"""
OAuth2 and OpenID Connect domain models.

This module provides comprehensive domain models for OAuth2 authorization
and OpenID Connect (OIDC) identity protocols, including:

- OAuth2 authorization flows (authorization code, client credentials, etc.)
- Client registration and management
- Token lifecycle management (access tokens, refresh tokens, ID tokens)
- OIDC identity and user information handling
- Provider configuration and discovery

All models follow RFC 6749 (OAuth2), RFC 6750 (Bearer tokens),
RFC 7636 (PKCE), and OpenID Connect specifications.
"""

# OAuth2 Authorization models
from .oauth2_authorization import (
    OAuth2Authorization,
    OAuth2AuthorizationRequest,
    OAuth2AuthorizationResponse,
    OAuth2Flow,
    OAuth2ResponseType,
    OAuth2Scope,
    generate_authorization_code,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)

# OAuth2 Client models
from .oauth2_client import (
    OAuth2ApplicationType,
    OAuth2Client,
    OAuth2ClientRegistration,
    OAuth2ClientType,
    OAuth2TokenEndpointAuthMethod,
    generate_client_id,
    generate_client_secret,
)

# OAuth2 Token models
from .oauth2_token import (
    OAuth2AccessToken,
    OAuth2GrantType,
    OAuth2RefreshToken,
    OAuth2TokenIntrospection,
    OAuth2TokenRequest,
    OAuth2TokenResponse,
    OAuth2TokenType,
    generate_access_token,
    generate_refresh_token,
)

# OIDC models
from .oidc_models import (
    OIDCAuthenticationRequest,
    OIDCClaimType,
    OIDCDiscoveryDocument,
    OIDCIdToken,
    OIDCPrompt,
    OIDCResponseMode,
    OIDCUserInfo,
    extract_claims_for_scope,
    generate_nonce,
)

__all__ = [
    # OAuth2 Authorization
    "OAuth2Flow",
    "OAuth2ResponseType",
    "OAuth2Scope",
    "OAuth2AuthorizationRequest",
    "OAuth2Authorization",
    "OAuth2AuthorizationResponse",
    "generate_authorization_code",
    "generate_state",
    "generate_code_verifier",
    "generate_code_challenge",
    # OAuth2 Client
    "OAuth2ClientType",
    "OAuth2ApplicationType",
    "OAuth2TokenEndpointAuthMethod",
    "OAuth2Client",
    "OAuth2ClientRegistration",
    "generate_client_id",
    "generate_client_secret",
    # OAuth2 Token
    "OAuth2TokenType",
    "OAuth2GrantType",
    "OAuth2AccessToken",
    "OAuth2RefreshToken",
    "OAuth2TokenRequest",
    "OAuth2TokenResponse",
    "OAuth2TokenIntrospection",
    "generate_access_token",
    "generate_refresh_token",
    # OIDC
    "OIDCClaimType",
    "OIDCResponseMode",
    "OIDCPrompt",
    "OIDCIdToken",
    "OIDCUserInfo",
    "OIDCAuthenticationRequest",
    "OIDCDiscoveryDocument",
    "generate_nonce",
    "extract_claims_for_scope",
]
