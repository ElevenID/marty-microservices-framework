"""
Domain models for deployment.
"""

import builtins
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import (
    CloudProvider,
    DeploymentStatus,
    DeploymentStrategy,
    EnvironmentType,
    GitOpsProvider,
    IaCProvider,
    InfrastructureProvider,
    PipelineProvider,
    PipelineStage,
    PipelineStatus,
    ResourceType,
)


@dataclass
class DeploymentTarget:
    """Deployment target configuration."""

    name: str
    environment: EnvironmentType
    provider: InfrastructureProvider
    region: str | None = None
    cluster: str | None = None
    namespace: str | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceRequirements:
    """Resource requirements for deployment."""

    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"
    storage: str | None = None
    replicas: int = 1
    min_replicas: int = 1
    max_replicas: int = 10
    custom_resources: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Health check configuration."""

    path: str = "/health"
    port: int = 8080
    initial_delay: int = 30
    period: int = 10
    timeout: int = 5
    failure_threshold: int = 3
    success_threshold: int = 1
    scheme: str = "HTTP"


@dataclass
class DeploymentConfig:
    """Deployment configuration."""

    service_name: str
    version: str
    image: str
    target: DeploymentTarget
    strategy: DeploymentStrategy = DeploymentStrategy.ROLLING_UPDATE
    resources: ResourceRequirements = field(default_factory=ResourceRequirements)
    health_check: HealthCheck = field(default_factory=HealthCheck)
    environment_variables: builtins.dict[str, str] = field(default_factory=dict)
    secrets: builtins.dict[str, str] = field(default_factory=dict)
    config_maps: builtins.dict[str, builtins.dict[str, str]] = field(default_factory=dict)
    volumes: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    network_policies: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    service_account: str | None = None
    annotations: builtins.dict[str, str] = field(default_factory=dict)
    labels: builtins.dict[str, str] = field(default_factory=dict)
    custom_spec: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class DeploymentEvent:
    """Deployment event."""

    id: str
    deployment_id: str
    timestamp: datetime
    event_type: str
    message: str
    level: str = "info"
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class Deployment:
    """Deployment instance."""

    id: str
    config: DeploymentConfig
    status: DeploymentStatus = DeploymentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deployed_at: datetime | None = None
    events: builtins.list[DeploymentEvent] = field(default_factory=list)
    previous_version: str | None = None
    rollback_config: DeploymentConfig | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def add_event(self, event_type: str, message: str, level: str = "info", **metadata):
        """Add deployment event."""
        event = DeploymentEvent(
            id=str(uuid.uuid4()),
            deployment_id=self.id,
            timestamp=datetime.utcnow(),
            event_type=event_type,
            message=message,
            level=level,
            metadata=metadata,
        )
        self.events.append(event)
        self.updated_at = datetime.utcnow()


@dataclass
class IaCConfig:
    """Infrastructure as Code configuration."""

    provider: IaCProvider
    cloud_provider: CloudProvider
    project_name: str
    environment: EnvironmentType
    region: str = "us-east-1"
    variables: builtins.dict[str, Any] = field(default_factory=dict)
    backend_config: builtins.dict[str, Any] = field(default_factory=dict)
    outputs: builtins.list[str] = field(default_factory=list)
    dependencies: builtins.list[str] = field(default_factory=list)


@dataclass
class ResourceConfig:
    """Infrastructure resource configuration."""

    name: str
    type: ResourceType
    provider: CloudProvider
    properties: builtins.dict[str, Any] = field(default_factory=dict)
    dependencies: builtins.list[str] = field(default_factory=list)
    tags: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class InfrastructureStack:
    """Infrastructure stack definition."""

    name: str
    config: IaCConfig
    resources: builtins.list[ResourceConfig] = field(default_factory=list)
    modules: builtins.list[str] = field(default_factory=list)
    data_sources: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)


@dataclass
class InfrastructureState:
    """Infrastructure state information."""

    stack_name: str
    status: str
    resources: builtins.dict[str, Any] = field(default_factory=dict)
    outputs: builtins.dict[str, Any] = field(default_factory=dict)
    last_updated: datetime | None = None
    version: str | None = None


@dataclass
class PipelineConfig:
    """Pipeline configuration."""

    name: str
    provider: PipelineProvider
    repository_url: str
    branch: str = "main"
    triggers: builtins.list[str] = field(default_factory=lambda: ["push", "pull_request"])
    stages: builtins.list[PipelineStage] = field(default_factory=list)
    environment_variables: builtins.dict[str, str] = field(default_factory=dict)
    secrets: builtins.dict[str, str] = field(default_factory=dict)
    parallel_stages: bool = True
    timeout_minutes: int = 30
    retry_count: int = 3
    notifications: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class GitOpsConfig:
    """GitOps configuration."""

    provider: GitOpsProvider
    repository_url: str
    path: str = "manifests"
    branch: str = "main"
    sync_policy: builtins.dict[str, Any] = field(default_factory=dict)
    auto_sync: bool = True
    self_heal: bool = True
    prune: bool = True
    timeout_seconds: int = 300


@dataclass
class PipelineExecution:
    """Pipeline execution information."""

    id: str
    pipeline_name: str
    status: PipelineStatus
    started_at: datetime
    finished_at: datetime | None = None
    duration: datetime | None = None  # Using datetime as placeholder for timedelta
    stages: builtins.dict[str, PipelineStatus] = field(default_factory=dict)
    logs: builtins.dict[str, str] = field(default_factory=dict)
    artifacts: builtins.dict[str, str] = field(default_factory=dict)
    commit_sha: str | None = None
    triggered_by: str | None = None


@dataclass
class DeploymentPipeline:
    """Deployment pipeline definition."""

    name: str
    config: PipelineConfig
    gitops_config: GitOpsConfig | None = None
    deployment_config: DeploymentConfig | None = None
    # helm_charts: builtins.list[HelmChart] = field(default_factory=list) # HelmChart not yet migrated
