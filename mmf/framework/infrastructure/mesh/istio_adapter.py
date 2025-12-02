"""
Istio Service Mesh Adapter

Implementation of service mesh ports for Istio.
"""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

from mmf.core.security.domain.models.service_mesh import (
    PolicySyncResult,
    ServiceMeshPolicy,
)
from mmf.core.security.ports.service_mesh import IServiceMeshManager
from mmf.framework.mesh.ports.lifecycle import MeshLifecyclePort

logger = logging.getLogger(__name__)


class IstioAdapter(MeshLifecyclePort, IServiceMeshManager):
    """Istio implementation of service mesh ports."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.namespace = self.config.get("namespace", "istio-system")
        self.kubectl_cmd = self.config.get("kubectl_cmd", "kubectl")
        self.istioctl_cmd = self.config.get("istioctl_cmd", "istioctl")

    # MeshLifecyclePort implementation

    async def check_installation(self) -> bool:
        """Check if Istio CLI is installed."""
        try:
            result = await asyncio.create_subprocess_exec(
                self.istioctl_cmd,
                "version",
                "--remote=false",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            return result.returncode == 0
        except FileNotFoundError:
            logger.info("istioctl not found in PATH")
            return False
        except Exception as e:
            logger.error("Error checking Istio installation: %s", e)
            return False

    async def deploy(
        self, namespace: str = "istio-system", config: dict[str, Any] | None = None
    ) -> bool:
        """Deploy Istio service mesh."""
        try:
            # Install Istio
            cmd = [
                self.istioctl_cmd,
                "install",
                "--set",
                "values.global.meshConfig.defaultConfig.proxyStatsMatcher.inclusionRegexps=.*outlier_detection.*",
                "--set",
                "values.pilot.env.EXTERNAL_ISTIOD=false",
                "--set",
                "values.global.meshConfig.defaultConfig.discoveryRefreshDelay=10s",
                "--set",
                "values.global.meshConfig.defaultConfig.proxyMetadata.ISTIO_META_DNS_CAPTURE=true",
                "-y",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error("Istio installation failed: %s", stderr.decode())
                return False

            logger.info("Istio installed successfully")

            # Enable sidecar injection
            await self._enable_sidecar_injection(namespace)
            return True

        except Exception as e:
            logger.error("Failed to deploy Istio: %s", e)
            return False

    async def get_status(self) -> dict[str, Any]:
        """Get Istio status."""
        installed = await self.check_installation()
        return {"type": "istio", "installed": installed, "namespace": self.namespace}

    async def verify_prerequisites(self) -> bool:
        """Verify prerequisites for Istio."""
        # Basic check: is kubectl available?
        try:
            result = await asyncio.create_subprocess_exec(
                self.kubectl_cmd,
                "version",
                "--client",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            return result.returncode == 0
        except Exception:
            return False

    # IServiceMeshManager implementation

    async def apply_policy(self, policy: ServiceMeshPolicy) -> bool:
        """Apply a single security policy."""
        # Convert domain model to K8s resource
        resource = policy.to_kubernetes_manifest()
        return await self._apply_k8s_resource(resource)

    async def apply_policies(self, policies: list[ServiceMeshPolicy]) -> PolicySyncResult:
        """Apply multiple policies."""
        success_count = 0
        failed_count = 0
        errors = []

        for policy in policies:
            if await self.apply_policy(policy):
                success_count += 1
            else:
                failed_count += 1
                errors.append(f"Failed to apply policy {policy.name}")

        return PolicySyncResult(
            success=failed_count == 0,
            policies_applied=success_count,
            policies_failed=failed_count,
            errors=errors,
        )

    async def remove_policy(self, policy_name: str, namespace: str) -> bool:
        """Remove a policy."""
        # Try to delete AuthorizationPolicy by default, or try multiple types
        # Since we don't know the type, we'll try the most common ones
        kinds = [
            "authorizationpolicy",
            "requestauthentication",
            "peerauthentication",
            "envoyfilter",
        ]

        success = False
        for kind in kinds:
            try:
                cmd = [
                    self.kubectl_cmd,
                    "delete",
                    kind,
                    policy_name,
                    "-n",
                    namespace,
                    "--ignore-not-found",
                ]
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                if process.returncode == 0:
                    success = True  # Considered success if command ran, even if not found (due to ignore-not-found)
            except Exception as e:
                logger.warning("Failed to delete %s %s: %s", kind, policy_name, e)

        return success

    # Helper methods

    async def _enable_sidecar_injection(self, namespace: str) -> None:
        """Enable automatic sidecar injection."""
        try:
            cmd = [
                self.kubectl_cmd,
                "label",
                "namespace",
                namespace,
                "istio-injection=enabled",
                "--overwrite",
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            logger.info("Enabled sidecar injection for namespace: %s", namespace)
        except Exception as e:
            logger.warning("Failed to enable sidecar injection: %s", e)

    async def _apply_k8s_resource(self, resource: dict[str, Any]) -> bool:
        """Apply Kubernetes resource using kubectl."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                yaml.dump(resource, f, default_flow_style=False)
                temp_file = f.name

            try:
                result = await asyncio.create_subprocess_exec(
                    self.kubectl_cmd,
                    "apply",
                    "-f",
                    temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await result.communicate()

                if result.returncode != 0:
                    logger.error("Failed to apply resource: %s", stderr.decode())
                    return False
                return True
            finally:
                Path(temp_file).unlink(missing_ok=True)
        except Exception as e:
            logger.error("Failed to apply K8s resource: %s", e)
            return False
