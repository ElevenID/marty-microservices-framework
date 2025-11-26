"""Main deployment orchestration engine."""

import asyncio
import builtins
import logging
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .enums import (
    DeploymentPhase,
    DeploymentStatus,
    DeploymentStrategy,
    EnvironmentType,
    ValidationResult,
)
from .managers.features import FeatureFlagManager
from .managers.infrastructure import InfrastructureManager
from .managers.rollback import RollbackManager
from .managers.traffic import TrafficManager
from .managers.validation import ValidationManager
from .models import (
    Deployment,
    DeploymentEvent,
    DeploymentTarget,
    DeploymentValidation,
    RollbackConfiguration,
    ServiceVersion,
    TrafficSplit,
)


class DeploymentOrchestrator:
    """Main deployment orchestration engine."""

    def __init__(self, service_name: str):
        """Initialize deployment orchestrator."""
        self.service_name = service_name

        # Active deployments
        self.active_deployments: builtins.dict[str, Deployment] = {}
        self.deployment_history: deque = deque(maxlen=1000)

        # Infrastructure managers
        self.infrastructure_manager = InfrastructureManager()
        self.traffic_manager = TrafficManager()
        self.validation_manager = ValidationManager()
        self.feature_flag_manager = FeatureFlagManager()
        self.rollback_manager = RollbackManager()

        # Deployment event tracking
        self.deployment_events: deque = deque(maxlen=10000)

        # Thread pool for concurrent operations
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="deployment")

    async def create_deployment(self, deployment_config: builtins.dict[str, Any]) -> str:
        """Create a new deployment."""
        deployment_id = str(uuid.uuid4())

        deployment = Deployment(
            deployment_id=deployment_id,
            service_name=self.service_name,
            strategy=DeploymentStrategy(deployment_config["strategy"]),
            source_version=ServiceVersion(**deployment_config["source_version"]),
            target_version=ServiceVersion(**deployment_config["target_version"]),
            target_environment=DeploymentTarget(**deployment_config["target_environment"]),
            traffic_split=TrafficSplit(**deployment_config.get("traffic_split", {})),
            validations=[
                DeploymentValidation(**v) for v in deployment_config.get("validations", [])
            ],
            rollback_config=RollbackConfiguration(**deployment_config.get("rollback_config", {})),
        )

        self.active_deployments[deployment_id] = deployment

        # Log deployment creation
        await self._log_deployment_event(
            deployment_id,
            "deployment_created",
            DeploymentPhase.PLANNING,
            {"strategy": deployment.strategy.value},
        )

        return deployment_id

    async def start_deployment(self, deployment_id: str) -> bool:
        """Start a deployment."""
        if deployment_id not in self.active_deployments:
            return False

        deployment = self.active_deployments[deployment_id]

        try:
            # Execute deployment based on strategy
            if deployment.strategy == DeploymentStrategy.BLUE_GREEN:
                await self._execute_blue_green_deployment(deployment)
            elif deployment.strategy == DeploymentStrategy.CANARY:
                await self._execute_canary_deployment(deployment)
            elif deployment.strategy == DeploymentStrategy.ROLLING:
                await self._execute_rolling_deployment(deployment)
            elif deployment.strategy == DeploymentStrategy.A_B_TEST:
                await self._execute_ab_test_deployment(deployment)
            else:
                await self._execute_recreate_deployment(deployment)

            return True

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(e)

            await self._log_deployment_event(
                deployment_id,
                "deployment_failed",
                deployment.current_phase,
                {"error": str(e)},
            )

            # Trigger rollback if configured
            if deployment.rollback_config.enabled:
                await self.rollback_deployment(deployment_id)

            return False

    async def _execute_blue_green_deployment(self, deployment: "Deployment"):
        """Execute blue-green deployment strategy."""
        deployment.status = DeploymentStatus.RUNNING
        deployment.current_phase = DeploymentPhase.PRE_DEPLOYMENT

        try:
            # Phase 1: Pre-deployment validation
            await self._log_deployment_event(
                deployment.deployment_id,
                "phase_started",
                DeploymentPhase.PRE_DEPLOYMENT,
            )

            # Prepare green environment
            green_environment = await self.infrastructure_manager.prepare_environment(
                deployment.target_environment,
                deployment.target_version,
                EnvironmentType.GREEN,
            )

            # Phase 2: Deploy to green environment
            deployment.current_phase = DeploymentPhase.DEPLOYMENT
            await self._log_deployment_event(
                deployment.deployment_id, "phase_started", DeploymentPhase.DEPLOYMENT
            )

            await self.infrastructure_manager.deploy_service(
                green_environment, deployment.target_version
            )

            # Phase 3: Validation
            deployment.current_phase = DeploymentPhase.VALIDATION
            await self._log_deployment_event(
                deployment.deployment_id, "phase_started", DeploymentPhase.VALIDATION
            )

            validation_results = await self.validation_manager.run_validations(
                deployment.validations, green_environment
            )

            if not all(r.result == ValidationResult.PASS for r in validation_results if r.required):
                raise Exception("Validation failed for green environment")

            # Phase 4: Traffic switching
            deployment.current_phase = DeploymentPhase.TRAFFIC_SHIFTING
            await self._log_deployment_event(
                deployment.deployment_id,
                "phase_started",
                DeploymentPhase.TRAFFIC_SHIFTING,
            )

            # Switch traffic from blue to green
            await self.traffic_manager.switch_traffic(
                deployment.target_environment,
                from_version=deployment.source_version.version,
                to_version=deployment.target_version.version,
            )

            # Phase 5: Post-deployment monitoring
            deployment.current_phase = DeploymentPhase.MONITORING
            await self._log_deployment_event(
                deployment.deployment_id, "phase_started", DeploymentPhase.MONITORING
            )

            # Monitor for stability period
            await self._monitor_deployment_health(deployment, duration_seconds=300)

            # Phase 6: Completion
            deployment.current_phase = DeploymentPhase.COMPLETION
            deployment.status = DeploymentStatus.SUCCESS

            await self._log_deployment_event(
                deployment.deployment_id,
                "deployment_completed",
                DeploymentPhase.COMPLETION,
            )

            # Cleanup old blue environment
            await self.infrastructure_manager.cleanup_environment(
                deployment.target_environment,
                deployment.source_version,
                EnvironmentType.BLUE,
            )

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(e)
            raise

    async def _execute_canary_deployment(self, deployment: "Deployment"):
        """Execute canary deployment strategy."""
        deployment.status = DeploymentStatus.RUNNING
        deployment.current_phase = DeploymentPhase.PRE_DEPLOYMENT

        try:
            # Phase 1: Pre-deployment validation
            await self._log_deployment_event(
                deployment.deployment_id,
                "phase_started",
                DeploymentPhase.PRE_DEPLOYMENT,
            )

            # Prepare canary environment
            canary_environment = await self.infrastructure_manager.prepare_environment(
                deployment.target_environment,
                deployment.target_version,
                EnvironmentType.CANARY,
            )

            # Phase 2: Deploy canary version
            deployment.current_phase = DeploymentPhase.DEPLOYMENT
            await self._log_deployment_event(
                deployment.deployment_id, "phase_started", DeploymentPhase.DEPLOYMENT
            )

            await self.infrastructure_manager.deploy_service(
                canary_environment, deployment.target_version
            )

            # Phase 3: Initial validation
            deployment.current_phase = DeploymentPhase.VALIDATION
            await self._log_deployment_event(
                deployment.deployment_id, "phase_started", DeploymentPhase.VALIDATION
            )

            validation_results = await self.validation_manager.run_validations(
                deployment.validations, canary_environment
            )

            if not all(r.result == ValidationResult.PASS for r in validation_results if r.required):
                raise Exception("Initial validation failed for canary deployment")

            # Phase 4: Gradual traffic shifting
            deployment.current_phase = DeploymentPhase.TRAFFIC_SHIFTING
            await self._log_deployment_event(
                deployment.deployment_id,
                "phase_started",
                DeploymentPhase.TRAFFIC_SHIFTING,
            )

            # Gradual traffic increase: 5% -> 25% -> 50% -> 100%
            traffic_steps = [0.05, 0.25, 0.50, 1.0]

            for _, traffic_percentage in enumerate(traffic_steps):
                await self.traffic_manager.update_traffic_split(
                    deployment.target_environment,
                    TrafficSplit(
                        version_weights={
                            deployment.source_version.version: 1.0 - traffic_percentage,
                            deployment.target_version.version: traffic_percentage,
                        }
                    ),
                )

                # Monitor each step
                await self._monitor_deployment_health(deployment, duration_seconds=300)

                # Run validation after each step
                step_validations = await self.validation_manager.run_validations(
                    deployment.validations, canary_environment
                )

                if not all(
                    r.result == ValidationResult.PASS for r in step_validations if r.required
                ):
                    raise Exception(f"Validation failed at {traffic_percentage * 100}% traffic")

                await self._log_deployment_event(
                    deployment.deployment_id,
                    "traffic_step_completed",
                    DeploymentPhase.TRAFFIC_SHIFTING,
                    {"traffic_percentage": traffic_percentage * 100},
                )

            # Phase 5: Final monitoring
            deployment.current_phase = DeploymentPhase.MONITORING
            await self._log_deployment_event(
                deployment.deployment_id, "phase_started", DeploymentPhase.MONITORING
            )

            await self._monitor_deployment_health(deployment, duration_seconds=600)

            # Phase 6: Completion
            deployment.current_phase = DeploymentPhase.COMPLETION
            deployment.status = DeploymentStatus.SUCCESS

            await self._log_deployment_event(
                deployment.deployment_id,
                "deployment_completed",
                DeploymentPhase.COMPLETION,
            )

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(e)
            raise

    async def _execute_rolling_deployment(self, deployment: "Deployment"):
        """Execute rolling deployment strategy."""
        deployment.status = DeploymentStatus.RUNNING
        deployment.current_phase = DeploymentPhase.DEPLOYMENT

        try:
            # Get current instances
            current_instances = await self.infrastructure_manager.get_service_instances(
                deployment.target_environment, deployment.source_version
            )

            # Calculate rolling update strategy
            max_unavailable = max(1, len(current_instances) // 4)  # 25% max unavailable
            max_surge = max(1, len(current_instances) // 2)  # 50% max surge

            await self._log_deployment_event(
                deployment.deployment_id,
                "rolling_strategy_calculated",
                DeploymentPhase.DEPLOYMENT,
                {
                    "total_instances": len(current_instances),
                    "max_unavailable": max_unavailable,
                    "max_surge": max_surge,
                },
            )

            # Execute rolling update
            for i in range(0, len(current_instances), max_unavailable):
                batch_instances = current_instances[i : i + max_unavailable]

                # Deploy new instances
                new_instances = await self.infrastructure_manager.deploy_instances(
                    deployment.target_environment,
                    deployment.target_version,
                    len(batch_instances),
                )

                # Wait for new instances to be ready
                await self.infrastructure_manager.wait_for_instances_ready(new_instances)

                # Remove old instances
                await self.infrastructure_manager.remove_instances(batch_instances)

                await self._log_deployment_event(
                    deployment.deployment_id,
                    "rolling_batch_completed",
                    DeploymentPhase.DEPLOYMENT,
                    {"batch_size": len(batch_instances)},
                )

            # Final validation
            deployment.current_phase = DeploymentPhase.VALIDATION
            validation_results = await self.validation_manager.run_validations(
                deployment.validations, deployment.target_environment
            )

            if not all(r.result == ValidationResult.PASS for r in validation_results if r.required):
                raise Exception("Final validation failed for rolling deployment")

            deployment.status = DeploymentStatus.SUCCESS
            deployment.current_phase = DeploymentPhase.COMPLETION

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(e)
            raise

    async def _execute_ab_test_deployment(self, deployment: "Deployment"):
        """Execute A/B test deployment strategy."""
        deployment.status = DeploymentStatus.RUNNING
        deployment.current_phase = DeploymentPhase.DEPLOYMENT

        try:
            # Deploy both versions in parallel
            await self.infrastructure_manager.deploy_parallel_versions(
                deployment.target_environment,
                [deployment.source_version, deployment.target_version],
            )

            # Set up A/B test traffic split
            ab_traffic_split = TrafficSplit(
                version_weights={
                    deployment.source_version.version: 0.5,  # Control group
                    deployment.target_version.version: 0.5,  # Test group
                },
                routing_rules=[{"type": "user_cohort", "field": "user_id", "hash_mod": 2}],
            )

            await self.traffic_manager.configure_ab_test(
                deployment.target_environment, ab_traffic_split
            )

            # Run A/B test for specified duration
            deployment.current_phase = DeploymentPhase.MONITORING
            test_duration = 24 * 3600  # Default 24 hours

            await self._monitor_ab_test(deployment, duration_seconds=test_duration)

            deployment.status = DeploymentStatus.SUCCESS
            deployment.current_phase = DeploymentPhase.COMPLETION

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(e)
            raise

    async def _execute_recreate_deployment(self, deployment: "Deployment"):
        """Execute recreate deployment strategy."""
        deployment.status = DeploymentStatus.RUNNING
        deployment.current_phase = DeploymentPhase.DEPLOYMENT

        try:
            # Stop all old instances
            await self.infrastructure_manager.stop_all_instances(
                deployment.target_environment, deployment.source_version
            )

            # Deploy new version
            environment = await self.infrastructure_manager.prepare_environment(
                deployment.target_environment,
                deployment.target_version,
                EnvironmentType.PRODUCTION,
            )

            await self.infrastructure_manager.deploy_service(environment, deployment.target_version)

            # Validation
            deployment.current_phase = DeploymentPhase.VALIDATION
            validation_results = await self.validation_manager.run_validations(
                deployment.validations, environment
            )

            if not all(r.result == ValidationResult.PASS for r in validation_results if r.required):
                raise Exception("Validation failed for recreate deployment")

            deployment.status = DeploymentStatus.SUCCESS
            deployment.current_phase = DeploymentPhase.COMPLETION

        except Exception as e:
            deployment.status = DeploymentStatus.FAILED
            deployment.error_message = str(e)
            raise

    async def rollback_deployment(self, deployment_id: str) -> bool:
        """Rollback a deployment."""
        if deployment_id not in self.active_deployments:
            return False

        deployment = self.active_deployments[deployment_id]
        return await self.rollback_manager.execute_rollback(deployment)

    async def _monitor_deployment_health(self, deployment: "Deployment", duration_seconds: int):
        """Monitor deployment health for a specific duration."""
        start_time = time.time()

        while (time.time() - start_time) < duration_seconds:
            # Check service health
            health_status = await self.infrastructure_manager.check_service_health(
                deployment.target_environment, deployment.target_version
            )

            if not health_status["healthy"]:
                raise Exception(f"Health check failed: {health_status.get('errors', [])}")

            # Check performance metrics
            metrics = await self.infrastructure_manager.get_performance_metrics(
                deployment.target_environment, deployment.target_version
            )

            # Check for concerning metrics
            if metrics["error_rate"] > 0.05:  # 5% error rate threshold
                raise Exception(f"High error rate: {metrics['error_rate']:.2%}")

            if metrics["response_time_p95"] > 2000:  # 2s response time threshold
                raise Exception(f"High response time: {metrics['response_time_p95']:.0f}ms")

            await asyncio.sleep(30)  # Check every 30 seconds

    async def _monitor_ab_test(self, deployment: "Deployment", duration_seconds: int):
        """Monitor A/B test deployment."""
        start_time = time.time()

        while (time.time() - start_time) < duration_seconds:
            # Collect metrics for both versions
            metrics = await self.infrastructure_manager.collect_ab_test_metrics(
                deployment.target_environment,
                [deployment.source_version.version, deployment.target_version.version],
            )

            # Log metrics
            await self._log_deployment_event(
                deployment.deployment_id,
                "ab_test_metrics",
                DeploymentPhase.MONITORING,
                metrics,
            )

            # Check for significant issues in either version
            for version, version_metrics in metrics.items():
                if version_metrics["error_rate"] > 0.1:  # 10% error rate threshold
                    raise Exception(
                        f"High error rate in version {version}: {version_metrics['error_rate']:.2%}"
                    )

            await asyncio.sleep(300)  # Check every 5 minutes

        # Determine winner based on metrics
        source_metrics = metrics[deployment.source_version.version]
        target_metrics = metrics[deployment.target_version.version]

        source_score = self._calculate_ab_test_score(source_metrics)
        target_score = self._calculate_ab_test_score(target_metrics)

        winner = (
            deployment.target_version.version
            if target_score > source_score
            else deployment.source_version.version
        )

        await self._log_deployment_event(
            deployment.deployment_id,
            "ab_test_winner",
            DeploymentPhase.MONITORING,
            {
                "winner": winner,
                "source_score": source_score,
                "target_score": target_score,
            },
        )

        # Route all traffic to winner
        if winner == deployment.target_version.version:
            await self.traffic_manager.switch_traffic(
                deployment.target_environment,
                from_version=deployment.source_version.version,
                to_version=deployment.target_version.version,
            )
        else:
            # Keep source version as active
            await self.traffic_manager.switch_traffic(
                deployment.target_environment,
                from_version=deployment.target_version.version,
                to_version=deployment.source_version.version,
            )

    def _calculate_ab_test_score(self, metrics: builtins.dict[str, Any]) -> float:
        """Calculate A/B test score based on metrics."""
        error_rate = metrics["error_rate"]
        response_time = metrics["avg_response_time"]
        throughput = metrics["requests_per_second"]
        conversion_rate = metrics["conversion_rate"]
        user_satisfaction = metrics["user_satisfaction"]

        # Weighted score calculation
        score = (
            (1 - error_rate) * 0.3
            + conversion_rate * 100 * 0.3
            + user_satisfaction / 5 * 0.2
            + (1000 / max(response_time, 1)) * 0.1
            + (throughput / 100) * 0.1
        )

        return score

    async def _log_deployment_event(
        self,
        deployment_id: str,
        event_type: str,
        phase: DeploymentPhase,
        details: builtins.dict[str, Any] | None = None,
    ):
        """Log deployment event."""
        event = DeploymentEvent(
            event_id=str(uuid.uuid4()),
            deployment_id=deployment_id,
            event_type=event_type,
            phase=phase,
            details=details or {},
        )

        self.deployment_events.append(event)
        logging.info(f"Deployment {deployment_id}: {event_type} in {phase.value}")

    def get_deployment_status(self, deployment_id: str) -> builtins.dict[str, Any] | None:
        """Get deployment status."""
        if deployment_id not in self.active_deployments:
            return None

        deployment = self.active_deployments[deployment_id]

        return {
            "deployment_id": deployment.deployment_id,
            "service_name": deployment.service_name,
            "strategy": deployment.strategy.value,
            "status": deployment.status.value,
            "current_phase": deployment.current_phase.value,
            "source_version": deployment.source_version.version,
            "target_version": deployment.target_version.version,
            "started_at": deployment.started_at.isoformat() if deployment.started_at else None,
            "completed_at": deployment.completed_at.isoformat()
            if deployment.completed_at
            else None,
            "error_message": deployment.error_message,
        }

    def get_all_deployments_status(self) -> builtins.dict[str, Any]:
        """Get status of all deployments."""
        active_deployments = {
            dep_id: self.get_deployment_status(dep_id) for dep_id in self.active_deployments
        }

        return {
            "active_deployments": active_deployments,
            "total_deployments": len(self.deployment_history),
            "recent_events": len(self.deployment_events),
        }


def create_deployment_orchestrator(service_name: str) -> DeploymentOrchestrator:
    """Create deployment orchestrator instance."""
    return DeploymentOrchestrator(service_name)
