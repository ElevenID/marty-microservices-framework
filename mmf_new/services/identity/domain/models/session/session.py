"""
Core Session domain models.

This module contains the primary session models including session state,
security context, and lifecycle management functionality.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from mmf_new.core.domain.entity import ValueObject


class SessionStatus(Enum):
    """Session lifecycle status."""

    ACTIVE = "active"  # Session is active and valid
    EXPIRED = "expired"  # Session has expired due to timeout
    INVALIDATED = "invalidated"  # Session was explicitly invalidated
    TERMINATED = "terminated"  # Session was terminated by admin/security
    SUSPENDED = "suspended"  # Session is temporarily suspended


@dataclass(frozen=True)
class SessionTimeout(ValueObject):
    """Session timeout configuration."""

    idle_timeout_seconds: int = 1800  # 30 minutes
    absolute_timeout_seconds: int = 28800  # 8 hours
    extend_on_activity: bool = True

    def __post_init__(self):
        """Validate timeout configuration."""
        if self.idle_timeout_seconds <= 0:
            raise ValueError("Idle timeout must be positive")

        if self.absolute_timeout_seconds <= 0:
            raise ValueError("Absolute timeout must be positive")

        if self.idle_timeout_seconds > self.absolute_timeout_seconds:
            raise ValueError("Idle timeout cannot exceed absolute timeout")


@dataclass(frozen=True)
class SessionSecurityContext(ValueObject):
    """Security context for session validation."""

    ip_address: str
    user_agent: str | None = None
    secure_connection: bool = True
    client_fingerprint: str | None = None
    location_info: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate security context."""
        if not self.ip_address or not self.ip_address.strip():
            raise ValueError("IP address is required")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

    def matches(self, other: SessionSecurityContext, strict: bool = True) -> bool:
        """Check if security context matches another context."""
        if strict:
            # Strict matching requires exact IP and user agent
            return self.ip_address == other.ip_address and self.user_agent == other.user_agent
        else:
            # Lenient matching allows different user agents from same IP
            return self.ip_address == other.ip_address


@dataclass(frozen=True)
class SessionActivity(ValueObject):
    """Records session activity for audit and security."""

    action: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate activity record."""
        if not self.action or not self.action.strip():
            raise ValueError("Action is required")

        # Ensure timezone awareness
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))


@dataclass(frozen=True)
class SessionData(ValueObject):
    """Container for session-specific data."""

    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate session data."""
        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.updated_at.tzinfo is None:
            object.__setattr__(self, "updated_at", self.updated_at.replace(tzinfo=timezone.utc))

    def get_attribute(self, key: str, default: Any = None) -> Any:
        """Get a session attribute."""
        return self.attributes.get(key, default)

    def has_attribute(self, key: str) -> bool:
        """Check if session has an attribute."""
        return key in self.attributes

    def with_attribute(self, key: str, value: Any) -> SessionData:
        """Create new session data with additional attribute."""
        new_attributes = {**self.attributes, key: value}
        return SessionData(
            attributes=new_attributes,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
        )

    def without_attribute(self, key: str) -> SessionData:
        """Create new session data without an attribute."""
        new_attributes = {k: v for k, v in self.attributes.items() if k != key}
        return SessionData(
            attributes=new_attributes,
            created_at=self.created_at,
            updated_at=datetime.now(timezone.utc),
        )


@dataclass(frozen=True)
class Session(ValueObject):
    """
    Core Session domain model.

    Represents an authenticated user session with security context,
    timeout management, and activity tracking.
    """

    session_id: str
    user_id: str
    status: SessionStatus = SessionStatus.ACTIVE
    security_context: SessionSecurityContext | None = None
    timeout_config: SessionTimeout = field(default_factory=SessionTimeout)
    session_data: SessionData = field(default_factory=SessionData)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    invalidated_at: datetime | None = None

    # Activity tracking
    activity_log: list[SessionActivity] = field(default_factory=list)

    # Integration with authentication system
    auth_method: str | None = None
    mfa_completed: bool = False
    roles: set[str] = field(default_factory=set)
    permissions: set[str] = field(default_factory=set)

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate and initialize session."""
        if not self.session_id or not self.session_id.strip():
            raise ValueError("Session ID cannot be empty")

        if not self.user_id or not self.user_id.strip():
            raise ValueError("User ID cannot be empty")

        # Ensure timezone awareness for all timestamps
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.last_accessed_at.tzinfo is None:
            object.__setattr__(
                self, "last_accessed_at", self.last_accessed_at.replace(tzinfo=timezone.utc)
            )

        if self.expires_at and self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=timezone.utc))

        if self.invalidated_at and self.invalidated_at.tzinfo is None:
            object.__setattr__(
                self, "invalidated_at", self.invalidated_at.replace(tzinfo=timezone.utc)
            )

        # Set initial expiration if not provided
        if self.expires_at is None and self.status == SessionStatus.ACTIVE:
            expires_at = self.created_at + timedelta(
                seconds=self.timeout_config.idle_timeout_seconds
            )
            object.__setattr__(self, "expires_at", expires_at)

    @classmethod
    def create_new(
        cls,
        user_id: str,
        security_context: SessionSecurityContext,
        timeout_config: SessionTimeout | None = None,
        auth_method: str | None = None,
        roles: set[str] | None = None,
        permissions: set[str] | None = None,
        **kwargs,
    ) -> Session:
        """Create a new session."""
        session_id = generate_session_id()
        now = datetime.now(timezone.utc)

        timeout = timeout_config or SessionTimeout()
        expires_at = now + timedelta(seconds=timeout.idle_timeout_seconds)

        # Initial activity
        initial_activity = SessionActivity(
            action="session_created",
            timestamp=now,
            ip_address=security_context.ip_address,
            user_agent=security_context.user_agent,
        )

        return cls(
            session_id=session_id,
            user_id=user_id,
            security_context=security_context,
            timeout_config=timeout,
            created_at=now,
            last_accessed_at=now,
            expires_at=expires_at,
            activity_log=[initial_activity],
            auth_method=auth_method,
            roles=roles or set(),
            permissions=permissions or set(),
            **kwargs,
        )

    def is_active(self) -> bool:
        """Check if session is active and valid."""
        return (
            self.status == SessionStatus.ACTIVE
            and not self.is_expired()
            and self.invalidated_at is None
        )

    def is_expired(self) -> bool:
        """Check if session has expired."""
        if self.expires_at is None:
            return False

        now = datetime.now(timezone.utc)
        return now >= self.expires_at

    def is_absolute_timeout_exceeded(self) -> bool:
        """Check if absolute timeout has been exceeded."""
        now = datetime.now(timezone.utc)
        absolute_expiry = self.created_at + timedelta(
            seconds=self.timeout_config.absolute_timeout_seconds
        )
        return now >= absolute_expiry

    def access(
        self, security_context: SessionSecurityContext | None = None, action: str = "accessed"
    ) -> Session:
        """Record session access and extend timeout if configured."""
        if not self.is_active():
            raise ValueError("Cannot access inactive session")

        # Validate security context if provided
        if security_context and self.security_context:
            if not self.security_context.matches(security_context, strict=False):
                raise ValueError("Security context mismatch")

        now = datetime.now(timezone.utc)

        # Check absolute timeout
        if self.is_absolute_timeout_exceeded():
            return self._replace(status=SessionStatus.EXPIRED, invalidated_at=now)

        # Extend timeout if configured
        new_expires_at = self.expires_at
        if self.timeout_config.extend_on_activity:
            new_expires_at = now + timedelta(seconds=self.timeout_config.idle_timeout_seconds)
            # Don't extend beyond absolute timeout
            absolute_expiry = self.created_at + timedelta(
                seconds=self.timeout_config.absolute_timeout_seconds
            )
            if new_expires_at > absolute_expiry:
                new_expires_at = absolute_expiry

        # Record activity
        activity = SessionActivity(
            action=action,
            timestamp=now,
            ip_address=security_context.ip_address if security_context else None,
            user_agent=security_context.user_agent if security_context else None,
        )

        new_activity_log = list(self.activity_log)
        new_activity_log.append(activity)

        return self._replace(
            last_accessed_at=now, expires_at=new_expires_at, activity_log=new_activity_log
        )

    def invalidate(self, reason: str = "manual_invalidation") -> Session:
        """Invalidate the session."""
        now = datetime.now(timezone.utc)

        activity = SessionActivity(
            action="session_invalidated", timestamp=now, metadata={"reason": reason}
        )

        new_activity_log = list(self.activity_log)
        new_activity_log.append(activity)

        return self._replace(
            status=SessionStatus.INVALIDATED, invalidated_at=now, activity_log=new_activity_log
        )

    def terminate(self, reason: str = "security_termination") -> Session:
        """Terminate the session for security reasons."""
        now = datetime.now(timezone.utc)

        activity = SessionActivity(
            action="session_terminated", timestamp=now, metadata={"reason": reason}
        )

        new_activity_log = list(self.activity_log)
        new_activity_log.append(activity)

        return self._replace(
            status=SessionStatus.TERMINATED, invalidated_at=now, activity_log=new_activity_log
        )

    def set_data(self, key: str, value: Any) -> Session:
        """Set session data attribute."""
        new_session_data = self.session_data.with_attribute(key, value)
        return self._replace(session_data=new_session_data)

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get session data attribute."""
        return self.session_data.get_attribute(key, default)

    def remove_data(self, key: str) -> Session:
        """Remove session data attribute."""
        new_session_data = self.session_data.without_attribute(key)
        return self._replace(session_data=new_session_data)

    def has_role(self, role: str) -> bool:
        """Check if session has a specific role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if session has a specific permission."""
        return permission in self.permissions

    def add_role(self, role: str) -> Session:
        """Add a role to the session."""
        new_roles = {*self.roles, role}
        return self._replace(roles=new_roles)

    def add_permission(self, permission: str) -> Session:
        """Add a permission to the session."""
        new_permissions = {*self.permissions, permission}
        return self._replace(permissions=new_permissions)

    def remove_role(self, role: str) -> Session:
        """Remove a role from the session."""
        new_roles = self.roles - {role}
        return self._replace(roles=new_roles)

    def remove_permission(self, permission: str) -> Session:
        """Remove a permission from the session."""
        new_permissions = self.permissions - {permission}
        return self._replace(permissions=new_permissions)

    def get_recent_activity(self, limit: int = 10) -> list[SessionActivity]:
        """Get recent session activity."""
        return sorted(self.activity_log, key=lambda a: a.timestamp, reverse=True)[:limit]

    def _replace(self, **changes) -> Session:
        """Create a new session with specified changes."""
        kwargs = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status,
            "security_context": self.security_context,
            "timeout_config": self.timeout_config,
            "session_data": self.session_data,
            "created_at": self.created_at,
            "last_accessed_at": self.last_accessed_at,
            "expires_at": self.expires_at,
            "invalidated_at": self.invalidated_at,
            "activity_log": self.activity_log,
            "auth_method": self.auth_method,
            "mfa_completed": self.mfa_completed,
            "roles": self.roles,
            "permissions": self.permissions,
            "metadata": self.metadata,
        }
        kwargs.update(changes)
        return Session(**kwargs)


def generate_session_id(length: int = 32) -> str:
    """Generate a secure session ID."""
    return secrets.token_urlsafe(length)


def generate_session_token(length: int = 64) -> str:
    """Generate a secure session token for external references."""
    return secrets.token_urlsafe(length)
