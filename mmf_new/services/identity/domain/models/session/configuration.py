"""
Session configuration domain models.

This module contains configuration models for session management,
including security policies, timeout configurations, and session policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any

from mmf_new.core.domain.entity import ValueObject


class SessionStorageType(Enum):
    """Session storage backend types."""

    IN_MEMORY = "in_memory"
    REDIS = "redis"
    DATABASE = "database"
    DISTRIBUTED = "distributed"


class SecurityPolicy(Enum):
    """Session security policy levels."""

    STRICT = "strict"  # Strict IP and user agent validation
    STANDARD = "standard"  # Standard validation with some flexibility
    LENIENT = "lenient"  # Lenient validation for development


class SessionCleanupStrategy(Enum):
    """Session cleanup strategies."""

    IMMEDIATE = "immediate"  # Cleanup immediately on expiration
    BACKGROUND = "background"  # Background cleanup process
    ON_ACCESS = "on_access"  # Cleanup during access checks
    SCHEDULED = "scheduled"  # Scheduled cleanup intervals


@dataclass(frozen=True)
class SessionTimeoutPolicy(ValueObject):
    """Session timeout policy configuration."""

    # Base timeout settings
    idle_timeout: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    absolute_timeout: timedelta = field(default_factory=lambda: timedelta(hours=8))

    # Timeout behavior
    extend_on_activity: bool = True
    warn_before_expiry: bool = True
    warning_threshold: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    # Grace period for session extension
    extension_grace_period: timedelta = field(default_factory=lambda: timedelta(minutes=2))
    max_extensions: int = 5

    def __post_init__(self):
        """Validate timeout policy."""
        if self.idle_timeout.total_seconds() <= 0:
            raise ValueError("Idle timeout must be positive")

        if self.absolute_timeout.total_seconds() <= 0:
            raise ValueError("Absolute timeout must be positive")

        if self.idle_timeout >= self.absolute_timeout:
            raise ValueError("Idle timeout must be less than absolute timeout")

        if self.warning_threshold >= self.idle_timeout:
            raise ValueError("Warning threshold must be less than idle timeout")

        if self.extension_grace_period.total_seconds() < 0:
            raise ValueError("Extension grace period cannot be negative")

        if self.max_extensions < 0:
            raise ValueError("Max extensions cannot be negative")

    @property
    def idle_timeout_seconds(self) -> int:
        """Get idle timeout in seconds."""
        return int(self.idle_timeout.total_seconds())

    @property
    def absolute_timeout_seconds(self) -> int:
        """Get absolute timeout in seconds."""
        return int(self.absolute_timeout.total_seconds())

    @property
    def warning_threshold_seconds(self) -> int:
        """Get warning threshold in seconds."""
        return int(self.warning_threshold.total_seconds())


@dataclass(frozen=True)
class SessionSecurityPolicy(ValueObject):
    """Session security policy configuration."""

    # IP address validation
    validate_ip_address: bool = True
    allow_ip_changes: bool = False
    ip_change_detection: bool = True

    # User agent validation
    validate_user_agent: bool = True
    allow_user_agent_changes: bool = True
    user_agent_strict_match: bool = False

    # Session hijacking protection
    require_secure_connection: bool = True
    session_fingerprinting: bool = True
    detect_concurrent_sessions: bool = True
    max_concurrent_sessions: int = 3

    # Session rotation
    rotate_session_on_auth: bool = True
    rotate_session_on_privilege_change: bool = True
    rotation_interval: timedelta | None = None

    # Suspicious activity detection
    track_login_attempts: bool = True
    max_failed_attempts: int = 5
    lockout_duration: timedelta = field(default_factory=lambda: timedelta(minutes=15))

    # Geographic restrictions
    geo_restrictions_enabled: bool = False
    allowed_countries: set[str] = field(default_factory=set)
    blocked_countries: set[str] = field(default_factory=set)

    def __post_init__(self):
        """Validate security policy."""
        if self.max_concurrent_sessions < 1:
            raise ValueError("Max concurrent sessions must be at least 1")

        if self.max_failed_attempts < 1:
            raise ValueError("Max failed attempts must be at least 1")

        if self.lockout_duration.total_seconds() < 0:
            raise ValueError("Lockout duration cannot be negative")

        if self.rotation_interval and self.rotation_interval.total_seconds() <= 0:
            raise ValueError("Rotation interval must be positive")


@dataclass(frozen=True)
class SessionStorageConfiguration(ValueObject):
    """Session storage configuration."""

    storage_type: SessionStorageType = SessionStorageType.IN_MEMORY
    connection_string: str | None = None

    # Storage-specific settings
    key_prefix: str = "session:"
    serialization_format: str = "json"  # json, pickle, msgpack
    compression_enabled: bool = False

    # Performance settings
    connection_pool_size: int = 10
    connection_timeout_seconds: int = 5
    operation_timeout_seconds: int = 30

    # Persistence settings
    persistence_enabled: bool = True
    backup_enabled: bool = False
    backup_interval: timedelta = field(default_factory=lambda: timedelta(hours=1))

    def __post_init__(self):
        """Validate storage configuration."""
        if self.storage_type in [SessionStorageType.REDIS, SessionStorageType.DATABASE]:
            if not self.connection_string:
                raise ValueError(f"Connection string required for {self.storage_type.value}")

        if self.connection_pool_size < 1:
            raise ValueError("Connection pool size must be at least 1")

        if self.connection_timeout_seconds < 1:
            raise ValueError("Connection timeout must be at least 1 second")

        if self.operation_timeout_seconds < 1:
            raise ValueError("Operation timeout must be at least 1 second")


@dataclass(frozen=True)
class SessionCleanupConfiguration(ValueObject):
    """Session cleanup configuration."""

    strategy: SessionCleanupStrategy = SessionCleanupStrategy.BACKGROUND

    # Background cleanup settings
    cleanup_interval: timedelta = field(default_factory=lambda: timedelta(minutes=15))
    batch_size: int = 100
    max_cleanup_duration: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    # Retention settings
    keep_expired_sessions: timedelta = field(default_factory=lambda: timedelta(days=7))
    keep_invalidated_sessions: timedelta = field(default_factory=lambda: timedelta(days=30))
    archive_old_sessions: bool = False

    # Performance settings
    cleanup_during_peak_hours: bool = False
    peak_hours_start: int = 9  # 9 AM
    peak_hours_end: int = 17  # 5 PM

    def __post_init__(self):
        """Validate cleanup configuration."""
        if self.cleanup_interval.total_seconds() < 60:
            raise ValueError("Cleanup interval must be at least 1 minute")

        if self.batch_size < 1:
            raise ValueError("Batch size must be at least 1")

        if self.max_cleanup_duration.total_seconds() <= 0:
            raise ValueError("Max cleanup duration must be positive")

        if self.keep_expired_sessions.total_seconds() < 0:
            raise ValueError("Keep expired sessions duration cannot be negative")

        if self.keep_invalidated_sessions.total_seconds() < 0:
            raise ValueError("Keep invalidated sessions duration cannot be negative")

        if not (0 <= self.peak_hours_start <= 23):
            raise ValueError("Peak hours start must be between 0 and 23")

        if not (0 <= self.peak_hours_end <= 23):
            raise ValueError("Peak hours end must be between 0 and 23")


@dataclass(frozen=True)
class SessionConfiguration(ValueObject):
    """
    Complete session management configuration.

    This aggregates all session-related configuration including timeouts,
    security policies, storage, and cleanup settings.
    """

    # Core configuration
    timeout_policy: SessionTimeoutPolicy = field(default_factory=SessionTimeoutPolicy)
    security_policy: SessionSecurityPolicy = field(default_factory=SessionSecurityPolicy)
    storage_config: SessionStorageConfiguration = field(default_factory=SessionStorageConfiguration)
    cleanup_config: SessionCleanupConfiguration = field(default_factory=SessionCleanupConfiguration)

    # Feature flags
    enable_session_management: bool = True
    enable_session_analytics: bool = False
    enable_session_debugging: bool = False

    # Integration settings
    integrate_with_authentication: bool = True
    sync_with_user_roles: bool = True
    propagate_session_events: bool = True

    # Monitoring and alerting
    enable_session_monitoring: bool = True
    alert_on_suspicious_activity: bool = True
    session_metrics_enabled: bool = True

    # Development settings
    development_mode: bool = False
    allow_insecure_cookies: bool = False  # Only for development
    disable_csrf_protection: bool = False  # Only for development

    # Custom settings
    custom_session_attributes: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration compatibility."""
        # Warn about insecure development settings in production
        if not self.development_mode:
            if self.allow_insecure_cookies:
                raise ValueError("Insecure cookies not allowed in production mode")

            if self.disable_csrf_protection:
                raise ValueError("CSRF protection cannot be disabled in production mode")

        # Validate feature compatibility
        if not self.enable_session_management:
            if self.enable_session_analytics:
                raise ValueError("Session analytics requires session management to be enabled")

            if self.enable_session_monitoring:
                raise ValueError("Session monitoring requires session management to be enabled")

    @classmethod
    def create_development_config(cls) -> SessionConfiguration:
        """Create a development-friendly configuration."""
        return cls(
            development_mode=True,
            timeout_policy=SessionTimeoutPolicy(
                idle_timeout=timedelta(hours=8),  # Longer for development
                absolute_timeout=timedelta(hours=24),  # Much longer for development
                extend_on_activity=True,
                warn_before_expiry=False,  # No warnings in dev
            ),
            security_policy=SessionSecurityPolicy(
                validate_ip_address=False,  # More flexible for dev
                allow_ip_changes=True,
                validate_user_agent=False,
                require_secure_connection=False,  # Allow HTTP in dev
                max_concurrent_sessions=10,  # More sessions for testing
                track_login_attempts=False,  # No lockouts in dev
            ),
            storage_config=SessionStorageConfiguration(
                storage_type=SessionStorageType.IN_MEMORY,
            ),
            cleanup_config=SessionCleanupConfiguration(
                cleanup_interval=timedelta(hours=1),  # Less frequent cleanup
                keep_expired_sessions=timedelta(hours=1),
            ),
            enable_session_debugging=True,
            allow_insecure_cookies=True,
        )

    @classmethod
    def create_production_config(cls) -> SessionConfiguration:
        """Create a production-ready configuration."""
        return cls(
            development_mode=False,
            timeout_policy=SessionTimeoutPolicy(
                idle_timeout=timedelta(minutes=30),
                absolute_timeout=timedelta(hours=8),
                extend_on_activity=True,
                warn_before_expiry=True,
                warning_threshold=timedelta(minutes=5),
            ),
            security_policy=SessionSecurityPolicy(
                validate_ip_address=True,
                allow_ip_changes=False,
                validate_user_agent=True,
                require_secure_connection=True,
                session_fingerprinting=True,
                detect_concurrent_sessions=True,
                max_concurrent_sessions=3,
                rotate_session_on_auth=True,
                track_login_attempts=True,
                max_failed_attempts=5,
                lockout_duration=timedelta(minutes=15),
            ),
            storage_config=SessionStorageConfiguration(
                storage_type=SessionStorageType.REDIS,
                persistence_enabled=True,
                backup_enabled=True,
            ),
            cleanup_config=SessionCleanupConfiguration(
                strategy=SessionCleanupStrategy.BACKGROUND,
                cleanup_interval=timedelta(minutes=15),
                keep_expired_sessions=timedelta(days=7),
                archive_old_sessions=True,
            ),
            enable_session_monitoring=True,
            alert_on_suspicious_activity=True,
            session_metrics_enabled=True,
        )

    @classmethod
    def create_high_security_config(cls) -> SessionConfiguration:
        """Create a high-security configuration."""
        return cls(
            development_mode=False,
            timeout_policy=SessionTimeoutPolicy(
                idle_timeout=timedelta(minutes=15),  # Shorter timeouts
                absolute_timeout=timedelta(hours=4),
                extend_on_activity=True,
                warn_before_expiry=True,
                warning_threshold=timedelta(minutes=2),
                max_extensions=3,  # Limited extensions
            ),
            security_policy=SessionSecurityPolicy(
                validate_ip_address=True,
                allow_ip_changes=False,  # No IP changes
                ip_change_detection=True,
                validate_user_agent=True,
                user_agent_strict_match=True,  # Strict matching
                require_secure_connection=True,
                session_fingerprinting=True,
                detect_concurrent_sessions=True,
                max_concurrent_sessions=1,  # Single session only
                rotate_session_on_auth=True,
                rotate_session_on_privilege_change=True,
                rotation_interval=timedelta(hours=1),  # Regular rotation
                track_login_attempts=True,
                max_failed_attempts=3,  # Lower threshold
                lockout_duration=timedelta(hours=1),  # Longer lockout
            ),
            storage_config=SessionStorageConfiguration(
                storage_type=SessionStorageType.DATABASE,
                persistence_enabled=True,
                backup_enabled=True,
                compression_enabled=True,
            ),
            cleanup_config=SessionCleanupConfiguration(
                strategy=SessionCleanupStrategy.IMMEDIATE,
                keep_expired_sessions=timedelta(days=1),  # Short retention
                keep_invalidated_sessions=timedelta(days=7),
                archive_old_sessions=True,
            ),
            enable_session_monitoring=True,
            alert_on_suspicious_activity=True,
            session_metrics_enabled=True,
        )


# Utility functions for common configuration tasks


def create_timeout_policy(
    idle_minutes: int = 30, absolute_hours: int = 8, extend_on_activity: bool = True
) -> SessionTimeoutPolicy:
    """Create a timeout policy with common settings."""
    return SessionTimeoutPolicy(
        idle_timeout=timedelta(minutes=idle_minutes),
        absolute_timeout=timedelta(hours=absolute_hours),
        extend_on_activity=extend_on_activity,
    )


def create_security_policy(
    security_level: SecurityPolicy = SecurityPolicy.STANDARD,
) -> SessionSecurityPolicy:
    """Create a security policy based on security level."""
    if security_level == SecurityPolicy.STRICT:
        return SessionSecurityPolicy(
            validate_ip_address=True,
            allow_ip_changes=False,
            validate_user_agent=True,
            user_agent_strict_match=True,
            require_secure_connection=True,
            session_fingerprinting=True,
            max_concurrent_sessions=1,
            rotate_session_on_auth=True,
        )
    elif security_level == SecurityPolicy.LENIENT:
        return SessionSecurityPolicy(
            validate_ip_address=False,
            allow_ip_changes=True,
            validate_user_agent=False,
            require_secure_connection=False,
            session_fingerprinting=False,
            max_concurrent_sessions=10,
            track_login_attempts=False,
        )
    else:  # STANDARD
        return SessionSecurityPolicy()
