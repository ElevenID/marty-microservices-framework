"""Security monitoring services initialization.

Handles setup and DI registration of monitoring components including
event collection, analytics engines, SIEM integration, and dashboards.
"""

from __future__ import annotations

import logging
from typing import Any

from .monitoring import (
    SecurityAnalyticsEngine,
    SecurityEventCollector,
    SecurityMonitoringDashboard,
    SecurityMonitoringSystem,
    SIEMIntegration,
)

logger = logging.getLogger(__name__)


class MonitoringInitializer:
    """Handles initialization of security monitoring services."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def initialize_monitoring_services(self) -> None:
        """Initialize security monitoring services and register in DI."""
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
