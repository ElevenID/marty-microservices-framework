"""
Built-in Policy Engine Implementation

Provides a simple, efficient policy engine for basic RBAC and ABAC policies
without external dependencies.
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional, Union

from ..api import AbstractPolicyEngine, SecurityContext, SecurityDecision

logger = logging.getLogger(__name__)


class BuiltinPolicyEngine(AbstractPolicyEngine):
    """Built-in policy engine with JSON-based policy definitions"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.policies: list[dict[str, Any]] = []
        self.policy_cache: dict[str, Any] = {}

        # Load initial policies
        self._load_initial_policies()

    async def evaluate_policy(self, context: SecurityContext) -> SecurityDecision:
        """Evaluate security policy against context"""
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

            return final_decision

        except Exception as e:
            logger.error(f"Policy evaluation error: {e}")
            return SecurityDecision(
                allowed=False,
                reason=f"Policy evaluation error: {e}",
                evaluation_time_ms=0.0
            )

    async def load_policies(self, policies: list[dict[str, Any]]) -> bool:
        """Load security policies"""
        try:
            # Validate policies first
            for policy in policies:
                if not self._validate_policy(policy):
                    logger.error(f"Invalid policy: {policy.get('name', 'unnamed')}")
                    return False

            self.policies = policies
            self.policy_cache.clear()  # Clear cache when policies change

            logger.info(f"Loaded {len(policies)} policies")
            return True

        except Exception as e:
            logger.error(f"Policy loading error: {e}")
            return False

    async def validate_policies(self) -> list[str]:
        """Validate loaded policies and return any errors"""
        errors = []

        for i, policy in enumerate(self.policies):
            policy_errors = self._validate_policy_detailed(policy)
            if policy_errors:
                policy_name = policy.get("name", f"policy_{i}")
                errors.extend([f"{policy_name}: {error}" for error in policy_errors])

        return errors

    def _load_initial_policies(self) -> None:
        """Load initial policies from configuration"""
        initial_policies = self.config.get("policies", [])

        if not initial_policies:
            # Load default policies
            initial_policies = self._get_default_policies()

        # Load policies synchronously during initialization
        for policy in initial_policies:
            if self._validate_policy(policy):
                self.policies.append(policy)
            else:
                logger.warning(f"Skipping invalid policy: {policy.get('name', 'unnamed')}")

    def _policy_matches_context(self, policy: dict[str, Any], context: SecurityContext) -> bool:
        """Check if policy applies to the given context"""
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
            logger.error(f"Policy matching error: {e}")
            return False

    def _evaluate_single_policy(self, policy: dict[str, Any], context: SecurityContext) -> SecurityDecision:
        """Evaluate a single policy"""
        try:
            effect = policy.get("effect", "deny").lower()
            condition = policy.get("condition")

            # If there's a condition, evaluate it
            if condition:
                condition_result = self._evaluate_condition(condition, context)
                if not condition_result:
                    return SecurityDecision(
                        allowed=False,
                        reason=f"Policy condition not met: {policy.get('name', 'unnamed')}"
                    )

            # Return decision based on effect
            if effect == "allow":
                return SecurityDecision(
                    allowed=True,
                    reason=f"Policy allows access: {policy.get('name', 'unnamed')}"
                )
            else:
                return SecurityDecision(
                    allowed=False,
                    reason=f"Policy denies access: {policy.get('name', 'unnamed')}"
                )

        except Exception as e:
            logger.error(f"Single policy evaluation error: {e}")
            return SecurityDecision(
                allowed=False,
                reason=f"Policy evaluation error: {e}"
            )

    def _matches_pattern(self, pattern: str, value: str) -> bool:
        """Check if value matches pattern (supports wildcards)"""
        try:
            # Convert wildcard pattern to regex
            regex_pattern = pattern.replace("*", ".*").replace("?", ".")
            return bool(re.match(f"^{regex_pattern}$", value))
        except Exception:
            return False

    def _matches_principal_conditions(self, conditions: dict[str, Any], principal) -> bool:
        """Check if principal matches conditions"""
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
            logger.error(f"Principal condition matching error: {e}")
            return False

    def _matches_environment_conditions(self, conditions: dict[str, Any], environment: dict[str, Any]) -> bool:
        """Check if environment matches conditions"""
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
            logger.error(f"Environment condition matching error: {e}")
            return False

    def _evaluate_complex_environment_condition(self, condition: dict[str, Any], value: Any) -> bool:
        """Evaluate complex environment conditions"""
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
            logger.error(f"Complex condition evaluation error: {e}")
            return False

    def _evaluate_condition(self, condition: dict[str, Any], context: SecurityContext) -> bool:
        """Evaluate policy condition"""
        try:
            # This is a simplified condition evaluator
            # In a real implementation, you might want to use a proper expression evaluator

            condition_type = condition.get("type", "simple")

            if condition_type == "time_based":
                return self._evaluate_time_condition(condition, context)
            elif condition_type == "attribute_based":
                return self._evaluate_attribute_condition(condition, context)
            else:
                # Default to true for unknown condition types
                return True

        except Exception as e:
            logger.error(f"Condition evaluation error: {e}")
            return False

    def _evaluate_time_condition(self, condition: dict[str, Any], context: SecurityContext) -> bool:
        """Evaluate time-based conditions"""
        try:
            current_time = context.timestamp

            # Check time range
            start_time = condition.get("start_time")
            end_time = condition.get("end_time")

            if start_time and current_time.time() < datetime.fromisoformat(start_time).time():
                return False
            if end_time and current_time.time() > datetime.fromisoformat(end_time).time():
                return False

            # Check days of week
            allowed_days = condition.get("days_of_week")
            if allowed_days and current_time.weekday() not in allowed_days:
                return False

            return True

        except Exception as e:
            logger.error(f"Time condition evaluation error: {e}")
            return False

    def _evaluate_attribute_condition(self, condition: dict[str, Any], context: SecurityContext) -> bool:
        """Evaluate attribute-based conditions"""
        try:
            required_attributes = condition.get("attributes", {})

            for attr_name, attr_value in required_attributes.items():
                actual_value = context.principal.attributes.get(attr_name)
                if actual_value != attr_value:
                    return False

            return True

        except Exception as e:
            logger.error(f"Attribute condition evaluation error: {e}")
            return False

    def _combine_policy_decisions(self, decisions: list[SecurityDecision]) -> SecurityDecision:
        """Combine multiple policy decisions"""
        if not decisions:
            return SecurityDecision(
                allowed=False,
                reason="No matching policies found"
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
            reason="Access denied by policy"
        )

    def _validate_policy(self, policy: dict[str, Any]) -> bool:
        """Basic policy validation"""
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
        """Detailed policy validation with error messages"""
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
        """Get default policies for the system"""
        return [
            {
                "name": "admin_full_access",
                "description": "Administrators have full access",
                "resource": "*",
                "action": "*",
                "principal": {
                    "roles": ["admin"]
                },
                "effect": "allow"
            },
            {
                "name": "user_read_access",
                "description": "Users have read access to their resources",
                "resource": "/api/v1/users/*",
                "action": "GET",
                "principal": {
                    "roles": ["user"]
                },
                "effect": "allow"
            },
            {
                "name": "deny_by_default",
                "description": "Deny all other access",
                "resource": "*",
                "action": "*",
                "effect": "deny"
            }
        ]
