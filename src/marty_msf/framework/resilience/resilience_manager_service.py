"""
Resilience Manager Service

Service-based resilience management that integrates with the enhanced DI system.
"""

from __future__ import annotations

import asyncio
from typing import Any

from marty_msf.core.base_services import BaseService
from marty_msf.core.enhanced_di import LambdaFactory, register_service

from .consolidated_manager import (
    ConsolidatedResilienceConfig,
    ConsolidatedResilienceManager,
)


class ResilienceManagerService(BaseService):
    """Service for managing consolidated resilience operations."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._resilience_manager: ConsolidatedResilienceManager | None = None

    async def _on_initialize(self) -> None:
        """Initialize the resilience manager service."""
        # Create configuration from service config
        resilience_config = None
        service_config = None

        if self._config:
            service_config = self._config

            # Extract resilience-specific configuration
            resilience_settings = self._config.get("resilience", {})
            if resilience_settings:
                resilience_config = ConsolidatedResilienceConfig(
                    # Circuit breaker settings
                    circuit_breaker_enabled=resilience_settings.get("circuit_breaker_enabled", True),
                    circuit_breaker_failure_threshold=resilience_settings.get("circuit_breaker_failure_threshold", 5),
                    circuit_breaker_recovery_timeout=resilience_settings.get("circuit_breaker_recovery_timeout", 60.0),

                    # Retry settings
                    retry_enabled=resilience_settings.get("retry_enabled", True),
                    retry_max_attempts=resilience_settings.get("retry_max_attempts", 3),
                    retry_base_delay=resilience_settings.get("retry_base_delay", 1.0),
                    retry_exponential_base=resilience_settings.get("retry_exponential_base", 2.0),

                    # Timeout settings
                    timeout_enabled=resilience_settings.get("timeout_enabled", True),
                    timeout_seconds=resilience_settings.get("timeout_seconds", 30.0),

                    # Bulkhead settings
                    bulkhead_enabled=resilience_settings.get("bulkhead_enabled", False),
                    bulkhead_max_concurrent=resilience_settings.get("bulkhead_max_concurrent", 100),
                )

        self._resilience_manager = ConsolidatedResilienceManager(resilience_config, service_config)

    async def _on_shutdown(self) -> None:
        """Shutdown the resilience manager service."""
        if self._resilience_manager:
            # Reset metrics and cleanup
            self._resilience_manager.reset_metrics()
            self._resilience_manager = None

    def get_manager(self) -> ConsolidatedResilienceManager:
        """Get the resilience manager instance."""
        if not self._resilience_manager:
            raise RuntimeError("ResilienceManagerService not initialized")
        return self._resilience_manager

    def update_config(self, config: dict[str, Any]) -> None:
        """Update the resilience configuration."""
        self.configure(config)
        if self._resilience_manager and self.is_initialized:
            # Recreate manager with new config
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._reinitialize())
            else:
                loop.run_until_complete(self._reinitialize())

    async def _reinitialize(self) -> None:
        """Reinitialize the service with new configuration."""
        await self._on_shutdown()
        await self._on_initialize()


def _create_resilience_manager_service(config: dict[str, Any]) -> ResilienceManagerService:
    """Factory function for creating resilience manager service."""
    return ResilienceManagerService(config)


# Register the service with the DI container
register_service(
    ResilienceManagerService,
    factory=LambdaFactory(ResilienceManagerService, _create_resilience_manager_service),
    is_singleton=True
)
