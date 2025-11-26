"""Security services health checking.

Validates the health and availability of all security services including
core services (auth, secrets, etc.) and monitoring components.
"""

from __future__ import annotations

import logging

from ..audit_compliance.monitoring import (
    SecurityAnalyticsEngine,
    SecurityEventCollector,
    SecurityMonitoringSystem,
    SIEMIntegration,
)
from ..core.di_container import get_service
from .api import (
    IAuditor,
    IAuthenticator,
    IAuthorizer,
    ICacheManager,
    ISecretManager,
    ISessionManager,
)

logger = logging.getLogger(__name__)


def check_security_services_health(factory) -> dict[str, bool | str]:
    """Check the health of all security services.

    Args:
        factory: SecurityServiceFactory instance to check

    Returns:
        Dictionary mapping service names to health status
    """
    health_status = {}

    try:
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
