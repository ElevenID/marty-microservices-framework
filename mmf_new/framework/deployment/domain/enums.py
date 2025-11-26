"""
Enums for deployment domain.
"""

from enum import Enum


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


class IaCProvider(Enum):
    """Infrastructure as Code providers."""

    TERRAFORM = "terraform"
    PULUMI = "pulumi"
    CLOUDFORMATION = "cloudformation"
    ARM = "arm"
    CDK = "cdk"


class CloudProvider(Enum):
    """Cloud providers."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    KUBERNETES = "kubernetes"


class ResourceType(Enum):
    """Infrastructure resource types."""

    COMPUTE = "compute"
    STORAGE = "storage"
    NETWORK = "network"
    DATABASE = "database"
    LOAD_BALANCER = "load_balancer"
    SECURITY_GROUP = "security_group"
    IAM = "iam"
    MONITORING = "monitoring"
    SECRETS = "secrets"


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
