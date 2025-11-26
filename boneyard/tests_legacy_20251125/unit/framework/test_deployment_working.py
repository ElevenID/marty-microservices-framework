"""
Comprehensive Deployment Framework Tests - Working with Real Components

Tests all major deployment patterns using real implementations:
- Deployment Configuration and Management
- Deployment Targets and Providers
- Deployment Lifecycle and Status Management
- Resource Requirements and Health Checks
- Infrastructure Provider Abstractions
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from marty_msf.framework.deployment import (  # Core Components; Utility Functions
    Deployment,
    DeploymentConfig,
    DeploymentManager,
    DeploymentStatus,
    DeploymentStrategy,
    DeploymentTarget,
    EnvironmentType,
    HealthCheck,
    InfrastructureProvider,
    ResourceRequirements,
    create_deployment_config,
    create_kubernetes_target,
)


class TestDeploymentConfiguration:
    """Test deployment configuration and creation."""

    def test_deployment_target_creation(self):
        """Test deployment target configuration."""
        target = DeploymentTarget(
            name="production-cluster",
            environment=EnvironmentType.PRODUCTION,
            provider=InfrastructureProvider.KUBERNETES,
            region="us-west-2",
            cluster="main-cluster",
            namespace="production",
        )

        assert target.name == "production-cluster"
        assert target.environment == EnvironmentType.PRODUCTION
        assert target.provider == InfrastructureProvider.KUBERNETES
        assert target.region == "us-west-2"
        assert target.cluster == "main-cluster"
        assert target.namespace == "production"

    def test_resource_requirements_creation(self):
        """Test resource requirements configuration."""
        resources = ResourceRequirements(
            cpu_request="200m",
            cpu_limit="1000m",
            memory_request="256Mi",
            memory_limit="1Gi",
            replicas=3,
            min_replicas=2,
            max_replicas=10,
        )

        assert resources.cpu_request == "200m"
        assert resources.cpu_limit == "1000m"
        assert resources.memory_request == "256Mi"
        assert resources.memory_limit == "1Gi"
        assert resources.replicas == 3
        assert resources.min_replicas == 2
        assert resources.max_replicas == 10

    def test_health_check_configuration(self):
        """Test health check configuration."""
        health_check = HealthCheck(
            path="/api/health",
            port=9000,
            initial_delay=60,
            period=15,
            timeout=10,
            failure_threshold=5,
            success_threshold=2,
        )

        assert health_check.path == "/api/health"
        assert health_check.port == 9000
        assert health_check.initial_delay == 60
        assert health_check.period == 15
        assert health_check.timeout == 10
        assert health_check.failure_threshold == 5
        assert health_check.success_threshold == 2

    def test_deployment_config_creation(self):
        """Test comprehensive deployment configuration."""
        target = DeploymentTarget(
            name="staging",
            environment=EnvironmentType.STAGING,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = DeploymentConfig(
            service_name="user-service",
            version="1.2.3",
            image="user-service:1.2.3",
            target=target,
            strategy=DeploymentStrategy.BLUE_GREEN,
            environment_variables={"DB_HOST": "localhost", "LOG_LEVEL": "INFO"},
            labels={"app": "user-service", "version": "1.2.3"},
        )

        assert config.service_name == "user-service"
        assert config.version == "1.2.3"
        assert config.image == "user-service:1.2.3"
        assert config.target == target
        assert config.strategy == DeploymentStrategy.BLUE_GREEN
        assert config.environment_variables["DB_HOST"] == "localhost"
        assert config.labels["app"] == "user-service"


class TestDeploymentLifecycle:
    """Test deployment lifecycle management."""

    def test_deployment_creation(self):
        """Test deployment instance creation."""
        target = DeploymentTarget(
            name="test",
            environment=EnvironmentType.TESTING,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = DeploymentConfig(
            service_name="test-service", version="1.0.0", image="test-service:1.0.0", target=target
        )

        deployment = Deployment(id="deployment-123", config=config)

        assert deployment.id == "deployment-123"
        assert deployment.config == config
        assert deployment.status == DeploymentStatus.PENDING
        assert isinstance(deployment.created_at, datetime)
        assert isinstance(deployment.updated_at, datetime)
        assert deployment.deployed_at is None
        assert len(deployment.events) == 0

    def test_deployment_event_handling(self):
        """Test deployment event management."""
        target = DeploymentTarget(
            name="test",
            environment=EnvironmentType.TESTING,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = DeploymentConfig(
            service_name="test-service", version="1.0.0", image="test-service:1.0.0", target=target
        )

        deployment = Deployment(id="deployment-123", config=config)

        # Add events
        deployment.add_event("STARTED", "Deployment started", level="info")
        deployment.add_event("PROGRESS", "Pulling container image", level="info")
        deployment.add_event("WARNING", "Resource limit exceeded", level="warning")

        assert len(deployment.events) == 3
        assert deployment.events[0].event_type == "STARTED"
        assert deployment.events[0].message == "Deployment started"
        assert deployment.events[0].level == "info"
        assert deployment.events[1].event_type == "PROGRESS"
        assert deployment.events[2].level == "warning"

    def test_deployment_status_transitions(self):
        """Test deployment status management."""
        target = DeploymentTarget(
            name="test",
            environment=EnvironmentType.TESTING,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = DeploymentConfig(
            service_name="test-service", version="1.0.0", image="test-service:1.0.0", target=target
        )

        deployment = Deployment(id="deployment-123", config=config)

        # Test status transitions
        assert deployment.status == DeploymentStatus.PENDING

        deployment.status = DeploymentStatus.PREPARING
        assert deployment.status == DeploymentStatus.PREPARING

        deployment.status = DeploymentStatus.DEPLOYING
        assert deployment.status == DeploymentStatus.DEPLOYING

        deployment.status = DeploymentStatus.DEPLOYED
        deployment.deployed_at = datetime.utcnow()
        assert deployment.status == DeploymentStatus.DEPLOYED
        assert deployment.deployed_at is not None


class TestDeploymentStrategies:
    """Test different deployment strategies."""

    def test_rolling_update_strategy(self):
        """Test rolling update deployment strategy."""
        target = DeploymentTarget(
            name="production",
            environment=EnvironmentType.PRODUCTION,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = DeploymentConfig(
            service_name="web-service",
            version="2.0.0",
            image="web-service:2.0.0",
            target=target,
            strategy=DeploymentStrategy.ROLLING_UPDATE,
        )

        deployment = Deployment(id="rolling-deploy-1", config=config)

        assert deployment.config.strategy == DeploymentStrategy.ROLLING_UPDATE
        deployment.add_event("ROLLING_UPDATE_STARTED", "Starting rolling update")
        assert "ROLLING_UPDATE_STARTED" in [e.event_type for e in deployment.events]

    def test_blue_green_strategy(self):
        """Test blue-green deployment strategy."""
        target = DeploymentTarget(
            name="production",
            environment=EnvironmentType.PRODUCTION,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = DeploymentConfig(
            service_name="api-service",
            version="3.0.0",
            image="api-service:3.0.0",
            target=target,
            strategy=DeploymentStrategy.BLUE_GREEN,
        )

        deployment = Deployment(id="blue-green-deploy-1", config=config)

        assert deployment.config.strategy == DeploymentStrategy.BLUE_GREEN
        deployment.add_event("BLUE_GREEN_STARTED", "Starting blue-green deployment")
        deployment.add_event("GREEN_ENVIRONMENT_READY", "Green environment is ready")

        events = [e.event_type for e in deployment.events]
        assert "BLUE_GREEN_STARTED" in events
        assert "GREEN_ENVIRONMENT_READY" in events

    def test_canary_strategy(self):
        """Test canary deployment strategy."""
        target = DeploymentTarget(
            name="production",
            environment=EnvironmentType.PRODUCTION,
            provider=InfrastructureProvider.KUBERNETES,
        )

        resources = ResourceRequirements(replicas=10, min_replicas=2, max_replicas=20)

        config = DeploymentConfig(
            service_name="payment-service",
            version="1.5.0",
            image="payment-service:1.5.0",
            target=target,
            strategy=DeploymentStrategy.CANARY,
            resources=resources,
        )

        deployment = Deployment(id="canary-deploy-1", config=config)

        assert deployment.config.strategy == DeploymentStrategy.CANARY
        assert deployment.config.resources.replicas == 10
        deployment.add_event("CANARY_STARTED", "Starting canary deployment with 10% traffic")
        deployment.add_event("CANARY_PROGRESS", "Increasing traffic to 50%")

        events = [e.event_type for e in deployment.events]
        assert "CANARY_STARTED" in events
        assert "CANARY_PROGRESS" in events


class TestInfrastructureProviders:
    """Test infrastructure provider configurations."""

    def test_kubernetes_provider_target(self):
        """Test Kubernetes provider configuration."""
        target = DeploymentTarget(
            name="k8s-cluster",
            environment=EnvironmentType.PRODUCTION,
            provider=InfrastructureProvider.KUBERNETES,
            region="us-east-1",
            cluster="production-cluster",
            namespace="microservices",
        )

        assert target.provider == InfrastructureProvider.KUBERNETES
        assert target.cluster == "production-cluster"
        assert target.namespace == "microservices"

    def test_aws_eks_provider_target(self):
        """Test AWS EKS provider configuration."""
        target = DeploymentTarget(
            name="eks-cluster",
            environment=EnvironmentType.PRODUCTION,
            provider=InfrastructureProvider.AWS_EKS,
            region="us-west-2",
            cluster="production-eks",
            metadata={
                "account_id": "123456789012",
                "role_arn": "arn:aws:iam::123456789012:role/EKSRole",
            },
        )

        assert target.provider == InfrastructureProvider.AWS_EKS
        assert target.region == "us-west-2"
        assert target.metadata["account_id"] == "123456789012"

    def test_azure_aks_provider_target(self):
        """Test Azure AKS provider configuration."""
        target = DeploymentTarget(
            name="aks-cluster",
            environment=EnvironmentType.PRODUCTION,
            provider=InfrastructureProvider.AZURE_AKS,
            region="eastus",
            cluster="production-aks",
            metadata={"subscription_id": "sub-123", "resource_group": "production-rg"},
        )

        assert target.provider == InfrastructureProvider.AZURE_AKS
        assert target.region == "eastus"
        assert target.metadata["subscription_id"] == "sub-123"

    def test_gcp_gke_provider_target(self):
        """Test GCP GKE provider configuration."""
        target = DeploymentTarget(
            name="gke-cluster",
            environment=EnvironmentType.PRODUCTION,
            provider=InfrastructureProvider.GCP_GKE,
            region="us-central1",
            cluster="production-gke",
            metadata={"project_id": "my-project", "zone": "us-central1-a"},
        )

        assert target.provider == InfrastructureProvider.GCP_GKE
        assert target.region == "us-central1"
        assert target.metadata["project_id"] == "my-project"


class TestDeploymentUtilities:
    """Test deployment utility functions."""

    def test_create_kubernetes_target_utility(self):
        """Test create_kubernetes_target utility function."""
        target = create_kubernetes_target(
            name="test-cluster",
            environment=EnvironmentType.TESTING,
            cluster="test-k8s",
            namespace="testing",
        )

        assert target.name == "test-cluster"
        assert target.environment == EnvironmentType.TESTING
        assert target.provider == InfrastructureProvider.KUBERNETES
        assert target.cluster == "test-k8s"
        assert target.namespace == "testing"

    def test_create_deployment_config_utility(self):
        """Test create_deployment_config utility function."""
        target = DeploymentTarget(
            name="staging",
            environment=EnvironmentType.STAGING,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = create_deployment_config(
            service_name="notification-service",
            version="2.1.0",
            image="notification-service:2.1.0",
            target=target,
            strategy=DeploymentStrategy.ROLLING_UPDATE,
        )

        assert config.service_name == "notification-service"
        assert config.version == "2.1.0"
        assert config.image == "notification-service:2.1.0"
        assert config.target == target
        assert config.strategy == DeploymentStrategy.ROLLING_UPDATE


class TestDeploymentManager:
    """Test deployment manager functionality."""

    def test_deployment_manager_creation(self):
        """Test deployment manager creation."""
        manager = DeploymentManager()

        assert manager is not None
        assert hasattr(manager, "deployments")

    @pytest.mark.asyncio
    async def test_deployment_registration(self):
        """Test deployment registration in manager."""
        manager = DeploymentManager()

        target = DeploymentTarget(
            name="test",
            environment=EnvironmentType.TESTING,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = DeploymentConfig(
            service_name="test-service", version="1.0.0", image="test-service:1.0.0", target=target
        )

        # Create mock provider
        mock_provider = AsyncMock()
        mock_provider.provider_type = InfrastructureProvider.KUBERNETES
        mock_provider.deploy.return_value = True
        manager.register_provider(mock_provider)

        # Deploy (which registers the deployment)
        deployment = await manager.deploy(config)

        assert deployment.id in manager.deployments
        assert manager.deployments[deployment.id] == deployment
        assert deployment.config.service_name == "test-service"

    @pytest.mark.asyncio
    async def test_deployment_status_tracking(self):
        """Test deployment status tracking."""
        manager = DeploymentManager()

        target = DeploymentTarget(
            name="test",
            environment=EnvironmentType.TESTING,
            provider=InfrastructureProvider.KUBERNETES,
        )

        config = DeploymentConfig(
            service_name="status-test-service",
            version="1.0.0",
            image="status-test-service:1.0.0",
            target=target,
        )

        # Create mock provider
        mock_provider = AsyncMock()
        mock_provider.provider_type = InfrastructureProvider.KUBERNETES
        mock_provider.deploy.return_value = True
        manager.register_provider(mock_provider)

        # Deploy
        deployment = await manager.deploy(config)

        # Track status changes
        assert deployment.status == DeploymentStatus.PENDING

        deployment.status = DeploymentStatus.DEPLOYING
        deployment.add_event("STATUS_CHANGE", "Changed to deploying")

        assert manager.deployments[deployment.id].status == DeploymentStatus.DEPLOYING
        assert len(deployment.events) > 1  # Should have deployment_initiated + our custom event


class TestDeploymentIntegration:
    """Test integrated deployment scenarios."""

    @pytest.mark.asyncio
    async def test_complete_deployment_workflow(self):
        """Test complete deployment workflow simulation."""
        manager = DeploymentManager()

        # Create target
        target = create_kubernetes_target(
            name="integration-cluster",
            environment=EnvironmentType.STAGING,
            cluster="staging-k8s",
            namespace="integration",
        )

        # Create configuration
        resources = ResourceRequirements(
            cpu_request="500m",
            cpu_limit="2000m",
            memory_request="1Gi",
            memory_limit="4Gi",
            replicas=3,
        )

        health_check = HealthCheck(path="/api/health", port=8080, initial_delay=30, period=10)

        DeploymentConfig(
            service_name="integration-service",
            version="3.2.1",
            image="integration-service:3.2.1",
            target=target,
            strategy=DeploymentStrategy.ROLLING_UPDATE,
            resources=resources,
            health_check=health_check,
            environment_variables={"ENV": "staging", "LOG_LEVEL": "DEBUG"},
            labels={"app": "integration-service", "tier": "backend"},
        )

        # Create deployment
        deployment_config = DeploymentConfig(
            service_name="integration-service",
            version="3.2.1",
            image="integration-service:3.2.1",
            target=target,
            strategy=DeploymentStrategy.ROLLING_UPDATE,
            resources=resources,
            health_check=health_check,
            environment_variables={"ENV": "staging", "LOG_LEVEL": "DEBUG"},
            labels={"app": "integration-service", "tier": "backend"},
        )

        # Create mock provider and register it
        mock_provider = AsyncMock()
        mock_provider.provider_type = InfrastructureProvider.KUBERNETES
        mock_provider.deploy.return_value = True
        manager.register_provider(mock_provider)

        # Deploy using manager
        deployment = await manager.deploy(deployment_config)

        # Simulate deployment phases
        deployment.status = DeploymentStatus.PREPARING
        deployment.add_event("PREPARE_START", "Starting deployment preparation")

        deployment.status = DeploymentStatus.DEPLOYING
        deployment.add_event("DEPLOY_START", "Starting service deployment")
        deployment.add_event("IMAGE_PULL", "Pulling container image")
        deployment.add_event("REPLICAS_SCALING", "Scaling to 3 replicas")

        deployment.status = DeploymentStatus.DEPLOYED
        deployment.deployed_at = datetime.utcnow()
        deployment.add_event("DEPLOY_SUCCESS", "Deployment completed successfully")

        # Verify final state
        assert deployment.status == DeploymentStatus.DEPLOYED
        assert deployment.deployed_at is not None
        assert len(deployment.events) == 6  # deployment_initiated + 5 workflow events
        assert deployment.config.resources.replicas == 3

        # Verify manager state
        assert deployment.id in manager.deployments
        assert manager.deployments[deployment.id].status == DeploymentStatus.DEPLOYED

    @pytest.mark.asyncio
    async def test_multi_environment_deployment(self):
        """Test deployment across multiple environments."""
        manager = DeploymentManager()

        environments = [
            (EnvironmentType.DEVELOPMENT, "dev-cluster"),
            (EnvironmentType.TESTING, "test-cluster"),
            (EnvironmentType.STAGING, "staging-cluster"),
        ]

        deployments = []

        for env_type, cluster_name in environments:
            target = DeploymentTarget(
                name=cluster_name,
                environment=env_type,
                provider=InfrastructureProvider.KUBERNETES,
                cluster=cluster_name,
                namespace=env_type.value,
            )

            config = DeploymentConfig(
                service_name="multi-env-service",
                version="1.0.0",
                image="multi-env-service:1.0.0",
                target=target,
                environment_variables={"ENV": env_type.value},
            )

            # Deploy the configuration
            deployment = await manager.deploy(config)
            deployments.append(deployment)

        # Verify all deployments
        assert len(deployments) == 3

        # Verify environment-specific configurations
        for i, (env_type, cluster_name) in enumerate(environments):
            deployment = deployments[i]
            assert deployment.config.target.environment == env_type
            assert deployment.config.environment_variables["ENV"] == env_type.value
            assert deployment.config.target.cluster == cluster_name
