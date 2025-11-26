"""
Deployment Strategy Enums

Core enumeration types for deployment strategies, phases, status,
environments, feature flags, and validation results.
"""

from enum import Enum


class DeploymentStrategy(Enum):
    """Deployment strategy types."""

    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    ROLLING = "rolling"
    RECREATE = "recreate"
    A_B_TEST = "a_b_test"


class DeploymentPhase(Enum):
    """Deployment phases."""

    PLANNING = "planning"
    PRE_DEPLOYMENT = "pre_deployment"
    DEPLOYMENT = "deployment"
    VALIDATION = "validation"
    TRAFFIC_SHIFTING = "traffic_shifting"
    MONITORING = "monitoring"
    COMPLETION = "completion"
    ROLLBACK = "rollback"


class DeploymentStatus(Enum):
    """Deployment status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLING_BACK = "rolling_back"


class EnvironmentType(Enum):
    """Environment types."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    CANARY = "canary"
    BLUE = "blue"
    GREEN = "green"


class FeatureFlagType(Enum):
    """Feature flag types."""

    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    COHORT = "cohort"
    CONFIGURATION = "configuration"


class ValidationResult(Enum):
    """Validation results."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    SKIP = "skip"
