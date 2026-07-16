from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from mmf.core.security.domain.models.rate_limit import (
    RateLimitQuota,
    RateLimitResult,
    RateLimitRule,
    RateLimitScope,
    RateLimitStrategy,
    RateLimitWindow,
)
from mmf.core.security.domain.services.rate_limiting import (
    RateLimitCoordinationService,
    RateLimitEngine,
    SessionCleanupService,
)


class TestRateLimitEngine:
    @pytest.fixture
    def engine(self):
        return RateLimitEngine()

    @pytest.fixture
    def quota(self):
        return RateLimitQuota(user_id="user1")

    def test_check_limit_disabled_rule(self, engine, quota):
        rule = RateLimitRule(
            name="disabled",
            scope=RateLimitScope.GLOBAL,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=10,
            window_seconds=60,
            enabled=False,
        )
        result = engine.check_limit(rule, quota)
        assert result.allowed is True
        assert result.current_count == 0

    def test_check_limit_unsupported_strategy(self, engine, quota):
        rule = RateLimitRule(
            name="test",
            scope=RateLimitScope.GLOBAL,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=10,
            window_seconds=60,
        )
        # Hack to inject unsupported strategy
        rule.strategy = "unsupported"

        with pytest.raises(ValueError, match="Unsupported rate limit strategy"):
            engine.check_limit(rule, quota)

    def test_token_bucket_check(self, engine, quota):
        rule = RateLimitRule(
            name="token",
            scope=RateLimitScope.GLOBAL,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            limit=10,
            window_seconds=10,  # 1 token per second
        )

        # Initial check - full bucket
        result = engine.check_limit(rule, quota)
        assert result.allowed is True
        assert result.current_count == 1  # 1 used

        # Simulate empty bucket
        window = RateLimitWindow(
            key="key",
            current_count=0,  # Empty
            reset_time=datetime.utcnow(),
        )
        # Need to mock time to control refill
        # But the implementation uses created_at to calculate refill.
        # Let's just test the logic with a window passed in.

        # Case: Empty bucket, no time passed
        result = engine._token_bucket_check(rule, quota, window)
        assert result.allowed is False
        assert result.retry_after_seconds > 0

    def test_fixed_window_check(self, engine, quota):
        rule = RateLimitRule(
            name="fixed",
            scope=RateLimitScope.GLOBAL,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=2,
            window_seconds=60,
        )

        # 1st request
        result = engine.check_limit(rule, quota)
        assert result.allowed is True
        assert result.current_count == 1

        # Reuse window for 2nd request
        # We need to capture the window state if we want to reuse it,
        # but check_limit doesn't return the window object, only result.
        # So we manually create a window.
        window = RateLimitWindow(
            key="key", current_count=1, reset_time=datetime.utcnow() + timedelta(seconds=60)
        )

        # 2nd request
        result = engine.check_limit(rule, quota, window)
        assert result.allowed is True
        assert result.current_count == 2

        # 3rd request (blocked)
        result = engine.check_limit(rule, quota, window)
        assert result.allowed is False
        assert result.retry_after_seconds > 0

    def test_sliding_window_check(self, engine, quota):
        rule = RateLimitRule(
            name="sliding",
            scope=RateLimitScope.GLOBAL,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
            limit=2,
            window_seconds=60,
        )

        # 1st request
        result = engine.check_limit(rule, quota)
        assert result.allowed is True

        # Simulate window near limit
        window = RateLimitWindow(
            key="key", current_count=2, reset_time=datetime.utcnow() + timedelta(seconds=60)
        )

        # Blocked
        result = engine.check_limit(rule, quota, window)
        assert result.allowed is False

    def test_leaky_bucket_check(self, engine, quota):
        rule = RateLimitRule(
            name="leaky",
            scope=RateLimitScope.GLOBAL,
            strategy=RateLimitStrategy.LEAKY_BUCKET,
            limit=10,
            window_seconds=10,  # 1 req/sec leak rate
        )

        # 1st request
        result = engine.check_limit(rule, quota)
        assert result.allowed is True

        # Simulate full bucket
        window = RateLimitWindow(
            key="key", current_count=10, reset_time=datetime.utcnow() + timedelta(seconds=60)
        )

        # Blocked
        result = engine.check_limit(rule, quota, window)
        assert result.allowed is False


class TestSessionCleanupService:
    def test_should_run_cleanup(self):
        service = SessionCleanupService(cleanup_interval_minutes=5)

        # Just initialized, shouldn't run yet (unless we wait 5 mins)
        # Wait, logic is (now - last_cleanup) >= interval.
        # last_cleanup is set to now() on init.
        assert service.should_run_cleanup() is False

        # Mock last_cleanup to be old
        service.last_cleanup = datetime.utcnow() - timedelta(minutes=6)
        assert service.should_run_cleanup() is True

    def test_mark_cleanup_completed(self):
        service = SessionCleanupService()
        old_time = service.last_cleanup

        # Ensure time passes
        import time

        time.sleep(0.001)

        service.mark_cleanup_completed()
        assert service.last_cleanup > old_time

    def test_calculate_cleanup_priority(self):
        service = SessionCleanupService()

        assert service.calculate_cleanup_priority(30) == 1
        assert service.calculate_cleanup_priority(90) == 2
        assert service.calculate_cleanup_priority(300) == 3
        assert service.calculate_cleanup_priority(500) == 4
        assert service.calculate_cleanup_priority(800) == 5


class TestRateLimitCoordinationService:
    def test_calculate_istio_limit(self):
        service = RateLimitCoordinationService(istio_safety_multiplier=2.0)
        assert service.calculate_istio_limit(100) == 200

    def test_should_apply_istio_limit(self):
        service = RateLimitCoordinationService()

        # Allowed app result, authenticated -> False
        res_allowed = RateLimitResult(True, "r", 1, 10, datetime.utcnow())
        assert service.should_apply_istio_limit(res_allowed, user_authenticated=True) is False

        # Blocked app result -> True
        res_blocked = RateLimitResult(False, "r", 11, 10, datetime.utcnow())
        assert service.should_apply_istio_limit(res_blocked, user_authenticated=True) is True

        # Unauthenticated -> True
        assert service.should_apply_istio_limit(res_allowed, user_authenticated=False) is True

    def test_create_coordination_metadata(self):
        service = RateLimitCoordinationService()
        res = RateLimitResult(False, "r", 11, 10, datetime.utcnow())

        meta = service.create_coordination_metadata(res)
        assert meta["app_limit_hit"] is True
        assert meta["app_limit"] == 10
        assert meta["istio_limit"] == 20
