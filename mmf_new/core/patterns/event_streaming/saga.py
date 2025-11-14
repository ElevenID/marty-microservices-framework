"""
Saga Orchestration Implementation

Provides saga pattern implementation for managing long-running business transactions
across multiple microservices with compensation and failure handling.
"""

import asyncio
import builtins
import logging
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, TypeVar

from .core import DomainEvent, EventBus, EventMetadata
from .cqrs import Command, CommandBus, CommandStatus

logger = logging.getLogger(__name__)

TSaga = TypeVar("TSaga", bound="Saga")


class SagaStatus(Enum):
    """Saga execution status."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    ABORTED = "aborted"


class StepStatus(Enum):
    """Saga step execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    SKIPPED = "skipped"


class CompensationStrategy(Enum):
    """Compensation strategy for failed sagas."""

    SEQUENTIAL = "sequential"  # Compensate in reverse order
    PARALLEL = "parallel"  # Compensate all steps in parallel
    CUSTOM = "custom"  # Use custom compensation logic


@dataclass
class SagaContext:
    """Context data shared across saga steps."""

    saga_id: str
    correlation_id: str
    data: builtins.dict[str, Any] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get context data."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set context data."""
        self.data[key] = value

    def update(self, data: builtins.dict[str, Any]) -> None:
        """Update context data."""
        self.data.update(data)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary."""
        return {
            "saga_id": self.saga_id,
            "correlation_id": self.correlation_id,
            "data": self.data,
            "metadata": self.metadata,
        }


@dataclass
class CompensationAction:
    """Compensation action for saga step failure."""

    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""
    command: Command | None = None
    custom_handler: Callable | None = None
    parameters: builtins.dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: timedelta = field(default_factory=lambda: timedelta(seconds=5))

    async def execute(self, context: SagaContext, command_bus: CommandBus = None) -> bool:
        """Execute compensation action."""
        try:
            if self.command and command_bus:
                result = await command_bus.send(self.command)
                return result.status == CommandStatus.COMPLETED
            if self.custom_handler:
                await self.custom_handler(context, self.parameters)
                return True
            logger.warning(f"No compensation action defined for {self.action_id}")
            return True

        except Exception as e:
            logger.error(f"Compensation action {self.action_id} failed: {e}")
            return False


@dataclass
class SagaStep:
    """Individual step in a saga."""

    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    step_name: str = ""
    step_order: int = 0
    command: Command | None = None
    custom_handler: Callable | None = None
    compensation_action: CompensationAction | None = None
    status: StepStatus = StepStatus.PENDING

    # Execution tracking
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    result_data: Any = None

    # Retry configuration
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: timedelta = field(default_factory=lambda: timedelta(seconds=5))

    # Conditional execution
    condition: Callable[[SagaContext], bool] | None = None

    def should_execute(self, context: SagaContext) -> bool:
        """Check if step should be executed."""
        if self.condition:
            return self.condition(context)
        return True

    async def execute(self, context: SagaContext, command_bus: CommandBus = None) -> bool:
        """Execute saga step."""
        self.status = StepStatus.EXECUTING
        self.started_at = datetime.utcnow()

        try:
            if self.command and command_bus:
                # Update command with saga context
                self.command.correlation_id = context.correlation_id
                self.command.metadata.update(
                    {
                        "saga_id": context.saga_id,
                        "step_id": self.step_id,
                        "step_name": self.step_name,
                    }
                )

                result = await command_bus.send(self.command)

                if result.status == CommandStatus.COMPLETED:
                    self.status = StepStatus.COMPLETED
                    self.result_data = result.result_data
                    self.completed_at = datetime.utcnow()
                    return True
                self.status = StepStatus.FAILED
                self.error_message = result.error_message
                return False

            if self.custom_handler:
                result = await self.custom_handler(context)
                self.status = StepStatus.COMPLETED
                self.result_data = result
                self.completed_at = datetime.utcnow()
                return True
            logger.warning(f"No action defined for step {self.step_id}")
            self.status = StepStatus.SKIPPED
            self.completed_at = datetime.utcnow()
            return True

        except Exception as e:
            logger.error(f"Step {self.step_id} failed: {e}")
            self.status = StepStatus.FAILED
            self.error_message = str(e)
            return False

    async def compensate(self, context: SagaContext, command_bus: CommandBus = None) -> bool:
        """Execute compensation for this step."""
        if not self.compensation_action:
            logger.info(f"No compensation action for step {self.step_id}")
            return True

        self.status = StepStatus.COMPENSATING

        try:
            success = await self.compensation_action.execute(context, command_bus)
            if success:
                self.status = StepStatus.COMPENSATED
            else:
                logger.error(f"Compensation failed for step {self.step_id}")
            return success

        except Exception as e:
            logger.error(f"Compensation error for step {self.step_id}: {e}")
            return False


class Saga(ABC):
    """Base saga class for orchestrating distributed transactions."""

    def __init__(self, saga_id: str = None, correlation_id: str = None):
        self.saga_id = saga_id or str(uuid.uuid4())
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.status = SagaStatus.CREATED
        self.context = SagaContext(self.saga_id, self.correlation_id)
        self.steps: builtins.list[SagaStep] = []
        self.current_step_index = 0

        # Metadata
        self.saga_type = self.__class__.__name__
        self.created_at = datetime.utcnow()
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.error_message: str | None = None

        # Configuration
        self.compensation_strategy = CompensationStrategy.SEQUENTIAL
        self.timeout: timedelta | None = None

        # Initialize steps
        self._initialize_steps()

    @abstractmethod
    def _initialize_steps(self) -> None:
        """Initialize saga steps (implement in subclasses)."""
        raise NotImplementedError

    def add_step(self, step: SagaStep) -> None:
        """Add step to saga."""
        step.step_order = len(self.steps)
        self.steps.append(step)

    def create_step(
        self,
        step_name: str,
        command: Command = None,
        custom_handler: Callable = None,
        compensation_action: CompensationAction = None,
    ) -> SagaStep:
        """Create and add a new step."""
        step = SagaStep(
            step_name=step_name,
            command=command,
            custom_handler=custom_handler,
            compensation_action=compensation_action,
        )
        self.add_step(step)
        return step

    async def execute(self, command_bus: CommandBus) -> bool:
        """Execute the saga."""
        self.status = SagaStatus.RUNNING
        self.started_at = datetime.utcnow()

        try:
            # Execute steps sequentially
            for i, step in enumerate(self.steps):
                self.current_step_index = i

                # Check if step should be executed
                if not step.should_execute(self.context):
                    step.status = StepStatus.SKIPPED
                    continue

                # Execute step with retries
                success = await self._execute_step_with_retries(step, command_bus)

                if not success:
                    # Step failed, start compensation
                    self.status = SagaStatus.FAILED
                    self.error_message = step.error_message

                    # Execute compensation
                    compensation_success = await self._compensate(command_bus)
                    if compensation_success:
                        self.status = SagaStatus.COMPENSATED
                    else:
                        self.status = SagaStatus.ABORTED

                    self.completed_at = datetime.utcnow()
                    return False

            # All steps completed successfully
            self.status = SagaStatus.COMPLETED
            self.completed_at = datetime.utcnow()
            return True

        except Exception as e:
            logger.error(f"Saga {self.saga_id} execution failed: {e}")
            self.status = SagaStatus.FAILED
            self.error_message = str(e)
            self.completed_at = datetime.utcnow()
            return False

    async def _execute_step_with_retries(self, step: SagaStep, command_bus: CommandBus) -> bool:
        """Execute step with retry logic."""
        while step.retry_count <= step.max_retries:
            success = await step.execute(self.context, command_bus)

            if success:
                return True

            step.retry_count += 1
            if step.retry_count <= step.max_retries:
                logger.info(f"Retrying step {step.step_id} (attempt {step.retry_count})")
                await asyncio.sleep(step.retry_delay.total_seconds())
            else:
                logger.error(f"Step {step.step_id} failed after {step.max_retries} retries")
                return False

        return False

    async def _compensate(self, command_bus: CommandBus) -> bool:
        """Execute compensation for completed steps."""
        self.status = SagaStatus.COMPENSATING

        if self.compensation_strategy == CompensationStrategy.SEQUENTIAL:
            return await self._compensate_sequential(command_bus)
        if self.compensation_strategy == CompensationStrategy.PARALLEL:
            return await self._compensate_parallel(command_bus)
        return await self._compensate_custom(command_bus)

    async def _compensate_sequential(self, command_bus: CommandBus) -> bool:
        """Compensate steps in reverse order."""
        completed_steps = [
            s for s in self.steps[: self.current_step_index] if s.status == StepStatus.COMPLETED
        ]

        # Reverse order for compensation
        for step in reversed(completed_steps):
            success = await step.compensate(self.context, command_bus)
            if not success:
                logger.error(f"Compensation failed for step {step.step_id}")
                return False

        return True

    async def _compensate_parallel(self, command_bus: CommandBus) -> bool:
        """Compensate all completed steps in parallel."""
        completed_steps = [
            s for s in self.steps[: self.current_step_index] if s.status == StepStatus.COMPLETED
        ]

        tasks = []
        for step in completed_steps:
            tasks.append(asyncio.create_task(step.compensate(self.context, command_bus)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return all(result is True for result in results if not isinstance(result, Exception))

    async def _compensate_custom(self, command_bus: CommandBus) -> bool:
        """Custom compensation logic (override in subclasses)."""
        return await self._compensate_sequential(command_bus)

    def get_saga_state(self) -> builtins.dict[str, Any]:
        """Get current saga state."""
        return {
            "saga_id": self.saga_id,
            "saga_type": self.saga_type,
            "correlation_id": self.correlation_id,
            "status": self.status.value,
            "current_step_index": self.current_step_index,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "context": self.context.to_dict(),
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "step_order": step.step_order,
                    "status": step.status.value,
                    "started_at": step.started_at.isoformat() if step.started_at else None,
                    "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                    "error_message": step.error_message,
                    "retry_count": step.retry_count,
                }
                for step in self.steps
            ],
        }


class SagaOrchestrator:
    """Orchestrates saga execution and management."""

    def __init__(self, command_bus: CommandBus, event_bus: EventBus):
        self.command_bus = command_bus
        self.event_bus = event_bus
        self._active_sagas: builtins.dict[str, Saga] = {}
        self._saga_types: builtins.dict[str, builtins.type[Saga]] = {}
        self._lock = asyncio.Lock()

    def register_saga_type(self, saga_type: str, saga_class: builtins.type[Saga]) -> None:
        """Register saga type."""
        self._saga_types[saga_type] = saga_class

    async def start_saga(self, saga: Saga) -> bool:
        """Start saga execution."""
        async with self._lock:
            self._active_sagas[saga.saga_id] = saga

        try:
            # Publish saga started event
            await self._publish_saga_event("SagaStarted", saga)

            # Execute saga
            success = await saga.execute(self.command_bus)

            # Publish completion event
            if success:
                await self._publish_saga_event("SagaCompleted", saga)
            else:
                await self._publish_saga_event("SagaFailed", saga)

            # Remove from active sagas
            async with self._lock:
                if saga.saga_id in self._active_sagas:
                    del self._active_sagas[saga.saga_id]

            return success

        except Exception as e:
            logger.error(f"Error executing saga {saga.saga_id}: {e}")

            # Publish error event
            await self._publish_saga_event("SagaError", saga, {"error": str(e)})

            # Remove from active sagas
            async with self._lock:
                if saga.saga_id in self._active_sagas:
                    del self._active_sagas[saga.saga_id]

            return False

    async def get_saga_status(self, saga_id: str) -> builtins.dict[str, Any] | None:
        """Get saga status."""
        async with self._lock:
            saga = self._active_sagas.get(saga_id)
            if saga:
                return saga.get_saga_state()
        return None

    async def cancel_saga(self, saga_id: str) -> bool:
        """Cancel running saga."""
        async with self._lock:
            saga = self._active_sagas.get(saga_id)
            if not saga:
                return False

            if saga.status in [SagaStatus.RUNNING]:
                saga.status = SagaStatus.ABORTED
                saga.completed_at = datetime.utcnow()

                # Publish cancelled event
                await self._publish_saga_event("SagaCancelled", saga)

                # Remove from active sagas
                del self._active_sagas[saga_id]
                return True

        return False

    async def _publish_saga_event(
        self,
        event_type: str,
        saga: Saga,
        additional_data: builtins.dict[str, Any] = None,
    ) -> None:
        """Publish saga lifecycle event."""
        event_data = saga.get_saga_state()
        if additional_data:
            event_data.update(additional_data)

        event = DomainEvent(
            aggregate_id=saga.saga_id,
            event_type=event_type,
            event_data=event_data,
            metadata=EventMetadata(correlation_id=saga.correlation_id),
        )
        event.aggregate_type = "Saga"

        await self.event_bus.publish(event)


class SagaManager:
    """High-level saga management interface."""

    def __init__(self, orchestrator: SagaOrchestrator):
        self.orchestrator = orchestrator
        self._saga_repository: SagaRepository | None = None

    def set_saga_repository(self, repository: "SagaRepository") -> None:
        """Set saga repository for persistence."""
        self._saga_repository = repository

    async def create_and_start_saga(
        self, saga_type: str, initial_data: builtins.dict[str, Any] = None
    ) -> str:
        """Create and start a new saga."""
        if saga_type not in self.orchestrator._saga_types:
            raise ValueError(f"Unknown saga type: {saga_type}")

        saga_class = self.orchestrator._saga_types[saga_type]
        saga = saga_class()

        if initial_data:
            saga.context.update(initial_data)

        # Save saga if repository is available
        if self._saga_repository:
            await self._saga_repository.save(saga)

        # Start saga execution
        await self.orchestrator.start_saga(saga)

        return saga.saga_id

    async def get_saga_history(self, saga_id: str) -> builtins.dict[str, Any] | None:
        """Get saga execution history."""
        if self._saga_repository:
            return await self._saga_repository.get_saga_history(saga_id)
        return None


class SagaRepository(ABC):
    """Abstract saga repository for persistence."""

    @abstractmethod
    async def save(self, saga: Saga) -> None:
        """Save saga state."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, saga_id: str) -> Saga | None:
        """Get saga by ID."""
        raise NotImplementedError

    @abstractmethod
    async def get_saga_history(self, saga_id: str) -> builtins.dict[str, Any] | None:
        """Get saga execution history."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, saga_id: str) -> None:
        """Delete saga."""
        raise NotImplementedError


# Saga patterns and utilities


class SagaError(Exception):
    """Saga execution error."""


class SagaTimeoutError(SagaError):
    """Saga timeout error."""


class SagaCompensationError(SagaError):
    """Saga compensation error."""


# Convenience functions


def create_compensation_action(
    action_type: str,
    command: Command = None,
    custom_handler: Callable = None,
    parameters: builtins.dict[str, Any] = None,
) -> CompensationAction:
    """Create compensation action."""
    return CompensationAction(
        action_type=action_type,
        command=command,
        custom_handler=custom_handler,
        parameters=parameters or {},
    )


def create_saga_step(
    step_name: str,
    command: Command = None,
    custom_handler: Callable = None,
    compensation_action: CompensationAction = None,
) -> SagaStep:
    """Create saga step."""
    return SagaStep(
        step_name=step_name,
        command=command,
        custom_handler=custom_handler,
        compensation_action=compensation_action,
    )
