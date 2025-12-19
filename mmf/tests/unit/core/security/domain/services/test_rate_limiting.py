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
        return RateLimitQuota(ip_address="127.0.0.1")

    def test_check_limit_disabled_rule(self, engine, quota):
        rule = RateLimitRule(
            name="disabled",
            scope=RateLimitScope.PER_IP,
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
            name="invalid",
            scope=RateLimitScope.PER_IP,
            strategy="INVALID_STRATEGY",  # type: ignore
            limit=10,
            window_seconds=60,
        )
        with pytest.raises(ValueError, match="Unsupported rate limit strategy"):
            engine.check_limit(rule, quota)

    def test_fixed_window_check_allow(self, engine, quota):
        rule = RateLimitRule(
            name="fixed",
            scope=RateLimitScope.PER_IP,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=10,
            window_seconds=60,
        )
        result = engine.check_limit(rule, quota)
        assert result.allowed is True
        assert result.current_count == 1

    def test_fixed_window_check_block(self, engine, quota):
        rule = RateLimitRule(
            name="fixed",
            scope=RateLimitScope.PER_IP,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=1,
            window_seconds=60,
        )
        # First request allowed
        window = RateLimitWindow(
            key=quota.get_cache_key(rule),
            current_count=1,
            reset_time=datetime.utcnow() + timedelta(seconds=60),
        )

        # Second request blocked
        result = engine.check_limit(rule, quota, current_window=window)
        assert result.allowed is False
        assert result.retry_after_seconds > 0

    def test_token_bucket_check(self, engine, quota):
        rule = RateLimitRule(
            name="token",
            scope=RateLimitScope.PER_IP,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            limit=10,
            window_seconds=60,
        )
        result = engine.check_limit(rule, quota)
        # Token bucket starts full, so it should be allowed
        # Implementation details: current_count starts at limit, decrements.
        # Wait, implementation says:
        # current_window.current_count = limit
        # if current_count >= 1: current_count -= 1, allowed=True
        # result.current_count = limit - current_window.current_count

        assert result.allowed is True
        # Initial: 10. Consumed 1. Remaining 9.
        # Result current_count is "used count" or "remaining"?
        # Code: current_count=rule.limit - current_window.current_count
        # So if window.current_count is 9, result.current_count is 10-9=1.
        assert result.current_count == 1

    def test_sliding_window_check(self, engine, quota):
        rule = RateLimitRule(
            name="sliding",
            scope=RateLimitScope.PER_IP,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
            limit=10,
            window_seconds=60,
        )
        result = engine.check_limit(rule, quota)
        assert result.allowed is True
        assert result.current_count == 1

    def test_leaky_bucket_check(self, engine, quota):
        rule = RateLimitRule(
            name="leaky",
            scope=RateLimitScope.PER_IP,
            strategy=RateLimitStrategy.LEAKY_BUCKET,
            limit=10,
            window_seconds=60,
        )
        result = engine.check_limit(rule, quota)
        assert result.allowed is True
        assert result.current_count == 1


class TestSessionCleanupService:
    @pytest.fixture
    def service(self):
        return SessionCleanupService(cleanup_interval_minutes=5)

    def test_should_run_cleanup_true(self, service):
        service.last_cleanup = datetime.utcnow() - timedelta(minutes=6)
        assert service.should_run_cleanup() is True

    def test_should_run_cleanup_false(self, service):
        service.last_cleanup = datetime.utcnow() - timedelta(minutes=1)
        assert service.should_run_cleanup() is False

    def test_mark_cleanup_completed(self, service):
        old_time = service.last_cleanup
        service.mark_cleanup_completed()
        assert service.last_cleanup > old_time

    @pytest.mark.parametrize(
        "age,expected_priority", [(721, 5), (481, 4), (241, 3), (61, 2), (30, 1)]
    )
    def test_calculate_cleanup_priority(self, service, age, expected_priority):
        assert service.calculate_cleanup_priority(age) == expected_priority


class TestRateLimitCoordinationService:
    @pytest.fixture
    def service(self):
        return RateLimitCoordinationService(istio_safety_multiplier=2.0)

    def test_calculate_istio_limit(self, service):
        assert service.calculate_istio_limit(100) == 200

    def test_should_apply_istio_limit(self, service):
        # Allowed and authenticated -> False
        result_allowed = Mock(spec=RateLimitResult)
        result_allowed.allowed = True
        assert service.should_apply_istio_limit(result_allowed, user_authenticated=True) is False

        # Blocked and authenticated -> True
        result_blocked = Mock(spec=RateLimitResult)
        result_blocked.allowed = False
        assert service.should_apply_istio_limit(result_blocked, user_authenticated=True) is True

        # Allowed and unauthenticated -> True
        assert service.should_apply_istio_limit(result_allowed, user_authenticated=False) is True

    def test_create_coordination_metadata(self, service):
        result = Mock(spec=RateLimitResult)
        result.allowed = False
        result.current_count = 101
        result.limit = 100

        metadata = service.create_coordination_metadata(result)
        assert metadata["app_limit_hit"] is True
        assert metadata["app_current_count"] == 101
        assert metadata["app_limit"] == 100
        assert metadata["istio_limit"] == 200
        assert metadata["coordination_strategy"] == "safety_net"
