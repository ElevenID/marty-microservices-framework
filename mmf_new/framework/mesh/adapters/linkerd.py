"""
Linkerd Adapter.
"""

import asyncio
import json
import logging
import subprocess
from typing import Any

from mmf_new.framework.mesh.ports.lifecycle import MeshLifecyclePort

logger = logging.getLogger(__name__)


class LinkerdAdapter(MeshLifecyclePort):
    """Linkerd implementation of MeshLifecyclePort."""

    def __init__(self):
        """Initialize Linkerd adapter."""
        self.is_installed = False

    async def check_installation(self) -> bool:
        """
        Check if Linkerd CLI tools are installed and available.

        Returns:
            bool: True if installed, False otherwise.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "linkerd",
                "version",
                "--client",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            self.is_installed = process.returncode == 0
        except FileNotFoundError:
            logger.info("linkerd CLI not found in PATH")
            self.is_installed = False
        except Exception as e:
            logger.error(f"Error checking Linkerd installation: {e}")
            self.is_installed = False

        return self.is_installed

    async def deploy(
        self, namespace: str = "linkerd", config: dict[str, Any] | None = None
    ) -> bool:
        """
        Deploy Linkerd to the cluster.

        Args:
            namespace: Kubernetes namespace to deploy to.
            config: Optional configuration for the deployment.

        Returns:
            bool: True if deployment was successful.
        """
        if not await self.check_installation():
            logger.error("Linkerd is not installed")
            return False

        try:
            # Pre-check
            check_cmd = ["linkerd", "check", "--pre"]
            process = await asyncio.create_subprocess_exec(
                *check_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"Linkerd pre-check failed: {stderr.decode()}")
                return False

            # Install Linkerd
            install_cmd = ["linkerd", "install"]
            process = await asyncio.create_subprocess_exec(
                *install_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                # Apply the installation
                apply_cmd = ["kubectl", "apply", "-f", "-"]
                apply_process = await asyncio.create_subprocess_exec(
                    *apply_cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await apply_process.communicate(input=stdout)

                if apply_process.returncode == 0:
                    logger.info("Linkerd installed successfully")
                    return True

            logger.error(f"Linkerd installation failed: {stderr.decode()}")
            return False

        except Exception as e:
            logger.error(f"Failed to deploy Linkerd: {e}")
            return False

    async def get_status(self) -> dict[str, Any]:
        """
        Get the current status of the service mesh.

        Returns:
            Dict[str, Any]: Status information.
        """
        status = {
            "installed": self.is_installed,
            "type": "linkerd",
            "components": {},
            "security_events": [],
        }

        if not self.is_installed:
            return status

        try:
            # Get check status
            process = await asyncio.create_subprocess_exec(
                "linkerd", "check", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()
            status["check_status"] = "ok" if process.returncode == 0 else "failed"
            status["check_output"] = stdout.decode()

            # Get security events
            status["security_events"] = await self._get_security_events("default")

        except Exception as e:
            logger.error(f"Failed to get Linkerd status: {e}")
            status["error"] = str(e)

        return status

    async def _get_security_events(self, namespace: str) -> list[dict[str, Any]]:
        """Get security events from Linkerd stats."""
        events = []
        try:
            cmd = ["linkerd", "stat", "deploy", "-n", namespace, "--output", "json"]
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await process.communicate()

            if process.returncode == 0:
                stats_data = json.loads(stdout.decode())
                for stat in stats_data.get("rows", []):
                    if stat.get("meshed", "") == "-":
                        events.append(
                            {
                                "timestamp": "now",
                                "type": "mesh_injection_missing",
                                "source": "linkerd",
                                "message": f"Service {stat.get('name')} is not meshed",
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
        Generate Linkerd deployment script.

        Args:
            service_name: Name of the service.
            config: Optional configuration.

        Returns:
            str: The generated deployment script.
        """
        config = config or {}

        script = f"""#!/bin/bash
# Enhanced Linkerd Deployment Script for {service_name}
# Generated by Marty Microservices Framework

set -e

echo "Deploying {service_name} with Linkerd service mesh..."

# Inject Linkerd proxy into deployment manifests
linkerd inject k8s/ | kubectl apply -f -
"""
        return script
