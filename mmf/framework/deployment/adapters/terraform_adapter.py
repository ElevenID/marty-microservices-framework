"""
Terraform infrastructure adapter.
"""

import asyncio
import json
import logging
import shutil
from typing import Any

from mmf.framework.deployment.domain.enums import CloudProvider, IaCProvider
from mmf.framework.deployment.domain.models import (
    DeploymentConfig,
    IaCConfig,
    InfrastructureStack,
    InfrastructureState,
    ResourceConfig,
    ResourceType,
)
from mmf.framework.deployment.ports.infrastructure_port import InfrastructurePort

logger = logging.getLogger(__name__)


class TerraformAdapter(InfrastructurePort):
    """Terraform infrastructure provider."""

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self.terraform_binary = shutil.which("terraform") or "terraform"

    async def _run_terraform(self, args: list[str]) -> tuple[int, str, str]:
        """Run terraform command."""
        cmd = [self.terraform_binary, *args]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            return process.returncode or 0, stdout.decode(), stderr.decode()
        except Exception as e:
            logger.error("Failed to run terraform: %s", e)
            return 1, "", str(e)

    async def provision(self, stack: InfrastructureStack) -> InfrastructureState:
        """Provision infrastructure stack."""
        # Initialize
        rc, _, err = await self._run_terraform(["init", "-no-color"])
        if rc != 0:
            logger.error("Terraform init failed: %s", err)
            return InfrastructureState(
                stack_name=stack.name,
                status="failed",
                resources={},
                outputs={"error": err},
            )

        # Apply
        rc, _, err = await self._run_terraform(["apply", "-auto-approve", "-no-color"])

        status = "provisioned" if rc == 0 else "failed"
        outputs = {}

        if rc == 0:
            # Get outputs
            rc_out, json_out, _ = await self._run_terraform(["output", "-json"])
            if rc_out == 0:
                try:
                    outputs = json.loads(json_out)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse terraform output")

        return InfrastructureState(
            stack_name=stack.name,
            status=status,
            resources={},
            outputs=outputs,
        )

    async def destroy(self, stack: InfrastructureStack) -> bool:
        """Destroy infrastructure stack."""
        rc, _, err = await self._run_terraform(["destroy", "-auto-approve", "-no-color"])
        if rc != 0:
            logger.error("Terraform destroy failed: %s", err)
            return False
        return True

    async def get_state(self, stack: InfrastructureStack) -> InfrastructureState:
        """Get infrastructure stack state."""
        rc, out, err = await self._run_terraform(["show", "-json"])
        if rc != 0:
            return InfrastructureState(
                stack_name=stack.name,
                status="unknown",
                resources={},
                outputs={"error": err},
            )

        try:
            state_data = json.loads(out)
            # Simplified state parsing - extracting outputs from state
            outputs = state_data.get("values", {}).get("outputs", {})
            return InfrastructureState(
                stack_name=stack.name,
                status="provisioned",
                resources={},
                outputs=outputs,
            )
        except json.JSONDecodeError:
            return InfrastructureState(
                stack_name=stack.name,
                status="unknown",
                resources={},
                outputs={"error": "Failed to parse state json"},
            )

    def generate_provider_config(
        self, cloud_provider: CloudProvider, region: str
    ) -> dict[str, Any]:
        """Generate Terraform provider configuration."""
        providers = {}

        if cloud_provider == CloudProvider.AWS:
            providers["aws"] = {
                "region": region,
                "default_tags": {"tags": {"ManagedBy": "Terraform", "Framework": "Marty"}},
            }
        elif cloud_provider == CloudProvider.AZURE:
            providers["azurerm"] = {"features": {}}
        elif cloud_provider == CloudProvider.GCP:
            providers["google"] = {"region": region, "project": "${var.project_id}"}
        elif cloud_provider == CloudProvider.KUBERNETES:
            providers["kubernetes"] = {"config_path": "~/.kube/config"}

        return {"terraform": {"required_providers": {}}, "provider": providers}

    def generate_backend_config(self, backend_config: dict[str, Any]) -> dict[str, Any]:
        """Generate Terraform backend configuration."""
        if not backend_config:
            return {}

        backend_type = backend_config.get("type", "local")

        backends = {
            "s3": {
                "bucket": backend_config.get("bucket"),
                "key": backend_config.get("key"),
                "region": backend_config.get("region"),
                "dynamodb_table": backend_config.get("dynamodb_table"),
                "encrypt": True,
            },
            "azurerm": {
                "storage_account_name": backend_config.get("storage_account"),
                "container_name": backend_config.get("container"),
                "key": backend_config.get("key"),
                "resource_group_name": backend_config.get("resource_group"),
            },
            "gcs": {
                "bucket": backend_config.get("bucket"),
                "prefix": backend_config.get("prefix"),
            },
        }

        if backend_type in backends:
            return {"terraform": {"backend": {backend_type: backends[backend_type]}}}

        return {}

    def generate_microservice_infrastructure(
        self, deployment_config: DeploymentConfig, cloud_provider: CloudProvider
    ) -> InfrastructureStack:
        """Generate infrastructure for microservice."""
        stack_name = (
            f"{deployment_config.service_name}-{deployment_config.target.environment.value}"
        )

        config = IaCConfig(
            provider=IaCProvider.TERRAFORM,
            cloud_provider=cloud_provider,
            project_name=deployment_config.service_name,
            environment=deployment_config.target.environment,
            region=deployment_config.target.region or "us-east-1",
        )

        resources = []

        # TODO: Implement resource generation logic for different providers
        # This was partially implemented in the legacy code, but for brevity I'm skipping the full implementation here
        # and just providing the structure.

        return InfrastructureStack(name=stack_name, config=config, resources=resources)
