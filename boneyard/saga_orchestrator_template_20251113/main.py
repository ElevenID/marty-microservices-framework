"""
Saga Pattern Orchestrator for Distributed Transactions

This module implements a comprehensive saga orchestration system for managing
distributed transactions across multiple microservices with proper compensation,
state management, and failure recovery mechanisms.

Key Features:
- Saga definition and execution
- Compensation logic for rollbacks
- State persistence and recovery
- Timeout and retry handling
- Event-driven architecture
- Circuit breaker integration
- Monitoring and observability

Author: Marty Framework Team
Version: 1.0.0
"""

import asyncio
import builtins
import json
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, dict, list

import httpx
import structlog
import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field

__version__ = "1.0.0"



# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Metrics
saga_executions_total = Counter(
    "saga_executions_total", "Total saga executions", ["status", "saga_type"]
)
saga_step_duration = Histogram(
    "saga_step_duration_seconds", "Step execution duration", ["step_name", "saga_type"]
)
saga_compensation_total = Counter(
    "saga_compensation_total",
    "Total compensations executed",
    ["step_name", "saga_type"],
)
active_sagas_gauge = Gauge("active_sagas_total", "Number of active sagas")
saga_retry_total = Counter(
    "saga_retry_total", "Total step retries", ["step_name", "saga_type"]
)


class SagaStatus(Enum):
    """Saga execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    TIMEOUT = "timeout"


class StepStatus(Enum):
    """Step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"
    SKIPPED = "skipped"


class CompensationMode(Enum):
    """Compensation execution mode."""

    FORWARD = "forward"  # Compensate in forward order
    REVERSE = "reverse"  # Compensate in reverse order (recommended)
    PARALLEL = "parallel"  # Compensate all eligible steps in parallel


@dataclass
class SagaStep:
    """Individual step in a saga transaction."""

    name: str
    service_url: str
    method: str = "POST"
    payload: builtins.dict[str, Any] = field(default_factory=dict)
    headers: builtins.dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retries: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0

    # Compensation configuration
    compensation_url: str | None = None
    compensation_method: str = "POST"
    compensation_payload: builtins.dict[str, Any] = field(default_factory=dict)
    compensation_headers: builtins.dict[str, str] = field(default_factory=dict)
    compensation_timeout: int = 30
    compensation_retries: int = 3

    # Step dependencies and conditions
    depends_on: builtins.list[str] = field(default_factory=list)
    condition: str | None = None  # JavaScript-like condition
    required: bool = True

    # Execution state
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    response: builtins.dict[str, Any] | None = None
    attempt_count: int = 0

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert step to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        if self.started_at:
            data["started_at"] = self.started_at.isoformat()
        if self.completed_at:
            data["completed_at"] = self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "SagaStep":
        """Create step from dictionary."""
        # Convert ISO strings back to datetime objects
        if data.get("started_at"):
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])
        return cls(**data)


@dataclass
class SagaDefinition:
    """Saga definition with steps and configuration."""

    name: str
    steps: builtins.list[SagaStep]
    timeout: int = 300  # 5 minutes default
    compensation_mode: CompensationMode = CompensationMode.REVERSE
    parallel_execution: bool = False
    max_retries: int = 3
    retry_delay: float = 5.0

    # Saga metadata
    description: str | None = None
    version: str = "1.0.0"
    tags: builtins.list[str] = field(default_factory=list)
    created_by: str | None = None

    def validate(self) -> builtins.list[str]:
        """Validate saga definition."""
        errors = []

        if not self.steps:
            errors.append("Saga must have at least one step")

        step_names = {step.name for step in self.steps}
        if len(step_names) != len(self.steps):
            errors.append("Step names must be unique")

        # Validate dependencies
        for step in self.steps:
            for dep in step.depends_on:
                if dep not in step_names:
                    errors.append(f"Step '{step.name}' depends on unknown step '{dep}'")

        # Check for circular dependencies
        if self._has_circular_dependencies():
            errors.append("Circular dependencies detected in saga steps")

        return errors

    def _has_circular_dependencies(self) -> bool:
        """Check for circular dependencies in step graph."""
        visited = set()
        rec_stack = set()

        def has_cycle(step_name: str) -> bool:
            visited.add(step_name)
            rec_stack.add(step_name)

            step = next((s for s in self.steps if s.name == step_name), None)
            if step:
                for dep in step.depends_on:
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True

            rec_stack.remove(step_name)
            return False

        for step in self.steps:
            if step.name not in visited:
                if has_cycle(step.name):
                    return True

        return False

    def get_execution_order(self) -> builtins.list[builtins.list[str]]:
        """Get step execution order respecting dependencies."""
        if self.parallel_execution:
            return self._get_parallel_execution_order()
        else:
            return [[step.name] for step in self.steps]

    def _get_parallel_execution_order(self) -> builtins.list[builtins.list[str]]:
        """Calculate parallel execution order based on dependencies."""
        remaining_steps = {step.name for step in self.steps}
        execution_order = []

        while remaining_steps:
            # Find steps with no unresolved dependencies
            ready_steps = []
            for step_name in remaining_steps:
                step = next(s for s in self.steps if s.name == step_name)
                if all(dep not in remaining_steps for dep in step.depends_on):
                    ready_steps.append(step_name)

            if not ready_steps:
                # Circular dependency or error
                break

            execution_order.append(ready_steps)
            remaining_steps -= set(ready_steps)

        return execution_order


@dataclass
class SagaExecution:
    """Saga execution instance with state tracking."""

    id: str
    saga_name: str
    status: SagaStatus = SagaStatus.PENDING
    steps: builtins.list[SagaStep] = field(default_factory=list)

    # Execution timing
    started_at: datetime | None = None
    completed_at: datetime | None = None
    timeout_at: datetime | None = None

    # Execution context
    context: builtins.dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    user_id: str | None = None

    # Error handling
    error: str | None = None
    failed_step: str | None = None
    compensation_started_at: datetime | None = None
    compensation_completed_at: datetime | None = None

    # Metadata
    created_by: str | None = None
    tags: builtins.list[str] = field(default_factory=list)

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert execution to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime objects
        datetime_fields = [
            "started_at",
            "completed_at",
            "timeout_at",
            "compensation_started_at",
            "compensation_completed_at",
        ]
        for field_name in datetime_fields:
            if getattr(self, field_name):
                data[field_name] = getattr(self, field_name).isoformat()

        # Convert steps
        data["steps"] = [step.to_dict() for step in self.steps]
        return data

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "SagaExecution":
        """Create execution from dictionary."""
        # Convert datetime fields
        datetime_fields = [
            "started_at",
            "completed_at",
            "timeout_at",
            "compensation_started_at",
            "compensation_completed_at",
        ]
        for field_name in datetime_fields:
            if data.get(field_name):
                data[field_name] = datetime.fromisoformat(data[field_name])

        # Convert steps
        if data.get("steps"):
            data["steps"] = [
                SagaStep.from_dict(step_data) for step_data in data["steps"]
            ]

        return cls(**data)


class SagaStore(ABC):
    """Abstract base class for saga state persistence."""

    @abstractmethod
    async def save_execution(self, execution: SagaExecution) -> bool:
        """Save saga execution state."""
        pass

    @abstractmethod
    async def load_execution(self, execution_id: str) -> SagaExecution | None:
        """Load saga execution state."""
        pass

    @abstractmethod
    async def list_executions(
        self, status: SagaStatus | None = None, limit: int = 100
    ) -> builtins.list[SagaExecution]:
        """List saga executions."""
        pass

    @abstractmethod
    async def delete_execution(self, execution_id: str) -> bool:
        """Delete saga execution."""
        pass

    @abstractmethod
    async def save_definition(self, definition: SagaDefinition) -> bool:
        """Save saga definition."""
        pass

    @abstractmethod
    async def load_definition(self, name: str) -> SagaDefinition | None:
        """Load saga definition."""
        pass

    @abstractmethod
    async def list_definitions(self) -> builtins.list[SagaDefinition]:
        """List saga definitions."""
        pass


class MemorySagaStore(SagaStore):
    """In-memory saga store for development and testing."""

    def __init__(self):
        self._executions: builtins.dict[str, SagaExecution] = {}
        self._definitions: builtins.dict[str, SagaDefinition] = {}

    async def save_execution(self, execution: SagaExecution) -> bool:
        """Save saga execution state."""
        self._executions[execution.id] = execution
        return True

    async def load_execution(self, execution_id: str) -> SagaExecution | None:
        """Load saga execution state."""
        return self._executions.get(execution_id)

    async def list_executions(
        self, status: SagaStatus | None = None, limit: int = 100
    ) -> builtins.list[SagaExecution]:
        """List saga executions."""
        executions = list(self._executions.values())
        if status:
            executions = [e for e in executions if e.status == status]
        return executions[:limit]

    async def delete_execution(self, execution_id: str) -> bool:
        """Delete saga execution."""
        if execution_id in self._executions:
            del self._executions[execution_id]
            return True
        return False

    async def save_definition(self, definition: SagaDefinition) -> bool:
        """Save saga definition."""
        self._definitions[definition.name] = definition
        return True

    async def load_definition(self, name: str) -> SagaDefinition | None:
        """Load saga definition."""
        return self._definitions.get(name)

    async def list_definitions(self) -> builtins.list[SagaDefinition]:
        """List saga definitions."""
        return list(self._definitions.values())


class SagaOrchestrator:
    """Main saga orchestrator for managing distributed transactions."""

    def __init__(
        self, store: SagaStore, http_client: httpx.AsyncClient | None = None
    ):
        self.store = store
        self.http_client = http_client or httpx.AsyncClient(timeout=30.0)
        self.tracer = trace.get_tracer(__name__)
        self._running_sagas: builtins.dict[str, asyncio.Task] = {}

    async def register_saga(self, definition: SagaDefinition) -> bool:
        """Register a saga definition."""
        errors = definition.validate()
        if errors:
            raise ValueError(f"Invalid saga definition: {', '.join(errors)}")

        success = await self.store.save_definition(definition)
        if success:
            logger.info(
                "Saga definition registered",
                saga_name=definition.name,
                version=definition.version,
            )
        return success

    async def start_saga(
        self,
        saga_name: str,
        context: builtins.dict[str, Any] = None,
        correlation_id: str = None,
        user_id: str = None,
    ) -> str:
        """Start saga execution."""
        definition = await self.store.load_definition(saga_name)
        if not definition:
            raise ValueError(f"Saga definition '{saga_name}' not found")

        execution_id = str(uuid.uuid4())
        execution = SagaExecution(
            id=execution_id,
            saga_name=saga_name,
            status=SagaStatus.PENDING,
            steps=[SagaStep(**asdict(step)) for step in definition.steps],
            context=context or {},
            correlation_id=correlation_id,
            user_id=user_id,
            timeout_at=datetime.utcnow() + timedelta(seconds=definition.timeout),
        )

        await self.store.save_execution(execution)

        # Start saga execution as background task
        task = asyncio.create_task(self._execute_saga(execution_id, definition))
        self._running_sagas[execution_id] = task

        saga_executions_total.labels(status="started", saga_type=saga_name).inc()
        active_sagas_gauge.inc()

        logger.info(
            "Saga execution started",
            execution_id=execution_id,
            saga_name=saga_name,
            correlation_id=correlation_id,
        )

        return execution_id

    async def get_execution(self, execution_id: str) -> SagaExecution | None:
        """Get saga execution by ID."""
        return await self.store.load_execution(execution_id)

    async def cancel_saga(self, execution_id: str) -> bool:
        """Cancel running saga execution."""
        execution = await self.store.load_execution(execution_id)
        if not execution:
            return False

        if execution.status in [
            SagaStatus.COMPLETED,
            SagaStatus.FAILED,
            SagaStatus.COMPENSATED,
        ]:
            return False

        # Cancel running task
        if execution_id in self._running_sagas:
            task = self._running_sagas[execution_id]
            task.cancel()
            del self._running_sagas[execution_id]

        # Start compensation
        definition = await self.store.load_definition(execution.saga_name)
        if definition:
            await self._compensate_saga(execution, definition)

        return True

    async def _execute_saga(self, execution_id: str, definition: SagaDefinition):
        """Execute saga with proper error handling and state management."""
        execution = await self.store.load_execution(execution_id)
        if not execution:
            return

        try:
            with self.tracer.start_as_current_span(
                f"saga_execution_{execution.saga_name}"
            ) as span:
                span.set_attribute("saga.id", execution_id)
                span.set_attribute("saga.name", execution.saga_name)

                execution.status = SagaStatus.RUNNING
                execution.started_at = datetime.utcnow()
                await self.store.save_execution(execution)

                logger.info("Saga execution started", execution_id=execution_id)

                # Execute steps according to execution order
                execution_order = definition.get_execution_order()

                for step_batch in execution_order:
                    # Check for timeout
                    if (
                        execution.timeout_at
                        and datetime.utcnow() > execution.timeout_at
                    ):
                        raise TimeoutError("Saga execution timeout")

                    # Execute steps in batch (parallel if multiple steps)
                    if len(step_batch) == 1:
                        await self._execute_step(execution, step_batch[0])
                    else:
                        tasks = [
                            self._execute_step(execution, step_name)
                            for step_name in step_batch
                        ]
                        await asyncio.gather(*tasks)

                    await self.store.save_execution(execution)

                # All steps completed successfully
                execution.status = SagaStatus.COMPLETED
                execution.completed_at = datetime.utcnow()
                await self.store.save_execution(execution)

                saga_executions_total.labels(
                    status="completed", saga_type=execution.saga_name
                ).inc()
                logger.info("Saga execution completed", execution_id=execution_id)

        except Exception as e:
            logger.error(
                "Saga execution failed", execution_id=execution_id, error=str(e)
            )
            execution.status = SagaStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.utcnow()
            await self.store.save_execution(execution)

            # Start compensation
            await self._compensate_saga(execution, definition)

            saga_executions_total.labels(
                status="failed", saga_type=execution.saga_name
            ).inc()

        finally:
            active_sagas_gauge.dec()
            if execution_id in self._running_sagas:
                del self._running_sagas[execution_id]

    async def _execute_step(self, execution: SagaExecution, step_name: str):
        """Execute individual saga step."""
        step = next((s for s in execution.steps if s.name == step_name), None)
        if not step:
            raise ValueError(f"Step '{step_name}' not found in execution")

        if step.status != StepStatus.PENDING:
            return

        # Check dependencies
        for dep_name in step.depends_on:
            dep_step = next((s for s in execution.steps if s.name == dep_name), None)
            if not dep_step or dep_step.status != StepStatus.COMPLETED:
                raise ValueError(
                    f"Step '{step_name}' dependency '{dep_name}' not satisfied"
                )

        # Check condition if specified
        if step.condition and not self._evaluate_condition(
            step.condition, execution.context
        ):
            step.status = StepStatus.SKIPPED
            logger.info(
                "Step skipped due to condition",
                step_name=step_name,
                condition=step.condition,
            )
            return

        with self.tracer.start_as_current_span(f"saga_step_{step_name}") as span:
            span.set_attribute("step.name", step_name)
            span.set_attribute("step.service_url", step.service_url)

            step.status = StepStatus.RUNNING
            step.started_at = datetime.utcnow()

            success = False
            last_error = None

            # Retry logic
            for attempt in range(step.retries + 1):
                try:
                    step.attempt_count = attempt + 1

                    # Prepare request
                    headers = {**step.headers}
                    if execution.correlation_id:
                        headers["X-Correlation-ID"] = execution.correlation_id
                    if execution.user_id:
                        headers["X-User-ID"] = execution.user_id

                    # Execute HTTP request
                    start_time = datetime.utcnow()

                    response = await self.http_client.request(
                        method=step.method,
                        url=step.service_url,
                        json=step.payload,
                        headers=headers,
                        timeout=step.timeout,
                    )

                    duration = (datetime.utcnow() - start_time).total_seconds()
                    saga_step_duration.labels(
                        step_name=step_name, saga_type=execution.saga_name
                    ).observe(duration)

                    response.raise_for_status()

                    # Step completed successfully
                    step.status = StepStatus.COMPLETED
                    step.completed_at = datetime.utcnow()
                    step.response = response.json() if response.content else {}

                    # Update execution context with response data
                    if step.response:
                        execution.context[f"{step_name}_response"] = step.response

                    success = True
                    logger.info(
                        "Step completed successfully",
                        step_name=step_name,
                        duration=duration,
                        status_code=response.status_code,
                    )
                    break

                except Exception as e:
                    last_error = str(e)
                    saga_retry_total.labels(
                        step_name=step_name, saga_type=execution.saga_name
                    ).inc()
                    logger.warning(
                        "Step execution failed",
                        step_name=step_name,
                        attempt=attempt + 1,
                        error=last_error,
                    )

                    if attempt < step.retries:
                        delay = step.retry_delay * (
                            step.retry_backoff_factor**attempt
                        )
                        await asyncio.sleep(delay)

            if not success:
                step.status = StepStatus.FAILED
                step.error = last_error
                step.completed_at = datetime.utcnow()
                execution.failed_step = step_name

                if step.required:
                    raise Exception(f"Required step '{step_name}' failed: {last_error}")
                else:
                    logger.warning(
                        "Optional step failed", step_name=step_name, error=last_error
                    )

    async def _compensate_saga(
        self, execution: SagaExecution, definition: SagaDefinition
    ):
        """Execute compensation for failed saga."""
        if execution.status == SagaStatus.COMPENSATING:
            return  # Already compensating

        execution.status = SagaStatus.COMPENSATING
        execution.compensation_started_at = datetime.utcnow()
        await self.store.save_execution(execution)

        logger.info("Starting saga compensation", execution_id=execution.id)

        try:
            # Get steps that need compensation (completed steps)
            steps_to_compensate = [
                step
                for step in execution.steps
                if step.status == StepStatus.COMPLETED and step.compensation_url
            ]

            if definition.compensation_mode == CompensationMode.REVERSE:
                steps_to_compensate.reverse()
            elif definition.compensation_mode == CompensationMode.PARALLEL:
                # Execute all compensations in parallel
                tasks = [
                    self._compensate_step(execution, step)
                    for step in steps_to_compensate
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
            else:  # FORWARD
                for step in steps_to_compensate:
                    await self._compensate_step(execution, step)

            execution.status = SagaStatus.COMPENSATED
            execution.compensation_completed_at = datetime.utcnow()

            logger.info("Saga compensation completed", execution_id=execution.id)

        except Exception as e:
            logger.error(
                "Saga compensation failed", execution_id=execution.id, error=str(e)
            )
            execution.error = f"Compensation failed: {str(e)}"

        await self.store.save_execution(execution)

    async def _compensate_step(self, execution: SagaExecution, step: SagaStep):
        """Execute compensation for individual step."""
        if not step.compensation_url:
            return

        logger.info(
            "Compensating step",
            step_name=step.name,
            compensation_url=step.compensation_url,
        )

        try:
            # Prepare compensation request
            headers = {**step.compensation_headers}
            if execution.correlation_id:
                headers["X-Correlation-ID"] = execution.correlation_id
            if execution.user_id:
                headers["X-User-ID"] = execution.user_id

            # Add original response to compensation payload
            compensation_payload = {
                **step.compensation_payload,
                "original_response": step.response,
                "execution_id": execution.id,
                "step_name": step.name,
            }

            # Execute compensation with retries
            for attempt in range(step.compensation_retries + 1):
                try:
                    response = await self.http_client.request(
                        method=step.compensation_method,
                        url=step.compensation_url,
                        json=compensation_payload,
                        headers=headers,
                        timeout=step.compensation_timeout,
                    )

                    response.raise_for_status()

                    step.status = StepStatus.COMPENSATED
                    saga_compensation_total.labels(
                        step_name=step.name, saga_type=execution.saga_name
                    ).inc()

                    logger.info(
                        "Step compensation completed",
                        step_name=step.name,
                        status_code=response.status_code,
                    )
                    break

                except Exception as e:
                    if attempt < step.compensation_retries:
                        await asyncio.sleep(1.0 * (2**attempt))  # Exponential backoff
                    else:
                        logger.error(
                            "Step compensation failed",
                            step_name=step.name,
                            error=str(e),
                        )
                        raise

        except Exception as e:
            logger.error("Step compensation failed", step_name=step.name, error=str(e))
            # Continue with other compensations even if one fails

    def _evaluate_condition(self, condition: str, context: builtins.dict[str, Any]) -> bool:
        """Evaluate step condition using simple expression evaluation."""
        # Simple condition evaluation - can be extended with more sophisticated logic
        try:
            # Replace context variables in condition
            for key, value in context.items():
                condition = condition.replace(f"${key}", json.dumps(value))

            # Evaluate simple conditions (extend as needed)
            return eval(condition)
        except Exception:
            return True  # Default to true if evaluation fails


# FastAPI application
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting Saga Orchestrator")

    # Initialize tracing
    if app.state.config.get("tracing_enabled", False):
        trace.set_tracer_provider(TracerProvider())
        jaeger_exporter = JaegerExporter(
            agent_host_name=app.state.config.get("jaeger_host", "localhost"),
            agent_port=app.state.config.get("jaeger_port", 6831),
        )
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)

        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

    yield

    # Shutdown
    logger.info("Shutting down Saga Orchestrator")


app = FastAPI(
    title="Saga Orchestrator",
    description="Distributed transaction orchestration for microservices",
    version=__version__,
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Global state
store = MemorySagaStore()
orchestrator = SagaOrchestrator(store)

# Configuration
app.state.config = {
    "tracing_enabled": False,
    "jaeger_host": "localhost",
    "jaeger_port": 6831,
}


# Pydantic models for API
class SagaStepRequest(BaseModel):
    name: str
    service_url: str
    method: str = "POST"
    payload: builtins.dict[str, Any] = {}
    headers: builtins.dict[str, str] = {}
    timeout: int = Field(30, ge=1, le=300)
    retries: int = Field(3, ge=0, le=10)
    retry_delay: float = Field(1.0, ge=0.1, le=60.0)
    retry_backoff_factor: float = Field(2.0, ge=1.0, le=5.0)

    compensation_url: str | None = None
    compensation_method: str = "POST"
    compensation_payload: builtins.dict[str, Any] = {}
    compensation_headers: builtins.dict[str, str] = {}
    compensation_timeout: int = Field(30, ge=1, le=300)
    compensation_retries: int = Field(3, ge=0, le=10)

    depends_on: builtins.list[str] = []
    condition: str | None = None
    required: bool = True


class SagaDefinitionRequest(BaseModel):
    name: str
    steps: builtins.list[SagaStepRequest]
    timeout: int = Field(300, ge=1, le=3600)
    compensation_mode: CompensationMode = CompensationMode.REVERSE
    parallel_execution: bool = False
    max_retries: int = Field(3, ge=0, le=10)
    retry_delay: float = Field(5.0, ge=0.1, le=60.0)
    description: str | None = None
    version: str = "1.0.0"
    tags: builtins.list[str] = []


class SagaStartRequest(BaseModel):
    saga_name: str
    context: builtins.dict[str, Any] = {}
    correlation_id: str | None = None
    user_id: str | None = None


# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": __version__,
        "active_sagas": len(orchestrator._running_sagas),
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/sagas/definitions", status_code=201)
async def register_saga_definition(definition_request: SagaDefinitionRequest):
    """Register a new saga definition."""
    try:
        # Convert request to domain objects
        steps = [
            SagaStep(
                name=step.name,
                service_url=step.service_url,
                method=step.method,
                payload=step.payload,
                headers=step.headers,
                timeout=step.timeout,
                retries=step.retries,
                retry_delay=step.retry_delay,
                retry_backoff_factor=step.retry_backoff_factor,
                compensation_url=step.compensation_url,
                compensation_method=step.compensation_method,
                compensation_payload=step.compensation_payload,
                compensation_headers=step.compensation_headers,
                compensation_timeout=step.compensation_timeout,
                compensation_retries=step.compensation_retries,
                depends_on=step.depends_on,
                condition=step.condition,
                required=step.required,
            )
            for step in definition_request.steps
        ]

        definition = SagaDefinition(
            name=definition_request.name,
            steps=steps,
            timeout=definition_request.timeout,
            compensation_mode=definition_request.compensation_mode,
            parallel_execution=definition_request.parallel_execution,
            max_retries=definition_request.max_retries,
            retry_delay=definition_request.retry_delay,
            description=definition_request.description,
            version=definition_request.version,
            tags=definition_request.tags,
        )

        await orchestrator.register_saga(definition)

        return {
            "message": "Saga definition registered successfully",
            "name": definition.name,
            "version": definition.version,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to register saga: {str(e)}"
        )


@app.get("/api/v1/sagas/definitions")
async def list_saga_definitions():
    """List all saga definitions."""
    definitions = await store.list_definitions()
    return {
        "definitions": [
            {
                "name": d.name,
                "version": d.version,
                "description": d.description,
                "steps_count": len(d.steps),
                "timeout": d.timeout,
                "tags": d.tags,
            }
            for d in definitions
        ]
    }


@app.get("/api/v1/sagas/definitions/{saga_name}")
async def get_saga_definition(saga_name: str):
    """Get saga definition by name."""
    definition = await store.load_definition(saga_name)
    if not definition:
        raise HTTPException(
            status_code=404, detail=f"Saga definition '{saga_name}' not found"
        )

    return {
        "name": definition.name,
        "version": definition.version,
        "description": definition.description,
        "timeout": definition.timeout,
        "compensation_mode": definition.compensation_mode.value,
        "parallel_execution": definition.parallel_execution,
        "steps": [step.to_dict() for step in definition.steps],
        "tags": definition.tags,
    }


@app.post("/api/v1/sagas/executions", status_code=201)
async def start_saga_execution(start_request: SagaStartRequest):
    """Start saga execution."""
    try:
        execution_id = await orchestrator.start_saga(
            saga_name=start_request.saga_name,
            context=start_request.context,
            correlation_id=start_request.correlation_id,
            user_id=start_request.user_id,
        )

        return {
            "message": "Saga execution started",
            "execution_id": execution_id,
            "saga_name": start_request.saga_name,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start saga: {str(e)}")


@app.get("/api/v1/sagas/executions/{execution_id}")
async def get_saga_execution(execution_id: str):
    """Get saga execution by ID."""
    execution = await orchestrator.get_execution(execution_id)
    if not execution:
        raise HTTPException(
            status_code=404, detail=f"Saga execution '{execution_id}' not found"
        )

    return execution.to_dict()


@app.get("/api/v1/sagas/executions")
async def list_saga_executions(status: SagaStatus | None = None, limit: int = 100):
    """List saga executions."""
    executions = await store.list_executions(status=status, limit=limit)
    return {
        "executions": [
            {
                "id": e.id,
                "saga_name": e.saga_name,
                "status": e.status.value,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "correlation_id": e.correlation_id,
                "user_id": e.user_id,
                "failed_step": e.failed_step,
                "error": e.error,
            }
            for e in executions
        ]
    }


@app.delete("/api/v1/sagas/executions/{execution_id}")
async def cancel_saga_execution(execution_id: str):
    """Cancel saga execution."""
    success = await orchestrator.cancel_saga(execution_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Saga execution '{execution_id}' not found or cannot be cancelled",
        )

    return {"message": "Saga execution cancelled"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(),
                },
            },
            "handlers": {
                "default": {
                    "level": "INFO",
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        },
    )
