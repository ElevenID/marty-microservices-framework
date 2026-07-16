"""
Session Management Domain Models

Domain models for session management functionality in the security module.
"""

from __future__ import annotations

import builtins
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class SessionState(Enum):
    """Session state enumeration."""

    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    INVALID = "invalid"


class SessionEventType(Enum):
    """Session event types for cleanup."""

    LOGOUT = "logout"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"
    ADMIN_TERMINATION = "admin_termination"
    PASSWORD_CHANGE = "password_change"


@dataclass
class SessionData:
    """Session data container."""

    session_id: str
    user_id: str
    created_at: datetime
    last_accessed: datetime
    expires_at: datetime
    state: SessionState = SessionState.ACTIVE
    ip_address: str | None = None
    user_agent: str | None = None
    attributes: builtins.dict[str, Any] = field(default_factory=dict)
    security_context: builtins.dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        user_id: str,
        timeout_minutes: int = 30,
        ip_address: str | None = None,
        user_agent: str | None = None,
        **attributes: Any,
    ) -> SessionData:
        """Create a new session."""
        now = datetime.utcnow()
        return cls(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            created_at=now,
            last_accessed=now,
            expires_at=now + timedelta(minutes=timeout_minutes),
            ip_address=ip_address,
            user_agent=user_agent,
            attributes=attributes,
        )

    @property
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.utcnow() >= self.expires_at or self.state != SessionState.ACTIVE

    @property
    def time_remaining(self) -> timedelta:
        """Get remaining time until expiration."""
        if self.is_expired:
            return timedelta(0)
        return self.expires_at - datetime.utcnow()

    @property
    def age(self) -> timedelta:
        """Get session age."""
        return datetime.utcnow() - self.created_at

    def extend(self, minutes: int) -> None:
        """Extend session expiration."""
        if self.state == SessionState.ACTIVE:
            self.expires_at = datetime.utcnow() + timedelta(minutes=minutes)
            self.last_accessed = datetime.utcnow()

    def touch(self) -> None:
        """Update last accessed time."""
        if self.state == SessionState.ACTIVE:
            self.last_accessed = datetime.utcnow()

    def terminate(self, reason: SessionEventType = SessionEventType.LOGOUT) -> None:
        """Terminate the session."""
        self.state = SessionState.TERMINATED
        self.attributes["termination_reason"] = reason.value
        self.attributes["terminated_at"] = datetime.utcnow().isoformat()

    def invalidate(self) -> None:
        """Mark session as invalid."""
        self.state = SessionState.INVALID

    def get_cache_key(self, prefix: str = "session") -> str:
        """Get cache key for this session."""
        return f"{prefix}:{self.session_id}"


@dataclass
class SessionCleanupEvent:
    """Event for session cleanup."""

    session_id: str
    user_id: str
    event_type: SessionEventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionLifecycle:
    """Session lifecycle configuration."""

    default_timeout_minutes: int = 30
    max_timeout_minutes: int = 480  # 8 hours
    idle_timeout_minutes: int = 15
    absolute_timeout_minutes: int = 720  # 12 hours
    extend_on_activity: bool = True
    require_ip_consistency: bool = False
    require_user_agent_consistency: bool = False

    def calculate_expiration(
        self,
        created_at: datetime,
        last_accessed: datetime,
        requested_timeout: int | None = None,
    ) -> datetime:
        """Calculate session expiration time."""
        now = datetime.utcnow()

        # Use requested timeout or default
        timeout_minutes = min(
            requested_timeout or self.default_timeout_minutes, self.max_timeout_minutes
        )

        # Calculate various expiration times
        idle_expiry = last_accessed + timedelta(minutes=self.idle_timeout_minutes)
        absolute_expiry = created_at + timedelta(minutes=self.absolute_timeout_minutes)
        timeout_expiry = now + timedelta(minutes=timeout_minutes)

        # Return the earliest expiration
        return min(idle_expiry, absolute_expiry, timeout_expiry)


@dataclass
class SessionMetrics:
    """Session management metrics."""

    total_sessions_created: int = 0
    active_sessions: int = 0
    expired_sessions: int = 0
    terminated_sessions: int = 0
    cleanup_events: builtins.dict[str, int] = field(default_factory=dict)
    average_session_duration_minutes: float = 0.0
    peak_concurrent_sessions: int = 0
    cleanup_operations: int = 0

    def record_session_created(self) -> None:
        """Record session creation."""
        self.total_sessions_created += 1
        self.active_sessions += 1
        self.peak_concurrent_sessions = max(self.peak_concurrent_sessions, self.active_sessions)

    def record_session_terminated(self, reason: SessionEventType) -> None:
        """Record session termination."""
        if self.active_sessions > 0:
            self.active_sessions -= 1
        self.terminated_sessions += 1
        self.cleanup_events[reason.value] = self.cleanup_events.get(reason.value, 0) + 1

    def record_session_expired(self) -> None:
        """Record session expiration."""
        if self.active_sessions > 0:
            self.active_sessions -= 1
        self.expired_sessions += 1

    def record_cleanup_operation(self) -> None:
        """Record cleanup operation."""
        self.cleanup_operations += 1


@dataclass
class SessionSecurityPolicy:
    """Session security policy."""

    require_secure_transport: bool = True
    enforce_same_origin: bool = True
    detect_session_hijacking: bool = True
    max_sessions_per_user: int = 5
    lock_on_security_violation: bool = True
    notification_on_new_session: bool = False
    log_all_session_events: bool = True

    def validate_session_request(
        self,
        session: SessionData,
        current_ip: str | None = None,
        current_user_agent: str | None = None,
    ) -> builtins.list[str]:
        """Validate session request and return violations."""
        violations = []

        if self.detect_session_hijacking:
            if session.ip_address and current_ip and session.ip_address != current_ip:
                violations.append("IP address mismatch detected")

            if (
                session.user_agent
                and current_user_agent
                and session.user_agent != current_user_agent
            ):
                violations.append("User agent mismatch detected")

        return violations
