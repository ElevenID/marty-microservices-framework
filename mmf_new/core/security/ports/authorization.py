"""
Authorization Ports

This module defines interfaces for authorization providers.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..domain.models.context import AuthorizationContext, SecurityContext
from ..domain.models.result import AuthorizationResult, PolicyResult
from ..domain.models.user import User


@runtime_checkable
class IAuthorizer(Protocol):
    """Interface for authorization providers."""

    def authorize(self, context: AuthorizationContext) -> AuthorizationResult:
        """
        Check if a user is authorized for a specific action on a resource.

        Args:
            context: Authorization context containing user, resource, and action

        Returns:
            AuthorizationResult indicating if access is allowed
        """
        ...

    def get_user_permissions(self, user: User) -> set[str]:
        """
        Get all permissions for a user.

        Args:
            user: User to get permissions for

        Returns:
            Set of permission strings
        """
        ...


@runtime_checkable
class IPolicyEngine(Protocol):
    """Interface for policy engines."""

    def evaluate_policy(self, context: SecurityContext) -> PolicyResult:
        """
        Evaluate a policy for the given context.

        Args:
            context: Security context for evaluation

        Returns:
            PolicyResult indicating the decision
        """
        ...

    def load_policies(self, policies: dict[str, Any]) -> bool:
        """
        Load policies into the engine.

        Args:
            policies: Policy definitions to load

        Returns:
            True if successfully loaded
        """
        ...

    def validate_policies(self) -> list[str]:
        """
        Validate loaded policies.

        Returns:
            List of validation errors (empty if valid)
        """
        ...
