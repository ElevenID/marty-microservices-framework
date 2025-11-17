"""Core domain models for identity management."""

# Legacy domain models (will be phased out as we migrate)
from dataclasses import dataclass
from datetime import datetime

from .api_key import (
    APIKey,
    APIKeyMetadata,
    APIKeyPermission,
    APIKeyRotationPolicy,
    APIKeyScope,
    APIKeyStatus,
    APIKeyUsage,
    APIKeyValidationResult,
)
from .authenticated_user import AuthenticatedUser
from .authentication import (
    AuthenticationAttempt,
    AuthenticationChain,
    AuthenticationContext,
    AuthenticationEvent,
    AuthenticationMethod,
    AuthenticationPolicy,
    AuthenticationProvider,
    AuthenticationSecurityLevel,
)
from .authentication_result import (
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)
from .basic_auth import (
    BasicAuthAttempt,
    BasicAuthCredentials,
    HashedPassword,
    PasswordHashAlgorithm,
    PasswordPolicy,
    PasswordRequirements,
    PasswordStrength,
    PasswordValidationResult,
)
from .configuration import (
    AuthenticationConfiguration,
    IntegrationConfiguration,
    PolicyConfiguration,
    ProviderConfiguration,
    SecurityConfiguration,
)
from .mfa import (
    MFAChallenge,
    MFAChallengeStatus,
    MFADevice,
    MFADeviceStatus,
    MFADeviceType,
    MFAMethod,
    MFAVerification,
    MFAVerificationResponse,
    MFAVerificationResult,
)
from .mtls import (  # Certificate models; Authentication models; Configuration models
    AuthorityInformationAccess,
    AuthorityKeyIdentifier,
    BasicConstraints,
    CertificateAuthority,
    CertificateError,
    CertificateExtension,
    CertificateExtractionConfiguration,
    CertificateIdentity,
    CertificateIssuer,
    CertificatePolicies,
    CertificateSource,
    CertificateStatus,
    CertificateSubject,
    CertificateValidationConfiguration,
    CertificateValidationPolicy,
    CertificateValidationResult,
    ClientCertificate,
    CRLDistributionPoints,
    ExtendedKeyUsage,
    KeyUsage,
    MTLSAuthenticationContext,
    MTLSAuthenticationEvent,
    MTLSAuthenticationResult,
    MTLSConfiguration,
    MTLSSession,
    MTLSUserMapping,
    RevocationCheckConfiguration,
    RevocationCheckMethod,
    SubjectAlternativeName,
    SubjectKeyIdentifier,
    TrustStoreConfiguration,
    TrustStoreType,
    UserMappingMethod,
    X509Extension,
    create_file_based_trust_store,
    create_mtls_config,
    create_pkcs11_trust_store,
)
from .oauth2 import (  # OAuth2 Authorization; OAuth2 Client; OAuth2 Token; OIDC
    OAuth2AccessToken,
    OAuth2ApplicationType,
    OAuth2Authorization,
    OAuth2AuthorizationRequest,
    OAuth2AuthorizationResponse,
    OAuth2Client,
    OAuth2ClientRegistration,
    OAuth2ClientType,
    OAuth2Flow,
    OAuth2GrantType,
    OAuth2RefreshToken,
    OAuth2ResponseType,
    OAuth2Scope,
    OAuth2TokenEndpointAuthMethod,
    OAuth2TokenIntrospection,
    OAuth2TokenRequest,
    OAuth2TokenResponse,
    OAuth2TokenType,
    OIDCAuthenticationRequest,
    OIDCClaimType,
    OIDCDiscoveryDocument,
    OIDCIdToken,
    OIDCPrompt,
    OIDCResponseMode,
    OIDCUserInfo,
    extract_claims_for_scope,
    generate_access_token,
    generate_authorization_code,
    generate_client_id,
    generate_client_secret,
    generate_code_challenge,
    generate_code_verifier,
    generate_nonce,
    generate_refresh_token,
    generate_state,
)
from .oidc import (  # Discovery models; Token and JWKS models
    JWK,
    JWKS,
    JWKSCache,
    JWKType,
    JWKUse,
    JWTHeader,
    JWTPayload,
    OIDCCapability,
    OIDCDiscoveryResult,
    OIDCEndpoints,
    OIDCProviderConfiguration,
    OIDCProviderMetadata,
    OIDCToken,
    TokenStatus,
    TokenType,
    TokenValidationRequest,
    TokenValidationResult,
    create_discovery_url,
    parse_jwt_header,
    parse_jwt_payload,
    parse_provider_metadata,
)
from .session import (
    Session,
    SessionActivity,
    SessionCreationRequest,
    SessionDevice,
    SessionMetadata,
    SessionPolicy,
    SessionSecurityLevel,
    SessionStatus,
    SessionType,
)
from .user import (
    PasswordHash,
    SecurityQuestion,
    User,
    UserAccountSettings,
    UserActivity,
    UserCredentials,
    UserProfile,
    UserSecuritySettings,
    UserStatus,
)


@dataclass(frozen=True)
class UserId:
    """Value object representing a user identifier."""

    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("UserId cannot be empty")


@dataclass(frozen=True)
class Credentials:
    """Value object representing authentication credentials."""

    username: str
    password: str

    def __post_init__(self):
        if not self.username or not self.username.strip():
            raise ValueError("Username cannot be empty")
        if not self.password:
            raise ValueError("Password cannot be empty")


@dataclass
class Principal:
    """Entity representing an authenticated principal."""

    user_id: UserId
    username: str
    authenticated_at: datetime
    expires_at: datetime | None = None

    def is_expired(self, current_time: datetime) -> bool:
        """Check if the principal's authentication has expired."""
        if self.expires_at is None:
            return False
        return current_time >= self.expires_at


# Legacy AuthenticationResult - use the new one instead
@dataclass
class LegacyAuthenticationResult:
    """Legacy result of an authentication attempt."""

    status: AuthenticationStatus
    principal: Principal | None = None
    error_message: str | None = None

    def __post_init__(self):
        if self.status == AuthenticationStatus.SUCCESS and self.principal is None:
            raise ValueError("Successful authentication must include a principal")
        if self.status == AuthenticationStatus.FAILED and self.error_message is None:
            raise ValueError("Failed authentication must include an error message")


# MFA domain models

# mTLS models

# OAuth2 models

# OIDC models

# User and authentication models

__all__ = [
    # Legacy models
    "AuthenticationErrorCode",
    "AuthenticationResult",
    "AuthenticationStatus",
    "AuthenticatedUser",
    "UserId",
    "Credentials",
    "Principal",
    "LegacyAuthenticationResult",
    # MFA models
    "MFAChallenge",
    "MFAChallengeStatus",
    "MFADevice",
    "MFADeviceStatus",
    "MFADeviceType",
    "MFAMethod",
    "MFAVerification",
    "MFAVerificationResult",
    "MFAVerificationResponse",
    # User models
    "User",
    "UserProfile",
    "UserStatus",
    "UserCredentials",
    "PasswordHash",
    "SecurityQuestion",
    "UserSecuritySettings",
    "UserActivity",
    "UserAccountSettings",
    # Basic authentication models
    "BasicAuthCredentials",
    "BasicAuthAttempt",
    "PasswordPolicy",
    "PasswordStrength",
    "PasswordRequirements",
    "PasswordValidationResult",
    "PasswordHashAlgorithm",
    "HashedPassword",
    # API Key models
    "APIKey",
    "APIKeyStatus",
    "APIKeyScope",
    "APIKeyMetadata",
    "APIKeyRotationPolicy",
    "APIKeyUsage",
    "APIKeyPermission",
    "APIKeyValidationResult",
    # Session models
    "Session",
    "SessionStatus",
    "SessionType",
    "SessionSecurityLevel",
    "SessionPolicy",
    "SessionMetadata",
    "SessionDevice",
    "SessionActivity",
    "SessionCreationRequest",
    # Authentication models
    "AuthenticationProvider",
    "AuthenticationMethod",
    "AuthenticationAttempt",
    "AuthenticationContext",
    "AuthenticationPolicy",
    "AuthenticationSecurityLevel",
    "AuthenticationChain",
    "AuthenticationEvent",
    # Configuration models
    "AuthenticationConfiguration",
    "ProviderConfiguration",
    "SecurityConfiguration",
    "PolicyConfiguration",
    "IntegrationConfiguration",
]

# Note: OAuth2, mTLS, and OIDC models are included via wildcard imports above
# This provides all the models while maintaining clean separation of concerns
