"""
Enhanced Workflow Engine with DSL Support

This module provides a comprehensive workflow engine that supports:
- Saga orchestration patterns
- Compensating transactions
- Long-running business processes
- Declarative workflow DSL
- State persistence and recovery
- Timeout and retry handling
- Event-driven workflow execution
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Union

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    and_,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base

from ..events.enhanced_event_bus import BaseEvent, EventBus, EventHandler
from ..events.enhanced_events import create_workflow_event

logger = logging.getLogger(__name__)

# Base for workflow persistence
WorkflowBase = declarative_base()


class WorkflowStatus(Enum):
    """Workflow execution status."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


class StepStatus(Enum):
    """Individual step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    COMPENSATED = "compensated"


class StepType(Enum):
    """Types of workflow steps."""
    ACTION = "action"
    DECISION = "decision"
    PARALLEL = "parallel"
    LOOP = "loop"
    WAIT = "wait"
    COMPENSATION = "compensation"


@dataclass
class StepResult:
    """Result of step execution."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    should_retry: bool = False
    retry_delay: timedelta | None = None


@dataclass
class WorkflowContext:
    """Workflow execution context."""
    workflow_id: str
    data: dict[str, Any] = field(default_factory=dict)
    step_results: dict[str, StepResult] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None


class WorkflowStep(ABC):
    """Abstract base class for workflow steps."""

    def __init__(
        self,
        step_id: str,
        name: str,
        step_type: StepType,
        timeout: timedelta | None = None,
        retry_count: int = 0,
        retry_delay: timedelta | None = None,
        compensation_step: WorkflowStep | None = None,
        condition: Callable[[WorkflowContext], bool] | None = None
    ):
        self.step_id = step_id
        self.name = name
        self.step_type = step_type
        self.timeout = timeout or timedelta(minutes=30)
        self.retry_count = retry_count
        self.retry_delay = retry_delay or timedelta(seconds=30)
        self.compensation_step = compensation_step
        self.condition = condition
        self.status = StepStatus.PENDING

    @abstractmethod
    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute the workflow step."""
        ...

    async def compensate(self, context: WorkflowContext) -> StepResult:
        """Execute compensation logic."""
        if self.compensation_step:
            return await self.compensation_step.execute(context)
        return StepResult(success=True)

    def should_execute(self, context: WorkflowContext) -> bool:
        """Check if step should be executed based on condition."""
        if self.condition is None:
            return True
        return self.condition(context)


class ActionStep(WorkflowStep):
    """Step that executes a specific action."""

    def __init__(
        self,
        step_id: str,
        name: str,
        action: Callable[[WorkflowContext], Any],
        **kwargs
    ):
        super().__init__(step_id, name, StepType.ACTION, **kwargs)
        self.action = action

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute the action."""
        try:
            if asyncio.iscoroutinefunction(self.action):
                result = await self.action(context)
            else:
                result = self.action(context)

            return StepResult(
                success=True,
                data={"result": result} if result is not None else {}
            )
        except Exception as e:
            logger.error(f"Action step {self.step_id} failed: {e}")
            return StepResult(
                success=False,
                error=str(e),
                should_retry=self.retry_count > 0
            )


class DecisionStep(WorkflowStep):
    """Step that makes a decision based on context."""

    def __init__(
        self,
        step_id: str,
        name: str,
        decision_logic: Callable[[WorkflowContext], str],
        branches: dict[str, list[WorkflowStep]],
        **kwargs
    ):
        super().__init__(step_id, name, StepType.DECISION, **kwargs)
        self.decision_logic = decision_logic
        self.branches = branches

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute decision logic."""
        try:
            branch = self.decision_logic(context)
            return StepResult(
                success=True,
                data={"branch": branch}
            )
        except Exception as e:
            logger.error(f"Decision step {self.step_id} failed: {e}")
            return StepResult(success=False, error=str(e))


class ParallelStep(WorkflowStep):
    """Step that executes multiple steps in parallel."""

    def __init__(
        self,
        step_id: str,
        name: str,
        parallel_steps: list[WorkflowStep],
        wait_for_all: bool = True,
        **kwargs
    ):
        super().__init__(step_id, name, StepType.PARALLEL, **kwargs)
        self.parallel_steps = parallel_steps
        self.wait_for_all = wait_for_all

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute parallel steps."""
        tasks = []
        for step in self.parallel_steps:
            if step.should_execute(context):
                tasks.append(self._execute_step(step, context))

        if not tasks:
            return StepResult(success=True)

        try:
            if self.wait_for_all:
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                results = [task.result() for task in done]

            # Aggregate results
            all_success = all(
                isinstance(r, StepResult) and r.success
                for r in results if not isinstance(r, Exception)
            )

            return StepResult(
                success=all_success,
                data={"parallel_results": results}
            )
        except Exception as e:
            logger.error(f"Parallel step {self.step_id} failed: {e}")
            return StepResult(success=False, error=str(e))

    async def _execute_step(self, step: WorkflowStep, context: WorkflowContext) -> StepResult:
        """Execute a single step within parallel execution."""
        return await step.execute(context)


class WaitStep(WorkflowStep):
    """Step that waits for a specific duration or condition."""

    def __init__(
        self,
        step_id: str,
        name: str,
        wait_duration: timedelta | None = None,
        wait_condition: Callable[[WorkflowContext], bool] | None = None,
        check_interval: timedelta | None = None,
        **kwargs
    ):
        super().__init__(step_id, name, StepType.WAIT, **kwargs)
        self.wait_duration = wait_duration
        self.wait_condition = wait_condition
        self.check_interval = check_interval or timedelta(seconds=10)

    async def execute(self, context: WorkflowContext) -> StepResult:
        """Execute wait logic."""
        if self.wait_duration:
            await asyncio.sleep(self.wait_duration.total_seconds())
            return StepResult(success=True)

        if self.wait_condition:
            start_time = datetime.now(timezone.utc)
            while True:
                if self.wait_condition(context):
                    return StepResult(success=True)

                # Check timeout
                if (datetime.now(timezone.utc) - start_time) > self.timeout:
                    return StepResult(success=False, error="Wait condition timeout")

                await asyncio.sleep(self.check_interval.total_seconds())

        return StepResult(success=True)


# Persistence models
class WorkflowInstance(WorkflowBase):
    """Workflow instance persistence model."""

    __tablename__ = "workflow_instances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(255), nullable=False, unique=True, index=True)
    workflow_type = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, default=WorkflowStatus.CREATED.value, index=True)
    context_data = Column(Text, nullable=False)
    current_step = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    tenant_id = Column(String(255), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)


class WorkflowStepExecution(WorkflowBase):
    """Step execution history."""

    __tablename__ = "workflow_step_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id = Column(String(255), nullable=False, index=True)
    step_id = Column(String(255), nullable=False, index=True)
    status = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    result_data = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    attempt_number = Column(Integer, nullable=False, default=1)


class WorkflowDefinition:
    """Workflow definition with DSL support."""

    def __init__(
        self,
        workflow_type: str,
        name: str,
        description: str = "",
        version: str = "1.0",
        timeout: timedelta | None = None
    ):
        self.workflow_type = workflow_type
        self.name = name
        self.description = description
        self.version = version
        self.timeout = timeout or timedelta(hours=24)
        self.steps: list[WorkflowStep] = []
        self.variables: dict[str, Any] = {}
        self.event_handlers: dict[str, Callable] = {}

    def add_step(self, step: WorkflowStep) -> WorkflowDefinition:
        """Add a step to the workflow."""
        self.steps.append(step)
        return self

    def add_action(
        self,
        step_id: str,
        name: str,
        action: Callable[[WorkflowContext], Any],
        **kwargs
    ) -> WorkflowDefinition:
        """Add an action step."""
        step = ActionStep(step_id, name, action, **kwargs)
        return self.add_step(step)

    def add_decision(
        self,
        step_id: str,
        name: str,
        decision_logic: Callable[[WorkflowContext], str],
        branches: dict[str, list[WorkflowStep]],
        **kwargs
    ) -> WorkflowDefinition:
        """Add a decision step."""
        step = DecisionStep(step_id, name, decision_logic, branches, **kwargs)
        return self.add_step(step)

    def add_parallel(
        self,
        step_id: str,
        name: str,
        parallel_steps: list[WorkflowStep],
        **kwargs
    ) -> WorkflowDefinition:
        """Add a parallel execution step."""
        step = ParallelStep(step_id, name, parallel_steps, **kwargs)
        return self.add_step(step)

    def add_wait(
        self,
        step_id: str,
        name: str,
        wait_duration: timedelta | None = None,
        wait_condition: Callable[[WorkflowContext], bool] | None = None,
        **kwargs
    ) -> WorkflowDefinition:
        """Add a wait step."""
        step = WaitStep(step_id, name, wait_duration, wait_condition, **kwargs)
        return self.add_step(step)

    def on_event(self, event_type: str, handler: Callable[[BaseEvent, WorkflowContext], Any]):
        """Register event handler for workflow."""
        self.event_handlers[event_type] = handler

    def set_variable(self, name: str, value: Any) -> WorkflowDefinition:
        """Set a workflow variable."""
        self.variables[name] = value
        return self


class WorkflowEngine:
    """Enhanced workflow engine with saga and compensation support."""

    def __init__(
        self,
        event_bus: EventBus,
        session_factory: Callable[[], AsyncSession] | None = None,
        processing_interval: float = 5.0,
        max_concurrent_workflows: int = 100
    ):
        self.event_bus = event_bus
        self.session_factory = session_factory
        self.processing_interval = processing_interval
        self.max_concurrent_workflows = max_concurrent_workflows

        # Workflow registry
        self.workflow_definitions: dict[str, WorkflowDefinition] = {}

        # Runtime state
        self.running_workflows: dict[str, asyncio.Task] = {}
        self.workflow_semaphore = asyncio.Semaphore(max_concurrent_workflows)

        # Processing state
        self._running = False
        self._processor_task: asyncio.Task | None = None

        # Metrics
        self.metrics = {
            "workflows_started": 0,
            "workflows_completed": 0,
            "workflows_failed": 0,
            "steps_executed": 0,
            "compensations_executed": 0
        }

    def register_workflow(self, definition: WorkflowDefinition) -> None:
        """Register a workflow definition."""
        self.workflow_definitions[definition.workflow_type] = definition
        logger.info(f"Registered workflow definition: {definition.workflow_type}")

    async def start_workflow(
        self,
        workflow_type: str,
        workflow_id: str | None = None,
        initial_data: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None
    ) -> str:
        """Start a new workflow instance."""
        if workflow_type not in self.workflow_definitions:
            raise ValueError(f"Unknown workflow type: {workflow_type}")

        workflow_id = workflow_id or str(uuid.uuid4())

        # Create workflow context
        context = WorkflowContext(
            workflow_id=workflow_id,
            data=initial_data or {},
            correlation_id=correlation_id,
            user_id=user_id,
            tenant_id=tenant_id
        )

        # Persist workflow instance
        if self.session_factory:
            await self._persist_workflow_instance(
                workflow_id, workflow_type, context, WorkflowStatus.CREATED
            )

        # Schedule for execution
        if self._running:
            task = asyncio.create_task(self._execute_workflow(workflow_type, context))
            self.running_workflows[workflow_id] = task

        # Publish workflow started event
        event = create_workflow_event(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            event_type="WorkflowStarted",
            workflow_status=WorkflowStatus.CREATED.value,
            correlation_id=correlation_id
        )
        await self.event_bus.publish(event)

        self.metrics["workflows_started"] += 1
        logger.info(f"Started workflow {workflow_id} of type {workflow_type}")

        return workflow_id

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        # Cancel running task
        if workflow_id in self.running_workflows:
            task = self.running_workflows[workflow_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.running_workflows[workflow_id]

        # Update persistence
        if self.session_factory:
            await self._update_workflow_status(workflow_id, WorkflowStatus.CANCELLED)

        # Publish cancelled event
        event = create_workflow_event(
            workflow_id=workflow_id,
            workflow_type="",  # Will be filled from persistence
            event_type="WorkflowCancelled",
            workflow_status=WorkflowStatus.CANCELLED.value
        )
        await self.event_bus.publish(event)

        logger.info(f"Cancelled workflow {workflow_id}")
        return True

    async def get_workflow_status(self, workflow_id: str) -> dict[str, Any] | None:
        """Get workflow status and progress."""
        if not self.session_factory:
            return None

        async with self._get_session() as session:

            query = select(WorkflowInstance).where(WorkflowInstance.workflow_id == workflow_id)
            result = await session.execute(query)
            instance = result.scalar_one_or_none()

            if not instance:
                return None

            return {
                "workflow_id": instance.workflow_id,
                "workflow_type": instance.workflow_type,
                "status": instance.status,
                "current_step": instance.current_step,
                "created_at": instance.created_at,
                "updated_at": instance.updated_at,
                "started_at": instance.started_at,
                "completed_at": instance.completed_at,
                "error_message": instance.error_message,
                "retry_count": instance.retry_count
            }

    async def retry_failed_workflow(self, workflow_id: str) -> bool:
        """Retry a failed workflow from the last successful step."""
        status = await self.get_workflow_status(workflow_id)
        if not status or status["status"] != WorkflowStatus.FAILED.value:
            return False

        # Load workflow context
        context = await self._load_workflow_context(workflow_id)
        if not context:
            return False

        # Restart workflow execution
        workflow_type = status["workflow_type"]
        task = asyncio.create_task(self._execute_workflow(workflow_type, context))
        self.running_workflows[workflow_id] = task

        logger.info(f"Retrying failed workflow {workflow_id}")
        return True

    async def start(self) -> None:
        """Start the workflow engine."""
        if self._running:
            return

        self._running = True

        # Start background processor for failed/pending workflows
        if self.session_factory:
            self._processor_task = asyncio.create_task(self._process_pending_workflows())

        logger.info("Workflow engine started")

    async def stop(self) -> None:
        """Stop the workflow engine."""
        if not self._running:
            return

        self._running = False

        # Cancel all running workflows
        for _workflow_id, task in list(self.running_workflows.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.running_workflows.clear()

        # Stop background processor
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        logger.info("Workflow engine stopped")

    # Private methods
    async def _execute_workflow(self, workflow_type: str, context: WorkflowContext) -> None:
        """Execute a workflow instance."""
        async with self.workflow_semaphore:
            definition = self.workflow_definitions[workflow_type]

            try:
                # Update status to running
                if self.session_factory:
                    await self._update_workflow_status(context.workflow_id, WorkflowStatus.RUNNING)

                # Publish running event
                event = create_workflow_event(
                    workflow_id=context.workflow_id,
                    workflow_type=workflow_type,
                    event_type="WorkflowRunning",
                    workflow_status=WorkflowStatus.RUNNING.value,
                    correlation_id=context.correlation_id
                )
                await self.event_bus.publish(event)

                # Execute workflow steps
                for step in definition.steps:
                    if not step.should_execute(context):
                        continue

                    success = await self._execute_step(step, context, workflow_type)

                    if not success:
                        # Start compensation if step failed
                        await self._compensate_workflow(definition, context, workflow_type)
                        return

                # Workflow completed successfully
                await self._complete_workflow(context.workflow_id, workflow_type, WorkflowStatus.COMPLETED)

            except Exception as e:
                logger.error(f"Workflow {context.workflow_id} failed: {e}")
                await self._complete_workflow(
                    context.workflow_id, workflow_type, WorkflowStatus.FAILED, str(e)
                )
            finally:
                # Clean up running workflow
                if context.workflow_id in self.running_workflows:
                    del self.running_workflows[context.workflow_id]

    async def _execute_step(
        self,
        step: WorkflowStep,
        context: WorkflowContext,
        workflow_type: str
    ) -> bool:
        """Execute a single workflow step with retry logic."""
        attempts = 0
        max_attempts = step.retry_count + 1

        while attempts < max_attempts:
            try:
                # Update current step
                if self.session_factory:
                    await self._update_current_step(context.workflow_id, step.step_id)

                # Execute step
                step.status = StepStatus.RUNNING
                result = await asyncio.wait_for(
                    step.execute(context),
                    timeout=step.timeout.total_seconds()
                )

                # Process result
                if result.success:
                    step.status = StepStatus.COMPLETED
                    context.step_results[step.step_id] = result

                    # Merge result data into context
                    if result.data:
                        context.data.update(result.data)

                    # Persist step execution
                    if self.session_factory:
                        await self._persist_step_execution(
                            context.workflow_id, step.step_id, StepStatus.COMPLETED, result
                        )

                    # Publish step completed event
                    event = create_workflow_event(
                        workflow_id=context.workflow_id,
                        workflow_type=workflow_type,
                        event_type="StepCompleted",
                        workflow_step=step.step_id,
                        workflow_data=result.data,
                        correlation_id=context.correlation_id
                    )
                    await self.event_bus.publish(event)

                    self.metrics["steps_executed"] += 1
                    return True
                else:
                    # Step failed
                    step.status = StepStatus.FAILED

                    if result.should_retry and attempts < max_attempts - 1:
                        attempts += 1
                        if result.retry_delay:
                            await asyncio.sleep(result.retry_delay.total_seconds())
                        elif step.retry_delay:
                            await asyncio.sleep(step.retry_delay.total_seconds())
                        continue
                    else:
                        # Final failure
                        if self.session_factory:
                            await self._persist_step_execution(
                                context.workflow_id, step.step_id, StepStatus.FAILED, result
                            )

                        # Publish step failed event
                        event = create_workflow_event(
                            workflow_id=context.workflow_id,
                            workflow_type=workflow_type,
                            event_type="StepFailed",
                            workflow_step=step.step_id,
                            workflow_data={"error": result.error},
                            correlation_id=context.correlation_id
                        )
                        await self.event_bus.publish(event)

                        return False

            except asyncio.TimeoutError:
                logger.error(f"Step {step.step_id} timed out")
                step.status = StepStatus.FAILED

                if attempts < max_attempts - 1:
                    attempts += 1
                    continue
                else:
                    return False

            except Exception as e:
                logger.error(f"Step {step.step_id} failed with exception: {e}")
                step.status = StepStatus.FAILED

                if attempts < max_attempts - 1:
                    attempts += 1
                    if step.retry_delay:
                        await asyncio.sleep(step.retry_delay.total_seconds())
                    continue
                else:
                    return False

        return False

    async def _compensate_workflow(
        self,
        definition: WorkflowDefinition,
        context: WorkflowContext,
        workflow_type: str
    ) -> None:
        """Execute compensation logic for failed workflow."""
        logger.info(f"Starting compensation for workflow {context.workflow_id}")

        # Update status to compensating
        if self.session_factory:
            await self._update_workflow_status(context.workflow_id, WorkflowStatus.COMPENSATING)

        # Publish compensating event
        event = create_workflow_event(
            workflow_id=context.workflow_id,
            workflow_type=workflow_type,
            event_type="WorkflowCompensating",
            workflow_status=WorkflowStatus.COMPENSATING.value,
            correlation_id=context.correlation_id
        )
        await self.event_bus.publish(event)

        # Execute compensation in reverse order
        completed_steps = [
            step for step in reversed(definition.steps)
            if step.step_id in context.step_results and context.step_results[step.step_id].success
        ]

        compensation_success = True

        for step in completed_steps:
            try:
                result = await step.compensate(context)

                if result.success:
                    step.status = StepStatus.COMPENSATED
                    self.metrics["compensations_executed"] += 1

                    # Publish compensation completed event
                    event = create_workflow_event(
                        workflow_id=context.workflow_id,
                        workflow_type=workflow_type,
                        event_type="StepCompensated",
                        workflow_step=step.step_id,
                        correlation_id=context.correlation_id
                    )
                    await self.event_bus.publish(event)

                else:
                    logger.error(f"Compensation failed for step {step.step_id}: {result.error}")
                    compensation_success = False
                    break

            except Exception as e:
                logger.error(f"Compensation exception for step {step.step_id}: {e}")
                compensation_success = False
                break

        # Complete compensation
        final_status = WorkflowStatus.COMPENSATED if compensation_success else WorkflowStatus.FAILED
        await self._complete_workflow(context.workflow_id, workflow_type, final_status)

    async def _complete_workflow(
        self,
        workflow_id: str,
        workflow_type: str,
        status: WorkflowStatus,
        error_message: str | None = None
    ) -> None:
        """Complete workflow execution."""
        # Update persistence
        if self.session_factory:
            await self._update_workflow_completion(workflow_id, status, error_message)

        # Publish completion event
        event_type_map = {
            WorkflowStatus.COMPLETED: "WorkflowCompleted",
            WorkflowStatus.FAILED: "WorkflowFailed",
            WorkflowStatus.CANCELLED: "WorkflowCancelled",
            WorkflowStatus.COMPENSATED: "WorkflowCompensated"
        }

        event = create_workflow_event(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            event_type=event_type_map.get(status, "WorkflowStatusChanged"),
            workflow_status=status.value
        )
        await self.event_bus.publish(event)

        # Update metrics
        if status == WorkflowStatus.COMPLETED:
            self.metrics["workflows_completed"] += 1
        elif status == WorkflowStatus.FAILED:
            self.metrics["workflows_failed"] += 1

        logger.info(f"Workflow {workflow_id} completed with status: {status.value}")

    async def _process_pending_workflows(self) -> None:
        """Background task to process pending/failed workflows."""
        while self._running:
            try:
                await self._recover_interrupted_workflows()
                await asyncio.sleep(self.processing_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in workflow processor: {e}")
                await asyncio.sleep(self.processing_interval)

    async def _recover_interrupted_workflows(self) -> None:
        """Recover workflows that were interrupted."""
        if not self.session_factory:
            return

        async with self._get_session() as session:

            # Find workflows that were running but have no active task
            query = select(WorkflowInstance).where(
                and_(
                    WorkflowInstance.status == WorkflowStatus.RUNNING.value,
                    WorkflowInstance.updated_at < datetime.now(timezone.utc) - timedelta(minutes=5)
                )
            ).limit(10)

            result = await session.execute(query)
            interrupted_workflows = result.scalars().all()

            for workflow in interrupted_workflows:
                if workflow.workflow_id not in self.running_workflows:
                    # Restart interrupted workflow
                    context = await self._load_workflow_context(str(workflow.workflow_id))
                    if context:
                        task = asyncio.create_task(
                            self._execute_workflow(str(workflow.workflow_type), context)
                        )
                        self.running_workflows[str(workflow.workflow_id)] = task
                        logger.info(f"Recovered interrupted workflow {workflow.workflow_id}")

    # Database helper methods
    @asynccontextmanager
    async def _get_session(self):
        """Get database session."""
        if not self.session_factory:
            raise RuntimeError("Database session factory not configured")

        session = self.session_factory()
        try:
            yield session
        finally:
            await session.close()

    async def _persist_workflow_instance(
        self,
        workflow_id: str,
        workflow_type: str,
        context: WorkflowContext,
        status: WorkflowStatus
    ) -> None:
        """Persist workflow instance to database."""
        async with self._get_session() as session:
            instance = WorkflowInstance(
                workflow_id=workflow_id,
                workflow_type=workflow_type,
                status=status.value,
                context_data=json.dumps(context.__dict__, default=str),
                correlation_id=context.correlation_id,
                user_id=context.user_id,
                tenant_id=context.tenant_id
            )

            session.add(instance)
            await session.commit()

    async def _update_workflow_status(self, workflow_id: str, status: WorkflowStatus) -> None:
        """Update workflow status."""
        async with self._get_session() as session:

            query = update(WorkflowInstance).where(
                WorkflowInstance.workflow_id == workflow_id
            ).values(
                status=status.value,
                updated_at=datetime.now(timezone.utc)
            )

            await session.execute(query)
            await session.commit()

    async def _update_current_step(self, workflow_id: str, step_id: str) -> None:
        """Update current step."""
        async with self._get_session() as session:

            query = update(WorkflowInstance).where(
                WorkflowInstance.workflow_id == workflow_id
            ).values(
                current_step=step_id,
                updated_at=datetime.now(timezone.utc)
            )

            await session.execute(query)
            await session.commit()

    async def _update_workflow_completion(
        self,
        workflow_id: str,
        status: WorkflowStatus,
        error_message: str | None = None
    ) -> None:
        """Update workflow completion."""
        async with self._get_session() as session:

            query = update(WorkflowInstance).where(
                WorkflowInstance.workflow_id == workflow_id
            ).values(
                status=status.value,
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                error_message=error_message
            )

            await session.execute(query)
            await session.commit()

    async def _persist_step_execution(
        self,
        workflow_id: str,
        step_id: str,
        status: StepStatus,
        result: StepResult
    ) -> None:
        """Persist step execution result."""
        async with self._get_session() as session:
            execution = WorkflowStepExecution(
                workflow_id=workflow_id,
                step_id=step_id,
                status=status.value,
                completed_at=datetime.now(timezone.utc) if status in [StepStatus.COMPLETED, StepStatus.FAILED] else None,
                result_data=json.dumps(result.data) if result.data else None,
                error_message=result.error
            )

            session.add(execution)
            await session.commit()

    async def _load_workflow_context(self, workflow_id: str) -> WorkflowContext | None:
        """Load workflow context from database."""
        async with self._get_session() as session:

            query = select(WorkflowInstance).where(WorkflowInstance.workflow_id == workflow_id)
            result = await session.execute(query)
            instance = result.scalar_one_or_none()

            if not instance:
                return None

            context_data = json.loads(str(instance.context_data))
            return WorkflowContext(**context_data)


# DSL Builder for easier workflow creation
class WorkflowBuilder:
    """Fluent interface for building workflows."""

    def __init__(self, workflow_type: str, name: str):
        self.definition = WorkflowDefinition(workflow_type, name)

    def description(self, desc: str) -> WorkflowBuilder:
        """Set workflow description."""
        self.definition.description = desc
        return self

    def version(self, ver: str) -> WorkflowBuilder:
        """Set workflow version."""
        self.definition.version = ver
        return self

    def timeout(self, timeout: timedelta) -> WorkflowBuilder:
        """Set workflow timeout."""
        self.definition.timeout = timeout
        return self

    def step(self, step: WorkflowStep) -> WorkflowBuilder:
        """Add a step to the workflow."""
        self.definition.add_step(step)
        return self

    def action(
        self,
        step_id: str,
        name: str,
        action: Callable[[WorkflowContext], Any],
        **kwargs
    ) -> WorkflowBuilder:
        """Add an action step."""
        self.definition.add_action(step_id, name, action, **kwargs)
        return self

    def decision(
        self,
        step_id: str,
        name: str,
        decision_logic: Callable[[WorkflowContext], str],
        branches: dict[str, list[WorkflowStep]],
        **kwargs
    ) -> WorkflowBuilder:
        """Add a decision step."""
        self.definition.add_decision(step_id, name, decision_logic, branches, **kwargs)
        return self

    def parallel(
        self,
        step_id: str,
        name: str,
        parallel_steps: list[WorkflowStep],
        **kwargs
    ) -> WorkflowBuilder:
        """Add a parallel step."""
        self.definition.add_parallel(step_id, name, parallel_steps, **kwargs)
        return self

    def wait(
        self,
        step_id: str,
        name: str,
        wait_duration: timedelta | None = None,
        wait_condition: Callable[[WorkflowContext], bool] | None = None,
        **kwargs
    ) -> WorkflowBuilder:
        """Add a wait step."""
        self.definition.add_wait(step_id, name, wait_duration, wait_condition, **kwargs)
        return self

    def on_event(
        self,
        event_type: str,
        handler: Callable[[BaseEvent, WorkflowContext], Any]
    ) -> WorkflowBuilder:
        """Register event handler."""
        self.definition.on_event(event_type, handler)
        return self

    def variable(self, name: str, value: Any) -> WorkflowBuilder:
        """Set workflow variable."""
        self.definition.set_variable(name, value)
        return self

    def build(self) -> WorkflowDefinition:
        """Build the workflow definition."""
        return self.definition


# Context manager for workflow engine
@asynccontextmanager
async def workflow_engine_context(
    event_bus: EventBus,
    session_factory: Callable[[], AsyncSession] | None = None,
    **kwargs
):
    """Context manager for workflow engine lifecycle."""
    engine = WorkflowEngine(event_bus, session_factory, **kwargs)
    try:
        await engine.start()
        yield engine
    finally:
        await engine.stop()


# Convenience function for creating workflows
def create_workflow(workflow_type: str, name: str) -> WorkflowBuilder:
    """Create a new workflow with builder pattern."""
    return WorkflowBuilder(workflow_type, name)
