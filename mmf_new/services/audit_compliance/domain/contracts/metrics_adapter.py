"""
Metrics adapter contract.
"""

from typing import Any, Protocol


class IMetricsAdapter(Protocol):
    """Interface for metrics adapter."""

    def record_audit_event(self, event_type: str, status: str) -> None:
        """Record an audit event."""
        ...

    def record_compliance_check(self, check_id: str, status: str) -> None:
        """Record a compliance check."""
        ...

    def record_threat_detection(self, threat_type: str, severity: str) -> None:
        """Record a threat detection."""
        ...
