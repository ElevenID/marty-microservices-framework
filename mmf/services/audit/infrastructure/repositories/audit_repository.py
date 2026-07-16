"""Audit repository implementation."""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from mmf.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity
from mmf.services.audit.domain.contracts import IAuditRepository
from mmf.services.audit.domain.entities import RequestAuditEvent
from mmf.services.audit.domain.value_objects import (
    ActorInfo,
    PerformanceMetrics,
    RequestContext,
    ResourceInfo,
    ResponseMetadata,
    ServiceContext,
)

from ..models import AuditLogRecord

logger = logging.getLogger(__name__)


class AuditRepository(IAuditRepository):
    """Repository for audit events with database persistence."""

    def __init__(self, session_factory):
        """Initialize repository.

        Args:
            session_factory: Factory function to create database sessions
        """
        self.session_factory = session_factory

    async def save(self, event: RequestAuditEvent) -> RequestAuditEvent:
        """Save an audit event.

        Args:
            event: The audit event to save

        Returns:
            Saved event
        """
        async with self.session_factory() as session:
            record = self._event_to_record(event)
            session.add(record)
            await session.commit()
            return event

    async def save_batch(self, events: list[RequestAuditEvent]) -> list[RequestAuditEvent]:
        """Save a batch of audit events.

        Args:
            events: List of events to save

        Returns:
            List of saved events
        """
        async with self.session_factory() as session:
            for event in events:
                record = self._event_to_record(event)
                session.add(record)
            await session.commit()
            return events

    async def find_by_id(self, event_id: UUID) -> RequestAuditEvent | None:
        """Find an audit event by ID.

        Args:
            event_id: The event ID

        Returns:
            The audit event or None
        """
        async with self.session_factory() as session:
            stmt = select(AuditLogRecord).where(AuditLogRecord.event_id == str(event_id))
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            return self._record_to_event(record) if record else None

    async def find_by_criteria(
        self,
        event_type: AuditEventType | None = None,
        severity: AuditSeverity | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        user_id: str | None = None,
        service_name: str | None = None,
        correlation_id: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RequestAuditEvent]:
        """Find audit events by criteria.

        Args:
            event_type: Filter by event type
            severity: Filter by severity
            start_time: Filter by start time
            end_time: Filter by end time
            user_id: Filter by user ID
            service_name: Filter by service name
            correlation_id: Filter by correlation ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of matching audit events
        """
        async with self.session_factory() as session:
            stmt = select(AuditLogRecord)

            # Build where clauses
            conditions = []
            if event_type:
                conditions.append(AuditLogRecord.event_type == event_type.value)
            if severity:
                conditions.append(AuditLogRecord.severity == severity.value)
            if start_time:
                conditions.append(AuditLogRecord.timestamp >= start_time)
            if end_time:
                conditions.append(AuditLogRecord.timestamp <= end_time)
            if user_id:
                conditions.append(AuditLogRecord.user_id == user_id)
            if service_name:
                conditions.append(AuditLogRecord.service_name == service_name)
            if correlation_id:
                conditions.append(AuditLogRecord.correlation_id == correlation_id)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.order_by(AuditLogRecord.timestamp.desc())
            stmt = stmt.offset(skip).limit(limit)

            result = await session.execute(stmt)
            records = result.scalars().all()
            return [self._record_to_event(r) for r in records]

    async def count(
        self,
        event_type: AuditEventType | None = None,
        severity: AuditSeverity | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> int:
        """Count audit events matching criteria.

        Args:
            event_type: Filter by event type
            severity: Filter by severity
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            Count of matching events
        """
        async with self.session_factory() as session:
            stmt = select(func.count()).select_from(AuditLogRecord)

            conditions = []
            if event_type:
                conditions.append(AuditLogRecord.event_type == event_type.value)
            if severity:
                conditions.append(AuditLogRecord.severity == severity.value)
            if start_time:
                conditions.append(AuditLogRecord.timestamp >= start_time)
            if end_time:
                conditions.append(AuditLogRecord.timestamp <= end_time)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await session.execute(stmt)
            return result.scalar_one()

    def _event_to_record(self, event: RequestAuditEvent) -> AuditLogRecord:
        """Convert event to database record."""
        # Extract from value objects
        user_id = event.actor_info.user_id if event.actor_info else None
        username = event.actor_info.username if event.actor_info else None
        session_id = event.actor_info.session_id if event.actor_info else None
        api_key_id = event.actor_info.api_key_id if event.actor_info else None

        source_ip = event.request_context.source_ip if event.request_context else None
        user_agent = event.request_context.user_agent if event.request_context else None
        request_id = event.request_context.request_id if event.request_context else None
        method = event.request_context.method if event.request_context else None
        endpoint = event.request_context.endpoint if event.request_context else None
        correlation_id = event.request_context.correlation_id if event.request_context else None
        trace_id = event.request_context.trace_id if event.request_context else None

        resource_type = event.resource_info.resource_type if event.resource_info else None
        resource_id = event.resource_info.resource_id if event.resource_info else None
        action = event.resource_info.action if event.resource_info else ""

        service_name = event.service_context.service_name if event.service_context else None
        environment = event.service_context.environment if event.service_context else None

        duration_ms = event.performance_metrics.duration_ms if event.performance_metrics else None
        status_code = event.response_metadata.status_code if event.response_metadata else None
        error_code = event.response_metadata.error_code if event.response_metadata else None
        error_message = event.response_metadata.error_message if event.response_metadata else None

        return AuditLogRecord(
            event_id=str(event.id),
            event_type=event.event_type.value,
            severity=event.severity.value,
            outcome=event.outcome.value,
            timestamp=event.timestamp,
            message=event.message,
            user_id=user_id,
            username=username,
            session_id=session_id,
            api_key_id=api_key_id,
            source_ip=source_ip,
            user_agent=user_agent,
            request_id=request_id,
            method=method,
            endpoint=endpoint,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            service_name=service_name,
            environment=environment,
            correlation_id=correlation_id,
            trace_id=trace_id,
            duration_ms=duration_ms,
            status_code=status_code,
            error_code=error_code,
            error_message=error_message,
            details=event.details,
            encrypted_fields=event.encrypted_fields,
            security_event_id=event.security_event_id,
        )

    def _record_to_event(self, record: AuditLogRecord) -> RequestAuditEvent:
        """Convert database record to event."""
        # Build value objects
        request_context = None
        if record.method or record.endpoint:
            request_context = RequestContext(
                method=record.method or "",
                endpoint=record.endpoint or "",
                source_ip=record.source_ip,
                user_agent=record.user_agent,
                request_id=record.request_id,
                correlation_id=record.correlation_id,
                trace_id=record.trace_id,
            )

        actor_info = None
        if any([record.user_id, record.username, record.session_id]):
            actor_info = ActorInfo(
                user_id=record.user_id,
                username=record.username,
                session_id=record.session_id,
                api_key_id=record.api_key_id,
            )

        resource_info = None
        if record.resource_type:
            resource_info = ResourceInfo(
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                action=record.action or "",
            )

        service_context = None
        if record.service_name:
            service_context = ServiceContext(
                service_name=record.service_name,
                environment=record.environment or "unknown",
                version="unknown",
                instance_id="unknown",
            )

        response_metadata = None
        if record.status_code:
            response_metadata = ResponseMetadata(
                status_code=record.status_code,
                error_code=record.error_code,
                error_message=record.error_message,
            )

        performance_metrics = None
        if record.duration_ms:
            performance_metrics = PerformanceMetrics(
                duration_ms=record.duration_ms,
                started_at=record.timestamp,
                completed_at=record.timestamp,
            )

        return RequestAuditEvent(
            event_id=UUID(record.event_id),
            event_type=AuditEventType(record.event_type),
            severity=AuditSeverity(record.severity),
            outcome=AuditOutcome(record.outcome),
            timestamp=record.timestamp,
            message=record.message or "",
            request_context=request_context,
            response_metadata=response_metadata,
            performance_metrics=performance_metrics,
            actor_info=actor_info,
            resource_info=resource_info,
            service_context=service_context,
            details=record.details or {},
            encrypted_fields=record.encrypted_fields or [],
            security_event_id=record.security_event_id,
            created_at=record.created_at,
        )
