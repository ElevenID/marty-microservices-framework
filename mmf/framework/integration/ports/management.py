"""
Integration Management Ports
"""

from abc import ABC, abstractmethod
from typing import Any

from mmf.framework.integration.domain.models import (
    CircuitBreakerStatus,
    ConnectionConfig,
)


class ConnectorManagementPort(ABC):
    """Port for managing connectors."""

    @abstractmethod
    async def register_connector(self, config: ConnectionConfig) -> bool:
        """Register a new connector configuration."""

    @abstractmethod
    async def get_connector_status(self, system_id: str) -> dict[str, Any]:
        """Get status of a connector."""

    @abstractmethod
    async def get_circuit_breaker_status(self, system_id: str) -> CircuitBreakerStatus:
        """Get circuit breaker status."""

    @abstractmethod
    async def reset_circuit_breaker(self, system_id: str) -> None:
        """Reset circuit breaker for a system."""
