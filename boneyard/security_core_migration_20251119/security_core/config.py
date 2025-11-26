"""
Security configuration for the enterprise security framework.
"""

import builtins
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SecurityLevel(Enum):
    """Security levels for different environments."""

    LOW = "low"  # Development
    MEDIUM = "medium"  # Staging
    HIGH = "high"  # Production
    CRITICAL = "critical"  # Highly sensitive production


@dataclass
class JWTConfig:
    """JWT authentication configuration."""

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    issuer: str | None = None
    audience: str | None = None

    def __post_init__(self):
        if not self.secret_key:
            raise ValueError("JWT secret key is required")


@dataclass
class MTLSConfig:
    """Mutual TLS configuration."""

    ca_cert_path: str | None = None
    cert_path: str | None = None
    key_path: str | None = None
    verify_client_cert: bool = True
    allowed_issuers: builtins.list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.verify_client_cert and not self.ca_cert_path:
            raise ValueError("CA certificate path required when client verification enabled")


@dataclass
class APIKeyConfig:
    """API Key authentication configuration."""

    header_name: str = "X-API-Key"
    query_param_name: str = "api_key"
    allow_header: bool = True
    allow_query_param: bool = False
    valid_keys: builtins.list[str] = field(default_factory=list)
    key_sources: builtins.list[str] = field(default_factory=list)  # URLs, files, databases


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    enabled: bool = True
    default_rate: str = "100/minute"  # Format: "count/period"
    redis_url: str | None = None
    use_memory_backend: bool = True
    key_prefix: str = "rate_limit"
    per_endpoint_limits: builtins.dict[str, str] = field(default_factory=dict)
    per_user_limits: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class SecurityConfig:
    """Comprehensive security configuration."""

    # General settings
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    service_name: str = "microservice"

    # Authentication settings
    jwt_config: JWTConfig | None = None
    mtls_config: MTLSConfig | None = None
    api_key_config: APIKeyConfig | None = None

    # Rate limiting
    rate_limit_config: RateLimitConfig = field(default_factory=RateLimitConfig)

    # Security headers
    security_headers: builtins.dict[str, str] = field(
        default_factory=lambda: {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }
    )

    # CORS settings
    cors_origins: builtins.list[str] = field(default_factory=lambda: ["*"])
    cors_methods: builtins.list[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"]
    )
    cors_headers: builtins.list[str] = field(default_factory=lambda: ["*"])
    cors_credentials: bool = True

    # Session settings
    session_timeout_minutes: int = 60
    max_concurrent_sessions: int = 5

    # Audit settings
    audit_enabled: bool = True
    audit_all_requests: bool = False
    audit_failed_requests: bool = True

    # Feature flags
    enable_mtls: bool = False
    enable_jwt: bool = True
    enable_api_keys: bool = False
    enable_rate_limiting: bool = True
    enable_request_logging: bool = True

    @classmethod
    def from_environment(cls, service_name: str) -> "SecurityConfig":
        """Create security config from environment variables."""

        # Determine security level
        security_level_str = os.getenv("SECURITY_LEVEL", "medium").lower()
        security_level = SecurityLevel(security_level_str)

        config = cls(
            security_level=security_level,
            service_name=service_name,
        )

        # JWT configuration
        jwt_secret = os.getenv("JWT_SECRET_KEY")
        if jwt_secret:
            config.jwt_config = JWTConfig(
                secret_key=jwt_secret,
                algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
                access_token_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE", "30")),
                refresh_token_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE", "7")),
                issuer=os.getenv("JWT_ISSUER"),
                audience=os.getenv("JWT_AUDIENCE"),
            )
            config.enable_jwt = True

        # mTLS configuration
        ca_cert_path = os.getenv("MTLS_CA_CERT_PATH")
        if ca_cert_path:
            config.mtls_config = MTLSConfig(
                ca_cert_path=ca_cert_path,
                cert_path=os.getenv("MTLS_CERT_PATH"),
                key_path=os.getenv("MTLS_KEY_PATH"),
                verify_client_cert=os.getenv("MTLS_VERIFY_CLIENT", "true").lower() == "true",
            )
            config.enable_mtls = True

        # API Key configuration
        api_keys = os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []
        if api_keys:
            config.api_key_config = APIKeyConfig(
                valid_keys=api_keys,
                header_name=os.getenv("API_KEY_HEADER", "X-API-Key"),
                allow_header=os.getenv("API_KEY_ALLOW_HEADER", "true").lower() == "true",
                allow_query_param=os.getenv("API_KEY_ALLOW_QUERY", "false").lower() == "true",
            )
            config.enable_api_keys = True

        # Rate limiting configuration
        redis_url = os.getenv("REDIS_URL")
        config.rate_limit_config = RateLimitConfig(
            enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            default_rate=os.getenv("RATE_LIMIT_DEFAULT", "100/minute"),
            redis_url=redis_url,
            use_memory_backend=redis_url is None,
        )

        # Feature flags from environment
        config.enable_rate_limiting = os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true"
        config.enable_request_logging = (
            os.getenv("ENABLE_REQUEST_LOGGING", "true").lower() == "true"
        )
        config.audit_enabled = os.getenv("AUDIT_ENABLED", "true").lower() == "true"

        return config

    def is_production_level(self) -> bool:
        """Check if security level is production or higher."""
        return self.security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]

    def requires_mtls(self) -> bool:
        """Check if mTLS is required based on security level."""
        return self.security_level == SecurityLevel.CRITICAL or self.enable_mtls

    def get_cors_config(self) -> builtins.dict[str, Any]:
        """Get CORS configuration for FastAPI."""
        return {
            "allow_origins": self.cors_origins,
            "allow_credentials": self.cors_credentials,
            "allow_methods": self.cors_methods,
            "allow_headers": self.cors_headers,
        }
