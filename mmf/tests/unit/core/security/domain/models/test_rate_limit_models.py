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
    def test_create_valid(self):
        rule = RateLimitRule(
            name="test-rule",
            scope=RateLimitScope.GLOBAL,
            strategy=RateLimitStrategy.FIXED_WINDOW,
            limit=100,
            window_seconds=60,
        )
        assert rule.name == "test-rule"
        assert rule.limit == 100
        assert rule.window_seconds == 60
        assert rule.enabled is True

    def test_validation(self):
        with pytest.raises(ValueError, match="Rate limit must be positive"):
            RateLimitRule(
                name="invalid",
                scope=RateLimitScope.GLOBAL,
                strategy=RateLimitStrategy.FIXED_WINDOW,
                limit=0,
                window_seconds=60,
            )

        with pytest.raises(ValueError, match="Window size must be positive"):
            RateLimitRule(
                name="invalid",
                scope=RateLimitScope.GLOBAL,
                strategy=RateLimitStrategy.FIXED_WINDOW,
                limit=100,
                window_seconds=0,
            )

        with pytest.raises(ValueError, match="Burst size cannot be negative"):
            RateLimitRule(
                name="invalid",
                scope=RateLimitScope.GLOBAL,
                strategy=RateLimitStrategy.FIXED_WINDOW,
                limit=100,
                window_seconds=60,
                burst_size=-1,
            )


class TestRateLimitWindow:
    def test_is_expired(self):
        now = datetime.utcnow()
        window = RateLimitWindow(key="test", current_count=0, reset_time=now - timedelta(seconds=1))
        assert window.is_expired is True

        window = RateLimitWindow(
            key="test", current_count=0, reset_time=now + timedelta(seconds=60)
        )
        assert window.is_expired is False

    def test_reset(self):
        window = RateLimitWindow(
            key="test", current_count=10, reset_time=datetime.utcnow(), burst_count=5
        )

        window.reset(window_seconds=60)

        assert window.current_count == 0
        assert window.burst_count == 0
        assert window.reset_time > datetime.utcnow()


class TestRateLimitResult:
    def test_remaining(self):
        result = RateLimitResult(
            allowed=True,
            rule_name="test",
            current_count=10,
            limit=100,
            reset_time=datetime.utcnow(),
        )
        assert result.remaining == 90

        result = RateLimitResult(
            allowed=False,
            rule_name="test",
            current_count=110,
            limit=100,
            reset_time=datetime.utcnow(),
        )
        assert result.remaining == 0


class TestRateLimitQuota:
    def test_get_cache_key(self):
        quota = RateLimitQuota(
            user_id="user1",
            ip_address="1.2.3.4",
            endpoint="/api",
            service="svc1",
            custom_key="custom",
        )

        # Global
        rule = RateLimitRule("r1", RateLimitScope.GLOBAL, RateLimitStrategy.FIXED_WINDOW, 10, 60)
        assert quota.get_cache_key(rule) == "rate_limit:r1:global"

        # User
        rule.scope = RateLimitScope.PER_USER
        assert quota.get_cache_key(rule) == "rate_limit:r1:user:user1"

        # IP
        rule.scope = RateLimitScope.PER_IP
        assert quota.get_cache_key(rule) == "rate_limit:r1:ip:1.2.3.4"

        # Endpoint
        rule.scope = RateLimitScope.PER_ENDPOINT
        assert quota.get_cache_key(rule) == "rate_limit:r1:endpoint:/api"

        # Service
        rule.scope = RateLimitScope.PER_SERVICE
        assert quota.get_cache_key(rule) == "rate_limit:r1:service:svc1"

        # Custom (fallback if scope doesn't match specific logic but custom_key exists?
        # Actually the logic checks scope first. Let's check the logic in source.)
        # The source code checks scope first. If scope is not one of the specific ones, it falls through.
        # But RateLimitScope is an Enum, so we can't easily pass an unknown scope unless we mock or extend enum.
        # However, if we have a scope that isn't handled in the if/elif chain but is in Enum?
        # The code handles GLOBAL, PER_USER, PER_IP, PER_ENDPOINT, PER_SERVICE.
        # If we had another scope, it would fall to custom_key.
        # But RateLimitScope only has those values.

        # Let's test missing values for scopes
        rule.scope = RateLimitScope.PER_USER
        quota_no_user = RateLimitQuota(ip_address="1.2.3.4")
        # If user_id is missing, it falls through to custom_key check
        assert quota_no_user.get_cache_key(rule) == "rate_limit:r1:unknown"  # custom_key is None

        quota_custom = RateLimitQuota(custom_key="my-key")
        assert quota_custom.get_cache_key(rule) == "rate_limit:r1:my-key"


class TestRateLimitMetrics:
    def test_metrics(self):
        metrics = RateLimitMetrics()

        assert metrics.block_rate == 0.0

        metrics.record_request(allowed=True)
        assert metrics.total_requests == 1
        assert metrics.allowed_requests == 1
        assert metrics.block_rate == 0.0
        assert metrics.allow_rate == 100.0

        metrics.record_request(allowed=False, rule_name="rule1")
        assert metrics.total_requests == 2
        assert metrics.blocked_requests == 1
        assert metrics.block_rate == 50.0
        assert metrics.allow_rate == 50.0
        assert metrics.rules_triggered["rule1"] == 1
