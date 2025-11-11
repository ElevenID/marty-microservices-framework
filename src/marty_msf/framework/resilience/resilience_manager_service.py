"""
Resilience Manager Service

Service-based resilience management that integrates with the enhanced DI system.
"""

from __future__ import annotations

import asyncio
from typing import Any

from marty_msf.core.base_services import BaseService

from .api import IResilienceManager, ResilienceStrategy
from .service_api import IServiceResilienceManager


class ResilienceManagerService(BaseService):
    """
    Resilience Manager Service with completely isolated implementation.
    Breaks circular dependency by not inheriting from shared interfaces.
    """

    def __init__(self, config: dict[str, Any] = None):
        super().__init__(config or {})
        self._resilience_manager: IServiceResilienceManager | None = None

    async def _on_initialize(self) -> None:
        """Initialize the resilience manager service."""
        # Create configuration from service config
        resilience_config = None

        if self._config:
            resilience_settings = self._config.get("resilience", {})
            if resilience_settings:
                # TODO: Implement ResilienceConfig properly
                pass
                # The configuration code would go here when ResilienceConfig is available

        # Create a minimal resilience manager implementation directly (pure interface approach)
        # This avoids importing consolidated_manager or bootstrap to break circular dependency

        # Create a simple proxy implementation that can be enhanced later
        class BasicResilienceManager(IResilienceManager):
            def __init__(self, config):
                self.config = config
                self._metrics = {"total_operations": 0, "success_count": 0, "failure_count": 0}

            async def execute_resilient(
                self,
                func,
                strategy=ResilienceStrategy.INTERNAL_SERVICE,
                config_override=None,
                operation_name=None,
            ):
                try:
                    result = await func() if asyncio.iscoroutinefunction(func) else func()
                    self._metrics["success_count"] += 1
                    return result
                except Exception:
                    self._metrics["failure_count"] += 1
                    raise
                finally:
                    self._metrics["total_operations"] += 1

            def execute_resilient_sync(self, func, *args, **kwargs):
                try:
                    result = func(*args, **kwargs)
                    self._metrics["success_count"] += 1
                    return result
                except Exception:
                    self._metrics["failure_count"] += 1
                    raise
                finally:
                    self._metrics["total_operations"] += 1

            async def apply_resilience(self, func, *args, **kwargs):
                return await self.execute_resilient(lambda: func(*args, **kwargs))

            def get_metrics(self):
                return self._metrics.copy()

            async def health_check(self):
                return {"status": "healthy", "metrics": self.get_metrics()}

            def reset_metrics(self):
                self._metrics = {"total_operations": 0, "success_count": 0, "failure_count": 0}

            def update_config(self, config):
                self.config = config

        # Use the basic implementation for now
        if resilience_config:
            self._resilience_manager = BasicResilienceManager(resilience_config)  # type: ignore
        else:
            self._resilience_manager = BasicResilienceManager(None)  # type: ignore

    async def _on_shutdown(self) -> None:
        """Shutdown the resilience manager service."""
        if self._resilience_manager:
            # Reset metrics and cleanup
            if hasattr(self._resilience_manager, "reset_metrics"):
                self._resilience_manager.reset_metrics()  # type: ignore
            self._resilience_manager = None

    def get_manager(self):
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


# DI registration can be moved to a separate module to avoid circular dependencies
# The registration is commented out to prevent circular dependency issues
# To register this service, use: register_service in your application bootstrap
#
# from marty_msf.core.enhanced_di import LambdaFactory, register_service
# register_service(
#     ResilienceManagerService,
#     factory=LambdaFactory(ResilienceManagerService, _create_resilience_manager_service),
#     is_singleton=True
# )
