"""
Istio Adapter.
"""

import asyncio
import logging
import subprocess
from typing import Any

from mmf.framework.mesh.ports.lifecycle import MeshLifecyclePort

logger = logging.getLogger(__name__)


class IstioAdapter(MeshLifecyclePort):
    """Istio implementation of MeshLifecyclePort."""

    def __init__(self):
        """Initialize Istio adapter."""
        self.is_installed = False

    async def check_installation(self) -> bool:
        """
        Check if Istio CLI tools are installed and available.

        Returns:
            bool: True if installed, False otherwise.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "istioctl",
                "version",
                "--remote=false",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            self.is_installed = process.returncode == 0
        except FileNotFoundError:
            logger.info("istioctl CLI not found in PATH")
            self.is_installed = False
        except Exception as e:
            logger.error(f"Error checking Istio installation: {e}")
            self.is_installed = False

        return self.is_installed

    async def deploy(
        self, namespace: str = "istio-system", config: dict[str, Any] | None = None
    ) -> bool:
        """
        Deploy Istio to the cluster.

        Args:
            namespace: Kubernetes namespace to deploy to.
            config: Optional configuration for the deployment.

        Returns:
            bool: True if deployment was successful.
        """
        if not await self.check_installation():
            logger.error("Istio is not installed")
            return False

        try:
            # Install Istio with configuration
            cmd = [
                "istioctl",
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

            # Add custom config if provided
            if config:
                for key, value in config.items():
                    cmd.extend(["--set", f"{key}={value}"])

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info("Istio installed successfully")
                # Enable automatic sidecar injection for default namespace or specified namespace
                target_namespace = (
                    config.get("target_namespace", "default") if config else "default"
                )
                await self._enable_sidecar_injection(target_namespace)
                return True
            else:
                logger.error(f"Istio installation failed: {stderr.decode()}")
                return False

        except Exception as e:
            logger.error(f"Failed to deploy Istio: {e}")
            return False

    async def _enable_sidecar_injection(self, namespace: str) -> None:
        """Enable automatic sidecar injection for a namespace."""
        try:
            cmd = [
                "kubectl",
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
            logger.info(f"Enabled sidecar injection for namespace: {namespace}")
        except Exception as e:
            logger.warning(f"Failed to enable sidecar injection: {e}")

    async def get_status(self) -> dict[str, Any]:
        """
        Get the current status of the service mesh.

        Returns:
            Dict[str, Any]: Status information.
        """
        status = {
            "installed": self.is_installed,
            "type": "istio",
            "components": {},
            "security_events": [],
        }

        if not self.is_installed:
            return status

        try:
            # Get proxy status
            process = await asyncio.create_subprocess_exec(
                "istioctl",
                "proxy-status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            if process.returncode == 0:
                status["proxy_status"] = stdout.decode()

            # Get security events (simplified version of old code)
            # In a real implementation, we might want to pass the namespace
            status["security_events"] = await self._get_security_events("default")

        except Exception as e:
            logger.error(f"Failed to get Istio status: {e}")
            status["error"] = str(e)

        return status

    async def _get_security_events(self, namespace: str) -> list[dict[str, Any]]:
        """Get security events from Istio access logs."""
        events = []
        try:
            cmd = ["kubectl", "logs", "-l", "app=istio-proxy", "-n", namespace, "--tail=100"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()

            if process.returncode == 0:
                log_lines = stdout.decode().split("\n")
                for line in log_lines:
                    if any(
                        indicator in line.lower()
                        for indicator in ["denied", "unauthorized", "forbidden"]
                    ):
                        events.append(
                            {
                                "timestamp": "now",
                                "type": "security_violation",
                                "source": "istio",
                                "message": line.strip(),
                                "namespace": namespace,
                            }
                        )
        except Exception as e:
            logger.warning(f"Failed to get security events: {e}")

        return events

    async def verify_prerequisites(self) -> bool:
        """
        Verify that the environment meets the prerequisites for deployment.

        Returns:
            bool: True if prerequisites are met.
        """
        # Check for kubectl
        try:
            process = await asyncio.create_subprocess_exec(
                "kubectl",
                "version",
                "--client",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            if process.returncode != 0:
                logger.error("kubectl not found or not working")
                return False
        except FileNotFoundError:
            logger.error("kubectl not found")
            return False

        return True

    async def generate_deployment_script(
        self, service_name: str, config: dict[str, Any] | None = None
    ) -> str:
        """
        Generate Istio deployment script.

        Args:
            service_name: Name of the service.
            config: Optional configuration.

        Returns:
            str: The generated deployment script.
        """
        config = config or {}
        security_config = config.get("security", {})

        script = f"""#!/bin/bash
# Enhanced Istio Deployment Script for {service_name}
# Generated by Marty Microservices Framework

set -e

echo "Deploying {service_name} with Istio service mesh..."

# Apply Kubernetes manifests
kubectl apply -f k8s/

# Ensure namespace has sidecar injection enabled
kubectl label namespace default istio-injection=enabled --overwrite
"""

        if security_config:
            script += f"""
# Apply Istio-specific configurations
cat <<EOF | kubectl apply -f -
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: {service_name}-peer-auth
  namespace: default
spec:
  selector:
    matchLabels:
      app: {service_name}
  mtls:
    mode: {security_config.get("mtls_mode", "STRICT")}
EOF
"""
        return script
