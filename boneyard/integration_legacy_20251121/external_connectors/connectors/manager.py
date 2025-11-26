"""External system manager for coordinating multiple connectors."""

import builtins
import logging
from collections import defaultdict
from typing import Any

from ..base import ExternalSystemConnector
from ..config import IntegrationRequest, IntegrationResponse


class ExternalSystemManager:
    """Manager for external system integrations."""

    def __init__(self):
        """Initialize external system manager."""
        self.connectors: builtins.dict[str, ExternalSystemConnector] = {}
        self.active_connections: builtins.dict[str, bool] = {}
        self.system_metrics: builtins.dict[str, builtins.dict[str, Any]] = defaultdict(dict)

    def register_connector(self, system_id: str, connector: ExternalSystemConnector) -> bool:
        """Register external system connector."""
        try:
            self.connectors[system_id] = connector
            self.active_connections[system_id] = False
            logging.info(f"Registered connector for system: {system_id}")
            return True
        except Exception as e:
            logging.exception(f"Failed to register connector for {system_id}: {e}")
            return False

    async def connect_system(self, system_id: str) -> bool:
        """Connect to external system."""
        if system_id not in self.connectors:
            logging.error(f"No connector registered for system: {system_id}")
            return False

        try:
            connector = self.connectors[system_id]
            success = await connector.connect()
            self.active_connections[system_id] = success
            return success
        except Exception as e:
            logging.exception(f"Failed to connect to system {system_id}: {e}")
            return False

    async def disconnect_system(self, system_id: str) -> bool:
        """Disconnect from external system."""
        if system_id not in self.connectors:
            logging.error(f"No connector registered for system: {system_id}")
            return False

        try:
            connector = self.connectors[system_id]
            success = await connector.disconnect()
            self.active_connections[system_id] = False
            return success
        except Exception as e:
            logging.exception(f"Failed to disconnect from system {system_id}: {e}")
            return False

    async def execute_integration(
        self, system_id: str, request: IntegrationRequest
    ) -> IntegrationResponse:
        """Execute integration request on specific system."""
        if system_id not in self.connectors:
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=f"No connector registered for system: {system_id}",
                latency_ms=0.0,
            )

        if not self.active_connections.get(system_id, False):
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=f"System {system_id} is not connected",
                latency_ms=0.0,
            )

        try:
            connector = self.connectors[system_id]
            response = await connector.execute_request(request)

            # Update metrics
            self.update_system_metrics(system_id, response)

            return response
        except Exception as e:
            logging.exception(f"Failed to execute integration on system {system_id}: {e}")
            return IntegrationResponse(
                request_id=request.request_id,
                success=False,
                data=None,
                error_message=str(e),
                latency_ms=0.0,
            )

    async def health_check_all(self) -> builtins.dict[str, bool]:
        """Perform health check on all registered systems."""
        health_results = {}

        for system_id, connector in self.connectors.items():
            try:
                health_results[system_id] = await connector.health_check()
            except Exception as e:
                logging.exception(f"Health check failed for system {system_id}: {e}")
                health_results[system_id] = False

        return health_results

    def get_system_metrics(self, system_id: str) -> builtins.dict[str, Any]:
        """Get metrics for specific system."""
        return self.system_metrics.get(system_id, {})

    def get_all_metrics(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Get metrics for all systems."""
        return dict(self.system_metrics)

    def update_system_metrics(self, system_id: str, response: IntegrationResponse) -> None:
        """Update metrics for a system based on response."""
        metrics = self.system_metrics[system_id]

        # Update request counts
        metrics["total_requests"] = metrics.get("total_requests", 0) + 1
        if response.success:
            metrics["successful_requests"] = metrics.get("successful_requests", 0) + 1
        else:
            metrics["failed_requests"] = metrics.get("failed_requests", 0) + 1

        # Update latency metrics
        latencies = metrics.get("latencies", [])
        latencies.append(response.latency_ms)
        if len(latencies) > 100:  # Keep only last 100 latencies
            latencies = latencies[-100:]
        metrics["latencies"] = latencies

        # Calculate average latency
        if latencies:
            metrics["avg_latency_ms"] = sum(latencies) / len(latencies)

        # Calculate success rate
        total = metrics["total_requests"]
        successful = metrics.get("successful_requests", 0)
        metrics["success_rate"] = (successful / total) * 100 if total > 0 else 0.0

    def list_systems(self) -> builtins.list[str]:
        """List all registered system IDs."""
        return list(self.connectors.keys())

    def is_system_connected(self, system_id: str) -> bool:
        """Check if a system is connected."""
        return self.active_connections.get(system_id, False)


def create_external_integration_platform() -> ExternalSystemManager:
    """Create and configure an external integration platform.

    This is a factory function that creates a pre-configured
    ExternalSystemManager with common settings.
    """
    manager = ExternalSystemManager()
    logging.info("Created external integration platform")
    return manager
