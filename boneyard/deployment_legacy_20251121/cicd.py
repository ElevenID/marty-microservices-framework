"""
CI/CD pipeline integration for Marty Microservices Framework.

This module provides comprehensive CI/CD pipeline integration capabilities including
GitOps workflows, automated deployment triggers, pipeline orchestration, and
deployment automation for microservices architectures.
"""

import asyncio
import builtins
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .core import DeploymentConfig
from .helm_charts import HelmChart

logger = logging.getLogger(__name__)


class PipelineProvider(Enum):
    """CI/CD pipeline providers."""

    GITHUB_ACTIONS = "github_actions"
    GITLAB_CI = "gitlab_ci"
    JENKINS = "jenkins"
    AZURE_DEVOPS = "azure_devops"
    TEKTON = "tekton"
    ARGO_WORKFLOWS = "argo_workflows"


class PipelineStage(Enum):
    """Pipeline stages."""

    BUILD = "build"
    TEST = "test"
    SECURITY_SCAN = "security_scan"
    DEPLOY_DEV = "deploy_dev"
    DEPLOY_STAGING = "deploy_staging"
    DEPLOY_PRODUCTION = "deploy_production"
    ROLLBACK = "rollback"


class PipelineStatus(Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class GitOpsProvider(Enum):
    """GitOps providers."""

    ARGOCD = "argocd"
    FLUX = "flux"
    JENKINS_X = "jenkins_x"


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
    duration: timedelta | None = None
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
    helm_charts: builtins.list[HelmChart] = field(default_factory=list)


class PipelineGenerator:
    """Generates CI/CD pipeline configurations."""

    def generate_github_actions_workflow(
        self, config: PipelineConfig, deployment_config: DeploymentConfig
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
        if PipelineStage.BUILD in config.stages:
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

        # Security scan job
        if PipelineStage.SECURITY_SCAN in config.stages:
            workflow["jobs"]["security"] = {
                "runs-on": "ubuntu-latest",
                "needs": "build" if PipelineStage.BUILD in config.stages else None,
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Run security scan",
                        "uses": "securecodewarrior/github-action-add-sarif@v1",
                        "with": {"sarif-file": "security-scan.sarif"},
                    },
                ],
            }

        # Deploy jobs
        deploy_stages = [s for s in config.stages if s.value.startswith("deploy_")]
        for stage in deploy_stages:
            env_name = stage.value.replace("deploy_", "")
            workflow["jobs"][f"deploy-{env_name}"] = {
                "runs-on": "ubuntu-latest",
                "needs": ["build", "test"] if not config.parallel_stages else "build",
                "environment": env_name,
                "if": f"github.ref == 'refs/heads/{config.branch}'",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "name": "Deploy to Kubernetes",
                        "run": f"""
                            helm upgrade --install {deployment_config.service_name}-{env_name} ./helm/{deployment_config.service_name} \\
                              --namespace {env_name} \\
                              --create-namespace \\
                              --set image.tag=${{{{ github.sha }}}} \\
                              --wait --timeout=5m
                        """,
                    },
                ],
            }

        return yaml.dump(workflow, default_flow_style=False)

    def generate_gitlab_ci_pipeline(
        self, config: PipelineConfig, deployment_config: DeploymentConfig
    ) -> str:
        """Generate GitLab CI pipeline."""
        pipeline = {
            "stages": [stage.value for stage in config.stages],
            "variables": config.environment_variables,
            "default": {"image": "docker:latest", "services": ["docker:dind"]},
        }

        # Build stage
        if PipelineStage.BUILD in config.stages:
            pipeline["build"] = {
                "stage": "build",
                "script": [
                    "docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY",
                    f"docker build -t $CI_REGISTRY_IMAGE/{deployment_config.service_name}:$CI_COMMIT_SHA .",
                    f"docker push $CI_REGISTRY_IMAGE/{deployment_config.service_name}:$CI_COMMIT_SHA",
                ],
                "only": ["main", "develop"],
            }

        # Test stage
        if PipelineStage.TEST in config.stages:
            pipeline["test"] = {
                "stage": "test",
                "script": ["make test"],
                "artifacts": {
                    "reports": {"junit": "test-results/junit.xml"},
                    "paths": ["test-results/"],
                },
            }

        # Security scan stage
        if PipelineStage.SECURITY_SCAN in config.stages:
            pipeline["security_scan"] = {
                "stage": "security_scan",
                "script": ["make security-scan"],
                "artifacts": {"reports": {"sast": "security-scan.json"}},
            }

        # Deploy stages
        deploy_stages = [s for s in config.stages if s.value.startswith("deploy_")]
        for stage in deploy_stages:
            env_name = stage.value.replace("deploy_", "")
            pipeline[f"deploy_{env_name}"] = {
                "stage": stage.value,
                "script": [
                    f"helm upgrade --install {deployment_config.service_name}-{env_name} ./helm/{deployment_config.service_name}",
                    f"--namespace {env_name}",
                    "--create-namespace",
                    "--set image.tag=$CI_COMMIT_SHA",
                    "--wait --timeout=5m",
                ],
                "environment": {
                    "name": env_name,
                    "url": f"https://{deployment_config.service_name}-{env_name}.example.com",
                },
                "only": ["main"] if env_name == "production" else ["main", "develop"],
            }

        return yaml.dump(pipeline, default_flow_style=False)

    def generate_jenkins_pipeline(
        self, config: PipelineConfig, deployment_config: DeploymentConfig
    ) -> str:
        """Generate Jenkins pipeline (Jenkinsfile)."""
        newline_char = "\n"
        stages_code = []

        # Build stage
        if PipelineStage.BUILD in config.stages:
            stages_code.append(
                """
        stage('Build') {
            steps {
                script {
                    docker.build("${REGISTRY}/${SERVICE_NAME}:${BUILD_NUMBER}")
                    docker.withRegistry("https://${REGISTRY}", 'registry-credentials') {
                        docker.image("${REGISTRY}/${SERVICE_NAME}:${BUILD_NUMBER}").push()
                        docker.image("${REGISTRY}/${SERVICE_NAME}:${BUILD_NUMBER}").push('latest')
                    }
                }
            }
        }"""
            )

        # Test stage
        if PipelineStage.TEST in config.stages:
            stages_code.append(
                """
        stage('Test') {
            steps {
                sh 'make test'
                publishTestResults testResultsPattern: 'test-results/junit.xml'
            }
        }"""
            )

        # Security scan stage
        if PipelineStage.SECURITY_SCAN in config.stages:
            stages_code.append(
                """
        stage('Security Scan') {
            steps {
                sh 'make security-scan'
                publishHTML([
                    allowMissing: false,
                    alwaysLinkToLastBuild: true,
                    keepAll: true,
                    reportDir: 'security-report',
                    reportFiles: 'index.html',
                    reportName: 'Security Scan Report'
                ])
            }
        }"""
            )

        # Deploy stages
        deploy_stages = [s for s in config.stages if s.value.startswith("deploy_")]
        for stage in deploy_stages:
            env_name = stage.value.replace("deploy_", "")
            stages_code.append(
                f"""
        stage('Deploy to {env_name.title()}') {{
            when {{
                branch '{config.branch}'
            }}
            steps {{
                script {{
                    sh '''
                        helm upgrade --install {deployment_config.service_name}-{env_name} ./helm/{deployment_config.service_name} \\
                          --namespace {env_name} \\
                          --create-namespace \\
                          --set image.tag=${{BUILD_NUMBER}} \\
                          --wait --timeout=5m
                    '''
                }}
            }}
        }}"""
            )

        pipeline = f"""
pipeline {{
    agent any

    environment {{
        REGISTRY = credentials('container-registry')
        SERVICE_NAME = '{deployment_config.service_name}'
    }}

    stages {{{newline_char.join(stages_code)}
    }}

    post {{
        always {{
            cleanWs()
        }}
        success {{
            slackSend(
                channel: '#deployments',
                color: 'good',
                message: "✅ Pipeline succeeded for ${{env.JOB_NAME}} - ${{env.BUILD_NUMBER}}"
            )
        }}
        failure {{
            slackSend(
                channel: '#deployments',
                color: 'danger',
                message: "❌ Pipeline failed for ${{env.JOB_NAME}} - ${{env.BUILD_NUMBER}}"
            )
        }}
    }}
}}
"""
        return pipeline

    def generate_tekton_pipeline(
        self, config: PipelineConfig, deployment_config: DeploymentConfig
    ) -> builtins.dict[str, Any]:
        """Generate Tekton pipeline."""
        tasks = []

        # Build task
        if PipelineStage.BUILD in config.stages:
            tasks.append(
                {
                    "name": "build",
                    "taskRef": {"name": "buildah"},
                    "params": [
                        {
                            "name": "IMAGE",
                            "value": f"$(params.REGISTRY)/{deployment_config.service_name}:$(params.TAG)",
                        },
                        {"name": "DOCKERFILE", "value": "./Dockerfile"},
                    ],
                    "workspaces": [{"name": "source", "workspace": "shared-workspace"}],
                }
            )

        # Test task
        if PipelineStage.TEST in config.stages:
            tasks.append(
                {
                    "name": "test",
                    "taskRef": {"name": "pytest"},
                    "runAfter": ["build"] if PipelineStage.BUILD in config.stages else None,
                    "workspaces": [{"name": "source", "workspace": "shared-workspace"}],
                }
            )

        # Deploy tasks
        deploy_stages = [s for s in config.stages if s.value.startswith("deploy_")]
        for stage in deploy_stages:
            env_name = stage.value.replace("deploy_", "")
            tasks.append(
                {
                    "name": f"deploy-{env_name}",
                    "taskRef": {"name": "helm-deploy"},
                    "runAfter": ["test"] if PipelineStage.TEST in config.stages else ["build"],
                    "params": [
                        {
                            "name": "CHART_PATH",
                            "value": f"./helm/{deployment_config.service_name}",
                        },
                        {
                            "name": "RELEASE_NAME",
                            "value": f"{deployment_config.service_name}-{env_name}",
                        },
                        {"name": "NAMESPACE", "value": env_name},
                        {"name": "VALUES", "value": "image.tag=$(params.TAG)"},
                    ],
                    "workspaces": [{"name": "source", "workspace": "shared-workspace"}],
                }
            )

        pipeline = {
            "apiVersion": "tekton.dev/v1beta1",
            "kind": "Pipeline",
            "metadata": {"name": config.name},
            "spec": {
                "params": [
                    {"name": "REGISTRY", "type": "string"},
                    {"name": "TAG", "type": "string"},
                ],
                "workspaces": [{"name": "shared-workspace"}],
                "tasks": tasks,
            },
        }

        return pipeline


class GitOpsManager:
    """Manages GitOps workflows."""

    def __init__(self, config: GitOpsConfig):
        self.config = config

    async def create_application(
        self, app_name: str, deployment_config: DeploymentConfig
    ) -> builtins.dict[str, Any]:
        """Create GitOps application."""
        if self.config.provider == GitOpsProvider.ARGOCD:
            return self._create_argocd_application(app_name, deployment_config)
        if self.config.provider == GitOpsProvider.FLUX:
            return self._create_flux_application(app_name, deployment_config)
        raise ValueError(f"Unsupported GitOps provider: {self.config.provider}")

    def _create_argocd_application(
        self, app_name: str, deployment_config: DeploymentConfig
    ) -> builtins.dict[str, Any]:
        """Create ArgoCD application."""
        app = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {"name": app_name, "namespace": "argocd"},
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": self.config.repository_url,
                    "targetRevision": self.config.branch,
                    "path": f"{self.config.path}/{app_name}",
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": deployment_config.target.namespace or "default",
                },
                "syncPolicy": {
                    "automated": {
                        "prune": self.config.prune,
                        "selfHeal": self.config.self_heal,
                    }
                    if self.config.auto_sync
                    else None,
                    "syncOptions": ["CreateNamespace=true"],
                },
            },
        }

        return app

    def _create_flux_application(
        self, app_name: str, deployment_config: DeploymentConfig
    ) -> builtins.dict[str, Any]:
        """Create Flux application."""
        app = {
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1beta2",
            "kind": "Kustomization",
            "metadata": {"name": app_name, "namespace": "flux-system"},
            "spec": {
                "interval": "5m",
                "path": f"./{self.config.path}/{app_name}",
                "prune": self.config.prune,
                "sourceRef": {"kind": "GitRepository", "name": app_name},
                "targetNamespace": deployment_config.target.namespace or "default",
            },
        }

        git_repo = {
            "apiVersion": "source.toolkit.fluxcd.io/v1beta2",
            "kind": "GitRepository",
            "metadata": {"name": app_name, "namespace": "flux-system"},
            "spec": {
                "interval": "1m",
                "ref": {"branch": self.config.branch},
                "url": self.config.repository_url,
            },
        }

        return {"kustomization": app, "gitrepository": git_repo}

    async def sync_application(self, app_name: str) -> bool:
        """Sync GitOps application."""
        try:
            if self.config.provider == GitOpsProvider.ARGOCD:
                return await self._sync_argocd_application(app_name)
            if self.config.provider == GitOpsProvider.FLUX:
                return await self._sync_flux_application(app_name)
            return False
        except Exception as e:
            logger.error(f"GitOps sync error: {e}")
            return False

    async def _sync_argocd_application(self, app_name: str) -> bool:
        """Sync ArgoCD application."""
        cmd = [
            "argocd",
            "app",
            "sync",
            app_name,
            "--timeout",
            str(self.config.timeout_seconds),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"ArgoCD application {app_name} synced successfully")
            return True
        logger.error(f"ArgoCD sync failed: {stderr.decode()}")
        return False

    async def _sync_flux_application(self, app_name: str) -> bool:
        """Sync Flux application."""
        cmd = [
            "flux",
            "reconcile",
            "kustomization",
            app_name,
            "--timeout",
            f"{self.config.timeout_seconds}s",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"Flux application {app_name} synced successfully")
            return True
        logger.error(f"Flux sync failed: {stderr.decode()}")
        return False


class CICDManager:
    """Manages CI/CD pipeline lifecycle."""

    def __init__(self):
        self.pipeline_generator = PipelineGenerator()
        self.executions: builtins.dict[str, PipelineExecution] = {}

    async def create_pipeline(self, pipeline: DeploymentPipeline, output_dir: Path) -> bool:
        """Create CI/CD pipeline configuration files."""
        try:
            config = pipeline.config
            deployment_config = pipeline.deployment_config

            if not deployment_config:
                raise ValueError("Deployment config is required")

            # Generate pipeline configuration
            if config.provider == PipelineProvider.GITHUB_ACTIONS:
                workflow_content = self.pipeline_generator.generate_github_actions_workflow(
                    config, deployment_config
                )

                workflows_dir = output_dir / ".github" / "workflows"
                workflows_dir.mkdir(parents=True, exist_ok=True)

                with open(workflows_dir / f"{config.name}.yml", "w") as f:
                    f.write(workflow_content)

            elif config.provider == PipelineProvider.GITLAB_CI:
                pipeline_content = self.pipeline_generator.generate_gitlab_ci_pipeline(
                    config, deployment_config
                )

                with open(output_dir / ".gitlab-ci.yml", "w") as f:
                    f.write(pipeline_content)

            elif config.provider == PipelineProvider.JENKINS:
                jenkinsfile_content = self.pipeline_generator.generate_jenkins_pipeline(
                    config, deployment_config
                )

                with open(output_dir / "Jenkinsfile", "w") as f:
                    f.write(jenkinsfile_content)

            elif config.provider == PipelineProvider.TEKTON:
                tekton_pipeline = self.pipeline_generator.generate_tekton_pipeline(
                    config, deployment_config
                )

                tekton_dir = output_dir / "tekton"
                tekton_dir.mkdir(exist_ok=True)

                with open(tekton_dir / "pipeline.yaml", "w") as f:
                    yaml.dump(tekton_pipeline, f, default_flow_style=False)

            # Create GitOps configuration if specified
            if pipeline.gitops_config:
                await self._create_gitops_config(pipeline, output_dir)

            logger.info(f"Created CI/CD pipeline: {config.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to create pipeline: {e}")
            return False

    async def _create_gitops_config(self, pipeline: DeploymentPipeline, output_dir: Path) -> None:
        """Create GitOps configuration."""
        gitops_config = pipeline.gitops_config
        deployment_config = pipeline.deployment_config

        if not gitops_config or not deployment_config:
            return

        gitops_manager = GitOpsManager(gitops_config)
        app_name = f"{deployment_config.service_name}-{deployment_config.target.environment.value}"

        app_config = await gitops_manager.create_application(app_name, deployment_config)

        gitops_dir = output_dir / "gitops"
        gitops_dir.mkdir(exist_ok=True)

        if gitops_config.provider == GitOpsProvider.ARGOCD:
            with open(gitops_dir / f"{app_name}-application.yaml", "w") as f:
                yaml.dump(app_config, f, default_flow_style=False)

        elif gitops_config.provider == GitOpsProvider.FLUX:
            with open(gitops_dir / f"{app_name}-kustomization.yaml", "w") as f:
                yaml.dump(app_config["kustomization"], f, default_flow_style=False)

            with open(gitops_dir / f"{app_name}-gitrepository.yaml", "w") as f:
                yaml.dump(app_config["gitrepository"], f, default_flow_style=False)

    async def trigger_pipeline(
        self, pipeline_name: str, commit_sha: str, triggered_by: str
    ) -> PipelineExecution | None:
        """Trigger pipeline execution."""
        try:
            execution = PipelineExecution(
                id=f"{pipeline_name}-{commit_sha[:8]}",
                pipeline_name=pipeline_name,
                status=PipelineStatus.PENDING,
                started_at=datetime.utcnow(),
                commit_sha=commit_sha,
                triggered_by=triggered_by,
            )

            self.executions[execution.id] = execution

            # Simulate pipeline execution
            asyncio.create_task(self._execute_pipeline(execution))

            logger.info(f"Triggered pipeline: {execution.id}")
            return execution

        except Exception as e:
            logger.error(f"Failed to trigger pipeline: {e}")
            return None

    async def _execute_pipeline(self, execution: PipelineExecution) -> None:
        """Execute pipeline stages."""
        try:
            execution.status = PipelineStatus.RUNNING

            # Simulate stage execution
            stages = [PipelineStage.BUILD, PipelineStage.TEST, PipelineStage.DEPLOY_DEV]

            for stage in stages:
                execution.stages[stage.value] = PipelineStatus.RUNNING

                # Simulate stage execution time
                await asyncio.sleep(2)

                # Simulate stage completion
                execution.stages[stage.value] = PipelineStatus.SUCCESS
                logger.info(f"Stage {stage.value} completed for {execution.id}")

            execution.status = PipelineStatus.SUCCESS
            execution.finished_at = datetime.utcnow()
            execution.duration = execution.finished_at - execution.started_at

            logger.info(f"Pipeline {execution.id} completed successfully")

        except Exception as e:
            execution.status = PipelineStatus.FAILURE
            execution.finished_at = datetime.utcnow()
            execution.duration = execution.finished_at - execution.started_at
            logger.error(f"Pipeline {execution.id} failed: {e}")

    async def get_pipeline_status(self, execution_id: str) -> PipelineExecution | None:
        """Get pipeline execution status."""
        return self.executions.get(execution_id)

    async def list_pipeline_executions(
        self, pipeline_name: str | None = None
    ) -> builtins.list[PipelineExecution]:
        """List pipeline executions."""
        executions = list(self.executions.values())

        if pipeline_name:
            executions = [e for e in executions if e.pipeline_name == pipeline_name]

        return sorted(executions, key=lambda x: x.started_at, reverse=True)

    async def cancel_pipeline(self, execution_id: str) -> bool:
        """Cancel pipeline execution."""
        execution = self.executions.get(execution_id)

        if not execution:
            return False

        if execution.status in [PipelineStatus.PENDING, PipelineStatus.RUNNING]:
            execution.status = PipelineStatus.CANCELLED
            execution.finished_at = datetime.utcnow()
            execution.duration = execution.finished_at - execution.started_at

            logger.info(f"Pipeline {execution_id} cancelled")
            return True

        return False


# Utility functions
def create_deployment_pipeline(
    name: str,
    service_config: DeploymentConfig,
    provider: PipelineProvider = PipelineProvider.GITHUB_ACTIONS,
    enable_gitops: bool = False,
) -> DeploymentPipeline:
    """Create deployment pipeline configuration."""
    pipeline_config = PipelineConfig(
        name=f"{name}-pipeline",
        provider=provider,
        repository_url=f"https://github.com/example/{name}",
        stages=[
            PipelineStage.BUILD,
            PipelineStage.TEST,
            PipelineStage.SECURITY_SCAN,
            PipelineStage.DEPLOY_DEV,
            PipelineStage.DEPLOY_STAGING,
            PipelineStage.DEPLOY_PRODUCTION,
        ],
    )

    gitops_config = None
    if enable_gitops:
        gitops_config = GitOpsConfig(
            provider=GitOpsProvider.ARGOCD,
            repository_url=f"https://github.com/example/{name}-gitops",
        )

    return DeploymentPipeline(
        name=name,
        config=pipeline_config,
        gitops_config=gitops_config,
        deployment_config=service_config,
    )


async def deploy_with_cicd(
    manager: CICDManager,
    pipeline: DeploymentPipeline,
    commit_sha: str,
    triggered_by: str = "automated",
) -> builtins.tuple[bool, str | None]:
    """Deploy service using CI/CD pipeline."""
    try:
        execution = await manager.trigger_pipeline(pipeline.config.name, commit_sha, triggered_by)

        if not execution:
            return False, "Failed to trigger pipeline"

        # Wait for pipeline completion (simplified)
        timeout = 300  # 5 minutes
        start_time = datetime.utcnow()

        while (datetime.utcnow() - start_time).total_seconds() < timeout:
            current_execution = await manager.get_pipeline_status(execution.id)

            if not current_execution:
                return False, "Pipeline execution not found"

            if current_execution.status == PipelineStatus.SUCCESS:
                return True, f"Pipeline {execution.id} completed successfully"
            if current_execution.status == PipelineStatus.FAILURE:
                return False, f"Pipeline {execution.id} failed"
            if current_execution.status == PipelineStatus.CANCELLED:
                return False, f"Pipeline {execution.id} was cancelled"

            await asyncio.sleep(5)

        return False, f"Pipeline {execution.id} timed out"

    except Exception as e:
        return False, f"CI/CD deployment error: {e!s}"
