"""
Authorization Bootstrap Module

Provides concrete implementations of authorization providers and factory functions
for creating authorizers. This module consolidates the best implementations from
the legacy authorization system while integrating with the new RBAC and ABAC modules.

Key Implementations:
- RoleBasedAuthorizer: RBAC with role hierarchy support
- PermissionBasedAuthorizer: Granular permission checking
- AttributeBasedAuthorizer: Policy evaluation with ABAC engine
- CompositeAuthorizer: Combines multiple authorization strategies

Factory Functions:
- create_role_based_authorizer(): Creates RBAC authorizer
- create_permission_based_authorizer(): Creates permission-based authorizer
- create_attribute_based_authorizer(): Creates ABAC authorizer
- create_composite_authorizer(): Creates composite authorizer

Architecture:
    The bootstrap module acts as a bridge between the authorization API
    and the underlying RBAC/ABAC systems. It provides simplified factories
    for common use cases while allowing full customization when needed.
"""

from __future__ import annotations

import logging
from typing import Any

from .abac import ABACContext, ABACManager, get_abac_manager
from .api import AuthorizationContext, AuthorizationResult, IAuthorizer, User
from .rbac import RBACManager, get_rbac_manager

logger = logging.getLogger(__name__)


class RoleBasedAuthorizer(IAuthorizer):
    """
    Role-based access control (RBAC) authorizer.

    Grants access based on user roles and role-to-permission mappings.
    Supports role hierarchy where roles can inherit permissions from other roles.

    Attributes:
        role_manager: RBACManager instance for role operations

    Example:
        authorizer = RoleBasedAuthorizer()
        context = AuthorizationContext(user, "documents", "read")
        result = authorizer.authorize(context)
        if result.allowed:
            # Grant access
    """

    def __init__(self, role_manager: RBACManager | None = None):
        """
        Initialize the role-based authorizer.

        Args:
            role_manager: Optional RBACManager instance. If None, uses global manager.
        """
        self.role_manager = role_manager or get_rbac_manager()

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Check authorization based on user roles and permissions.

        Process:
        1. Extract required permission from context (resource:action)
        2. Get user's effective permissions from roles
        3. Check if user has required permission
        4. Handle admin override if applicable

        Args:
            context: Authorization context with user, resource, and action

        Returns:
            AuthorizationResult indicating if access is allowed
        """
        try:
            user = context.user
            resource = context.resource
            action = context.action

            # Build required permission
            required_permission = f"{resource}:{action}"

            # Get user's effective permissions from roles
            user_permissions = self.get_user_permissions(user)

            # Check if user has required permission
            if required_permission in user_permissions or "*:*" in user_permissions:
                logger.info(
                    "RBAC authorization granted for %s on %s:%s",
                    user.username,
                    resource,
                    action,
                )
                return AuthorizationResult(
                    allowed=True,
                    reason=f"User has permission {required_permission}",
                    policies_evaluated=["role_based"],
                    metadata={
                        "authorizer": "rbac",
                        "permission": required_permission,
                        "user_roles": list(user.roles),
                    },
                )

            # Check for admin override
            if "admin" in user.roles:
                logger.info("RBAC authorization granted for admin user %s", user.username)
                return AuthorizationResult(
                    allowed=True,
                    reason="User has admin role",
                    policies_evaluated=["role_based", "admin_override"],
                    metadata={"authorizer": "rbac", "admin_override": True},
                )

            # Access denied
            logger.warning(
                "RBAC authorization denied for %s on %s:%s", user.username, resource, action
            )
            return AuthorizationResult(
                allowed=False,
                reason=f"User lacks permission {required_permission}",
                policies_evaluated=["role_based"],
                metadata={
                    "authorizer": "rbac",
                    "required_permission": required_permission,
                    "user_roles": list(user.roles),
                },
            )

        except Exception as e:
            logger.error("RBAC authorization error: %s", e)
            return AuthorizationResult(
                allowed=False,
                reason="Authorization check failed",
                policies_evaluated=["role_based"],
                metadata={"authorizer": "rbac", "error": str(e)},
            )

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get all permissions for a user based on their roles.

        Includes permissions from role hierarchy - if a role inherits
        from other roles, those permissions are included as well.

        Args:
            user: User to get permissions for

        Returns:
            Set of permission strings (format: "resource:action")
        """
        permissions = set()

        for role_name in user.roles:
            role_info = self.role_manager.get_role_info(role_name)
            if role_info:
                permissions.update(role_info.get("permissions", set()))

        return permissions


class PermissionBasedAuthorizer(IAuthorizer):
    """
    Direct permission-based authorizer.

    Grants access based on direct user-to-permission mappings without
    roles. Useful for fine-grained access control or when roles don't
    map well to your use case.

    Attributes:
        user_permissions: Mapping of user IDs to permission sets

    Permission Format:
        - Specific: "resource:action" (e.g., "documents:read")
        - Wildcard action: "resource:*" (e.g., "documents:*")
        - Wildcard resource: "*:action" (e.g., "*:read")
        - Full wildcard: "*:*" (admin-level access)

    Example:
        authorizer = PermissionBasedAuthorizer({
            "user123": ["documents:read", "documents:write"],
            "admin456": ["*:*"]
        })
    """

    def __init__(self, user_permissions: dict[str, list[str]] | None = None):
        """
        Initialize with user-to-permissions mapping.

        Args:
            user_permissions: Dict mapping user IDs to lists of permissions
        """
        self.user_permissions = user_permissions or {}

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Authorize based on direct user permissions.

        Checks multiple permission patterns in order:
        1. Exact match: "resource:action"
        2. Resource wildcard: "*:action"
        3. Action wildcard: "resource:*"
        4. Full wildcard: "*:*"

        Args:
            context: Authorization context with user, resource, and action

        Returns:
            AuthorizationResult indicating if access is allowed
        """
        try:
            user = context.user
            resource = context.resource
            action = context.action

            # Get user permissions
            user_permissions = self.get_user_permissions(user)

            # Check permission patterns
            required_permission = f"{resource}:{action}"
            global_action = f"*:{action}"
            global_resource = f"{resource}:*"
            full_wildcard = "*:*"

            if (
                required_permission in user_permissions
                or global_action in user_permissions
                or global_resource in user_permissions
                or full_wildcard in user_permissions
            ):
                logger.info(
                    "Permission-based authorization granted for %s on %s:%s",
                    user.username,
                    resource,
                    action,
                )
                return AuthorizationResult(
                    allowed=True,
                    reason=f"User has required permission: {required_permission}",
                    policies_evaluated=["permission_based"],
                    metadata={
                        "authorizer": "permission",
                        "user_permissions": list(user_permissions),
                        "required_permission": required_permission,
                    },
                )

            # Access denied
            logger.warning(
                "Permission-based authorization denied for %s on %s:%s",
                user.username,
                resource,
                action,
            )
            return AuthorizationResult(
                allowed=False,
                reason=f"User lacks required permission: {required_permission}",
                policies_evaluated=["permission_based"],
                metadata={
                    "authorizer": "permission",
                    "required_permission": required_permission,
                },
            )

        except Exception as e:
            logger.error("Permission-based authorization error: %s", e)
            return AuthorizationResult(
                allowed=False,
                reason="Authorization check failed",
                policies_evaluated=["permission_based"],
                metadata={"authorizer": "permission", "error": str(e)},
            )

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get user permissions from direct mapping.

        Args:
            user: User to get permissions for

        Returns:
            Set of permission strings
        """
        return set(self.user_permissions.get(user.id, []))


class AttributeBasedAuthorizer(IAuthorizer):
    """
    Attribute-based access control (ABAC) authorizer.

    Grants access based on policies that evaluate attributes of the principal,
    resource, action, and environment. Policies can include complex conditions
    and support pattern matching.

    Attributes:
        abac_manager: ABACManager instance for policy evaluation

    Example:
        authorizer = AttributeBasedAuthorizer()
        context = AuthorizationContext(
            user,
            "/api/v1/transactions/12345",
            "POST",
            environment={"transaction_amount": 15000}
        )
        result = authorizer.authorize(context)
    """

    def __init__(self, abac_manager: ABACManager | None = None):
        """
        Initialize with ABAC manager.

        Args:
            abac_manager: Optional ABACManager instance. If None, uses global manager.
        """
        self.abac_manager = abac_manager or get_abac_manager()

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Authorize based on ABAC policy evaluation.

        Converts authorization context to ABAC context and evaluates
        all applicable policies. First matching policy determines access.

        Args:
            context: Authorization context with user, resource, action, environment

        Returns:
            AuthorizationResult indicating if access is allowed
        """
        try:
            # Convert to ABAC context
            abac_context = self._convert_to_abac_context(context)

            # Evaluate policies
            result = self.abac_manager.evaluate_access(abac_context)

            # Convert ABAC result to authorization result
            allowed = result.decision.value in ["allow", "audit"]

            logger.info(
                "ABAC authorization %s for %s on %s:%s",
                "granted" if allowed else "denied",
                context.user.username,
                context.resource,
                context.action,
            )

            return AuthorizationResult(
                allowed=allowed,
                reason=f"ABAC policy decision: {result.decision.value}",
                policies_evaluated=result.applicable_policies or ["abac"],
                metadata={
                    "authorizer": "abac",
                    "decision": result.decision.value,
                    "applicable_policies": result.applicable_policies,
                    "evaluation_time_ms": result.evaluation_time_ms,
                },
            )

        except Exception as e:
            logger.error("ABAC authorization error: %s", e)
            return AuthorizationResult(
                allowed=False,
                reason="Authorization check failed",
                policies_evaluated=["abac"],
                metadata={"authorizer": "abac", "error": str(e)},
            )

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get permissions based on ABAC policy evaluation.

        Tests common actions against a dummy resource to determine
        which permissions the user would have based on policies.

        Args:
            user: User to get permissions for

        Returns:
            Set of permission strings
        """
        permissions = set()

        # Test common actions
        test_actions = ["read", "write", "delete", "execute", "admin"]

        for action in test_actions:
            context = AuthorizationContext(
                user=user, resource="test_resource", action=action, environment={}
            )

            result = self.authorize(context)
            if result.allowed:
                permissions.add(action)

        return permissions

    def _convert_to_abac_context(self, context: AuthorizationContext) -> ABACContext:
        """
        Convert authorization context to ABAC context.

        Args:
            context: Authorization context

        Returns:
            ABAC context for policy evaluation
        """
        # Build principal attributes from user
        principal = {
            "id": context.user.id,
            "username": context.user.username,
            "roles": list(context.user.roles),
            "department": context.user.metadata.get("department"),
            "user": {
                "department": context.user.metadata.get("department"),
            },
        }

        # Add any additional user metadata
        principal.update(context.user.metadata)

        return ABACContext(
            principal=principal,
            resource=context.resource,
            action=context.action,
            environment=context.environment or {},
        )


class CompositeAuthorizer(IAuthorizer):
    """
    Composite authorizer that combines multiple authorization strategies.

    Supports two strategies:
    - "any": Allow if ANY authorizer allows (OR logic)
    - "all": Allow only if ALL authorizers allow (AND logic)

    Attributes:
        authorizers: List of authorizers to combine
        strategy: Combination strategy ("any" or "all")

    Example:
        # Allow if either RBAC or permission-based allows
        authorizer = CompositeAuthorizer(
            [RoleBasedAuthorizer(), PermissionBasedAuthorizer()],
            strategy="any"
        )

        # Require both RBAC and ABAC to allow
        authorizer = CompositeAuthorizer(
            [RoleBasedAuthorizer(), AttributeBasedAuthorizer()],
            strategy="all"
        )
    """

    def __init__(self, authorizers: list[IAuthorizer], strategy: str = "any"):
        """
        Initialize composite authorizer.

        Args:
            authorizers: List of authorizers to compose
            strategy: "any" (OR logic) or "all" (AND logic)

        Raises:
            ValueError: If strategy is not "any" or "all"
        """
        if strategy not in ["any", "all"]:
            raise ValueError(f"Invalid strategy: {strategy}. Must be 'any' or 'all'")

        self.authorizers = authorizers
        self.strategy = strategy

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Authorize using composite strategy.

        For "any" strategy:
            Returns first allowing result, or combined denial if all deny

        For "all" strategy:
            Returns combined allowance if all allow, or first denial

        Args:
            context: Authorization context

        Returns:
            AuthorizationResult based on composite strategy
        """
        try:
            results = []

            # Evaluate all authorizers
            for authorizer in self.authorizers:
                result = authorizer.authorize(context)
                results.append(result)

            if self.strategy == "any":
                # Allow if any authorizer allows
                for result in results:
                    if result.allowed:
                        result.metadata["composite_strategy"] = "any"
                        result.metadata["authorizers_evaluated"] = len(self.authorizers)
                        logger.info(
                            "Composite (any) authorization granted for %s on %s:%s",
                            context.user.username,
                            context.resource,
                            context.action,
                        )
                        return result

                # All denied
                logger.warning(
                    "Composite (any) authorization denied for %s on %s:%s",
                    context.user.username,
                    context.resource,
                    context.action,
                )
                return AuthorizationResult(
                    allowed=False,
                    reason="All authorizers denied access",
                    policies_evaluated=[r.reason for r in results],
                    metadata={
                        "composite_strategy": "any",
                        "authorizers_evaluated": len(self.authorizers),
                        "all_results": [r.reason for r in results],
                    },
                )

            else:  # strategy == "all"
                # Allow only if all authorizers allow
                for result in results:
                    if not result.allowed:
                        logger.warning(
                            "Composite (all) authorization denied for %s on %s:%s",
                            context.user.username,
                            context.resource,
                            context.action,
                        )
                        return AuthorizationResult(
                            allowed=False,
                            reason=f"Authorizer denied: {result.reason}",
                            policies_evaluated=[r.reason for r in results],
                            metadata={
                                "composite_strategy": "all",
                                "authorizers_evaluated": len(self.authorizers),
                                "failing_reason": result.reason,
                            },
                        )

                # All allowed
                logger.info(
                    "Composite (all) authorization granted for %s on %s:%s",
                    context.user.username,
                    context.resource,
                    context.action,
                )
                return AuthorizationResult(
                    allowed=True,
                    reason="All authorizers allowed access",
                    policies_evaluated=[r.reason for r in results],
                    metadata={
                        "composite_strategy": "all",
                        "authorizers_evaluated": len(self.authorizers),
                    },
                )

        except Exception as e:
            logger.error("Composite authorization error: %s", e)
            return AuthorizationResult(
                allowed=False,
                reason="Authorization check failed",
                policies_evaluated=["composite"],
                metadata={"composite_strategy": self.strategy, "error": str(e)},
            )

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get combined permissions from all authorizers.

        Returns union of all permissions regardless of strategy.

        Args:
            user: User to get permissions for

        Returns:
            Set of all permissions from all authorizers
        """
        all_permissions = set()

        for authorizer in self.authorizers:
            permissions = authorizer.get_user_permissions(user)
            all_permissions.update(permissions)

        return all_permissions


# Factory Functions


def create_role_based_authorizer(
    role_manager: RBACManager | None = None,
) -> RoleBasedAuthorizer:
    """
    Create a role-based authorizer.

    Factory function for creating RBAC authorizers with optional
    custom role manager.

    Args:
        role_manager: Optional RBACManager instance

    Returns:
        Configured RoleBasedAuthorizer

    Example:
        authorizer = create_role_based_authorizer()
    """
    return RoleBasedAuthorizer(role_manager=role_manager)


def create_permission_based_authorizer(
    user_permissions: dict[str, list[str]] | None = None,
) -> PermissionBasedAuthorizer:
    """
    Create a permission-based authorizer.

    Factory function for creating authorizers with direct user-to-permission
    mappings.

    Args:
        user_permissions: Optional mapping of user IDs to permission lists

    Returns:
        Configured PermissionBasedAuthorizer

    Example:
        authorizer = create_permission_based_authorizer({
            "user123": ["documents:read", "documents:write"]
        })
    """
    return PermissionBasedAuthorizer(user_permissions=user_permissions)


def create_attribute_based_authorizer(
    abac_manager: ABACManager | None = None,
) -> AttributeBasedAuthorizer:
    """
    Create an attribute-based authorizer.

    Factory function for creating ABAC authorizers with optional
    custom policy manager.

    Args:
        abac_manager: Optional ABACManager instance

    Returns:
        Configured AttributeBasedAuthorizer

    Example:
        authorizer = create_attribute_based_authorizer()
    """
    return AttributeBasedAuthorizer(abac_manager=abac_manager)


def create_composite_authorizer(
    authorizers: list[IAuthorizer], strategy: str = "any"
) -> CompositeAuthorizer:
    """
    Create a composite authorizer.

    Factory function for creating authorizers that combine multiple
    authorization strategies.

    Args:
        authorizers: List of authorizers to compose
        strategy: "any" (OR logic) or "all" (AND logic)

    Returns:
        Configured CompositeAuthorizer

    Example:
        # Allow if either RBAC or permission-based allows
        authorizer = create_composite_authorizer([
            create_role_based_authorizer(),
            create_permission_based_authorizer()
        ], strategy="any")
    """
    return CompositeAuthorizer(authorizers=authorizers, strategy=strategy)


__all__ = [
    "RoleBasedAuthorizer",
    "PermissionBasedAuthorizer",
    "AttributeBasedAuthorizer",
    "CompositeAuthorizer",
    "create_role_based_authorizer",
    "create_permission_based_authorizer",
    "create_attribute_based_authorizer",
    "create_composite_authorizer",
]
