"""SIEM adapter port interface for the domain layer."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from mmf_new.core.domain import SecurityEvent

from ..models.security_audit_event import SecurityAuditEvent


class ISIEMAdapter(ABC):
    """Port interface for SIEM integration operations."""

    @abstractmethod
    async def send_event(self, event: SecurityEvent | SecurityAuditEvent) -> bool:
        """Send a security event to the SIEM system.

        Args:
            event: The security event to send

        Returns:
            True if successfully sent, False otherwise
        """
        pass

    @abstractmethod
    async def send_events_batch(
        self, events: list[SecurityEvent | SecurityAuditEvent]
    ) -> dict[str, Any]:
        """Send multiple events to the SIEM system in batch.

        Args:
            events: List of security events to send

        Returns:
            Dictionary with batch results (success count, failures, etc.)
        """
        pass

    @abstractmethod
    async def query_events(
        self,
        query: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query events from the SIEM system.

        Args:
            query: SIEM-specific query string
            start_time: Start time for the query
            end_time: End time for the query
            limit: Maximum number of results

        Returns:
            List of matching events
        """
        pass

    @abstractmethod
    async def create_alert(
        self,
        title: str,
        description: str,
        severity: str,
        event_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create an alert in the SIEM system.

        Args:
            title: Alert title
            description: Alert description
            severity: Alert severity level
            event_ids: Related event IDs
            metadata: Additional alert metadata

        Returns:
            Alert ID from the SIEM system
        """
        pass

    @abstractmethod
    async def get_connection_status(self) -> dict[str, Any]:
        """Get the connection status to the SIEM system.

        Returns:
            Dictionary with connection status and health information
        """
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the connection to the SIEM system.

        Returns:
            True if connection is successful, False otherwise
        """
        pass
