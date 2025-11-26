"""
Infrastructure as Code (IaC) integration for Marty Microservices Framework.

This module provides comprehensive Infrastructure as Code capabilities including
Terraform and Pulumi integration, cloud resource provisioning, environment
management, and infrastructure automation for microservices architectures.
"""

import asyncio
import builtins
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from .core import DeploymentConfig, EnvironmentType

logger = logging.getLogger(__name__)


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


@dataclass
class IaCConfig:
    """Infrastructure as Code configuration."""

    provider: IaCProvider
    cloud_provider: CloudProvider
    project_name: str
    environment: EnvironmentType
    region: str = "us-east-1"
    variables: builtins.dict[str, Any] = field(default_factory=dict)
    backend_config: builtins.dict[str, Any] = field(default_factory=dict)
    outputs: builtins.list[str] = field(default_factory=list)
    dependencies: builtins.list[str] = field(default_factory=list)


@dataclass
class ResourceConfig:
    """Infrastructure resource configuration."""

    name: str
    type: ResourceType
    provider: CloudProvider
    properties: builtins.dict[str, Any] = field(default_factory=dict)
    dependencies: builtins.list[str] = field(default_factory=list)
    tags: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class InfrastructureStack:
    """Infrastructure stack definition."""

    name: str
    config: IaCConfig
    resources: builtins.list[ResourceConfig] = field(default_factory=list)
    modules: builtins.list[str] = field(default_factory=list)
    data_sources: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)


@dataclass
class InfrastructureState:
    """Infrastructure state information."""

    stack_name: str
    status: str
    resources: builtins.dict[str, Any] = field(default_factory=dict)
    outputs: builtins.dict[str, Any] = field(default_factory=dict)
    last_updated: datetime | None = None
    version: str | None = None


class TerraformGenerator:
    """Generates Terraform configurations."""

    def generate_provider_config(
        self, cloud_provider: CloudProvider, region: str
    ) -> builtins.dict[str, Any]:
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

    def generate_backend_config(
        self, backend_config: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
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

        if cloud_provider == CloudProvider.AWS:
            resources.extend(self._generate_aws_microservice_resources(deployment_config))
        elif cloud_provider == CloudProvider.AZURE:
            resources.extend(self._generate_azure_microservice_resources(deployment_config))
        elif cloud_provider == CloudProvider.GCP:
            resources.extend(self._generate_gcp_microservice_resources(deployment_config))
        elif cloud_provider == CloudProvider.KUBERNETES:
            resources.extend(self._generate_k8s_microservice_resources(deployment_config))

        return InfrastructureStack(name=stack_name, config=config, resources=resources)

    def _generate_aws_microservice_resources(
        self, config: DeploymentConfig
    ) -> builtins.list[ResourceConfig]:
        """Generate AWS resources for microservice."""
        service_name = config.service_name
        environment = config.target.environment.value

        resources = [
            # ECS Cluster
            ResourceConfig(
                name=f"{service_name}-cluster",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.AWS,
                properties={
                    "name": f"{service_name}-{environment}",
                    "capacity_providers": ["FARGATE", "FARGATE_SPOT"],
                    "default_capacity_provider_strategy": [
                        {"capacity_provider": "FARGATE", "weight": 1}
                    ],
                },
            ),
            # ECS Task Definition
            ResourceConfig(
                name=f"{service_name}-task",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.AWS,
                properties={
                    "family": f"{service_name}-{environment}",
                    "network_mode": "awsvpc",
                    "requires_compatibilities": ["FARGATE"],
                    "cpu": config.resources.cpu_request,
                    "memory": config.resources.memory_request,
                    "execution_role_arn": f"${{aws_iam_role.{service_name}_execution_role.arn}}",
                    "task_role_arn": f"${{aws_iam_role.{service_name}_task_role.arn}}",
                    "container_definitions": json.dumps(
                        [
                            {
                                "name": service_name,
                                "image": config.image,
                                "portMappings": [
                                    {
                                        "containerPort": config.health_check.port,
                                        "protocol": "tcp",
                                    }
                                ],
                                "environment": [
                                    {"name": k, "value": v}
                                    for k, v in config.environment_variables.items()
                                ],
                                "logConfiguration": {
                                    "logDriver": "awslogs",
                                    "options": {
                                        "awslogs-group": f"/ecs/{service_name}-{environment}",
                                        "awslogs-region": "${var.aws_region}",
                                        "awslogs-stream-prefix": "ecs",
                                    },
                                },
                                "healthCheck": {
                                    "command": [
                                        "CMD-SHELL",
                                        f"curl -f http://localhost:{config.health_check.port}{config.health_check.path} || exit 1",
                                    ],
                                    "interval": config.health_check.period,
                                    "timeout": 5,
                                    "retries": 3,
                                    "startPeriod": config.health_check.initial_delay,
                                },
                            }
                        ]
                    ),
                },
            ),
            # ECS Service
            ResourceConfig(
                name=f"{service_name}-service",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.AWS,
                properties={
                    "name": f"{service_name}-{environment}",
                    "cluster": f"${{aws_ecs_cluster.{service_name}_cluster.id}}",
                    "task_definition": f"${{aws_ecs_task_definition.{service_name}_task.arn}}",
                    "desired_count": config.resources.replicas,
                    "launch_type": "FARGATE",
                    "network_configuration": {
                        "subnets": "${var.private_subnet_ids}",
                        "security_groups": [f"${{aws_security_group.{service_name}_sg.id}}"],
                        "assign_public_ip": False,
                    },
                    "load_balancer": [
                        {
                            "target_group_arn": f"${{aws_lb_target_group.{service_name}_tg.arn}}",
                            "container_name": service_name,
                            "container_port": config.health_check.port,
                        }
                    ],
                },
            ),
            # Application Load Balancer
            ResourceConfig(
                name=f"{service_name}-alb",
                type=ResourceType.LOAD_BALANCER,
                provider=CloudProvider.AWS,
                properties={
                    "name": f"{service_name}-{environment}-alb",
                    "load_balancer_type": "application",
                    "scheme": "internal",
                    "subnets": "${var.private_subnet_ids}",
                    "security_groups": [f"${{aws_security_group.{service_name}_alb_sg.id}}"],
                },
            ),
            # Target Group
            ResourceConfig(
                name=f"{service_name}-target-group",
                type=ResourceType.LOAD_BALANCER,
                provider=CloudProvider.AWS,
                properties={
                    "name": f"{service_name}-{environment}-tg",
                    "port": config.health_check.port,
                    "protocol": "HTTP",
                    "vpc_id": "${var.vpc_id}",
                    "target_type": "ip",
                    "health_check": {
                        "enabled": True,
                        "healthy_threshold": 2,
                        "interval": config.health_check.period,
                        "matcher": "200",
                        "path": config.health_check.path,
                        "port": "traffic-port",
                        "protocol": "HTTP",
                        "timeout": 5,
                        "unhealthy_threshold": 2,
                    },
                },
            ),
            # Security Group for Service
            ResourceConfig(
                name=f"{service_name}-security-group",
                type=ResourceType.SECURITY_GROUP,
                provider=CloudProvider.AWS,
                properties={
                    "name": f"{service_name}-{environment}-sg",
                    "description": f"Security group for {service_name} service",
                    "vpc_id": "${var.vpc_id}",
                    "ingress": [
                        {
                            "from_port": config.health_check.port,
                            "to_port": config.health_check.port,
                            "protocol": "tcp",
                            "security_groups": [
                                f"${{aws_security_group.{service_name}_alb_sg.id}}"
                            ],
                        }
                    ],
                    "egress": [
                        {
                            "from_port": 0,
                            "to_port": 0,
                            "protocol": "-1",
                            "cidr_blocks": ["0.0.0.0/0"],
                        }
                    ],
                },
            ),
            # IAM Role for Task Execution
            ResourceConfig(
                name=f"{service_name}-execution-role",
                type=ResourceType.IAM,
                provider=CloudProvider.AWS,
                properties={
                    "name": f"{service_name}-{environment}-execution-role",
                    "assume_role_policy": json.dumps(
                        {
                            "Version": "2012-10-17",
                            "Statement": [
                                {
                                    "Action": "sts:AssumeRole",
                                    "Effect": "Allow",
                                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                                }
                            ],
                        }
                    ),
                    "managed_policy_arns": [
                        "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
                    ],
                },
            ),
        ]

        return resources

    def _generate_azure_microservice_resources(
        self, config: DeploymentConfig
    ) -> builtins.list[ResourceConfig]:
        """Generate Azure resources for microservice."""
        service_name = config.service_name
        environment = config.target.environment.value

        return [
            # Resource Group
            ResourceConfig(
                name=f"{service_name}-rg",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.AZURE,
                properties={
                    "name": f"{service_name}-{environment}-rg",
                    "location": "${var.location}",
                },
            ),
            # Container App Environment
            ResourceConfig(
                name=f"{service_name}-env",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.AZURE,
                properties={
                    "name": f"{service_name}-{environment}-env",
                    "location": f"${{azurerm_resource_group.{service_name}_rg.location}}",
                    "resource_group_name": f"${{azurerm_resource_group.{service_name}_rg.name}}",
                },
            ),
            # Container App
            ResourceConfig(
                name=f"{service_name}-app",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.AZURE,
                properties={
                    "name": f"{service_name}-{environment}",
                    "container_app_environment_id": f"${{azurerm_container_app_environment.{service_name}_env.id}}",
                    "resource_group_name": f"${{azurerm_resource_group.{service_name}_rg.name}}",
                    "revision_mode": "Single",
                    "template": {
                        "container": [
                            {
                                "name": service_name,
                                "image": config.image,
                                "cpu": float(config.resources.cpu_request.rstrip("m")) / 1000,
                                "memory": f"{config.resources.memory_request}i",
                                "env": [
                                    {"name": k, "value": v}
                                    for k, v in config.environment_variables.items()
                                ],
                            }
                        ],
                        "min_replicas": config.resources.min_replicas,
                        "max_replicas": config.resources.max_replicas,
                    },
                    "ingress": {
                        "external_enabled": True,
                        "target_port": config.health_check.port,
                        "traffic_weight": [{"percentage": 100, "latest_revision": True}],
                    },
                },
            ),
        ]

    def _generate_gcp_microservice_resources(
        self, config: DeploymentConfig
    ) -> builtins.list[ResourceConfig]:
        """Generate GCP resources for microservice."""
        service_name = config.service_name
        environment = config.target.environment.value

        return [
            # Cloud Run Service
            ResourceConfig(
                name=f"{service_name}-service",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.GCP,
                properties={
                    "name": f"{service_name}-{environment}",
                    "location": "${var.region}",
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "image": config.image,
                                    "ports": [{"container_port": config.health_check.port}],
                                    "env": [
                                        {"name": k, "value": v}
                                        for k, v in config.environment_variables.items()
                                    ],
                                    "resources": {
                                        "limits": {
                                            "cpu": config.resources.cpu_limit,
                                            "memory": config.resources.memory_limit,
                                        }
                                    },
                                }
                            ],
                            "container_concurrency": 100,
                            "timeout_seconds": 300,
                        },
                        "metadata": {
                            "annotations": {
                                "autoscaling.knative.dev/minScale": str(
                                    config.resources.min_replicas
                                ),
                                "autoscaling.knative.dev/maxScale": str(
                                    config.resources.max_replicas
                                ),
                            }
                        },
                    },
                    "traffic": [{"percent": 100, "latest_revision": True}],
                },
            )
        ]

    def _generate_k8s_microservice_resources(
        self, config: DeploymentConfig
    ) -> builtins.list[ResourceConfig]:
        """Generate Kubernetes resources for microservice."""
        service_name = config.service_name
        environment = config.target.environment.value

        return [
            # Namespace
            ResourceConfig(
                name=f"{service_name}-namespace",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.KUBERNETES,
                properties={"metadata": {"name": f"{service_name}-{environment}"}},
            ),
            # Deployment
            ResourceConfig(
                name=f"{service_name}-deployment",
                type=ResourceType.COMPUTE,
                provider=CloudProvider.KUBERNETES,
                properties={
                    "metadata": {
                        "name": service_name,
                        "namespace": f"{service_name}-{environment}",
                    },
                    "spec": {
                        "replicas": config.resources.replicas,
                        "selector": {"match_labels": {"app": service_name}},
                        "template": {
                            "metadata": {
                                "labels": {
                                    "app": service_name,
                                    "version": config.version,
                                }
                            },
                            "spec": {
                                "containers": [
                                    {
                                        "name": service_name,
                                        "image": config.image,
                                        "ports": [{"container_port": config.health_check.port}],
                                        "env": [
                                            {"name": k, "value": v}
                                            for k, v in config.environment_variables.items()
                                        ],
                                        "resources": {
                                            "requests": {
                                                "cpu": config.resources.cpu_request,
                                                "memory": config.resources.memory_request,
                                            },
                                            "limits": {
                                                "cpu": config.resources.cpu_limit,
                                                "memory": config.resources.memory_limit,
                                            },
                                        },
                                        "liveness_probe": {
                                            "http_get": {
                                                "path": config.health_check.path,
                                                "port": config.health_check.port,
                                            },
                                            "initial_delay_seconds": config.health_check.initial_delay,
                                            "period_seconds": config.health_check.period,
                                        },
                                        "readiness_probe": {
                                            "http_get": {
                                                "path": config.health_check.path,
                                                "port": config.health_check.port,
                                            },
                                            "initial_delay_seconds": 5,
                                            "period_seconds": config.health_check.period,
                                        },
                                    }
                                ]
                            },
                        },
                    },
                },
            ),
            # Service
            ResourceConfig(
                name=f"{service_name}-service",
                type=ResourceType.NETWORK,
                provider=CloudProvider.KUBERNETES,
                properties={
                    "metadata": {
                        "name": service_name,
                        "namespace": f"{service_name}-{environment}",
                    },
                    "spec": {
                        "selector": {"app": service_name},
                        "ports": [
                            {
                                "port": 80,
                                "target_port": config.health_check.port,
                                "protocol": "TCP",
                            }
                        ],
                        "type": "ClusterIP",
                    },
                },
            ),
        ]


class PulumiGenerator:
    """Generates Pulumi configurations."""

    def generate_microservice_infrastructure(
        self,
        deployment_config: DeploymentConfig,
        cloud_provider: CloudProvider,
        language: str = "python",
    ) -> str:
        """Generate Pulumi infrastructure code."""
        if language == "python":
            return self._generate_python_pulumi(deployment_config, cloud_provider)
        if language == "typescript":
            return self._generate_typescript_pulumi(deployment_config, cloud_provider)
        raise ValueError(f"Unsupported Pulumi language: {language}")

    def _generate_python_pulumi(
        self, config: DeploymentConfig, cloud_provider: CloudProvider
    ) -> str:
        """Generate Python Pulumi code."""
        service_name = config.service_name
        environment = config.target.environment.value

        if cloud_provider == CloudProvider.AWS:
            return f"""import pulumi
import pulumi_aws as aws

# ECS Cluster
cluster = aws.ecs.Cluster("{service_name}-cluster",
    name=f"{service_name}-{environment}",
    capacity_providers=["FARGATE", "FARGATE_SPOT"],
    default_capacity_provider_strategies=[
        aws.ecs.ClusterDefaultCapacityProviderStrategyArgs(
            capacity_provider="FARGATE",
            weight=1,
        )
    ]
)

# Task Definition
task_definition = aws.ecs.TaskDefinition("{service_name}-task",
    family=f"{service_name}-{environment}",
    network_mode="awsvpc",
    requires_compatibilities=["FARGATE"],
    cpu="{config.resources.cpu_request}",
    memory="{config.resources.memory_request}",
    container_definitions=pulumi.Output.all().apply(lambda args: [{{
        "name": "{service_name}",
        "image": "{config.image}",
        "portMappings": [{{
            "containerPort": {config.health_check.port},
            "protocol": "tcp"
        }}],
        "environment": {list(config.environment_variables.items())},
        "healthCheck": {{
            "command": ["CMD-SHELL", "curl -f http://localhost:{config.health_check.port}{config.health_check.path} || exit 1"],
            "interval": {config.health_check.period},
            "timeout": 5,
            "retries": 3,
            "startPeriod": {config.health_check.initial_delay}
        }}
    }}])
)

# ECS Service
service = aws.ecs.Service("{service_name}-service",
    name=f"{service_name}-{environment}",
    cluster=cluster.id,
    task_definition=task_definition.arn,
    desired_count={config.resources.replicas},
    launch_type="FARGATE",
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        subnets=pulumi.Config("aws").require_object("private_subnet_ids"),
        assign_public_ip=False
    )
)

# Export the service ARN
pulumi.export("service_arn", service.arn)
pulumi.export("cluster_arn", cluster.arn)
"""

        if cloud_provider == CloudProvider.GCP:
            return f"""import pulumi
import pulumi_gcp as gcp

# Cloud Run Service
service = gcp.cloudrun.Service("{service_name}-service",
    name=f"{service_name}-{environment}",
    location=pulumi.Config("gcp").get("region"),
    template=gcp.cloudrun.ServiceTemplateArgs(
        spec=gcp.cloudrun.ServiceTemplateSpecArgs(
            containers=[gcp.cloudrun.ServiceTemplateSpecContainerArgs(
                image="{config.image}",
                ports=[gcp.cloudrun.ServiceTemplateSpecContainerPortArgs(
                    container_port={config.health_check.port}
                )],
                envs=[gcp.cloudrun.ServiceTemplateSpecContainerEnvArgs(
                    name=name,
                    value=value
                ) for name, value in {dict(config.environment_variables)}.items()],
                resources=gcp.cloudrun.ServiceTemplateSpecContainerResourcesArgs(
                    limits={{
                        "cpu": "{config.resources.cpu_limit}",
                        "memory": "{config.resources.memory_limit}"
                    }}
                )
            )],
            container_concurrency=100,
            timeout_seconds=300
        ),
        metadata=gcp.cloudrun.ServiceTemplateMetadataArgs(
            annotations={{
                "autoscaling.knative.dev/minScale": "{config.resources.min_replicas}",
                "autoscaling.knative.dev/maxScale": "{config.resources.max_replicas}"
            }}
        )
    ),
    traffics=[gcp.cloudrun.ServiceTrafficArgs(
        percent=100,
        latest_revision=True
    )]
)

# Export the service URL
pulumi.export("service_url", service.statuses[0].url)
"""

        return ""


class InfrastructureManager:
    """Manages Infrastructure as Code operations."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir
        self.terraform_generator = TerraformGenerator()
        self.pulumi_generator = PulumiGenerator()

    async def create_infrastructure_stack(self, stack: InfrastructureStack) -> bool:
        """Create infrastructure stack."""
        try:
            stack_dir = self.working_dir / stack.name
            stack_dir.mkdir(parents=True, exist_ok=True)

            if stack.config.provider == IaCProvider.TERRAFORM:
                return await self._create_terraform_stack(stack, stack_dir)
            if stack.config.provider == IaCProvider.PULUMI:
                return await self._create_pulumi_stack(stack, stack_dir)
            raise ValueError(f"Unsupported IaC provider: {stack.config.provider}")

        except Exception as e:
            logger.error(f"Failed to create infrastructure stack: {e}")
            return False

    async def _create_terraform_stack(self, stack: InfrastructureStack, stack_dir: Path) -> bool:
        """Create Terraform stack."""
        # Generate provider configuration
        provider_config = self.terraform_generator.generate_provider_config(
            stack.config.cloud_provider, stack.config.region
        )

        # Generate backend configuration
        backend_config = self.terraform_generator.generate_backend_config(
            stack.config.backend_config
        )

        # Merge configurations
        main_config = {**provider_config, **backend_config}

        # Add variables
        if stack.config.variables:
            variables_config = {}
            for var_name, var_value in stack.config.variables.items():
                variables_config[f'variable "{var_name}"'] = {
                    "description": f"Variable {var_name}",
                    "type": type(var_value).__name__,
                    "default": var_value,
                }

            with open(stack_dir / "variables.tf", "w") as f:
                self._write_terraform_hcl(variables_config, f)

        # Generate resource configurations
        resources_config = {}
        for resource in stack.resources:
            resource_type = self._get_terraform_resource_type(resource)
            resource_key = f'resource "{resource_type}" "{resource.name}"'
            resources_config[resource_key] = resource.properties

        # Write main.tf
        with open(stack_dir / "main.tf", "w") as f:
            self._write_terraform_hcl(main_config, f)
            self._write_terraform_hcl(resources_config, f)

        # Generate outputs
        if stack.config.outputs:
            outputs_config = {}
            for output in stack.config.outputs:
                outputs_config[f'output "{output}"'] = {"value": f"${{{output}}}"}

            with open(stack_dir / "outputs.tf", "w") as f:
                self._write_terraform_hcl(outputs_config, f)

        logger.info(f"Created Terraform stack: {stack_dir}")
        return True

    def _get_terraform_resource_type(self, resource: ResourceConfig) -> str:
        """Get Terraform resource type."""
        provider_prefixes = {
            CloudProvider.AWS: "aws",
            CloudProvider.AZURE: "azurerm",
            CloudProvider.GCP: "google",
            CloudProvider.KUBERNETES: "kubernetes",
        }

        resource_types = {
            ResourceType.COMPUTE: {
                CloudProvider.AWS: "ecs_service",
                CloudProvider.AZURE: "container_app",
                CloudProvider.GCP: "cloud_run_service",
                CloudProvider.KUBERNETES: "deployment",
            },
            ResourceType.LOAD_BALANCER: {
                CloudProvider.AWS: "lb",
                CloudProvider.AZURE: "lb",
                CloudProvider.GCP: "compute_global_forwarding_rule",
            },
            ResourceType.SECURITY_GROUP: {
                CloudProvider.AWS: "security_group",
                CloudProvider.AZURE: "network_security_group",
                CloudProvider.GCP: "compute_firewall",
            },
        }

        prefix = provider_prefixes.get(resource.provider, "")
        resource_type = resource_types.get(resource.type, {}).get(resource.provider, "resource")

        return f"{prefix}_{resource_type}"

    def _write_terraform_hcl(self, config: builtins.dict[str, Any], file_handle) -> None:
        """Write Terraform HCL configuration."""
        # Simplified HCL writer - in production, use proper HCL library
        for key, value in config.items():
            file_handle.write(f"{key} {{\n")
            self._write_hcl_value(value, file_handle, indent=2)
            file_handle.write("}\n\n")

    def _write_hcl_value(self, value: Any, file_handle, indent: int = 0) -> None:
        """Write HCL value with proper indentation."""
        prefix = " " * indent

        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, dict):
                    file_handle.write(f"{prefix}{k} {{\n")
                    self._write_hcl_value(v, file_handle, indent + 2)
                    file_handle.write(f"{prefix}}}\n")
                elif isinstance(v, list):
                    file_handle.write(f"{prefix}{k} = [\n")
                    for item in v:
                        if isinstance(item, dict):
                            file_handle.write(f"{prefix}  {{\n")
                            self._write_hcl_value(item, file_handle, indent + 4)
                            file_handle.write(f"{prefix}  }},\n")
                        else:
                            file_handle.write(f"{prefix}  {json.dumps(item)},\n")
                    file_handle.write(f"{prefix}]\n")
                elif isinstance(v, str) and v.startswith("${"):
                    file_handle.write(f"{prefix}{k} = {v}\n")
                else:
                    file_handle.write(f"{prefix}{k} = {json.dumps(v)}\n")
        elif isinstance(value, list):
            for item in value:
                self._write_hcl_value(item, file_handle, indent)

    async def _create_pulumi_stack(self, stack: InfrastructureStack, stack_dir: Path) -> bool:
        """Create Pulumi stack."""
        # Generate Pulumi configuration
        pulumi_config = {
            "name": stack.name,
            "runtime": "python",
            "description": f"Infrastructure for {stack.name}",
        }

        with open(stack_dir / "Pulumi.yaml", "w") as f:
            yaml.dump(pulumi_config, f, default_flow_style=False)

        # Generate main.py if deployment config exists
        if hasattr(stack, "deployment_config") and stack.deployment_config:
            pulumi_code = self.pulumi_generator.generate_microservice_infrastructure(
                stack.deployment_config, stack.config.cloud_provider
            )

            with open(stack_dir / "__main__.py", "w") as f:
                f.write(pulumi_code)

        # Generate requirements.txt
        requirements = [
            "pulumi>=3.0.0,<4.0.0",
        ]

        if stack.config.cloud_provider == CloudProvider.AWS:
            requirements.append("pulumi-aws>=6.0.0,<7.0.0")
        elif stack.config.cloud_provider == CloudProvider.GCP:
            requirements.append("pulumi-gcp>=7.0.0,<8.0.0")
        elif stack.config.cloud_provider == CloudProvider.AZURE:
            requirements.append("pulumi-azure-native>=2.0.0,<3.0.0")

        with open(stack_dir / "requirements.txt", "w") as f:
            f.write("\n".join(requirements))

        logger.info(f"Created Pulumi stack: {stack_dir}")
        return True

    async def deploy_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> builtins.tuple[bool, str | None]:
        """Deploy infrastructure stack."""
        try:
            stack_dir = self.working_dir / stack_name

            if not stack_dir.exists():
                return False, f"Stack directory not found: {stack_dir}"

            # Check if it's a Terraform or Pulumi stack
            if (stack_dir / "main.tf").exists():
                return await self._deploy_terraform_stack(stack_dir, auto_approve)
            if (stack_dir / "Pulumi.yaml").exists():
                return await self._deploy_pulumi_stack(stack_dir)
            return False, "Unknown stack type"

        except Exception as e:
            return False, f"Deployment failed: {e!s}"

    async def _deploy_terraform_stack(
        self, stack_dir: Path, auto_approve: bool
    ) -> builtins.tuple[bool, str | None]:
        """Deploy Terraform stack."""
        try:
            # Initialize
            init_process = await asyncio.create_subprocess_exec(
                "terraform",
                "init",
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await init_process.communicate()

            if init_process.returncode != 0:
                return False, "Terraform init failed"

            # Plan
            plan_process = await asyncio.create_subprocess_exec(
                "terraform",
                "plan",
                "-out=tfplan",
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await plan_process.communicate()

            if plan_process.returncode != 0:
                return False, "Terraform plan failed"

            # Apply
            apply_cmd = ["terraform", "apply"]
            if auto_approve:
                apply_cmd.append("-auto-approve")
            else:
                apply_cmd.append("tfplan")

            apply_process = await asyncio.create_subprocess_exec(
                *apply_cmd,
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await apply_process.communicate()

            if apply_process.returncode == 0:
                return True, "Terraform deployment successful"
            return False, f"Terraform apply failed: {stderr.decode()}"

        except Exception as e:
            return False, f"Terraform deployment error: {e!s}"

    async def _deploy_pulumi_stack(self, stack_dir: Path) -> builtins.tuple[bool, str | None]:
        """Deploy Pulumi stack."""
        try:
            # Install dependencies
            pip_process = await asyncio.create_subprocess_exec(
                "pip",
                "install",
                "-r",
                "requirements.txt",
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await pip_process.communicate()

            # Deploy
            up_process = await asyncio.create_subprocess_exec(
                "pulumi",
                "up",
                "--yes",
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await up_process.communicate()

            if up_process.returncode == 0:
                return True, "Pulumi deployment successful"
            return False, f"Pulumi deployment failed: {stderr.decode()}"

        except Exception as e:
            return False, f"Pulumi deployment error: {e!s}"

    async def get_stack_state(self, stack_name: str) -> InfrastructureState | None:
        """Get infrastructure stack state."""
        try:
            stack_dir = self.working_dir / stack_name

            if (stack_dir / "terraform.tfstate").exists():
                return await self._get_terraform_state(stack_dir)
            if (stack_dir / "Pulumi.yaml").exists():
                return await self._get_pulumi_state(stack_dir)

            return None

        except Exception as e:
            logger.error(f"Failed to get stack state: {e}")
            return None

    async def _get_terraform_state(self, stack_dir: Path) -> InfrastructureState | None:
        """Get Terraform state."""
        try:
            show_process = await asyncio.create_subprocess_exec(
                "terraform",
                "show",
                "-json",
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await show_process.communicate()

            if show_process.returncode == 0:
                state_data = json.loads(stdout.decode())

                return InfrastructureState(
                    stack_name=stack_dir.name,
                    status="deployed",
                    resources={
                        r["address"]: r
                        for r in state_data.get("values", {})
                        .get("root_module", {})
                        .get("resources", [])
                    },
                    outputs=state_data.get("values", {}).get("outputs", {}),
                    version=state_data.get("terraform_version"),
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get Terraform state: {e}")
            return None

    async def _get_pulumi_state(self, stack_dir: Path) -> InfrastructureState | None:
        """Get Pulumi state."""
        try:
            stack_process = await asyncio.create_subprocess_exec(
                "pulumi",
                "stack",
                "output",
                "--json",
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await stack_process.communicate()

            if stack_process.returncode == 0:
                outputs = json.loads(stdout.decode()) if stdout else {}

                return InfrastructureState(
                    stack_name=stack_dir.name, status="deployed", outputs=outputs
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get Pulumi state: {e}")
            return None

    async def destroy_stack(
        self, stack_name: str, auto_approve: bool = False
    ) -> builtins.tuple[bool, str | None]:
        """Destroy infrastructure stack."""
        try:
            stack_dir = self.working_dir / stack_name

            if (stack_dir / "main.tf").exists():
                return await self._destroy_terraform_stack(stack_dir, auto_approve)
            if (stack_dir / "Pulumi.yaml").exists():
                return await self._destroy_pulumi_stack(stack_dir)
            return False, "Unknown stack type"

        except Exception as e:
            return False, f"Destroy failed: {e!s}"

    async def _destroy_terraform_stack(
        self, stack_dir: Path, auto_approve: bool
    ) -> builtins.tuple[bool, str | None]:
        """Destroy Terraform stack."""
        try:
            destroy_cmd = ["terraform", "destroy"]
            if auto_approve:
                destroy_cmd.append("-auto-approve")

            destroy_process = await asyncio.create_subprocess_exec(
                *destroy_cmd,
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await destroy_process.communicate()

            if destroy_process.returncode == 0:
                return True, "Terraform destroy successful"
            return False, f"Terraform destroy failed: {stderr.decode()}"

        except Exception as e:
            return False, f"Terraform destroy error: {e!s}"

    async def _destroy_pulumi_stack(self, stack_dir: Path) -> builtins.tuple[bool, str | None]:
        """Destroy Pulumi stack."""
        try:
            destroy_process = await asyncio.create_subprocess_exec(
                "pulumi",
                "destroy",
                "--yes",
                cwd=stack_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await destroy_process.communicate()

            if destroy_process.returncode == 0:
                return True, "Pulumi destroy successful"
            return False, f"Pulumi destroy failed: {stderr.decode()}"

        except Exception as e:
            return False, f"Pulumi destroy error: {e!s}"


# Utility functions
def create_microservice_infrastructure(
    deployment_config: DeploymentConfig,
    cloud_provider: CloudProvider = CloudProvider.AWS,
    iac_provider: IaCProvider = IaCProvider.TERRAFORM,
) -> InfrastructureStack:
    """Create infrastructure stack for microservice."""
    generator = TerraformGenerator()
    return generator.generate_microservice_infrastructure(deployment_config, cloud_provider)


async def deploy_infrastructure(
    manager: InfrastructureManager,
    stack: InfrastructureStack,
    auto_approve: bool = False,
) -> builtins.tuple[bool, str | None]:
    """Deploy infrastructure stack."""
    try:
        # Create stack
        created = await manager.create_infrastructure_stack(stack)
        if not created:
            return False, "Failed to create infrastructure stack"

        # Deploy stack
        success, message = await manager.deploy_stack(stack.name, auto_approve)

        if success:
            return True, f"Infrastructure deployed successfully: {message}"
        return False, f"Infrastructure deployment failed: {message}"

    except Exception as e:
        return False, f"Infrastructure deployment error: {e!s}"
