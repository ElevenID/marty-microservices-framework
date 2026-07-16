from datetime import datetime

import pytest

from mmf.core.security.domain.models.event import AuditEvent


class TestAuditEvent:
    def test_defaults(self):
        event = AuditEvent(
            event_type="login",
            principal_id="user-1",
            resource=None,
            action="authenticate",
            result="success",
        )

        assert event.event_type == "login"
        assert event.principal_id == "user-1"
        assert event.resource is None
        assert event.action == "authenticate"
        assert event.result == "success"
        assert event.details == {}
        assert isinstance(event.timestamp, datetime)
        assert event.session_id is None

    def test_full_initialization(self):
        details = {"ip": "127.0.0.1"}
        event = AuditEvent(
            event_type="access_denied",
            principal_id="user-2",
            resource="doc-1",
            action="read",
            result="failure",
            details=details,
            session_id="sess-123",
        )

        assert event.resource == "doc-1"
        assert event.details == details
        assert event.session_id == "sess-123"
