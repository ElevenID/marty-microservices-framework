"""
Authentication providers for the enterprise security framework.
"""

import builtins
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from ..security_core.config import SecurityConfig
from ..security_core.exceptions import CertificateValidationError

logger = logging.getLogger(__name__)


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user."""

    user_id: str
    username: str | None = None
    email: str | None = None
    roles: builtins.list[str] = field(default_factory=list)
    permissions: builtins.list[str] = field(default_factory=list)
    session_id: str | None = None
    auth_method: str | None = None
    expires_at: datetime | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Fields are now properly initialized with default_factory
        pass

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def is_expired(self) -> bool:
        """Check if the authentication has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class AuthenticationResult:
    """Result of an authentication attempt."""

    success: bool
    user: AuthenticatedUser | None = None
    error: str | None = None
    error_code: str | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Field is now properly initialized with default_factory
        pass


class BaseAuthenticator(ABC):
    """Base class for authentication providers."""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.service_name = config.service_name

    @abstractmethod
    async def authenticate(self, credentials: builtins.dict[str, Any]) -> AuthenticationResult:
        """Authenticate a user with provided credentials."""

    @abstractmethod
    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate an authentication token."""


class JWTAuthenticator(BaseAuthenticator):
    """JWT token authentication provider."""

    def __init__(self, config: SecurityConfig):
        super().__init__(config)
        if not config.jwt_config:
            raise ValueError("JWT configuration is required")
        self.jwt_config = config.jwt_config

    async def authenticate(self, credentials: builtins.dict[str, Any]) -> AuthenticationResult:
        """Authenticate with username/password and return JWT."""
        # This would typically validate against a user store
        # For now, we'll implement a basic validation
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            return AuthenticationResult(
                success=False,
                error="Username and password required",
                error_code="MISSING_CREDENTIALS",
            )

        # Here you would validate against your user store
        # For demo purposes, we'll create a token for any valid input
        user = AuthenticatedUser(
            user_id=username,
            username=username,
            auth_method="jwt",
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=self.jwt_config.access_token_expire_minutes),
        )

        token = self._create_token(user)

        return AuthenticationResult(success=True, user=user, metadata={"access_token": token})

    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate a JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.jwt_config.secret_key,
                algorithms=[self.jwt_config.algorithm],
                issuer=self.jwt_config.issuer,
                audience=self.jwt_config.audience,
            )

            user = AuthenticatedUser(
                user_id=payload.get("sub"),
                username=payload.get("username"),
                email=payload.get("email"),
                roles=payload.get("roles", []),
                permissions=payload.get("permissions", []),
                auth_method="jwt",
                expires_at=datetime.fromtimestamp(payload.get("exp", 0), timezone.utc),
                metadata=payload.get("metadata", {}),
            )

            if user.is_expired():
                return AuthenticationResult(
                    success=False, error="Token has expired", error_code="TOKEN_EXPIRED"
                )

            return AuthenticationResult(success=True, user=user)

        except jwt.ExpiredSignatureError:
            return AuthenticationResult(
                success=False, error="Token has expired", error_code="TOKEN_EXPIRED"
            )
        except jwt.InvalidTokenError as e:
            return AuthenticationResult(
                success=False,
                error=f"Invalid token: {e!s}",
                error_code="INVALID_TOKEN",
            )

    def _create_token(self, user: AuthenticatedUser) -> str:
        """Create a JWT token for the user."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user.user_id,
            "username": user.username,
            "email": user.email,
            "roles": user.roles,
            "permissions": user.permissions,
            "iat": now,
            "exp": now + timedelta(minutes=self.jwt_config.access_token_expire_minutes),
            "iss": self.jwt_config.issuer,
            "aud": self.jwt_config.audience,
            "metadata": user.metadata,
        }

        return jwt.encode(payload, self.jwt_config.secret_key, algorithm=self.jwt_config.algorithm)


class APIKeyAuthenticator(BaseAuthenticator):
    """API Key authentication provider."""

    def __init__(self, config: SecurityConfig):
        super().__init__(config)
        if not config.api_key_config:
            raise ValueError("API Key configuration is required")
        self.api_key_config = config.api_key_config
        self._api_keys = set(self.api_key_config.valid_keys)

    async def authenticate(self, credentials: builtins.dict[str, Any]) -> AuthenticationResult:
        """Authenticate with API key."""
        api_key = credentials.get("api_key")

        if not api_key:
            return AuthenticationResult(
                success=False, error="API key required", error_code="MISSING_API_KEY"
            )

        return await self.validate_token(api_key)

    async def validate_token(self, token: str) -> AuthenticationResult:
        """Validate an API key."""
        if not token:
            return AuthenticationResult(
                success=False, error="API key required", error_code="MISSING_API_KEY"
            )

        # Hash the key for comparison (in production, store hashed keys)
        key_hash = hashlib.sha256(token.encode()).hexdigest()

        if token in self._api_keys:
            user = AuthenticatedUser(
                user_id=f"api_key_{key_hash[:8]}",
                auth_method="api_key",
                roles=["api_user"],
                permissions=["api_access"],
            )

            return AuthenticationResult(success=True, user=user)

        return AuthenticationResult(
            success=False, error="Invalid API key", error_code="INVALID_API_KEY"
        )

    def extract_api_key(
        self, headers: builtins.dict[str, str], query_params: builtins.dict[str, str]
    ) -> str | None:
        """Extract API key from headers or query parameters."""
        if self.api_key_config.allow_header:
            api_key = headers.get(self.api_key_config.header_name.lower())
            if api_key:
                return api_key

        if self.api_key_config.allow_query_param:
            return query_params.get(self.api_key_config.query_param_name)

        return None


class MTLSAuthenticator(BaseAuthenticator):
    """Mutual TLS authentication provider."""

    def __init__(self, config: SecurityConfig):
        super().__init__(config)
        if not config.mtls_config:
            raise ValueError("mTLS configuration is required")
        self.mtls_config = config.mtls_config
        self._ca_cert = None
        if self.mtls_config.ca_cert_path:
            self._load_ca_certificate()

    def _load_ca_certificate(self):
        """Load the CA certificate for client verification."""
        try:
            ca_cert_path = self.mtls_config.ca_cert_path
            if not ca_cert_path:
                raise ValueError("CA certificate path is required")

            with open(ca_cert_path, "rb") as cert_file:
                self._ca_cert = x509.load_pem_x509_certificate(cert_file.read(), default_backend())
        except Exception as e:
            logger.error(f"Failed to load CA certificate: {e}")
            raise CertificateValidationError(f"Failed to load CA certificate: {e}")

    async def authenticate(self, credentials: builtins.dict[str, Any]) -> AuthenticationResult:
        """Authenticate with client certificate."""
        cert_der = credentials.get("client_cert")

        if not cert_der:
            return AuthenticationResult(
                success=False,
                error="Client certificate required",
                error_code="MISSING_CLIENT_CERT",
            )

        return await self.validate_certificate(cert_der)

    async def validate_token(self, token: str) -> AuthenticationResult:
        """For mTLS, the 'token' is the certificate in PEM format."""
        try:
            cert = x509.load_pem_x509_certificate(token.encode(), default_backend())
            return await self.validate_certificate(cert)
        except Exception as e:
            return AuthenticationResult(
                success=False,
                error=f"Invalid certificate format: {e}",
                error_code="INVALID_CERT_FORMAT",
            )

    async def validate_certificate(self, cert) -> AuthenticationResult:
        """Validate a client certificate."""
        try:
            # Check if certificate is expired
            now = datetime.now(timezone.utc)
            if cert.not_valid_after.replace(tzinfo=timezone.utc) < now:
                return AuthenticationResult(
                    success=False,
                    error="Certificate has expired",
                    error_code="CERT_EXPIRED",
                )

            if cert.not_valid_before.replace(tzinfo=timezone.utc) > now:
                return AuthenticationResult(
                    success=False,
                    error="Certificate not yet valid",
                    error_code="CERT_NOT_YET_VALID",
                )

            # Extract subject information
            subject = cert.subject
            common_name = None
            email = None

            for attribute in subject:
                if attribute.oid._name == "commonName":
                    common_name = attribute.value
                elif attribute.oid._name == "emailAddress":
                    email = attribute.value

            # Verify issuer if configured
            if self.mtls_config.allowed_issuers:
                issuer_name = cert.issuer.rfc4514_string()
                if not any(allowed in issuer_name for allowed in self.mtls_config.allowed_issuers):
                    return AuthenticationResult(
                        success=False,
                        error="Certificate issuer not allowed",
                        error_code="ISSUER_NOT_ALLOWED",
                    )

            user = AuthenticatedUser(
                user_id=common_name or "mtls_user",
                username=common_name,
                email=email,
                auth_method="mtls",
                roles=["mtls_user"],
                permissions=["secure_access"],
                expires_at=cert.not_valid_after.replace(tzinfo=timezone.utc),
            )

            return AuthenticationResult(success=True, user=user)

        except Exception as e:
            logger.error(f"Certificate validation error: {e}")
            return AuthenticationResult(
                success=False,
                error=f"Certificate validation failed: {e}",
                error_code="CERT_VALIDATION_FAILED",
            )
