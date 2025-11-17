"""
Authorization Implementations

Concrete implementations of authorization providers.
"""

import builtins
import logging
from datetime import datetime, timezone
from typing import Any

from ..security_core.api import (
    AuthorizationContext,
    AuthorizationResult,
    IAuthorizer,
    PermissionAction,
    User,
)

logger = logging.getLogger(__name__)


class RoleBasedAuthorizer(IAuthorizer):
    """Role-based access control (RBAC) authorizer."""

    def __init__(self, role_permissions: builtins.dict[str, builtins.list[str]] | None = None):
        """
        Initialize with role to permissions mapping.

        Args:
            role_permissions: Dict mapping role names to list of permissions
        """
        self.role_permissions = role_permissions or {
            "admin": ["*"],
            "user": ["read", "write"],
            "guest": ["read"],
        }

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """Authorize based on user roles."""
        user_permissions = self.get_user_permissions(context.user)

        # Check if user has required permission
        if context.action in user_permissions or "*" in user_permissions:
            return AuthorizationResult(
                allowed=True,
                reason=f"User has required permission: {context.action}",
                metadata={
                    "authorizer": "rbac",
                    "user_roles": context.user.roles,
                    "user_permissions": list(user_permissions),
                },
            )

        return AuthorizationResult(
            allowed=False,
            reason=f"User lacks required permission: {context.action}",
            metadata={
                "authorizer": "rbac",
                "user_roles": context.user.roles,
                "required_permission": context.action,
            },
        )

    def get_user_permissions(self, user: User) -> set[str]:
        """Get user permissions based on roles."""
        permissions = set()

        for role in user.roles:
            role_perms = self.role_permissions.get(role, [])
            permissions.update(role_perms)

        return permissions


class AttributeBasedAuthorizer(IAuthorizer):
    """Attribute-based access control (ABAC) authorizer."""

    def __init__(self, policy_rules: builtins.list[builtins.dict[str, Any]] | None = None):
        """
        Initialize with ABAC policy rules.

        Args:
            policy_rules: List of policy rule dictionaries
        """
        self.policy_rules = policy_rules or []

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """Authorize based on attributes and policies."""
        for rule in self.policy_rules:
            if self._evaluate_rule(rule, context):
                return AuthorizationResult(
                    allowed=True,
                    reason=f"Policy rule matched: {rule.get('name', 'unnamed')}",
                    metadata={
                        "authorizer": "abac",
                        "matched_rule": rule.get("name"),
                        "rule_id": rule.get("id"),
                    },
                )

        return AuthorizationResult(
            allowed=False,
            reason="No policy rules matched the request",
            metadata={"authorizer": "abac", "rules_evaluated": len(self.policy_rules)},
        )

    def get_user_permissions(self, user: User) -> set[str]:
        """Get permissions based on attribute evaluation."""
        permissions = set()

        # Create dummy contexts for permission evaluation
        for action in ["read", "write", "delete", "execute", "admin"]:
            context = AuthorizationContext(user=user, resource="test_resource", action=action)

            result = self.authorize(context)
            if result.allowed:
                permissions.add(action)

        return permissions

    def _evaluate_rule(self, rule: builtins.dict[str, Any], context: AuthorizationContext) -> bool:
        """Evaluate a single ABAC rule."""
        conditions = rule.get("conditions", {})

        # Check resource conditions
        resource_pattern = conditions.get("resource")
        if resource_pattern and context.resource != resource_pattern:
            return False

        # Check action conditions
        action_pattern = conditions.get("action")
        if action_pattern and context.action != action_pattern:
            return False

        # Check user attribute conditions
        user_conditions = conditions.get("user", {})
        for attr, expected_value in user_conditions.items():
            user_value = getattr(context.user, attr, None)
            if user_value != expected_value:
                return False

        # Check environment conditions
        env_conditions = conditions.get("environment", {})
        for attr, expected_value in env_conditions.items():
            env_value = context.environment.get(attr)
            if env_value != expected_value:
                return False

        return True


class PermissionBasedAuthorizer(IAuthorizer):
    """Direct permission-based authorizer."""

    def __init__(self, user_permissions: builtins.dict[str, builtins.list[str]] | None = None):
        """
        Initialize with user to permissions mapping.

        Args:
            user_permissions: Dict mapping user IDs to list of permissions
        """
        self.user_permissions = user_permissions or {}

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """Authorize based on direct user permissions."""
        user_permissions = self.get_user_permissions(context.user)

        # Check if user has required permission
        required_permission = f"{context.resource}:{context.action}"
        global_permission = f"*:{context.action}"

        if (
            required_permission in user_permissions
            or global_permission in user_permissions
            or "*:*" in user_permissions
        ):
            return AuthorizationResult(
                allowed=True,
                reason=f"User has required permission: {required_permission}",
                metadata={
                    "authorizer": "permission",
                    "user_permissions": list(user_permissions),
                    "required_permission": required_permission,
                },
            )

        return AuthorizationResult(
            allowed=False,
            reason=f"User lacks required permission: {required_permission}",
            metadata={"authorizer": "permission", "required_permission": required_permission},
        )

    def get_user_permissions(self, user: User) -> set[str]:
        """Get user permissions."""
        return set(self.user_permissions.get(user.id, []))


class CompositeAuthorizer(IAuthorizer):
    """Composite authorizer that combines multiple authorization strategies."""

    def __init__(self, authorizers: builtins.list[IAuthorizer], strategy: str = "any"):
        """
        Initialize composite authorizer.

        Args:
            authorizers: List of authorizers to compose
            strategy: "any" (allow if any authorizer allows) or
                     "all" (allow only if all authorizers allow)
        """
        self.authorizers = authorizers
        self.strategy = strategy

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """Authorize using composite strategy."""
        results = []

        for authorizer in self.authorizers:
            result = authorizer.authorize(context)
            results.append(result)

        if self.strategy == "any":
            # Allow if any authorizer allows
            for result in results:
                if result.allowed:
                    result.metadata["composite_strategy"] = "any"
                    result.metadata["authorizers_evaluated"] = len(self.authorizers)
                    return result

            # All denied
            return AuthorizationResult(
                allowed=False,
                reason="All authorizers denied access",
                metadata={
                    "composite_strategy": "any",
                    "authorizers_evaluated": len(self.authorizers),
                    "all_results": [r.reason for r in results],
                },
            )

        elif self.strategy == "all":
            # Allow only if all authorizers allow
            for result in results:
                if not result.allowed:
                    return AuthorizationResult(
                        allowed=False,
                        reason=f"Authorizer denied: {result.reason}",
                        metadata={
                            "composite_strategy": "all",
                            "authorizers_evaluated": len(self.authorizers),
                            "failing_reason": result.reason,
                        },
                    )

            # All allowed
            return AuthorizationResult(
                allowed=True,
                reason="All authorizers allowed access",
                metadata={
                    "composite_strategy": "all",
                    "authorizers_evaluated": len(self.authorizers),
                },
            )

        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

    def get_user_permissions(self, user: User) -> set[str]:
        """Get combined permissions from all authorizers."""
        all_permissions = set()

        for authorizer in self.authorizers:
            permissions = authorizer.get_user_permissions(user)
            all_permissions.update(permissions)

        return all_permissions
