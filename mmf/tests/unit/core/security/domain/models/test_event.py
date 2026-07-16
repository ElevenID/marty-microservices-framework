from datetime import datetime, timezone

import pytest

from mmf.core.security.domain.models.event import AuditEvent


class TestAuditEvent:
    def test_audit_event_creation_defaults(self):
        event = AuditEvent(
            event_type="login",
            principal_id="user-123",
            resource="auth-service",
            action="authenticate",
            result="success",
        )

        assert event.event_type == "login"
        assert event.principal_id == "user-123"
        assert event.resource == "auth-service"
        assert event.action == "authenticate"
        assert event.result == "success"
        assert event.details == {}
        assert isinstance(event.timestamp, datetime)
        assert event.timestamp.tzinfo == timezone.utc
        assert event.session_id is None

    def test_audit_event_full_creation(self):
        details = {"ip": "127.0.0.1", "method": "password"}
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        event = AuditEvent(
            event_type="access_denied",
            principal_id="user-456",
            resource="admin-panel",
            action="delete",
            result="failure",
            details=details,
            timestamp=timestamp,
            session_id="sess-789",
        )

        assert event.event_type == "access_denied"
        assert event.principal_id == "user-456"
        assert event.resource == "admin-panel"
        assert event.action == "delete"
        assert event.result == "failure"
        assert event.details == details
        assert event.timestamp == timestamp
        assert event.session_id == "sess-789"
