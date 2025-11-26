"""Feature flag management for deployment strategies."""

import builtins
import hashlib
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from ..models import FeatureFlag, FeatureFlagType


class FeatureFlagManager:
    """Feature flag management for deployment strategies."""

    def __init__(self):
        """Initialize feature flag manager."""
        self.feature_flags: builtins.dict[str, FeatureFlag] = {}
        self.flag_evaluations: deque = deque(maxlen=10000)

    async def create_feature_flag(
        self,
        name: str,
        flag_type: FeatureFlagType,
        value: Any = None,
        targeting_rules: builtins.list[builtins.dict[str, Any]] | None = None,
        enabled: bool = True,
    ) -> str:
        """Create a new feature flag."""
        flag_id = str(uuid.uuid4())

        feature_flag = FeatureFlag(
            flag_id=flag_id,
            name=name,
            flag_type=flag_type,
            value=value,
            targeting_rules=targeting_rules or [],
            enabled=enabled,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.feature_flags[flag_id] = feature_flag

        logging.info(f"Created feature flag: {name} ({flag_id})")

        return flag_id

    async def update_feature_flag(
        self,
        flag_id: str,
        value: Any = None,
        enabled: bool | None = None,
        targeting_rules: builtins.list[builtins.dict[str, Any]] | None = None,
    ) -> bool:
        """Update existing feature flag."""
        if flag_id not in self.feature_flags:
            return False

        flag = self.feature_flags[flag_id]

        if value is not None:
            flag.value = value
        if enabled is not None:
            flag.enabled = enabled
        if targeting_rules is not None:
            flag.targeting_rules = targeting_rules

        flag.updated_at = datetime.now(timezone.utc)

        logging.info(f"Updated feature flag: {flag.name} ({flag_id})")

        return True

    async def delete_feature_flag(self, flag_id: str) -> bool:
        """Delete feature flag."""
        if flag_id not in self.feature_flags:
            return False

        flag = self.feature_flags.pop(flag_id)
        logging.info(f"Deleted feature flag: {flag.name} ({flag_id})")

        return True

    async def evaluate_flag(
        self, flag_id: str, context: builtins.dict[str, Any] | None = None
    ) -> Any:
        """Evaluate feature flag with given context."""
        if flag_id not in self.feature_flags:
            return None

        flag = self.feature_flags[flag_id]

        if not flag.enabled:
            return None

        context = context or {}

        # Log evaluation
        self.flag_evaluations.append(
            {
                "flag_id": flag_id,
                "context": context,
                "timestamp": datetime.now(timezone.utc),
                "result": None,  # Will be updated below
            }
        )

        # Evaluate based on flag type
        if flag.flag_type == FeatureFlagType.BOOLEAN:
            result = self._evaluate_boolean_flag(flag, context)
        elif flag.flag_type == FeatureFlagType.PERCENTAGE:
            result = self._evaluate_percentage_flag(flag, context)
        elif flag.flag_type == FeatureFlagType.USER_LIST:
            result = self._evaluate_user_list_flag(flag, context)
        elif flag.flag_type == FeatureFlagType.COHORT:
            result = self._evaluate_cohort_flag(flag, context)
        elif flag.flag_type == FeatureFlagType.CONFIGURATION:
            result = self._evaluate_configuration_flag(flag, context)
        else:
            result = flag.value

        # Update evaluation result
        if self.flag_evaluations:
            self.flag_evaluations[-1]["result"] = result

        return result

    def _evaluate_boolean_flag(self, flag: FeatureFlag, context: builtins.dict[str, Any]) -> bool:
        """Evaluate boolean feature flag."""
        # Check targeting rules
        for rule in flag.targeting_rules:
            if self._evaluate_targeting_rule(rule, context):
                return rule.get("value", True)

        return bool(flag.value) if flag.value is not None else True

    def _evaluate_percentage_flag(
        self, flag: FeatureFlag, context: builtins.dict[str, Any]
    ) -> bool:
        """Evaluate percentage-based feature flag."""
        user_id = context.get("user_id", "anonymous")

        # Generate consistent hash for user
        user_hash = int(hashlib.sha256(f"{flag.flag_id}:{user_id}".encode()).hexdigest(), 16)
        user_percentage = (user_hash % 100) / 100.0

        threshold = flag.value if isinstance(flag.value, int | float) else 0.5

        return user_percentage < threshold

    def _evaluate_user_list_flag(self, flag: FeatureFlag, context: builtins.dict[str, Any]) -> bool:
        """Evaluate user list feature flag."""
        user_id = context.get("user_id")
        if not user_id:
            return False

        user_list = flag.value if isinstance(flag.value, list) else []
        return user_id in user_list

    def _evaluate_cohort_flag(self, flag: FeatureFlag, context: builtins.dict[str, Any]) -> bool:
        """Evaluate cohort-based feature flag."""
        # Simplified cohort evaluation
        cohort = context.get("cohort", "default")
        target_cohorts = flag.value if isinstance(flag.value, list) else []

        return cohort in target_cohorts

    def _evaluate_configuration_flag(
        self, flag: FeatureFlag, context: builtins.dict[str, Any]
    ) -> Any:
        """Evaluate configuration feature flag."""
        # Return configuration value directly
        return flag.value

    def _evaluate_targeting_rule(
        self, rule: builtins.dict[str, Any], context: builtins.dict[str, Any]
    ) -> bool:
        """Evaluate targeting rule."""
        rule_type = rule.get("type")

        if rule_type == "user_attribute":
            attribute = rule.get("attribute")
            operator = rule.get("operator", "equals")
            expected_value = rule.get("value")

            actual_value = context.get(attribute)

            if operator == "equals":
                return actual_value == expected_value
            if operator == "contains":
                return expected_value in str(actual_value) if actual_value else False
            if operator == "in":
                return actual_value in expected_value if isinstance(expected_value, list) else False

        elif rule_type == "percentage":
            percentage = rule.get("percentage", 0)
            user_id = context.get("user_id", "anonymous")

            user_hash = int(hashlib.sha256(f"rule:{user_id}".encode()).hexdigest(), 16)
            user_percentage = (user_hash % 100) / 100.0

            return user_percentage < percentage

        return False

    def get_flag_status(self, flag_id: str) -> builtins.dict[str, Any] | None:
        """Get feature flag status."""
        if flag_id not in self.feature_flags:
            return None

        flag = self.feature_flags[flag_id]

        # Calculate evaluation statistics
        recent_evaluations = [e for e in self.flag_evaluations if e["flag_id"] == flag_id]

        return {
            "flag_id": flag.flag_id,
            "name": flag.name,
            "type": flag.flag_type.value,
            "enabled": flag.enabled,
            "value": flag.value,
            "evaluation_count": len(recent_evaluations),
            "created_at": flag.created_at.isoformat(),
            "updated_at": flag.updated_at.isoformat(),
        }
