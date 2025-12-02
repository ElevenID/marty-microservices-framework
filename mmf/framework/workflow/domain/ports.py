"""
Workflow Domain Ports.
"""

from abc import ABC, abstractmethod

from mmf.framework.workflow.domain.entities import WorkflowContext, WorkflowStatus


class WorkflowRepositoryPort(ABC):
    """Interface for workflow persistence."""

    @abstractmethod
    async def save_workflow(self, context: WorkflowContext, status: WorkflowStatus) -> None:
        """Save workflow state."""

    @abstractmethod
    async def get_workflow(self, workflow_id: str) -> tuple[WorkflowContext, WorkflowStatus] | None:
        """Get workflow state."""

    @abstractmethod
    async def update_status(self, workflow_id: str, status: WorkflowStatus) -> None:
        """Update workflow status."""
