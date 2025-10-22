"""
Completely isolated resilience manager service.
This module has NO dependencies on other resilience modules to break circular dependency.
"""

from __future__ import annotations

import asyncio
from typing import Any

from marty_msf.core.base_services import BaseService


class IsolatedResilienceManager:
    """Completely isolated resilience manager implementation."""

    def __init__(self, config=None):
        self.config = config
        self._metrics = {"total_operations": 0, "success_count": 0, "failure_count": 0}

    async def execute_resilient(self, func, **kwargs):
        """Execute a function with basic resilience patterns."""
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
        """Execute a function synchronously with resilience patterns."""
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
        """Apply resilience patterns to a function."""
        return await self.execute_resilient(lambda: func(*args, **kwargs))

    def get_metrics(self):
        """Get resilience metrics."""
        return self._metrics.copy()

    async def health_check(self):
        """Check service health."""
        return {"status": "healthy", "metrics": self.get_metrics()}

    def reset_metrics(self):
        """Reset metrics."""
        self._metrics = {"total_operations": 0, "success_count": 0, "failure_count": 0}

    def update_config(self, config):
        """Update configuration."""
        self.config = config


class ResilienceManagerService(BaseService):
    """
    Resilience Manager Service with completely isolated implementation.
    Breaks circular dependency by not importing any other resilience modules.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config or {})
        self._resilience_manager = IsolatedResilienceManager(config)

    async def start(self):
        """Start the resilience service."""
        await super().start()
        if self._resilience_manager:
            self._resilience_manager.reset_metrics()

    def get_manager(self):
        """Get the resilience manager."""
        return self._resilience_manager

    def get_resilience_config(self):
        """Get current resilience configuration."""
        return self._resilience_manager.config if self._resilience_manager else None

    async def apply_resilience_patterns(self, func, *args, **kwargs):
        """Apply resilience patterns to a function."""
        if self._resilience_manager:
            return await self._resilience_manager.apply_resilience(func, *args, **kwargs)
        else:
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)

    def apply_resilience_patterns_sync(self, func, *args, **kwargs):
        """Apply resilience patterns to a synchronous function."""
        if self._resilience_manager:
            return self._resilience_manager.execute_resilient_sync(func, *args, **kwargs)
        else:
            return func(*args, **kwargs)

    async def get_health_status(self):
        """Get health status of the resilience service."""
        if self._resilience_manager:
            return await self._resilience_manager.health_check()
        else:
            return {"status": "unhealthy", "error": "No resilience manager configured"}

    def get_metrics(self):
        """Get resilience metrics."""
        if self._resilience_manager:
            return self._resilience_manager.get_metrics()
        else:
            return {"total_operations": 0, "success_count": 0, "failure_count": 0}


# DI registration can be moved to a separate module to avoid circular dependencies
# The registration is commented out to prevent circular dependency issues
# To register this service, use: register_service in your application bootstrap
#
# from marty_msf.core.enhanced_di import LambdaFactory, register_service
# register_service(
#     ResilienceManagerService,
#     factory=LambdaFactory(ResilienceManagerService, lambda config: ResilienceManagerService(config)),
#     is_singleton=True
# )
