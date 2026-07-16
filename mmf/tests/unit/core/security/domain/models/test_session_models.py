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
    def test_create(self):
        session = SessionData.create(
            user_id="user1",
            timeout_minutes=60,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            custom_attr="value",
        )

        assert session.user_id == "user1"
        assert session.state == SessionState.ACTIVE
        assert session.ip_address == "127.0.0.1"
        assert session.user_agent == "test-agent"
        assert session.attributes["custom_attr"] == "value"
        assert session.session_id is not None
        assert session.created_at is not None
        assert session.expires_at > session.created_at

    def test_is_expired(self):
        session = SessionData.create("user1", timeout_minutes=-1)  # Expired immediately
        assert session.is_expired is True

        session = SessionData.create("user1", timeout_minutes=60)
        assert session.is_expired is False

        session.state = SessionState.TERMINATED
        assert session.is_expired is True

    def test_time_remaining(self):
        session = SessionData.create("user1", timeout_minutes=60)
        remaining = session.time_remaining
        assert remaining.total_seconds() > 0

        session = SessionData.create("user1", timeout_minutes=-1)
        assert session.time_remaining.total_seconds() == 0

    def test_age(self):
        session = SessionData.create("user1")
        assert session.age.total_seconds() >= 0

    def test_extend(self):
        session = SessionData.create("user1", timeout_minutes=10)
        original_expiry = session.expires_at

        session.extend(minutes=20)
        assert session.expires_at > original_expiry

    def test_touch(self):
        session = SessionData.create("user1")
        original_access = session.last_accessed

        # Wait a tiny bit to ensure timestamp difference
        import time

        time.sleep(0.001)

        session.touch()
        assert session.last_accessed > original_access

    def test_terminate(self):
        session = SessionData.create("user1")
        session.terminate(reason=SessionEventType.LOGOUT)

        assert session.state == SessionState.TERMINATED
        assert session.attributes["termination_reason"] == SessionEventType.LOGOUT.value
        assert "terminated_at" in session.attributes

    def test_invalidate(self):
        session = SessionData.create("user1")
        session.invalidate()
        assert session.state == SessionState.INVALID

    def test_get_cache_key(self):
        session = SessionData.create("user1")
        key = session.get_cache_key("prefix")
        assert key == f"prefix:{session.session_id}"


class TestSessionLifecycle:
    def test_calculate_expiration(self):
        lifecycle = SessionLifecycle(
            default_timeout_minutes=30,
            max_timeout_minutes=60,
            idle_timeout_minutes=10,
            absolute_timeout_minutes=120,
        )

        now = datetime.utcnow()
        created_at = now
        last_accessed = now

        # Case 1: Idle timeout is earliest
        expiry = lifecycle.calculate_expiration(created_at, last_accessed)
        # Should be now + 10 mins (idle) vs now + 30 mins (default) vs now + 120 mins (absolute)
        expected = last_accessed + timedelta(minutes=10)
        assert abs((expiry - expected).total_seconds()) < 1

        # Case 2: Requested timeout is respected but capped
        expiry = lifecycle.calculate_expiration(created_at, last_accessed, requested_timeout=100)
        # Requested 100, capped at 60.
        # Idle is still 10 mins from last_accessed.
        # So idle wins again if last_accessed is now.

        # Let's move last_accessed so idle isn't the limiting factor
        last_accessed = now + timedelta(minutes=50)
        # Idle expiry = now + 50 + 10 = now + 60
        # Timeout expiry = now + 60 (capped)
        # Absolute expiry = now + 120

        expiry = lifecycle.calculate_expiration(created_at, last_accessed, requested_timeout=100)
        # Should be around now + 60
        expected = now + timedelta(minutes=60)
        assert abs((expiry - expected).total_seconds()) < 1


class TestSessionMetrics:
    def test_metrics_recording(self):
        metrics = SessionMetrics()

        metrics.record_session_created()
        assert metrics.total_sessions_created == 1
        assert metrics.active_sessions == 1
        assert metrics.peak_concurrent_sessions == 1

        metrics.record_session_created()
        assert metrics.active_sessions == 2
        assert metrics.peak_concurrent_sessions == 2

        metrics.record_session_terminated(SessionEventType.LOGOUT)
        assert metrics.active_sessions == 1
        assert metrics.terminated_sessions == 1
        assert metrics.cleanup_events[SessionEventType.LOGOUT.value] == 1

        metrics.record_session_expired()
        assert metrics.active_sessions == 0
        assert metrics.expired_sessions == 1

        metrics.record_cleanup_operation()
        assert metrics.cleanup_operations == 1


class TestSessionSecurityPolicy:
    def test_validate_session_request(self):
        policy = SessionSecurityPolicy(detect_session_hijacking=True)
        session = SessionData.create("user1", ip_address="1.2.3.4", user_agent="Mozilla/5.0")

        # Valid request
        violations = policy.validate_session_request(
            session, current_ip="1.2.3.4", current_user_agent="Mozilla/5.0"
        )
        assert len(violations) == 0

        # IP mismatch
        violations = policy.validate_session_request(
            session, current_ip="5.6.7.8", current_user_agent="Mozilla/5.0"
        )
        assert "IP address mismatch detected" in violations

        # User Agent mismatch
        violations = policy.validate_session_request(
            session, current_ip="1.2.3.4", current_user_agent="Chrome/90.0"
        )
        assert "User agent mismatch detected" in violations

    def test_validate_session_request_disabled_checks(self):
        policy = SessionSecurityPolicy(detect_session_hijacking=False)
        session = SessionData.create("user1", ip_address="1.2.3.4", user_agent="Mozilla/5.0")

        violations = policy.validate_session_request(
            session,
            current_ip="5.6.7.8",  # Mismatch
            current_user_agent="Chrome/90.0",  # Mismatch
        )
        assert len(violations) == 0
