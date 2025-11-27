"""
Event Bus Service for Decorators

Service-based event bus management that integrates with the enhanced DI system.
"""

from __future__ import annotations

from typing import Any

from mmf_new.core.platform.base_services import BaseService
from mmf_new.framework.infrastructure.dependency_injection import (
    LambdaFactory,
    register_service,
)

from .enhanced_event_bus import EnhancedEventBus, KafkaConfig


class EventBusService(BaseService):
    """Service for managing the enhanced event bus."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._event_bus: EnhancedEventBus | None = None

    async def _on_initialize(self) -> None:
        """Initialize the event bus service."""
        kafka_config = KafkaConfig()

        # Override with any provided configuration
        if self._config:
            kafka_config_dict = self._config.get("kafka", {})
            for key, value in kafka_config_dict.items():
                if hasattr(kafka_config, key):
                    setattr(kafka_config, key, value)

        self._event_bus = EnhancedEventBus(kafka_config)
        await self._event_bus.start()

    async def _on_shutdown(self) -> None:
        """Shutdown the event bus service."""
        if self._event_bus:
            await self._event_bus.stop()
            self._event_bus = None

    def get_event_bus(self) -> EnhancedEventBus:
        """Get the event bus instance."""
        if not self._event_bus:
            raise RuntimeError("EventBusService not initialized")
        return self._event_bus


def _create_event_bus_service(config: dict[str, Any]) -> EventBusService:
    """Factory function for creating event bus service."""
    service_config = config.get("event_bus", {}) if config else {}
    return EventBusService(service_config)


# Register the service with the DI container
register_service(
    EventBusService,
    factory=LambdaFactory(EventBusService, _create_event_bus_service),
    is_singleton=True,
)
