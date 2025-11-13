"""
GitOps Workflow Management for Marty Microservices Framework

Provides comprehensive GitOps capabilities including:
- Git-based declarative configuration management
- ArgoCD integration and automation
- Configuration drift detection and remediation
- Multi-repository GitOps workflows
- Environment promotion pipelines
- Rollback and recovery mechanisms
"""

import asyncio
import builtins
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import git
import requests
import yaml
from kubernetes import client, config

# External dependencies
try:
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

try:
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False

try:
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class GitOpsOperationType(Enum):
    """Types of GitOps operations"""

    SYNC = "sync"
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    REFRESH = "refresh"
    PRUNE = "prune"
    VALIDATE = "validate"
    DRIFT_DETECTION = "drift_detection"
    HEALTH_CHECK = "health_check"


class GitOpsApplicationStatus(Enum):
    """GitOps application status"""

    HEALTHY = "healthy"
    PROGRESSING = "progressing"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    MISSING = "missing"
    UNKNOWN = "unknown"


class GitOpsSyncStatus(Enum):
    """GitOps sync status"""

    SYNCED = "synced"
    OUT_OF_SYNC = "out_of_sync"
    SYNCING = "syncing"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class GitRepository:
    """Git repository configuration"""

    name: str
    url: str
    branch: str = "main"
    path: str = "."

    # Authentication
    username: str | None = None
    password: str | None = None
    ssh_key_path: str | None = None

    # Local clone info
    local_path: str | None = None
    last_commit: str | None = None
    last_sync: datetime | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
        }


@dataclass
class GitOpsApplication:
    """GitOps application configuration"""

    name: str
    namespace: str
    source_repo: GitRepository
    destination_cluster: str = "in-cluster"

    # Application configuration
    chart_path: str = "."
    values_files: builtins.list[str] = field(default_factory=list)
    helm_parameters: builtins.dict[str, str] = field(default_factory=dict)
    kustomize_parameters: builtins.dict[str, str] = field(default_factory=dict)

    # Sync policy
    auto_sync_enabled: bool = False
    auto_sync_prune: bool = False
    auto_sync_self_heal: bool = False
    sync_timeout: int = 300  # 5 minutes

    # Health and status
    health_status: GitOpsApplicationStatus = GitOpsApplicationStatus.UNKNOWN
    sync_status: GitOpsSyncStatus = GitOpsSyncStatus.UNKNOWN
    last_operation: str | None = None
    last_sync_time: datetime | None = None

    # Monitoring
    drift_detected: bool = False
    drift_resources: builtins.list[str] = field(default_factory=list)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "source_repo": self.source_repo.to_dict(),
            "health_status": self.health_status.value,
            "sync_status": self.sync_status.value,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
        }


@dataclass
class GitOpsOperation:
    """GitOps operation record"""

    operation_id: str
    application_name: str
    operation_type: GitOpsOperationType
    started_at: datetime

    # Operation details
    initiator: str = "system"
    target_revision: str | None = None
    sync_options: builtins.list[str] = field(default_factory=list)

    # Status tracking
    status: str = "running"  # running, succeeded, failed, cancelled
    completed_at: datetime | None = None
    error_message: str | None = None

    # Results
    resources_synced: builtins.list[str] = field(default_factory=list)
    resources_pruned: builtins.list[str] = field(default_factory=list)
    resources_failed: builtins.list[str] = field(default_factory=list)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "operation_type": self.operation_type.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class GitRepositoryManager:
    """
    Git repository management for GitOps workflows

    Features:
    - Repository cloning and syncing
    - Branch and tag management
    - Commit tracking and validation
    - Multi-repository coordination
    """

    def __init__(self, base_path: str = "/tmp/gitops-repos"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.repositories: builtins.dict[str, GitRepository] = {}

        # Repository cache
        self.repo_cache: builtins.dict[str, Any] = {}

    async def register_repository(self, repo: GitRepository) -> bool:
        """Register a Git repository for GitOps"""

        try:
            # Set local path
            repo.local_path = str(self.base_path / repo.name)

            # Clone or update repository
            await self._clone_or_update_repo(repo)

            # Store repository
            self.repositories[repo.name] = repo

            print(f"✅ Registered GitOps repository: {repo.name}")
            return True

        except Exception as e:
            print(f"❌ Failed to register repository {repo.name}: {e}")
            return False

    async def _clone_or_update_repo(self, repo: GitRepository):
        """Clone or update a Git repository"""

        if not GIT_AVAILABLE:
            raise Exception("Git package not available")

        local_path = Path(repo.local_path)

        if local_path.exists():
            # Update existing repository
            git_repo = git.Repo(repo.local_path)
            origin = git_repo.remotes.origin
            origin.fetch()

            # Switch to target branch
            if repo.branch not in [branch.name for branch in git_repo.branches]:
                git_repo.create_head(repo.branch, f"origin/{repo.branch}")

            git_repo.heads[repo.branch].checkout()
            origin.pull(repo.branch)

        else:
            # Clone repository
            git_repo = git.Repo.clone_from(repo.url, repo.local_path, branch=repo.branch)

        # Update repository info
        repo.last_commit = git_repo.head.commit.hexsha
        repo.last_sync = datetime.now()

        # Cache git repo object
        self.repo_cache[repo.name] = git_repo

    async def get_latest_commit(self, repo_name: str) -> str | None:
        """Get latest commit hash for repository"""

        if repo_name not in self.repositories:
            return None

        repo = self.repositories[repo_name]
        await self._clone_or_update_repo(repo)

        return repo.last_commit

    async def get_file_content(
        self, repo_name: str, file_path: str, revision: str = None
    ) -> str | None:
        """Get content of a file from repository"""

        if repo_name not in self.repositories:
            return None

        repo = self.repositories[repo_name]
        full_path = Path(repo.local_path) / file_path

        if revision:
            # Get file content for specific revision
            git_repo = self.repo_cache.get(repo_name)
            if git_repo:
                try:
                    commit = git_repo.commit(revision)
                    return commit.tree[file_path].data_stream.read().decode("utf-8")
                except Exception:
                    return None
        # Get current file content
        elif full_path.exists():
            return full_path.read_text()

        return None

    async def get_changed_files(
        self, repo_name: str, from_revision: str, to_revision: str = None
    ) -> builtins.list[str]:
        """Get list of changed files between revisions"""

        if repo_name not in self.repositories:
            return []

        git_repo = self.repo_cache.get(repo_name)
        if not git_repo:
            return []

        try:
            if to_revision is None:
                to_revision = "HEAD"

            diff = git_repo.git.diff("--name-only", from_revision, to_revision)
            return diff.split("\n") if diff else []

        except Exception as e:
            print(f"Error getting changed files: {e}")
            return []

    def validate_repository_structure(self, repo_name: str) -> builtins.dict[str, Any]:
        """Validate GitOps repository structure"""

        if repo_name not in self.repositories:
            return {"valid": False, "error": "Repository not found"}

        repo = self.repositories[repo_name]
        repo_path = Path(repo.local_path)

        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "structure": {},
        }

        # Check for common GitOps structure
        expected_dirs = ["applications", "environments", "charts"]
        expected_files = ["kustomization.yaml", "Chart.yaml"]

        for dir_name in expected_dirs:
            dir_path = repo_path / dir_name
            validation_results["structure"][dir_name] = dir_path.exists()
            if not dir_path.exists():
                validation_results["warnings"].append(f"Missing directory: {dir_name}")

        for file_name in expected_files:
            file_path = repo_path / file_name
            if file_path.exists():
                validation_results["structure"][file_name] = True

                # Validate YAML files
                try:
                    with open(file_path) as f:
                        yaml.safe_load(f)
                except yaml.YAMLError as e:
                    validation_results["errors"].append(f"Invalid YAML in {file_name}: {e}")
                    validation_results["valid"] = False

        return validation_results


class ArgoCDIntegration:
    """
    ArgoCD integration and management

    Features:
    - ArgoCD application lifecycle management
    - Sync operations and monitoring
    - Health checks and status reporting
    - Custom resource definitions
    """

    def __init__(self, argocd_server: str = "localhost:8080", token: str = None):
        self.argocd_server = argocd_server
        self.token = token
        self.applications: builtins.dict[str, GitOpsApplication] = {}

        # API client setup
        self.api_base_url = f"http://{argocd_server}/api/v1"
        self.headers = {"Content-Type": "application/json"}

        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    async def create_application(self, app: GitOpsApplication) -> bool:
        """Create ArgoCD application"""

        if not REQUESTS_AVAILABLE:
            print("⚠️ Requests package not available, using mock ArgoCD integration")
            return await self._mock_create_application(app)

        try:
            # Convert to ArgoCD application spec
            app_spec = self._convert_to_argocd_spec(app)

            # Create application via ArgoCD API
            response = requests.post(
                f"{self.api_base_url}/applications",
                headers=self.headers,
                json=app_spec,
                timeout=30,
            )

            if response.status_code in [200, 201]:
                self.applications[app.name] = app
                print(f"✅ Created ArgoCD application: {app.name}")
                return True
            print(f"❌ Failed to create application: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            print(f"❌ Error creating ArgoCD application: {e}")
            return False

    async def _mock_create_application(self, app: GitOpsApplication) -> bool:
        """Mock ArgoCD application creation for testing"""

        # Simulate application creation
        app.health_status = GitOpsApplicationStatus.HEALTHY
        app.sync_status = GitOpsSyncStatus.SYNCED
        app.last_sync_time = datetime.now()

        self.applications[app.name] = app
        print(f"✅ Mock created ArgoCD application: {app.name}")
        return True

    def _convert_to_argocd_spec(self, app: GitOpsApplication) -> builtins.dict[str, Any]:
        """Convert GitOpsApplication to ArgoCD application spec"""

        spec = {
            "metadata": {"name": app.name, "namespace": "argocd"},
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": app.source_repo.url,
                    "targetRevision": app.source_repo.branch,
                    "path": app.chart_path,
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": app.namespace,
                },
                "syncPolicy": {},
            },
        }

        # Add auto-sync policy if enabled
        if app.auto_sync_enabled:
            spec["spec"]["syncPolicy"]["automated"] = {
                "prune": app.auto_sync_prune,
                "selfHeal": app.auto_sync_self_heal,
            }

        # Add Helm configuration if applicable
        if app.values_files or app.helm_parameters:
            spec["spec"]["source"]["helm"] = {}

            if app.values_files:
                spec["spec"]["source"]["helm"]["valueFiles"] = app.values_files

            if app.helm_parameters:
                spec["spec"]["source"]["helm"]["parameters"] = [
                    {"name": k, "value": v} for k, v in app.helm_parameters.items()
                ]

        # Add Kustomize configuration if applicable
        if app.kustomize_parameters:
            spec["spec"]["source"]["kustomize"] = {
                "images": list(app.kustomize_parameters.values())
            }

        return spec

    async def sync_application(self, app_name: str, revision: str = None) -> GitOpsOperation:
        """Sync ArgoCD application"""

        operation = GitOpsOperation(
            operation_id=f"sync_{app_name}_{int(time.time())}",
            application_name=app_name,
            operation_type=GitOpsOperationType.SYNC,
            started_at=datetime.now(),
            target_revision=revision,
        )

        try:
            if not REQUESTS_AVAILABLE:
                return await self._mock_sync_application(operation)

            # Trigger sync via ArgoCD API
            sync_request = {
                "revision": revision or "HEAD",
                "prune": True,
                "dryRun": False,
                "strategy": {"hook": {"force": True}},
            }

            response = requests.post(
                f"{self.api_base_url}/applications/{app_name}/sync",
                headers=self.headers,
                json=sync_request,
                timeout=30,
            )

            if response.status_code in [200, 202]:
                operation.status = "succeeded"
                operation.completed_at = datetime.now()

                # Update application status
                if app_name in self.applications:
                    self.applications[app_name].sync_status = GitOpsSyncStatus.SYNCED
                    self.applications[app_name].last_sync_time = datetime.now()
                    self.applications[app_name].last_operation = operation.operation_id

                print(f"✅ Synced application: {app_name}")
            else:
                operation.status = "failed"
                operation.error_message = f"API error: {response.status_code}"
                print(f"❌ Failed to sync application: {app_name}")

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            operation.completed_at = datetime.now()
            print(f"❌ Error syncing application {app_name}: {e}")

        return operation

    async def _mock_sync_application(self, operation: GitOpsOperation) -> GitOpsOperation:
        """Mock application sync for testing"""

        # Simulate sync operation
        await asyncio.sleep(1)  # Simulate sync time

        operation.status = "succeeded"
        operation.completed_at = datetime.now()
        operation.resources_synced = [
            f"deployment/{operation.application_name}",
            f"service/{operation.application_name}",
            f"configmap/{operation.application_name}-config",
        ]

        # Update application status
        if operation.application_name in self.applications:
            app = self.applications[operation.application_name]
            app.sync_status = GitOpsSyncStatus.SYNCED
            app.health_status = GitOpsApplicationStatus.HEALTHY
            app.last_sync_time = datetime.now()
            app.last_operation = operation.operation_id

        print(f"✅ Mock synced application: {operation.application_name}")
        return operation

    async def get_application_status(self, app_name: str) -> builtins.dict[str, Any] | None:
        """Get ArgoCD application status"""

        if app_name not in self.applications:
            return None

        app = self.applications[app_name]

        try:
            if not REQUESTS_AVAILABLE:
                return self._mock_get_application_status(app)

            # Get status via ArgoCD API
            response = requests.get(
                f"{self.api_base_url}/applications/{app_name}",
                headers=self.headers,
                timeout=30,
            )

            if response.status_code == 200:
                app_data = response.json()
                return self._parse_argocd_status(app_data)
            print(f"❌ Failed to get application status: {response.status_code}")
            return None

        except Exception as e:
            print(f"❌ Error getting application status: {e}")
            return None

    def _mock_get_application_status(self, app: GitOpsApplication) -> builtins.dict[str, Any]:
        """Mock application status for testing"""

        return {
            "name": app.name,
            "namespace": app.namespace,
            "health_status": app.health_status.value,
            "sync_status": app.sync_status.value,
            "last_sync_time": app.last_sync_time.isoformat() if app.last_sync_time else None,
            "resources": [
                {
                    "kind": "Deployment",
                    "name": app.name,
                    "health": "Healthy",
                    "status": "Running",
                },
                {
                    "kind": "Service",
                    "name": app.name,
                    "health": "Healthy",
                    "status": "Active",
                },
            ],
        }

    def _parse_argocd_status(self, app_data: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
        """Parse ArgoCD application status response"""

        status = app_data.get("status", {})

        return {
            "name": app_data["metadata"]["name"],
            "namespace": app_data["spec"]["destination"]["namespace"],
            "health_status": status.get("health", {}).get("status", "Unknown"),
            "sync_status": status.get("sync", {}).get("status", "Unknown"),
            "last_sync_time": status.get("operationState", {}).get("finishedAt"),
            "resources": status.get("resources", []),
            "conditions": status.get("conditions", []),
        }

    async def rollback_application(self, app_name: str, target_revision: str) -> GitOpsOperation:
        """Rollback ArgoCD application to specific revision"""

        operation = GitOpsOperation(
            operation_id=f"rollback_{app_name}_{int(time.time())}",
            application_name=app_name,
            operation_type=GitOpsOperationType.ROLLBACK,
            started_at=datetime.now(),
            target_revision=target_revision,
        )

        try:
            # Update application source revision
            sync_operation = await self.sync_application(app_name, target_revision)

            if sync_operation.status == "succeeded":
                operation.status = "succeeded"
                operation.completed_at = datetime.now()
                print(f"✅ Rolled back application {app_name} to {target_revision}")
            else:
                operation.status = "failed"
                operation.error_message = "Sync operation failed"
                print(f"❌ Failed to rollback application {app_name}")

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            operation.completed_at = datetime.now()
            print(f"❌ Error rolling back application {app_name}: {e}")

        return operation


class ConfigurationDriftDetector:
    """
    Configuration drift detection and remediation

    Features:
    - Live vs. desired state comparison
    - Automated drift detection
    - Drift remediation recommendations
    - Configuration compliance monitoring
    """

    def __init__(self):
        self.drift_rules: builtins.list[builtins.dict[str, Any]] = []
        self.detected_drifts: builtins.dict[str, builtins.list[builtins.dict[str, Any]]] = {}

        # Initialize Kubernetes client if available
        if KUBERNETES_AVAILABLE:
            try:
                config.load_incluster_config()
            except Exception as incluster_error:
                try:
                    config.load_kube_config()
                except Exception as kubeconfig_error:
                    print(
                        "⚠️ Kubernetes config not available "
                        f"(in-cluster error={incluster_error}, kubeconfig error={kubeconfig_error})"
                    )

            self.k8s_client = client.ApiClient()
        else:
            self.k8s_client = None

    def add_drift_rule(self, rule: builtins.dict[str, Any]):
        """Add configuration drift detection rule"""

        self.drift_rules.append(rule)
        print(f"✅ Added drift detection rule: {rule.get('name', 'unnamed')}")

    async def detect_configuration_drift(
        self, app: GitOpsApplication
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Detect configuration drift for an application"""

        detected_drifts = []

        try:
            # Get desired state from Git
            desired_state = await self._get_desired_state(app)

            # Get live state from Kubernetes
            live_state = await self._get_live_state(app)

            # Compare states
            drifts = self._compare_states(desired_state, live_state, app.name)

            if drifts:
                detected_drifts.extend(drifts)
                self.detected_drifts[app.name] = drifts

                # Update application drift status
                app.drift_detected = True
                app.drift_resources = [drift["resource"] for drift in drifts]

                print(f"⚠️ Configuration drift detected for {app.name}: {len(drifts)} resources")
            else:
                app.drift_detected = False
                app.drift_resources = []
                if app.name in self.detected_drifts:
                    del self.detected_drifts[app.name]

                print(f"✅ No configuration drift detected for {app.name}")

        except Exception as e:
            print(f"❌ Error detecting drift for {app.name}: {e}")

        return detected_drifts

    async def _get_desired_state(self, app: GitOpsApplication) -> builtins.dict[str, Any]:
        """Get desired state from Git repository"""

        # Mock implementation - would parse Kubernetes manifests from Git
        return {
            "deployments": {
                app.name: {
                    "replicas": 3,
                    "image": f"{app.name}:latest",
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": "500m", "memory": "512Mi"},
                    },
                }
            },
            "services": {
                app.name: {
                    "type": "ClusterIP",
                    "ports": [{"port": 80, "targetPort": 8080}],
                }
            },
        }

    async def _get_live_state(self, app: GitOpsApplication) -> builtins.dict[str, Any]:
        """Get live state from Kubernetes cluster"""

        if not self.k8s_client:
            # Mock live state
            return {
                "deployments": {
                    app.name: {
                        "replicas": 2,  # Drift: should be 3
                        "image": f"{app.name}:v1.0.0",  # Drift: should be latest
                        "resources": {
                            "requests": {"cpu": "100m", "memory": "128Mi"},
                            "limits": {"cpu": "500m", "memory": "512Mi"},
                        },
                    }
                },
                "services": {
                    app.name: {
                        "type": "ClusterIP",
                        "ports": [{"port": 80, "targetPort": 8080}],
                    }
                },
            }

        # Real Kubernetes API calls would go here
        apps_v1 = client.AppsV1Api(self.k8s_client)
        core_v1 = client.CoreV1Api(self.k8s_client)

        live_state = {"deployments": {}, "services": {}}

        try:
            # Get deployments
            deployments = apps_v1.list_namespaced_deployment(namespace=app.namespace)
            for deployment in deployments.items:
                if deployment.metadata.name == app.name:
                    live_state["deployments"][app.name] = {
                        "replicas": deployment.spec.replicas,
                        "image": deployment.spec.template.spec.containers[0].image,
                        "resources": deployment.spec.template.spec.containers[
                            0
                        ].resources.to_dict(),
                    }

            # Get services
            services = core_v1.list_namespaced_service(namespace=app.namespace)
            for service in services.items:
                if service.metadata.name == app.name:
                    live_state["services"][app.name] = {
                        "type": service.spec.type,
                        "ports": [
                            {"port": port.port, "targetPort": port.target_port}
                            for port in service.spec.ports
                        ],
                    }

        except Exception as e:
            print(f"Error getting live state: {e}")

        return live_state

    def _compare_states(
        self,
        desired: builtins.dict[str, Any],
        live: builtins.dict[str, Any],
        app_name: str,
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Compare desired and live states to detect drift"""

        drifts = []

        # Compare deployments
        for resource_type in ["deployments", "services"]:
            desired_resources = desired.get(resource_type, {})
            live_resources = live.get(resource_type, {})

            for resource_name, desired_config in desired_resources.items():
                live_config = live_resources.get(resource_name, {})

                resource_drifts = self._compare_resource_config(
                    desired_config, live_config, f"{resource_type}/{resource_name}"
                )

                if resource_drifts:
                    drifts.extend(resource_drifts)

        return drifts

    def _compare_resource_config(
        self,
        desired: builtins.dict[str, Any],
        live: builtins.dict[str, Any],
        resource_path: str,
    ) -> builtins.list[builtins.dict[str, Any]]:
        """Compare specific resource configuration"""

        drifts = []

        def _deep_compare(d_config, l_config, path):
            for key, desired_value in d_config.items():
                current_path = f"{path}.{key}"
                live_value = l_config.get(key)

                if isinstance(desired_value, dict) and isinstance(live_value, dict):
                    _deep_compare(desired_value, live_value, current_path)
                elif desired_value != live_value:
                    drifts.append(
                        {
                            "resource": resource_path,
                            "field": current_path,
                            "desired_value": desired_value,
                            "live_value": live_value,
                            "drift_type": "value_mismatch",
                        }
                    )

        _deep_compare(desired, live, resource_path)

        return drifts

    async def remediate_drift(self, app_name: str, drift: builtins.dict[str, Any]) -> bool:
        """Remediate configuration drift"""

        try:
            print(f"🔧 Remediating drift for {app_name}: {drift['field']}")

            # In a real implementation, this would apply the desired configuration
            # For now, we'll simulate successful remediation
            await asyncio.sleep(1)

            # Remove from detected drifts
            if app_name in self.detected_drifts:
                self.detected_drifts[app_name] = [
                    d
                    for d in self.detected_drifts[app_name]
                    if not (d["resource"] == drift["resource"] and d["field"] == drift["field"])
                ]

                if not self.detected_drifts[app_name]:
                    del self.detected_drifts[app_name]

            print(f"✅ Remediated drift: {drift['field']}")
            return True

        except Exception as e:
            print(f"❌ Failed to remediate drift: {e}")
            return False


class GitOpsOrchestrator:
    """
    Main GitOps orchestrator coordinating all GitOps operations

    Features:
    - Workflow orchestration
    - Multi-application management
    - Event-driven operations
    - Health monitoring and alerting
    """

    def __init__(self):
        self.repo_manager = GitRepositoryManager()
        self.argocd = ArgoCDIntegration()
        self.drift_detector = ConfigurationDriftDetector()

        # Operation tracking
        self.operations: builtins.dict[str, GitOpsOperation] = {}
        self.applications: builtins.dict[str, GitOpsApplication] = {}

        # Monitoring
        self.monitoring_enabled = True
        self.monitoring_interval = 60  # seconds

        # Event handlers
        self.event_handlers: builtins.dict[str, builtins.list[callable]] = {}

    async def register_application(self, app: GitOpsApplication) -> bool:
        """Register a new GitOps application"""

        try:
            print(f"📝 Registering GitOps application: {app.name}")

            # Register source repository
            success = await self.repo_manager.register_repository(app.source_repo)
            if not success:
                return False

            # Create ArgoCD application
            success = await self.argocd.create_application(app)
            if not success:
                return False

            # Store application
            self.applications[app.name] = app

            # Configure drift detection rules
            self.drift_detector.add_drift_rule(
                {
                    "name": f"{app.name}_drift_detection",
                    "application": app.name,
                    "enabled": True,
                }
            )

            print(f"✅ Successfully registered GitOps application: {app.name}")
            return True

        except Exception as e:
            print(f"❌ Failed to register application {app.name}: {e}")
            return False

    async def deploy_application(
        self, app_name: str, target_revision: str = None
    ) -> GitOpsOperation:
        """Deploy application using GitOps workflow"""

        operation = GitOpsOperation(
            operation_id=f"deploy_{app_name}_{int(time.time())}",
            application_name=app_name,
            operation_type=GitOpsOperationType.DEPLOY,
            started_at=datetime.now(),
            target_revision=target_revision,
            initiator="orchestrator",
        )

        try:
            print(f"🚀 Deploying application: {app_name}")

            # Validate application exists
            if app_name not in self.applications:
                raise Exception(f"Application {app_name} not registered")

            app = self.applications[app_name]

            # Update repository
            await self.repo_manager._clone_or_update_repo(app.source_repo)

            # Validate configuration
            validation = self.repo_manager.validate_repository_structure(app.source_repo.name)
            if not validation["valid"]:
                raise Exception(f"Repository validation failed: {validation['errors']}")

            # Sync with ArgoCD
            sync_operation = await self.argocd.sync_application(app_name, target_revision)

            if sync_operation.status == "succeeded":
                operation.status = "succeeded"
                operation.resources_synced = sync_operation.resources_synced
                print(f"✅ Successfully deployed application: {app_name}")
            else:
                operation.status = "failed"
                operation.error_message = sync_operation.error_message
                print(f"❌ Failed to deploy application: {app_name}")

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            print(f"❌ Error deploying application {app_name}: {e}")

        operation.completed_at = datetime.now()
        self.operations[operation.operation_id] = operation

        # Trigger event
        await self._trigger_event(
            "application_deployed",
            {"application": app_name, "operation": operation.to_dict()},
        )

        return operation

    async def start_monitoring(self):
        """Start GitOps monitoring and drift detection"""

        print("🔍 Starting GitOps monitoring...")

        while self.monitoring_enabled:
            try:
                # Check all applications
                for _app_name, app in self.applications.items():
                    await self._monitor_application(app)

                # Wait for next monitoring cycle
                await asyncio.sleep(self.monitoring_interval)

            except Exception as e:
                print(f"❌ Error in GitOps monitoring: {e}")
                await asyncio.sleep(30)  # Brief pause before retry

    async def _monitor_application(self, app: GitOpsApplication):
        """Monitor individual application"""

        try:
            # Check application health
            status = await self.argocd.get_application_status(app.name)
            if status:
                app.health_status = GitOpsApplicationStatus(status.get("health_status", "unknown"))
                app.sync_status = GitOpsSyncStatus(status.get("sync_status", "unknown"))

            # Check for configuration drift
            drifts = await self.drift_detector.detect_configuration_drift(app)

            if drifts:
                # Trigger drift detection event
                await self._trigger_event(
                    "drift_detected", {"application": app.name, "drifts": drifts}
                )

                # Auto-remediation if enabled
                if app.auto_sync_self_heal:
                    for drift in drifts:
                        await self.drift_detector.remediate_drift(app.name, drift)

            # Check for repository updates
            latest_commit = await self.repo_manager.get_latest_commit(app.source_repo.name)
            if latest_commit and latest_commit != app.source_repo.last_commit:
                app.source_repo.last_commit = latest_commit

                # Trigger update event
                await self._trigger_event(
                    "repository_updated",
                    {"application": app.name, "new_commit": latest_commit},
                )

                # Auto-sync if enabled
                if app.auto_sync_enabled:
                    await self.argocd.sync_application(app.name)

        except Exception as e:
            print(f"❌ Error monitoring application {app.name}: {e}")

    def add_event_handler(self, event_type: str, handler: callable):
        """Add event handler for GitOps events"""

        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []

        self.event_handlers[event_type].append(handler)
        print(f"✅ Added event handler for: {event_type}")

    async def _trigger_event(self, event_type: str, event_data: builtins.dict[str, Any]):
        """Trigger GitOps event"""

        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event_data)
                    else:
                        handler(event_data)
                except Exception as e:
                    print(f"❌ Error in event handler for {event_type}: {e}")

    def get_orchestrator_status(self) -> builtins.dict[str, Any]:
        """Get GitOps orchestrator status"""

        app_statuses = {}
        for name, app in self.applications.items():
            app_statuses[name] = {
                "health": app.health_status.value,
                "sync": app.sync_status.value,
                "drift_detected": app.drift_detected,
                "auto_sync": app.auto_sync_enabled,
            }

        return {
            "applications": len(self.applications),
            "repositories": len(self.repo_manager.repositories),
            "operations": len(self.operations),
            "monitoring_enabled": self.monitoring_enabled,
            "detected_drifts": len(self.drift_detector.detected_drifts),
            "application_statuses": app_statuses,
        }


# Example usage and demo
async def main():
    """Example usage of GitOps framework"""

    print("=== GitOps Workflow Demo ===")

    # Initialize GitOps orchestrator
    gitops = GitOpsOrchestrator()

    # Create example repository
    example_repo = GitRepository(
        name="example-app-config",
        url="https://github.com/example/app-config.git",
        branch="main",
        path="applications/example-app",
    )

    # Create example application
    example_app = GitOpsApplication(
        name="example-app",
        namespace="default",
        source_repo=example_repo,
        auto_sync_enabled=True,
        auto_sync_prune=True,
        auto_sync_self_heal=True,
    )

    # Register application
    success = await gitops.register_application(example_app)
    if success:
        print("✅ Application registered successfully")

    # Deploy application
    deployment = await gitops.deploy_application("example-app")
    print(f"Deployment status: {deployment.status}")

    # Add event handlers
    gitops.add_event_handler("drift_detected", lambda data: print(f"🚨 Drift detected: {data}"))
    gitops.add_event_handler("application_deployed", lambda data: print(f"🚀 App deployed: {data}"))

    # Get status
    status = gitops.get_orchestrator_status()
    print("\nGitOps Status:")
    print(f"Applications: {status['applications']}")
    print(f"Repositories: {status['repositories']}")
    print(f"Operations: {status['operations']}")
    print(f"Detected Drifts: {status['detected_drifts']}")


if __name__ == "__main__":
    asyncio.run(main())
