"""Port interfaces (contracts) for the audit domain."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from mmf_new.core.domain.audit_types import AuditEventType, AuditSeverity

from .entities import RequestAuditEvent


class IAuditDestination(ABC):
    """Port interface for audit destinations (file, database, SIEM, etc.)."""

    @abstractmethod
    async def write_event(self, event: RequestAuditEvent) -> None:
        """Write a single audit event.

        Args:
            event: The audit event to write
        """
        pass

    @abstractmethod
    async def write_batch(self, events: list[RequestAuditEvent]) -> None:
        """Write a batch of audit events.

        Args:
            events: List of audit events to write
        """
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Flush any buffered events."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the destination and cleanup resources."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the destination is healthy.

        Returns:
            True if destination is operational
        """
        pass


class IAuditEncryption(ABC):
    """Port interface for audit encryption operations."""

    @abstractmethod
    def encrypt_field(self, field_name: str, value: Any) -> tuple[str, bool]:
        """Encrypt a field value if it's sensitive.

        Args:
            field_name: Name of the field
            value: Value to potentially encrypt

        Returns:
            Tuple of (encrypted_or_original_value, was_encrypted)
        """
        pass

    @abstractmethod
    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt an encrypted field value.

        Args:
            encrypted_value: The encrypted value

        Returns:
            Decrypted value
        """
        pass

    @abstractmethod
    def encrypt_event(self, event: RequestAuditEvent) -> RequestAuditEvent:
        """Encrypt sensitive fields in an audit event.

        Args:
            event: The audit event to encrypt

        Returns:
            Event with encrypted sensitive fields
        """
        pass

    @abstractmethod
    def is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field name indicates sensitive data.

        Args:
            field_name: Name of the field

        Returns:
            True if field is considered sensitive
        """
        pass


class IAuditRepository(ABC):
    """Port interface for audit event persistence."""

    @abstractmethod
    async def save(self, event: RequestAuditEvent) -> RequestAuditEvent:
        """Save an audit event.

        Args:
            event: The audit event to save

        Returns:
            Saved event
        """
        pass

    @abstractmethod
    async def save_batch(self, events: list[RequestAuditEvent]) -> list[RequestAuditEvent]:
        """Save a batch of audit events.

        Args:
            events: List of events to save

        Returns:
            List of saved events
        """
        pass

    @abstractmethod
    async def find_by_id(self, event_id: UUID) -> RequestAuditEvent | None:
        """Find an audit event by ID.

        Args:
            event_id: The event ID

        Returns:
            The audit event or None
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass


class IAuditLogger(ABC):
    """Port interface for high-level audit logging."""

    @abstractmethod
    async def log_request(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity,
        message: str,
        **kwargs,
    ) -> RequestAuditEvent:
        """Log an audit event.

        Args:
            event_type: Type of event
            severity: Severity level
            message: Event message
            **kwargs: Additional event attributes

        Returns:
            Created audit event
        """
        pass

    @abstractmethod
    async def log_api_call(
        self,
        target_service: str,
        target_endpoint: str,
        severity: AuditSeverity,
        **kwargs,
    ) -> RequestAuditEvent:
        """Log an API call event.

        Args:
            target_service: Target service name
            target_endpoint: Target endpoint
            severity: Severity level
            **kwargs: Additional event attributes

        Returns:
            Created audit event
        """
        pass


class IMiddlewareAuditor(ABC):
    """Port interface for middleware audit integration."""

    @abstractmethod
    async def audit_request_start(
        self,
        request_id: str,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> str:
        """Audit the start of a request.

        Args:
            request_id: Request identifier
            method: HTTP method
            endpoint: Request endpoint
            **kwargs: Additional request attributes

        Returns:
            Audit event ID
        """
        pass

    @abstractmethod
    async def audit_request_end(
        self,
        request_id: str,
        status_code: int,
        duration_ms: float,
        **kwargs,
    ) -> str:
        """Audit the end of a request.

        Args:
            request_id: Request identifier
            status_code: Response status code
            duration_ms: Request duration
            **kwargs: Additional response attributes

        Returns:
            Audit event ID
        """
        pass

    @abstractmethod
    async def audit_error(
        self,
        request_id: str,
        error_message: str,
        **kwargs,
    ) -> str:
        """Audit an error during request processing.

        Args:
            request_id: Request identifier
            error_message: Error message
            **kwargs: Additional error attributes

        Returns:
            Audit event ID
        """
        pass
