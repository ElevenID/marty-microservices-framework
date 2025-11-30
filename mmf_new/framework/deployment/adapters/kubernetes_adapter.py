"""
Kubernetes deployment adapter.
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any

import yaml

from mmf_new.framework.deployment.domain.enums import (
    DeploymentStatus,
    InfrastructureProvider,
)
from mmf_new.framework.deployment.domain.models import Deployment
from mmf_new.framework.deployment.ports.deployment_port import DeploymentPort

logger = logging.getLogger(__name__)


class KubernetesAdapter(DeploymentPort):
    """Kubernetes deployment provider."""

    def __init__(self, kubeconfig_path: str | None = None):
        self.provider_type = InfrastructureProvider.KUBERNETES
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

    async def get_status(self, deployment: Deployment) -> dict[str, Any]:
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

    async def _run_kubectl_command(self, cmd: list[str]) -> Any:
        """Run kubectl command."""

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        class CommandResult:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout.decode()
                self.stderr = stderr.decode()

        return CommandResult(process.returncode, stdout, stderr)

    def _generate_manifests(self, deployment: Deployment) -> list[dict[str, Any]]:
        """Generate Kubernetes manifests."""
        config = deployment.config

        # Labels
        labels = {
            "app": config.service_name,
            "version": config.version,
            "managed-by": "mmf",
        }
        labels.update(config.labels)

        # Deployment Manifest
        k8s_deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": config.service_name,
                "namespace": config.target.namespace or "default",
                "labels": labels,
                "annotations": config.annotations,
            },
            "spec": {
                "replicas": config.resources.replicas,
                "selector": {"matchLabels": {"app": config.service_name}},
                "template": {
                    "metadata": {
                        "labels": labels,
                    },
                    "spec": {
                        "serviceAccountName": config.service_account,
                        "containers": [
                            {
                                "name": config.service_name,
                                "image": config.image,
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
                                "ports": [{"containerPort": config.health_check.port}],
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
                                    "initialDelaySeconds": config.health_check.initial_delay,
                                    "periodSeconds": config.health_check.period,
                                    "timeoutSeconds": config.health_check.timeout,
                                    "failureThreshold": config.health_check.failure_threshold,
                                },
                            }
                        ],
                    },
                },
            },
        }

        # Service Manifest
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": config.service_name,
                "namespace": config.target.namespace or "default",
                "labels": labels,
            },
            "spec": {
                "selector": {"app": config.service_name},
                "ports": [
                    {
                        "protocol": "TCP",
                        "port": 80,
                        "targetPort": config.health_check.port,
                    }
                ],
                "type": "ClusterIP",
            },
        }

        return [k8s_deployment, service]

    async def _apply_manifest(self, deployment: Deployment, manifest: dict[str, Any]) -> bool:
        """Apply Kubernetes manifest."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                yaml.dump(manifest, f)
                temp_path = f.name

            cmd = [
                self.kubectl_binary,
                "apply",
                "-f",
                temp_path,
            ]

            if self.kubeconfig_path:
                cmd.extend(["--kubeconfig", self.kubeconfig_path])

            result = await self._run_kubectl_command(cmd)

            # Cleanup
            os.unlink(temp_path)

            if result.returncode != 0:
                logger.error(f"Failed to apply manifest: {result.stderr}")
                return False

            return True
        except Exception as e:
            logger.error(f"Error applying manifest: {e}")
            if "temp_path" in locals() and os.path.exists(temp_path):
                os.unlink(temp_path)
            return False

    async def _wait_for_deployment_ready(self, deployment: Deployment) -> bool:
        """Wait for deployment to be ready."""
        cmd = [
            self.kubectl_binary,
            "rollout",
            "status",
            f"deployment/{deployment.config.service_name}",
            "-n",
            deployment.config.target.namespace or "default",
            "--timeout=300s",
        ]

        if self.kubeconfig_path:
            cmd.extend(["--kubeconfig", self.kubeconfig_path])

        result = await self._run_kubectl_command(cmd)

        if result.returncode != 0:
            logger.error(f"Deployment failed to become ready: {result.stderr}")
            return False

        return True
