"""
Authorization Module

This module contains concrete implementations of authorization providers.
It depends only on the security.api layer, following the level contract principle.

Key Features:
- Role-based access control (RBAC)
- Permission-based authorization
- Policy-based authorization
- Resource-specific access control
"""

import logging
from typing import Any

from .api import (
    AuthorizationContext,
    AuthorizationError,
    AuthorizationResult,
    PermissionAction,
    User,
)

logger = logging.getLogger(__name__)


class RoleBasedAuthorizer:
    """
    Role-based access control authorizer.

    This authorizer grants access based on user roles and predefined
    role-to-permission mappings. It supports role hierarchies where
    roles can inherit permissions from other roles.
    """

    def __init__(
        self,
        role_permissions: dict[str, set[str]] | None = None,
        role_hierarchy: dict[str, set[str]] | None = None
    ):
        """
        Initialize the role-based authorizer.

        Args:
            role_permissions: Mapping of roles to permissions
            role_hierarchy: Mapping of roles to inherited roles
        """
        self.role_permissions = role_permissions or self._get_default_role_permissions()
        self.role_hierarchy = role_hierarchy or self._get_default_role_hierarchy()

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Check authorization based on user roles.

        Args:
            context: Authorization context containing user, resource, and action

        Returns:
            AuthorizationResult indicating if access is allowed
        """
        try:
            user = context.user
            resource = context.resource
            action = context.action

            # Get required permission for this resource and action
            required_permission = f"{resource}:{action}"

            # Get user's effective permissions from roles
            user_permissions = self.get_user_permissions(user)

            # Check if user has the required permission
            if required_permission in user_permissions:
                logger.info(f"Authorization granted for user {user.username} on {resource}:{action}")
                return AuthorizationResult(
                    allowed=True,
                    reason=f"User has permission {required_permission}",
                    policies_evaluated=["role_based"],
                    metadata={"permission": required_permission}
                )

            # Check for admin override
            if "admin" in user.roles:
                logger.info(f"Authorization granted for admin user {user.username}")
                return AuthorizationResult(
                    allowed=True,
                    reason="User has admin role",
                    policies_evaluated=["role_based", "admin_override"],
                    metadata={"admin_override": True}
                )

            # Access denied
            logger.warning(f"Authorization denied for user {user.username} on {resource}:{action}")
            return AuthorizationResult(
                allowed=False,
                reason=f"User lacks permission {required_permission}",
                policies_evaluated=["role_based"],
                metadata={"required_permission": required_permission}
            )

        except Exception as e:
            logger.error(f"Authorization error: {e}")
            return AuthorizationResult(
                allowed=False,
                reason="Authorization check failed",
                policies_evaluated=["role_based"],
                metadata={"error": str(e)}
            )

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get all permissions for a user based on their roles and role hierarchy.

        Args:
            user: User to get permissions for

        Returns:
            Set of permission strings
        """
        permissions = set()
        effective_roles = self.get_effective_roles(user)

        # Add permissions from all effective roles
        for role in effective_roles:
            if role in self.role_permissions:
                permissions.update(self.role_permissions[role])

        return permissions

    def get_effective_roles(self, user: User) -> set[str]:
        """
        Get effective roles for a user including inherited roles.

        Args:
            user: User to get roles for

        Returns:
            Set of effective role names
        """
        effective_roles = set(user.roles)

        def add_inherited_roles(role: str):
            if role in self.role_hierarchy:
                for inherited_role in self.role_hierarchy[role]:
                    if inherited_role not in effective_roles:
                        effective_roles.add(inherited_role)
                        add_inherited_roles(inherited_role)  # Recursive inheritance

        # Add inherited roles for each user role
        for role in user.roles:
            add_inherited_roles(role)

        return effective_roles

    def _get_default_role_permissions(self) -> dict[str, set[str]]:
        """
        Get default role-to-permission mappings.

        Returns:
            Dictionary mapping roles to sets of permissions
        """
        return {
            "admin": {
                "*:*",  # Admin can do everything
            },
            "user": {
                "profile:read",
                "profile:write",
                "data:read",
            },
            "viewer": {
                "data:read",
                "profile:read",
            },
            "editor": {
                "data:read",
                "data:write",
                "profile:read",
                "profile:write",
            },
            "moderator": {
                "data:read",
                "data:write",
                "data:delete",
                "profile:read",
                "users:read",
            }
        }

    def _get_default_role_hierarchy(self) -> dict[str, set[str]]:
        """
        Get default role hierarchy.

        Returns:
            Dictionary mapping roles to sets of inherited roles
        """
        return {
            "admin": {"moderator", "editor", "user", "viewer"},
            "moderator": {"editor", "user", "viewer"},
            "editor": {"user", "viewer"},
            "user": {"viewer"},
        }

    def create_role(
        self,
        role_name: str,
        permissions: set[str] | None = None,
        inherited_roles: set[str] | None = None
    ) -> bool:
        """
        Create a new role with specified permissions and inheritance.

        Args:
            role_name: Name of the role to create
            permissions: Set of permissions for the role
            inherited_roles: Set of roles this role inherits from

        Returns:
            True if role was created successfully
        """
        try:
            if role_name in self.role_permissions:
                logger.warning("Role %s already exists", role_name)
                return False

            # Set permissions
            self.role_permissions[role_name] = permissions or set()

            # Set inheritance
            if inherited_roles:
                # Validate inherited roles exist
                for inherited_role in inherited_roles:
                    if inherited_role not in self.role_permissions:
                        logger.error("Cannot inherit from non-existent role: %s", inherited_role)
                        # Clean up
                        self.role_permissions.pop(role_name, None)
                        return False

                self.role_hierarchy[role_name] = inherited_roles

            # Validate no circular dependencies
            if self._has_circular_dependency(role_name):
                logger.error("Creating role %s would create circular dependency", role_name)
                # Clean up
                self.role_permissions.pop(role_name, None)
                self.role_hierarchy.pop(role_name, None)
                return False

            logger.info("Created role: %s", role_name)
            return True

        except Exception as e:
            logger.error("Error creating role %s: %s", role_name, e)
            return False

    def delete_role(self, role_name: str) -> bool:
        """
        Delete a role and remove it from hierarchy.

        Args:
            role_name: Name of the role to delete

        Returns:
            True if role was deleted successfully
        """
        try:
            if role_name not in self.role_permissions:
                logger.warning("Role %s does not exist", role_name)
                return False

            # Remove from permissions
            del self.role_permissions[role_name]

            # Remove from hierarchy
            self.role_hierarchy.pop(role_name, None)

            # Remove from other roles' inheritance
            for _role, inherited_roles in self.role_hierarchy.items():
                inherited_roles.discard(role_name)

            logger.info("Deleted role: %s", role_name)
            return True

        except Exception as e:
            logger.error("Error deleting role %s: %s", role_name, e)
            return False

    def get_role_info(self, role_name: str) -> dict[str, Any] | None:
        """
        Get information about a role.

        Args:
            role_name: Name of the role

        Returns:
            Dictionary with role information or None if not found
        """
        if role_name not in self.role_permissions:
            return None

        return {
            "name": role_name,
            "permissions": list(self.role_permissions[role_name]),
            "inherited_roles": list(self.role_hierarchy.get(role_name, set())),
            "effective_permissions": list(self._get_effective_permissions_for_role(role_name))
        }

    def list_roles(self) -> dict[str, dict[str, Any]]:
        """
        List all roles and their information.

        Returns:
            Dictionary mapping role names to role information
        """
        roles_info = {}
        for role_name in self.role_permissions.keys():
            role_info = self.get_role_info(role_name)
            if role_info:
                roles_info[role_name] = role_info
        return roles_info

    def validate_role_hierarchy(self) -> list[str]:
        """
        Validate the role hierarchy for circular dependencies.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        for role in self.role_permissions.keys():
            if self._has_circular_dependency(role):
                errors.append(f"Circular dependency detected for role: {role}")

        return errors

    def _get_effective_permissions_for_role(self, role_name: str) -> set[str]:
        """
        Get effective permissions for a role including inherited permissions.

        Args:
            role_name: Name of the role

        Returns:
            Set of effective permissions
        """
        if role_name not in self.role_permissions:
            return set()

        permissions = set(self.role_permissions[role_name])

        def add_inherited_permissions(role: str):
            if role in self.role_hierarchy:
                for inherited_role in self.role_hierarchy[role]:
                    if inherited_role in self.role_permissions:
                        permissions.update(self.role_permissions[inherited_role])
                        add_inherited_permissions(inherited_role)

        add_inherited_permissions(role_name)
        return permissions

    def _has_circular_dependency(self, role: str, visited: set[str] | None = None, path: set[str] | None = None) -> bool:
        """
        Check if a role has circular dependencies in the hierarchy.

        Args:
            role: Role to check
            visited: Set of visited roles (for optimization)
            path: Current path being explored

        Returns:
            True if circular dependency exists
        """
        if visited is None:
            visited = set()
        if path is None:
            path = set()

        if role in path:
            return True  # Circular dependency found

        if role in visited:
            return False  # Already checked this path

        visited.add(role)
        path.add(role)

        # Check inherited roles
        if role in self.role_hierarchy:
            for inherited_role in self.role_hierarchy[role]:
                if self._has_circular_dependency(inherited_role, visited, path):
                    return True

        path.remove(role)
        return False


class PermissionBasedAuthorizer:
    """
    Permission-based access control authorizer.

    This authorizer checks explicit permissions assigned to users
    rather than role-based permissions.
    """

    def __init__(self):
        """Initialize the permission-based authorizer."""
        pass

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Check authorization based on explicit user permissions.

        Args:
            context: Authorization context containing user, resource, and action

        Returns:
            AuthorizationResult indicating if access is allowed
        """
        try:
            user = context.user
            resource = context.resource
            action = context.action

            # Build required permission
            required_permission = f"{resource}:{action}"

            # Check if user has the explicit permission
            user_permissions = self.get_user_permissions(user)

            if required_permission in user_permissions:
                logger.info(f"Permission authorization granted for user {user.username}")
                return AuthorizationResult(
                    allowed=True,
                    reason=f"User has explicit permission {required_permission}",
                    policies_evaluated=["permission_based"],
                    metadata={"permission": required_permission}
                )

            # Check for wildcard permissions
            wildcard_permissions = [
                f"{resource}:*",  # All actions on resource
                "*:*",           # All actions on all resources
            ]

            for wildcard in wildcard_permissions:
                if wildcard in user_permissions:
                    logger.info(f"Wildcard authorization granted for user {user.username}")
                    return AuthorizationResult(
                        allowed=True,
                        reason=f"User has wildcard permission {wildcard}",
                        policies_evaluated=["permission_based"],
                        metadata={"wildcard_permission": wildcard}
                    )

            # Access denied
            logger.warning(f"Permission authorization denied for user {user.username}")
            return AuthorizationResult(
                allowed=False,
                reason=f"User lacks permission {required_permission}",
                policies_evaluated=["permission_based"],
                metadata={"required_permission": required_permission}
            )

        except Exception as e:
            logger.error(f"Permission authorization error: {e}")
            return AuthorizationResult(
                allowed=False,
                reason="Authorization check failed",
                policies_evaluated=["permission_based"],
                metadata={"error": str(e)}
            )

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get explicit permissions for a user.

        Args:
            user: User to get permissions for

        Returns:
            Set of permission strings from user attributes
        """
        # Get permissions from user attributes
        permissions = set()

        # Check if user has explicit permissions in attributes
        if "permissions" in user.attributes:
            user_perms = user.attributes["permissions"]
            if isinstance(user_perms, list | set):
                permissions.update(user_perms)
            elif isinstance(user_perms, str):
                permissions.add(user_perms)

        return permissions


class AttributeBasedAuthorizer:
    """
    Attribute-based access control (ABAC) authorizer.

    This authorizer makes decisions based on user attributes,
    resource attributes, and environmental context.
    """

    def __init__(self, policies: list[dict[str, Any]] | None = None):
        """
        Initialize the attribute-based authorizer.

        Args:
            policies: List of ABAC policy definitions
        """
        self.policies = policies or self._get_default_policies()

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Check authorization based on attributes and policies.

        Args:
            context: Authorization context with user, resource, action, and environment

        Returns:
            AuthorizationResult indicating if access is allowed
        """
        try:
            evaluated_policies = []

            for policy in self.policies:
                policy_name = policy.get("name", "unnamed_policy")
                evaluated_policies.append(policy_name)

                if self._evaluate_policy(policy, context):
                    logger.info(f"ABAC authorization granted by policy {policy_name}")
                    return AuthorizationResult(
                        allowed=True,
                        reason=f"Access granted by policy {policy_name}",
                        policies_evaluated=evaluated_policies,
                        metadata={"matching_policy": policy_name}
                    )

            # No policy granted access
            logger.warning(f"ABAC authorization denied for user {context.user.username}")
            return AuthorizationResult(
                allowed=False,
                reason="No policy grants access",
                policies_evaluated=evaluated_policies,
                metadata={"policies_count": len(self.policies)}
            )

        except Exception as e:
            logger.error(f"ABAC authorization error: {e}")
            return AuthorizationResult(
                allowed=False,
                reason="Authorization check failed",
                policies_evaluated=["abac"],
                metadata={"error": str(e)}
            )

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get permissions for a user (ABAC doesn't use explicit permissions).

        Args:
            user: User to get permissions for

        Returns:
            Empty set (ABAC uses dynamic policy evaluation)
        """
        return set()

    def _evaluate_policy(self, policy: dict[str, Any], context: AuthorizationContext) -> bool:
        """
        Evaluate a single ABAC policy against the context.

        Args:
            policy: Policy definition
            context: Authorization context

        Returns:
            True if policy grants access, False otherwise
        """
        try:
            # Check if policy applies to this resource and action
            if not self._matches_resource(policy, context.resource, context.action):
                return False

            # Evaluate user conditions
            if not self._evaluate_user_conditions(policy, context.user):
                return False

            # Evaluate environment conditions
            if not self._evaluate_environment_conditions(policy, context.environment):
                return False

            return True

        except Exception as e:
            logger.warning(f"Policy evaluation error: {e}")
            return False

    def _matches_resource(self, policy: dict[str, Any], resource: str, action: str) -> bool:
        """Check if policy applies to the given resource and action."""
        policy_resources = policy.get("resources", ["*"])
        policy_actions = policy.get("actions", ["*"])

        resource_match = "*" in policy_resources or resource in policy_resources
        action_match = "*" in policy_actions or action in policy_actions

        return resource_match and action_match

    def _evaluate_user_conditions(self, policy: dict[str, Any], user: User) -> bool:
        """Evaluate user-based conditions in the policy."""
        conditions = policy.get("user_conditions", {})

        # Check role requirements
        if "roles" in conditions:
            required_roles = conditions["roles"]
            if not any(role in user.roles for role in required_roles):
                return False

        # Check attribute requirements
        if "attributes" in conditions:
            for attr_name, expected_value in conditions["attributes"].items():
                user_value = user.attributes.get(attr_name)
                if user_value != expected_value:
                    return False

        return True

    def _evaluate_environment_conditions(self, policy: dict[str, Any], environment: dict[str, Any]) -> bool:
        """Evaluate environment-based conditions in the policy."""
        conditions = policy.get("environment_conditions", {})

        for condition_name, expected_value in conditions.items():
            env_value = environment.get(condition_name)
            if env_value != expected_value:
                return False

        return True

    def _get_default_policies(self) -> list[dict[str, Any]]:
        """
        Get default ABAC policies.

        Returns:
            List of default policy definitions
        """
        return [
            {
                "name": "admin_full_access",
                "resources": ["*"],
                "actions": ["*"],
                "user_conditions": {
                    "roles": ["admin"]
                }
            },
            {
                "name": "user_profile_access",
                "resources": ["profile"],
                "actions": ["read", "write"],
                "user_conditions": {
                    "roles": ["user", "editor", "moderator"]
                }
            },
            {
                "name": "data_read_access",
                "resources": ["data"],
                "actions": ["read"],
                "user_conditions": {
                    "roles": ["user", "viewer", "editor", "moderator"]
                }
            },
            {
                "name": "data_write_access",
                "resources": ["data"],
                "actions": ["write"],
                "user_conditions": {
                    "roles": ["editor", "moderator"]
                }
            }
        ]
