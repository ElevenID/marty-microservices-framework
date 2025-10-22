"""
Service-specific API for resilience manager service.
This is completely separate from api.py to break circular dependencies.
"""

from abc import ABC, abstractmethod
from typing import Any


class IServiceResilienceManager(ABC):
    """Service-specific interface for resilience manager."""

    @abstractmethod
    async def execute_resilient(self, func, **kwargs):
        """Execute a function with resilience patterns."""
        pass

    @abstractmethod
    def execute_resilient_sync(self, func, *args, **kwargs):
        """Execute a function synchronously with resilience patterns."""
        pass

    @abstractmethod
    async def apply_resilience(self, func, *args, **kwargs):
        """Apply resilience patterns to a function."""
        pass

    @abstractmethod
    def get_metrics(self):
        """Get resilience metrics."""
        pass

    @abstractmethod
    async def health_check(self):
        """Check service health."""
        pass
