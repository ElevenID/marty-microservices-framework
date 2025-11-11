"""
Security Service Factory

This module provides a centralized factory for creating and registering all security-related
services in the DI container with proper lifecycles and dependencies.

This is the single entry point for initializing the entire security subsystem.
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
    has_service,
    register_factory,
    register_instance,
)
from ..security_core.api import (
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    ICacheManager,
    ISecretManager,
    ISessionManager,
)
from ..security_core.bootstrap import (
    SecurityHardeningFramework,
    create_security_framework,
)

logger = logging.getLogger(__name__)


class SecurityServiceFactory:
    """
    Factory for creating and managing all security services in the DI container.

    This factory ensures that all security components are properly registered
    with correct dependencies and lifecycles.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the security service factory.

        Args:
            config: Optional configuration for security services
        """
        self.config = config or {}
        self._initialized = False

    def initialize_all_security_services(self) -> None:
        """
        Initialize and register all security services in the DI container.

        This method should be called once during application startup.
        """
        if self._initialized:
            logger.debug("Security services already initialized")
            return

        logger.info("Initializing all security services...")

        # 1. Initialize core security services (authentication, authorization, etc.)
        self._initialize_core_security_services()

        # 2. Initialize monitoring services
        self._initialize_monitoring_services()

        # 3. Register this factory itself
        register_instance(SecurityServiceFactory, self)

        self._initialized = True
        logger.info("All security services initialized successfully")

    def _initialize_core_security_services(self) -> None:
        """Initialize core security services via SecurityHardeningFramework."""
        service_name = self.config.get("service_name", "default_service")
        bootstrap = create_security_framework(service_name, self.config)
        bootstrap.initialize_security()

        logger.info(
            "Core security services registered: %s",
            [
                ISecretManager.__name__,
                IAuthenticator.__name__,
                IAuthorizer.__name__,
                IAuditor.__name__,
                ICacheManager.__name__,
                ISessionManager.__name__,
            ],
        )

    def _initialize_monitoring_services(self) -> None:
        """Initialize security monitoring services."""
        # Create monitoring components with DI support
        event_collector = SecurityEventCollector()
        analytics_engine = SecurityAnalyticsEngine()
        siem_integration = SIEMIntegration()
        dashboard = SecurityMonitoringDashboard()

        # Create the main monitoring system
        monitoring_system = SecurityMonitoringSystem(
            event_collector=event_collector,
            analytics_engine=analytics_engine,
            siem_integration=siem_integration,
            dashboard=dashboard,
        )

        # The monitoring system constructor already registers all components in DI
        logger.info(
            "Security monitoring services registered: %s", [type(monitoring_system).__name__]
        )
        logger.debug(
            "Monitoring system components: %s",
            [
                SecurityEventCollector.__name__,
                SecurityAnalyticsEngine.__name__,
                SIEMIntegration.__name__,
                SecurityMonitoringDashboard.__name__,
                SecurityMonitoringSystem.__name__,
            ],
        )

    def get_core_security_services(self) -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
        """
        Get core security services from DI container.

        Returns:
            Tuple of (authenticator, authorizer, secret_manager)
        """
        self._ensure_initialized()
        return (get_service(IAuthenticator), get_service(IAuthorizer), get_service(ISecretManager))

    def get_monitoring_system(self) -> SecurityMonitoringSystem:
        """
        Get the security monitoring system from DI container.

        Returns:
            SecurityMonitoringSystem instance
        """
        self._ensure_initialized()
        return get_service(SecurityMonitoringSystem)

    def get_event_collector(self) -> SecurityEventCollector:
        """
        Get the security event collector from DI container.

        Returns:
            SecurityEventCollector instance
        """
        self._ensure_initialized()
        return get_service(SecurityEventCollector)

    def get_analytics_engine(self) -> SecurityAnalyticsEngine:
        """
        Get the security analytics engine from DI container.

        Returns:
            SecurityAnalyticsEngine instance
        """
        self._ensure_initialized()
        return get_service(SecurityAnalyticsEngine)

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


# Global factory instance management

# SecurityServiceFactory management through DI container


def get_security_factory() -> SecurityServiceFactory:
    """
    Get the global security service factory instance.

    Returns:
        SecurityServiceFactory instance
    """
    factory = get_service(SecurityServiceFactory)
    if factory is None:
        factory = SecurityServiceFactory()
        register_instance(SecurityServiceFactory, factory)
    return factory


def initialize_security_services(config: dict[str, Any] | None = None) -> None:
    """
    Initialize all security services using the factory.

    This is the main entry point for setting up the security subsystem.

    Args:
        config: Optional configuration for security services
    """
    factory = get_security_factory()
    if config:
        factory.config.update(config)
    factory.initialize_all_security_services()


def get_security_services() -> tuple[IAuthenticator, IAuthorizer, ISecretManager]:
    """
    Get core security services, initializing if necessary.

    Returns:
        Tuple of (authenticator, authorizer, secret_manager)
    """
    factory = get_security_factory()
    return factory.get_core_security_services()


def get_security_monitoring() -> SecurityMonitoringSystem:
    """
    Get security monitoring system, initializing if necessary.

    Returns:
        SecurityMonitoringSystem instance
    """
    factory = get_security_factory()
    return factory.get_monitoring_system()


def reset_security_services() -> None:
    """Reset all security services (primarily for testing)."""
    factory = get_service_optional(SecurityServiceFactory)
    if factory:
        factory.reset()

    # Remove the factory from DI container
    container = get_container()
    container.remove(SecurityServiceFactory)


# Service health check functions


def check_security_services_health() -> dict[str, bool | str]:
    """
    Check the health of all security services.

    Returns:
        Dictionary mapping service names to health status
    """
    health_status = {}

    try:
        factory = get_security_factory()
        if not factory.is_initialized():
            return {"factory": False, "message": "Security services not initialized"}

        # Check core services
        core_services = [
            (IAuthenticator, "authenticator"),
            (IAuthorizer, "authorizer"),
            (ISecretManager, "secret_manager"),
            (IAuditor, "auditor"),
            (ICacheManager, "cache_manager"),
            (ISessionManager, "session_manager"),
        ]

        for service_type, service_name in core_services:
            try:
                service = get_service(service_type)
                health_status[service_name] = service is not None
            except Exception as e:
                health_status[service_name] = False
                logger.warning(f"Health check failed for {service_name}: {e}")

        # Check monitoring services
        monitoring_services = [
            (SecurityEventCollector, "event_collector"),
            (SecurityAnalyticsEngine, "analytics_engine"),
            (SIEMIntegration, "siem_integration"),
            (SecurityMonitoringSystem, "monitoring_system"),
        ]

        for service_type, service_name in monitoring_services:
            try:
                service = get_service(service_type)
                health_status[service_name] = service is not None
            except Exception as e:
                health_status[service_name] = False
                logger.warning(f"Health check failed for {service_name}: {e}")

    except Exception as e:
        logger.error(f"Security services health check failed: {e}")
        health_status["error"] = str(e)

    return health_status
