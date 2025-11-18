"""
Service Factory for Audit Compliance Service

This module provides a clean, high-level API for interacting with the audit
compliance service. It abstracts away the complexity of dependency injection
and provides convenient methods for common operations.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Optional, Union

from mmf_new.core.domain.audit_models import AuditEvent, ComplianceResult, SecurityEvent
from mmf_new.core.domain.audit_types import (
    AuditLevel,
    ComplianceFramework,
    SecurityEventSeverity,
    SecurityEventType,
)

from .application.commands import (
    AnalyzeThreatPatternCommand,
    CollectSecurityEventCommand,
    GenerateSecurityReportCommand,
    LogAuditEventCommand,
    ScanComplianceCommand,
)
from .di_config import (
    AuditComplianceConfig,
    AuditComplianceDIContainer,
    create_development_config,
    create_production_config,
    create_test_config,
    get_container,
    initialize_audit_compliance_service,
    shutdown_audit_compliance_service,
)
from .domain.entities import ComplianceScanResult, SecurityAuditEvent, ThreatPattern
from .domain.value_objects import ComplianceRule, SecurityMetrics, ThreatSignature

logger = logging.getLogger(__name__)


class AuditComplianceService:
    """
    High-level service API for audit compliance operations.

    This class provides a clean, convenient interface for all audit compliance
    functionality while hiding the complexity of the hexagonal architecture
    and dependency injection.
    """

    def __init__(self, container: AuditComplianceDIContainer):
        self.container = container
        self._is_initialized = False
        logger.info("Audit compliance service created")

    async def initialize(self):
        """Initialize the service and all dependencies."""
        if not self._is_initialized:
            await self.container.initialize()
            self._is_initialized = True
            logger.info("Audit compliance service initialized")

    async def shutdown(self):
        """Shutdown the service gracefully."""
        if self._is_initialized:
            await self.container.shutdown()
            self._is_initialized = False
            logger.info("Audit compliance service shutdown")

    def _ensure_initialized(self):
        """Ensure service is initialized before operations."""
        if not self._is_initialized:
            raise RuntimeError("Service not initialized. Call initialize() first.")

    # Audit Event Operations

    async def log_audit_event(
        self,
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        source: str,
        description: str,
        user_id: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SecurityAuditEvent:
        """
        Log a security audit event.

        Args:
            event_type: Type of security event
            severity: Severity level of the event
            source: Source system or component
            description: Human-readable description
            user_id: Optional user identifier
            resource_id: Optional resource identifier
            metadata: Optional additional metadata

        Returns:
            Created security audit event
        """
        self._ensure_initialized()

        use_case = self.container.get_log_audit_event_use_case()

        command = LogAuditEventCommand.Request(
            event_type=event_type,
            severity=severity,
            source=source,
            description=description,
            user_id=user_id,
            resource_id=resource_id,
            metadata=metadata or {},
        )

        response = await use_case.execute(command)
        return response.audit_event

    async def get_audit_events(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        event_types: list[SecurityEventType] | None = None,
        severities: list[SecurityEventSeverity] | None = None,
        limit: int = 100,
    ) -> list[SecurityAuditEvent]:
        """
        Retrieve audit events with filtering.

        Args:
            start_time: Start of time range
            end_time: End of time range
            event_types: Filter by event types
            severities: Filter by severities
            limit: Maximum number of events to return

        Returns:
            List of matching audit events
        """
        self._ensure_initialized()

        repository = self.container.get_audit_event_repository()

        # Build filters
        filters = {}
        if start_time:
            filters["start_time"] = start_time
        if end_time:
            filters["end_time"] = end_time
        if event_types:
            filters["event_types"] = event_types
        if severities:
            filters["severities"] = severities

        return await repository.find_by_criteria(filters, limit=limit)

    # Compliance Operations

    async def scan_compliance(
        self,
        frameworks: list[ComplianceFramework],
        target_resource: str,
        scan_depth: str = "standard",
    ) -> ComplianceScanResult:
        """
        Perform compliance scan against specified frameworks.

        Args:
            frameworks: Compliance frameworks to scan against
            target_resource: Resource or system to scan
            scan_depth: Depth of scan (quick, standard, thorough)

        Returns:
            Compliance scan results
        """
        self._ensure_initialized()

        use_case = self.container.get_scan_compliance_use_case()

        command = ScanComplianceCommand.Request(
            frameworks=frameworks, target_resource=target_resource, scan_depth=scan_depth
        )

        response = await use_case.execute(command)
        return response.scan_result

    async def get_compliance_status(
        self, framework: ComplianceFramework, resource_id: str | None = None
    ) -> dict[str, Any]:
        """
        Get current compliance status for a framework.

        Args:
            framework: Compliance framework to check
            resource_id: Optional specific resource

        Returns:
            Compliance status summary
        """
        self._ensure_initialized()

        scanner = self.container.get_compliance_scanner()
        return await scanner.get_compliance_status(framework, resource_id)

    # Threat Analysis Operations

    async def analyze_threat_patterns(
        self, analysis_window_hours: int = 24, confidence_threshold: float = 0.7
    ) -> list[ThreatPattern]:
        """
        Analyze recent events for threat patterns.

        Args:
            analysis_window_hours: How far back to analyze
            confidence_threshold: Minimum confidence for threats

        Returns:
            List of detected threat patterns
        """
        self._ensure_initialized()

        use_case = self.container.get_analyze_threat_pattern_use_case()

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=analysis_window_hours)

        command = AnalyzeThreatPatternCommand.Request(
            start_time=start_time, end_time=end_time, confidence_threshold=confidence_threshold
        )

        response = await use_case.execute(command)
        return response.threat_patterns

    async def get_threat_intelligence(
        self, threat_type: str | None = None, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """
        Get current threat intelligence data.

        Args:
            threat_type: Optional filter by threat type
            active_only: Only return active threats

        Returns:
            List of threat intelligence data
        """
        self._ensure_initialized()

        analyzer = self.container.get_threat_analyzer()
        return await analyzer.get_threat_intelligence(threat_type, active_only)

    # Security Report Operations

    async def generate_security_report(
        self,
        report_type: str = "comprehensive",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        output_format: str = "json",
        include_recommendations: bool = True,
    ) -> dict[str, Any]:
        """
        Generate a security report.

        Args:
            report_type: Type of report (comprehensive, compliance, threat, executive)
            start_time: Start of reporting period
            end_time: End of reporting period
            output_format: Output format (json, html, pdf)
            include_recommendations: Include security recommendations

        Returns:
            Generated report data
        """
        self._ensure_initialized()

        use_case = self.container.get_generate_security_report_use_case()

        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=30)
        if not end_time:
            end_time = datetime.utcnow()

        command = GenerateSecurityReportCommand.Request(
            report_type=report_type,
            start_time=start_time,
            end_time=end_time,
            output_format=output_format,
            include_recommendations=include_recommendations,
        )

        response = await use_case.execute(command)
        return {
            "report_id": response.report_id,
            "report_path": response.report_path,
            "metadata": response.metadata,
        }

    # SIEM Integration Operations

    async def collect_security_events(
        self,
        source_systems: list[str] | None = None,
        event_types: list[SecurityEventType] | None = None,
        time_range_hours: int = 1,
    ) -> list[SecurityEvent]:
        """
        Collect security events from SIEM systems.

        Args:
            source_systems: Optional filter by source systems
            event_types: Optional filter by event types
            time_range_hours: How far back to collect events

        Returns:
            List of collected security events
        """
        self._ensure_initialized()

        use_case = self.container.get_collect_security_event_use_case()

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=time_range_hours)

        command = CollectSecurityEventCommand.Request(
            start_time=start_time,
            end_time=end_time,
            source_systems=source_systems,
            event_types=event_types,
        )

        response = await use_case.execute(command)
        return response.security_events

    async def forward_to_siem(self, events: list[SecurityAuditEvent | SecurityEvent]) -> bool:
        """
        Forward events to SIEM system.

        Args:
            events: Events to forward

        Returns:
            Success status
        """
        self._ensure_initialized()

        siem_adapter = self.container.get_siem_adapter()

        try:
            for event in events:
                await siem_adapter.send_event(event)
            return True
        except Exception as e:
            logger.error(f"Failed to forward events to SIEM: {e}")
            return False

    # Cache Operations

    async def get_cached_events(
        self, event_types: list[SecurityEventType] | None = None, max_age_hours: int = 24
    ) -> list[SecurityAuditEvent]:
        """
        Get events from cache (fast access).

        Args:
            event_types: Optional filter by event types
            max_age_hours: Maximum age of cached events

        Returns:
            List of cached events
        """
        self._ensure_initialized()

        cache = self.container.get_audit_event_cache()

        # Calculate time threshold
        threshold = datetime.utcnow() - timedelta(hours=max_age_hours)

        events = await cache.get_events_after(threshold)

        # Filter by event types if specified
        if event_types:
            events = [e for e in events if e.event_type in event_types]

        return events

    # Health and Monitoring

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all service components."""
        return self.container.get_health_status()

    async def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of service metrics."""
        self._ensure_initialized()

        metrics = self.container.get_compliance_metrics()
        return await metrics.get_metrics_summary()

    # Bulk Operations

    async def bulk_log_events(self, events: list[dict[str, Any]]) -> list[SecurityAuditEvent]:
        """
        Log multiple events in bulk for efficiency.

        Args:
            events: List of event data dictionaries

        Returns:
            List of created audit events
        """
        self._ensure_initialized()

        results = []
        use_case = self.container.get_log_audit_event_use_case()

        # Process events in parallel for better performance
        tasks = []
        for event_data in events:
            command = LogAuditEventCommand.Request(**event_data)
            tasks.append(use_case.execute(command))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for response in responses:
            if isinstance(response, Exception):
                logger.error(f"Failed to log event: {response}")
            else:
                results.append(response.audit_event)

        return results


# Factory Functions


async def create_audit_compliance_service(
    config: AuditComplianceConfig | None = None, environment: str = "development"
) -> AuditComplianceService:
    """
    Create and initialize an audit compliance service.

    Args:
        config: Optional configuration, uses environment default if not provided
        environment: Environment type (development, production, test)

    Returns:
        Initialized audit compliance service
    """
    if config is None:
        if environment == "production":
            config = create_production_config()
        elif environment == "test":
            config = create_test_config()
        else:
            config = create_development_config()

    container = await initialize_audit_compliance_service(config)
    service = AuditComplianceService(container)
    await service.initialize()

    logger.info(f"Created audit compliance service for {environment} environment")
    return service


@asynccontextmanager
async def audit_compliance_service(
    config: AuditComplianceConfig | None = None, environment: str = "development"
):
    """
    Context manager for audit compliance service.

    Usage:
        async with audit_compliance_service() as service:
            await service.log_audit_event(...)
    """
    service = await create_audit_compliance_service(config, environment)
    try:
        yield service
    finally:
        await service.shutdown()


# Convenience Functions for Common Operations


async def quick_audit_log(
    event_type: SecurityEventType,
    description: str,
    severity: SecurityEventSeverity = SecurityEventSeverity.INFO,
    source: str = "system",
    **kwargs,
) -> SecurityAuditEvent:
    """
    Quick function to log an audit event with minimal setup.

    Args:
        event_type: Type of security event
        description: Event description
        severity: Event severity (defaults to INFO)
        source: Event source (defaults to 'system')
        **kwargs: Additional event data

    Returns:
        Created audit event
    """
    async with audit_compliance_service() as service:
        return await service.log_audit_event(
            event_type=event_type,
            severity=severity,
            source=source,
            description=description,
            **kwargs,
        )


async def quick_compliance_scan(
    frameworks: list[ComplianceFramework], target: str
) -> ComplianceScanResult:
    """
    Quick function to perform a compliance scan.

    Args:
        frameworks: Frameworks to scan against
        target: Target resource to scan

    Returns:
        Compliance scan result
    """
    async with audit_compliance_service() as service:
        return await service.scan_compliance(frameworks, target)


async def quick_threat_analysis(hours: int = 24, threshold: float = 0.7) -> list[ThreatPattern]:
    """
    Quick function to analyze recent threat patterns.

    Args:
        hours: Hours to analyze
        threshold: Confidence threshold

    Returns:
        List of threat patterns
    """
    async with audit_compliance_service() as service:
        return await service.analyze_threat_patterns(hours, threshold)


# Export main service class and factory functions
__all__ = [
    "AuditComplianceService",
    "create_audit_compliance_service",
    "audit_compliance_service",
    "quick_audit_log",
    "quick_compliance_scan",
    "quick_threat_analysis",
]
