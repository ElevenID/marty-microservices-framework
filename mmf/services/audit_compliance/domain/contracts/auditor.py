"""Auditor port interface for the domain layer."""

from abc import ABC, abstractmethod
from typing import Any

from ..models.security_audit_event import SecurityAuditEvent


class IAuditor(ABC):
    """Port interface for audit event logging."""

    @abstractmethod
    async def audit_event(self, event: SecurityAuditEvent) -> None:
        """Log an audit event.

        Args:
            event: The security audit event to log
        """
        pass

    @abstractmethod
    async def audit_event_dict(self, event_type: str, details: dict[str, Any]) -> None:
        """Log an audit event from dictionary data.

        Args:
            event_type: Type of security event
            details: Event details and metadata
        """
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Flush any pending audit events."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the auditor and cleanup resources."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Check if the auditor is healthy and operational."""
        pass
