"""
Comprehensive tests for Saga Orchestration module.

Tests SagaStatus, StepStatus, CompensationStrategy, SagaContext,
SagaStep, and Saga classes for distributed transaction handling.
"""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf.core.application.base import Command, CommandResult, CommandStatus
from mmf.framework.patterns.event_streaming.saga import (
    CompensationAction,
    CompensationStrategy,
    Saga,
    SagaContext,
    SagaStatus,
    SagaStep,
    StepStatus,
)


class TestSagaStatus:
    """Tests for SagaStatus enum."""

    def test_all_status_values(self):
        """Test all status enum values exist."""
        assert SagaStatus.CREATED.value == "created"
        assert SagaStatus.RUNNING.value == "running"
        assert SagaStatus.COMPLETED.value == "completed"
        assert SagaStatus.FAILED.value == "failed"
        assert SagaStatus.COMPENSATING.value == "compensating"
        assert SagaStatus.COMPENSATED.value == "compensated"
        assert SagaStatus.ABORTED.value == "aborted"

    def test_status_count(self):
        """Test total number of statuses."""
        assert len(SagaStatus) == 7


class TestStepStatus:
    """Tests for StepStatus enum."""

    def test_all_step_status_values(self):
        """Test all step status enum values exist."""
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.EXECUTING.value == "executing"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.COMPENSATING.value == "compensating"
        assert StepStatus.COMPENSATED.value == "compensated"
        assert StepStatus.SKIPPED.value == "skipped"

    def test_step_status_count(self):
        """Test total number of step statuses."""
        assert len(StepStatus) == 7


class TestCompensationStrategy:
    """Tests for CompensationStrategy enum."""

    def test_all_strategy_values(self):
        """Test all compensation strategy enum values exist."""
        assert CompensationStrategy.SEQUENTIAL.value == "sequential"
        assert CompensationStrategy.PARALLEL.value == "parallel"
        assert CompensationStrategy.CUSTOM.value == "custom"

    def test_strategy_count(self):
        """Test total number of strategies."""
        assert len(CompensationStrategy) == 3


class TestSagaContext:
    """Tests for SagaContext dataclass."""

    def test_basic_context(self):
        """Test creating a basic context."""
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
        )

        assert context.saga_id == "saga-123"
        assert context.correlation_id == "corr-456"
        assert context.data == {}
        assert context.metadata == {}

    def test_context_with_data(self):
        """Test creating context with initial data."""
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
            data={"order_id": "order-789"},
            metadata={"source": "api"},
        )

        assert context.data["order_id"] == "order-789"
        assert context.metadata["source"] == "api"

    def test_get_existing_key(self):
        """Test getting existing data key."""
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
            data={"amount": 100},
        )

        assert context.get("amount") == 100

    def test_get_missing_key_default(self):
        """Test getting missing key returns default."""
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
        )

        assert context.get("missing") is None
        assert context.get("missing", "default") == "default"

    def test_set_value(self):
        """Test setting a value."""
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
        )

        context.set("user_id", "user-123")

        assert context.data["user_id"] == "user-123"

    def test_update_data(self):
        """Test updating data with dict."""
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
            data={"existing": "value"},
        )

        context.update({"new": "data", "another": "field"})

        assert context.data["existing"] == "value"
        assert context.data["new"] == "data"
        assert context.data["another"] == "field"

    def test_to_dict(self):
        """Test converting context to dictionary."""
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
            data={"key": "value"},
            metadata={"meta": "info"},
        )

        result = context.to_dict()

        assert result["saga_id"] == "saga-123"
        assert result["correlation_id"] == "corr-456"
        assert result["data"] == {"key": "value"}
        assert result["metadata"] == {"meta": "info"}


class TestCompensationAction:
    """Tests for CompensationAction dataclass."""

    def test_default_compensation_action(self):
        """Test default compensation action values."""
        action = CompensationAction()

        assert action.action_id is not None
        assert action.action_type == ""
        assert action.command is None
        assert action.custom_handler is None
        assert action.parameters == {}
        assert action.retry_count == 0
        assert action.max_retries == 3

    def test_compensation_action_with_parameters(self):
        """Test compensation action with custom parameters."""
        action = CompensationAction(
            action_type="refund",
            parameters={"order_id": "123", "amount": 50.00},
            max_retries=5,
        )

        assert action.action_type == "refund"
        assert action.parameters["order_id"] == "123"
        assert action.max_retries == 5

    async def test_execute_with_custom_handler(self):
        """Test executing compensation with custom handler."""
        handler = AsyncMock(return_value=None)
        action = CompensationAction(
            custom_handler=handler,
            parameters={"key": "value"},
        )

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await action.execute(context)

        assert result is True
        handler.assert_called_once_with(context, {"key": "value"})

    async def test_execute_with_command(self):
        """Test executing compensation with command."""
        # Create mock command
        mock_command = MagicMock(spec=Command)
        mock_command_bus = AsyncMock()
        mock_command_bus.send.return_value = MagicMock(status=CommandStatus.COMPLETED)

        action = CompensationAction(command=mock_command)

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await action.execute(context, mock_command_bus)

        assert result is True
        mock_command_bus.send.assert_called_once_with(mock_command)

    async def test_execute_with_failed_command(self):
        """Test executing compensation with failed command."""
        mock_command = MagicMock(spec=Command)
        mock_command_bus = AsyncMock()
        mock_command_bus.send.return_value = MagicMock(status=CommandStatus.FAILED)

        action = CompensationAction(command=mock_command)

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await action.execute(context, mock_command_bus)

        assert result is False

    async def test_execute_no_action_defined(self):
        """Test executing compensation with no action returns True with warning."""
        action = CompensationAction()

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await action.execute(context)

        # No action defined should return True (skip compensation)
        assert result is True

    async def test_execute_handler_exception(self):
        """Test executing compensation when handler raises exception."""
        handler = AsyncMock(side_effect=ValueError("Handler failed"))
        action = CompensationAction(custom_handler=handler)

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await action.execute(context)

        assert result is False


class TestSagaStep:
    """Tests for SagaStep dataclass."""

    def test_default_saga_step(self):
        """Test default saga step values."""
        step = SagaStep()

        assert step.step_id is not None
        assert step.step_name == ""
        assert step.step_order == 0
        assert step.command is None
        assert step.custom_handler is None
        assert step.compensation_action is None
        assert step.status == StepStatus.PENDING
        assert step.started_at is None
        assert step.completed_at is None
        assert step.max_retries == 3
        assert step.retry_count == 0

    def test_saga_step_with_config(self):
        """Test saga step with custom configuration."""
        step = SagaStep(
            step_name="process_payment",
            step_order=1,
            max_retries=5,
            retry_delay=timedelta(seconds=10),
        )

        assert step.step_name == "process_payment"
        assert step.step_order == 1
        assert step.max_retries == 5
        assert step.retry_delay == timedelta(seconds=10)

    def test_should_execute_no_condition(self):
        """Test should_execute returns True without condition."""
        step = SagaStep(step_name="no_condition")
        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")

        assert step.should_execute(context) is True

    def test_should_execute_condition_true(self):
        """Test should_execute with condition returning True."""
        step = SagaStep(
            step_name="conditional",
            condition=lambda ctx: ctx.get("enabled", False),
        )
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
            data={"enabled": True},
        )

        assert step.should_execute(context) is True

    def test_should_execute_condition_false(self):
        """Test should_execute with condition returning False."""
        step = SagaStep(
            step_name="conditional",
            condition=lambda ctx: ctx.get("enabled", False),
        )
        context = SagaContext(
            saga_id="saga-123",
            correlation_id="corr-456",
            data={"enabled": False},
        )

        assert step.should_execute(context) is False

    async def test_execute_custom_handler_success(self):
        """Test executing step with successful custom handler."""
        handler = AsyncMock(return_value={"result": "success"})
        step = SagaStep(
            step_name="custom_step",
            custom_handler=handler,
        )

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await step.execute(context)

        assert result is True
        assert step.status == StepStatus.COMPLETED
        assert step.result_data == {"result": "success"}
        assert step.started_at is not None
        assert step.completed_at is not None

    async def test_execute_custom_handler_failure(self):
        """Test executing step with failing custom handler."""
        handler = AsyncMock(side_effect=RuntimeError("Step failed"))
        step = SagaStep(
            step_name="failing_step",
            custom_handler=handler,
        )

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await step.execute(context)

        assert result is False
        assert step.status == StepStatus.FAILED
        assert "Step failed" in step.error_message

    async def test_execute_no_action_skipped(self):
        """Test executing step with no action gets skipped."""
        step = SagaStep(step_name="empty_step")

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await step.execute(context)

        assert result is True
        assert step.status == StepStatus.SKIPPED

    async def test_execute_with_command_success(self):
        """Test executing step with successful command."""
        mock_command = MagicMock(spec=Command)
        mock_command.correlation_id = None
        mock_command.metadata = {}

        mock_command_bus = AsyncMock()
        mock_command_bus.send.return_value = MagicMock(
            status=CommandStatus.COMPLETED,
            result_data={"id": "123"},
        )

        step = SagaStep(
            step_name="command_step",
            command=mock_command,
        )

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await step.execute(context, mock_command_bus)

        assert result is True
        assert step.status == StepStatus.COMPLETED
        assert step.result_data == {"id": "123"}

    async def test_execute_with_command_failure(self):
        """Test executing step with failed command."""
        mock_command = MagicMock(spec=Command)
        mock_command.correlation_id = None
        mock_command.metadata = {}

        mock_command_bus = AsyncMock()
        mock_command_bus.send.return_value = MagicMock(
            status=CommandStatus.FAILED,
            error_message="Command failed",
        )

        step = SagaStep(
            step_name="failing_command",
            command=mock_command,
        )

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await step.execute(context, mock_command_bus)

        assert result is False
        assert step.status == StepStatus.FAILED
        assert step.error_message == "Command failed"

    async def test_compensate_with_action(self):
        """Test compensation with action."""
        comp_handler = AsyncMock(return_value=None)
        comp_action = CompensationAction(custom_handler=comp_handler)

        step = SagaStep(
            step_name="compensatable_step",
            compensation_action=comp_action,
        )
        step.status = StepStatus.COMPLETED

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await step.compensate(context)

        assert result is True
        assert step.status == StepStatus.COMPENSATED

    async def test_compensate_without_action(self):
        """Test compensation without action returns True."""
        step = SagaStep(step_name="no_compensation")
        step.status = StepStatus.COMPLETED

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await step.compensate(context)

        assert result is True

    async def test_compensate_action_fails(self):
        """Test compensation when action fails."""
        comp_handler = AsyncMock(side_effect=RuntimeError("Compensation failed"))
        comp_action = CompensationAction(custom_handler=comp_handler)

        step = SagaStep(
            step_name="failing_compensation",
            compensation_action=comp_action,
        )
        step.status = StepStatus.COMPLETED

        context = SagaContext(saga_id="saga-123", correlation_id="corr-456")
        result = await step.compensate(context)

        assert result is False


class SimpleSaga(Saga):
    """Simple test saga implementation."""

    def _initialize_steps(self):
        """Initialize test steps."""
        pass


class TestSaga:
    """Tests for Saga abstract class."""

    def test_saga_creation(self):
        """Test creating a saga."""
        saga = SimpleSaga()

        assert saga.saga_id is not None
        assert saga.correlation_id is not None
        assert saga.status == SagaStatus.CREATED
        assert saga.steps == []
        assert saga.current_step_index == 0
        assert saga.saga_type == "SimpleSaga"
        assert saga.created_at is not None
        assert saga.compensation_strategy == CompensationStrategy.SEQUENTIAL

    def test_saga_with_custom_ids(self):
        """Test creating saga with custom IDs."""
        saga = SimpleSaga(
            saga_id="custom-saga-id",
            correlation_id="custom-corr-id",
        )

        assert saga.saga_id == "custom-saga-id"
        assert saga.correlation_id == "custom-corr-id"

    def test_add_step(self):
        """Test adding a step to saga."""
        saga = SimpleSaga()
        step = SagaStep(step_name="test_step")

        saga.add_step(step)

        assert len(saga.steps) == 1
        assert saga.steps[0] == step
        assert step.step_order == 0

    def test_add_multiple_steps(self):
        """Test adding multiple steps assigns correct order."""
        saga = SimpleSaga()

        step1 = SagaStep(step_name="step1")
        step2 = SagaStep(step_name="step2")
        step3 = SagaStep(step_name="step3")

        saga.add_step(step1)
        saga.add_step(step2)
        saga.add_step(step3)

        assert len(saga.steps) == 3
        assert step1.step_order == 0
        assert step2.step_order == 1
        assert step3.step_order == 2

    def test_create_step(self):
        """Test creating and adding step in one call."""
        saga = SimpleSaga()

        step = saga.create_step(
            step_name="created_step",
            custom_handler=AsyncMock(),
        )

        assert len(saga.steps) == 1
        assert step.step_name == "created_step"
        assert step in saga.steps

    async def test_execute_success(self):
        """Test executing saga successfully."""
        saga = SimpleSaga()

        handler1 = AsyncMock(return_value={"step": 1})
        handler2 = AsyncMock(return_value={"step": 2})

        saga.create_step(step_name="step1", custom_handler=handler1)
        saga.create_step(step_name="step2", custom_handler=handler2)

        mock_command_bus = AsyncMock()
        result = await saga.execute(mock_command_bus)

        assert result is True
        assert saga.status == SagaStatus.COMPLETED
        assert saga.started_at is not None
        assert saga.completed_at is not None
        handler1.assert_called_once()
        handler2.assert_called_once()

    async def test_execute_with_skipped_step(self):
        """Test executing saga with conditional step skipped."""
        saga = SimpleSaga()

        handler1 = AsyncMock(return_value={"step": 1})
        handler2 = AsyncMock(return_value={"step": 2})

        saga.create_step(step_name="always_run", custom_handler=handler1)

        step2 = SagaStep(
            step_name="conditional",
            custom_handler=handler2,
            condition=lambda ctx: ctx.get("run_step2", False),
        )
        saga.add_step(step2)

        mock_command_bus = AsyncMock()
        result = await saga.execute(mock_command_bus)

        assert result is True
        assert saga.status == SagaStatus.COMPLETED
        handler1.assert_called_once()
        handler2.assert_not_called()
        assert step2.status == StepStatus.SKIPPED

    async def test_execute_step_failure_triggers_compensation(self):
        """Test that step failure triggers compensation."""
        saga = SimpleSaga()

        handler1 = AsyncMock(return_value={"step": 1})
        handler2 = AsyncMock(side_effect=RuntimeError("Step 2 failed"))
        comp_handler = AsyncMock(return_value=None)

        comp_action = CompensationAction(custom_handler=comp_handler)
        saga.create_step(
            step_name="step1",
            custom_handler=handler1,
            compensation_action=comp_action,
        )

        step2 = SagaStep(step_name="step2", custom_handler=handler2, max_retries=0)
        saga.add_step(step2)

        mock_command_bus = AsyncMock()
        result = await saga.execute(mock_command_bus)

        assert result is False
        assert saga.status == SagaStatus.COMPENSATED
        comp_handler.assert_called_once()

    async def test_execute_empty_saga(self):
        """Test executing saga with no steps."""
        saga = SimpleSaga()

        mock_command_bus = AsyncMock()
        result = await saga.execute(mock_command_bus)

        assert result is True
        assert saga.status == SagaStatus.COMPLETED

    def test_get_saga_state(self):
        """Test getting saga state."""
        saga = SimpleSaga(saga_id="state-test", correlation_id="corr-state")
        saga.create_step(step_name="test_step")

        state = saga.get_saga_state()

        assert state["saga_id"] == "state-test"
        assert state["saga_type"] == "SimpleSaga"
        assert state["correlation_id"] == "corr-state"
        assert state["status"] == "created"
        assert state["current_step_index"] == 0
        assert len(state["steps"]) == 1
        assert state["steps"][0]["step_name"] == "test_step"


class TestSagaCompensationStrategies:
    """Tests for different compensation strategies."""

    async def test_sequential_compensation(self):
        """Test sequential compensation in reverse order."""
        saga = SimpleSaga()
        saga.compensation_strategy = CompensationStrategy.SEQUENTIAL

        comp_order = []

        async def make_comp_handler(order):
            async def handler(ctx, params):
                comp_order.append(order)

            return handler

        comp1 = CompensationAction(custom_handler=await make_comp_handler(1))
        comp2 = CompensationAction(custom_handler=await make_comp_handler(2))

        saga.create_step(
            step_name="step1",
            custom_handler=AsyncMock(return_value=True),
            compensation_action=comp1,
        )
        saga.create_step(
            step_name="step2",
            custom_handler=AsyncMock(return_value=True),
            compensation_action=comp2,
        )

        # Mark steps as completed
        for step in saga.steps:
            step.status = StepStatus.COMPLETED
        saga.current_step_index = 2

        mock_command_bus = AsyncMock()
        result = await saga._compensate_sequential(mock_command_bus)

        assert result is True
        # Should be in reverse order
        assert comp_order == [2, 1]

    async def test_parallel_compensation(self):
        """Test parallel compensation executes all steps."""
        saga = SimpleSaga()
        saga.compensation_strategy = CompensationStrategy.PARALLEL

        comp_executed = {"comp1": False, "comp2": False}

        async def comp_handler_1(ctx, params):
            comp_executed["comp1"] = True

        async def comp_handler_2(ctx, params):
            comp_executed["comp2"] = True

        comp1 = CompensationAction(custom_handler=comp_handler_1)
        comp2 = CompensationAction(custom_handler=comp_handler_2)

        saga.create_step(
            step_name="step1",
            custom_handler=AsyncMock(return_value=True),
            compensation_action=comp1,
        )
        saga.create_step(
            step_name="step2",
            custom_handler=AsyncMock(return_value=True),
            compensation_action=comp2,
        )

        # Mark steps as completed
        for step in saga.steps:
            step.status = StepStatus.COMPLETED
        saga.current_step_index = 2

        mock_command_bus = AsyncMock()
        result = await saga._compensate_parallel(mock_command_bus)

        assert result is True
        assert comp_executed["comp1"] is True
        assert comp_executed["comp2"] is True


class TestSagaRetryLogic:
    """Tests for saga step retry logic."""

    async def test_step_retries_on_failure(self):
        """Test that step retries on failure."""
        saga = SimpleSaga()

        call_count = 0

        async def flaky_handler(ctx):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Temporary failure")
            return {"success": True}

        step = SagaStep(
            step_name="flaky_step",
            custom_handler=flaky_handler,
            max_retries=3,
            retry_delay=timedelta(milliseconds=1),  # Very short for tests
        )
        saga.add_step(step)

        mock_command_bus = AsyncMock()
        result = await saga.execute(mock_command_bus)

        assert result is True
        assert saga.status == SagaStatus.COMPLETED
        assert call_count == 3

    async def test_step_exhausts_retries(self):
        """Test that step fails after exhausting retries."""
        saga = SimpleSaga()

        call_count = 0

        async def always_fail(ctx):
            nonlocal call_count
            call_count += 1
            raise RuntimeError("Always fails")

        step = SagaStep(
            step_name="always_failing",
            custom_handler=always_fail,
            max_retries=2,
            retry_delay=timedelta(milliseconds=1),
        )
        saga.add_step(step)

        mock_command_bus = AsyncMock()
        result = await saga.execute(mock_command_bus)

        assert result is False
        assert saga.status in [SagaStatus.COMPENSATED, SagaStatus.ABORTED]
        # max_retries=2 means 3 total attempts (initial + 2 retries)
        assert call_count == 3
