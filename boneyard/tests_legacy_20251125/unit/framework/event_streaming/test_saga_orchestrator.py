from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from marty_msf.framework.event_streaming.saga import Saga, SagaOrchestrator, SagaStatus


class ControllableSaga(Saga):
    def __init__(self, *, success: bool = True, raise_error: bool = False):
        self._success = success
        self._raise_error = raise_error
        super().__init__()

    def _initialize_steps(self) -> None:
        """No automatic steps for controllable saga."""

    async def execute(self, command_bus) -> bool:  # noqa: D401
        if self._raise_error:
            raise RuntimeError("boom")

        self.started_at = datetime.utcnow()

        if self._success:
            self.status = SagaStatus.COMPLETED
            self.completed_at = datetime.utcnow()
            return True

        self.status = SagaStatus.FAILED
        self.error_message = "failed"
        self.completed_at = datetime.utcnow()
        return False


@pytest.mark.asyncio
async def test_orchestrator_publishes_success_events() -> None:
    event_bus = SimpleNamespace(publish=AsyncMock())
    orchestrator = SagaOrchestrator(command_bus=object(), event_bus=event_bus)
    saga = ControllableSaga(success=True)

    result = await orchestrator.start_saga(saga)
    assert result is True

    event_types = [call.args[0].event_type for call in event_bus.publish.call_args_list]
    assert event_types == ["SagaStarted", "SagaCompleted"]
    assert await orchestrator.get_saga_status(saga.saga_id) is None


@pytest.mark.asyncio
async def test_orchestrator_emits_failure_event_on_unsuccessful_execution() -> None:
    event_bus = SimpleNamespace(publish=AsyncMock())
    orchestrator = SagaOrchestrator(command_bus=object(), event_bus=event_bus)
    saga = ControllableSaga(success=False)

    result = await orchestrator.start_saga(saga)
    assert result is False

    event_types = [call.args[0].event_type for call in event_bus.publish.call_args_list]
    assert event_types == ["SagaStarted", "SagaFailed"]


@pytest.mark.asyncio
async def test_orchestrator_gracefully_handles_exceptions() -> None:
    event_bus = SimpleNamespace(publish=AsyncMock())
    orchestrator = SagaOrchestrator(command_bus=object(), event_bus=event_bus)
    saga = ControllableSaga(success=True, raise_error=True)

    result = await orchestrator.start_saga(saga)
    assert result is False

    event_types = [call.args[0].event_type for call in event_bus.publish.call_args_list]
    assert event_types == ["SagaStarted", "SagaError"]


@pytest.mark.asyncio
async def test_cancel_saga_publishes_cancelled_event() -> None:
    event_bus = SimpleNamespace(publish=AsyncMock())
    orchestrator = SagaOrchestrator(command_bus=object(), event_bus=event_bus)
    saga = ControllableSaga(success=True)
    saga.status = SagaStatus.RUNNING
    saga.started_at = datetime.utcnow()

    async with orchestrator._lock:
        orchestrator._active_sagas[saga.saga_id] = saga

    cancelled = await orchestrator.cancel_saga(saga.saga_id)
    assert cancelled is True
    assert saga.status == SagaStatus.ABORTED

    event_types = [call.args[0].event_type for call in event_bus.publish.call_args_list]
    assert "SagaCancelled" in event_types
