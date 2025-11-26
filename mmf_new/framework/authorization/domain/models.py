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


@dataclass
class Permission:
    """
    Represents a permission to perform an action on a resource.

    Format: resource_type:resource_id:action
    Example: user:123:read
    """
    resource_type: str
    resource_id: str
    action: str

    def __str__(self) -> str:
        return f"{self.resource_type}:{self.resource_id}:{self.action}"


class IAuthorizationEngine(Protocol):
    """Interface for authorization engines (RBAC, ABAC)."""

    def check_permission(self, principal_id: str, permission: Permission, context: dict[str, Any] | None = None) -> bool:
        """Check if principal has permission."""
        ...


class IPolicyRepository(Protocol):
    """Interface for policy storage."""

    def get_policy(self, policy_id: str) -> Any:
        """Get policy by ID."""
        ...
