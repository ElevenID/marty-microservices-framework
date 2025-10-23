"""Security services access and retrieval.

Provides convenient getter methods for retrieving security services from
the DI container with proper initialization guarantees.
"""

from __future__ import annotations

from ..audit_compliance.monitoring import (
    SecurityAnalyticsEngine,
    SecurityEventCollector,
    SecurityMonitoringSystem,
)
from ..core.di_container import get_service
from .api import IAuthenticator, IAuthorizer, ISecretManager


class SecurityServiceAccessor:
    """Provides access methods for security services with initialization checks."""

    def __init__(self, ensure_initialized_callback) -> None:
        """Initialize with a callback to ensure services are initialized."""
        self._ensure_initialized = ensure_initialized_callback

    def get_core_security_services(self) -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
        """Get core security services from DI container."""
        self._ensure_initialized()
        return (
            get_service(IAuthenticator),
            get_service(IAuthorizer),
            get_service(ISecretManager)
        )

    def get_monitoring_system(self) -> SecurityMonitoringSystem:
        """Get the security monitoring system from DI container."""
        self._ensure_initialized()
        return get_service(SecurityMonitoringSystem)

    def get_event_collector(self) -> SecurityEventCollector:
        """Get the security event collector from DI container."""
        self._ensure_initialized()
        return get_service(SecurityEventCollector)

    def get_analytics_engine(self) -> SecurityAnalyticsEngine:
        """Get the security analytics engine from DI container."""
        self._ensure_initialized()
        return get_service(SecurityAnalyticsEngine)
