"""Database destination adapter for audit logging."""

import asyncio
import hashlib
import logging
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mmf.core.domain.audit_types import AuditEventType, AuditSeverity
from mmf.services.audit.domain.contracts import IAuditDestination
from mmf.services.audit.domain.entities import RequestAuditEvent

from ..models import AuditLogRecord

logger = logging.getLogger(__name__)


class DatabaseAuditDestination(IAuditDestination):
    """Database destination adapter with batching support."""

    def __init__(
        self,
        session_factory,
        batch_size: int = 100,
        enable_batching: bool = True,
    ):
        """Initialize database destination.

        Args:
            session_factory: Factory function to create database sessions
            batch_size: Number of events to batch before flushing
            enable_batching: Whether to batch writes
        """
        self.session_factory = session_factory
        self.batch_size = batch_size
        self.enable_batching = enable_batching
        self._batch: list[RequestAuditEvent] = []
        self._batch_lock = asyncio.Lock()

    async def write_event(self, event: RequestAuditEvent) -> None:
        """Write a single audit event to database.

        Args:
            event: The audit event to write
        """
        if self.enable_batching:
            async with self._batch_lock:
                self._batch.append(event)
                if len(self._batch) >= self.batch_size:
                    await self._flush_batch()
        else:
            await self._write_direct(event)

    async def write_batch(self, events: list[RequestAuditEvent]) -> None:
        """Write a batch of audit events to database.

        Args:
            events: List of audit events to write
        """
        async with self._batch_lock:
            async with self.session_factory() as session:
                for event in events:
                    record = self._event_to_record(event)
                    session.add(record)
                await session.commit()

    async def flush(self) -> None:
        """Flush any buffered events."""
        if self.enable_batching:
            async with self._batch_lock:
                await self._flush_batch()

    async def close(self) -> None:
        """Close the destination and cleanup resources."""
        await self.flush()

    async def health_check(self) -> bool:
        """Check if the destination is healthy.

        Returns:
            True if destination is operational
        """
        try:
            async with self.session_factory() as session:
                # Simple query to check database connectivity
                await session.execute(select(func.count()).select_from(AuditLogRecord))
                return True
        except Exception as e:
            logger.error("Database destination health check failed: %s", e)
            return False

    async def _flush_batch(self) -> None:
        """Flush the current batch to database."""
        if not self._batch:
            return

        try:
            async with self.session_factory() as session:
                for event in self._batch:
                    record = self._event_to_record(event)
                    session.add(record)
                await session.commit()
            self._batch.clear()
        except Exception as e:
            logger.error("Failed to flush audit batch to database: %s", e, exc_info=True)

    async def _write_direct(self, event: RequestAuditEvent) -> None:
        """Write event directly to database without batching.

        Args:
            event: The audit event to write
        """
        try:
            async with self.session_factory() as session:
                record = self._event_to_record(event)
                session.add(record)
                await session.commit()
        except Exception as e:
            logger.error("Failed to write audit event to database: %s", e, exc_info=True)

    def _event_to_record(self, event: RequestAuditEvent) -> AuditLogRecord:
        """Convert audit event to database record.

        Args:
            event: The audit event

        Returns:
            Database record
        """
        # Extract data from value objects
        user_id = None
        username = None
        session_id = None
        api_key_id = None
        if event.actor_info:
            user_id = event.actor_info.user_id
            username = event.actor_info.username
            session_id = event.actor_info.session_id
            api_key_id = event.actor_info.api_key_id

        source_ip = None
        user_agent = None
        request_id = None
        method = None
        endpoint = None
        correlation_id = None
        trace_id = None
        if event.request_context:
            source_ip = event.request_context.source_ip
            user_agent = event.request_context.user_agent
            request_id = event.request_context.request_id
            method = event.request_context.method
            endpoint = event.request_context.endpoint
            correlation_id = event.request_context.correlation_id
            trace_id = event.request_context.trace_id

        resource_type = None
        resource_id = None
        action = ""
        if event.resource_info:
            resource_type = event.resource_info.resource_type
            resource_id = event.resource_info.resource_id
            action = event.resource_info.action

        service_name = None
        environment = None
        if event.service_context:
            service_name = event.service_context.service_name
            environment = event.service_context.environment

        duration_ms = None
        if event.performance_metrics:
            duration_ms = event.performance_metrics.duration_ms

        status_code = None
        error_code = None
        error_message = None
        if event.response_metadata:
            status_code = event.response_metadata.status_code
            error_code = event.response_metadata.error_code
            error_message = event.response_metadata.error_message

        # Calculate event hash for integrity
        event_hash = self._calculate_event_hash(event)

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
            event_hash=event_hash,
        )

    def _calculate_event_hash(self, event: RequestAuditEvent) -> str:
        """Calculate hash for event integrity.

        Args:
            event: The audit event

        Returns:
            SHA-256 hash hex string
        """
        event_string = (
            f"{event.id}{event.timestamp.isoformat()}{event.event_type.value}{event.message}"
        )
        return hashlib.sha256(event_string.encode()).hexdigest()
