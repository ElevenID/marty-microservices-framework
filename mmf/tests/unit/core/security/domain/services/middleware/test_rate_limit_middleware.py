from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.security.domain.config import RateLimitConfig
from mmf.core.security.domain.models.rate_limit import (
    RateLimitQuota,
    RateLimitResult,
    RateLimitRule,
    RateLimitScope,
    RateLimitStrategy,
)
from mmf.core.security.domain.services.middleware.rate_limit import RateLimitMiddleware
from mmf.core.security.ports.rate_limiting import IRateLimiter


@pytest.fixture
def rate_limiter():
    return AsyncMock(spec=IRateLimiter)


@pytest.fixture
def config():
    return RateLimitConfig(enabled=True, default_rate="100/minute")


@pytest.fixture
def middleware(rate_limiter, config):
    return RateLimitMiddleware(rate_limiter=rate_limiter, config=config)


@pytest.mark.asyncio
class TestRateLimitMiddleware:
    async def test_process_disabled(self, middleware):
        middleware.config.enabled = False
        context = {}
        result = await middleware.process(context)
        assert "error" not in result

    async def test_process_allowed(self, middleware, rate_limiter):
        context = {"ip_address": "127.0.0.1"}
        rate_limiter.check_rate_limit.return_value = RateLimitResult(
            allowed=True,
            rule_name="default",
            current_count=1,
            limit=100,
            reset_time=datetime.utcnow(),
        )

        result = await middleware.process(context)

        assert "error" not in result
        rate_limiter.check_rate_limit.assert_called_once()

    async def test_process_blocked(self, middleware, rate_limiter):
        context = {"ip_address": "127.0.0.1"}
        rate_limiter.check_rate_limit.return_value = RateLimitResult(
            allowed=False,
            rule_name="default",
            current_count=101,
            limit=100,
            reset_time=datetime.utcnow(),
        )

        result = await middleware.process(context)

        assert result["error"] == "Rate limit exceeded"
        assert result["status_code"] == 429

    async def test_process_next_middleware(self, middleware, rate_limiter):
        context = {"ip_address": "127.0.0.1"}
        rate_limiter.check_rate_limit.return_value = RateLimitResult(
            allowed=True,
            rule_name="default",
            current_count=1,
            limit=100,
            reset_time=datetime.utcnow(),
        )

        next_called = False

        async def next_mw(ctx):
            nonlocal next_called
            next_called = True
            return ctx

        await middleware.process(context, next_middleware=next_mw)
        assert next_called

    async def test_check_rate_limits_logic(self, middleware, rate_limiter):
        # Test that quota is constructed correctly
        context = {"ip_address": "1.2.3.4", "user_id": "user-1", "path": "/api/test"}
        rate_limiter.check_rate_limit.return_value = RateLimitResult(
            allowed=True,
            rule_name="default",
            current_count=1,
            limit=100,
            reset_time=datetime.utcnow(),
        )

        await middleware.process(context)

        call_args = rate_limiter.check_rate_limit.call_args
        quota = call_args[0][0]

        assert quota.user_id == "user-1"
        assert quota.ip_address == "1.2.3.4"
        assert quota.endpoint == "/api/test"
        assert len(quota.rules) == 1
        assert quota.rules[0].limit == 100
