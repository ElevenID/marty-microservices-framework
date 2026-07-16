"""
Tests for Security Middleware Components
"""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.security.domain.config import JWTConfig, RateLimitConfig, SessionConfig
from mmf.core.security.domain.models.rate_limit import RateLimitResult
from mmf.core.security.domain.models.session import SessionData, SessionState
from mmf.core.security.domain.services.middleware.authentication import (
    AuthenticationMiddleware,
)
from mmf.core.security.domain.services.middleware.rate_limit import RateLimitMiddleware
from mmf.core.security.domain.services.middleware.session import SessionMiddleware


@pytest.mark.asyncio
class TestRateLimitMiddleware:
    async def test_rate_limit_allowed(self):
        rate_limiter = AsyncMock()
        rate_limiter.check_rate_limit.return_value = RateLimitResult(
            allowed=True,
            rule_name="default",
            current_count=1,
            limit=100,
            reset_time=datetime.utcnow(),
        )
        config = RateLimitConfig(enabled=True, default_rate="100/m")
        middleware = RateLimitMiddleware(rate_limiter, config)

        context = {"path": "/test"}
        next_called = False

        async def next_middleware(ctx):
            nonlocal next_called
            next_called = True
            return ctx

        result = await middleware.process(context, next_middleware)

        assert next_called
        assert "error" not in result

    async def test_rate_limit_exceeded(self):
        rate_limiter = AsyncMock()
        rate_limiter.check_rate_limit.return_value = RateLimitResult(
            allowed=False,
            rule_name="default",
            current_count=101,
            limit=100,
            reset_time=datetime.utcnow(),
        )
        config = RateLimitConfig(enabled=True, default_rate="100/m")
        middleware = RateLimitMiddleware(rate_limiter, config)

        context = {"path": "/test"}
        next_called = False

        async def next_middleware(ctx):
            nonlocal next_called
            next_called = True
            return ctx

        result = await middleware.process(context, next_middleware)

        assert not next_called
        assert result["status_code"] == 429
        assert result["error"] == "Rate limit exceeded"


@pytest.mark.asyncio
class TestSessionMiddleware:
    async def test_session_found(self):
        session_manager = AsyncMock()
        session = SessionData(
            session_id="123",
            user_id="user1",
            state=SessionState.ACTIVE,
            created_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            expires_at=datetime.utcnow(),
        )
        session_manager.get_session.return_value = session

        config = SessionConfig(enabled=True, session_cookie_name="session_id")
        middleware = SessionMiddleware(session_manager, config)

        context = {"cookies": {"session_id": "123"}}

        async def next_middleware(ctx):
            return ctx

        result = await middleware.process(context, next_middleware)

        assert result["user"] == "user1"
        assert result["session"] == session
        session_manager.update_session.assert_called_once()

    async def test_no_session(self):
        session_manager = AsyncMock()
        session_manager.get_session.return_value = None

        config = SessionConfig(enabled=True, session_cookie_name="session_id")
        middleware = SessionMiddleware(session_manager, config)

        context = {"cookies": {}}

        async def next_middleware(ctx):
            return ctx

        result = await middleware.process(context, next_middleware)

        assert "user" not in result
        assert "session" not in result


@pytest.mark.asyncio
class TestAuthenticationMiddleware:
    async def test_auth_execution(self):
        middleware = AuthenticationMiddleware()

        context = {}

        async def next_middleware(ctx):
            return ctx

        # Currently just a placeholder, so it shouldn't add user unless we mock _authenticate_request
        # But let's just check it runs next_middleware
        result = await middleware.process(context, next_middleware)

        assert result is context

    async def test_jwt_auth_success(self):
        import jwt

        secret = "secret"  # pragma: allowlist secret
        jwt_config = JWTConfig(secret_key=secret, algorithm="HS256")
        middleware = AuthenticationMiddleware(jwt_config)

        token = jwt.encode({"sub": "user1"}, secret, algorithm="HS256")
        context = {"headers": {"authorization": f"Bearer {token}"}}

        async def next_middleware(ctx):
            return ctx

        result = await middleware.process(context, next_middleware)

        assert "user" in result
        assert result["user"]["sub"] == "user1"
