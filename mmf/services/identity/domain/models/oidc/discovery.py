"""
OIDC discovery domain models.

This module contains domain models for OpenID Connect discovery including
provider configuration, endpoint discovery, and capability detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from mmf.core.domain.entity import DomainEntity, ValueObject


class OIDCCapability(Enum):
    """OIDC capabilities and features."""

    # Core OIDC capabilities
    AUTHORIZATION_CODE_FLOW = "authorization_code"
    IMPLICIT_FLOW = "implicit"
    HYBRID_FLOW = "hybrid"

    # Additional OAuth2 flows
    CLIENT_CREDENTIALS_FLOW = "client_credentials"
    PASSWORD_FLOW = "password"  # pragma: allowlist secret
    REFRESH_TOKEN_FLOW = "refresh_token"

    # PKCE support
    PKCE = "pkce"
    PKCE_S256 = "pkce_s256"

    # Token types
    JWT_TOKENS = "jwt"
    REFERENCE_TOKENS = "reference"

    # Additional features
    USERINFO = "userinfo"
    INTROSPECTION = "introspection"
    REVOCATION = "revocation"

    # Session management
    SESSION_MANAGEMENT = "session_management"
    FRONT_CHANNEL_LOGOUT = "front_channel_logout"
    BACK_CHANNEL_LOGOUT = "back_channel_logout"

    # Discovery
    DISCOVERY = "discovery"
    DYNAMIC_REGISTRATION = "dynamic_registration"


@dataclass(frozen=True)
class OIDCEndpoints(ValueObject):
    """OIDC provider endpoints."""

    # Core endpoints (required)
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str

    # Discovery endpoint
    issuer: str

    # Optional endpoints
    registration_endpoint: str | None = None
    introspection_endpoint: str | None = None
    revocation_endpoint: str | None = None
    end_session_endpoint: str | None = None

    # Session management endpoints
    check_session_iframe: str | None = None

    # Device authorization endpoints
    device_authorization_endpoint: str | None = None

    def __post_init__(self):
        """Validate endpoints."""
        required_endpoints = [
            ("authorization_endpoint", self.authorization_endpoint),
            ("token_endpoint", self.token_endpoint),
            ("userinfo_endpoint", self.userinfo_endpoint),
            ("jwks_uri", self.jwks_uri),
            ("issuer", self.issuer),
        ]

        for name, endpoint in required_endpoints:
            if not endpoint or not endpoint.strip():
                raise ValueError(f"{name} cannot be empty")

            # Basic URL validation
            parsed = urlparse(endpoint)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"{name} must be a valid URL")

    def get_endpoint(self, endpoint_type: str) -> str | None:
        """Get endpoint by type."""
        endpoint_mapping = {
            "authorization": self.authorization_endpoint,
            "token": self.token_endpoint,
            "userinfo": self.userinfo_endpoint,
            "jwks": self.jwks_uri,
            "registration": self.registration_endpoint,
            "introspection": self.introspection_endpoint,
            "revocation": self.revocation_endpoint,
            "end_session": self.end_session_endpoint,
            "check_session": self.check_session_iframe,
            "device_authorization": self.device_authorization_endpoint,
        }
        return endpoint_mapping.get(endpoint_type)


@dataclass(frozen=True)
class OIDCProviderMetadata(ValueObject):
    """Complete OIDC provider metadata from discovery."""

    # Provider identification
    issuer: str

    # Endpoints
    endpoints: OIDCEndpoints

    # Supported features
    response_types_supported: set[str] = field(default_factory=set)
    response_modes_supported: set[str] = field(default_factory=set)
    grant_types_supported: set[str] = field(default_factory=set)
    subject_types_supported: set[str] = field(default_factory=set)

    # Cryptographic capabilities
    id_token_signing_alg_values_supported: set[str] = field(default_factory=set)
    id_token_encryption_alg_values_supported: set[str] = field(default_factory=set)
    userinfo_signing_alg_values_supported: set[str] = field(default_factory=set)
    userinfo_encryption_alg_values_supported: set[str] = field(default_factory=set)

    # Token and claim capabilities
    token_endpoint_auth_methods_supported: set[str] = field(default_factory=set)
    scopes_supported: set[str] = field(default_factory=set)
    claims_supported: set[str] = field(default_factory=set)
    claim_types_supported: set[str] = field(default_factory=set)

    # PKCE and security features
    code_challenge_methods_supported: set[str] = field(default_factory=set)

    # Additional capabilities
    capabilities: set[OIDCCapability] = field(default_factory=set)

    # Provider-specific metadata
    custom_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate provider metadata."""
        if not self.issuer.strip():
            raise ValueError("Issuer cannot be empty")

        # Validate issuer is a valid HTTPS URL (required by OIDC spec)
        parsed = urlparse(self.issuer)
        if parsed.scheme != "https" and not self.issuer.startswith("http://localhost"):
            raise ValueError("Issuer must use HTTPS (except localhost for testing)")

    def supports_response_type(self, response_type: str) -> bool:
        """Check if provider supports a specific response type."""
        return response_type in self.response_types_supported

    def supports_grant_type(self, grant_type: str) -> bool:
        """Check if provider supports a specific grant type."""
        return grant_type in self.grant_types_supported

    def supports_scope(self, scope: str) -> bool:
        """Check if provider supports a specific scope."""
        return scope in self.scopes_supported

    def supports_capability(self, capability: OIDCCapability) -> bool:
        """Check if provider supports a specific capability."""
        return capability in self.capabilities

    def supports_pkce(self) -> bool:
        """Check if provider supports PKCE."""
        return bool(self.code_challenge_methods_supported)

    def supports_s256_pkce(self) -> bool:
        """Check if provider supports S256 PKCE method."""
        return "S256" in self.code_challenge_methods_supported

    def get_preferred_signing_algorithm(self) -> str:
        """Get preferred ID token signing algorithm."""
        # Prefer stronger algorithms
        preferred_order = ["RS256", "PS256", "ES256", "HS256"]

        for alg in preferred_order:
            if alg in self.id_token_signing_alg_values_supported:
                return alg

        # Fall back to any supported algorithm
        if self.id_token_signing_alg_values_supported:
            return next(iter(self.id_token_signing_alg_values_supported))

        return "RS256"  # Default fallback


@dataclass
class OIDCProviderConfiguration(DomainEntity):
    """OIDC provider configuration including metadata and client settings."""

    # Provider identification
    provider_name: str
    issuer_url: str

    # Client configuration
    client_id: str
    client_secret: str | None = None

    # Discovered metadata
    metadata: OIDCProviderMetadata | None = None

    # Discovery settings
    discovery_url: str | None = None
    auto_discovery: bool = True
    discovery_cache_ttl: timedelta = field(default_factory=lambda: timedelta(hours=24))

    # Client settings
    redirect_uri: str | None = None
    post_logout_redirect_uri: str | None = None
    default_scopes: set[str] = field(default_factory=lambda: {"openid", "profile", "email"})

    # Security settings
    require_https: bool = True
    validate_issuer: bool = True
    validate_audience: bool = True
    clock_skew_tolerance: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    # Cache and performance
    jwks_cache_ttl: timedelta = field(default_factory=lambda: timedelta(hours=1))
    metadata_cache_ttl: timedelta = field(default_factory=lambda: timedelta(hours=24))

    # State management
    state_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=10))
    nonce_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=10))

    # Discovery status
    last_discovery_attempt: datetime | None = None
    last_successful_discovery: datetime | None = None
    discovery_error: str | None = None
    is_discovered: bool = False

    def __post_init__(self):
        """Validate provider configuration."""
        if not self.provider_name.strip():
            raise ValueError("Provider name cannot be empty")

        if not self.issuer_url.strip():
            raise ValueError("Issuer URL cannot be empty")

        if not self.client_id.strip():
            raise ValueError("Client ID cannot be empty")

        # Generate discovery URL if not provided
        if not self.discovery_url and self.auto_discovery:
            self.discovery_url = f"{self.issuer_url.rstrip('/')}/.well-known/openid-configuration"

    def is_discovery_needed(self) -> bool:
        """Check if discovery needs to be performed."""
        if not self.auto_discovery:
            return False

        if not self.is_discovered:
            return True

        if not self.last_successful_discovery:
            return True

        # Check if cache has expired
        cache_expiry = self.last_successful_discovery + self.discovery_cache_ttl
        return datetime.utcnow() > cache_expiry

    def mark_discovery_success(self, metadata: OIDCProviderMetadata) -> None:
        """Mark discovery as successful and cache metadata."""
        self.metadata = metadata
        self.is_discovered = True
        self.last_successful_discovery = datetime.utcnow()
        self.last_discovery_attempt = datetime.utcnow()
        self.discovery_error = None

    def mark_discovery_failure(self, error: str) -> None:
        """Mark discovery as failed."""
        self.discovery_error = error
        self.last_discovery_attempt = datetime.utcnow()
        self.is_discovered = False

    def get_authorization_endpoint(self) -> str | None:
        """Get authorization endpoint URL."""
        return self.metadata.endpoints.authorization_endpoint if self.metadata else None

    def get_token_endpoint(self) -> str | None:
        """Get token endpoint URL."""
        return self.metadata.endpoints.token_endpoint if self.metadata else None

    def get_userinfo_endpoint(self) -> str | None:
        """Get userinfo endpoint URL."""
        return self.metadata.endpoints.userinfo_endpoint if self.metadata else None

    def get_jwks_uri(self) -> str | None:
        """Get JWKS URI."""
        return self.metadata.endpoints.jwks_uri if self.metadata else None

    def supports_flow(self, flow_type: str) -> bool:
        """Check if provider supports a specific flow type."""
        if not self.metadata:
            return False

        flow_mapping = {
            "authorization_code": "authorization_code",
            "implicit": "implicit",
            "hybrid": ["code id_token", "code token", "code id_token token"],
            "client_credentials": "client_credentials",
            "password": "password",  # pragma: allowlist secret
        }

        required_grant = flow_mapping.get(flow_type)
        if isinstance(required_grant, str):
            return self.metadata.supports_grant_type(required_grant)
        elif isinstance(required_grant, list):
            return any(self.metadata.supports_response_type(rt) for rt in required_grant)

        return False

    def get_recommended_scopes(self, additional_scopes: set[str] | None = None) -> set[str]:
        """Get recommended scopes for authentication."""
        scopes = self.default_scopes.copy()

        if additional_scopes:
            scopes.update(additional_scopes)

        # Filter to only supported scopes if metadata is available
        if self.metadata and self.metadata.scopes_supported:
            scopes = scopes.intersection(self.metadata.scopes_supported)

        # Ensure openid scope is always included for OIDC
        scopes.add("openid")

        return scopes


@dataclass(frozen=True)
class OIDCDiscoveryResult(ValueObject):
    """Result of OIDC discovery operation."""

    # Discovery outcome
    success: bool
    provider_configuration: OIDCProviderConfiguration

    # Error information
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] = field(default_factory=dict)

    # Discovery metadata
    discovery_url: str = ""
    discovery_duration_ms: int = 0
    discovered_at: datetime = field(default_factory=datetime.utcnow)

    # Capabilities summary
    supported_flows: set[str] = field(default_factory=set)
    supported_scopes: set[str] = field(default_factory=set)
    security_features: set[str] = field(default_factory=set)

    @classmethod
    def create_success(
        cls,
        configuration: OIDCProviderConfiguration,
        discovery_url: str,
        duration_ms: int = 0,
    ) -> OIDCDiscoveryResult:
        """Create a successful discovery result."""
        supported_flows = set()
        supported_scopes = set()
        security_features = set()

        if configuration.metadata:
            # Extract supported flows
            if configuration.metadata.supports_grant_type("authorization_code"):
                supported_flows.add("authorization_code")
            if configuration.metadata.supports_grant_type("implicit"):
                supported_flows.add("implicit")
            if configuration.metadata.supports_grant_type("client_credentials"):
                supported_flows.add("client_credentials")

            # Extract supported scopes
            supported_scopes = configuration.metadata.scopes_supported.copy()

            # Extract security features
            if configuration.metadata.supports_pkce():
                security_features.add("pkce")
            if configuration.metadata.supports_s256_pkce():
                security_features.add("pkce_s256")

        return cls(
            success=True,
            provider_configuration=configuration,
            discovery_url=discovery_url,
            discovery_duration_ms=duration_ms,
            supported_flows=supported_flows,
            supported_scopes=supported_scopes,
            security_features=security_features,
        )

    @classmethod
    def create_failure(
        cls,
        configuration: OIDCProviderConfiguration,
        error_code: str,
        error_message: str,
        discovery_url: str = "",
        duration_ms: int = 0,
        error_details: dict[str, Any] | None = None,
    ) -> OIDCDiscoveryResult:
        """Create a failed discovery result."""
        return cls(
            success=False,
            provider_configuration=configuration,
            error_code=error_code,
            error_message=error_message,
            error_details=error_details or {},
            discovery_url=discovery_url,
            discovery_duration_ms=duration_ms,
        )


# Utility functions for discovery


def create_discovery_url(issuer: str) -> str:
    """Create OIDC discovery URL from issuer."""
    return urljoin(issuer.rstrip("/") + "/", ".well-known/openid-configuration")


def parse_provider_metadata(metadata_dict: dict[str, Any]) -> OIDCProviderMetadata:
    """Parse provider metadata from discovery response."""
    # Extract endpoints
    endpoints = OIDCEndpoints(
        issuer=metadata_dict["issuer"],
        authorization_endpoint=metadata_dict["authorization_endpoint"],
        token_endpoint=metadata_dict["token_endpoint"],
        userinfo_endpoint=metadata_dict["userinfo_endpoint"],
        jwks_uri=metadata_dict["jwks_uri"],
        registration_endpoint=metadata_dict.get("registration_endpoint"),
        introspection_endpoint=metadata_dict.get("introspection_endpoint"),
        revocation_endpoint=metadata_dict.get("revocation_endpoint"),
        end_session_endpoint=metadata_dict.get("end_session_endpoint"),
        check_session_iframe=metadata_dict.get("check_session_iframe"),
        device_authorization_endpoint=metadata_dict.get("device_authorization_endpoint"),
    )

    # Parse capabilities
    capabilities = set()

    # Check for standard capabilities
    if "authorization_code" in metadata_dict.get("grant_types_supported", []):
        capabilities.add(OIDCCapability.AUTHORIZATION_CODE_FLOW)
    if "implicit" in metadata_dict.get("grant_types_supported", []):
        capabilities.add(OIDCCapability.IMPLICIT_FLOW)
    if "client_credentials" in metadata_dict.get("grant_types_supported", []):
        capabilities.add(OIDCCapability.CLIENT_CREDENTIALS_FLOW)

    # Check for PKCE support
    if metadata_dict.get("code_challenge_methods_supported"):
        capabilities.add(OIDCCapability.PKCE)
        if "S256" in metadata_dict["code_challenge_methods_supported"]:
            capabilities.add(OIDCCapability.PKCE_S256)

    return OIDCProviderMetadata(
        issuer=metadata_dict["issuer"],
        endpoints=endpoints,
        response_types_supported=set(metadata_dict.get("response_types_supported", [])),
        response_modes_supported=set(metadata_dict.get("response_modes_supported", [])),
        grant_types_supported=set(metadata_dict.get("grant_types_supported", [])),
        subject_types_supported=set(metadata_dict.get("subject_types_supported", [])),
        id_token_signing_alg_values_supported=set(
            metadata_dict.get("id_token_signing_alg_values_supported", [])
        ),
        id_token_encryption_alg_values_supported=set(
            metadata_dict.get("id_token_encryption_alg_values_supported", [])
        ),
        userinfo_signing_alg_values_supported=set(
            metadata_dict.get("userinfo_signing_alg_values_supported", [])
        ),
        userinfo_encryption_alg_values_supported=set(
            metadata_dict.get("userinfo_encryption_alg_values_supported", [])
        ),
        token_endpoint_auth_methods_supported=set(
            metadata_dict.get("token_endpoint_auth_methods_supported", [])
        ),
        scopes_supported=set(metadata_dict.get("scopes_supported", [])),
        claims_supported=set(metadata_dict.get("claims_supported", [])),
        claim_types_supported=set(metadata_dict.get("claim_types_supported", [])),
        code_challenge_methods_supported=set(
            metadata_dict.get("code_challenge_methods_supported", [])
        ),
        capabilities=capabilities,
        custom_metadata={
            k: v
            for k, v in metadata_dict.items()
            if k
            not in [
                "issuer",
                "authorization_endpoint",
                "token_endpoint",
                "userinfo_endpoint",
                "jwks_uri",
                "response_types_supported",
                "response_modes_supported",
                "grant_types_supported",
                "subject_types_supported",
                "id_token_signing_alg_values_supported",
                "token_endpoint_auth_methods_supported",
                "scopes_supported",
                "claims_supported",
                "code_challenge_methods_supported",
                "claim_types_supported",
            ]
        },
    )
