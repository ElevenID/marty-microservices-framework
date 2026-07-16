"""
Integration Transformation Ports
"""

from abc import ABC, abstractmethod
from typing import Any


class TransformationPort(ABC):
    """Port for data transformation."""

    @abstractmethod
    async def transform(self, data: Any, transformation_id: str) -> Any:
        """Transform data using specified transformation."""

    @abstractmethod
    async def validate(self, data: Any, schema_id: str) -> bool:
        """Validate data against schema."""
