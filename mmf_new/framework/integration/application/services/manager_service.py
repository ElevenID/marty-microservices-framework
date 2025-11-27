"""
Connector Manager Service
"""

import logging
from typing import Any

from mmf_new.framework.integration.adapters.database_adapter import DatabaseAdapter
from mmf_new.framework.integration.adapters.filesystem_adapter import FileSystemAdapter
from mmf_new.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf_new.framework.integration.domain.exceptions import (
    CircuitBreakerOpenError,
    ConfigurationError,
)
from mmf_new.framework.integration.domain.models import (
    CircuitBreakerStatus,
    ConnectionConfig,
    ConnectorType,
    IntegrationRequest,
    IntegrationResponse,
)
from mmf_new.framework.integration.domain.services import (
    CircuitBreakerService,
    MetricsTracker,
)
from mmf_new.framework.integration.ports.connector import ExternalSystemPort
from mmf_new.framework.integration.ports.management import ConnectorManagementPort


class ConnectorManagerService(ConnectorManagementPort):
    """Service for managing external system connectors."""

    def __init__(self):
        self._connectors: dict[str, ExternalSystemPort] = {}
        self._configs: dict[str, ConnectionConfig] = {}
        self._circuit_breaker_service = CircuitBreakerService()
        self._metrics_tracker = MetricsTracker()

    async def register_connector(self, config: ConnectionConfig) -> bool:
        """Register a new connector configuration."""
        try:
            if config.system_id in self._connectors:
                logging.warning("Connector %s already exists. Overwriting.", config.system_id)
                await self._connectors[config.system_id].disconnect()

            connector = self._create_connector(config)
            self._connectors[config.system_id] = connector
            self._configs[config.system_id] = config

            logging.info("Registered connector: %s (%s)", config.system_id, config.connector_type)
            return True
        except Exception as e:
            logging.exception("Failed to register connector %s: %s", config.system_id, e)
            raise ConfigurationError(f"Failed to register connector: {e}") from e

    def _create_connector(self, config: ConnectionConfig) -> ExternalSystemPort:
        """Factory method to create connector instance."""
        if config.connector_type == ConnectorType.REST_API:
            return RESTAPIAdapter(config)
        elif config.connector_type == ConnectorType.FILESYSTEM:
            return FileSystemAdapter(config)
        elif config.connector_type == ConnectorType.DATABASE:
            return DatabaseAdapter(config)
        else:
            raise ConfigurationError(f"Unsupported connector type: {config.connector_type}")

    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute request through registered connector."""
        system_id = request.system_id
        if system_id not in self._connectors:
            raise ConfigurationError(f"Connector not found: {system_id}")

        connector = self._connectors[system_id]
        config = self._configs[system_id]

        # Check circuit breaker
        try:
            self._circuit_breaker_service.check_availability(system_id, config)
        except CircuitBreakerOpenError as e:
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                error_code="CIRCUIT_OPEN",
            )

        try:
            response = await connector.execute_request(request)

            # Update metrics and circuit breaker
            self._metrics_tracker.record_request(
                system_id, response.latency_ms or 0.0, response.success
            )

            if response.success:
                self._circuit_breaker_service.record_success(system_id)
            else:
                self._circuit_breaker_service.record_failure(system_id, config)

            return response

        except Exception as e:
            # Record failure for unhandled exceptions
            self._circuit_breaker_service.record_failure(system_id, config)
            self._metrics_tracker.record_request(system_id, 0.0, False)

            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                error_code="EXECUTION_ERROR",
            )

    async def get_connector_status(self, system_id: str) -> dict[str, Any]:
        """Get status of a connector."""
        if system_id not in self._connectors:
            raise ConfigurationError(f"Connector not found: {system_id}")

        connector = self._connectors[system_id]
        cb_status = self._circuit_breaker_service.get_status(system_id)
        metrics = self._metrics_tracker.get_metrics(system_id)

        # Perform health check
        is_healthy = await connector.health_check()

        return {
            "system_id": system_id,
            "healthy": is_healthy,
            "circuit_breaker": {"state": cb_status.state, "failure_count": cb_status.failure_count},
            "metrics": metrics,
        }

    async def get_circuit_breaker_status(self, system_id: str) -> CircuitBreakerStatus:
        """Get circuit breaker status."""
        return self._circuit_breaker_service.get_status(system_id)

    async def reset_circuit_breaker(self, system_id: str) -> None:
        """Reset circuit breaker for a system."""
        if system_id in self._connectors:
            self._circuit_breaker_service.record_success(system_id)
