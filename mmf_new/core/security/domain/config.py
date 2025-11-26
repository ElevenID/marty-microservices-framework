"""
Security Configuration

This module defines configuration models for the security module.
"""

from __future__ import annotations

import builtins
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
    # Dual-layer coordination
    istio_safety_multiplier: float = 2.0  # Istio limits = app limits * multiplier
    burst_size: int = 10  # Allow burst above steady rate
    sliding_window_size: int = 60  # Sliding window in seconds


@dataclass
class SessionConfig:
    """Session management configuration."""

    enabled: bool = True
    default_timeout_minutes: int = 30
    max_timeout_minutes: int = 480  # 8 hours
    cleanup_interval_minutes: int = 5
    redis_url: str | None = None
    use_memory_backend: bool = True
    key_prefix: str = "session"
    enable_event_driven_cleanup: bool = True
    session_cookie_name: str = "session_id"
    secure_cookies: bool = True
    same_site: str = "strict"  # strict, lax, none


@dataclass
class ServiceMeshConfig:
    """Service mesh configuration."""

    enabled: bool = False
    mesh_type: str = "istio"  # Only istio supported
    namespace: str = "default"
    istio_namespace: str = "istio-system"
    kubectl_cmd: str = "kubectl"
    # mTLS settings
    enforce_mtls: bool = True
    mtls_mode: str = "STRICT"  # STRICT, PERMISSIVE
    # Policy sync
    enable_policy_sync: bool = True
    policy_sync_interval_minutes: int = 10
    sync_on_policy_change: bool = True


@dataclass
class ThreatDetectionConfig:
    """Threat detection configuration."""

    enabled: bool = True
    # Event processing
    max_events_per_second: int = 10000
    event_retention_hours: int = 24
    redis_url: str | None = None
    use_memory_backend: bool = True

    # ML-based detection
    enable_ml_detection: bool = True
    anomaly_threshold: float = 0.7  # 0.0 to 1.0
    min_training_samples: int = 100
    model_update_interval_minutes: int = 60

    # Pattern-based detection
    enable_pattern_detection: bool = True
    sql_injection_detection: bool = True
    xss_detection: bool = True
    path_traversal_detection: bool = True
    command_injection_detection: bool = True

    # Behavioral analysis
    enable_behavioral_analysis: bool = True
    profile_update_interval_minutes: int = 30

    # Alerting
    alert_on_critical: bool = True
    alert_on_high: bool = True
    alert_webhook_url: str | None = None


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

    # Session management
    session_config: SessionConfig = field(default_factory=SessionConfig)

    # Service mesh
    service_mesh_config: ServiceMeshConfig = field(default_factory=ServiceMeshConfig)

    # Threat detection
    threat_detection_config: ThreatDetectionConfig = field(default_factory=ThreatDetectionConfig)

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

    # Feature flags
    enable_jwt: bool = False
    enable_mtls: bool = False
    enable_api_keys: bool = False
    enable_audit_logging: bool = True
    enable_threat_detection: bool = True
