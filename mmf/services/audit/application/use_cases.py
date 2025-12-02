"""Use cases for audit service application layer."""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from mmf.core.domain.audit_types import (
    AuditEventType,
    AuditOutcome,
    AuditSeverity,
    SecurityEventSeverity,
    SecurityEventType,
)
from mmf.services.audit.domain.contracts import IAuditDestination, IAuditRepository
from mmf.services.audit.domain.entities import ApiCallEvent, RequestAuditEvent
from mmf.services.audit.domain.value_objects import (
    ActorInfo,
    PerformanceMetrics,
    RequestContext,
    ResourceInfo,
    ResponseMetadata,
    ServiceContext,
)

from ..application.commands import (
    GenerateAuditReportCommand,
    GenerateAuditReportResponse,
    LogApiCallCommand,
    LogApiCallResponse,
    LogRequestCommand,
    LogRequestResponse,
    QueryAuditEventsCommand,
    QueryAuditEventsResponse,
)

logger = logging.getLogger(__name__)


class LogRequestUseCase:
    """Use case for logging audit requests."""

    def __init__(
        self,
        repository: IAuditRepository,
        destinations: list[IAuditDestination],
        auto_forward_threshold: AuditSeverity = AuditSeverity.HIGH,
        compliance_logger=None,  # Optional: audit_compliance service for forwarding
    ):
        """Initialize use case.

        Args:
            repository: Audit repository
            destinations: List of audit destinations
            auto_forward_threshold: Severity threshold for auto-forwarding to compliance
            compliance_logger: Optional audit_compliance logger for high-severity events
        """
        self.repository = repository
        self.destinations = destinations
        self.auto_forward_threshold = auto_forward_threshold
        self.compliance_logger = compliance_logger

    async def execute(self, command: LogRequestCommand) -> LogRequestResponse:
        """Execute the log request use case.

        Args:
            command: Log request command

        Returns:
            Log request response with event ID
        """
        # Build value objects
        request_context = None
        if command.method and command.endpoint:
            request_context = RequestContext(
                method=command.method,
                endpoint=command.endpoint,
                source_ip=command.source_ip,
                user_agent=command.user_agent,
                request_id=command.request_id,
                correlation_id=command.correlation_id,
                trace_id=command.trace_id,
            )

        response_metadata = None
        if command.status_code is not None:
            response_metadata = ResponseMetadata(
                status_code=command.status_code,
                response_size=command.response_size,
            )

        performance_metrics = None
        if command.duration_ms is not None:
            now = datetime.now(timezone.utc)
            performance_metrics = PerformanceMetrics(
                duration_ms=command.duration_ms,
                started_at=now,
                completed_at=now,
                is_slow_request=command.duration_ms > 1000,
                is_large_response=(command.response_size or 0) > 1_000_000,
            )

        actor_info = None
        if any([command.user_id, command.username, command.session_id]):
            actor_info = ActorInfo(
                user_id=command.user_id,
                username=command.username,
                session_id=command.session_id,
                api_key_id=command.api_key_id,
            )

        resource_info = None
        if command.resource_type:
            resource_info = ResourceInfo(
                resource_type=command.resource_type,
                resource_id=command.resource_id,
                action=command.action,
            )

        service_context = None
        if command.service_name:
            service_context = ServiceContext(
                service_name=command.service_name,
                environment=command.environment or "unknown",
                version=command.version or "unknown",
                instance_id=command.instance_id or str(uuid4()),
            )

        # Create audit event entity
        event = RequestAuditEvent(
            event_type=command.event_type,
            severity=command.severity,
            outcome=command.outcome,
            message=command.message,
            request_context=request_context,
            response_metadata=response_metadata,
            performance_metrics=performance_metrics,
            actor_info=actor_info,
            resource_info=resource_info,
            service_context=service_context,
            details=command.details,
        )

        # Save to repository
        saved_event = await self.repository.save(event)

        # Write to all destinations independently (failures don't block others)
        for destination in self.destinations:
            try:
                await destination.write_event(saved_event)
            except Exception as e:
                logger.error(
                    f"Failed to write to destination {destination.__class__.__name__}: {e}",
                    exc_info=True,
                )

        # Auto-forward high-severity events to audit_compliance
        security_event_id = None
        if self._should_forward_to_compliance(event):
            security_event_id = await self._forward_to_compliance(event)

        return LogRequestResponse(
            event_id=saved_event.id,
            timestamp=saved_event.timestamp,
            security_event_id=security_event_id,
        )

    def _should_forward_to_compliance(self, event: RequestAuditEvent) -> bool:
        """Check if event should be forwarded to compliance.

        Args:
            event: The audit event

        Returns:
            True if should forward
        """
        severity_values = {
            AuditSeverity.INFO: 0,
            AuditSeverity.LOW: 1,
            AuditSeverity.MEDIUM: 2,
            AuditSeverity.HIGH: 3,
            AuditSeverity.CRITICAL: 4,
        }
        return severity_values.get(event.severity, 0) >= severity_values.get(
            self.auto_forward_threshold, 3
        )

    async def _forward_to_compliance(self, event: RequestAuditEvent) -> str | None:
        """Forward high-severity event to audit_compliance.

        Args:
            event: The audit event to forward

        Returns:
            Security event ID if forwarded successfully
        """
        if not self.compliance_logger:
            logger.warning("Compliance logger not configured, skipping forwarding")
            return None

        try:
            # Forward to audit_compliance (async fire-and-forget to avoid blocking)
            security_event_id = str(uuid4())
            logger.info(
                f"Forwarding high-severity event {event.id} to audit_compliance "
                f"as security_event_id {security_event_id}"
            )

            # Map severity
            severity_map = {
                AuditSeverity.INFO: SecurityEventSeverity.INFO,
                AuditSeverity.LOW: SecurityEventSeverity.LOW,
                AuditSeverity.MEDIUM: SecurityEventSeverity.MEDIUM,
                AuditSeverity.HIGH: SecurityEventSeverity.HIGH,
                AuditSeverity.CRITICAL: SecurityEventSeverity.CRITICAL,
            }
            severity = severity_map.get(event.severity, SecurityEventSeverity.MEDIUM)

            # Map event type (simplified mapping)
            event_type = SecurityEventType.SECURITY_VIOLATION

            user_id = event.actor_info.user_id if event.actor_info else None
            resource_id = event.resource_info.resource_id if event.resource_info else None

            # Call compliance logger
            if hasattr(self.compliance_logger, "log_audit_event"):
                result = await self.compliance_logger.log_audit_event(
                    event_type=event_type,
                    severity=severity,
                    source="audit-service",
                    description=event.message or "High severity audit event",
                    user_id=user_id,
                    resource_id=resource_id,
                    metadata=event.details,
                )
                if result:
                    return str(result.event_id)

            return security_event_id

        except Exception as e:
            logger.error(f"Failed to forward to compliance: {e}", exc_info=True)
            return None


class LogApiCallUseCase:
    """Use case for logging API calls."""

    def __init__(
        self,
        repository: IAuditRepository,
        destinations: list[IAuditDestination],
        auto_forward_threshold: AuditSeverity = AuditSeverity.HIGH,
        compliance_logger=None,
    ):
        """Initialize use case.

        Args:
            repository: Audit repository
            destinations: List of audit destinations
            auto_forward_threshold: Severity threshold for auto-forwarding
            compliance_logger: Optional compliance logger
        """
        self.repository = repository
        self.destinations = destinations
        self.auto_forward_threshold = auto_forward_threshold
        self.compliance_logger = compliance_logger

    async def execute(self, command: LogApiCallCommand) -> LogApiCallResponse:
        """Execute the log API call use case.

        Args:
            command: Log API call command

        Returns:
            Log API call response
        """
        # Build value objects
        request_context = None
        if command.method:
            request_context = RequestContext(
                method=command.method,
                endpoint=command.target_endpoint,
                source_ip=command.source_ip,
                correlation_id=command.correlation_id,
            )

        performance_metrics = None
        if command.duration_ms is not None:
            now = datetime.now(timezone.utc)
            performance_metrics = PerformanceMetrics(
                duration_ms=command.duration_ms,
                started_at=now,
                completed_at=now,
            )

        actor_info = None
        if command.user_id or command.username:
            actor_info = ActorInfo(
                user_id=command.user_id,
                username=command.username,
            )

        response_metadata = None
        if command.status_code is not None:
            response_metadata = ResponseMetadata(status_code=command.status_code)

        # Create API call event
        event = ApiCallEvent(
            target_service=command.target_service,
            target_endpoint=command.target_endpoint,
            severity=command.severity,
            outcome=command.outcome,
            message=command.message,
            request_context=request_context,
            performance_metrics=performance_metrics,
            actor_info=actor_info,
            response_metadata=response_metadata,
            details=command.details,
        )

        # Save to repository
        saved_event = await self.repository.save(event)

        # Write to destinations independently
        for destination in self.destinations:
            try:
                await destination.write_event(saved_event)
            except Exception as e:
                logger.error(
                    f"Failed to write to destination {destination.__class__.__name__}: {e}",
                    exc_info=True,
                )

        # Auto-forward if needed
        security_event_id = None
        severity_values = {
            AuditSeverity.INFO: 0,
            AuditSeverity.LOW: 1,
            AuditSeverity.MEDIUM: 2,
            AuditSeverity.HIGH: 3,
            AuditSeverity.CRITICAL: 4,
        }
        if severity_values.get(event.severity, 0) >= severity_values.get(
            self.auto_forward_threshold, 3
        ):
            if self.compliance_logger:
                try:
                    security_event_id = str(uuid4())
                    logger.info(f"Forwarding API call event {event.id} to audit_compliance")
                    # TODO: Forward to compliance
                except Exception as e:
                    logger.error(f"Failed to forward to compliance: {e}")

        return LogApiCallResponse(
            event_id=saved_event.id,
            timestamp=saved_event.timestamp,
            security_event_id=security_event_id,
        )


class QueryAuditEventsUseCase:
    """Use case for querying audit events."""

    def __init__(self, repository: IAuditRepository):
        """Initialize use case.

        Args:
            repository: Audit repository
        """
        self.repository = repository

    async def execute(self, command: QueryAuditEventsCommand) -> QueryAuditEventsResponse:
        """Execute the query audit events use case.

        Args:
            command: Query command

        Returns:
            Query response with events
        """
        # Query events from repository
        events = await self.repository.find_by_criteria(
            event_type=command.event_type,
            severity=command.severity,
            start_time=command.start_time,
            end_time=command.end_time,
            user_id=command.user_id,
            service_name=command.service_name,
            correlation_id=command.correlation_id,
            skip=command.skip,
            limit=command.limit,
        )

        # Get total count
        total_count = await self.repository.count(
            event_type=command.event_type,
            severity=command.severity,
            start_time=command.start_time,
            end_time=command.end_time,
        )

        # Convert to dictionaries
        event_dicts = [event.to_dict() for event in events]

        return QueryAuditEventsResponse(
            events=event_dicts,
            total_count=total_count,
            skip=command.skip,
            limit=command.limit,
        )


class GenerateAuditReportUseCase:
    """Use case for generating audit reports."""

    def __init__(self, repository: IAuditRepository):
        """Initialize use case.

        Args:
            repository: Audit repository
        """
        self.repository = repository

    async def execute(self, command: GenerateAuditReportCommand) -> GenerateAuditReportResponse:
        """Execute the generate audit report use case.

        Args:
            command: Generate report command

        Returns:
            Generate report response
        """
        # Query events for report period
        events = await self.repository.find_by_criteria(
            start_time=command.start_time,
            end_time=command.end_time,
            service_name=command.service_name,
            skip=0,
            limit=10000,  # Large limit for reports
        )

        # Filter by severity threshold if specified
        if command.severity_threshold:
            severity_values = {
                AuditSeverity.INFO: 0,
                AuditSeverity.LOW: 1,
                AuditSeverity.MEDIUM: 2,
                AuditSeverity.HIGH: 3,
                AuditSeverity.CRITICAL: 4,
            }
            threshold_value = severity_values.get(command.severity_threshold, 0)
            events = [e for e in events if severity_values.get(e.severity, 0) >= threshold_value]

        # Filter by event types if specified
        if command.event_types:
            events = [e for e in events if e.event_type in command.event_types]

        # Generate report data
        report_id = str(uuid4())
        report_data = {
            "report_id": report_id,
            "period": {
                "start": command.start_time.isoformat(),
                "end": command.end_time.isoformat(),
            },
            "filters": {
                "event_types": (
                    [et.value for et in command.event_types] if command.event_types else None
                ),
                "severity_threshold": (
                    command.severity_threshold.value if command.severity_threshold else None
                ),
                "service_name": command.service_name,
            },
            "summary": {
                "total_events": len(events),
                "by_severity": self._count_by_severity(events),
                "by_type": self._count_by_type(events),
                "by_outcome": self._count_by_outcome(events),
            },
            "events": [event.to_dict() for event in events],
        }

        return GenerateAuditReportResponse(
            report_id=report_id,
            report_data=report_data,
            generated_at=datetime.now(timezone.utc),
        )

    def _count_by_severity(self, events: list[RequestAuditEvent]) -> dict[str, int]:
        """Count events by severity."""
        counts: dict[str, int] = {}
        for event in events:
            severity = event.severity.value
            counts[severity] = counts.get(severity, 0) + 1
        return counts

    def _count_by_type(self, events: list[RequestAuditEvent]) -> dict[str, int]:
        """Count events by type."""
        counts: dict[str, int] = {}
        for event in events:
            event_type = event.event_type.value
            counts[event_type] = counts.get(event_type, 0) + 1
        return counts

    def _count_by_outcome(self, events: list[RequestAuditEvent]) -> dict[str, int]:
        """Count events by outcome."""
        counts: dict[str, int] = {}
        for event in events:
            outcome = event.outcome.value
            counts[outcome] = counts.get(outcome, 0) + 1
        return counts
