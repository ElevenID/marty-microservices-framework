"""
Saga Pattern Implementation for Marty Microservices Framework

This module implements the Saga pattern for managing distributed transactions
with compensation logic and long-running business processes.
"""

import asyncio
import builtins
import logging
import threading
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SagaState(Enum):
    """Saga execution states."""

    CREATED = "created"
    EXECUTING = "executing"
    COMPENSATING = "compensating"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Individual step in a saga."""

    step_id: str
    step_name: str
    service_name: str
    action: str
    compensation_action: str
    parameters: builtins.dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30
    retry_count: int = 3
    is_critical: bool = True  # If false, failure doesn't abort saga


@dataclass
class SagaTransaction:
    """Saga transaction definition."""

    saga_id: str
    saga_type: str
    steps: builtins.list[SagaStep]
    state: SagaState = SagaState.CREATED
    current_step: int = 0
    completed_steps: builtins.list[str] = field(default_factory=list)
    compensated_steps: builtins.list[str] = field(default_factory=list)
    context: builtins.dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SagaOrchestrator:
    """Orchestrates saga execution with compensation logic."""

    def __init__(self, orchestrator_id: str):
        """Initialize saga orchestrator."""
        self.orchestrator_id = orchestrator_id
        self.sagas: builtins.dict[str, SagaTransaction] = {}
        self.step_handlers: builtins.dict[str, Callable] = {}
        self.compensation_handlers: builtins.dict[str, Callable] = {}
        self.lock = threading.RLock()

        # Background processing
        self.processing_queue = deque()
        self.worker_tasks: builtins.list[asyncio.Task] = []
        self.is_running = False

    async def start(self, worker_count: int = 3):
        """Start saga orchestrator with background workers."""
        if self.is_running:
            return

        self.is_running = True

        # Start worker tasks
        for i in range(worker_count):
            task = asyncio.create_task(self._worker_loop(f"worker-{i}"))
            self.worker_tasks.append(task)

        logging.info("Saga orchestrator started: %s", self.orchestrator_id)

    async def stop(self):
        """Stop saga orchestrator and workers."""
        if not self.is_running:
            return

        self.is_running = False

        # Cancel worker tasks
        for task in self.worker_tasks:
            task.cancel()

        # Wait for workers to stop
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        self.worker_tasks.clear()
        logging.info("Saga orchestrator stopped: %s", self.orchestrator_id)

    def register_step_handler(self, step_name: str, handler: Callable):
        """Register handler for saga step."""
        self.step_handlers[step_name] = handler

    def register_compensation_handler(self, step_name: str, handler: Callable):
        """Register compensation handler for saga step."""
        self.compensation_handlers[step_name] = handler

    async def start_saga(
        self,
        saga_type: str,
        steps: builtins.list[SagaStep],
        context: builtins.dict[str, Any] | None = None,
    ) -> str:
        """Start a new saga."""
        saga_id = str(uuid.uuid4())

        saga = SagaTransaction(
            saga_id=saga_id,
            saga_type=saga_type,
            steps=steps,
            context=context or {},
        )

        with self.lock:
            self.sagas[saga_id] = saga
            self.processing_queue.append(saga_id)

        logging.info("Started saga: %s (type: %s)", saga_id, saga_type)
        return saga_id

    async def get_saga_status(self, saga_id: str) -> SagaState | None:
        """Get saga status."""
        with self.lock:
            saga = self.sagas.get(saga_id)
            return saga.state if saga else None

    async def get_saga(self, saga_id: str) -> SagaTransaction | None:
        """Get saga details."""
        with self.lock:
            return self.sagas.get(saga_id)

    async def _worker_loop(self, worker_id: str):
        """Worker loop for processing sagas."""
        logging.info("Saga worker started: %s", worker_id)

        while self.is_running:
            try:
                # Get next saga to process
                saga_id = None
                with self.lock:
                    if self.processing_queue:
                        saga_id = self.processing_queue.popleft()

                if saga_id:
                    await self._process_saga(saga_id)
                else:
                    await asyncio.sleep(1)  # No work available

            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.exception("Worker error in %s: %s", worker_id, e)
                await asyncio.sleep(5)

        logging.info("Saga worker stopped: %s", worker_id)

    async def _process_saga(self, saga_id: str):
        """Process a single saga."""
        with self.lock:
            saga = self.sagas.get(saga_id)
            if not saga:
                return

        if saga.state == SagaState.CREATED:
            await self._execute_saga(saga)
        elif saga.state == SagaState.COMPENSATING:
            await self._compensate_saga(saga)
        # Other states don't need processing

    async def _execute_saga(self, saga: SagaTransaction):
        """Execute saga steps forward."""
        with self.lock:
            saga.state = SagaState.EXECUTING
            saga.updated_at = datetime.now(timezone.utc)

        while saga.current_step < len(saga.steps):
            step = saga.steps[saga.current_step]

            try:
                success = await self._execute_step(saga, step)

                if success:
                    with self.lock:
                        saga.completed_steps.append(step.step_id)
                        saga.current_step += 1
                        saga.updated_at = datetime.now(timezone.utc)

                    logging.info(
                        "Saga step completed: %s/%s (saga: %s)",
                        step.step_name,
                        step.step_id,
                        saga.saga_id,
                    )
                else:
                    if step.is_critical:
                        # Critical step failed, start compensation
                        await self._start_compensation(saga)
                        return
                    else:
                        # Non-critical step failed, continue
                        logging.warning(
                            "Non-critical saga step failed: %s/%s (saga: %s)",
                            step.step_name,
                            step.step_id,
                            saga.saga_id,
                        )
                        with self.lock:
                            saga.current_step += 1
                            saga.updated_at = datetime.now(timezone.utc)

            except Exception as e:
                logging.exception(
                    "Saga step error: %s/%s (saga: %s): %s",
                    step.step_name,
                    step.step_id,
                    saga.saga_id,
                    e,
                )

                if step.is_critical:
                    await self._start_compensation(saga)
                    return
                else:
                    with self.lock:
                        saga.current_step += 1
                        saga.updated_at = datetime.now(timezone.utc)

        # All steps completed successfully
        with self.lock:
            saga.state = SagaState.COMPLETED
            saga.updated_at = datetime.now(timezone.utc)

        logging.info("Saga completed successfully: %s", saga.saga_id)

    async def _execute_step(self, saga: SagaTransaction, step: SagaStep) -> bool:
        """Execute individual saga step."""
        handler = self.step_handlers.get(step.step_name)
        if not handler:
            logging.error("No handler found for step: %s", step.step_name)
            return False

        # Prepare step context
        step_context = {
            "saga_id": saga.saga_id,
            "step_id": step.step_id,
            "step_name": step.step_name,
            "parameters": step.parameters,
            "saga_context": saga.context,
        }

        # Execute with retries
        for attempt in range(step.retry_count + 1):
            try:
                # Execute with timeout
                result = await asyncio.wait_for(handler(step_context), timeout=step.timeout_seconds)
                return bool(result)

            except asyncio.TimeoutError:
                logging.warning(
                    "Saga step timeout (attempt %d/%d): %s/%s",
                    attempt + 1,
                    step.retry_count + 1,
                    step.step_name,
                    step.step_id,
                )
            except Exception as e:
                logging.exception(
                    "Saga step execution error (attempt %d/%d): %s/%s: %s",
                    attempt + 1,
                    step.retry_count + 1,
                    step.step_name,
                    step.step_id,
                    e,
                )

            if attempt < step.retry_count:
                await asyncio.sleep(2**attempt)  # Exponential backoff

        return False

    async def _start_compensation(self, saga: SagaTransaction):
        """Start saga compensation process."""
        with self.lock:
            saga.state = SagaState.COMPENSATING
            saga.updated_at = datetime.now(timezone.utc)
            # Add back to queue for compensation processing
            self.processing_queue.append(saga.saga_id)

        logging.info("Starting saga compensation: %s", saga.saga_id)

    async def _compensate_saga(self, saga: SagaTransaction):
        """Execute compensation steps in reverse order."""
        # Compensate completed steps in reverse order
        completed_steps = saga.completed_steps.copy()
        completed_steps.reverse()

        for step_id in completed_steps:
            # Find the step
            step = None
            for s in saga.steps:
                if s.step_id == step_id:
                    step = s
                    break

            if not step:
                continue

            try:
                success = await self._compensate_step(saga, step)

                if success:
                    with self.lock:
                        saga.compensated_steps.append(step.step_id)
                        saga.updated_at = datetime.now(timezone.utc)

                    logging.info(
                        "Saga step compensated: %s/%s (saga: %s)",
                        step.step_name,
                        step.step_id,
                        saga.saga_id,
                    )
                else:
                    logging.error(
                        "Saga step compensation failed: %s/%s (saga: %s)",
                        step.step_name,
                        step.step_id,
                        saga.saga_id,
                    )

            except Exception as e:
                logging.exception(
                    "Saga step compensation error: %s/%s (saga: %s): %s",
                    step.step_name,
                    step.step_id,
                    saga.saga_id,
                    e,
                )

        # Mark saga as compensated
        with self.lock:
            if len(saga.compensated_steps) == len(saga.completed_steps):
                saga.state = SagaState.COMPENSATED
            else:
                saga.state = SagaState.FAILED

            saga.updated_at = datetime.now(timezone.utc)

        logging.info("Saga compensation completed: %s (state: %s)", saga.saga_id, saga.state.value)

    async def _compensate_step(self, saga: SagaTransaction, step: SagaStep) -> bool:
        """Execute compensation for individual step."""
        handler = self.compensation_handlers.get(step.step_name)
        if not handler:
            logging.warning("No compensation handler found for step: %s", step.step_name)
            return True  # Assume success if no compensation needed

        # Prepare compensation context
        compensation_context = {
            "saga_id": saga.saga_id,
            "step_id": step.step_id,
            "step_name": step.step_name,
            "parameters": step.parameters,
            "saga_context": saga.context,
        }

        # Execute compensation with retries
        for attempt in range(step.retry_count + 1):
            try:
                result = await asyncio.wait_for(
                    handler(compensation_context), timeout=step.timeout_seconds
                )
                return bool(result)

            except asyncio.TimeoutError:
                logging.warning(
                    "Saga compensation timeout (attempt %d/%d): %s/%s",
                    attempt + 1,
                    step.retry_count + 1,
                    step.step_name,
                    step.step_id,
                )
            except Exception as e:
                logging.exception(
                    "Saga compensation error (attempt %d/%d): %s/%s: %s",
                    attempt + 1,
                    step.retry_count + 1,
                    step.step_name,
                    step.step_id,
                    e,
                )

            if attempt < step.retry_count:
                await asyncio.sleep(2**attempt)

        return False

    def get_saga_statistics(self) -> builtins.dict[str, Any]:
        """Get saga statistics."""
        with self.lock:
            stats = {
                "total_sagas": len(self.sagas),
                "by_state": defaultdict(int),
                "orchestrator_id": self.orchestrator_id,
                "queue_size": len(self.processing_queue),
            }

            for saga in self.sagas.values():
                stats["by_state"][saga.state.value] += 1

            return dict(stats)


class SagaBuilder:
    """Builder for creating saga definitions."""

    def __init__(self, saga_type: str):
        """Initialize saga builder."""
        self.saga_type = saga_type
        self.steps: builtins.list[SagaStep] = []

    def add_step(
        self,
        step_name: str,
        service_name: str,
        action: str,
        compensation_action: str,
        parameters: builtins.dict[str, Any] | None = None,
        timeout_seconds: int = 30,
        retry_count: int = 3,
        is_critical: bool = True,
    ) -> "SagaBuilder":
        """Add step to saga."""
        step = SagaStep(
            step_id=str(uuid.uuid4()),
            step_name=step_name,
            service_name=service_name,
            action=action,
            compensation_action=compensation_action,
            parameters=parameters or {},
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            is_critical=is_critical,
        )

        self.steps.append(step)
        return self

    def build(self) -> builtins.list[SagaStep]:
        """Build saga steps."""
        return self.steps.copy()
