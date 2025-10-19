"""
OPA Policy Service

Service-based OPA policy management that integrates with the enhanced DI system.
"""

from __future__ import annotations

from typing import Any

from marty_msf.core.base_services import BaseService
from marty_msf.core.enhanced_di import LambdaFactory, register_service
from marty_msf.security.policy_engines import OPAPolicyService as _OPAPolicyService


class OPAPolicyServiceWrapper(BaseService):
    """Service wrapper for OPA policy management."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._policy_service: _OPAPolicyService | None = None

    async def _on_initialize(self) -> None:
        """Initialize the OPA policy service."""
        self._policy_service = _OPAPolicyService(service_config=self._config)
        await self._policy_service.initialize()

    async def _on_shutdown(self) -> None:
        """Shutdown the OPA policy service."""
        if self._policy_service:
            await self._policy_service.close()
            self._policy_service = None

    def get_policy_service(self) -> _OPAPolicyService:
        """Get the OPA policy service instance."""
        if not self._policy_service:
            raise RuntimeError("OPAPolicyServiceWrapper not initialized")
        return self._policy_service


def _create_opa_policy_service(config: dict[str, Any]) -> OPAPolicyServiceWrapper:
    """Factory function for creating OPA policy service."""
    return OPAPolicyServiceWrapper(config)


# Register the service with the DI container
register_service(
    OPAPolicyServiceWrapper,
    factory=LambdaFactory(OPAPolicyServiceWrapper, _create_opa_policy_service),
    is_singleton=True
)
