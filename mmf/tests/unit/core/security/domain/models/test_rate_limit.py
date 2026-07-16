from datetime import datetime, timedelta

import pytest

from mmf.core.security.domain.models.rate_limit import (
    RateLimitMetrics,
    RateLimitQuota,
    RateLimitResult,
    RateLimitRule,
    RateLimitScope,
    RateLimitStrategy,
    RateLimitWindow,
)


class TestRateLimitRule:
    def test_valid_rule(self):
        rule = RateLimitRule(
            name="test-rule",
            scope=RateLimitScope.PER_USER,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            limit=100,
            window_seconds=60,
            burst_size=10,
        )
        assert rule.limit == 100
        assert rule.window_seconds == 60
        assert rule.burst_size == 10

    def test_invalid_limit(self):
        with pytest.raises(ValueError, match="Rate limit must be positive"):
            RateLimitRule(
                name="test-rule",
                scope=RateLimitScope.PER_USER,
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                limit=0,
                window_seconds=60,
            )

    def test_invalid_window(self):
        with pytest.raises(ValueError, match="Window size must be positive"):
            RateLimitRule(
                name="test-rule",
                scope=RateLimitScope.PER_USER,
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                limit=100,
                window_seconds=0,
            )

    def test_invalid_burst(self):
        with pytest.raises(ValueError, match="Burst size cannot be negative"):
            RateLimitRule(
                name="test-rule",
                scope=RateLimitScope.PER_USER,
                strategy=RateLimitStrategy.TOKEN_BUCKET,
                limit=100,
                window_seconds=60,
                burst_size=-1,
            )


class TestRateLimitWindow:
    def test_window_expiry(self):
        reset_time = datetime.utcnow() - timedelta(seconds=1)
        window = RateLimitWindow(key="test-key", current_count=10, reset_time=reset_time)
        assert window.is_expired

    def test_window_not_expired(self):
        reset_time = datetime.utcnow() + timedelta(seconds=60)
        window = RateLimitWindow(key="test-key", current_count=10, reset_time=reset_time)
        assert not window.is_expired

    def test_window_reset(self):
        window = RateLimitWindow(
            key="test-key", current_count=10, reset_time=datetime.utcnow(), burst_count=5
        )
        window.reset(window_seconds=60)
        assert window.current_count == 0
        assert window.burst_count == 0
        assert window.reset_time > datetime.utcnow()


class TestRateLimitResult:
    def test_remaining_calculation(self):
        result = RateLimitResult(
            allowed=True,
            rule_name="test-rule",
            current_count=10,
            limit=100,
            reset_time=datetime.utcnow(),
        )
        assert result.remaining == 90

    def test_remaining_zero_when_exceeded(self):
        result = RateLimitResult(
            allowed=False,
            rule_name="test-rule",
            current_count=110,
            limit=100,
            reset_time=datetime.utcnow(),
        )
        assert result.remaining == 0


class TestRateLimitQuota:
    def test_cache_key_generation(self):
        quota = RateLimitQuota(
            user_id="user-123", ip_address="127.0.0.1", endpoint="/api/test", service="auth-service"
        )

        rule_user = RateLimitRule(
            name="user-rule",
            scope=RateLimitScope.PER_USER,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=10,
            window_seconds=60,
        )
        assert quota.get_cache_key(rule_user) == "rate_limit:user-rule:user:user-123"

        rule_ip = RateLimitRule(
            name="ip-rule",
            scope=RateLimitScope.PER_IP,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=10,
            window_seconds=60,
        )
        assert quota.get_cache_key(rule_ip) == "rate_limit:ip-rule:ip:127.0.0.1"

        rule_global = RateLimitRule(
            name="global-rule",
            scope=RateLimitScope.GLOBAL,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=10,
            window_seconds=60,
        )
        assert quota.get_cache_key(rule_global) == "rate_limit:global-rule:global"


class TestRateLimitMetrics:
    def test_metrics_recording(self):
        metrics = RateLimitMetrics()

        metrics.record_request(allowed=True)
        metrics.record_request(allowed=False, rule_name="limit-rule")
        metrics.record_request(allowed=True)

        assert metrics.total_requests == 3
        assert metrics.allowed_requests == 2
        assert metrics.blocked_requests == 1
        assert metrics.rules_triggered["limit-rule"] == 1

        assert metrics.block_rate == pytest.approx(33.33, 0.01)
        assert metrics.allow_rate == pytest.approx(66.66, 0.01)

    def test_empty_metrics(self):
        metrics = RateLimitMetrics()
        assert metrics.block_rate == 0.0
        assert metrics.allow_rate == 100.0
