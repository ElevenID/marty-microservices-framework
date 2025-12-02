from datetime import datetime, timedelta

import pytest

from mmf.core.security.domain.models.session import (
    SessionData,
    SessionEventType,
    SessionLifecycle,
    SessionMetrics,
    SessionSecurityPolicy,
    SessionState,
)


class TestSessionData:
    def test_create_session(self):
        session = SessionData.create(
            user_id="user-123",
            timeout_minutes=60,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            role="admin",
        )

        assert session.user_id == "user-123"
        assert session.state == SessionState.ACTIVE
        assert session.ip_address == "127.0.0.1"
        assert session.user_agent == "test-agent"
        assert session.attributes["role"] == "admin"
        assert not session.is_expired
        assert session.time_remaining.total_seconds() > 0

    def test_session_expiry(self):
        session = SessionData.create(user_id="user-123", timeout_minutes=-1)
        assert session.is_expired
        assert session.time_remaining.total_seconds() == 0

    def test_session_extension(self):
        session = SessionData.create(user_id="user-123", timeout_minutes=10)
        original_expiry = session.expires_at

        session.extend(minutes=20)
        assert session.expires_at > original_expiry
        assert not session.is_expired

    def test_session_termination(self):
        session = SessionData.create(user_id="user-123")
        session.terminate(reason=SessionEventType.LOGOUT)

        assert session.state == SessionState.TERMINATED
        assert session.attributes["termination_reason"] == "logout"
        assert session.is_expired  # Terminated sessions are considered expired

    def test_session_invalidation(self):
        session = SessionData.create(user_id="user-123")
        session.invalidate()

        assert session.state == SessionState.INVALID
        assert session.is_expired


class TestSessionLifecycle:
    def test_expiration_calculation(self):
        lifecycle = SessionLifecycle(
            default_timeout_minutes=30,
            max_timeout_minutes=60,
            idle_timeout_minutes=10,
            absolute_timeout_minutes=120,
        )

        now = datetime.utcnow()
        created_at = now - timedelta(minutes=50)
        last_accessed = now - timedelta(minutes=5)

        # Should be limited by max_timeout_minutes (60) from now?
        # No, calculate_expiration logic:
        # timeout_expiry = now + min(requested or default, max)
        # idle_expiry = last_accessed + idle
        # absolute_expiry = created_at + absolute

        expiry = lifecycle.calculate_expiration(created_at, last_accessed)

        # idle_expiry = now - 5 + 10 = now + 5
        # absolute_expiry = now - 50 + 120 = now + 70
        # timeout_expiry = now + 30

        # Min is idle_expiry (now + 5)
        assert expiry < now + timedelta(minutes=6)
        assert expiry > now + timedelta(minutes=4)


class TestSessionMetrics:
    def test_metrics_recording(self):
        metrics = SessionMetrics()

        metrics.record_session_created()
        metrics.record_session_created()
        assert metrics.active_sessions == 2
        assert metrics.total_sessions_created == 2
        assert metrics.peak_concurrent_sessions == 2

        metrics.record_session_terminated(SessionEventType.LOGOUT)
        assert metrics.active_sessions == 1
        assert metrics.terminated_sessions == 1
        assert metrics.cleanup_events["logout"] == 1

        metrics.record_session_expired()
        assert metrics.active_sessions == 0
        assert metrics.expired_sessions == 1


class TestSessionSecurityPolicy:
    def test_validation_no_violations(self):
        policy = SessionSecurityPolicy(detect_session_hijacking=True)
        session = SessionData.create(
            user_id="user-123", ip_address="127.0.0.1", user_agent="agent-1"
        )

        violations = policy.validate_session_request(
            session, current_ip="127.0.0.1", current_user_agent="agent-1"
        )
        assert len(violations) == 0

    def test_validation_violations(self):
        policy = SessionSecurityPolicy(detect_session_hijacking=True)
        session = SessionData.create(
            user_id="user-123", ip_address="127.0.0.1", user_agent="agent-1"
        )

        violations = policy.validate_session_request(
            session, current_ip="192.168.1.1", current_user_agent="agent-2"
        )
        assert len(violations) == 2
        assert "IP address mismatch detected" in violations
        assert "User agent mismatch detected" in violations
