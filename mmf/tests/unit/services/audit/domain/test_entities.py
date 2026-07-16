"""
Unit tests for Audit domain entities.
"""

from datetime import datetime, timezone
from uuid import uuid4

from mmf.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity
from mmf.services.audit.domain.entities import RequestAuditEvent
from mmf.services.audit.domain.value_objects import RequestContext


class TestRequestAuditEvent:
    """Test suite for RequestAuditEvent entity."""

    def test_create_minimal(self):
        """Test creating event with minimal fields."""
        event = RequestAuditEvent(message="Test event")

        assert event.message == "Test event"
        assert event.event_type == AuditEventType.API_REQUEST
        assert event.severity == AuditSeverity.INFO
        assert event.outcome == AuditOutcome.SUCCESS
        assert event.timestamp is not None
        assert event.timestamp.tzinfo == timezone.utc
        assert event.details == {}
        assert event.encrypted_fields == []

    def test_create_full(self):
        """Test creating event with all fields."""
        event_id = uuid4()
        req_ctx = RequestContext(method="GET", endpoint="/test")
        now = datetime.now(timezone.utc)

        event = RequestAuditEvent(
            event_id=event_id,
            event_type=AuditEventType.SECURITY_INTRUSION_ATTEMPT,
            severity=AuditSeverity.CRITICAL,
            outcome=AuditOutcome.FAILURE,
            timestamp=now,
            message="Security breach",
            request_context=req_ctx,
            details={"ip": "1.2.3.4"},
            encrypted_fields=["password"],
            security_event_id="sec-123",
        )

        assert event.id == event_id
        assert event.event_type == AuditEventType.SECURITY_INTRUSION_ATTEMPT
        assert event.severity == AuditSeverity.CRITICAL
        assert event.outcome == AuditOutcome.FAILURE
        assert event.timestamp == now
        assert event.request_context == req_ctx
        assert event.details["ip"] == "1.2.3.4"
        assert "password" in event.encrypted_fields
        assert event.security_event_id == "sec-123"

    def test_should_forward_to_compliance(self):
        """Test compliance forwarding logic."""
        # Info severity - should not forward
        event_info = RequestAuditEvent(severity=AuditSeverity.INFO)
        assert event_info.should_forward_to_compliance() is False

        # Medium severity - should not forward
        event_med = RequestAuditEvent(severity=AuditSeverity.MEDIUM)
        assert event_med.should_forward_to_compliance() is False

        # High severity - should forward
        event_high = RequestAuditEvent(severity=AuditSeverity.HIGH)
        assert event_high.should_forward_to_compliance() is True

        # Critical severity - should forward
        event_crit = RequestAuditEvent(severity=AuditSeverity.CRITICAL)
        assert event_crit.should_forward_to_compliance() is True

    def test_to_dict(self):
        """Test dictionary conversion."""
        req_ctx = RequestContext(method="GET", endpoint="/test")
        event = RequestAuditEvent(
            message="Test", severity=AuditSeverity.HIGH, request_context=req_ctx
        )

        data = event.to_dict()

        assert data["message"] == "Test"
        assert data["severity"] == "high"
        assert data["request_context"]["method"] == "GET"
        assert "timestamp" in data
