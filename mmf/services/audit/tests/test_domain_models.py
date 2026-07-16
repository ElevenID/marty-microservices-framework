from datetime import datetime, timezone
from uuid import uuid4

import pytest

from mmf.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity
from mmf.services.audit.domain.entities import RequestAuditEvent
from mmf.services.audit.domain.value_objects import (
    ActorInfo,
    PerformanceMetrics,
    RequestContext,
    ResourceInfo,
    ResponseMetadata,
    ServiceContext,
)


@pytest.mark.unit
class TestRequestAuditEvent:
    def test_initialization(self):
        event_id = uuid4()
        event = RequestAuditEvent(
            event_id=event_id,
            event_type=AuditEventType.API_REQUEST,
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            message="Test event",
        )

        assert event.id == event_id
        assert event.event_type == AuditEventType.API_REQUEST
        assert event.severity == AuditSeverity.INFO
        assert event.outcome == AuditOutcome.SUCCESS
        assert event.message == "Test event"
        assert event.timestamp is not None

    def test_should_forward_to_compliance(self):
        # Info severity should not forward
        event_info = RequestAuditEvent(severity=AuditSeverity.INFO)
        assert not event_info.should_forward_to_compliance()

        # Low severity should not forward
        event_low = RequestAuditEvent(severity=AuditSeverity.LOW)
        assert not event_low.should_forward_to_compliance()

        # High severity should forward
        event_high = RequestAuditEvent(severity=AuditSeverity.HIGH)
        assert event_high.should_forward_to_compliance()

        # Critical severity should forward
        event_critical = RequestAuditEvent(severity=AuditSeverity.CRITICAL)
        assert event_critical.should_forward_to_compliance()

    def test_to_dict(self):
        event = RequestAuditEvent(message="Test event", details={"key": "value"})
        data = event.to_dict()

        assert data["message"] == "Test event"
        assert data["details"] == {"key": "value"}
        assert "timestamp" in data
        assert "event_type" in data
        assert "severity" in data


@pytest.mark.unit
class TestValueObjects:
    def test_request_context(self):
        ctx = RequestContext(method="GET", endpoint="/api/test", source_ip="127.0.0.1")
        data = ctx.to_dict()
        assert data["method"] == "GET"
        assert data["endpoint"] == "/api/test"
        assert data["source_ip"] == "127.0.0.1"

    def test_response_metadata(self):
        meta = ResponseMetadata(status_code=200, response_size=1024)
        data = meta.to_dict()
        assert data["status_code"] == 200
        assert data["response_size"] == 1024

    def test_performance_metrics(self):
        now = datetime.now(timezone.utc)
        metrics = PerformanceMetrics(duration_ms=100.5, started_at=now, completed_at=now)
        data = metrics.to_dict()
        assert data["duration_ms"] == 100.5
        assert data["started_at"] == now.isoformat()

    def test_actor_info(self):
        actor = ActorInfo(user_id="user123", roles=("admin", "user"))
        data = actor.to_dict()
        assert data["user_id"] == "user123"
        assert data["roles"] == ["admin", "user"]
