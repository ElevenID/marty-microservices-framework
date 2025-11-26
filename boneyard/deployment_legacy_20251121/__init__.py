"""
Deployment module for Marty Microservices Framework.

This module provides comprehensive deployment automation capabilities including:
- Core deployment orchestration and lifecycle management
- Helm chart generation and management
- CI/CD pipeline integration with GitOps workflows
- Infrastructure as Code (Terraform/Pulumi) provisioning
- Kubernetes operators for automated operations

The module supports multiple deployment strategies, environment management,
and cloud provider integrations for enterprise microservices deployment.
"""

from .cicd import (  # CI/CD classes; Enums; Utility functions
    CICDManager,
    DeploymentPipeline,
    GitOpsConfig,
    GitOpsManager,
    GitOpsProvider,
    PipelineConfig,
    PipelineExecution,
    PipelineGenerator,
    PipelineProvider,
    PipelineStage,
    PipelineStatus,
    create_deployment_pipeline,
    deploy_with_cicd,
)
from .core import (  # Core deployment classes; Enums; Utility functions
    Deployment,
    DeploymentConfig,
    DeploymentManager,
    DeploymentStatus,
    DeploymentStrategy,
    DeploymentTarget,
    EnvironmentType,
    HealthCheck,
    InfrastructureProvider,
    KubernetesProvider,
    ResourceRequirements,
    create_deployment_config,
    create_kubernetes_target,
    deployment_context,
)
from .helm_charts import (  # Helm management classes; Enums; Utility functions
    ChartType,
    HelmAction,
    HelmChart,
    HelmManager,
    HelmRelease,
    HelmTemplateGenerator,
    HelmValues,
    create_helm_values_from_config,
    deploy_with_helm,
)
from .infrastructure import (  # IaC classes; Enums; Utility functions
    CloudProvider,
    IaCConfig,
    IaCProvider,
    InfrastructureManager,
    InfrastructureStack,
    InfrastructureState,
    PulumiGenerator,
    ResourceConfig,
    ResourceType,
    TerraformGenerator,
    create_microservice_infrastructure,
    deploy_infrastructure,
)
from .operators import (  # Operator classes; Enums; Utility functions
    CustomResourceDefinition,
    CustomResourceManager,
    MicroserviceOperator,
    OperatorConfig,
    OperatorManager,
    OperatorType,
    ReconciliationAction,
    ReconciliationEvent,
    create_operator_config,
    deploy_microservice_with_operator,
)

__all__ = [
    # CI/CD pipelines
    "CICDManager",
    "ChartType",
    "CloudProvider",
    "CustomResourceDefinition",
    "CustomResourceManager",
    "Deployment",
    "DeploymentConfig",
    # Core deployment
    "DeploymentManager",
    "DeploymentPipeline",
    "DeploymentStatus",
    "DeploymentStrategy",
    "DeploymentTarget",
    "EnvironmentType",
    "GitOpsConfig",
    "GitOpsManager",
    "GitOpsProvider",
    "HealthCheck",
    "HelmAction",
    "HelmChart",
    # Helm charts
    "HelmManager",
    "HelmRelease",
    "HelmTemplateGenerator",
    "HelmValues",
    "IaCConfig",
    "IaCProvider",
    # Infrastructure as Code
    "InfrastructureManager",
    "InfrastructureProvider",
    "InfrastructureStack",
    "InfrastructureState",
    "KubernetesProvider",
    "MicroserviceOperator",
    "OperatorConfig",
    # Kubernetes operators
    "OperatorManager",
    "OperatorType",
    "PipelineConfig",
    "PipelineExecution",
    "PipelineGenerator",
    "PipelineProvider",
    "PipelineStage",
    "PipelineStatus",
    "PulumiGenerator",
    "ReconciliationAction",
    "ReconciliationEvent",
    "ResourceConfig",
    "ResourceRequirements",
    "ResourceType",
    "TerraformGenerator",
    "create_deployment_config",
    "create_deployment_pipeline",
    "create_helm_values_from_config",
    "create_kubernetes_target",
    "create_microservice_infrastructure",
    "create_operator_config",
    "deploy_infrastructure",
    "deploy_microservice_with_operator",
    "deploy_with_cicd",
    "deploy_with_helm",
    "deployment_context",
]

# Version information
__version__ = "1.0.0"
__author__ = "Marty Framework Team"
__description__ = "Comprehensive deployment automation for microservices"
