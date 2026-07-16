"""
Authorization API - Interfaces and Data Contracts

This module defines the core interfaces and data models for the authorization system.
It re-exports security_core interfaces and extends with authorization-specific types.

Following mmf patterns:
- Clean separation between API (interfaces/contracts) and implementation
- Re-export from existing security_core until that module is migrated
- Authorization-specific enums and data models
"""

from __future__ import annotations

from enum import Enum

from mmf.core.security.domain.models.context import AuthorizationContext
from mmf.core.security.domain.models.result import AuthorizationResult
from mmf.core.security.domain.models.user import User
from mmf.core.security.ports.authorization import IAuthorizer

__all__ = [
    # Re-exported from security_core
    "IAuthorizer",
    "User",
    "AuthorizationContext",
    "AuthorizationResult",
    # Authorization-specific types
    "Permission",
    "PermissionAction",
    "ResourceType",
    "PolicyEffect",
    "ConditionOperator",
    "AttributeType",
]


# Authorization-specific enums


class PermissionAction(Enum):
    """Standard permission actions for authorization."""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    MANAGE = "manage"
    ALL = "*"


class ResourceType(Enum):
    """Standard resource types for authorization."""

    SERVICE = "service"
    CONFIG = "config"
    DEPLOYMENT = "deployment"
    LOG = "log"
    METRIC = "metric"
    USER = "user"
    ROLE = "role"
    POLICY = "policy"
    SECRET = "secret"  # pragma: allowlist secret
    DATABASE = "database"
    API = "api"
    ALL = "*"


class PolicyEffect(Enum):
    """Policy evaluation effects for ABAC."""

    ALLOW = "allow"
    DENY = "deny"
    AUDIT = "audit"  # Allow but log for audit purposes


class ConditionOperator(Enum):
    """Operators for attribute-based conditions in policies."""

    # Equality operators
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"

    # Comparison operators
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"

    # Collection operators
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"

    # String operators
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"

    # Existence operators
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class AttributeType(Enum):
    """Types of attributes used in ABAC policies."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    LIST = "list"
    OBJECT = "object"
    NULL = "null"


# Authorization-specific data models


class Permission:
    """
    Represents a fine-grained permission.

    Format: resource_type:resource_id:action
    Examples:
        - service:user-service:read
        - config:*:write
        - *:*:*  (superuser)
    """

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        action: str,
        constraints: dict | None = None,
    ):
        """
        Initialize a permission.

        Args:
            resource_type: Type of resource (e.g., "service", "config", "*")
            resource_id: Resource identifier (e.g., "user-service", "*")
            action: Action to perform (e.g., "read", "write", "*")
            constraints: Additional constraints (e.g., {"environment": "production"})
        """
        if not resource_type or not resource_id or not action:
            raise ValueError("Permission must have resource_type, resource_id, and action")

        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
        self.constraints = constraints or {}

    def matches(self, resource_type: str, resource_id: str, action: str) -> bool:
        """Check if this permission matches the requested access."""
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
    def from_string(cls, permission_str: str) -> Permission:
        """
        Create permission from string format.

        Args:
            permission_str: Permission string (e.g., "service:user-service:read")

        Returns:
            Permission instance
        """
        parts = permission_str.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid permission format: {permission_str}")
        return cls(resource_type=parts[0], resource_id=parts[1], action=parts[2])

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"Permission({self.to_string()})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Permission):
            return False
        return (
            self.resource_type == other.resource_type
            and self.resource_id == other.resource_id
            and self.action == other.action
        )

    def __hash__(self) -> int:
        return hash((self.resource_type, self.resource_id, self.action))
