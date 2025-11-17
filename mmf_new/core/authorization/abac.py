"""
ABAC (Attribute-Based Access Control) System

Comprehensive attribute-based access control with policy evaluation,
context-aware decisions, and integration with external policy engines.

Key Features:
- Attribute-based policy evaluation with complex conditions
- Context-aware access decisions (principal, resource, action, environment)
- Policy priority and conflict resolution
- Pattern matching for resources and actions (wildcards, regex)
- Multiple condition operators (equals, comparison, contains, regex, etc.)
- Policy caching for performance optimization
- Configuration-based policy loading and export
- Policy testing with multiple contexts
- Default policies (admin access, business hours, high-value transactions)

Architecture:
- AttributeCondition: Evaluates conditions on attributes using operators
- ABACPolicy: Policy definition with conditions, effect, and patterns
- ABACContext: Context for policy evaluation (principal, resource, action, environment)
- PolicyEvaluationResult: Result of policy evaluation with metadata
- ABACManager: Central manager for policy lifecycle and evaluation
- ABACManagerService: DI-compatible service wrapper

Policy Evaluation:
1. Filter applicable policies by resource/action patterns
2. Sort by priority (lower number = higher priority)
3. Evaluate conditions in priority order
4. First matching policy determines decision
5. Default to DENY if no policies match

Condition Operators:
- Equality: EQUALS, NOT_EQUALS
- Comparison: GREATER_THAN, LESS_THAN, GREATER_EQUAL, LESS_EQUAL
- Membership: IN, NOT_IN, CONTAINS
- String: STARTS_WITH, ENDS_WITH, REGEX
- Existence: EXISTS, NOT_EXISTS
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from marty_msf.core.enhanced_di import LambdaFactory, get_service, register_service
from marty_msf.security_core.exceptions import AuthorizationError

from .api import AttributeType, ConditionOperator, PolicyEffect

logger = logging.getLogger(__name__)


@dataclass
class AttributeCondition:
    """
    Represents a condition on an attribute in ABAC policy.

    Evaluates conditions against context attributes using dot-notation paths
    and various operators. Supports nested attribute access and type-aware
    comparisons.

    Attributes:
        attribute_path: Dot-notation path to attribute (e.g., "principal.department")
        operator: Comparison operator to apply
        value: Expected value for comparison
        description: Human-readable condition description

    Examples:
        AttributeCondition("principal.department", ConditionOperator.EQUALS, "finance")
        AttributeCondition("environment.time_of_day", ConditionOperator.GREATER_THAN, 9)
        AttributeCondition("principal.roles", ConditionOperator.CONTAINS, "admin")
    """

    attribute_path: str
    operator: ConditionOperator
    value: Any
    description: str | None = None

    def evaluate(self, context: dict[str, Any]) -> bool:
        """
        Evaluate condition against context.

        Extracts attribute value from context using dot-notation path,
        then applies operator to compare against expected value.

        Args:
            context: Evaluation context with nested attributes

        Returns:
            True if condition evaluates to true, False otherwise

        Note:
            Missing attributes or evaluation errors return False
        """
        try:
            actual_value = self._get_attribute_value(context, self.attribute_path)
            return self._apply_operator(actual_value, self.operator, self.value)
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Condition evaluation failed for %s: %s", self.attribute_path, e)
            return False

    def _get_attribute_value(self, context: dict[str, Any], path: str) -> Any:
        """
        Get attribute value from context using dot notation.

        Traverses nested dictionaries using dot-separated path.
        Returns None if path doesn't exist.

        Args:
            context: Context dictionary
            path: Dot-notation path (e.g., "principal.user.department")

        Returns:
            Attribute value or None if not found
        """
        keys = path.split(".")
        value = context

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _apply_operator(self, actual: Any, operator: ConditionOperator, expected: Any) -> bool:
        """
        Apply operator to compare actual and expected values.

        Handles type-aware comparisons and special operators like
        regex matching, containment checks, and existence tests.

        Args:
            actual: Actual value from context
            operator: Comparison operator
            expected: Expected value from condition

        Returns:
            True if comparison succeeds, False otherwise
        """
        # Existence checks don't require actual value
        if operator == ConditionOperator.EXISTS:
            return actual is not None
        elif operator == ConditionOperator.NOT_EXISTS:
            return actual is None

        # All other operators require non-None actual value
        if actual is None:
            return False

        if operator == ConditionOperator.EQUALS:
            return actual == expected
        elif operator == ConditionOperator.NOT_EQUALS:
            return actual != expected
        elif operator == ConditionOperator.GREATER_THAN:
            return actual > expected
        elif operator == ConditionOperator.LESS_THAN:
            return actual < expected
        elif operator == ConditionOperator.GREATER_EQUAL:
            return actual >= expected
        elif operator == ConditionOperator.LESS_EQUAL:
            return actual <= expected
        elif operator == ConditionOperator.IN:
            return actual in expected if isinstance(expected, list | set | tuple) else False
        elif operator == ConditionOperator.NOT_IN:
            return actual not in expected if isinstance(expected, list | set | tuple) else True
        elif operator == ConditionOperator.CONTAINS:
            return expected in actual if hasattr(actual, "__contains__") else False
        elif operator == ConditionOperator.STARTS_WITH:
            return str(actual).startswith(str(expected))
        elif operator == ConditionOperator.ENDS_WITH:
            return str(actual).endswith(str(expected))
        elif operator == ConditionOperator.REGEX:
            return bool(re.match(str(expected), str(actual)))

        return False


@dataclass
class ABACPolicy:
    """
    Represents an ABAC policy with conditions and effect.

    A policy defines access control rules based on attributes of the principal,
    resource, action, and environment. Policies can be scoped to specific
    resource and action patterns, and are evaluated in priority order.

    Attributes:
        id: Unique policy identifier
        name: Human-readable policy name
        description: Policy purpose description
        effect: Policy effect (ALLOW, DENY, AUDIT)
        conditions: List of conditions that must all be true
        resource_pattern: Pattern for resources (supports wildcards/regex)
        action_pattern: Pattern for actions (supports wildcards/regex)
        priority: Evaluation priority (lower = higher priority)
        is_active: If False, policy is not evaluated
        metadata: Additional policy metadata
        created_at: Policy creation timestamp

    Pattern Matching:
        - "*" matches any value
        - "prefix*" matches values starting with prefix
        - "/regex/" matches values against regex pattern
        - Exact string matches without wildcards

    Evaluation:
        All conditions must evaluate to true for policy to apply.
        First matching policy by priority determines access decision.
    """

    id: str
    name: str
    description: str
    effect: PolicyEffect
    conditions: list[AttributeCondition] = field(default_factory=list)
    resource_pattern: str | None = None
    action_pattern: str | None = None
    priority: int = 100
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate policy has required fields."""
        if not self.id or not self.name:
            raise ValueError("Policy ID and name are required")

    def matches_request(self, resource: str, action: str) -> bool:
        """
        Check if policy applies to the given resource and action.

        Uses pattern matching to determine if policy is applicable
        to the specific resource and action in the request.

        Args:
            resource: Resource being accessed
            action: Action being performed

        Returns:
            True if policy patterns match request
        """
        if self.resource_pattern and not self._matches_pattern(self.resource_pattern, resource):
            return False

        if self.action_pattern and not self._matches_pattern(self.action_pattern, action):
            return False

        return True

    def evaluate(self, context: dict[str, Any]) -> bool:
        """
        Evaluate all conditions against context.

        All conditions must evaluate to true for policy to apply.
        Inactive policies always return False.

        Args:
            context: Evaluation context with attributes

        Returns:
            True if all conditions pass, False otherwise
        """
        if not self.is_active:
            return False

        # All conditions must be true for policy to apply
        for condition in self.conditions:
            if not condition.evaluate(context):
                return False

        return True

    def _matches_pattern(self, pattern: str, value: str) -> bool:
        """
        Check if value matches pattern.

        Supports:
        - Wildcard: "*" matches any, "prefix*" matches prefix
        - Regex: "/pattern/" for regex matching
        - Exact: Direct string comparison

        Args:
            pattern: Pattern to match against
            value: Value to test

        Returns:
            True if value matches pattern
        """
        if pattern == "*":
            return True

        # Simple wildcard support
        if "*" in pattern:
            regex_pattern = pattern.replace("*", ".*")
            return bool(re.match(regex_pattern, value))

        # Check if it's a regex pattern (starts with / and ends with /)
        if pattern.startswith("/") and pattern.endswith("/"):
            regex_pattern = pattern[1:-1]
            return bool(re.match(regex_pattern, value))

        return pattern == value

    def to_dict(self) -> dict[str, Any]:
        """
        Convert policy to dictionary representation.

        Suitable for serialization, storage, or API responses.

        Returns:
            Dictionary with all policy attributes
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "effect": self.effect.value,
            "conditions": [
                {
                    "attribute_path": c.attribute_path,
                    "operator": c.operator.value,
                    "value": c.value,
                    "description": c.description,
                }
                for c in self.conditions
            ],
            "resource_pattern": self.resource_pattern,
            "action_pattern": self.action_pattern,
            "priority": self.priority,
            "is_active": self.is_active,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ABACContext:
    """
    Context for ABAC policy evaluation.

    Contains all attributes needed for policy evaluation: principal
    information, resource being accessed, action being performed,
    and environmental context.

    Attributes:
        principal: Principal attributes (user ID, roles, department, etc.)
        resource: Resource identifier or pattern
        action: Action being performed (read, write, delete, etc.)
        environment: Environmental attributes (time, location, IP, etc.)

    Example:
        context = ABACContext(
            principal={"id": "user123", "roles": ["admin"], "department": "finance"},
            resource="/api/v1/transactions/12345",
            action="POST",
            environment={"time_of_day": 14, "business_hours": True}
        )
    """

    principal: dict[str, Any]
    resource: str
    action: str
    environment: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """
        Convert context to dictionary for policy evaluation.

        Returns:
            Dictionary with all context attributes
        """
        return {
            "principal": self.principal,
            "resource": self.resource,
            "action": self.action,
            "environment": self.environment,
        }


@dataclass
class PolicyEvaluationResult:
    """
    Result of ABAC policy evaluation.

    Contains the access decision, applicable policies, performance metrics,
    and any errors encountered during evaluation.

    Attributes:
        decision: Policy effect (ALLOW, DENY, AUDIT)
        applicable_policies: List of policy IDs that matched
        evaluation_time_ms: Time taken to evaluate in milliseconds
        context_snapshot: Copy of evaluation context for audit
        error: Error message if evaluation failed
    """

    decision: PolicyEffect
    applicable_policies: list[str] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    context_snapshot: dict[str, Any] | None = None
    error: str | None = None


class ABACManager:
    """
    Comprehensive ABAC management system.

    Central manager for attribute-based access control, handling:
    - Policy lifecycle (create, update, delete)
    - Policy evaluation with context
    - Pattern matching for resources and actions
    - Priority-based policy resolution
    - Result caching for performance
    - Configuration-based policy management

    Policy Evaluation Process:
    1. Filter policies by resource/action patterns
    2. Sort by priority (lower number = higher priority)
    3. Evaluate conditions in priority order
    4. First matching policy determines decision
    5. Cache result for performance

    Default Policies:
    - admin_access: Admins have full access (priority 10)
    - business_hours_sensitive: Sensitive operations during business hours (priority 50)
    - high_value_transaction: High-value transactions require manager approval (priority 30)
    - default_deny: Deny all access by default (priority 1000)

    Thread Safety:
        This implementation is not thread-safe. For concurrent access,
        external synchronization is required.

    Performance:
        - Results are cached by context hash
        - Cache is invalidated on policy changes
        - Configurable cache enable/disable
    """

    def __init__(self):
        """Initialize ABAC manager with default policies."""
        self.policies: dict[str, ABACPolicy] = {}
        self.policy_cache: dict[str, PolicyEvaluationResult] = {}
        self.cache_enabled = True
        self.default_effect = PolicyEffect.DENY

        self._initialize_default_policies()

    def _initialize_default_policies(self):
        """
        Create default ABAC policies.

        Default policies provide baseline access control:
        - Admin full access
        - Business hours restrictions for sensitive operations
        - High-value transaction approval requirements
        - Default deny for unmatched requests
        """
        # Admin access policy
        admin_policy = ABACPolicy(
            id="admin_access",
            name="Admin Full Access",
            description="Administrators have full access to all resources",
            effect=PolicyEffect.ALLOW,
            priority=10,
        )
        admin_policy.conditions.append(
            AttributeCondition(
                attribute_path="principal.roles",
                operator=ConditionOperator.CONTAINS,
                value="admin",
                description="User must have admin role",
            )
        )
        self.add_policy(admin_policy)

        # Business hours policy
        business_hours_policy = ABACPolicy(
            id="business_hours_sensitive",
            name="Sensitive Operations During Business Hours",
            description="Sensitive operations only allowed during business hours",
            effect=PolicyEffect.ALLOW,
            resource_pattern="/api/v1/sensitive/*",
            priority=50,
        )
        business_hours_policy.conditions.extend(
            [
                AttributeCondition(
                    attribute_path="environment.business_hours",
                    operator=ConditionOperator.EQUALS,
                    value=True,
                    description="Must be during business hours",
                ),
                AttributeCondition(
                    attribute_path="principal.department",
                    operator=ConditionOperator.IN,
                    value=["finance", "admin"],
                    description="Must be in authorized department",
                ),
            ]
        )
        self.add_policy(business_hours_policy)

        # High-value transaction policy
        high_value_transaction = ABACPolicy(
            id="high_value_transaction",
            name="High Value Transaction Approval",
            description="High value transactions require manager approval",
            effect=PolicyEffect.ALLOW,
            resource_pattern="/api/v1/transactions/*",
            action_pattern="POST",
            priority=30,
        )
        high_value_transaction.conditions.extend(
            [
                AttributeCondition(
                    attribute_path="environment.transaction_amount",
                    operator=ConditionOperator.GREATER_THAN,
                    value=10000,
                    description="Transaction amount exceeds threshold",
                ),
                AttributeCondition(
                    attribute_path="principal.roles",
                    operator=ConditionOperator.CONTAINS,
                    value="finance_manager",
                    description="Must have finance manager role",
                ),
            ]
        )
        self.add_policy(high_value_transaction)

        # Default deny policy (lowest priority)
        default_deny = ABACPolicy(
            id="default_deny",
            name="Default Deny",
            description="Default deny all access",
            effect=PolicyEffect.DENY,
            priority=1000,
        )
        self.add_policy(default_deny)

        logger.info("Initialized default ABAC policies")

    def add_policy(self, policy: ABACPolicy) -> bool:
        """
        Add a new ABAC policy.

        Validates policy uniqueness and adds to policy store.
        Clears cache to ensure fresh evaluation.

        Args:
            policy: Policy to add

        Returns:
            True if added successfully, False on error

        Raises:
            ValueError: If policy ID already exists
        """
        try:
            if policy.id in self.policies:
                raise ValueError(f"Policy '{policy.id}' already exists")

            self.policies[policy.id] = policy
            self._clear_cache()

            logger.info("Added ABAC policy: %s", policy.id)
            return True

        except (ValueError, TypeError) as e:
            logger.error("Failed to add ABAC policy %s: %s", policy.id, e)
            return False

    def remove_policy(self, policy_id: str) -> bool:
        """
        Remove an ABAC policy.

        Removes policy from store and clears cache.

        Args:
            policy_id: ID of policy to remove

        Returns:
            True if removed, False if not found
        """
        try:
            if policy_id in self.policies:
                del self.policies[policy_id]
                self._clear_cache()
                logger.info("Removed ABAC policy: %s", policy_id)
                return True
            return False

        except (KeyError, ValueError) as e:
            logger.error("Failed to remove ABAC policy %s: %s", policy_id, e)
            return False

    def evaluate_access(self, context: ABACContext) -> PolicyEvaluationResult:
        """
        Evaluate access request against ABAC policies.

        Process:
        1. Check cache for previous evaluation
        2. Filter applicable policies by resource/action patterns
        3. Sort policies by priority (lower = higher priority)
        4. Evaluate conditions in priority order
        5. First matching policy determines decision
        6. Cache result for future requests

        Args:
            context: Evaluation context with all attributes

        Returns:
            PolicyEvaluationResult with decision and metadata
        """
        start_time = datetime.now()

        try:
            # Check cache
            cache_key = self._get_cache_key(context)
            if self.cache_enabled and cache_key in self.policy_cache:
                return self.policy_cache[cache_key]

            # Get applicable policies sorted by priority
            applicable_policies = self._get_applicable_policies(context.resource, context.action)
            applicable_policies.sort(key=lambda p: p.priority)

            evaluation_context = context.to_dict()
            decision = self.default_effect
            matched_policies = []

            # Evaluate policies in priority order
            for policy in applicable_policies:
                if policy.evaluate(evaluation_context):
                    matched_policies.append(policy.id)
                    decision = policy.effect

                    # First matching policy determines decision
                    break

            # Calculate evaluation time
            evaluation_time = (datetime.now() - start_time).total_seconds() * 1000

            result = PolicyEvaluationResult(
                decision=decision,
                applicable_policies=matched_policies,
                evaluation_time_ms=evaluation_time,
                context_snapshot=evaluation_context,
            )

            # Cache result
            if self.cache_enabled:
                self.policy_cache[cache_key] = result

            logger.debug(
                "ABAC evaluation: %s for %s on %s (%sms, %d policies matched)",
                decision.value,
                context.action,
                context.resource,
                f"{evaluation_time:.2f}",
                len(matched_policies),
            )

            return result

        except (ValueError, TypeError, KeyError) as e:
            logger.error("ABAC evaluation failed: %s", e)
            return PolicyEvaluationResult(decision=PolicyEffect.DENY, error=str(e))

    def check_access(
        self,
        principal: dict[str, Any],
        resource: str,
        action: str,
        environment: dict[str, Any] | None = None,
    ) -> bool:
        """
        Check if access should be allowed.

        Convenience method for simple allow/deny decision.

        Args:
            principal: Principal attributes
            resource: Resource identifier
            action: Action to perform
            environment: Optional environmental attributes

        Returns:
            True if access allowed (ALLOW or AUDIT), False otherwise
        """
        context = ABACContext(
            principal=principal, resource=resource, action=action, environment=environment or {}
        )

        result = self.evaluate_access(context)
        return result.decision in [PolicyEffect.ALLOW, PolicyEffect.AUDIT]

    def require_access(
        self,
        principal: dict[str, Any],
        resource: str,
        action: str,
        environment: dict[str, Any] | None = None,
    ):
        """
        Require access or raise AuthorizationError.

        Convenience method for enforcing access control.

        Args:
            principal: Principal attributes
            resource: Resource identifier
            action: Action to perform
            environment: Optional environmental attributes

        Raises:
            AuthorizationError: If access denied
        """
        if not self.check_access(principal, resource, action, environment):
            raise AuthorizationError(
                f"ABAC policy denied access to {action} on {resource}",
                resource=resource,
                action=action,
                context={"principal": principal, "environment": environment or {}},
            )

    def _get_applicable_policies(self, resource: str, action: str) -> list[ABACPolicy]:
        """
        Get policies that apply to the given resource and action.

        Filters policies by active status and pattern matching.

        Args:
            resource: Resource identifier
            action: Action being performed

        Returns:
            List of applicable policies
        """
        applicable = []

        for policy in self.policies.values():
            if policy.is_active and policy.matches_request(resource, action):
                applicable.append(policy)

        return applicable

    def _get_cache_key(self, context: ABACContext) -> str:
        """
        Generate cache key for context.

        Uses hash of sorted JSON representation for consistency.

        Args:
            context: Evaluation context

        Returns:
            Cache key string
        """
        context_str = json.dumps(context.to_dict(), sort_keys=True)
        return f"abac:{hash(context_str)}"

    def _clear_cache(self):
        """Clear policy evaluation cache."""
        self.policy_cache.clear()

    def load_policies_from_config(self, config_data: dict[str, Any]) -> bool:
        """
        Load ABAC policies from configuration.

        Config format:
        {
            "policies": [
                {
                    "id": "policy_id",
                    "name": "Policy Name",
                    "description": "Description",
                    "effect": "allow",
                    "resource_pattern": "/api/v1/*",
                    "action_pattern": "POST",
                    "priority": 100,
                    "conditions": [
                        {
                            "attribute_path": "principal.department",
                            "operator": "equals",
                            "value": "finance"
                        }
                    ]
                }
            ]
        }

        Args:
            config_data: Configuration dictionary

        Returns:
            True if loaded successfully, False on error
        """
        try:
            policies_data = config_data.get("policies", [])

            for policy_data in policies_data:
                policy = ABACPolicy(
                    id=policy_data["id"],
                    name=policy_data["name"],
                    description=policy_data["description"],
                    effect=PolicyEffect(policy_data["effect"]),
                    resource_pattern=policy_data.get("resource_pattern"),
                    action_pattern=policy_data.get("action_pattern"),
                    priority=policy_data.get("priority", 100),
                    is_active=policy_data.get("is_active", True),
                    metadata=policy_data.get("metadata", {}),
                )

                # Load conditions
                for condition_data in policy_data.get("conditions", []):
                    condition = AttributeCondition(
                        attribute_path=condition_data["attribute_path"],
                        operator=ConditionOperator(condition_data["operator"]),
                        value=condition_data["value"],
                        description=condition_data.get("description"),
                    )
                    policy.conditions.append(condition)

                self.add_policy(policy)

            logger.info("Loaded %d ABAC policies from configuration", len(policies_data))
            return True

        except (ValueError, KeyError, TypeError) as e:
            logger.error("Failed to load ABAC policies from config: %s", e)
            return False

    def export_policies_to_config(self) -> dict[str, Any]:
        """
        Export ABAC policies to configuration format.

        Returns:
            Configuration dictionary with all policies
        """
        policies_data = []

        for policy in self.policies.values():
            policies_data.append(policy.to_dict())

        return {"policies": policies_data}

    def get_policy_info(self, policy_id: str) -> dict[str, Any] | None:
        """
        Get detailed information about a policy.

        Args:
            policy_id: Policy identifier

        Returns:
            Policy information dictionary or None if not found
        """
        if policy_id not in self.policies:
            return None

        return self.policies[policy_id].to_dict()

    def list_policies(self, active_only: bool = False) -> list[dict[str, Any]]:
        """
        List all ABAC policies.

        Args:
            active_only: If True, only include active policies

        Returns:
            List of policy dictionaries sorted by priority
        """
        policies = []
        for policy in self.policies.values():
            if not active_only or policy.is_active:
                policies.append(policy.to_dict())

        return sorted(policies, key=lambda p: p["priority"])

    def test_policy(
        self, policy_id: str, test_contexts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Test a policy against multiple contexts.

        Useful for validating policy behavior and debugging conditions.

        Args:
            policy_id: Policy to test
            test_contexts: List of context dictionaries to test

        Returns:
            List of test results with outcomes

        Raises:
            ValueError: If policy not found
        """
        if policy_id not in self.policies:
            raise ValueError(f"Policy '{policy_id}' not found")

        policy = self.policies[policy_id]
        results = []

        for i, context_data in enumerate(test_contexts):
            try:
                context = ABACContext(
                    principal=context_data.get("principal", {}),
                    resource=context_data.get("resource", ""),
                    action=context_data.get("action", ""),
                    environment=context_data.get("environment", {}),
                )

                matches = policy.matches_request(context.resource, context.action)
                evaluates = policy.evaluate(context.to_dict()) if matches else False

                results.append(
                    {
                        "test_case": i + 1,
                        "context": context_data,
                        "matches_request": matches,
                        "conditions_pass": evaluates,
                        "would_apply": matches and evaluates,
                    }
                )

            except (ValueError, KeyError, TypeError) as e:
                results.append({"test_case": i + 1, "context": context_data, "error": str(e)})

        return results


class ABACManagerService:
    """
    Service wrapper for ABAC manager.

    Provides DI container integration for ABACManager.
    Registered as singleton in the DI container.
    """

    def __init__(self):
        """Initialize service with new ABACManager instance."""
        self._manager = ABACManager()

    def get_manager(self) -> ABACManager:
        """Get the ABAC manager instance."""
        return self._manager


def get_abac_manager() -> ABACManager:
    """
    Get ABAC manager instance from the DI container.

    Returns:
        Singleton ABACManager instance
    """
    service = get_service(ABACManagerService)
    return service.get_manager()


def reset_abac_manager():
    """
    Reset ABAC manager (not supported).

    ABAC manager lifecycle is controlled by the DI container.
    Use container lifecycle management for reset operations.

    Raises:
        NotImplementedError: Always raised
    """
    raise NotImplementedError(
        "reset_abac_manager is not supported. Use the DI container lifecycle management instead."
    )


# Register the service as singleton
register_service(
    ABACManagerService,
    factory=LambdaFactory(ABACManagerService, lambda _: ABACManagerService()),
    is_singleton=True,
)


__all__ = [
    "AttributeCondition",
    "ABACPolicy",
    "ABACContext",
    "ABACManager",
    "PolicyEvaluationResult",
    "AttributeType",
    "PolicyEffect",
    "ConditionOperator",
    "ABACManagerService",
    "get_abac_manager",
    "reset_abac_manager",
]
