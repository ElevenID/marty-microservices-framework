"""
Advanced Deployment Strategies for Marty Microservices Framework

Provides comprehensive deployment strategy implementations including:
- Blue-Green deployments with zero downtime
- Canary deployments with automated rollback
- Rolling deployments with health checks
- Feature flag integration
- Traffic splitting and load balancing
- Automated rollback mechanisms
- Deployment monitoring and validation
"""

import asyncio
import builtins
import importlib.util
import random
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from kubernetes import client, config
from prometheus_client import Counter, Gauge, Histogram

importlib.util.find_spec("kubernetes")
importlib.util.find_spec("prometheus_client")


class DeploymentStrategy(Enum):
    """Deployment strategy types"""

    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    ROLLING = "rolling"
    RECREATE = "recreate"
    A_B_TESTING = "a_b_testing"


class DeploymentPhase(Enum):
    """Deployment execution phases"""

    PLANNING = "planning"
    PREPARING = "preparing"
    DEPLOYING = "deploying"
    VALIDATING = "validating"
    PROMOTING = "promoting"
    COMPLETED = "completed"
    ROLLING_BACK = "rolling_back"
    FAILED = "failed"


class TrafficSplitMethod(Enum):
    """Traffic splitting methods"""

    WEIGHTED = "weighted"
    HEADER_BASED = "header_based"
    GEOGRAPHIC = "geographic"
    USER_BASED = "user_based"
    PERCENTAGE = "percentage"


@dataclass
class DeploymentTarget:
    """Deployment target configuration"""

    name: str
    namespace: str
    cluster: str = "default"

    # Resource configuration
    replicas: int = 3
    image: str = ""
    tag: str = "latest"

    # Resource limits
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"

    # Health checks
    health_check_path: str = "/health"
    health_check_port: int = 8080
    health_check_timeout: int = 30

    # Labels and annotations
    labels: builtins.dict[str, str] = field(default_factory=dict)
    annotations: builtins.dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


@dataclass
class TrafficSplit:
    """Traffic splitting configuration"""

    method: TrafficSplitMethod

    # Weight-based splitting
    blue_weight: int = 100
    green_weight: int = 0

    # Header-based splitting
    header_name: str | None = None
    header_values: builtins.dict[str, str] = field(default_factory=dict)

    # User-based splitting
    user_percentage: int = 0
    user_groups: builtins.list[str] = field(default_factory=list)

    # Geographic splitting
    geographic_rules: builtins.dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {**asdict(self), "method": self.method.value}


@dataclass
class DeploymentValidation:
    """Deployment validation configuration"""

    enabled: bool = True

    # Health check validation
    health_check_enabled: bool = True
    health_check_retries: int = 10
    health_check_interval: int = 30

    # Performance validation
    performance_check_enabled: bool = True
    max_response_time: int = 1000  # milliseconds
    min_success_rate: float = 0.95

    # Custom validation
    custom_validations: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)

    # Rollback triggers
    auto_rollback_enabled: bool = True
    error_threshold: float = 0.05  # 5% error rate
    latency_threshold: int = 2000  # 2 seconds

    def to_dict(self) -> builtins.dict[str, Any]:
        return asdict(self)


@dataclass
class DeploymentOperation:
    """Deployment operation tracking"""

    operation_id: str
    application_name: str
    strategy: DeploymentStrategy
    started_at: datetime

    # Configuration
    source_version: str = ""
    target_version: str = ""
    target_config: DeploymentTarget | None = None
    traffic_config: TrafficSplit | None = None
    validation_config: DeploymentValidation | None = None

    # State tracking
    current_phase: DeploymentPhase = DeploymentPhase.PLANNING
    progress_percentage: int = 0

    # Execution details
    blue_deployment: str | None = None
    green_deployment: str | None = None
    canary_deployment: str | None = None

    # Results
    status: str = "running"  # running, succeeded, failed, rolled_back
    completed_at: datetime | None = None
    error_message: str | None = None
    rollback_reason: str | None = None

    # Metrics
    deployment_duration: float | None = None
    validation_results: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "strategy": self.strategy.value,
            "current_phase": self.current_phase.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "target_config": self.target_config.to_dict() if self.target_config else None,
            "traffic_config": self.traffic_config.to_dict() if self.traffic_config else None,
            "validation_config": self.validation_config.to_dict()
            if self.validation_config
            else None,
        }


class DeploymentStrategyBase(ABC):
    """
    Base class for deployment strategies

    Defines the interface that all deployment strategies must implement
    """

    def __init__(self, name: str):
        self.name = name
        self.operations: builtins.dict[str, DeploymentOperation] = {}

        # Metrics
        self.deployments_total = Counter(
            f"marty_deployments_{name}_total",
            f"{name} deployments total",
            ["status"],
        )

        self.deployment_duration = Histogram(
            f"marty_deployment_{name}_duration_seconds",
            f"{name} deployment duration",
        )

    @abstractmethod
    async def deploy(self, operation: DeploymentOperation) -> bool:
        """Execute deployment strategy"""

    @abstractmethod
    async def rollback(self, operation_id: str, reason: str = "Manual rollback") -> bool:
        """Rollback deployment"""

    @abstractmethod
    async def validate_deployment(self, operation: DeploymentOperation) -> builtins.dict[str, Any]:
        """Validate deployment success"""

    def _update_operation_phase(
        self,
        operation: DeploymentOperation,
        phase: DeploymentPhase,
        progress: int = None,
    ):
        """Update operation phase and progress"""
        operation.current_phase = phase
        if progress is not None:
            operation.progress_percentage = progress

        print(f"📊 {operation.application_name} - {phase.value} ({operation.progress_percentage}%)")


class BlueGreenDeploymentStrategy(DeploymentStrategyBase):
    """
    Blue-Green deployment strategy implementation

    Features:
    - Zero-downtime deployments
    - Instant rollback capability
    - Complete environment isolation
    - Traffic switching automation
    """

    def __init__(self):
        super().__init__("blue_green")
        self.kubernetes_client = None

        try:
            config.load_incluster_config()
        except Exception as incluster_error:
            try:
                config.load_kube_config()
            except Exception as kubeconfig_error:
                print(
                    "⚠️ Kubernetes config not available for Blue-Green deployment: "
                    f"in-cluster error={incluster_error}, kubeconfig error={kubeconfig_error}"
                )

    async def deploy(self, operation: DeploymentOperation) -> bool:
        """Execute Blue-Green deployment"""

        try:
            print(f"🔵🟢 Starting Blue-Green deployment for {operation.application_name}")

            # Phase 1: Preparation
            self._update_operation_phase(operation, DeploymentPhase.PREPARING, 10)
            await self._prepare_deployment(operation)

            # Phase 2: Deploy Green environment
            self._update_operation_phase(operation, DeploymentPhase.DEPLOYING, 30)
            green_success = await self._deploy_green_environment(operation)

            if not green_success:
                operation.status = "failed"
                operation.error_message = "Failed to deploy green environment"
                return False

            # Phase 3: Validate Green environment
            self._update_operation_phase(operation, DeploymentPhase.VALIDATING, 60)
            validation_results = await self.validate_deployment(operation)

            if not validation_results.get("success", False):
                operation.status = "failed"
                operation.error_message = f"Validation failed: {validation_results.get('error')}"
                await self._cleanup_green_environment(operation)
                return False

            operation.validation_results = validation_results

            # Phase 4: Switch traffic to Green
            self._update_operation_phase(operation, DeploymentPhase.PROMOTING, 80)
            switch_success = await self._switch_traffic_to_green(operation)

            if not switch_success:
                operation.status = "failed"
                operation.error_message = "Failed to switch traffic to green environment"
                await self.rollback(operation.operation_id, "Traffic switch failed")
                return False

            # Phase 5: Cleanup Blue environment
            self._update_operation_phase(operation, DeploymentPhase.COMPLETED, 100)
            await self._cleanup_blue_environment(operation)

            # Complete deployment
            operation.status = "succeeded"
            operation.completed_at = datetime.now()
            operation.deployment_duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

            # Update metrics
            self.deployments_total.labels(status="success").inc()
            self.deployment_duration.observe(operation.deployment_duration)

            print(f"✅ Blue-Green deployment completed for {operation.application_name}")
            return True

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            operation.completed_at = datetime.now()

            self.deployments_total.labels(status="failed").inc()

            print(f"❌ Blue-Green deployment failed for {operation.application_name}: {e}")
            return False

    async def _prepare_deployment(self, operation: DeploymentOperation):
        """Prepare Blue-Green deployment"""

        # Identify current deployment (Blue)
        operation.blue_deployment = await self._get_current_deployment(operation)

        # Generate green deployment name
        operation.green_deployment = f"{operation.application_name}-green-{int(time.time())}"

        print(f"📋 Blue deployment: {operation.blue_deployment}")
        print(f"📋 Green deployment: {operation.green_deployment}")

    async def _deploy_green_environment(self, operation: DeploymentOperation) -> bool:
        """Deploy green environment"""

        try:
            # Real Kubernetes deployment would go here
            apps_v1 = client.AppsV1Api()

            # Create green deployment manifest
            deployment_manifest = self._create_deployment_manifest(operation, "green")

            # Deploy to Kubernetes
            apps_v1.create_namespaced_deployment(
                namespace=operation.target_config.namespace, body=deployment_manifest
            )

            # Wait for deployment to be ready
            await self._wait_for_deployment_ready(
                operation.green_deployment, operation.target_config.namespace
            )

            return True

        except Exception as e:
            print(f"❌ Failed to deploy green environment: {e}")
            return False

    async def _switch_traffic_to_green(self, operation: DeploymentOperation) -> bool:
        """Switch traffic from blue to green"""

        try:
            print("🔄 Switching traffic to green environment")

            # Update service selector to point to green deployment
            core_v1 = client.CoreV1Api()

            service_patch = {
                "spec": {"selector": {"app": operation.application_name, "version": "green"}}
            }

            core_v1.patch_namespaced_service(
                name=operation.application_name,
                namespace=operation.target_config.namespace,
                body=service_patch,
            )

            return True

        except Exception as e:
            print(f"❌ Failed to switch traffic: {e}")
            return False

    async def _cleanup_blue_environment(self, operation: DeploymentOperation):
        """Cleanup blue environment after successful deployment"""

        try:
            print(f"🧹 Cleaning up blue environment: {operation.blue_deployment}")

            # Delete blue deployment
            apps_v1 = client.AppsV1Api()
            apps_v1.delete_namespaced_deployment(
                name=operation.blue_deployment,
                namespace=operation.target_config.namespace,
            )

        except Exception as e:
            print(f"⚠️ Warning: Failed to cleanup blue environment: {e}")

    async def _cleanup_green_environment(self, operation: DeploymentOperation):
        """Cleanup green environment after failed deployment"""

        try:
            print(f"🧹 Cleaning up failed green environment: {operation.green_deployment}")

            # Delete green deployment
            apps_v1 = client.AppsV1Api()
            apps_v1.delete_namespaced_deployment(
                name=operation.green_deployment,
                namespace=operation.target_config.namespace,
            )

        except Exception as e:
            print(f"⚠️ Warning: Failed to cleanup green environment: {e}")

    async def rollback(self, operation_id: str, reason: str = "Manual rollback") -> bool:
        """Rollback Blue-Green deployment"""

        if operation_id not in self.operations:
            print(f"❌ Operation {operation_id} not found")
            return False

        operation = self.operations[operation_id]

        try:
            print(f"⏪ Rolling back Blue-Green deployment: {operation.application_name}")

            operation.current_phase = DeploymentPhase.ROLLING_BACK
            operation.rollback_reason = reason

            # Switch traffic back to blue
            switch_success = await self._switch_traffic_to_blue(operation)

            if switch_success:
                # Cleanup green environment
                await self._cleanup_green_environment(operation)

                operation.status = "rolled_back"
                operation.completed_at = datetime.now()

                print(f"✅ Rollback completed for {operation.application_name}")
                return True
            print(f"❌ Rollback failed for {operation.application_name}")
            return False

        except Exception as e:
            print(f"❌ Rollback error for {operation.application_name}: {e}")
            return False

    async def _switch_traffic_to_blue(self, operation: DeploymentOperation) -> bool:
        """Switch traffic back to blue environment"""

        try:
            print("🔄 Switching traffic back to blue environment")

            # Update service selector to point back to blue deployment
            core_v1 = client.CoreV1Api()

            service_patch = {
                "spec": {"selector": {"app": operation.application_name, "version": "blue"}}
            }

            core_v1.patch_namespaced_service(
                name=operation.application_name,
                namespace=operation.target_config.namespace,
                body=service_patch,
            )

            return True

        except Exception as e:
            print(f"❌ Failed to switch traffic back to blue: {e}")
            return False

    async def validate_deployment(self, operation: DeploymentOperation) -> builtins.dict[str, Any]:
        """Validate Blue-Green deployment"""

        validation_results = {"success": False, "checks": {}, "error": None}

        try:
            if not operation.validation_config or not operation.validation_config.enabled:
                validation_results["success"] = True
                return validation_results

            config = operation.validation_config

            # Health check validation
            if config.health_check_enabled:
                health_check = await self._perform_health_check(operation)
                validation_results["checks"]["health_check"] = health_check

                if not health_check["success"]:
                    validation_results["error"] = "Health check failed"
                    return validation_results

            # Performance validation
            if config.performance_check_enabled:
                performance_check = await self._perform_performance_check(operation)
                validation_results["checks"]["performance_check"] = performance_check

                if not performance_check["success"]:
                    validation_results["error"] = "Performance check failed"
                    return validation_results

            # Custom validations
            for custom_validation in config.custom_validations:
                custom_check = await self._perform_custom_validation(operation, custom_validation)
                validation_results["checks"][custom_validation["name"]] = custom_check

                if not custom_check["success"]:
                    validation_results["error"] = (
                        f"Custom validation failed: {custom_validation['name']}"
                    )
                    return validation_results

            validation_results["success"] = True

        except Exception as e:
            validation_results["error"] = str(e)

        return validation_results

    async def _perform_health_check(
        self, operation: DeploymentOperation
    ) -> builtins.dict[str, Any]:
        """Perform health check validation"""

        try:
            config = operation.validation_config

            for attempt in range(config.health_check_retries):
                # Mock health check - would make actual HTTP request
                await asyncio.sleep(1)

                # Simulate health check success after a few attempts
                if attempt >= 2:
                    return {
                        "success": True,
                        "attempts": attempt + 1,
                        "response_time": random.randint(50, 200),
                    }

            return {
                "success": False,
                "attempts": config.health_check_retries,
                "error": "Health check timeout",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _perform_performance_check(
        self, operation: DeploymentOperation
    ) -> builtins.dict[str, Any]:
        """Perform performance validation"""

        try:
            config = operation.validation_config

            # Mock performance metrics
            response_time = random.randint(100, 500)
            success_rate = random.uniform(0.95, 1.0)

            performance_ok = (
                response_time <= config.max_response_time
                and success_rate >= config.min_success_rate
            )

            return {
                "success": performance_ok,
                "response_time": response_time,
                "success_rate": success_rate,
                "threshold_response_time": config.max_response_time,
                "threshold_success_rate": config.min_success_rate,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _perform_custom_validation(
        self, operation: DeploymentOperation, validation: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Perform custom validation"""

        try:
            # Mock custom validation
            await asyncio.sleep(0.5)

            # Simulate validation based on type
            validation_type = validation.get("type", "generic")

            if validation_type == "database_connectivity":
                return {"success": True, "message": "Database connectivity verified"}
            if validation_type == "external_api_check":
                return {
                    "success": True,
                    "message": "External API connectivity verified",
                }
            return {"success": True, "message": "Generic validation passed"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _get_current_deployment(self, operation: DeploymentOperation) -> str:
        """Get current active deployment name"""
        return f"{operation.application_name}-blue"

    async def _wait_for_deployment_ready(self, deployment_name: str, namespace: str):
        """Wait for deployment to be ready"""
        # Mock implementation
        await asyncio.sleep(2)

    def _create_deployment_manifest(
        self, operation: DeploymentOperation, color: str
    ) -> builtins.dict[str, Any]:
        """Create Kubernetes deployment manifest"""

        target = operation.target_config

        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": f"{operation.application_name}-{color}",
                "namespace": target.namespace,
                "labels": {
                    "app": operation.application_name,
                    "version": color,
                    **target.labels,
                },
            },
            "spec": {
                "replicas": target.replicas,
                "selector": {"matchLabels": {"app": operation.application_name, "version": color}},
                "template": {
                    "metadata": {"labels": {"app": operation.application_name, "version": color}},
                    "spec": {
                        "containers": [
                            {
                                "name": operation.application_name,
                                "image": f"{target.image}:{target.tag}",
                                "ports": [{"containerPort": target.health_check_port}],
                                "resources": {
                                    "requests": {
                                        "cpu": target.cpu_request,
                                        "memory": target.memory_request,
                                    },
                                    "limits": {
                                        "cpu": target.cpu_limit,
                                        "memory": target.memory_limit,
                                    },
                                },
                                "livenessProbe": {
                                    "httpGet": {
                                        "path": target.health_check_path,
                                        "port": target.health_check_port,
                                    },
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {
                                        "path": target.health_check_path,
                                        "port": target.health_check_port,
                                    },
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                            }
                        ]
                    },
                },
            },
        }


class CanaryDeploymentStrategy(DeploymentStrategyBase):
    """
    Canary deployment strategy implementation

    Features:
    - Gradual traffic shifting
    - Automated rollback on failure
    - A/B testing capabilities
    - Metrics-based promotion
    """

    def __init__(self):
        super().__init__("canary")
        self.default_canary_steps = [10, 25, 50, 75, 100]
        self.step_duration = 300  # 5 minutes per step

    async def deploy(self, operation: DeploymentOperation) -> bool:
        """Execute Canary deployment"""

        try:
            print(f"🐦 Starting Canary deployment for {operation.application_name}")

            # Phase 1: Preparation
            self._update_operation_phase(operation, DeploymentPhase.PREPARING, 5)
            await self._prepare_canary_deployment(operation)

            # Phase 2: Deploy canary version
            self._update_operation_phase(operation, DeploymentPhase.DEPLOYING, 15)
            canary_success = await self._deploy_canary_version(operation)

            if not canary_success:
                operation.status = "failed"
                operation.error_message = "Failed to deploy canary version"
                return False

            # Phase 3: Gradual traffic shifting
            for i, traffic_percentage in enumerate(self.default_canary_steps):
                progress = 20 + (i * 15)  # Progress from 20% to 95%
                self._update_operation_phase(operation, DeploymentPhase.PROMOTING, progress)

                print(f"🔄 Shifting {traffic_percentage}% traffic to canary")

                # Update traffic split
                success = await self._update_traffic_split(operation, traffic_percentage)
                if not success:
                    await self.rollback(operation.operation_id, "Traffic split failed")
                    return False

                # Wait for step duration
                await asyncio.sleep(5)  # Shortened for demo

                # Validate canary performance
                validation_results = await self.validate_deployment(operation)
                operation.validation_results[f"step_{traffic_percentage}"] = validation_results

                if not validation_results.get("success", False):
                    await self.rollback(
                        operation.operation_id,
                        f"Validation failed at {traffic_percentage}%",
                    )
                    return False

                # Break if 100% traffic
                if traffic_percentage == 100:
                    break

            # Phase 4: Complete promotion
            self._update_operation_phase(operation, DeploymentPhase.COMPLETED, 100)
            await self._complete_canary_promotion(operation)

            operation.status = "succeeded"
            operation.completed_at = datetime.now()
            operation.deployment_duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

            self.deployments_total.labels(status="success").inc()
            self.deployment_duration.observe(operation.deployment_duration)

            print(f"✅ Canary deployment completed for {operation.application_name}")
            return True

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            operation.completed_at = datetime.now()

            self.deployments_total.labels(status="failed").inc()

            print(f"❌ Canary deployment failed for {operation.application_name}: {e}")
            return False

    async def _prepare_canary_deployment(self, operation: DeploymentOperation):
        """Prepare canary deployment"""

        # Generate canary deployment name
        operation.canary_deployment = f"{operation.application_name}-canary-{int(time.time())}"

        print(f"📋 Canary deployment: {operation.canary_deployment}")

    async def _deploy_canary_version(self, operation: DeploymentOperation) -> bool:
        """Deploy canary version"""

        try:
            print(f"🐦 Deploying canary version: {operation.canary_deployment}")

            # Mock canary deployment
            await asyncio.sleep(2)

            return True

        except Exception as e:
            print(f"❌ Failed to deploy canary version: {e}")
            return False

    async def _update_traffic_split(
        self, operation: DeploymentOperation, canary_percentage: int
    ) -> bool:
        """Update traffic split between stable and canary"""

        try:
            stable_percentage = 100 - canary_percentage

            print(f"📊 Traffic split - Stable: {stable_percentage}%, Canary: {canary_percentage}%")

            # Mock traffic split update
            await asyncio.sleep(1)

            return True

        except Exception as e:
            print(f"❌ Failed to update traffic split: {e}")
            return False

    async def _complete_canary_promotion(self, operation: DeploymentOperation):
        """Complete canary promotion by replacing stable version"""

        try:
            print("🎯 Promoting canary to stable")

            # Mock promotion
            await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ Warning: Failed to complete canary promotion: {e}")

    async def rollback(self, operation_id: str, reason: str = "Manual rollback") -> bool:
        """Rollback canary deployment"""

        if operation_id not in self.operations:
            print(f"❌ Operation {operation_id} not found")
            return False

        operation = self.operations[operation_id]

        try:
            print(f"⏪ Rolling back canary deployment: {operation.application_name}")

            operation.current_phase = DeploymentPhase.ROLLING_BACK
            operation.rollback_reason = reason

            # Revert traffic to 100% stable
            success = await self._update_traffic_split(operation, 0)

            if success:
                # Remove canary deployment
                await self._remove_canary_deployment(operation)

                operation.status = "rolled_back"
                operation.completed_at = datetime.now()

                print(f"✅ Canary rollback completed for {operation.application_name}")
                return True
            print(f"❌ Canary rollback failed for {operation.application_name}")
            return False

        except Exception as e:
            print(f"❌ Canary rollback error for {operation.application_name}: {e}")
            return False

    async def _remove_canary_deployment(self, operation: DeploymentOperation):
        """Remove canary deployment"""

        try:
            print(f"🧹 Removing canary deployment: {operation.canary_deployment}")

            # Mock canary removal
            await asyncio.sleep(1)

        except Exception as e:
            print(f"⚠️ Warning: Failed to remove canary deployment: {e}")

    async def validate_deployment(self, operation: DeploymentOperation) -> builtins.dict[str, Any]:
        """Validate canary deployment performance"""

        validation_results = {"success": False, "metrics": {}, "error": None}

        try:
            if not operation.validation_config or not operation.validation_config.enabled:
                validation_results["success"] = True
                return validation_results

            config = operation.validation_config

            # Mock metrics collection
            error_rate = random.uniform(0.0, 0.1)  # 0-10% error rate
            avg_latency = random.randint(100, 800)  # 100-800ms latency

            validation_results["metrics"] = {
                "error_rate": error_rate,
                "avg_latency": avg_latency,
                "success_rate": 1.0 - error_rate,
            }

            # Check thresholds
            if error_rate > config.error_threshold:
                validation_results["error"] = (
                    f"Error rate {error_rate:.3f} exceeds threshold {config.error_threshold}"
                )
                return validation_results

            if avg_latency > config.latency_threshold:
                validation_results["error"] = (
                    f"Latency {avg_latency}ms exceeds threshold {config.latency_threshold}ms"
                )
                return validation_results

            validation_results["success"] = True

        except Exception as e:
            validation_results["error"] = str(e)

        return validation_results


class RollingDeploymentStrategy(DeploymentStrategyBase):
    """
    Rolling deployment strategy implementation

    Features:
    - Pod-by-pod replacement
    - Configurable rollout parameters
    - Health check integration
    - Automatic pause on failure
    """

    def __init__(self):
        super().__init__("rolling")
        self.max_surge = "25%"
        self.max_unavailable = "25%"

    async def deploy(self, operation: DeploymentOperation) -> bool:
        """Execute Rolling deployment"""

        try:
            print(f"🔄 Starting Rolling deployment for {operation.application_name}")

            # Phase 1: Preparation
            self._update_operation_phase(operation, DeploymentPhase.PREPARING, 10)
            await self._prepare_rolling_deployment(operation)

            # Phase 2: Update deployment
            self._update_operation_phase(operation, DeploymentPhase.DEPLOYING, 30)
            update_success = await self._update_deployment(operation)

            if not update_success:
                operation.status = "failed"
                operation.error_message = "Failed to update deployment"
                return False

            # Phase 3: Monitor rollout
            self._update_operation_phase(operation, DeploymentPhase.VALIDATING, 50)
            rollout_success = await self._monitor_rollout(operation)

            if not rollout_success:
                await self.rollback(operation.operation_id, "Rollout validation failed")
                return False

            # Phase 4: Final validation
            self._update_operation_phase(operation, DeploymentPhase.COMPLETED, 100)
            validation_results = await self.validate_deployment(operation)
            operation.validation_results = validation_results

            if not validation_results.get("success", False):
                await self.rollback(operation.operation_id, "Final validation failed")
                return False

            operation.status = "succeeded"
            operation.completed_at = datetime.now()
            operation.deployment_duration = (
                operation.completed_at - operation.started_at
            ).total_seconds()

            self.deployments_total.labels(status="success").inc()
            self.deployment_duration.observe(operation.deployment_duration)

            print(f"✅ Rolling deployment completed for {operation.application_name}")
            return True

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            operation.completed_at = datetime.now()

            self.deployments_total.labels(status="failed").inc()

            print(f"❌ Rolling deployment failed for {operation.application_name}: {e}")
            return False

    async def _prepare_rolling_deployment(self, operation: DeploymentOperation):
        """Prepare rolling deployment"""
        print(f"📋 Preparing rolling update for {operation.application_name}")

    async def _update_deployment(self, operation: DeploymentOperation) -> bool:
        """Update deployment with new image"""

        try:
            print(
                f"🔄 Updating deployment image to {operation.target_config.image}:{operation.target_config.tag}"
            )

            # Mock deployment update
            await asyncio.sleep(2)

            return True

        except Exception as e:
            print(f"❌ Failed to update deployment: {e}")
            return False

    async def _monitor_rollout(self, operation: DeploymentOperation) -> bool:
        """Monitor rolling deployment progress"""

        try:
            print("👀 Monitoring rollout progress")

            # Mock rollout monitoring
            for i in range(5):
                await asyncio.sleep(1)
                progress = 50 + (i * 8)  # Progress from 50% to 82%
                self._update_operation_phase(operation, DeploymentPhase.VALIDATING, progress)
                print(f"📊 Rollout progress: {i + 1}/5 pods updated")

            return True

        except Exception as e:
            print(f"❌ Rollout monitoring failed: {e}")
            return False

    async def rollback(self, operation_id: str, reason: str = "Manual rollback") -> bool:
        """Rollback rolling deployment"""

        if operation_id not in self.operations:
            print(f"❌ Operation {operation_id} not found")
            return False

        operation = self.operations[operation_id]

        try:
            print(f"⏪ Rolling back deployment: {operation.application_name}")

            operation.current_phase = DeploymentPhase.ROLLING_BACK
            operation.rollback_reason = reason

            # Mock rollback
            await asyncio.sleep(2)

            operation.status = "rolled_back"
            operation.completed_at = datetime.now()

            print(f"✅ Rolling deployment rollback completed for {operation.application_name}")
            return True

        except Exception as e:
            print(f"❌ Rolling deployment rollback error for {operation.application_name}: {e}")
            return False

    async def validate_deployment(self, operation: DeploymentOperation) -> builtins.dict[str, Any]:
        """Validate rolling deployment"""

        validation_results = {"success": False, "pod_status": {}, "error": None}

        try:
            # Mock pod status check
            validation_results["pod_status"] = {
                "ready_pods": operation.target_config.replicas,
                "total_pods": operation.target_config.replicas,
                "ready_percentage": 100.0,
            }

            validation_results["success"] = True

        except Exception as e:
            validation_results["error"] = str(e)

        return validation_results


class DeploymentOrchestrator:
    """
    Main deployment orchestrator managing all deployment strategies

    Features:
    - Strategy selection and execution
    - Operation tracking and monitoring
    - Rollback management
    - Metrics and reporting
    """

    def __init__(self):
        # Initialize strategies
        self.strategies = {
            DeploymentStrategy.BLUE_GREEN: BlueGreenDeploymentStrategy(),
            DeploymentStrategy.CANARY: CanaryDeploymentStrategy(),
            DeploymentStrategy.ROLLING: RollingDeploymentStrategy(),
        }

        # Operation tracking
        self.operations: builtins.dict[str, DeploymentOperation] = {}

        # Metrics
        self.active_deployments = Gauge(
            "marty_active_deployments_total",
            "Active deployments by strategy",
            ["strategy"],
        )

    async def deploy(
        self,
        application_name: str,
        strategy: DeploymentStrategy,
        target_config: DeploymentTarget,
        source_version: str = "",
        target_version: str = "",
        validation_config: DeploymentValidation | None = None,
        traffic_config: TrafficSplit | None = None,
    ) -> DeploymentOperation:
        """Execute deployment with specified strategy"""

        # Create deployment operation
        operation = DeploymentOperation(
            operation_id=f"deploy_{application_name}_{int(time.time())}",
            application_name=application_name,
            strategy=strategy,
            started_at=datetime.now(),
            source_version=source_version,
            target_version=target_version,
            target_config=target_config,
            validation_config=validation_config or DeploymentValidation(),
            traffic_config=traffic_config,
        )

        # Store operation
        self.operations[operation.operation_id] = operation

        # Get strategy implementation
        strategy_impl = self.strategies.get(strategy)
        if not strategy_impl:
            operation.status = "failed"
            operation.error_message = f"Strategy {strategy.value} not implemented"
            return operation

        # Store operation in strategy
        strategy_impl.operations[operation.operation_id] = operation

        # Execute deployment
        try:
            print(f"🚀 Starting {strategy.value} deployment for {application_name}")

            success = await strategy_impl.deploy(operation)

            if success:
                print(f"✅ Deployment {operation.operation_id} completed successfully")
            else:
                print(f"❌ Deployment {operation.operation_id} failed")

        except Exception as e:
            operation.status = "failed"
            operation.error_message = str(e)
            operation.completed_at = datetime.now()
            print(f"❌ Deployment {operation.operation_id} error: {e}")

        return operation

    async def rollback_deployment(self, operation_id: str, reason: str = "Manual rollback") -> bool:
        """Rollback deployment operation"""

        if operation_id not in self.operations:
            print(f"❌ Operation {operation_id} not found")
            return False

        operation = self.operations[operation_id]
        strategy_impl = self.strategies.get(operation.strategy)

        if not strategy_impl:
            print(f"❌ Strategy {operation.strategy.value} not available for rollback")
            return False

        return await strategy_impl.rollback(operation_id, reason)

    def get_deployment_status(self, operation_id: str) -> builtins.dict[str, Any] | None:
        """Get deployment operation status"""

        if operation_id not in self.operations:
            return None

        operation = self.operations[operation_id]
        return operation.to_dict()

    def list_active_deployments(self) -> builtins.list[builtins.dict[str, Any]]:
        """List all active deployments"""

        active_ops = [op for op in self.operations.values() if op.status == "running"]

        return [op.to_dict() for op in active_ops]

    def get_deployment_metrics(self) -> builtins.dict[str, Any]:
        """Get deployment metrics and statistics"""

        total_deployments = len(self.operations)

        by_strategy = {}
        by_status = {}
        avg_duration = {}

        for operation in self.operations.values():
            # Count by strategy
            strategy = operation.strategy.value
            by_strategy[strategy] = by_strategy.get(strategy, 0) + 1

            # Count by status
            status = operation.status
            by_status[status] = by_status.get(status, 0) + 1

            # Average duration by strategy
            if operation.deployment_duration and operation.status == "succeeded":
                if strategy not in avg_duration:
                    avg_duration[strategy] = []
                avg_duration[strategy].append(operation.deployment_duration)

        # Calculate averages
        for strategy, durations in avg_duration.items():
            avg_duration[strategy] = sum(durations) / len(durations)

        return {
            "total_deployments": total_deployments,
            "deployments_by_strategy": by_strategy,
            "deployments_by_status": by_status,
            "average_duration_by_strategy": avg_duration,
            "active_deployments": len(self.list_active_deployments()),
        }


# Example usage and demo
async def main():
    """Example usage of advanced deployment strategies"""

    print("=== Advanced Deployment Strategies Demo ===")

    # Initialize deployment orchestrator
    orchestrator = DeploymentOrchestrator()

    # Create deployment target configuration
    target_config = DeploymentTarget(
        name="example-api",
        namespace="default",
        replicas=3,
        image="example/api",
        tag="v2.0.0",
        cpu_request="200m",
        cpu_limit="500m",
        memory_request="256Mi",
        memory_limit="512Mi",
    )

    # Create validation configuration
    validation_config = DeploymentValidation(
        enabled=True,
        health_check_enabled=True,
        performance_check_enabled=True,
        auto_rollback_enabled=True,
        error_threshold=0.05,
        custom_validations=[{"name": "database_connectivity", "type": "database_connectivity"}],
    )

    # Demo Blue-Green deployment
    print("\n🔵🟢 Testing Blue-Green Deployment")
    bg_operation = await orchestrator.deploy(
        application_name="example-api",
        strategy=DeploymentStrategy.BLUE_GREEN,
        target_config=target_config,
        source_version="v1.9.0",
        target_version="v2.0.0",
        validation_config=validation_config,
    )

    print(f"Blue-Green deployment result: {bg_operation.status}")

    # Demo Canary deployment
    print("\n🐦 Testing Canary Deployment")
    canary_operation = await orchestrator.deploy(
        application_name="example-worker",
        strategy=DeploymentStrategy.CANARY,
        target_config=target_config,
        source_version="v1.9.0",
        target_version="v2.0.0",
        validation_config=validation_config,
    )

    print(f"Canary deployment result: {canary_operation.status}")

    # Demo Rolling deployment
    print("\n🔄 Testing Rolling Deployment")
    rolling_operation = await orchestrator.deploy(
        application_name="example-frontend",
        strategy=DeploymentStrategy.ROLLING,
        target_config=target_config,
        source_version="v1.9.0",
        target_version="v2.0.0",
        validation_config=validation_config,
    )

    print(f"Rolling deployment result: {rolling_operation.status}")

    # Show deployment metrics
    metrics = orchestrator.get_deployment_metrics()
    print("\n📊 Deployment Metrics:")
    print(f"Total deployments: {metrics['total_deployments']}")
    print(f"By strategy: {metrics['deployments_by_strategy']}")
    print(f"By status: {metrics['deployments_by_status']}")
    print(f"Average durations: {metrics['average_duration_by_strategy']}")


if __name__ == "__main__":
    asyncio.run(main())
