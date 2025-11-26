"""
Core deployment framework for Marty Microservices Framework.

This module provides the foundational deployment infrastructure for enterprise microservices,
including deployment orchestration, environment management, and deployment lifecycle coordination.
"""

import asyncio
import builtins
import json
import logging
import subprocess
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class DeploymentStatus(Enum):
    """Deployment status states."""

    PENDING = "pending"
    PREPARING = "preparing"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    TERMINATED = "terminated"


class DeploymentStrategy(Enum):
    """Deployment strategies."""

    ROLLING_UPDATE = "rolling_update"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"
    A_B_TESTING = "a_b_testing"


class EnvironmentType(Enum):
    """Environment types."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    SANDBOX = "sandbox"


class InfrastructureProvider(Enum):
    """Infrastructure providers."""

    KUBERNETES = "kubernetes"
    DOCKER_SWARM = "docker_swarm"
    AWS_ECS = "aws_ecs"
    AWS_EKS = "aws_eks"
    AZURE_AKS = "azure_aks"
    GCP_GKE = "gcp_gke"


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


class DeploymentProvider(ABC):
    """Abstract base class for deployment providers."""

    def __init__(self, provider_type: InfrastructureProvider):
        self.provider_type = provider_type
        self.active_deployments: builtins.dict[str, Deployment] = {}

    @abstractmethod
    async def deploy(self, deployment: Deployment) -> bool:
        """Deploy service to target environment."""

    @abstractmethod
    async def rollback(self, deployment: Deployment) -> bool:
        """Rollback deployment to previous version."""

    @abstractmethod
    async def scale(self, deployment: Deployment, replicas: int) -> bool:
        """Scale deployment."""

    @abstractmethod
    async def get_status(self, deployment: Deployment) -> builtins.dict[str, Any]:
        """Get deployment status."""

    @abstractmethod
    async def get_logs(self, deployment: Deployment, lines: int = 100) -> builtins.list[str]:
        """Get deployment logs."""

    @abstractmethod
    async def terminate(self, deployment: Deployment) -> bool:
        """Terminate deployment."""

    async def health_check(self, deployment: Deployment) -> bool:
        """Perform health check on deployment."""
        try:
            status = await self.get_status(deployment)
            return status.get("healthy", False)
        except Exception as e:
            logger.error(f"Health check failed for deployment {deployment.id}: {e}")
            return False


class KubernetesProvider(DeploymentProvider):
    """Kubernetes deployment provider."""

    def __init__(self, kubeconfig_path: str | None = None):
        super().__init__(InfrastructureProvider.KUBERNETES)
        self.kubeconfig_path = kubeconfig_path
        self.kubectl_binary = "kubectl"

    async def deploy(self, deployment: Deployment) -> bool:
        """Deploy service to Kubernetes."""
        try:
            deployment.add_event("deployment_started", "Starting Kubernetes deployment")
            deployment.status = DeploymentStatus.DEPLOYING

            # Generate Kubernetes manifests
            manifests = self._generate_manifests(deployment)

            # Apply manifests
            for manifest in manifests:
                success = await self._apply_manifest(deployment, manifest)
                if not success:
                    deployment.status = DeploymentStatus.FAILED
                    deployment.add_event(
                        "deployment_failed",
                        "Failed to apply Kubernetes manifest",
                        "error",
                    )
                    return False

            # Wait for deployment to be ready
            if await self._wait_for_deployment_ready(deployment):
                deployment.status = DeploymentStatus.DEPLOYED
                deployment.deployed_at = datetime.utcnow()
                deployment.add_event(
                    "deployment_completed",
                    "Kubernetes deployment completed successfully",
                )
                return True
            deployment.status = DeploymentStatus.FAILED
            deployment.add_event("deployment_failed", "Deployment did not become ready", "error")
            return False

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.add_event("deployment_error", f"Deployment error: {e!s}", "error")
            logger.error(f"Kubernetes deployment failed: {e}")
            return False

    async def rollback(self, deployment: Deployment) -> bool:
        """Rollback Kubernetes deployment."""
        try:
            deployment.add_event("rollback_started", "Starting rollback")
            deployment.status = DeploymentStatus.ROLLING_BACK

            cmd = [
                self.kubectl_binary,
                "rollout",
                "undo",
                f"deployment/{deployment.config.service_name}",
                "-n",
                deployment.config.target.namespace or "default",
            ]

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_kubectl_command(cmd)

            if result.returncode == 0:
                if await self._wait_for_deployment_ready(deployment):
                    deployment.status = DeploymentStatus.ROLLED_BACK
                    deployment.add_event("rollback_completed", "Rollback completed successfully")
                    return True

            deployment.status = DeploymentStatus.FAILED
            deployment.add_event("rollback_failed", "Rollback failed", "error")
            return False

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.add_event("rollback_error", f"Rollback error: {e!s}", "error")
            logger.error(f"Kubernetes rollback failed: {e}")
            return False

    async def scale(self, deployment: Deployment, replicas: int) -> bool:
        """Scale Kubernetes deployment."""
        try:
            deployment.add_event("scaling_started", f"Scaling to {replicas} replicas")

            cmd = [
                self.kubectl_binary,
                "scale",
                f"deployment/{deployment.config.service_name}",
                f"--replicas={replicas}",
                "-n",
                deployment.config.target.namespace or "default",
            ]

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_kubectl_command(cmd)

            if result.returncode == 0:
                deployment.config.resources.replicas = replicas
                deployment.add_event("scaling_completed", f"Scaled to {replicas} replicas")
                return True

            deployment.add_event("scaling_failed", "Failed to scale deployment", "error")
            return False

        except Exception as e:
            deployment.add_event("scaling_error", f"Scaling error: {e!s}", "error")
            logger.error(f"Kubernetes scaling failed: {e}")
            return False

    async def get_status(self, deployment: Deployment) -> builtins.dict[str, Any]:
        """Get Kubernetes deployment status."""
        try:
            cmd = [
                self.kubectl_binary,
                "get",
                "deployment",
                deployment.config.service_name,
                "-n",
                deployment.config.target.namespace or "default",
                "-o",
                "json",
            ]

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_kubectl_command(cmd)

            if result.returncode == 0:
                status_data = json.loads(result.stdout)
                spec = status_data.get("spec", {})
                status = status_data.get("status", {})

                return {
                    "replicas": spec.get("replicas", 0),
                    "ready_replicas": status.get("readyReplicas", 0),
                    "available_replicas": status.get("availableReplicas", 0),
                    "updated_replicas": status.get("updatedReplicas", 0),
                    "healthy": status.get("readyReplicas", 0) == spec.get("replicas", 0),
                    "conditions": status.get("conditions", []),
                }

            return {"healthy": False, "error": "Failed to get status"}

        except Exception as e:
            logger.error(f"Failed to get Kubernetes status: {e}")
            return {"healthy": False, "error": str(e)}

    async def get_logs(self, deployment: Deployment, lines: int = 100) -> builtins.list[str]:
        """Get Kubernetes deployment logs."""
        try:
            cmd = [
                self.kubectl_binary,
                "logs",
                f"deployment/{deployment.config.service_name}",
                "-n",
                deployment.config.target.namespace or "default",
                f"--tail={lines}",
                "--all-containers=true",
            ]

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_kubectl_command(cmd)

            if result.returncode == 0:
                return result.stdout.split("\n")

            return [f"Failed to get logs: {result.stderr}"]

        except Exception as e:
            logger.error(f"Failed to get Kubernetes logs: {e}")
            return [f"Error getting logs: {e!s}"]

    async def terminate(self, deployment: Deployment) -> bool:
        """Terminate Kubernetes deployment."""
        try:
            deployment.add_event("termination_started", "Starting deployment termination")
            deployment.status = DeploymentStatus.TERMINATED

            # Delete deployment
            cmd = [
                self.kubectl_binary,
                "delete",
                "deployment",
                deployment.config.service_name,
                "-n",
                deployment.config.target.namespace or "default",
            ]

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_kubectl_command(cmd)

            if result.returncode == 0:
                deployment.add_event("termination_completed", "Deployment terminated successfully")
                return True

            deployment.add_event("termination_failed", "Failed to terminate deployment", "error")
            return False

        except Exception as e:
            deployment.add_event("termination_error", f"Termination error: {e!s}", "error")
            logger.error(f"Kubernetes termination failed: {e}")
            return False

    def _generate_manifests(self, deployment: Deployment) -> builtins.list[builtins.dict[str, Any]]:
        """Generate Kubernetes manifests."""
        manifests = []
        config = deployment.config

        # Deployment manifest
        deployment_manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": config.service_name,
                "namespace": config.target.namespace or "default",
                "labels": {
                    "app": config.service_name,
                    "version": config.version,
                    **config.labels,
                },
                "annotations": config.annotations,
            },
            "spec": {
                "replicas": config.resources.replicas,
                "selector": {"matchLabels": {"app": config.service_name}},
                "template": {
                    "metadata": {
                        "labels": {
                            "app": config.service_name,
                            "version": config.version,
                            **config.labels,
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": config.service_name,
                                "image": config.image,
                                "ports": [{"containerPort": config.health_check.port}],
                                "resources": {
                                    "requests": {
                                        "cpu": config.resources.cpu_request,
                                        "memory": config.resources.memory_request,
                                    },
                                    "limits": {
                                        "cpu": config.resources.cpu_limit,
                                        "memory": config.resources.memory_limit,
                                    },
                                },
                                "env": [
                                    {"name": k, "value": v}
                                    for k, v in config.environment_variables.items()
                                ],
                                "livenessProbe": {
                                    "httpGet": {
                                        "path": config.health_check.path,
                                        "port": config.health_check.port,
                                        "scheme": config.health_check.scheme,
                                    },
                                    "initialDelaySeconds": config.health_check.initial_delay,
                                    "periodSeconds": config.health_check.period,
                                    "timeoutSeconds": config.health_check.timeout,
                                    "failureThreshold": config.health_check.failure_threshold,
                                },
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": config.health_check.path,
                                        "port": config.health_check.port,
                                        "scheme": config.health_check.scheme,
                                    },
                                    "initialDelaySeconds": 10,
                                    "periodSeconds": config.health_check.period,
                                    "timeoutSeconds": config.health_check.timeout,
                                    "successThreshold": config.health_check.success_threshold,
                                },
                            }
                        ]
                    },
                },
                "strategy": self._get_deployment_strategy(config.strategy),
            },
        }

        # Add service account if specified
        if config.service_account:
            deployment_manifest["spec"]["template"]["spec"]["serviceAccountName"] = (
                config.service_account
            )

        # Add volumes if specified
        if config.volumes:
            deployment_manifest["spec"]["template"]["spec"]["volumes"] = config.volumes
            # Add volume mounts to container (simplified)
            volume_mounts = []
            for volume in config.volumes:
                if "mountPath" in volume:
                    volume_mounts.append({"name": volume["name"], "mountPath": volume["mountPath"]})
            if volume_mounts:
                deployment_manifest["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = (
                    volume_mounts
                )

        manifests.append(deployment_manifest)

        # Service manifest
        service_manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": config.service_name,
                "namespace": config.target.namespace or "default",
                "labels": {"app": config.service_name, **config.labels},
            },
            "spec": {
                "selector": {"app": config.service_name},
                "ports": [
                    {
                        "port": 80,
                        "targetPort": config.health_check.port,
                        "protocol": "TCP",
                    }
                ],
                "type": "ClusterIP",
            },
        }

        manifests.append(service_manifest)

        # ConfigMaps
        for cm_name, cm_data in config.config_maps.items():
            configmap_manifest = {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": cm_name,
                    "namespace": config.target.namespace or "default",
                },
                "data": cm_data,
            }
            manifests.append(configmap_manifest)

        # HorizontalPodAutoscaler
        if config.resources.max_replicas > config.resources.min_replicas:
            hpa_manifest = {
                "apiVersion": "autoscaling/v2",
                "kind": "HorizontalPodAutoscaler",
                "metadata": {
                    "name": f"{config.service_name}-hpa",
                    "namespace": config.target.namespace or "default",
                },
                "spec": {
                    "scaleTargetRef": {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "name": config.service_name,
                    },
                    "minReplicas": config.resources.min_replicas,
                    "maxReplicas": config.resources.max_replicas,
                    "metrics": [
                        {
                            "type": "Resource",
                            "resource": {
                                "name": "cpu",
                                "target": {
                                    "type": "Utilization",
                                    "averageUtilization": 70,
                                },
                            },
                        }
                    ],
                },
            }
            manifests.append(hpa_manifest)

        return manifests

    def _get_deployment_strategy(self, strategy: DeploymentStrategy) -> builtins.dict[str, Any]:
        """Get Kubernetes deployment strategy configuration."""
        if strategy == DeploymentStrategy.ROLLING_UPDATE:
            return {
                "type": "RollingUpdate",
                "rollingUpdate": {"maxUnavailable": "25%", "maxSurge": "25%"},
            }
        if strategy == DeploymentStrategy.RECREATE:
            return {"type": "Recreate"}
        # Default to rolling update
        return {
            "type": "RollingUpdate",
            "rollingUpdate": {"maxUnavailable": "25%", "maxSurge": "25%"},
        }

    async def _apply_manifest(
        self, deployment: Deployment, manifest: builtins.dict[str, Any]
    ) -> bool:
        """Apply Kubernetes manifest."""
        try:
            # Convert manifest to YAML
            manifest_yaml = yaml.dump(manifest)

            # Apply using kubectl
            cmd = [self.kubectl_binary, "apply", "-f", "-"]

            if deployment.config.target.namespace:
                cmd.extend(["-n", deployment.config.target.namespace])

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate(input=manifest_yaml.encode())

            if process.returncode == 0:
                deployment.add_event(
                    "manifest_applied",
                    f"Applied {manifest['kind']}: {manifest['metadata']['name']}",
                )
                return True
            deployment.add_event(
                "manifest_failed",
                f"Failed to apply {manifest['kind']}: {stderr.decode()}",
                "error",
            )
            return False

        except Exception as e:
            deployment.add_event("manifest_error", f"Error applying manifest: {e!s}", "error")
            return False

    async def _wait_for_deployment_ready(self, deployment: Deployment, timeout: int = 300) -> bool:
        """Wait for deployment to be ready."""
        start_time = datetime.utcnow()

        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            status = await self.get_status(deployment)

            if status.get("healthy", False):
                return True

            await asyncio.sleep(5)

        return False

    async def _run_kubectl_command(self, cmd: builtins.list[str]) -> subprocess.CompletedProcess:
        """Run kubectl command."""
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode,
            stdout=stdout.decode() if stdout else "",
            stderr=stderr.decode() if stderr else "",
        )


class DeploymentManager:
    """Manages deployment lifecycle and coordination."""

    def __init__(self):
        self.providers: builtins.dict[InfrastructureProvider, DeploymentProvider] = {}
        self.deployments: builtins.dict[str, Deployment] = {}
        self.deployment_history: builtins.dict[str, builtins.list[Deployment]] = {}

    def register_provider(self, provider: DeploymentProvider):
        """Register deployment provider."""
        self.providers[provider.provider_type] = provider
        logger.info(f"Registered deployment provider: {provider.provider_type.value}")

    async def deploy(self, config: DeploymentConfig) -> Deployment:
        """Deploy service using configuration."""
        # Create deployment instance
        deployment = Deployment(id=str(uuid.uuid4()), config=config)

        # Store current deployment as previous version if exists
        service_key = f"{config.service_name}:{config.target.environment.value}"
        if service_key in self.deployment_history:
            previous_deployments = self.deployment_history[service_key]
            if previous_deployments:
                deployment.previous_version = previous_deployments[-1].config.version
                deployment.rollback_config = previous_deployments[-1].config

        self.deployments[deployment.id] = deployment

        # Add to history
        if service_key not in self.deployment_history:
            self.deployment_history[service_key] = []
        self.deployment_history[service_key].append(deployment)

        # Get provider
        provider = self.providers.get(config.target.provider)
        if not provider:
            deployment.status = DeploymentStatus.FAILED
            deployment.add_event(
                "provider_not_found",
                f"Provider not found: {config.target.provider.value}",
                "error",
            )
            return deployment

        # Execute deployment
        deployment.add_event("deployment_initiated", "Deployment initiated")
        success = await provider.deploy(deployment)

        if not success:
            deployment.add_event("deployment_failed", "Deployment failed", "error")

        return deployment

    async def rollback(self, deployment_id: str) -> bool:
        """Rollback deployment."""
        deployment = self.deployments.get(deployment_id)
        if not deployment:
            logger.error(f"Deployment not found: {deployment_id}")
            return False

        provider = self.providers.get(deployment.config.target.provider)
        if not provider:
            logger.error(f"Provider not found: {deployment.config.target.provider.value}")
            return False

        return await provider.rollback(deployment)

    async def scale(self, deployment_id: str, replicas: int) -> bool:
        """Scale deployment."""
        deployment = self.deployments.get(deployment_id)
        if not deployment:
            logger.error(f"Deployment not found: {deployment_id}")
            return False

        provider = self.providers.get(deployment.config.target.provider)
        if not provider:
            logger.error(f"Provider not found: {deployment.config.target.provider.value}")
            return False

        return await provider.scale(deployment, replicas)

    async def get_deployment_status(self, deployment_id: str) -> builtins.dict[str, Any] | None:
        """Get deployment status."""
        deployment = self.deployments.get(deployment_id)
        if not deployment:
            return None

        provider = self.providers.get(deployment.config.target.provider)
        if not provider:
            return None

        provider_status = await provider.get_status(deployment)

        return {
            "id": deployment.id,
            "service_name": deployment.config.service_name,
            "version": deployment.config.version,
            "status": deployment.status.value,
            "created_at": deployment.created_at.isoformat(),
            "updated_at": deployment.updated_at.isoformat(),
            "deployed_at": deployment.deployed_at.isoformat() if deployment.deployed_at else None,
            "provider_status": provider_status,
            "events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "type": event.event_type,
                    "message": event.message,
                    "level": event.level,
                }
                for event in deployment.events[-10:]  # Last 10 events
            ],
        }

    async def get_deployment_logs(self, deployment_id: str, lines: int = 100) -> builtins.list[str]:
        """Get deployment logs."""
        deployment = self.deployments.get(deployment_id)
        if not deployment:
            return []

        provider = self.providers.get(deployment.config.target.provider)
        if not provider:
            return []

        return await provider.get_logs(deployment, lines)

    async def terminate_deployment(self, deployment_id: str) -> bool:
        """Terminate deployment."""
        deployment = self.deployments.get(deployment_id)
        if not deployment:
            logger.error(f"Deployment not found: {deployment_id}")
            return False

        provider = self.providers.get(deployment.config.target.provider)
        if not provider:
            logger.error(f"Provider not found: {deployment.config.target.provider.value}")
            return False

        return await provider.terminate(deployment)

    def get_service_deployments(
        self, service_name: str, environment: EnvironmentType = None
    ) -> builtins.list[Deployment]:
        """Get all deployments for a service."""
        deployments = []

        for deployment in self.deployments.values():
            if deployment.config.service_name == service_name:
                if environment is None or deployment.config.target.environment == environment:
                    deployments.append(deployment)

        return sorted(deployments, key=lambda d: d.created_at, reverse=True)

    def get_environment_deployments(
        self, environment: EnvironmentType
    ) -> builtins.list[Deployment]:
        """Get all deployments for an environment."""
        deployments = []

        for deployment in self.deployments.values():
            if deployment.config.target.environment == environment:
                deployments.append(deployment)

        return sorted(deployments, key=lambda d: d.created_at, reverse=True)


# Utility functions
def create_deployment_config(
    service_name: str, version: str, image: str, target: DeploymentTarget, **kwargs
) -> DeploymentConfig:
    """Create deployment configuration with defaults."""
    config = DeploymentConfig(
        service_name=service_name, version=version, image=image, target=target
    )

    # Apply any additional configuration
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config


def create_kubernetes_target(
    name: str,
    environment: EnvironmentType,
    cluster: str = "default",
    namespace: str = "default",
) -> DeploymentTarget:
    """Create Kubernetes deployment target."""
    return DeploymentTarget(
        name=name,
        environment=environment,
        provider=InfrastructureProvider.KUBERNETES,
        cluster=cluster,
        namespace=namespace,
    )


@asynccontextmanager
async def deployment_context(manager: DeploymentManager, config: DeploymentConfig):
    """Context manager for deployment lifecycle."""
    deployment = None
    try:
        deployment = await manager.deploy(config)
        yield deployment
    finally:
        if deployment and deployment.status == DeploymentStatus.DEPLOYED:
            # Optionally terminate deployment in development environments
            if config.target.environment == EnvironmentType.DEVELOPMENT:
                await manager.terminate_deployment(deployment.id)
