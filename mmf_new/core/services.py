"""
Core service definitions.

This module provides base classes for core framework services.
"""

from abc import ABC, abstractmethod
from typing import Any


class ObservabilityService(ABC):
    """
    Base class for observability services.
    """

    def __init__(self) -> None:
        self._initialized = False

    @abstractmethod
    def initialize(
        self, service_name: str, config: dict[str, Any] | None = None
    ) -> None:
        """Initialize the observability service."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup resources."""
        pass

    def is_initialized(self) -> bool:
        """Check if the service is initialized."""
        return self._initialized

    def _mark_initialized(self) -> None:
        """Mark service as initialized."""
        self._initialized = True
