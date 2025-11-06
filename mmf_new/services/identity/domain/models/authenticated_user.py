"""
Authenticated User domain model for the identity service.

This model represents an authenticated user within the system, containing
the essential information needed for authorization and audit purposes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AuthenticatedUser:
    """
    Domain model representing an authenticated user.

    This is a value object that encapsulates all the information
    about a user who has been successfully authenticated.
    """

    user_id: str
    username: str | None = None
    email: str | None = None
    roles: set[str] = field(default_factory=set)
    permissions: set[str] = field(default_factory=set)
    session_id: str | None = None
    auth_method: str | None = None
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate the authenticated user data."""
        # Validate required fields
        if not isinstance(self.user_id, str):
            raise TypeError("User ID must be a string")
        if not self.user_id.strip():
            raise ValueError("User ID cannot be empty")

        if not isinstance(self.username, str):
            raise TypeError("Username must be a string")
        if not self.username.strip():
            raise ValueError("Username cannot be empty")

        # Convert roles to set if it's a list
        if isinstance(self.roles, list):
            object.__setattr__(self, 'roles', set(self.roles))

        # Convert permissions to set if it's a list
        if isinstance(self.permissions, list):
            object.__setattr__(self, 'permissions', set(self.permissions))

        # Validate email format if provided
        if self.email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', self.email):
            raise ValueError("Invalid email format")

        # Ensure timezone awareness for datetime fields
        if self.expires_at and self.expires_at.tzinfo is None:
            object.__setattr__(self, 'expires_at', self.expires_at.replace(tzinfo=timezone.utc))

        if self.created_at.tzinfo is None:
            object.__setattr__(self, 'created_at', self.created_at.replace(tzinfo=timezone.utc))

    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions

    def has_any_role(self, roles: set[str]) -> bool:
        """Check if user has any of the specified roles."""
        return bool(self.roles.intersection(roles))

    def has_all_roles(self, roles: set[str]) -> bool:
        """Check if user has all of the specified roles."""
        return roles.issubset(self.roles)

    def has_any_permission(self, permissions: set[str]) -> bool:
        """Check if user has any of the specified permissions."""
        return bool(self.permissions.intersection(permissions))

    def has_all_permissions(self, permissions: set[str]) -> bool:
        """Check if user has all of the specified permissions."""
        return permissions.issubset(self.permissions)

    def is_expired(self) -> bool:
        """Check if the authentication has expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def time_until_expiry(self) -> float | None:
        """Get time in seconds until expiry, or None if no expiry set."""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.now(timezone.utc)
        return max(0.0, delta.total_seconds())

    def with_session(self, session_id: str) -> AuthenticatedUser:
        """Create a new instance with updated session ID."""
        return AuthenticatedUser(
            user_id=self.user_id,
            username=self.username,
            email=self.email,
            roles=self.roles,
            permissions=self.permissions,
            session_id=session_id,
            auth_method=self.auth_method,
            expires_at=self.expires_at,
            metadata=self.metadata,
            created_at=self.created_at
        )

    def with_expiry(self, expires_at: datetime) -> AuthenticatedUser:
        """Create a new instance with updated expiry time."""
        return AuthenticatedUser(
            user_id=self.user_id,
            username=self.username,
            email=self.email,
            roles=self.roles,
            permissions=self.permissions,
            session_id=self.session_id,
            auth_method=self.auth_method,
            expires_at=expires_at,
            metadata=self.metadata,
            created_at=self.created_at
        )

    def add_role(self, role: str) -> AuthenticatedUser:
        """Create a new instance with an additional role."""
        new_roles = self.roles.copy()
        new_roles.add(role)
        return AuthenticatedUser(
            user_id=self.user_id,
            username=self.username,
            email=self.email,
            roles=new_roles,
            permissions=self.permissions,
            session_id=self.session_id,
            auth_method=self.auth_method,
            expires_at=self.expires_at,
            metadata=self.metadata,
            created_at=self.created_at
        )

    def add_permission(self, permission: str) -> AuthenticatedUser:
        """Create a new instance with an additional permission."""
        new_permissions = self.permissions.copy()
        new_permissions.add(permission)
        return AuthenticatedUser(
            user_id=self.user_id,
            username=self.username,
            email=self.email,
            roles=self.roles,
            permissions=new_permissions,
            session_id=self.session_id,
            auth_method=self.auth_method,
            expires_at=self.expires_at,
            metadata=self.metadata,
            created_at=self.created_at
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'roles': list(self.roles),
            'permissions': list(self.permissions),
            'session_id': self.session_id,
            'auth_method': self.auth_method,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthenticatedUser:
        """Create instance from dictionary."""
        expires_at = None
        if data.get('expires_at'):
            expires_at = datetime.fromisoformat(data['expires_at'])

        created_at = datetime.fromisoformat(data['created_at'])

        return cls(
            user_id=data['user_id'],
            username=data.get('username'),
            email=data.get('email'),
            roles=set(data.get('roles', [])),
            permissions=set(data.get('permissions', [])),
            session_id=data.get('session_id'),
            auth_method=data.get('auth_method'),
            expires_at=expires_at,
            metadata=data.get('metadata', {}),
            created_at=created_at
        )
