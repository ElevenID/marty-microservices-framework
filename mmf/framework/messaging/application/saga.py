"""
Enhanced Saga Integration with Extended Messaging System

Integrates the existing Saga implementation with the new unified event bus
to provide distributed transaction coordination across multiple messaging backends.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from mmf.framework.messaging.domain.extended import (
    MessageMetadata,
    SagaEventBus,
    UnifiedEventBus,
)
from mmf.framework.patterns.event_streaming.saga import (
    Saga,
    SagaManager,
    SagaOrchestrator,
    SagaStatus,
    SagaStep,
)

# from .unified_event_bus import UnifiedEventBusImpl

# Import existing saga components
try:
    SAGA_AVAILABLE = True
except ImportError:
    SAGA_AVAILABLE = False

    # Create placeholder classes for type hints
    class Saga:
        pass

    class SagaOrchestrator:
        pass

    class SagaManager:
        pass

    class SagaStatus:
        pass

    class SagaStep:
        pass

    class EventBus:
        pass

    class CommandBus:
        pass

    class Event:
        pass

    class Command:
        pass


logger = logging.getLogger(__name__)


class EnhancedSagaOrchestrator:
    """Enhanced saga orchestrator using unified event bus."""

    def __init__(self, unified_event_bus: UnifiedEventBus):
        if not SAGA_AVAILABLE:
            raise ImportError("Saga framework not available")

        self.unified_bus = unified_event_bus
        self.saga_event_bus = SagaEventBus(unified_event_bus)
        self._active_sagas: dict[str, Saga] = {}
        self._saga_types: dict[str, type[Saga]] = {}
        self._step_handlers: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the enhanced saga orchestrator."""
        await self.unified_bus.start()

        # Subscribe to saga events
        await self.unified_bus.subscribe_to_events(
            event_types=["saga.*"], handler=self._handle_saga_event
        )

        logger.info("Enhanced saga orchestrator started")

    async def stop(self):
        """Stop the enhanced saga orchestrator."""
        await self.unified_bus.stop()
        logger.info("Enhanced saga orchestrator stopped")

    def register_saga_type(self, saga_name: str, saga_class: type[Saga]):
        """Register a saga type."""
        self._saga_types[saga_name] = saga_class
        logger.info(f"Registered saga type: {saga_name}")

    def register_step_handler(self, step_name: str, handler: Any):
        """Register a step handler for saga execution."""
        self._step_handlers[step_name] = handler
        logger.info(f"Registered step handler: {step_name}")

    async def start_saga(self, saga_name: str, context: dict[str, Any]) -> str:
        """Start a new saga."""
        if saga_name not in self._saga_types:
            raise ValueError(f"Unknown saga type: {saga_name}")

        saga_class = self._saga_types[saga_name]
        saga = saga_class()

        # Initialize saga context
        saga.context.update(context)

        async with self._lock:
            self._active_sagas[saga.saga_id] = saga

        # Publish saga started event
        await self.saga_event_bus.publish_saga_event(
            saga_id=saga.saga_id,
            event_type="SagaStarted",
            event_data={
                "saga_name": saga_name,
                "context": context,
                "started_at": datetime.utcnow().isoformat(),
            },
        )

        # Start saga execution
        asyncio.create_task(self._execute_saga(saga))

        logger.info(f"Started saga: {saga_name} with ID: {saga.saga_id}")
        return saga.saga_id

    async def _execute_saga(self, saga: Saga):
        """Execute saga steps."""
        try:
            saga.status = SagaStatus.RUNNING

            for step in saga.steps:
                if saga.status != SagaStatus.RUNNING:
                    break

                success = await self._execute_step(saga, step)

                if not success:
                    # Start compensation
                    await self._compensate_saga(saga)
                    return

            # All steps completed successfully
            saga.status = SagaStatus.COMPLETED
            saga.completed_at = datetime.utcnow()

            await self.saga_event_bus.publish_saga_event(
                saga_id=saga.saga_id, event_type="SagaCompleted", event_data=saga.get_saga_state()
            )

        except Exception as e:
            logger.error(f"Error executing saga {saga.saga_id}: {e}")
            saga.status = SagaStatus.FAILED
            saga.completed_at = datetime.utcnow()

            await self.saga_event_bus.publish_saga_event(
                saga_id=saga.saga_id,
                event_type="SagaFailed",
                event_data={"error": str(e), "saga_state": saga.get_saga_state()},
            )

        finally:
            # Remove from active sagas
            async with self._lock:
                if saga.saga_id in self._active_sagas:
                    del self._active_sagas[saga.saga_id]

    async def _execute_step(self, saga: Saga, step: SagaStep) -> bool:
        """Execute a single saga step."""
        try:
            step.started_at = datetime.utcnow()
            step.status = "running"

            # Publish step started event
            await self.saga_event_bus.publish_saga_event(
                saga_id=saga.saga_id,
                event_type="StepStarted",
                event_data={"step_name": step.step_name, "step_order": step.step_order},
                step_id=step.step_id,
            )

            # Execute step
            if step.step_name in self._step_handlers:
                handler = self._step_handlers[step.step_name]
                result = await handler(saga, step)
            else:
                # Send command for step execution
                result = await self._execute_step_via_command(saga, step)

            if result:
                step.status = "completed"
                step.completed_at = datetime.utcnow()

                await self.saga_event_bus.publish_saga_event(
                    saga_id=saga.saga_id,
                    event_type="StepCompleted",
                    event_data={
                        "step_name": step.step_name,
                        "step_order": step.step_order,
                        "result": result,
                    },
                    step_id=step.step_id,
                )
                return True
            else:
                step.status = "failed"
                step.completed_at = datetime.utcnow()

                await self.saga_event_bus.publish_saga_event(
                    saga_id=saga.saga_id,
                    event_type="StepFailed",
                    event_data={
                        "step_name": step.step_name,
                        "step_order": step.step_order,
                        "error": "Step execution failed",
                    },
                    step_id=step.step_id,
                )
                return False

        except Exception as e:
            logger.error(f"Error executing step {step.step_name}: {e}")
            step.status = "failed"
            step.completed_at = datetime.utcnow()

            await self.saga_event_bus.publish_saga_event(
                saga_id=saga.saga_id,
                event_type="StepFailed",
                event_data={
                    "step_name": step.step_name,
                    "step_order": step.step_order,
                    "error": str(e),
                },
                step_id=step.step_id,
            )
            return False

    async def _execute_step_via_command(self, saga: Saga, step: SagaStep) -> bool:
        """Execute step by sending command to appropriate service."""
        try:
            # Determine target service from step configuration
            target_service = step.options.get("service", "default")
            command_type = step.options.get("command", step.step_name)

            # Prepare command data
            command_data = {
                "saga_id": saga.saga_id,
                "step_id": step.step_id,
                "context": saga.context,
                "step_data": step.options.get("data", {}),
            }

            # Send command and wait for result
            result = await self.unified_bus.query(
                query_type=command_type,
                data=command_data,
                target_service=target_service,
                timeout=timedelta(seconds=step.options.get("timeout", 30)),
            )

            return result.get("success", False) if result else False

        except Exception as e:
            logger.error(f"Error executing step {step.step_name} via command: {e}")
            return False

    async def _compensate_saga(self, saga: Saga):
        """Execute compensation for failed saga."""
        try:
            saga.status = SagaStatus.COMPENSATING

            await self.saga_event_bus.publish_saga_event(
                saga_id=saga.saga_id,
                event_type="SagaCompensating",
                event_data=saga.get_saga_state(),
            )

            # Execute compensation in reverse order
            for step in reversed(saga.steps):
                if step.status == "completed":
                    await self._compensate_step(saga, step)

            saga.status = SagaStatus.COMPENSATED
            saga.completed_at = datetime.utcnow()

            await self.saga_event_bus.publish_saga_event(
                saga_id=saga.saga_id, event_type="SagaCompensated", event_data=saga.get_saga_state()
            )

        except Exception as e:
            logger.error(f"Error compensating saga {saga.saga_id}: {e}")
            saga.status = SagaStatus.FAILED

    async def _compensate_step(self, saga: Saga, step: SagaStep):
        """Compensate a completed step."""
        try:
            compensation_command = step.options.get("compensation_command")
            if not compensation_command:
                logger.warning(f"No compensation defined for step: {step.step_name}")
                return

            target_service = step.options.get("service", "default")

            # Prepare compensation data
            compensation_data = {
                "saga_id": saga.saga_id,
                "step_id": step.step_id,
                "context": saga.context,
                "original_step_data": step.options.get("data", {}),
            }

            # Send compensation command
            await self.unified_bus.send_command(
                command_type=compensation_command,
                data=compensation_data,
                target_service=target_service,
            )

            await self.saga_event_bus.publish_saga_event(
                saga_id=saga.saga_id,
                event_type="StepCompensated",
                event_data={
                    "step_name": step.step_name,
                    "compensation_command": compensation_command,
                },
                step_id=step.step_id,
            )

        except Exception as e:
            logger.error(f"Error compensating step {step.step_name}: {e}")

    async def _handle_saga_event(
        self, event_type: str, data: Any, metadata: MessageMetadata
    ) -> bool:
        """Handle saga-related events."""
        try:
            # Process saga events for monitoring, logging, etc.
            logger.debug(f"Received saga event: {event_type}")

            # You can add custom saga event processing here
            # For example: updating saga state in database, sending notifications, etc.

            return True

        except Exception as e:
            logger.error(f"Error handling saga event {event_type}: {e}")
            return False

    async def cancel_saga(self, saga_id: str) -> bool:
        """Cancel a running saga."""
        async with self._lock:
            if saga_id not in self._active_sagas:
                return False

            saga = self._active_sagas[saga_id]
            if saga.status == SagaStatus.RUNNING:
                saga.status = SagaStatus.CANCELLED

                await self.saga_event_bus.publish_saga_event(
                    saga_id=saga_id, event_type="SagaCancelled", event_data=saga.get_saga_state()
                )

                # Start compensation for cancelled saga
                await self._compensate_saga(saga)
                return True

        return False

    async def get_saga_status(self, saga_id: str) -> dict[str, Any] | None:
        """Get current status of a saga."""
        async with self._lock:
            if saga_id in self._active_sagas:
                saga = self._active_sagas[saga_id]
                return saga.get_saga_state()

        return None


class DistributedSagaManager:
    """Distributed saga manager using multiple messaging backends."""

    def __init__(self, unified_event_bus: UnifiedEventBus):
        self.orchestrator = EnhancedSagaOrchestrator(unified_event_bus)
        self._saga_registry: dict[str, dict] = {}

    async def start(self):
        """Start the distributed saga manager."""
        await self.orchestrator.start()
        logger.info("Distributed saga manager started")

    async def stop(self):
        """Stop the distributed saga manager."""
        await self.orchestrator.stop()
        logger.info("Distributed saga manager stopped")

    def register_saga(
        self,
        saga_name: str,
        saga_class: type[Saga],
        description: str = "",
        use_cases: list[str] = None,
    ):
        """Register a saga with metadata."""
        self.orchestrator.register_saga_type(saga_name, saga_class)

        self._saga_registry[saga_name] = {
            "class": saga_class,
            "description": description,
            "use_cases": use_cases or [],
            "registered_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"Registered distributed saga: {saga_name}")

    def register_step_handler(self, step_name: str, handler: Any, service_name: str = ""):
        """Register step handler with service information."""
        self.orchestrator.register_step_handler(step_name, handler)
        logger.info(f"Registered step handler: {step_name} for service: {service_name}")

    async def create_and_start_saga(self, saga_name: str, context: dict[str, Any]) -> str:
        """Create and start a new distributed saga."""
        if saga_name not in self._saga_registry:
            raise ValueError(f"Unknown saga: {saga_name}")

        saga_id = await self.orchestrator.start_saga(saga_name, context)
        logger.info(f"Started distributed saga: {saga_name} with ID: {saga_id}")
        return saga_id

    async def cancel_saga(self, saga_id: str) -> bool:
        """Cancel a distributed saga."""
        return await self.orchestrator.cancel_saga(saga_id)

    async def get_saga_status(self, saga_id: str) -> dict[str, Any] | None:
        """Get distributed saga status."""
        return await self.orchestrator.get_saga_status(saga_id)

    def get_registered_sagas(self) -> dict[str, dict]:
        """Get all registered sagas."""
        return self._saga_registry.copy()


def create_distributed_saga_manager(
    unified_event_bus: UnifiedEventBus,
) -> DistributedSagaManager:
    """Factory function to create distributed saga manager."""
    return DistributedSagaManager(unified_event_bus)
