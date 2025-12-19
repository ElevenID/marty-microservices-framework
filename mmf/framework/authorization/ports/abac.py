"""
ABAC Ports - Protocol-based interfaces for ABAC system.

This module defines the abstractions for Attribute-Based Access Control,
following hexagonal architecture principles. Each protocol represents a
single responsibility, enabling flexible composition and testing.

Architecture:
    ┌──────────────────────────────────────────────────────────────┐
    │                     Application Layer                        │
    │  (Use cases that orchestrate ABAC operations)                │
    └───────────────────────────┬──────────────────────────────────┘
                                │
    ┌───────────────────────────▼──────────────────────────────────┐
    │                       Ports Layer                            │
    │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
    │  │ IPolicyRepo     │  │ IPolicyEvaluator│  │ ICondition   │  │
    │  │ (Storage)       │  │ (Decision Logic)│  │ (Evaluation) │  │
    │  └─────────────────┘  └─────────────────┘  └──────────────┘  │
    └──────────────────────────────────────────────────────────────┘
                                │
    ┌───────────────────────────▼──────────────────────────────────┐
    │                     Adapters Layer                           │
    │  (Implementations: InMemoryPolicyRepository,                 │
    │   ABACPolicyEvaluator, AttributeConditionEvaluator)          │
    └──────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from mmf.framework.authorization.api import PolicyEffect


@runtime_checkable
class IConditionEvaluator(Protocol):
    """
    Protocol for evaluating conditions against a context.

    Single Responsibility: Evaluate a single condition against a context.
    """

    def evaluate(self, context: dict[str, Any]) -> bool:
        """
        Evaluate condition against context.

        Args:
            context: Dictionary containing attributes to evaluate against

        Returns:
            True if condition is satisfied, False otherwise
        """
        ...


@runtime_checkable
class IPolicyMatcher(Protocol):
    """
    Protocol for checking if a policy matches a request.

    Single Responsibility: Determine if a policy applies to a given
    resource/action combination.
    """

    def matches_request(self, resource: str, action: str) -> bool:
        """
        Check if policy matches the given resource and action.

        Args:
            resource: Resource identifier being accessed
            action: Action being performed

        Returns:
            True if policy applies to this request
        """
        ...

    def evaluate(self, context: dict[str, Any]) -> bool:
        """
        Evaluate policy conditions against context.

        Args:
            context: Evaluation context with all attributes

        Returns:
            True if all conditions pass
        """
        ...


@runtime_checkable
class IABACPolicy(Protocol):
    """
    Protocol representing an ABAC policy.

    Combines matching and evaluation capabilities with policy metadata.
    """

    @property
    def id(self) -> str:
        """Unique policy identifier."""
        ...

    @property
    def priority(self) -> int:
        """Policy priority (lower = higher priority)."""
        ...

    @property
    def effect(self) -> PolicyEffect:
        """Policy effect when conditions match."""
        ...

    @property
    def is_active(self) -> bool:
        """Whether policy is currently active."""
        ...

    def matches_request(self, resource: str, action: str) -> bool:
        """Check if policy matches request."""
        ...

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate policy conditions."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        ...


@runtime_checkable
class IPolicyRepository(Protocol):
    """
    Protocol for policy storage and retrieval.

    Single Responsibility: CRUD operations for policies.
    """

    def add_policy(self, policy: IABACPolicy) -> bool:
        """
        Add a new policy to the repository.

        Args:
            policy: Policy to add

        Returns:
            True if added successfully

        Raises:
            ValueError: If policy with same ID exists
        """
        ...

    def remove_policy(self, policy_id: str) -> bool:
        """
        Remove a policy by ID.

        Args:
            policy_id: ID of policy to remove

        Returns:
            True if removed, False if not found
        """
        ...

    def get_policy(self, policy_id: str) -> IABACPolicy | None:
        """
        Get a policy by ID.

        Args:
            policy_id: Policy identifier

        Returns:
            Policy if found, None otherwise
        """
        ...

    def list_policies(self, active_only: bool = False) -> list[IABACPolicy]:
        """
        List all policies.

        Args:
            active_only: If True, only return active policies

        Returns:
            List of policies sorted by priority
        """
        ...


@runtime_checkable
class IPolicyEvaluator(Protocol):
    """
    Protocol for policy evaluation.

    Single Responsibility: Evaluate access requests against policies.
    """

    def evaluate_access(
        self,
        principal: dict[str, Any],
        resource: str,
        action: str,
        environment: dict[str, Any] | None = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluate access request against policies.

        Args:
            principal: Principal attributes (user, roles, etc.)
            resource: Resource being accessed
            action: Action being performed
            environment: Environmental context

        Returns:
            Evaluation result with decision and metadata
        """
        ...


@runtime_checkable
class IPolicyCache(Protocol):
    """
    Protocol for policy evaluation caching.

    Single Responsibility: Cache and retrieve policy evaluation results.
    """

    def get(self, key: str) -> PolicyEvaluationResult | None:
        """
        Get cached result.

        Args:
            key: Cache key

        Returns:
            Cached result or None if not found
        """
        ...

    def set(self, key: str, result: PolicyEvaluationResult) -> None:
        """
        Cache a result.

        Args:
            key: Cache key
            result: Result to cache
        """
        ...

    def invalidate(self) -> None:
        """Invalidate all cached results."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether caching is enabled."""
        ...


# Import result type for type hints (avoiding circular imports)
from dataclasses import dataclass, field


@dataclass
class PolicyEvaluationResult:
    """
    Result of ABAC policy evaluation.

    Contains the access decision, applicable policies, performance metrics,
    and any errors encountered during evaluation.
    """

    decision: PolicyEffect
    applicable_policies: list[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    context_snapshot: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class ABACContext:
    """
    Context for ABAC policy evaluation.

    Contains all attributes needed for policy evaluation.
    """

    principal: dict[str, Any]
    resource: str
    action: str
    environment: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "principal": self.principal,
            "resource": self.resource,
            "action": self.action,
            "environment": self.environment,
        }


__all__ = [
    "IConditionEvaluator",
    "IPolicyMatcher",
    "IABACPolicy",
    "IPolicyRepository",
    "IPolicyEvaluator",
    "IPolicyCache",
    "PolicyEvaluationResult",
    "ABACContext",
]
