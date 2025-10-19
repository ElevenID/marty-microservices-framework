"""
Deployment Automation and Orchestration for Marty Microservices Framework

Provides comprehensive deployment automation including:
- Multi-environment deployment coordination
- Automated rollback mechanisms
- Health monitoring and validation
- Integration with CI/CD pipelines
- Feature flag management
- Deployment analytics and reporting
"""

import asyncio
import builtins
import importlib.util
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter, Histogram

# Import our deployment components
from .strategies import (
    DeploymentOperation,
    DeploymentOrchestrator,
    DeploymentStrategy,
    DeploymentTarget,
    DeploymentValidation,
)
from .traffic_management import (
    RoutingRule,
    TrafficBackend,
    TrafficDestination,
    TrafficOrchestrator,
    TrafficRoute,
)

# External dependencies availability checks
KUBERNETES_AVAILABLE = importlib.util.find_spec("kubernetes") is not None
METRICS_AVAILABLE = importlib.util.find_spec("prometheus_client") is not None

class Environment(Enum):
    """Deployment environment types"""

    DEVELOPMENT = "development"
    STAGING = "staging"
    TESTING = "testing"
    PRODUCTION = "production"
    CANARY = "canary"
    PREVIEW = "preview"


class DeploymentTrigger(Enum):
    """Deployment trigger types"""

    MANUAL = "manual"
    GIT_PUSH = "git_push"
    SCHEDULED = "scheduled"
    API_CALL = "api_call"
    WEBHOOK = "webhook"
    CI_CD = "ci_cd"


class ValidationLevel(Enum):
    """Validation strictness levels"""

    NONE = "none"
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"
    PARANOID = "paranoid"


@dataclass
class EnvironmentConfig:
    """Environment-specific configuration"""

    name: str
    environment: Environment

    # Cluster configuration
    cluster_name: str = "default"
    namespace: str = "default"
    region: str = "us-east-1"

    # Resource configuration
    min_replicas: int = 1
    max_replicas: int = 10
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"

    # Network configuration
    ingress_enabled: bool = True
    load_balancer_type: str = "nginx"
    ssl_enabled: bool = False

    # Monitoring configuration
    monitoring_enabled: bool = True
    logging_enabled: bool = True
    tracing_enabled: bool = False

    # Validation configuration
    validation_level: ValidationLevel = ValidationLevel.STANDARD
    health_check_timeout: int = 300
    performance_thresholds: builtins.dict[str, Any] = field(default_factory=dict)

    # Feature flags
    feature_flags: builtins.dict[str, bool] = field(default_factory=dict)

    # Environment variables
    env_vars: builtins.dict[str, str] = field(default_factory=dict)

    # Secret configuration
    secrets: builtins.list[str] = field(default_factory=list)
    config_maps: builtins.list[str] = field(default_factory=list)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "environment": self.environment.value,
            "validation_level": self.validation_level.value,
        }


@dataclass
class DeploymentPipeline:
    """Deployment pipeline configuration"""

    name: str
    application_name: str

    # Pipeline stages
    environments: builtins.list[EnvironmentConfig]

    # Deployment configuration
    strategy_per_env: builtins.dict[str, DeploymentStrategy] = field(default_factory=dict)
    approval_required: builtins.dict[str, bool] = field(default_factory=dict)
    auto_promote: builtins.dict[str, bool] = field(default_factory=dict)

    # Rollback configuration
    auto_rollback_enabled: bool = True
    rollback_conditions: builtins.dict[str, Any] = field(default_factory=dict)

    # Notifications
    notification_channels: builtins.list[str] = field(default_factory=list)

    # Traffic management
    traffic_backend: TrafficBackend = TrafficBackend.ISTIO

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "environments": [env.to_dict() for env in self.environments],
            "strategy_per_env": {
                env: strategy.value for env, strategy in self.strategy_per_env.items()
            },
            "traffic_backend": self.traffic_backend.value,
        }


@dataclass
class PipelineExecution:
    """Pipeline execution tracking"""

    execution_id: str
    pipeline_name: str
    triggered_by: DeploymentTrigger
    started_at: datetime

    # Execution context
    source_version: str = ""
    target_version: str = ""
    trigger_metadata: builtins.dict[str, Any] = field(default_factory=dict)

    # Stage tracking
    current_stage: str = ""
    completed_stages: builtins.list[str] = field(default_factory=list)
    failed_stages: builtins.list[str] = field(default_factory=list)

    # Operations
    deployment_operations: builtins.dict[str, str] = field(
        default_factory=dict
    )  # env -> operation_id

    # Status
    status: str = "running"  # running, succeeded, failed, cancelled, paused
    completed_at: datetime | None = None
    error_message: str | None = None

    # Results
    deployment_results: builtins.dict[str, Any] = field(default_factory=dict)
    validation_results: builtins.dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "triggered_by": self.triggered_by.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class FeatureFlagManager:
    """
    Feature flag management for deployment automation

    Features:
    - Environment-specific flags
    - Gradual rollout support
    - A/B testing integration
    - Runtime flag updates
    """

    def __init__(self):
        self.flags: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.flag_history: builtins.list[builtins.dict[str, Any]] = []

    def create_flag(
        self,
        flag_name: str,
        default_value: bool = False,
        description: str = "",
        environments: builtins.list[str] | None = None,
    ):
        """Create a new feature flag"""

        self.flags[flag_name] = {
            "name": flag_name,
            "description": description,
            "default_value": default_value,
            "created_at": datetime.now().isoformat(),
            "environments": {},
            "rollout_config": {},
            "metrics": {"evaluations": 0, "true_evaluations": 0},
        }

        # Initialize environment-specific values
        if environments:
            for env in environments:
                self.flags[flag_name]["environments"][env] = default_value

        print(f"🏳️ Created feature flag: {flag_name}")

    def set_flag_value(self, flag_name: str, value: bool, environment: str | None = None):
        """Set feature flag value"""

        if flag_name not in self.flags:
            print(f"❌ Feature flag {flag_name} not found")
            return

        if environment:
            self.flags[flag_name]["environments"][environment] = value
            target = f"environment {environment}"
        else:
            self.flags[flag_name]["default_value"] = value
            target = "default"

        # Record history
        self.flag_history.append(
            {
                "flag_name": flag_name,
                "environment": environment,
                "old_value": not value,  # Simplified
                "new_value": value,
                "timestamp": datetime.now().isoformat(),
                "changed_by": "system",
            }
        )

        print(f"🏳️ Updated flag {flag_name} for {target}: {value}")

    def evaluate_flag(
        self,
        flag_name: str,
        environment: str | None = None,
        user_context: builtins.dict[str, Any] | None = None,
    ) -> bool:
        """Evaluate feature flag value"""

        if flag_name not in self.flags:
            print(f"⚠️ Feature flag {flag_name} not found, returning False")
            return False

        flag = self.flags[flag_name]

        # Update metrics
        flag["metrics"]["evaluations"] += 1

        # Get value
        if environment and environment in flag["environments"]:
            value = flag["environments"][environment]
        else:
            value = flag["default_value"]

        # Check rollout configuration
        rollout_config = flag.get("rollout_config", {})
        if rollout_config and user_context:
            value = self._apply_rollout_rules(value, rollout_config, user_context)

        if value:
            flag["metrics"]["true_evaluations"] += 1

        return value

    def configure_gradual_rollout(
        self, flag_name: str, percentage: int, environment: str | None = None
    ):
        """Configure gradual rollout for feature flag"""

        if flag_name not in self.flags:
            print(f"❌ Feature flag {flag_name} not found")
            return

        rollout_key = environment if environment else "default"

        if "rollout_config" not in self.flags[flag_name]:
            self.flags[flag_name]["rollout_config"] = {}

        self.flags[flag_name]["rollout_config"][rollout_key] = {
            "type": "percentage",
            "percentage": percentage,
            "enabled": True,
        }

        print(f"🎯 Configured {percentage}% rollout for flag {flag_name}")

    def _apply_rollout_rules(
        self,
        base_value: bool,
        rollout_config: builtins.dict[str, Any],
        user_context: builtins.dict[str, Any],
    ) -> bool:
        """Apply rollout rules to determine flag value"""

        # Simple percentage-based rollout
        if rollout_config.get("type") == "percentage":
            percentage = rollout_config.get("percentage", 0)
            user_id = user_context.get("user_id", "anonymous")

            # Use hash of user_id to determine if user is in rollout
            user_hash = hash(user_id) % 100
            return base_value and (user_hash < percentage)

        return base_value

    def get_flag_status(self, flag_name: str) -> builtins.dict[str, Any] | None:
        """Get feature flag status and metrics"""

        if flag_name not in self.flags:
            return None

        flag = self.flags[flag_name].copy()

        # Calculate success rate
        evaluations = flag["metrics"]["evaluations"]
        if evaluations > 0:
            flag["metrics"]["true_rate"] = flag["metrics"]["true_evaluations"] / evaluations
        else:
            flag["metrics"]["true_rate"] = 0.0

        return flag

    def list_flags(self) -> builtins.list[builtins.dict[str, Any]]:
        """List all feature flags"""
        return [self.get_flag_status(name) for name in self.flags.keys()]


class HealthMonitor:
    """
    Health monitoring for deployment automation

    Features:
    - Multi-level health checks
    - Custom validation rules
    - Performance monitoring
    - Alerting integration
    """

    def __init__(self):
        self.health_checks: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.monitoring_history: builtins.list[builtins.dict[str, Any]] = []

    async def perform_health_check(
        self, target: str, check_config: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Perform comprehensive health check"""

        result = {
            "target": target,
            "timestamp": datetime.now().isoformat(),
            "overall_healthy": True,
            "checks": {},
            "metrics": {},
            "alerts": [],
        }

        try:
            # HTTP health check
            if check_config.get("http_check", {}).get("enabled", True):
                http_result = await self._perform_http_check(
                    target, check_config.get("http_check", {})
                )
                result["checks"]["http"] = http_result

                if not http_result["success"]:
                    result["overall_healthy"] = False
                    result["alerts"].append(f"HTTP health check failed for {target}")

            # Database connectivity check
            if check_config.get("database_check", {}).get("enabled", False):
                db_result = await self._perform_database_check(
                    target, check_config.get("database_check", {})
                )
                result["checks"]["database"] = db_result

                if not db_result["success"]:
                    result["overall_healthy"] = False
                    result["alerts"].append(f"Database connectivity failed for {target}")

            # Performance metrics check
            if check_config.get("performance_check", {}).get("enabled", True):
                perf_result = await self._perform_performance_check(
                    target, check_config.get("performance_check", {})
                )
                result["checks"]["performance"] = perf_result
                result["metrics"] = perf_result.get("metrics", {})

                if not perf_result["success"]:
                    result["overall_healthy"] = False
                    result["alerts"].append(f"Performance check failed for {target}")

            # Custom checks
            custom_checks = check_config.get("custom_checks", [])
            for custom_check in custom_checks:
                custom_result = await self._perform_custom_check(target, custom_check)
                result["checks"][custom_check["name"]] = custom_result

                if not custom_result["success"]:
                    result["overall_healthy"] = False
                    result["alerts"].append(
                        f"Custom check {custom_check['name']} failed for {target}"
                    )

        except Exception as e:
            result["overall_healthy"] = False
            result["error"] = str(e)
            result["alerts"].append(f"Health check error for {target}: {e}")

        # Store result
        self.monitoring_history.append(result)

        return result

    async def _perform_http_check(
        self, target: str, config: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Perform HTTP health check"""

        try:
            # Mock HTTP check
            await asyncio.sleep(0.1)

            # Simulate health check response
            response_time = 50 + (hash(target) % 100)  # 50-150ms
            status_code = 200

            success = status_code == 200 and response_time < config.get("timeout", 5000)

            return {
                "success": success,
                "status_code": status_code,
                "response_time": response_time,
                "endpoint": config.get("path", "/health"),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _perform_database_check(
        self, target: str, config: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Perform database connectivity check"""

        try:
            # Mock database check
            await asyncio.sleep(0.2)

            # Simulate database connectivity
            connection_time = 10 + (hash(target) % 50)  # 10-60ms
            success = connection_time < config.get("timeout", 1000)

            return {
                "success": success,
                "connection_time": connection_time,
                "database_type": config.get("type", "postgresql"),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _perform_performance_check(
        self, target: str, config: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Perform performance metrics check"""

        try:
            # Mock performance metrics
            await asyncio.sleep(0.1)

            # Simulate performance metrics
            cpu_usage = 20 + (hash(target) % 40)  # 20-60%
            memory_usage = 30 + (hash(target) % 50)  # 30-80%
            response_time = 100 + (hash(target) % 200)  # 100-300ms

            thresholds = config.get("thresholds", {})

            success = (
                cpu_usage < thresholds.get("cpu_max", 80)
                and memory_usage < thresholds.get("memory_max", 85)
                and response_time < thresholds.get("response_time_max", 500)
            )

            return {
                "success": success,
                "metrics": {
                    "cpu_usage": cpu_usage,
                    "memory_usage": memory_usage,
                    "response_time": response_time,
                },
                "thresholds": thresholds,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _perform_custom_check(
        self, target: str, config: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Perform custom health check"""

        try:
            # Mock custom check
            await asyncio.sleep(0.1)

            check_type = config.get("type", "generic")

            # Simulate different check types
            if check_type == "api_dependency":
                return {"success": True, "message": "API dependency check passed"}
            if check_type == "cache_connectivity":
                return {"success": True, "message": "Cache connectivity verified"}
            return {
                "success": True,
                "message": f"Custom check {config.get('name', 'unknown')} passed",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_health_summary(self, target: str, hours: int = 24) -> builtins.dict[str, Any]:
        """Get health summary for target over specified period"""

        cutoff_time = datetime.now() - timedelta(hours=hours)

        relevant_checks = [
            check
            for check in self.monitoring_history
            if (
                check["target"] == target
                and datetime.fromisoformat(check["timestamp"]) > cutoff_time
            )
        ]

        if not relevant_checks:
            return {
                "target": target,
                "period_hours": hours,
                "total_checks": 0,
                "success_rate": 0.0,
                "avg_response_time": 0.0,
            }

        total_checks = len(relevant_checks)
        successful_checks = sum(1 for check in relevant_checks if check["overall_healthy"])

        # Calculate average response time
        response_times = []
        for check in relevant_checks:
            http_check = check.get("checks", {}).get("http", {})
            if "response_time" in http_check:
                response_times.append(http_check["response_time"])

        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0

        return {
            "target": target,
            "period_hours": hours,
            "total_checks": total_checks,
            "successful_checks": successful_checks,
            "success_rate": successful_checks / total_checks,
            "avg_response_time": avg_response_time,
            "last_check": relevant_checks[-1] if relevant_checks else None,
        }


class DeploymentAutomationEngine:
    """
    Main deployment automation engine

    Features:
    - Pipeline execution and management
    - Multi-environment coordination
    - Automated rollbacks and validation
    - Feature flag integration
    - Health monitoring
    """

    def __init__(self):
        # Core components
        self.deployment_orchestrator = DeploymentOrchestrator()
        self.traffic_orchestrator = TrafficOrchestrator()
        self.feature_flag_manager = FeatureFlagManager()
        self.health_monitor = HealthMonitor()

        # Pipeline management
        self.pipelines: builtins.dict[str, DeploymentPipeline] = {}
        self.executions: builtins.dict[str, PipelineExecution] = {}

        # Configuration
        self.default_validation_configs = {
            ValidationLevel.BASIC: DeploymentValidation(
                enabled=True,
                health_check_enabled=True,
                performance_check_enabled=False,
                auto_rollback_enabled=True,
                error_threshold=0.1,
            ),
            ValidationLevel.STANDARD: DeploymentValidation(
                enabled=True,
                health_check_enabled=True,
                performance_check_enabled=True,
                auto_rollback_enabled=True,
                error_threshold=0.05,
            ),
            ValidationLevel.STRICT: DeploymentValidation(
                enabled=True,
                health_check_enabled=True,
                performance_check_enabled=True,
                auto_rollback_enabled=True,
                error_threshold=0.02,
                custom_validations=[
                    {"name": "security_scan", "type": "security"},
                    {"name": "performance_regression", "type": "performance"},
                ],
            ),
        }

        # Metrics
        if METRICS_AVAILABLE:
            self.pipeline_executions = Counter(
                "marty_pipeline_executions_total",
                "Total pipeline executions",
                ["pipeline", "status"],
            )

            self.deployment_duration = Histogram(
                "marty_pipeline_duration_seconds", "Pipeline execution duration"
            )

    def register_pipeline(self, pipeline: DeploymentPipeline):
        """Register deployment pipeline"""

        self.pipelines[pipeline.name] = pipeline
        print(f"📋 Registered pipeline: {pipeline.name}")

        # Initialize feature flags for environments
        for env_config in pipeline.environments:
            for flag_name, flag_value in env_config.feature_flags.items():
                if flag_name not in self.feature_flag_manager.flags:
                    self.feature_flag_manager.create_flag(
                        flag_name,
                        default_value=False,
                        description=f"Feature flag for {pipeline.application_name}",
                    )

                self.feature_flag_manager.set_flag_value(flag_name, flag_value, env_config.name)

    async def execute_pipeline(
        self,
        pipeline_name: str,
        target_version: str,
        trigger: DeploymentTrigger = DeploymentTrigger.MANUAL,
        source_version: str = "",
        trigger_metadata: builtins.dict[str, Any] | None = None,
        start_from_environment: str | None = None,
    ) -> PipelineExecution:
        """Execute deployment pipeline"""

        if pipeline_name not in self.pipelines:
            raise ValueError(f"Pipeline {pipeline_name} not found")

        pipeline = self.pipelines[pipeline_name]

        # Create execution
        execution = PipelineExecution(
            execution_id=f"exec_{pipeline_name}_{int(time.time())}",
            pipeline_name=pipeline_name,
            triggered_by=trigger,
            started_at=datetime.now(),
            source_version=source_version,
            target_version=target_version,
            trigger_metadata=trigger_metadata or {},
        )

        self.executions[execution.execution_id] = execution

        try:
            print(f"🚀 Starting pipeline execution: {execution.execution_id}")

            # Determine starting environment
            start_index = 0
            if start_from_environment:
                for i, env_config in enumerate(pipeline.environments):
                    if env_config.name == start_from_environment:
                        start_index = i
                        break

            # Execute pipeline stages
            for i in range(start_index, len(pipeline.environments)):
                env_config = pipeline.environments[i]

                execution.current_stage = env_config.name
                print(f"📍 Executing stage: {env_config.name}")

                # Check if approval is required
                if pipeline.approval_required.get(env_config.name, False):
                    print(f"⏸️ Manual approval required for {env_config.name}")
                    execution.status = "paused"
                    # In real implementation, would wait for approval
                    await asyncio.sleep(1)  # Mock approval wait
                    execution.status = "running"

                # Execute deployment for environment
                success = await self._execute_environment_deployment(
                    execution, pipeline, env_config
                )

                if success:
                    execution.completed_stages.append(env_config.name)
                    print(f"✅ Stage {env_config.name} completed successfully")

                    # Check auto-promotion
                    if not pipeline.auto_promote.get(env_config.name, True):
                        print(f"⏸️ Auto-promotion disabled for {env_config.name}")
                        execution.status = "paused"
                        break
                else:
                    execution.failed_stages.append(env_config.name)
                    execution.status = "failed"
                    execution.error_message = f"Deployment failed in {env_config.name}"

                    # Check auto-rollback
                    if pipeline.auto_rollback_enabled:
                        print(f"⏪ Auto-rollback triggered for {env_config.name}")
                        await self._execute_rollback(execution, pipeline, env_config)

                    break

            # Complete execution if all stages successful
            if len(execution.completed_stages) == len(pipeline.environments):
                execution.status = "succeeded"
                execution.completed_at = datetime.now()
                print(f"🎉 Pipeline execution completed successfully: {execution.execution_id}")

            # Update metrics
            if METRICS_AVAILABLE:
                self.pipeline_executions.labels(
                    pipeline=pipeline_name, status=execution.status
                ).inc()

                if execution.completed_at:
                    duration = (execution.completed_at - execution.started_at).total_seconds()
                    self.deployment_duration.observe(duration)

        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.now()
            print(f"❌ Pipeline execution failed: {execution.execution_id}: {e}")

        return execution

    async def _execute_environment_deployment(
        self,
        execution: PipelineExecution,
        pipeline: DeploymentPipeline,
        env_config: EnvironmentConfig,
    ) -> bool:
        """Execute deployment for specific environment"""

        try:
            # Create deployment target
            target = DeploymentTarget(
                name=pipeline.application_name,
                namespace=env_config.namespace,
                cluster=env_config.cluster_name,
                replicas=env_config.min_replicas,
                image=pipeline.application_name,
                tag=execution.target_version,
                cpu_request=env_config.cpu_request,
                cpu_limit=env_config.cpu_limit,
                memory_request=env_config.memory_request,
                memory_limit=env_config.memory_limit,
                labels={
                    "app": pipeline.application_name,
                    "environment": env_config.name,
                    "version": execution.target_version,
                },
            )

            # Get validation configuration
            validation_config = self.default_validation_configs.get(
                env_config.validation_level,
                self.default_validation_configs[ValidationLevel.STANDARD],
            )

            # Update validation with environment-specific thresholds
            if env_config.performance_thresholds:
                validation_config.custom_validations.append(
                    {
                        "name": "environment_performance",
                        "type": "performance",
                        "thresholds": env_config.performance_thresholds,
                    }
                )

            # Get deployment strategy
            strategy = pipeline.strategy_per_env.get(env_config.name, DeploymentStrategy.ROLLING)

            # Execute deployment
            deployment_operation = await self.deployment_orchestrator.deploy(
                application_name=pipeline.application_name,
                strategy=strategy,
                target_config=target,
                source_version=execution.source_version,
                target_version=execution.target_version,
                validation_config=validation_config,
            )

            # Store operation reference
            execution.deployment_operations[env_config.name] = deployment_operation.operation_id

            # Wait for deployment completion
            while deployment_operation.status == "running":
                await asyncio.sleep(5)
                # In real implementation, would check actual deployment status
                break  # Mock completion

            if deployment_operation.status == "succeeded":
                # Configure traffic management if required
                if strategy in [
                    DeploymentStrategy.BLUE_GREEN,
                    DeploymentStrategy.CANARY,
                ]:
                    await self._configure_environment_traffic(
                        execution, pipeline, env_config, deployment_operation
                    )

                # Perform additional health monitoring
                health_result = await self._monitor_environment_health(
                    execution, pipeline, env_config
                )

                execution.validation_results[env_config.name] = {
                    "deployment": deployment_operation.validation_results,
                    "health_monitoring": health_result,
                }

                return health_result.get("overall_healthy", True)
            execution.deployment_results[env_config.name] = {
                "status": deployment_operation.status,
                "error": deployment_operation.error_message,
            }
            return False

        except Exception as e:
            print(f"❌ Environment deployment failed for {env_config.name}: {e}")
            execution.deployment_results[env_config.name] = {
                "status": "failed",
                "error": str(e),
            }
            return False

    async def _configure_environment_traffic(
        self,
        execution: PipelineExecution,
        pipeline: DeploymentPipeline,
        env_config: EnvironmentConfig,
        deployment_operation: DeploymentOperation,
    ):
        """Configure traffic management for environment"""

        try:
            # Create traffic destinations
            destinations = [
                TrafficDestination(
                    name=f"{pipeline.application_name}-{env_config.name}",
                    host=f"{pipeline.application_name}.{env_config.namespace}.svc.cluster.local",
                    port=80,
                    weight=100,
                    labels={"version": execution.target_version},
                )
            ]

            # Create traffic route
            route = TrafficRoute(
                name=f"{pipeline.application_name}-{env_config.name}-route",
                rule_type=RoutingRule.WEIGHTED,
                destinations=destinations,
                match_paths=["/"],
                timeout=30,
            )

            # Configure route
            await self.traffic_orchestrator.configure_route(
                route, backends=[pipeline.traffic_backend]
            )

            print(f"🌐 Configured traffic for {env_config.name}")

        except Exception as e:
            print(f"⚠️ Failed to configure traffic for {env_config.name}: {e}")

    async def _monitor_environment_health(
        self,
        execution: PipelineExecution,
        pipeline: DeploymentPipeline,
        env_config: EnvironmentConfig,
    ) -> builtins.dict[str, Any]:
        """Monitor environment health after deployment"""

        target = f"{pipeline.application_name}-{env_config.name}"

        health_config = {
            "http_check": {
                "enabled": True,
                "path": "/health",
                "timeout": env_config.health_check_timeout,
            },
            "performance_check": {
                "enabled": env_config.monitoring_enabled,
                "thresholds": env_config.performance_thresholds,
            },
        }

        # Add environment-specific checks
        if "database" in env_config.env_vars:
            health_config["database_check"] = {
                "enabled": True,
                "type": "postgresql",
                "timeout": 1000,
            }

        health_result = await self.health_monitor.perform_health_check(target, health_config)

        print(
            f"🏥 Health check for {env_config.name}: {'✅' if health_result['overall_healthy'] else '❌'}"
        )

        return health_result

    async def _execute_rollback(
        self,
        execution: PipelineExecution,
        pipeline: DeploymentPipeline,
        env_config: EnvironmentConfig,
    ):
        """Execute rollback for environment"""

        try:
            operation_id = execution.deployment_operations.get(env_config.name)
            if operation_id:
                print(f"⏪ Rolling back deployment in {env_config.name}")

                success = await self.deployment_orchestrator.rollback_deployment(
                    operation_id, reason="Automated rollback due to deployment failure"
                )

                if success:
                    print(f"✅ Rollback completed for {env_config.name}")
                else:
                    print(f"❌ Rollback failed for {env_config.name}")

        except Exception as e:
            print(f"❌ Rollback error for {env_config.name}: {e}")

    def get_pipeline_status(self, pipeline_name: str) -> builtins.dict[str, Any] | None:
        """Get pipeline status and metrics"""

        if pipeline_name not in self.pipelines:
            return None

        pipeline = self.pipelines[pipeline_name]

        # Get recent executions
        recent_executions = [
            exec_data
            for exec_data in self.executions.values()
            if exec_data.pipeline_name == pipeline_name
        ]

        # Sort by start time
        recent_executions.sort(key=lambda x: x.started_at, reverse=True)

        # Calculate success rate
        total_executions = len(recent_executions)
        successful_executions = sum(
            1 for exec_data in recent_executions if exec_data.status == "succeeded"
        )

        success_rate = successful_executions / total_executions if total_executions > 0 else 0.0

        return {
            "pipeline": pipeline.to_dict(),
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": success_rate,
            "recent_executions": [exec_data.to_dict() for exec_data in recent_executions[:10]],
            "feature_flags": {
                flag_name: self.feature_flag_manager.get_flag_status(flag_name)
                for env_config in pipeline.environments
                for flag_name in env_config.feature_flags.keys()
            },
        }

    def get_execution_status(self, execution_id: str) -> builtins.dict[str, Any] | None:
        """Get execution status"""

        if execution_id not in self.executions:
            return None

        execution = self.executions[execution_id]
        return execution.to_dict()

    def list_active_executions(self) -> builtins.list[builtins.dict[str, Any]]:
        """List all active pipeline executions"""

        active_executions = [
            exec_data
            for exec_data in self.executions.values()
            if exec_data.status in ["running", "paused"]
        ]

        return [exec_data.to_dict() for exec_data in active_executions]


# Example usage and demo
async def main():
    """Example usage of deployment automation"""

    print("=== Deployment Automation Demo ===")

    # Initialize automation engine
    engine = DeploymentAutomationEngine()

    # Create environment configurations
    dev_env = EnvironmentConfig(
        name="development",
        environment=Environment.DEVELOPMENT,
        namespace="dev",
        min_replicas=1,
        max_replicas=3,
        validation_level=ValidationLevel.BASIC,
        feature_flags={"new_ui_enabled": True, "experimental_api": False},
    )

    staging_env = EnvironmentConfig(
        name="staging",
        environment=Environment.STAGING,
        namespace="staging",
        min_replicas=2,
        max_replicas=5,
        validation_level=ValidationLevel.STANDARD,
        feature_flags={"new_ui_enabled": True, "experimental_api": True},
        performance_thresholds={
            "response_time_max": 200,
            "cpu_max": 70,
            "memory_max": 80,
        },
    )

    prod_env = EnvironmentConfig(
        name="production",
        environment=Environment.PRODUCTION,
        namespace="prod",
        min_replicas=3,
        max_replicas=10,
        validation_level=ValidationLevel.STRICT,
        feature_flags={"new_ui_enabled": False, "experimental_api": False},
        performance_thresholds={
            "response_time_max": 100,
            "cpu_max": 60,
            "memory_max": 75,
        },
    )

    # Create deployment pipeline
    pipeline = DeploymentPipeline(
        name="api-service-pipeline",
        application_name="api-service",
        environments=[dev_env, staging_env, prod_env],
        strategy_per_env={
            "development": DeploymentStrategy.ROLLING,
            "staging": DeploymentStrategy.CANARY,
            "production": DeploymentStrategy.BLUE_GREEN,
        },
        approval_required={"production": True},
        auto_promote={"development": True, "staging": True, "production": False},
        auto_rollback_enabled=True,
    )

    # Register pipeline
    engine.register_pipeline(pipeline)

    # Execute pipeline
    print("\n🚀 Executing deployment pipeline")
    execution = await engine.execute_pipeline(
        pipeline_name="api-service-pipeline",
        target_version="v2.1.0",
        trigger=DeploymentTrigger.GIT_PUSH,
        source_version="v2.0.0",
        trigger_metadata={
            "commit_sha": "abc123def456",
            "author": "developer@company.com",
            "branch": "main",
        },
    )

    print(f"Pipeline execution result: {execution.status}")

    # Show pipeline status
    print("\n📊 Pipeline Status")
    pipeline_status = engine.get_pipeline_status("api-service-pipeline")
    if pipeline_status:
        print(f"Success rate: {pipeline_status['success_rate']:.2%}")
        print(f"Total executions: {pipeline_status['total_executions']}")
        print(f"Feature flags: {list(pipeline_status['feature_flags'].keys())}")

    # Test feature flag functionality
    print("\n🏳️ Feature Flag Management")
    ff_manager = engine.feature_flag_manager

    # Evaluate flags for different environments
    for env_name in ["development", "staging", "production"]:
        new_ui = ff_manager.evaluate_flag("new_ui_enabled", environment=env_name)
        experimental = ff_manager.evaluate_flag("experimental_api", environment=env_name)

        print(f"{env_name}: new_ui={new_ui}, experimental_api={experimental}")

    # Configure gradual rollout
    ff_manager.configure_gradual_rollout("new_ui_enabled", 50, "production")
    print("Configured 50% gradual rollout for new_ui_enabled in production")

    # Show execution details
    print("\n📋 Execution Details")
    execution_status = engine.get_execution_status(execution.execution_id)
    if execution_status:
        print(f"Execution ID: {execution_status['execution_id']}")
        print(f"Completed stages: {execution_status['completed_stages']}")
        print(f"Deployment operations: {list(execution_status['deployment_operations'].keys())}")


if __name__ == "__main__":
    asyncio.run(main())
