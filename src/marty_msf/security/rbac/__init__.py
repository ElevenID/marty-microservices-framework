"""
RBAC (Role-Based Access Control) System

Comprehensive role-based access control with hierarchical roles, permission inheritance,
dynamic role assignment, and integration with policy engines.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from marty_msf.core.enhanced_di import LambdaFactory, get_service, register_service

from ..exceptions import (
    PermissionDeniedError,
    PolicyEvaluationError,
    RoleRequiredError,
    SecurityError,
)

logger = logging.getLogger(__name__)


class PermissionAction(Enum):
    """Standard permission actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    MANAGE = "manage"
    ALL = "*"


class ResourceType(Enum):
    """Standard resource types."""
    SERVICE = "service"
    CONFIG = "config"
    DEPLOYMENT = "deployment"
    LOG = "log"
    METRIC = "metric"
    USER = "user"
    ROLE = "role"
    POLICY = "policy"
    SECRET = "secret"
    ALL = "*"


@dataclass
class Permission:
    """Represents a fine-grained permission."""

    resource_type: str  # e.g., "service", "config", "user"
    resource_id: str    # e.g., "*", "user-service", specific ID
    action: str         # e.g., "read", "write", "delete", "*"
    constraints: dict[str, Any] = field(default_factory=dict)  # Additional constraints

    def __post_init__(self):
        """Validate permission format."""
        if not self.resource_type or not self.resource_id or not self.action:
            raise ValueError("Permission must have resource_type, resource_id, and action")

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
        """Convert permission to string format: resource_type:resource_id:action."""
        return f"{self.resource_type}:{self.resource_id}:{self.action}"

    @classmethod
    def from_string(cls, permission_str: str) -> "Permission":
        """Create permission from string format."""
        parts = permission_str.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid permission format: {permission_str}")
        return cls(
            resource_type=parts[0],
            resource_id=parts[1],
            action=parts[2]
        )


@dataclass
class Role:
    """Represents a role with permissions and hierarchy."""

    name: str
    description: str
    permissions: set[Permission] = field(default_factory=set)
    inherits_from: set[str] = field(default_factory=set)  # Parent role names
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_system: bool = False  # System roles cannot be deleted
    is_active: bool = True

    def __post_init__(self):
        """Validate role."""
        if not self.name:
            raise ValueError("Role name is required")

    def add_permission(self, permission: Permission):
        """Add a permission to this role."""
        self.permissions.add(permission)

    def remove_permission(self, permission: Permission):
        """Remove a permission from this role."""
        self.permissions.discard(permission)

    def has_permission(self, resource_type: str, resource_id: str, action: str) -> bool:
        """Check if role has specific permission."""
        for permission in self.permissions:
            if permission.matches(resource_type, resource_id, action):
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert role to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "permissions": [p.to_string() for p in self.permissions],
            "inherits_from": list(self.inherits_from),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "is_system": self.is_system,
            "is_active": self.is_active
        }


class RBACManager:
    """Comprehensive RBAC management system."""

    def __init__(self):
        """Initialize RBAC manager."""
        self.roles: dict[str, Role] = {}
        self.user_roles: dict[str, set[str]] = {}  # user_id -> role_names
        self.role_hierarchy: dict[str, set[str]] = {}  # role -> inherited roles
        self.permission_cache: dict[str, set[Permission]] = {}  # Cache for resolved permissions
        self.cache_ttl = timedelta(minutes=30)
        self.last_cache_refresh = datetime.now(timezone.utc)

        # Initialize default roles
        self._initialize_default_roles()

    def _initialize_default_roles(self):
        """Create default system roles."""
        # Super admin role
        admin_role = Role(
            name="admin",
            description="System administrator with full access",
            is_system=True
        )
        admin_role.add_permission(Permission("*", "*", "*"))
        self.add_role(admin_role)

        # Service manager role
        service_manager = Role(
            name="service_manager",
            description="Can manage services and configurations",
            is_system=True
        )
        service_manager.add_permission(Permission("service", "*", "*"))
        service_manager.add_permission(Permission("config", "*", "read"))
        service_manager.add_permission(Permission("config", "*", "update"))
        service_manager.add_permission(Permission("deployment", "*", "*"))
        self.add_role(service_manager)

        # Developer role
        developer = Role(
            name="developer",
            description="Developer with read access and limited write access",
            is_system=True
        )
        developer.add_permission(Permission("service", "*", "read"))
        developer.add_permission(Permission("config", "public", "read"))
        developer.add_permission(Permission("log", "application", "read"))
        developer.add_permission(Permission("metric", "*", "read"))
        self.add_role(developer)

        # Viewer role
        viewer = Role(
            name="viewer",
            description="Read-only access to non-sensitive resources",
            is_system=True
        )
        viewer.add_permission(Permission("service", "*", "read"))
        viewer.add_permission(Permission("config", "public", "read"))
        viewer.add_permission(Permission("metric", "*", "read"))
        self.add_role(viewer)

        # Service account role
        service_account = Role(
            name="service_account",
            description="Limited access for automated systems",
            is_system=True
        )
        service_account.add_permission(Permission("service", "own", "read"))
        service_account.add_permission(Permission("service", "own", "update"))
        service_account.add_permission(Permission("config", "own", "read"))
        self.add_role(service_account)

        logger.info("Initialized default RBAC roles")

    def add_role(self, role: Role) -> bool:
        """Add a new role."""
        try:
            if role.name in self.roles:
                raise ValueError(f"Role '{role.name}' already exists")

            # Validate inheritance
            for parent_role in role.inherits_from:
                if parent_role not in self.roles:
                    raise ValueError(f"Parent role '{parent_role}' does not exist")

                # Check for circular inheritance
                if self._would_create_cycle(role.name, parent_role):
                    raise ValueError("Adding role would create circular inheritance")

            self.roles[role.name] = role
            self._update_role_hierarchy(role)
            self._clear_cache()

            logger.info(f"Added role: {role.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add role {role.name}: {e}")
            return False

    def remove_role(self, role_name: str) -> bool:
        """Remove a role if it's not a system role."""
        try:
            if role_name not in self.roles:
                return False

            role = self.roles[role_name]
            if role.is_system:
                raise ValueError(f"Cannot remove system role: {role_name}")

            # Remove from users
            for user_id in list(self.user_roles.keys()):
                self.user_roles[user_id].discard(role_name)

            # Update dependent roles
            for other_role in self.roles.values():
                other_role.inherits_from.discard(role_name)

            del self.roles[role_name]
            self._rebuild_role_hierarchy()
            self._clear_cache()

            logger.info(f"Removed role: {role_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to remove role {role_name}: {e}")
            return False

    def assign_role_to_user(self, user_id: str, role_name: str) -> bool:
        """Assign a role to a user."""
        try:
            if role_name not in self.roles:
                raise ValueError(f"Role '{role_name}' does not exist")

            if not self.roles[role_name].is_active:
                raise ValueError(f"Role '{role_name}' is not active")

            if user_id not in self.user_roles:
                self.user_roles[user_id] = set()

            self.user_roles[user_id].add(role_name)
            self._clear_user_cache(user_id)

            logger.info(f"Assigned role '{role_name}' to user '{user_id}'")
            return True

        except Exception as e:
            logger.error(f"Failed to assign role {role_name} to user {user_id}: {e}")
            return False

    def remove_role_from_user(self, user_id: str, role_name: str) -> bool:
        """Remove a role from a user."""
        try:
            if user_id in self.user_roles:
                self.user_roles[user_id].discard(role_name)
                self._clear_user_cache(user_id)
                logger.info(f"Removed role '{role_name}' from user '{user_id}'")
                return True
            return False

        except Exception as e:
            logger.error(f"Failed to remove role {role_name} from user {user_id}: {e}")
            return False

    def check_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str
    ) -> bool:
        """Check if user has permission for specific resource and action."""
        try:
            user_permissions = self._get_user_permissions(user_id)

            for permission in user_permissions:
                if permission.matches(resource_type, resource_id, action):
                    return True

            return False

        except Exception as e:
            logger.error(f"Permission check failed for user {user_id}: {e}")
            return False

    def require_permission(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str
    ):
        """Require permission or raise PermissionDeniedError."""
        if not self.check_permission(user_id, resource_type, resource_id, action):
            raise PermissionDeniedError(
                f"Permission denied for {action} on {resource_type}:{resource_id}",
                permission=f"{resource_type}:{resource_id}:{action}",
                resource=f"{resource_type}:{resource_id}",
                action=action
            )

    def check_role(self, user_id: str, role_name: str) -> bool:
        """Check if user has specific role (including inherited)."""
        user_roles = self._get_user_effective_roles(user_id)
        return role_name in user_roles

    def require_role(self, user_id: str, role_name: str):
        """Require role or raise RoleRequiredError."""
        if not self.check_role(user_id, role_name):
            raise RoleRequiredError(
                f"Role '{role_name}' required",
                required_role=role_name
            )

    def get_user_roles(self, user_id: str) -> set[str]:
        """Get direct roles assigned to user."""
        return self.user_roles.get(user_id, set()).copy()

    def get_user_effective_roles(self, user_id: str) -> set[str]:
        """Get all effective roles for user (including inherited)."""
        return self._get_user_effective_roles(user_id)

    def get_user_permissions(self, user_id: str) -> set[Permission]:
        """Get all effective permissions for user."""
        return self._get_user_permissions(user_id)

    def _get_user_effective_roles(self, user_id: str) -> set[str]:
        """Get all roles for user including inherited ones."""
        direct_roles = self.user_roles.get(user_id, set())
        effective_roles = set()

        for role_name in direct_roles:
            effective_roles.add(role_name)
            effective_roles.update(self.role_hierarchy.get(role_name, set()))

        return effective_roles

    def _get_user_permissions(self, user_id: str) -> set[Permission]:
        """Get all permissions for user with caching."""
        cache_key = f"user_permissions:{user_id}"

        # Check cache
        if (cache_key in self.permission_cache and
            datetime.now(timezone.utc) - self.last_cache_refresh < self.cache_ttl):
            return self.permission_cache[cache_key].copy()

        # Calculate permissions
        permissions = set()
        effective_roles = self._get_user_effective_roles(user_id)

        for role_name in effective_roles:
            if role_name in self.roles:
                permissions.update(self.roles[role_name].permissions)

        # Cache result
        self.permission_cache[cache_key] = permissions.copy()
        return permissions

    def _update_role_hierarchy(self, role: Role):
        """Update role hierarchy for a role."""
        inherited_roles = set()

        def collect_inherited(role_name: str):
            if role_name in self.roles:
                for parent in self.roles[role_name].inherits_from:
                    inherited_roles.add(parent)
                    collect_inherited(parent)

        collect_inherited(role.name)
        self.role_hierarchy[role.name] = inherited_roles

    def _rebuild_role_hierarchy(self):
        """Rebuild entire role hierarchy."""
        self.role_hierarchy.clear()
        for role in self.roles.values():
            self._update_role_hierarchy(role)

    def _would_create_cycle(self, role_name: str, parent_role: str) -> bool:
        """Check if adding inheritance would create a cycle."""
        visited = set()

        def has_cycle(current: str) -> bool:
            if current in visited:
                return True
            if current == role_name:
                return True

            visited.add(current)
            for inherited in self.role_hierarchy.get(current, set()):
                if has_cycle(inherited):
                    return True
            visited.remove(current)
            return False

        return has_cycle(parent_role)

    def _clear_cache(self):
        """Clear all permission caches."""
        self.permission_cache.clear()
        self.last_cache_refresh = datetime.now(timezone.utc)

    def _clear_user_cache(self, user_id: str):
        """Clear cache for specific user."""
        cache_key = f"user_permissions:{user_id}"
        self.permission_cache.pop(cache_key, None)

    def load_roles_from_config(self, config_data: dict[str, Any]) -> bool:
        """Load roles from configuration data."""
        try:
            roles_data = config_data.get("roles", {})

            for role_name, role_info in roles_data.items():
                if role_name in self.roles and self.roles[role_name].is_system:
                    logger.warning(f"Skipping system role: {role_name}")
                    continue

                role = Role(
                    name=role_name,
                    description=role_info.get("description", ""),
                    inherits_from=set(role_info.get("inherits", []))
                )

                # Add permissions
                for perm_str in role_info.get("permissions", []):
                    try:
                        permission = Permission.from_string(perm_str)
                        role.add_permission(permission)
                    except ValueError as e:
                        logger.error(f"Invalid permission '{perm_str}' in role '{role_name}': {e}")

                self.add_role(role)

            logger.info(f"Loaded {len(roles_data)} roles from configuration")
            return True

        except Exception as e:
            logger.error(f"Failed to load roles from config: {e}")
            return False

    def export_roles_to_config(self) -> dict[str, Any]:
        """Export roles to configuration format."""
        roles_data = {}

        for role in self.roles.values():
            if not role.is_system:  # Don't export system roles
                roles_data[role.name] = {
                    "description": role.description,
                    "permissions": [p.to_string() for p in role.permissions],
                    "inherits": list(role.inherits_from)
                }

        return {"roles": roles_data}

    def get_role_info(self, role_name: str) -> dict[str, Any] | None:
        """Get detailed information about a role."""
        if role_name not in self.roles:
            return None

        role = self.roles[role_name]
        return {
            **role.to_dict(),
            "effective_permissions": [p.to_string() for p in self._get_role_effective_permissions(role_name)],
            "inherited_roles": list(self.role_hierarchy.get(role_name, set()))
        }

    def _get_role_effective_permissions(self, role_name: str) -> set[Permission]:
        """Get all effective permissions for a role including inherited."""
        permissions = set()

        # Add direct permissions
        if role_name in self.roles:
            permissions.update(self.roles[role_name].permissions)

        # Add inherited permissions
        for inherited_role in self.role_hierarchy.get(role_name, set()):
            if inherited_role in self.roles:
                permissions.update(self.roles[inherited_role].permissions)

        return permissions

    def list_roles(self, include_system: bool = False) -> list[dict[str, Any]]:
        """List all roles."""
        roles = []
        for role in self.roles.values():
            if include_system or not role.is_system:
                roles.append(role.to_dict())
        return roles


# Service-based RBAC manager access


class RBACManagerService:
    """Service wrapper for RBAC manager."""

    def __init__(self):
        self._manager = RBACManager()

    def get_manager(self) -> RBACManager:
        """Get the RBAC manager instance."""
        return self._manager


def get_rbac_manager() -> RBACManager:
    """Get RBAC manager instance from the DI container."""
    service = get_service(RBACManagerService)
    return service.get_manager()


def reset_rbac_manager():
    """Reset RBAC manager (not supported - managed by DI container)."""
    raise NotImplementedError(
        "reset_rbac_manager is not supported. Use the DI container lifecycle management instead."
    )


# Register the service
register_service(
    RBACManagerService,
    factory=LambdaFactory(RBACManagerService, lambda _: RBACManagerService()),
    is_singleton=True
)


__all__ = [
    "Permission",
    "Role",
    "RBACManager",
    "PermissionAction",
    "ResourceType",
    "get_rbac_manager",
    "reset_rbac_manager"
]
