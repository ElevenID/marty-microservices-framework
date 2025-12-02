"""
Workflow Engine Application Service.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from mmf.framework.workflow.domain.entities import (
    StepResult,
    StepStatus,
    WorkflowContext,
    WorkflowStatus,
)
from mmf.framework.workflow.domain.ports import WorkflowRepositoryPort

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Orchestrates workflow execution.
    """

    def __init__(self, repository: WorkflowRepositoryPort | None = None):
        self.repository = repository

    async def start_workflow(
        self,
        workflow_id: str,
        steps: list[Callable[[WorkflowContext], Any]],
        initial_data: dict[str, Any] | None = None,
    ) -> WorkflowContext:
        """Start a new workflow execution."""
        context = WorkflowContext(
            workflow_id=workflow_id,
            correlation_id=str(uuid.uuid4()),
            data=initial_data or {},
        )

        if self.repository:
            await self.repository.save_workflow(context, WorkflowStatus.RUNNING)

        try:
            for step in steps:
                # Execute step
                try:
                    if asyncio.iscoroutinefunction(step):
                        _result = await step(context)
                    else:
                        _result = step(context)

                    # Update context with result if needed
                    # This is a simplified implementation

                except Exception as e:
                    logger.error(f"Workflow {workflow_id} failed at step {step.__name__}: {e}")
                    if self.repository:
                        await self.repository.update_status(workflow_id, WorkflowStatus.FAILED)
                    raise

            if self.repository:
                await self.repository.update_status(workflow_id, WorkflowStatus.COMPLETED)

            return context

        except Exception:
            if self.repository:
                await self.repository.update_status(workflow_id, WorkflowStatus.FAILED)
            raise
