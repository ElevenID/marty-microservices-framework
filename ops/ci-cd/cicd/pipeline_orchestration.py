"""
Pipeline Management and Orchestration

Provides centralized pipeline execution, monitoring, and coordination for CI/CD workflows.
Integrates with test execution, security scanning, quality gates, and deployment strategies.
"""

import asyncio
import builtins
import importlib.util
import os
import queue
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..deployment import DeploymentOrchestrator

# Local imports
from . import (
    ArtifactType,
    PipelineArtifact,
    PipelineDefinition,
    PipelineExecution,
    PipelineStage,
    PipelineStageDefinition,
    PipelineStatus,
    QualityGate,
    QualityGateEngine,
    SecurityScanConfiguration,
    SecurityScanner,
    SecurityScanType,
    TestConfiguration,
    TestRunner,
    TestType,
)

# External dependencies availability checks
DEPLOYMENT_AVAILABLE = importlib.util.find_spec("devops.deployment") is not None
KUBERNETES_AVAILABLE = importlib.util.find_spec("kubernetes") is not None


@dataclass
class PipelineMetrics:
    """Pipeline execution metrics"""

    execution_id: str
    pipeline_name: str

    # Timing metrics
    total_duration: float = 0.0
    stage_durations: builtins.dict[str, float] = field(default_factory=dict)
    queue_time: float = 0.0

    # Success metrics
    success_rate: float = 0.0
    test_success_rate: float = 0.0

    # Quality metrics
    code_coverage: float = 0.0
    security_score: float = 0.0
    quality_gate_score: float = 0.0

    # Resource metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0

    # Artifact metrics
    artifact_count: int = 0
    artifact_size_mb: float = 0.0


class PipelineOrchestrator:
    """
    Central pipeline orchestration engine

    Features:
    - Pipeline definition management
    - Stage execution coordination
    - Parallel stage execution
    - Dependency resolution
    - Artifact management
    - Integration with deployment strategies
    """

    def __init__(self, workspace_path: str = "."):
        self.workspace_path = workspace_path

        # Component instances
        self.test_runner = TestRunner()
        self.security_scanner = SecurityScanner()
        self.quality_gate_engine = QualityGateEngine()

        if DEPLOYMENT_AVAILABLE:
            self.deployment_orchestrator = DeploymentOrchestrator()
        else:
            self.deployment_orchestrator = None

        # Pipeline state
        self.pipelines: builtins.dict[str, PipelineDefinition] = {}
        self.executions: builtins.dict[str, PipelineExecution] = {}
        self.artifacts: builtins.dict[str, builtins.list[PipelineArtifact]] = {}

        # Execution queue
        self.execution_queue = queue.Queue()
        self.execution_threads: builtins.dict[str, threading.Thread] = {}

        # Metrics
        self.metrics: builtins.dict[str, PipelineMetrics] = {}

        print("🚀 Pipeline Orchestrator initialized")

    def register_pipeline(self, pipeline_definition: PipelineDefinition):
        """Register a pipeline definition"""

        # Validate pipeline definition
        self._validate_pipeline_definition(pipeline_definition)

        # Store pipeline
        self.pipelines[pipeline_definition.name] = pipeline_definition

        print(f"📋 Registered pipeline: {pipeline_definition.name}")

    def _validate_pipeline_definition(self, pipeline: PipelineDefinition):
        """Validate pipeline definition"""

        if not pipeline.name:
            raise ValueError("Pipeline name is required")

        if not pipeline.stages:
            raise ValueError("Pipeline must have at least one stage")

        # Validate stage dependencies
        stage_names = {stage.name for stage in pipeline.stages}

        for stage in pipeline.stages:
            for dependency in stage.depends_on:
                if dependency not in stage_names:
                    raise ValueError(
                        f"Stage '{stage.name}' depends on unknown stage '{dependency}'"
                    )

        # Check for circular dependencies
        self._check_circular_dependencies(pipeline.stages)

        print(f"✅ Pipeline validation passed: {pipeline.name}")

    def _check_circular_dependencies(self, stages: builtins.list[PipelineStageDefinition]):
        """Check for circular dependencies in stage definitions"""

        def has_circular_dependency(stage_name: str, visited: set, path: set) -> bool:
            if stage_name in path:
                return True
            if stage_name in visited:
                return False

            visited.add(stage_name)
            path.add(stage_name)

            # Find stage by name
            stage = next((s for s in stages if s.name == stage_name), None)
            if stage:
                for dependency in stage.depends_on:
                    if has_circular_dependency(dependency, visited, path):
                        return True

            path.remove(stage_name)
            return False

        visited = set()
        for stage in stages:
            if stage.name not in visited:
                if has_circular_dependency(stage.name, visited, set()):
                    raise ValueError(f"Circular dependency detected involving stage: {stage.name}")

    async def execute_pipeline(
        self,
        pipeline_name: str,
        trigger_type: str = "manual",
        trigger_source: str = "",
        commit_sha: str = "",
        branch: str = "main",
        environment_overrides: builtins.dict[str, str] | None = None,
    ) -> str:
        """Execute a pipeline"""

        if pipeline_name not in self.pipelines:
            raise ValueError(f"Pipeline not found: {pipeline_name}")

        pipeline_definition = self.pipelines[pipeline_name]
        execution_id = f"{pipeline_name}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"

        # Create execution record
        execution = PipelineExecution(
            execution_id=execution_id,
            pipeline_name=pipeline_name,
            started_at=datetime.now(),
            trigger_type=trigger_type,
            trigger_source=trigger_source,
            commit_sha=commit_sha,
            branch=branch,
            status=PipelineStatus.PENDING,
        )

        self.executions[execution_id] = execution

        # Initialize metrics
        self.metrics[execution_id] = PipelineMetrics(
            execution_id=execution_id, pipeline_name=pipeline_name
        )

        print(f"🎬 Starting pipeline execution: {execution_id}")

        # Execute pipeline asynchronously
        try:
            await self._execute_pipeline_stages(
                execution, pipeline_definition, environment_overrides
            )
        except Exception as e:
            execution.status = PipelineStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now()
            execution.duration = (execution.completed_at - execution.started_at).total_seconds()
            print(f"❌ Pipeline execution failed: {execution_id} - {e}")

        return execution_id

    async def _execute_pipeline_stages(
        self,
        execution: PipelineExecution,
        pipeline: PipelineDefinition,
        environment_overrides: builtins.dict[str, str] | None = None,
    ):
        """Execute pipeline stages with dependency resolution"""

        execution.status = PipelineStatus.RUNNING
        datetime.now()

        # Build dependency graph
        self._build_dependency_graph(pipeline.stages)

        # Execute stages in dependency order
        completed_stages = set()
        failed_stages = set()

        while len(completed_stages) < len(pipeline.stages):
            # Find stages ready to execute
            ready_stages = []

            for stage in pipeline.stages:
                if (
                    stage.name not in completed_stages
                    and stage.name not in failed_stages
                    and stage.enabled
                    and all(dep in completed_stages for dep in stage.depends_on)
                ):
                    ready_stages.append(stage)

            if not ready_stages:
                # Check if any stages are still pending
                pending_stages = [
                    s
                    for s in pipeline.stages
                    if s.name not in completed_stages and s.name not in failed_stages
                ]

                if pending_stages:
                    # Dependency deadlock or all remaining stages have failed dependencies
                    execution.status = PipelineStatus.FAILED
                    execution.error_message = "Pipeline deadlock: no stages ready to execute"
                    break
                # All stages completed
                break

            # Execute ready stages in parallel
            stage_tasks = []
            for stage in ready_stages:
                task = self._execute_stage(execution, stage, pipeline, environment_overrides)
                stage_tasks.append((stage.name, task))

            # Wait for stage completion
            for stage_name, task in stage_tasks:
                try:
                    stage_result = await task

                    if stage_result["status"] == "success":
                        completed_stages.add(stage_name)
                        execution.completed_stages.append(stage_name)
                        print(f"✅ Stage completed: {stage_name}")
                    elif stage_result["status"] == "skipped":
                        execution.skipped_stages.append(stage_name)
                        completed_stages.add(
                            stage_name
                        )  # Treat skipped as completed for dependencies
                        print(f"⏭️ Stage skipped: {stage_name}")
                    else:
                        failed_stages.add(stage_name)
                        execution.failed_stages.append(stage_name)
                        print(f"❌ Stage failed: {stage_name}")

                        # Check if stage failure should stop pipeline
                        stage_def = next(s for s in pipeline.stages if s.name == stage_name)
                        if not stage_def.allow_failure:
                            execution.status = PipelineStatus.FAILED
                            execution.error_message = f"Stage failed: {stage_name}"
                            break

                except Exception as e:
                    failed_stages.add(stage_name)
                    execution.failed_stages.append(stage_name)
                    print(f"❌ Stage error: {stage_name} - {e}")

                    # Check if stage failure should stop pipeline
                    stage_def = next(s for s in pipeline.stages if s.name == stage_name)
                    if not stage_def.allow_failure:
                        execution.status = PipelineStatus.FAILED
                        execution.error_message = f"Stage error: {stage_name} - {e}"
                        break

            # Break if pipeline failed
            if execution.status == PipelineStatus.FAILED:
                break

        # Final pipeline status
        if execution.status != PipelineStatus.FAILED:
            if failed_stages and not all(
                next(s for s in pipeline.stages if s.name == name).allow_failure
                for name in failed_stages
            ):
                execution.status = PipelineStatus.FAILED
            else:
                execution.status = PipelineStatus.SUCCEEDED

        # Complete execution
        execution.completed_at = datetime.now()
        execution.duration = (execution.completed_at - execution.started_at).total_seconds()

        # Update metrics
        metrics = self.metrics[execution.execution_id]
        metrics.total_duration = execution.duration
        metrics.success_rate = 1.0 if execution.status == PipelineStatus.SUCCEEDED else 0.0

        print(
            f"🏁 Pipeline execution completed: {execution.execution_id} - {execution.status.value}"
        )

    def _build_dependency_graph(
        self, stages: builtins.list[PipelineStageDefinition]
    ) -> builtins.dict[str, builtins.list[str]]:
        """Build stage dependency graph"""

        graph = {}
        for stage in stages:
            graph[stage.name] = stage.depends_on.copy()

        return graph

    async def _execute_stage(
        self,
        execution: PipelineExecution,
        stage: PipelineStageDefinition,
        pipeline: PipelineDefinition,
        environment_overrides: builtins.dict[str, str] | None = None,
    ) -> builtins.dict[str, Any]:
        """Execute a single pipeline stage"""

        stage_start = datetime.now()
        execution.current_stage = stage.name

        print(f"🔄 Executing stage: {stage.name} ({stage.stage_type.value})")

        # Check stage conditions
        if not self._evaluate_stage_conditions(stage, execution):
            return {"status": "skipped", "message": "Stage conditions not met"}

        # Set up environment
        stage_env = pipeline.environment_variables.copy()
        stage_env.update(stage.environment)
        if environment_overrides:
            stage_env.update(environment_overrides)

        # Execute stage based on type
        try:
            if stage.stage_type == PipelineStage.TEST:
                result = await self._execute_test_stage(execution, stage)
            elif stage.stage_type == PipelineStage.SECURITY_SCAN:
                result = await self._execute_security_stage(execution, stage)
            elif stage.stage_type == PipelineStage.QUALITY_GATE:
                result = await self._execute_quality_gate_stage(execution, stage)
            elif stage.stage_type == PipelineStage.BUILD:
                result = await self._execute_build_stage(execution, stage, stage_env)
            elif stage.stage_type == PipelineStage.PACKAGE:
                result = await self._execute_package_stage(execution, stage, stage_env)
            elif stage.stage_type == PipelineStage.DEPLOY:
                result = await self._execute_deploy_stage(execution, stage, pipeline)
            else:
                result = await self._execute_custom_stage(execution, stage, stage_env)

            # Update stage duration
            stage_end = datetime.now()
            stage_duration = (stage_end - stage_start).total_seconds()
            self.metrics[execution.execution_id].stage_durations[stage.name] = stage_duration

            return result

        except asyncio.TimeoutError:
            return {
                "status": "failed",
                "message": f"Stage timed out after {stage.timeout} seconds",
            }
        except Exception as e:
            return {"status": "failed", "message": str(e)}

    def _evaluate_stage_conditions(
        self, stage: PipelineStageDefinition, execution: PipelineExecution
    ) -> bool:
        """Evaluate stage execution conditions"""

        if not stage.conditions:
            return True

        # Simple condition evaluation
        for condition in stage.conditions:
            if condition == "always":
                continue
            if (condition == "on_success" and execution.failed_stages) or (
                condition == "on_failure" and not execution.failed_stages
            ):
                return False
            if condition.startswith("branch:"):
                required_branch = condition.split(":", 1)[1]
                if execution.branch != required_branch:
                    return False
            elif condition.startswith("env:"):
                env_check = condition.split(":", 1)[1]
                env_var, expected_value = env_check.split("=", 1)
                if os.environ.get(env_var) != expected_value:
                    return False

        return True

    async def _execute_test_stage(
        self, execution: PipelineExecution, stage: PipelineStageDefinition
    ) -> builtins.dict[str, Any]:
        """Execute test stage"""

        if not stage.test_config:
            return {"status": "failed", "message": "No test configuration provided"}

        test_result = await self.test_runner.execute_tests(
            execution.execution_id, stage.test_config
        )

        # Store test results
        execution.test_results[stage.name] = test_result

        # Update metrics
        metrics = self.metrics[execution.execution_id]
        if "coverage_percentage" in test_result:
            metrics.code_coverage = max(metrics.code_coverage, test_result["coverage_percentage"])

        if test_result["status"] in ["passed", "completed"]:
            return {"status": "success", "message": "Tests passed"}
        return {
            "status": "failed",
            "message": test_result.get("error_message", "Tests failed"),
        }

    async def _execute_security_stage(
        self, execution: PipelineExecution, stage: PipelineStageDefinition
    ) -> builtins.dict[str, Any]:
        """Execute security scan stage"""

        if not stage.security_scan_config:
            return {
                "status": "failed",
                "message": "No security scan configuration provided",
            }

        scan_result = await self.security_scanner.execute_security_scan(
            execution.execution_id, stage.security_scan_config
        )

        # Store security results
        execution.security_results[stage.name] = scan_result

        if scan_result["status"] in ["completed"]:
            return {"status": "success", "message": "Security scan completed"}
        return {
            "status": "failed",
            "message": scan_result.get("error_message", "Security scan failed"),
        }

    async def _execute_quality_gate_stage(
        self, execution: PipelineExecution, stage: PipelineStageDefinition
    ) -> builtins.dict[str, Any]:
        """Execute quality gate stage"""

        if not stage.quality_gate:
            return {
                "status": "failed",
                "message": "No quality gate configuration provided",
            }

        # Prepare execution context
        execution_context = {
            "test_results": execution.test_results,
            "security_results": execution.security_results,
            "build_duration": execution.duration or 0.0,
        }

        quality_result = await self.quality_gate_engine.evaluate_quality_gate(
            execution.execution_id, stage.quality_gate, execution_context
        )

        # Store quality results
        execution.quality_results[stage.name] = quality_result

        # Update metrics
        metrics = self.metrics[execution.execution_id]
        metrics.quality_gate_score = quality_result["overall_score"]

        if quality_result["status"] == "passed":
            return {"status": "success", "message": "Quality gate passed"}
        if quality_result["status"] == "warning":
            return {"status": "success", "message": "Quality gate passed with warnings"}
        if quality_result["status"] == "manual_approval_required":
            return {"status": "manual_approval", "message": "Manual approval required"}
        return {"status": "failed", "message": "Quality gate failed"}

    async def _execute_build_stage(
        self,
        execution: PipelineExecution,
        stage: PipelineStageDefinition,
        environment: builtins.dict[str, str],
    ) -> builtins.dict[str, Any]:
        """Execute build stage"""

        if not stage.commands:
            return {"status": "failed", "message": "No build commands provided"}

        # Execute build commands
        for command in stage.commands:
            result = await self._execute_command(
                command, stage.working_directory, environment, stage.timeout
            )

            if result["returncode"] != 0:
                return {
                    "status": "failed",
                    "message": f"Build command failed: {command}",
                    "output": result["stderr"],
                }

        # Create build artifacts
        build_artifact = PipelineArtifact(
            name=f"build_{execution.execution_id}",
            artifact_type=ArtifactType.BINARY,
            version=execution.commit_sha[:8] if execution.commit_sha else "latest",
            created_at=datetime.now(),
            tags={"stage": stage.name, "execution_id": execution.execution_id},
        )

        execution.artifacts.append(build_artifact)

        return {"status": "success", "message": "Build completed successfully"}

    async def _execute_package_stage(
        self,
        execution: PipelineExecution,
        stage: PipelineStageDefinition,
        environment: builtins.dict[str, str],
    ) -> builtins.dict[str, Any]:
        """Execute package stage"""

        if not stage.commands:
            # Default container packaging
            image_tag = f"{execution.pipeline_name}:{execution.commit_sha[:8] if execution.commit_sha else 'latest'}"
            commands = [f"docker build -t {image_tag} ."]
        else:
            commands = stage.commands

        # Execute packaging commands
        for command in commands:
            result = await self._execute_command(
                command, stage.working_directory, environment, stage.timeout
            )

            if result["returncode"] != 0:
                return {
                    "status": "failed",
                    "message": f"Package command failed: {command}",
                    "output": result["stderr"],
                }

        # Create container artifact
        container_artifact = PipelineArtifact(
            name=f"{execution.pipeline_name}_container",
            artifact_type=ArtifactType.CONTAINER_IMAGE,
            version=execution.commit_sha[:8] if execution.commit_sha else "latest",
            created_at=datetime.now(),
            tags={"stage": stage.name, "execution_id": execution.execution_id},
        )

        execution.artifacts.append(container_artifact)

        return {"status": "success", "message": "Packaging completed successfully"}

    async def _execute_deploy_stage(
        self,
        execution: PipelineExecution,
        stage: PipelineStageDefinition,
        pipeline: PipelineDefinition,
    ) -> builtins.dict[str, Any]:
        """Execute deployment stage"""

        if not DEPLOYMENT_AVAILABLE or not self.deployment_orchestrator:
            return {
                "status": "skipped",
                "message": "Deployment orchestrator not available",
            }

        try:
            # Get deployment strategy from pipeline configuration
            strategy_name = pipeline.deployment_strategy or "rolling"

            # Find container artifacts for deployment
            container_artifacts = [
                artifact
                for artifact in execution.artifacts
                if artifact.artifact_type == ArtifactType.CONTAINER_IMAGE
            ]

            if not container_artifacts:
                return {
                    "status": "failed",
                    "message": "No container artifacts found for deployment",
                }

            # Deploy using orchestrator
            deployment_config = {
                "service_name": execution.pipeline_name,
                "image": f"{container_artifacts[0].name}:{container_artifacts[0].version}",
                "replicas": 3,
                "environment": "staging",  # Would be configurable
            }

            deployment_result = await self.deployment_orchestrator.deploy_service(
                deployment_config, strategy_name
            )

            if deployment_result["status"] == "success":
                return {
                    "status": "success",
                    "message": "Deployment completed successfully",
                }
            return {
                "status": "failed",
                "message": deployment_result.get("message", "Deployment failed"),
            }

        except Exception as e:
            return {"status": "failed", "message": f"Deployment error: {e}"}

    async def _execute_custom_stage(
        self,
        execution: PipelineExecution,
        stage: PipelineStageDefinition,
        environment: builtins.dict[str, str],
    ) -> builtins.dict[str, Any]:
        """Execute custom stage with commands"""

        if not stage.commands:
            return {"status": "success", "message": "No commands to execute"}

        # Execute all commands in sequence
        for command in stage.commands:
            result = await self._execute_command(
                command, stage.working_directory, environment, stage.timeout
            )

            if result["returncode"] != 0:
                return {
                    "status": "failed",
                    "message": f"Command failed: {command}",
                    "output": result["stderr"],
                }

        return {"status": "success", "message": "Custom stage completed successfully"}

    async def _execute_command(
        self,
        command: str,
        working_directory: str,
        environment: builtins.dict[str, str],
        timeout: int,
    ) -> builtins.dict[str, Any]:
        """Execute shell command"""

        try:
            # Set up environment
            env = os.environ.copy()
            env.update(environment)

            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=working_directory,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                return {"returncode": -1, "stdout": "", "stderr": "Command timed out"}

            return {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
            }

        except Exception as e:
            return {"returncode": -1, "stdout": "", "stderr": str(e)}

    def get_execution_status(self, execution_id: str) -> builtins.dict[str, Any] | None:
        """Get pipeline execution status"""

        if execution_id not in self.executions:
            return None

        execution = self.executions[execution_id]
        metrics = self.metrics.get(execution_id)

        return {
            "execution": execution.to_dict(),
            "metrics": asdict(metrics) if metrics else None,
        }

    def list_executions(
        self,
        pipeline_name: str | None = None,
        status: PipelineStatus | None = None,
        limit: int = 50,
    ) -> builtins.list[builtins.dict[str, Any]]:
        """List pipeline executions with filtering"""

        executions = list(self.executions.values())

        # Apply filters
        if pipeline_name:
            executions = [e for e in executions if e.pipeline_name == pipeline_name]

        if status:
            executions = [e for e in executions if e.status == status]

        # Sort by start time (newest first)
        executions.sort(key=lambda e: e.started_at, reverse=True)

        # Limit results
        executions = executions[:limit]

        # Convert to dict format
        return [execution.to_dict() for execution in executions]

    def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running pipeline execution"""

        if execution_id not in self.executions:
            return False

        execution = self.executions[execution_id]

        if execution.status not in [PipelineStatus.PENDING, PipelineStatus.RUNNING]:
            return False

        execution.status = PipelineStatus.CANCELLED
        execution.completed_at = datetime.now()
        execution.duration = (execution.completed_at - execution.started_at).total_seconds()

        print(f"🛑 Pipeline execution cancelled: {execution_id}")
        return True

    def get_pipeline_metrics(self, pipeline_name: str, days: int = 30) -> builtins.dict[str, Any]:
        """Get aggregated pipeline metrics"""

        # Filter executions for the pipeline within time range
        cutoff_date = datetime.now() - timedelta(days=days)
        relevant_executions = [
            execution
            for execution in self.executions.values()
            if (execution.pipeline_name == pipeline_name and execution.started_at >= cutoff_date)
        ]

        if not relevant_executions:
            return {
                "pipeline_name": pipeline_name,
                "period_days": days,
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "avg_queue_time": 0.0,
            }

        # Calculate metrics
        total_executions = len(relevant_executions)
        successful_executions = len(
            [e for e in relevant_executions if e.status == PipelineStatus.SUCCEEDED]
        )
        success_rate = successful_executions / total_executions

        # Duration metrics
        completed_executions = [e for e in relevant_executions if e.duration is not None]
        avg_duration = (
            sum(e.duration for e in completed_executions if e.duration is not None)
            / len(completed_executions)
            if completed_executions
            else 0.0
        )

        # Quality metrics
        avg_coverage = 0.0
        avg_security_score = 0.0
        coverage_values = []
        security_scores = []

        for execution in relevant_executions:
            execution_metrics = self.metrics.get(execution.execution_id)
            if execution_metrics:
                if execution_metrics.code_coverage > 0:
                    coverage_values.append(execution_metrics.code_coverage)
                if execution_metrics.security_score > 0:
                    security_scores.append(execution_metrics.security_score)

        if coverage_values:
            avg_coverage = sum(coverage_values) / len(coverage_values)
        if security_scores:
            avg_security_score = sum(security_scores) / len(security_scores)

        return {
            "pipeline_name": pipeline_name,
            "period_days": days,
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": total_executions - successful_executions,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
            "avg_coverage": avg_coverage,
            "avg_security_score": avg_security_score,
            "recent_executions": [e.to_dict() for e in relevant_executions[-5:]],
        }


class PipelineConfigurationBuilder:
    """
    Builder for creating pipeline configurations

    Provides fluent API for constructing complex pipeline definitions
    """

    def __init__(self, name: str, description: str = ""):
        self.pipeline = PipelineDefinition(name=name, description=description)

    def trigger_on(self, *triggers: str) -> "PipelineConfigurationBuilder":
        """Set pipeline triggers"""
        self.pipeline.triggers.extend(triggers)
        return self

    def for_branches(self, *branches: str) -> "PipelineConfigurationBuilder":
        """Set target branches"""
        self.pipeline.branches.extend(branches)
        return self

    def with_timeout(self, timeout: int) -> "PipelineConfigurationBuilder":
        """Set pipeline timeout"""
        self.pipeline.timeout = timeout
        return self

    def with_environment(self, **env_vars) -> "PipelineConfigurationBuilder":
        """Add environment variables"""
        self.pipeline.environment_variables.update(env_vars)
        return self

    def add_stage(
        self, name: str, stage_type: PipelineStage, **kwargs
    ) -> "PipelineConfigurationBuilder":
        """Add a pipeline stage"""

        stage = PipelineStageDefinition(name=name, stage_type=stage_type, **kwargs)

        self.pipeline.stages.append(stage)
        return self

    def add_test_stage(
        self, name: str, test_config: TestConfiguration, **kwargs
    ) -> "PipelineConfigurationBuilder":
        """Add test stage"""

        return self.add_stage(
            name=name, stage_type=PipelineStage.TEST, test_config=test_config, **kwargs
        )

    def add_security_stage(
        self, name: str, scan_config: SecurityScanConfiguration, **kwargs
    ) -> "PipelineConfigurationBuilder":
        """Add security scan stage"""

        return self.add_stage(
            name=name,
            stage_type=PipelineStage.SECURITY_SCAN,
            security_scan_config=scan_config,
            **kwargs,
        )

    def add_quality_gate(
        self, name: str, quality_gate: QualityGate, **kwargs
    ) -> "PipelineConfigurationBuilder":
        """Add quality gate stage"""

        return self.add_stage(
            name=name,
            stage_type=PipelineStage.QUALITY_GATE,
            quality_gate=quality_gate,
            **kwargs,
        )

    def add_build_stage(
        self, name: str, commands: builtins.list[str], **kwargs
    ) -> "PipelineConfigurationBuilder":
        """Add build stage"""

        return self.add_stage(
            name=name, stage_type=PipelineStage.BUILD, commands=commands, **kwargs
        )

    def add_deploy_stage(
        self, name: str, depends_on: builtins.list[str], **kwargs
    ) -> "PipelineConfigurationBuilder":
        """Add deployment stage"""

        return self.add_stage(
            name=name, stage_type=PipelineStage.DEPLOY, depends_on=depends_on, **kwargs
        )

    def build(self) -> PipelineDefinition:
        """Build the pipeline definition"""
        return self.pipeline


# Example usage and demo
async def demo_pipeline_orchestration():
    """Demonstration of pipeline orchestration"""

    print("=== Pipeline Orchestration Demo ===")

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator()

    # Build a comprehensive pipeline using the builder
    pipeline = (
        PipelineConfigurationBuilder(
            "microservice_ci_cd", "Complete CI/CD pipeline for microservices"
        )
        .trigger_on("push", "pull_request")
        .for_branches("main", "develop", "feature/*")
        .with_timeout(3600)
        .with_environment(CI="true", NODE_ENV="test", DOCKER_BUILDKIT="1")
        # Source stage
        .add_stage("checkout", PipelineStage.SOURCE, commands=["git checkout ${BRANCH}"])
        # Build stage
        .add_build_stage(
            "build",
            commands=[
                "npm install",
                "npm run build",
                "docker build -t app:${COMMIT_SHA} .",
            ],
            depends_on=["checkout"],
            timeout=600,
        )
        # Test stages (parallel)
        .add_test_stage(
            "unit_tests",
            TestConfiguration(
                name="unit_tests",
                test_type=TestType.UNIT,
                framework="jest",
                parallel_enabled=True,
                coverage_enabled=True,
                coverage_threshold=0.8,
            ),
            depends_on=["build"],
        )
        .add_test_stage(
            "integration_tests",
            TestConfiguration(
                name="integration_tests",
                test_type=TestType.INTEGRATION,
                framework="jest",
                timeout=900,
            ),
            depends_on=["build"],
        )
        # Security scans (parallel)
        .add_security_stage(
            "sast_scan",
            SecurityScanConfiguration(
                name="sast_scan",
                scan_type=SecurityScanType.SAST,
                scanner_tool="semgrep",
                fail_on_critical=True,
            ),
            depends_on=["build"],
        )
        .add_security_stage(
            "dependency_scan",
            SecurityScanConfiguration(
                name="dependency_scan",
                scan_type=SecurityScanType.DEPENDENCY,
                scanner_tool="snyk",
                fail_on_critical=True,
                max_vulnerabilities=5,
            ),
            depends_on=["build"],
        )
        # Package stage
        .add_stage(
            "package",
            PipelineStage.PACKAGE,
            commands=["docker push app:${COMMIT_SHA}"],
            depends_on=[
                "unit_tests",
                "integration_tests",
                "sast_scan",
                "dependency_scan",
            ],
        )
        # Quality gate
        .add_quality_gate(
            "quality_gate",
            QualityGate(
                name="release_quality_gate",
                code_coverage_threshold=0.8,
                test_success_rate_threshold=1.0,
                security_score_threshold=0.9,
                blocking=True,
            ),
            depends_on=["package"],
        )
        # Deployment stages
        .add_deploy_stage("deploy_staging", depends_on=["quality_gate"])
        .add_test_stage(
            "e2e_tests",
            TestConfiguration(
                name="e2e_tests",
                test_type=TestType.E2E,
                framework="cypress",
                timeout=1200,
            ),
            depends_on=["deploy_staging"],
        )
        .add_deploy_stage("deploy_production", depends_on=["e2e_tests"], conditions=["branch:main"])
        .build()
    )

    # Register pipeline
    orchestrator.register_pipeline(pipeline)

    # Execute pipeline
    execution_id = await orchestrator.execute_pipeline(
        "microservice_ci_cd",
        trigger_type="push",
        commit_sha="abc123def456",
        branch="main",
    )

    print("\n📊 Pipeline Execution Results")

    # Get execution status
    execution_status = orchestrator.get_execution_status(execution_id)
    if execution_status:
        execution = execution_status["execution"]
        print(f"Status: {execution['status']}")
        print(f"Duration: {execution['duration']:.1f}s")
        print(f"Completed stages: {len(execution['completed_stages'])}")
        print(f"Failed stages: {len(execution['failed_stages'])}")
        print(f"Artifacts: {len(execution['artifacts'])}")

    # Get pipeline metrics
    metrics = orchestrator.get_pipeline_metrics("microservice_ci_cd")
    print("\n📈 Pipeline Metrics")
    print(f"Success rate: {metrics['success_rate']:.1%}")
    print(f"Average duration: {metrics['avg_duration']:.1f}s")
    print(f"Average coverage: {metrics['avg_coverage']:.1%}")

    return orchestrator


if __name__ == "__main__":
    asyncio.run(demo_pipeline_orchestration())
