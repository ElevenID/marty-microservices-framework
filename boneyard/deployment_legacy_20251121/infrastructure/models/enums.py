"""
Enums for infrastructure deployment components.
"""

from enum import Enum


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
