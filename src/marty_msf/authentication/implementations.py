"""
Authentication Implementations

Concrete implementations of authentication providers.
"""

import builtins
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from ..security_core.api import AuthenticatedUser, AuthenticationResult, IAuthenticator
from ..security_core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class BasicAuthenticator(IAuthenticator):
    """Basic username/password authenticator."""

    def __init__(self, user_store: builtins.dict[str, builtins.dict[str, Any]] | None = None):
        self.user_store = user_store or {}

    def authenticate(self, credentials: builtins.dict[str, Any]) -> AuthenticationResult:
        """Authenticate with username/password."""
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            return AuthenticationResult(
                success=False,
                error="Username and password required"
            )

        user_data = self.user_store.get(username)
        if not user_data:
            return AuthenticationResult(
                success=False,
                error="Invalid credentials"
            )

        # Simple password hash check (in real implementation, use proper hashing)
        stored_password = user_data.get("password")
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        if stored_password != password_hash:
            return AuthenticationResult(
                success=False,
                error="Invalid credentials"
            )

        user = AuthenticatedUser(
            user_id=user_data["id"],
            username=username,
            email=user_data.get("email"),
            roles=user_data.get("roles", []),
            auth_method="basic"
        )

        return AuthenticationResult(
            success=True,
            user=user,
            metadata={"auth_method": "basic"}
        )

    def validate_token(self, token: str) -> AuthenticationResult:
        """Basic authenticator doesn't use tokens."""
        return AuthenticationResult(
            success=False,
            error="Token validation not supported for basic auth"
        )

    def refresh_token(self, refresh_token: str) -> AuthenticationResult:
        """Token refresh not supported."""
        return AuthenticationResult(
            success=False,
            error="Token refresh not supported"
        )


class JwtAuthenticator(IAuthenticator):
    """JWT-based authenticator."""

    def __init__(self, secret_key: str, algorithm: str = "HS256",
                 token_expiry_minutes: int = 30):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry_minutes = token_expiry_minutes

    def authenticate(self, credentials: builtins.dict[str, Any]) -> AuthenticationResult:
        """Authenticate and return JWT token."""
        # This would typically validate against a user store
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            return AuthenticationResult(
                success=False,
                error="Username and password required"
            )

        # Create JWT token
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.token_expiry_minutes)
        payload = {
            "sub": username,
            "iat": datetime.now(timezone.utc),
            "exp": expires_at
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

        user = AuthenticatedUser(
            user_id=username,
            username=username,
            roles=["user"],  # Would come from user store
            auth_method="jwt",
            expires_at=expires_at
        )

        return AuthenticationResult(
            success=True,
            user=user,
            metadata={"auth_method": "jwt", "access_token": token}
        )

    def validate_token(self, token: str) -> AuthenticationResult:
        """Validate JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            user = AuthenticatedUser(
                user_id=payload["sub"],
                username=payload["sub"],
                roles=["user"],  # Would come from user store
                auth_method="jwt",
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            )

            return AuthenticationResult(
                success=True,
                user=user,
                metadata={"auth_method": "jwt", "token_validated": True}
            )

        except jwt.ExpiredSignatureError:
            return AuthenticationResult(
                success=False,
                error="Token has expired"
            )
        except jwt.InvalidTokenError:
            return AuthenticationResult(
                success=False,
                error="Invalid token"
            )

    def refresh_token(self, refresh_token: str) -> AuthenticationResult:
        """Refresh JWT token."""
        # Simplified refresh logic
        return self.validate_token(refresh_token)


class TokenAuthenticator(IAuthenticator):
    """Token-based authenticator for API keys."""

    def __init__(self, token_store: builtins.dict[str, builtins.dict[str, Any]] | None = None):
        self.token_store = token_store or {}

    def authenticate(self, credentials: builtins.dict[str, Any]) -> AuthenticationResult:
        """Authenticate with API token."""
        token = credentials.get("token") or credentials.get("api_key")

        if not token:
            return AuthenticationResult(
                success=False,
                error="Token required"
            )

        return self.validate_token(token)

    def validate_token(self, token: str) -> AuthenticationResult:
        """Validate API token."""
        token_data = self.token_store.get(token)

        if not token_data:
            return AuthenticationResult(
                success=False,
                error="Invalid token"
            )

        if not token_data.get("active", True):
            return AuthenticationResult(
                success=False,
                error="Token is disabled"
            )

        user = AuthenticatedUser(
            user_id=token_data["user_id"],
            username=token_data.get("username"),
            roles=token_data.get("roles", []),
            auth_method="token"
        )

        return AuthenticationResult(
            success=True,
            user=user,
            metadata={"auth_method": "token"}
        )

    def refresh_token(self, refresh_token: str) -> AuthenticationResult:
        """Token authenticator doesn't support refresh."""
        return AuthenticationResult(
            success=False,
            error="Token refresh not supported"
        )


class MultiFactorAuthenticator(IAuthenticator):
    """Multi-factor authentication wrapper."""

    def __init__(self, primary_authenticator: IAuthenticator,
                 secondary_authenticator: IAuthenticator):
        self.primary_authenticator = primary_authenticator
        self.secondary_authenticator = secondary_authenticator

    def authenticate(self, credentials: builtins.dict[str, Any]) -> AuthenticationResult:
        """Authenticate with multiple factors."""
        # First factor
        primary_result = self.primary_authenticator.authenticate(credentials)
        if not primary_result.success:
            return primary_result

        # Second factor
        secondary_credentials = credentials.get("second_factor", {})
        secondary_result = self.secondary_authenticator.authenticate(secondary_credentials)

        if not secondary_result.success:
            return AuthenticationResult(
                success=False,
                error="Second factor authentication failed"
            )

        # Modify the user's auth method to indicate MFA
        if primary_result.user:
            primary_result.user.auth_method = "mfa"

        # Combine results
        return AuthenticationResult(
            success=True,
            user=primary_result.user,
            metadata={"auth_method": "mfa", "factors_used": 2}
        )

    def validate_token(self, token: str) -> AuthenticationResult:
        """Validate token using primary authenticator."""
        return self.primary_authenticator.validate_token(token)

    def refresh_token(self, refresh_token: str) -> AuthenticationResult:
        """Refresh token using primary authenticator."""
        if hasattr(self.primary_authenticator, 'refresh_token'):
            return self.primary_authenticator.refresh_token(refresh_token)
        return AuthenticationResult(
            success=False,
            error="Token refresh not supported"
        )


class APIKeyAuthenticator(IAuthenticator):
    """API Key authentication provider."""

    def __init__(self, valid_keys: list[str], header_name: str = "X-API-Key",
                 allow_query_param: bool = False, query_param_name: str = "api_key"):
        self.valid_keys = set(valid_keys)
        self.header_name = header_name
        self.allow_query_param = allow_query_param
        self.query_param_name = query_param_name

    def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate with API key."""
        api_key = credentials.get("api_key")

        if not api_key:
            return AuthenticationResult(
                success=False,
                error="API key required",
                error_code="MISSING_API_KEY"
            )

        return self.validate_token(api_key)

    def validate_token(self, token: str) -> AuthenticationResult:
        """Validate an API key."""
        if not token:
            return AuthenticationResult(
                success=False,
                error="API key required",
                error_code="MISSING_API_KEY"
            )

        # Hash the key for comparison (in production, store hashed keys)
        key_hash = hashlib.sha256(token.encode()).hexdigest()

        if token in self.valid_keys:
            user = AuthenticatedUser(
                user_id=f"api_key_{key_hash[:8]}",
                username=f"api_user_{key_hash[:8]}",
                roles=["api_user"],
                permissions=["api_access"],
                auth_method="api_key"
            )

            return AuthenticationResult(success=True, user=user)

        return AuthenticationResult(
            success=False,
            error="Invalid API key",
            error_code="INVALID_API_KEY"
        )

    def extract_api_key(self, headers: dict[str, str], query_params: dict[str, str]) -> str | None:
        """Extract API key from headers or query parameters."""
        # Check headers first
        api_key = headers.get(self.header_name.lower())
        if api_key:
            return api_key

        # Check query parameters if allowed
        if self.allow_query_param:
            return query_params.get(self.query_param_name)

        return None


class MTLSAuthenticator(IAuthenticator):
    """Mutual TLS authentication provider."""

    def __init__(self, ca_cert_path: str | None = None, allowed_issuers: list[str] | None = None):
        self.ca_cert_path = ca_cert_path
        self.allowed_issuers = allowed_issuers or []
        self._ca_cert = None
        if self.ca_cert_path:
            self._load_ca_certificate()

    def _load_ca_certificate(self):
        """Load the CA certificate for client verification."""
        try:
            if not self.ca_cert_path:
                raise ValueError("CA certificate path is required")

            with open(self.ca_cert_path, "rb") as cert_file:
                self._ca_cert = x509.load_pem_x509_certificate(cert_file.read(), default_backend())
        except Exception as e:
            logger.error("Failed to load CA certificate: %s", e)
            raise AuthenticationError(f"Failed to load CA certificate: {e}") from e

    def authenticate(self, credentials: dict[str, Any]) -> AuthenticationResult:
        """Authenticate with client certificate."""
        cert_data = credentials.get("client_cert")

        if not cert_data:
            return AuthenticationResult(
                success=False,
                error="Client certificate required",
                error_code="MISSING_CLIENT_CERT"
            )

        return self.validate_certificate(cert_data)

    def validate_token(self, token: str) -> AuthenticationResult:
        """For mTLS, the 'token' is the certificate in PEM format."""
        try:
            cert = x509.load_pem_x509_certificate(token.encode(), default_backend())
            return self.validate_certificate(cert)
        except (ValueError, TypeError) as e:
            return AuthenticationResult(
                success=False,
                error=f"Invalid certificate format: {e}",
                error_code="INVALID_CERT_FORMAT"
            )

    def validate_certificate(self, cert) -> AuthenticationResult:
        """Validate a client certificate."""
        try:
            # Check if certificate is expired
            now = datetime.now(timezone.utc)
            if cert.not_valid_after.replace(tzinfo=timezone.utc) < now:
                return AuthenticationResult(
                    success=False,
                    error="Certificate has expired",
                    error_code="CERT_EXPIRED"
                )

            if cert.not_valid_before.replace(tzinfo=timezone.utc) > now:
                return AuthenticationResult(
                    success=False,
                    error="Certificate not yet valid",
                    error_code="CERT_NOT_YET_VALID"
                )

            # Extract subject information
            subject = cert.subject
            common_name = None
            email = None

            for attribute in subject:
                # Use string comparison to avoid accessing protected member
                attr_name = str(attribute.oid)
                if "commonName" in attr_name or "2.5.4.3" in attr_name:
                    common_name = attribute.value
                elif "emailAddress" in attr_name or "1.2.840.113549.1.9.1" in attr_name:
                    email = attribute.value

            # Verify issuer if configured
            if self.allowed_issuers:
                issuer_name = cert.issuer.rfc4514_string()
                if not any(allowed in issuer_name for allowed in self.allowed_issuers):
                    return AuthenticationResult(
                        success=False,
                        error="Certificate issuer not allowed",
                        error_code="ISSUER_NOT_ALLOWED"
                    )

            user = AuthenticatedUser(
                user_id=common_name or "mtls_user",
                username=common_name or "mtls_user",
                email=email,
                roles=["mtls_user"],
                permissions=["secure_access"],
                auth_method="mtls",
                expires_at=cert.not_valid_after.replace(tzinfo=timezone.utc)
            )

            return AuthenticationResult(success=True, user=user)

        except (ValueError, TypeError, AttributeError) as e:
            logger.error("Certificate validation error: %s", e)
            return AuthenticationResult(
                success=False,
                error=f"Certificate validation failed: {e}",
                error_code="CERT_VALIDATION_FAILED"
            )
