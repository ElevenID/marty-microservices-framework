"""
Pipeline port interface.
"""

from abc import ABC, abstractmethod
from typing import Any

from mmf_new.framework.deployment.domain.models import DeploymentPipeline, PipelineExecution


class PipelinePort(ABC):
    """Abstract base class for pipeline providers."""

    @abstractmethod
    async def create_pipeline(self, pipeline: DeploymentPipeline) -> bool:
        """Create or update CI/CD pipeline."""

    @abstractmethod
    async def trigger_pipeline(
        self, pipeline_name: str, variables: dict[str, Any] | None = None
    ) -> PipelineExecution:
        """Trigger pipeline execution."""

    @abstractmethod
    async def get_pipeline_status(self, execution_id: str) -> PipelineExecution:
        """Get pipeline execution status."""
