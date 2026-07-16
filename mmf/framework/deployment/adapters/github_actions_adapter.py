"""
GitHub Actions pipeline adapter.
"""

import logging
import os
from datetime import datetime
from typing import Any

import yaml

from mmf.framework.deployment.domain.enums import (
    PipelineProvider,
    PipelineStage,
    PipelineStatus,
)
from mmf.framework.deployment.domain.models import (
    DeploymentConfig,
    DeploymentPipeline,
    PipelineConfig,
    PipelineExecution,
)
from mmf.framework.deployment.ports.pipeline_port import PipelinePort

logger = logging.getLogger(__name__)


class GithubActionsAdapter(PipelinePort):
    """GitHub Actions pipeline provider."""

    async def create_pipeline(self, pipeline: DeploymentPipeline) -> bool:
        """Create or update CI/CD pipeline."""
        try:
            workflow_content = self.generate_github_actions_workflow(
                pipeline.config, pipeline.deployment_config
            )

            # Ensure .github/workflows directory exists
            workflows_dir = os.path.join(".github", "workflows")
            os.makedirs(workflows_dir, exist_ok=True)

            # Write workflow file
            filename = f"{pipeline.config.name.lower().replace(' ', '-')}.yaml"
            filepath = os.path.join(workflows_dir, filename)

            with open(filepath, "w") as f:
                f.write(workflow_content)

            logger.info(f"Generated workflow file at: {filepath}")
            logger.info(
                "Note: You need to commit and push this file to GitHub to activate the pipeline."
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create pipeline: {e}")
            return False

    async def trigger_pipeline(
        self, pipeline_name: str, variables: dict[str, Any] | None = None
    ) -> PipelineExecution:
        """Trigger pipeline execution."""
        # TODO: Implement GitHub API call to trigger workflow dispatch
        return PipelineExecution(
            id="mock-id",
            pipeline_name=pipeline_name,
            status=PipelineStatus.PENDING,
            started_at=datetime.utcnow(),
        )

    async def get_pipeline_status(self, execution_id: str) -> PipelineExecution:
        """Get pipeline execution status."""
        # TODO: Implement GitHub API call to get workflow run status
        return PipelineExecution(
            id=execution_id,
            pipeline_name="unknown",
            status=PipelineStatus.UNKNOWN,
            started_at=datetime.utcnow(),
        )

    def generate_github_actions_workflow(
        self, config: PipelineConfig, deployment_config: DeploymentConfig | None
    ) -> str:
        """Generate GitHub Actions workflow."""
        workflow = {
            "name": config.name,
            "on": {
                "push": {"branches": [config.branch]},
                "pull_request": {"branches": [config.branch]},
            },
            "env": config.environment_variables,
            "jobs": {},
        }

        # Build job
        if PipelineStage.BUILD in config.stages and deployment_config:
            workflow["jobs"]["build"] = {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Set up Docker Buildx",
                        "uses": "docker/setup-buildx-action@v3",
                    },
                    {
                        "name": "Login to Container Registry",
                        "uses": "docker/login-action@v3",
                        "with": {
                            "registry": "${{ secrets.CONTAINER_REGISTRY }}",
                            "username": "${{ secrets.REGISTRY_USERNAME }}",
                            "password": "${{ secrets.REGISTRY_PASSWORD }}",
                        },
                    },
                    {
                        "name": "Build and push Docker image",
                        "uses": "docker/build-push-action@v5",
                        "with": {
                            "context": ".",
                            "push": True,
                            "tags": f"${{{{ secrets.CONTAINER_REGISTRY }}}}/{deployment_config.service_name}:${{{{ github.sha }}}}",
                        },
                    },
                ],
            }

        # Test job
        if PipelineStage.TEST in config.stages:
            workflow["jobs"]["test"] = {
                "runs-on": "ubuntu-latest",
                "needs": "build" if PipelineStage.BUILD in config.stages else None,
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"name": "Run tests", "run": "make test"},
                    {
                        "name": "Upload test results",
                        "uses": "actions/upload-artifact@v3",
                        "with": {"name": "test-results", "path": "test-results/"},
                    },
                ],
            }

        # Security Scan job
        if PipelineStage.SECURITY_SCAN in config.stages and deployment_config:
            workflow["jobs"]["security-scan"] = {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Run Trivy vulnerability scanner",
                        "uses": "aquasecurity/trivy-action@master",
                        "with": {
                            "image-ref": f"${{{{ secrets.CONTAINER_REGISTRY }}}}/{deployment_config.service_name}:${{{{ github.sha }}}}",
                            "format": "table",
                            "exit-code": "1",
                            "ignore-unfixed": True,
                            "vuln-type": "os,library",
                            "severity": "CRITICAL,HIGH",
                        },
                    },
                ],
            }
            if PipelineStage.BUILD in config.stages:
                workflow["jobs"]["security-scan"]["needs"] = "build"

        # Deploy job
        deploy_stages = [
            (PipelineStage.DEPLOY_DEV, "development"),
            (PipelineStage.DEPLOY_STAGING, "staging"),
            (PipelineStage.DEPLOY_PRODUCTION, "production"),
        ]

        for stage, env_name in deploy_stages:
            if stage in config.stages and deployment_config:
                job_name = f"deploy-{env_name}"
                workflow["jobs"][job_name] = {
                    "runs-on": "ubuntu-latest",
                    "environment": env_name,
                    "needs": ["test", "security-scan"]
                    if PipelineStage.TEST in config.stages
                    and PipelineStage.SECURITY_SCAN in config.stages
                    else ["build"],
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Set up kubectl",
                            "uses": "azure/setup-kubectl@v3",
                        },
                        {
                            "name": "Deploy to Kubernetes",
                            "run": f"""
                                kubectl set image deployment/{deployment_config.service_name} {deployment_config.service_name}=${{{{ secrets.CONTAINER_REGISTRY }}}}/{deployment_config.service_name}:${{{{ github.sha }}}} -n {deployment_config.target.namespace or "default"}
                                kubectl rollout status deployment/{deployment_config.service_name} -n {deployment_config.target.namespace or "default"}
                            """,
                        },
                    ],
                }

        return yaml.dump(workflow, sort_keys=False)
