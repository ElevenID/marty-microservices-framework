"""Data models for deployment strategies."""

import builtins
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .enums import (
    DeploymentPhase,
    DeploymentStatus,
    DeploymentStrategy,
    EnvironmentType,
    FeatureFlagType,
)


@dataclass
class DeploymentTarget:
    """Deployment target specification."""

    environment: EnvironmentType
    cluster: str
    namespace: str
    region: str
    availability_zones: builtins.list[str] = field(default_factory=list)
    capacity: builtins.dict[str, Any] = field(default_factory=dict)
    configuration: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceVersion:
    """Service version specification."""

    service_name: str
    version: str
    image_tag: str
    configuration_hash: str
    artifacts: builtins.dict[str, str] = field(default_factory=dict)
    dependencies: builtins.list[str] = field(default_factory=list)
    health_check_endpoint: str = "/health"
    readiness_check_endpoint: str = "/ready"


@dataclass
class TrafficSplit:
    """Traffic splitting configuration."""

    version_weights: builtins.dict[str, float]  # version -> weight (0.0 to 1.0)
    routing_rules: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    sticky_sessions: bool = False
    session_affinity_key: str | None = None


@dataclass
class DeploymentValidation:
    """Deployment validation configuration."""

    validation_id: str
    name: str
    type: str  # health_check, performance_test, smoke_test, etc.
    timeout_seconds: int = 300
    retry_attempts: int = 3
    criteria: builtins.dict[str, Any] = field(default_factory=dict)
    required: bool = True


@dataclass
class FeatureFlag:
    """Feature flag configuration."""

    flag_id: str
    name: str
    description: str
    flag_type: FeatureFlagType
    enabled: bool = False
    value: Any = None
    targeting_rules: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: builtins.list[str] = field(default_factory=list)


@dataclass
class DeploymentEvent:
    """Deployment event for tracking."""

    event_id: str
    deployment_id: str
    event_type: str
    phase: DeploymentPhase
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: builtins.dict[str, Any] = field(default_factory=dict)
    success: bool = True


@dataclass
class RollbackConfiguration:
    """Rollback configuration."""

    enabled: bool = True
    automatic_triggers: builtins.list[str] = field(default_factory=list)
    max_rollback_time: int = 1800  # 30 minutes
    preserve_traffic_split: bool = False
    rollback_validation: builtins.list[DeploymentValidation] = field(default_factory=list)


@dataclass
class Deployment:
    """Main deployment configuration."""

    deployment_id: str
    service_name: str
    strategy: DeploymentStrategy
    source_version: ServiceVersion
    target_version: ServiceVersion
    target_environment: DeploymentTarget
    traffic_split: TrafficSplit
    validations: builtins.list[DeploymentValidation] = field(default_factory=list)
    rollback_config: RollbackConfiguration = field(default_factory=RollbackConfiguration)
    status: DeploymentStatus = DeploymentStatus.PENDING
    current_phase: DeploymentPhase = DeploymentPhase.PLANNING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    feature_flags: builtins.list[FeatureFlag] = field(default_factory=list)
    metrics: builtins.dict[str, Any] = field(default_factory=dict)
