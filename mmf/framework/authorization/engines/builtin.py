"""
Built-in Policy Engine Implementation

Provides a simple, efficient policy engine for basic RBAC and ABAC policies
without external dependencies. Supports JSON-based policy definitions with
wildcard matching and condition evaluation.

Features:
- JSON-based policy definitions
- Wildcard pattern matching for resources and actions
- Role-based access control (RBAC)
- Attribute-based conditions
- Time-based and environment-based conditions
- Policy caching for performance

Policy Format:
    {
        "name": "policy_name",
        "resource": "resource:pattern:*",
        "action": "read|write",
        "principal": {
            "roles": ["admin", "user"],
            "type": "user",
            "attributes": {"department": "engineering"}
        },
        "environment": {
            "time_range": {"start": "09:00", "end": "17:00"}
        },
        "condition": {
            "type": "attribute_based",
            "attributes": {"clearance_level": "high"}
        },
        "effect": "allow"
    }
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from .base import AbstractPolicyEngine, SecurityContext, SecurityDecision

logger = logging.getLogger(__name__)

__all__ = ["BuiltinPolicyEngine"]


class BuiltinPolicyEngine(AbstractPolicyEngine):
    """
    Built-in policy engine with JSON-based policy definitions.

    Provides efficient policy evaluation without external dependencies.
    Supports wildcard matching, role-based access, and attribute conditions.

    Attributes:
        config: Engine configuration
        policies: Loaded policy definitions
        policy_cache: Cache for compiled policy patterns
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the builtin policy engine.

        Args:
            config: Optional configuration dict with:
                - policies: Initial policies to load
                - enable_cache: Enable policy caching (default: True)
        """
        self.config = config or {}
        self.policies: list[dict[str, Any]] = []
        self.policy_cache: dict[str, Any] = {}
        self.enable_cache = self.config.get("enable_cache", True)

        # Load initial policies
        self._load_initial_policies()

    async def evaluate_policy(self, context: SecurityContext) -> SecurityDecision:
        """
        Evaluate security policy against context.

        Process:
        1. Find policies matching the context
        2. Evaluate each matching policy
        3. Combine decisions (deny takes precedence)

        Args:
            context: Security context with principal, resource, action

        Returns:
            SecurityDecision indicating if access is allowed
        """
        start_time = datetime.now(timezone.utc)

        try:
            policies_evaluated = []
            decisions = []

            for policy in self.policies:
                if self._policy_matches_context(policy, context):
                    policies_evaluated.append(policy.get("name", "unnamed"))
                    decision = self._evaluate_single_policy(policy, context)
                    decisions.append(decision)

            # Combine decisions
            final_decision = self._combine_policy_decisions(decisions)
            final_decision.policies_evaluated = policies_evaluated

            end_time = datetime.now(timezone.utc)
            final_decision.evaluation_time_ms = (end_time - start_time).total_seconds() * 1000

            logger.debug(
                f"Policy evaluation complete: {final_decision.allowed} - {final_decision.reason}"
            )

            return final_decision

        except Exception as e:
            logger.error(f"Policy evaluation error: {e}", exc_info=True)
            return SecurityDecision(
                allowed=False,
                reason=f"Policy evaluation error: {e}",
                evaluation_time_ms=0.0,
                metadata={"error": str(e)},
            )

    async def load_policies(self, policies: list[dict[str, Any]]) -> bool:
        """
        Load security policies into the engine.

        Validates each policy before loading. Clears policy cache
        after successful load.

        Args:
            policies: List of policy definitions

        Returns:
            True if all policies loaded successfully
        """
        try:
            # Validate policies first
            for policy in policies:
                if not self._validate_policy(policy):
                    policy_name = policy.get("name", "unnamed")
                    logger.error(f"Invalid policy: {policy_name}")
                    return False

            self.policies = policies
            if self.enable_cache:
                self.policy_cache.clear()  # Clear cache when policies change

            logger.info(f"Loaded {len(policies)} policies")
            return True

        except Exception as e:
            logger.error(f"Policy loading error: {e}", exc_info=True)
            return False

    async def validate_policies(self) -> list[str]:
        """
        Validate loaded policies and return any errors.

        Performs detailed validation of policy syntax and semantics.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        for i, policy in enumerate(self.policies):
            policy_errors = self._validate_policy_detailed(policy)
            if policy_errors:
                policy_name = policy.get("name", f"policy_{i}")
                errors.extend([f"{policy_name}: {error}" for error in policy_errors])

        return errors

    def _load_initial_policies(self) -> None:
        """Load initial policies from configuration."""
        initial_policies = self.config.get("policies", [])

        if not initial_policies:
            # Load default policies
            initial_policies = self._get_default_policies()

        # Validate and load policies
        for policy in initial_policies:
            if self._validate_policy(policy):
                self.policies.append(policy)
            else:
                logger.warning(f"Skipping invalid policy: {policy.get('name', 'unnamed')}")

    def _policy_matches_context(self, policy: dict[str, Any], context: SecurityContext) -> bool:
        """
        Check if policy applies to the given context.

        Tests resource pattern, action pattern, principal conditions,
        and environment conditions.

        Args:
            policy: Policy definition
            context: Security context

        Returns:
            True if policy applies to context
        """
        try:
            # Check resource pattern
            resource_pattern = policy.get("resource")
            if resource_pattern and not self._matches_pattern(resource_pattern, context.resource):
                return False

            # Check action pattern
            action_pattern = policy.get("action")
            if action_pattern and not self._matches_pattern(action_pattern, context.action):
                return False

            # Check principal conditions
            principal_conditions = policy.get("principal")
            if principal_conditions and not self._matches_principal_conditions(
                principal_conditions, context.principal
            ):
                return False

            # Check environment conditions
            environment_conditions = policy.get("environment")
            if environment_conditions and not self._matches_environment_conditions(
                environment_conditions, context.environment
            ):
                return False

            return True

        except Exception as e:
            logger.error(f"Policy matching error: {e}", exc_info=True)
            return False

    def _evaluate_single_policy(
        self, policy: dict[str, Any], context: SecurityContext
    ) -> SecurityDecision:
        """
        Evaluate a single policy.

        Checks policy conditions and returns decision based on effect.

        Args:
            policy: Policy definition
            context: Security context

        Returns:
            SecurityDecision for this policy
        """
        try:
            effect = policy.get("effect", "deny").lower()
            condition = policy.get("condition")

            # If there's a condition, evaluate it
            if condition:
                condition_result = self._evaluate_condition(condition, context)
                if not condition_result:
                    return SecurityDecision(
                        allowed=False,
                        reason=f"Policy condition not met: {policy.get('name', 'unnamed')}",
                    )

            # Return decision based on effect
            if effect == "allow":
                return SecurityDecision(
                    allowed=True,
                    reason=f"Policy allows access: {policy.get('name', 'unnamed')}",
                    metadata={"policy": policy.get("name")},
                )
            else:
                return SecurityDecision(
                    allowed=False,
                    reason=f"Policy denies access: {policy.get('name', 'unnamed')}",
                    metadata={"policy": policy.get("name")},
                )

        except Exception as e:
            logger.error(f"Single policy evaluation error: {e}", exc_info=True)
            return SecurityDecision(
                allowed=False, reason=f"Policy evaluation error: {e}", metadata={"error": str(e)}
            )

    def _matches_pattern(self, pattern: str, value: str) -> bool:
        """
        Check if value matches pattern (supports wildcards).

        Patterns:
        - * matches any sequence of characters
        - ? matches any single character

        Args:
            pattern: Pattern with wildcards
            value: Value to match

        Returns:
            True if value matches pattern
        """
        try:
            # Use cache if enabled
            cache_key = f"{pattern}:{value}"
            if self.enable_cache and cache_key in self.policy_cache:
                return self.policy_cache[cache_key]

            # Convert wildcard pattern to regex
            regex_pattern = pattern.replace("*", ".*").replace("?", ".")
            result = bool(re.match(f"^{regex_pattern}$", value))

            if self.enable_cache:
                self.policy_cache[cache_key] = result

            return result
        except Exception as e:
            logger.warning(f"Pattern matching error: {e}")
            return False

    def _matches_principal_conditions(self, conditions: dict[str, Any], principal) -> bool:
        """
        Check if principal matches conditions.

        Tests roles, principal type, and attributes.

        Args:
            conditions: Principal condition requirements
            principal: Security principal

        Returns:
            True if principal matches conditions
        """
        try:
            # Check roles
            required_roles = conditions.get("roles")
            if required_roles:
                if isinstance(required_roles, str):
                    required_roles = [required_roles]
                if not any(role in principal.roles for role in required_roles):
                    return False

            # Check principal type
            required_type = conditions.get("type")
            if required_type and principal.type != required_type:
                return False

            # Check attributes
            required_attributes = conditions.get("attributes")
            if required_attributes:
                for attr_name, attr_value in required_attributes.items():
                    principal_attr_value = principal.attributes.get(attr_name)
                    if principal_attr_value != attr_value:
                        return False

            return True

        except Exception as e:
            logger.error(f"Principal condition matching error: {e}", exc_info=True)
            return False

    def _matches_environment_conditions(
        self, conditions: dict[str, Any], environment: dict[str, Any]
    ) -> bool:
        """
        Check if environment matches conditions.

        Supports simple equality and complex conditions like ranges.

        Args:
            conditions: Environment condition requirements
            environment: Environment attributes

        Returns:
            True if environment matches conditions
        """
        try:
            for condition_name, condition_value in conditions.items():
                env_value = environment.get(condition_name)

                if isinstance(condition_value, dict):
                    # Handle complex conditions like ranges, comparisons
                    if not self._evaluate_complex_environment_condition(condition_value, env_value):
                        return False
                else:
                    # Simple equality check
                    if env_value != condition_value:
                        return False

            return True

        except Exception as e:
            logger.error(f"Environment condition matching error: {e}", exc_info=True)
            return False

    def _evaluate_complex_environment_condition(
        self, condition: dict[str, Any], value: Any
    ) -> bool:
        """
        Evaluate complex environment conditions.

        Supports:
        - Range conditions: {"min": 0, "max": 100}
        - List membership: {"in": [1, 2, 3]}
        - Pattern matching: {"pattern": "*.example.com"}

        Args:
            condition: Condition specification
            value: Actual environment value

        Returns:
            True if condition is satisfied
        """
        try:
            # Handle range conditions
            if "min" in condition or "max" in condition:
                if value is None:
                    return False

                min_val = condition.get("min")
                max_val = condition.get("max")

                if min_val is not None and value < min_val:
                    return False
                if max_val is not None and value > max_val:
                    return False

                return True

            # Handle list membership
            if "in" in condition:
                return value in condition["in"]

            # Handle pattern matching
            if "pattern" in condition:
                return self._matches_pattern(condition["pattern"], str(value))

            return True

        except Exception as e:
            logger.error(f"Complex condition evaluation error: {e}", exc_info=True)
            return False

    def _evaluate_condition(self, condition: dict[str, Any], context: SecurityContext) -> bool:
        """
        Evaluate policy condition.

        Dispatches to specialized condition evaluators based on type.

        Args:
            condition: Condition specification
            context: Security context

        Returns:
            True if condition is satisfied
        """
        try:
            condition_type = condition.get("type", "simple")

            if condition_type == "time_based":
                return self._evaluate_time_condition(condition, context)
            elif condition_type == "attribute_based":
                return self._evaluate_attribute_condition(condition, context)
            else:
                # Default to true for unknown condition types
                logger.warning(f"Unknown condition type: {condition_type}")
                return True

        except Exception as e:
            logger.error(f"Condition evaluation error: {e}", exc_info=True)
            return False

    def _evaluate_time_condition(self, condition: dict[str, Any], context: SecurityContext) -> bool:
        """
        Evaluate time-based conditions.

        Supports time ranges and day-of-week restrictions.

        Args:
            condition: Time condition specification
            context: Security context

        Returns:
            True if time condition is satisfied
        """
        try:
            current_time = context.timestamp

            # Check time range
            start_time = condition.get("start_time")
            end_time = condition.get("end_time")

            if start_time and current_time.time() < datetime.fromisoformat(start_time).time():
                return False
            if end_time and current_time.time() > datetime.fromisoformat(end_time).time():
                return False

            # Check days of week (0 = Monday, 6 = Sunday)
            allowed_days = condition.get("days_of_week")
            if allowed_days and current_time.weekday() not in allowed_days:
                return False

            return True

        except Exception as e:
            logger.error(f"Time condition evaluation error: {e}", exc_info=True)
            return False

    def _evaluate_attribute_condition(
        self, condition: dict[str, Any], context: SecurityContext
    ) -> bool:
        """
        Evaluate attribute-based conditions.

        Checks if principal has required attributes.

        Args:
            condition: Attribute condition specification
            context: Security context

        Returns:
            True if attribute condition is satisfied
        """
        try:
            required_attributes = condition.get("attributes", {})

            for attr_name, attr_value in required_attributes.items():
                actual_value = context.principal.attributes.get(attr_name)
                if actual_value != attr_value:
                    return False

            return True

        except Exception as e:
            logger.error(f"Attribute condition evaluation error: {e}", exc_info=True)
            return False

    def _combine_policy_decisions(self, decisions: list[SecurityDecision]) -> SecurityDecision:
        """
        Combine multiple policy decisions.

        Decision logic:
        1. If no matching policies, deny
        2. If any explicit deny, deny
        3. If any allow, allow
        4. Otherwise deny

        Args:
            decisions: List of individual policy decisions

        Returns:
            Combined SecurityDecision
        """
        if not decisions:
            return SecurityDecision(
                allowed=False,
                reason="No matching policies found",
                metadata={"decision_count": 0},
            )

        # Check for explicit denies first
        for decision in decisions:
            if not decision.allowed and "deny" in decision.reason.lower():
                return decision

        # Check for allows
        for decision in decisions:
            if decision.allowed:
                return decision

        # Default to deny
        return SecurityDecision(
            allowed=False,
            reason="Access denied by policy",
            metadata={"decision_count": len(decisions)},
        )

    def _validate_policy(self, policy: dict[str, Any]) -> bool:
        """
        Basic policy validation.

        Args:
            policy: Policy definition

        Returns:
            True if policy is valid
        """
        try:
            # Check required fields
            if "effect" not in policy:
                return False

            effect = policy["effect"].lower()
            if effect not in ["allow", "deny"]:
                return False

            return True

        except Exception:
            return False

    def _validate_policy_detailed(self, policy: dict[str, Any]) -> list[str]:
        """
        Detailed policy validation with error messages.

        Args:
            policy: Policy definition

        Returns:
            List of validation error messages
        """
        errors = []

        try:
            # Check effect
            if "effect" not in policy:
                errors.append("Missing required field: effect")
            elif policy["effect"].lower() not in ["allow", "deny"]:
                errors.append("Invalid effect: must be 'allow' or 'deny'")

            # Validate resource pattern if present
            if "resource" in policy:
                try:
                    pattern = policy["resource"]
                    re.compile(pattern.replace("*", ".*").replace("?", "."))
                except re.error:
                    errors.append("Invalid resource pattern")

            # Validate action pattern if present
            if "action" in policy:
                try:
                    pattern = policy["action"]
                    re.compile(pattern.replace("*", ".*").replace("?", "."))
                except re.error:
                    errors.append("Invalid action pattern")

            return errors

        except Exception as e:
            return [f"Policy validation error: {e}"]

    def _get_default_policies(self) -> list[dict[str, Any]]:
        """
        Get default policies for the system.

        Returns:
            List of default policy definitions
        """
        return [
            {
                "name": "admin_full_access",
                "description": "Administrators have full access",
                "resource": "*",
                "action": "*",
                "principal": {"roles": ["admin"]},
                "effect": "allow",
            },
            {
                "name": "user_read_access",
                "description": "Users have read access to their resources",
                "resource": "/api/v1/users/*",
                "action": "GET",
                "principal": {"roles": ["user"]},
                "effect": "allow",
            },
            {
                "name": "deny_by_default",
                "description": "Deny all other access",
                "resource": "*",
                "action": "*",
                "effect": "deny",
            },
        ]
