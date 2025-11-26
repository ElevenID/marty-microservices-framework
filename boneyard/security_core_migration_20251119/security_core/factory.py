"""Simplified Security Service Factory.

Orchestrates the initialization of security services by delegating to
specialized initializer components and providing a clean public API.
"""

from __future__ import annotations

import logging
from typing import Any

from ..audit_compliance.monitoring import (
    SecurityAnalyticsEngine,
    SecurityEventCollector,
    SecurityMonitoringDashboard,
    SecurityMonitoringSystem,
    SIEMIntegration,
)
from ..core.di_container import (
    get_container,
    get_service,
    get_service_optional,
    register_instance,
)
from .api import IAuthenticator, IAuthorizer, ISecretManager
from .core_initializer import CoreSecurityInitializer
from .health_checker import check_security_services_health as _check_health

# Monitoring initialization will be done inline
from .service_accessor import SecurityServiceAccessor

logger = logging.getLogger(__name__)


class SecurityServiceFactory:
    """Simplified factory that orchestrates security service initialization."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._initialized = False

        # Initialize specialized components
        self._core_initializer = CoreSecurityInitializer(self.config)
        # Monitoring will be initialized inline
        self._service_accessor = SecurityServiceAccessor(self._ensure_initialized)

    def initialize_all_security_services(self) -> None:
        """Initialize and register all security services in the DI container."""
        if self._initialized:
            logger.debug("Security services already initialized")
            return

        logger.info("Initializing all security services...")

        # 1. Initialize core security services
        self._core_initializer.initialize_core_services()

        # 2. Initialize monitoring services
        self._initialize_monitoring_services()

        # 3. Register this factory itself
        register_instance(SecurityServiceFactory, self)

        self._initialized = True
        logger.info("All security services initialized successfully")

    def _initialize_monitoring_services(self) -> None:
        """Initialize monitoring services directly."""
        # Import monitoring classes from audit_compliance

        # Create monitoring components
        event_collector = SecurityEventCollector()
        analytics_engine = SecurityAnalyticsEngine()
        siem_integration = SIEMIntegration()
        dashboard = SecurityMonitoringDashboard()

        # Create the main monitoring system which registers components in DI
        SecurityMonitoringSystem(
            event_collector=event_collector,
            analytics_engine=analytics_engine,
            siem_integration=siem_integration,
            dashboard=dashboard,
        )

    def get_core_security_services(self) -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
        """Get core security services from DI container."""
        return self._service_accessor.get_core_security_services()

    def get_monitoring_system(self) -> SecurityMonitoringSystem:
        """Get the security monitoring system from DI container."""
        return self._service_accessor.get_monitoring_system()

    def get_event_collector(self):
        """Get the security event collector from DI container."""
        return self._service_accessor.get_event_collector()

    def get_analytics_engine(self):
        """Get the security analytics engine from DI container."""
        return self._service_accessor.get_analytics_engine()

    def _ensure_initialized(self) -> None:
        """Ensure security services are initialized."""
        if not self._initialized:
            self.initialize_all_security_services()

    def is_initialized(self) -> bool:
        """Check if security services are initialized."""
        return self._initialized

    def reset(self) -> None:
        """Reset the factory state (primarily for testing)."""
        self._initialized = False


# Module-level convenience functions


def get_security_factory() -> SecurityServiceFactory:
    """Get the global security service factory instance."""
    factory = get_service(SecurityServiceFactory)
    if factory is None:
        factory = SecurityServiceFactory()
        register_instance(SecurityServiceFactory, factory)
    return factory


def initialize_security_services(config: dict[str, Any] | None = None) -> None:
    """Initialize all security services using the factory."""
    factory = get_security_factory()
    if config:
        factory.config.update(config)
    factory.initialize_all_security_services()


def get_security_services() -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
    """Get core security services, initializing if necessary."""
    return get_security_factory().get_core_security_services()


def get_security_monitoring() -> SecurityMonitoringSystem:
    """Get security monitoring system, initializing if necessary."""
    return get_security_factory().get_monitoring_system()


def reset_security_services() -> None:
    """Reset all security services (primarily for testing)."""
    factory = get_service_optional(SecurityServiceFactory)
    if factory:
        factory.reset()

    # Remove the factory from DI container
    container = get_container()
    container.remove(SecurityServiceFactory)


def check_security_services_health() -> dict[str, bool | str]:
    """Check the health of all security services."""
    factory = get_security_factory()
    return _check_health(factory)
