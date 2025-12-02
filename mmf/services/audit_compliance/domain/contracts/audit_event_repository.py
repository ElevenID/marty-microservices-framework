"""Audit event repository port interface for the domain layer."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from mmf.core.domain import Repository

from ..models.security_audit_event import SecurityAuditEvent


class IAuditEventRepository(Repository[SecurityAuditEvent], ABC):
    """Port interface for audit event repository operations."""

    @abstractmethod
    async def find_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SecurityAuditEvent]:
        """Find audit events within a time range.

        Args:
            start_time: Start of the time range
            end_time: End of the time range
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of audit events within the time range
        """
        pass

    @abstractmethod
    async def find_by_event_type(
        self,
        event_types: list[str],
        limit: int = 100,
        offset: int = 0,
    ) -> list[SecurityAuditEvent]:
        """Find audit events by event types.

        Args:
            event_types: List of event type strings to search for
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of matching audit events
        """
        pass

    @abstractmethod
    async def find_by_principal(
        self,
        principal_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SecurityAuditEvent]:
        """Find audit events by principal ID.

        Args:
            principal_id: The principal ID to search for
            limit: Maximum number of events to return
            offset: Number of events to skip

        Returns:
            List of audit events for the principal
        """
        pass

    @abstractmethod
    async def find_critical_events(
        self,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[SecurityAuditEvent]:
        """Find critical security audit events.

        Args:
            since: Optional timestamp to search from
            limit: Maximum number of events to return

        Returns:
            List of critical audit events
        """
        pass

    @abstractmethod
    async def save_batch(self, events: list[SecurityAuditEvent]) -> list[SecurityAuditEvent]:
        """Save multiple audit events efficiently.

        Args:
            events: List of audit events to save

        Returns:
            List of saved audit events with updated fields
        """
        pass

    @abstractmethod
    async def count_by_time_range(
        self,
        start_time: datetime,
        end_time: datetime,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count audit events within a time range with optional filters.

        Args:
            start_time: Start of the time range
            end_time: End of the time range
            filters: Optional filters to apply

        Returns:
            Count of matching audit events
        """
        pass

    @abstractmethod
    async def get_event_statistics(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Get statistics for audit events within a time range.

        Args:
            start_time: Start of the time range
            end_time: End of the time range

        Returns:
            Dictionary with event statistics
        """
        pass

    @abstractmethod
    async def cleanup_old_events(
        self,
        older_than: datetime,
        batch_size: int = 1000,
    ) -> int:
        """Clean up audit events older than the specified date.

        Args:
            older_than: Delete events older than this date
            batch_size: Number of events to delete per batch

        Returns:
            Number of events deleted
        """
        pass
