"""
Authorization Domain Models and Protocols.

This module defines the core domain models and interfaces for the authorization framework.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class PermissionAction(Enum):
    """Standard permission actions."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    UPDATE = "update"
    EXECUTE = "execute"
    ADMIN = "admin"


class ResourceType(Enum):
    """Standard resource types."""

    SERVICE = "service"
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    POLICY = "policy"
    AUDIT = "audit"
    CONFIG = "config"
    SYSTEM = "system"


@dataclass(frozen=True)
class Permission:
    """
    Represents a permission to perform an action on a resource.

    Format: resource_type:resource_id:action
    Example: user:123:read

    Supports wildcards (*) for matching:
    - "*:*:*" matches everything
    - "service:*:read" matches read on any service
    - "*:user-123:*" matches any action on user-123
    """

    resource_type: str
    resource_id: str
    action: str

    def matches(self, resource_type: str, resource_id: str, action: str) -> bool:
        """
        Check if this permission grants access to the requested resource/action.

        Supports wildcard matching with "*".

        Args:
            resource_type: Type of resource being accessed
            resource_id: ID of resource being accessed
            action: Action being performed

        Returns:
            True if permission matches (grants access)
        """
        # Check resource type
        if self.resource_type != "*" and self.resource_type != resource_type:
            return False

        # Check resource ID (support wildcards)
        if self.resource_id != "*" and not self._matches_pattern(self.resource_id, resource_id):
            return False

        # Check action
        if self.action != "*" and self.action != action:
            return False

        return True

    def _matches_pattern(self, pattern: str, value: str) -> bool:
        """Match pattern with wildcard support."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return value.startswith(pattern[:-1])
        if pattern.startswith("*"):
            return value.endswith(pattern[1:])
        return pattern == value

    def to_string(self) -> str:
        """Convert permission to string format."""
        return f"{self.resource_type}:{self.resource_id}:{self.action}"

    @classmethod
    def from_string(cls, permission_str: str) -> "Permission":
        """
        Create permission from string format.

        Args:
            permission_str: Permission string (e.g., "service:user-service:read")

        Returns:
            Permission instance

        Raises:
            ValueError: If format is invalid
        """
        parts = permission_str.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid permission format: {permission_str}")
        return cls(resource_type=parts[0], resource_id=parts[1], action=parts[2])

    def __str__(self) -> str:
        return self.to_string()


class IAuthorizationEngine(Protocol):
    """Interface for authorization engines (RBAC, ABAC)."""

    def check_permission(
        self, principal_id: str, permission: Permission, context: dict[str, Any] | None = None
    ) -> bool:
        """Check if principal has permission."""
        ...


class IPolicyRepository(Protocol):
    """Interface for policy storage."""

    def get_policy(self, policy_id: str) -> Any:
        """Get policy by ID."""
        ...
