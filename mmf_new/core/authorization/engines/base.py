"""
Base Policy Engine Module

Defines abstract base class and core types for policy engines.
Re-exports SecurityContext and SecurityDecision from security_core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

__all__ = [
    "AbstractPolicyEngine",
    "SecurityContext",
    "SecurityDecision",
    "SecurityPrincipal",
]


@dataclass
class SecurityPrincipal:
    """
    Represents a security principal (user, service, device).

    Attributes:
        id: Unique identifier for the principal
        type: Principal type (user, service, device)
        roles: Set of assigned roles
        attributes: Additional principal attributes for ABAC
        permissions: Explicit permissions granted
        created_at: When the principal was created
        identity_provider: Source of authentication
        session_id: Current session identifier
        expires_at: When the principal's credentials expire
    """

    id: str
    type: str  # user, service, device
    roles: set[str] = field(default_factory=set)
    attributes: dict[str, Any] = field(default_factory=dict)
    permissions: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    identity_provider: str | None = None
    session_id: str | None = None
    expires_at: datetime | None = None


@dataclass
class SecurityContext:
    """
    Context for security policy evaluation.

    Contains all information needed to make an authorization decision,
    including principal identity, resource being accessed, action being
    performed, and environmental context.

    Attributes:
        principal: Security principal requesting access
        resource: Resource being accessed
        action: Action being performed
        environment: Environmental attributes (time, location, etc.)
        request_metadata: Additional request context
        request_id: Request correlation ID
        timestamp: When the request was made
    """

    principal: SecurityPrincipal
    resource: str
    action: str
    environment: dict[str, Any] = field(default_factory=dict)
    request_metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SecurityDecision:
    """
    Result of a security policy evaluation.

    Contains the authorization decision along with metadata about
    how the decision was made and what policies were evaluated.

    Attributes:
        allowed: Whether access is granted
        reason: Human-readable explanation of the decision
        policies_evaluated: List of policies that were evaluated
        required_attributes: Attributes needed for access
        metadata: Additional decision metadata
        evaluation_time_ms: Time taken to evaluate (milliseconds)
        cache_key: Key for caching this decision
    """

    allowed: bool
    reason: str
    policies_evaluated: list[str] = field(default_factory=list)
    required_attributes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluation_time_ms: float = 0.0
    cache_key: str | None = None


class AbstractPolicyEngine(ABC):
    """
    Abstract base class for policy engines.

    Policy engines evaluate security policies to make authorization decisions.
    Different engines support different policy languages and evaluation strategies:
    - Builtin: JSON-based policies with wildcard matching
    - ACL: Resource-level access control lists
    - OPA: Open Policy Agent (Rego policies)
    - Oso: Oso authorization library (Polar policies)

    All engines must implement:
    - evaluate_policy: Evaluate a policy against a security context
    - load_policies: Load policy definitions
    - validate_policies: Validate policy syntax and semantics
    """

    @abstractmethod
    async def evaluate_policy(self, context: SecurityContext) -> SecurityDecision:
        """
        Evaluate security policy against context.

        Args:
            context: Security context with principal, resource, action

        Returns:
            SecurityDecision indicating if access is allowed
        """
        pass

    @abstractmethod
    async def load_policies(self, policies: list[dict[str, Any]]) -> bool:
        """
        Load security policies into the engine.

        Args:
            policies: List of policy definitions

        Returns:
            True if policies loaded successfully, False otherwise
        """
        pass

    @abstractmethod
    async def validate_policies(self) -> list[str]:
        """
        Validate loaded policies and return any errors.

        Returns:
            List of validation error messages (empty if valid)
        """
        pass
