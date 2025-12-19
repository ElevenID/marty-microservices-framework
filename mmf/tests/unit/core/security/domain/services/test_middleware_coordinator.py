from unittest.mock import AsyncMock, Mock, patch

import pytest

from mmf.core.security.domain.config import JWTConfig, RateLimitConfig, SessionConfig
from mmf.core.security.domain.services.middleware_coordinator import (
    SecurityMiddlewareCoordinator,
)
from mmf.core.security.ports.rate_limiting import IRateLimiter
from mmf.core.security.ports.session import ISessionManager


@pytest.fixture
def mock_session_manager():
    return Mock(spec=ISessionManager)


@pytest.fixture
def mock_rate_limiter():
    return Mock(spec=IRateLimiter)


@pytest.fixture
def session_config():
    return SessionConfig(
        enabled=True,
        default_timeout_minutes=30,
        session_cookie_name="session_id",
        secure_cookies=True,
        same_site="Lax",
    )


@pytest.fixture
def rate_limit_config():
    return RateLimitConfig(enabled=True, default_rate="100/minute", use_memory_backend=True)


@pytest.fixture
def jwt_config():
    return JWTConfig(
        secret_key="jwt_secret",  # pragma: allowlist secret
        algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )


@pytest.fixture
def coordinator(
    mock_session_manager, mock_rate_limiter, session_config, rate_limit_config, jwt_config
):
    return SecurityMiddlewareCoordinator(
        session_manager=mock_session_manager,
        rate_limiter=mock_rate_limiter,
        session_config=session_config,
        rate_limit_config=rate_limit_config,
        jwt_config=jwt_config,
    )


class TestSecurityMiddlewareCoordinator:
    def test_init(self, coordinator):
        assert coordinator.rate_limit_middleware is not None
        assert coordinator.session_middleware is not None
        assert coordinator.auth_middleware is not None

    @pytest.mark.asyncio
    async def test_process_request_success(self, coordinator):
        # Mock the middleware process methods to verify chain execution

        async def rate_side_effect(ctx, next_call):
            return await next_call(ctx)

        async def session_side_effect(ctx, next_call):
            return await next_call(ctx)

        mock_rate_middleware = AsyncMock()
        mock_rate_middleware.process.side_effect = rate_side_effect

        mock_session_middleware = AsyncMock()
        mock_session_middleware.process.side_effect = session_side_effect

        mock_auth_middleware = AsyncMock()
        mock_auth_middleware.process.return_value = {"status": "authenticated"}

        coordinator.rate_limit_middleware = mock_rate_middleware
        coordinator.session_middleware = mock_session_middleware
        coordinator.auth_middleware = mock_auth_middleware

        ctx = {"path": "/api/test"}
        result = await coordinator.process_request(ctx)

        assert result == {"status": "authenticated"}
        mock_rate_middleware.process.assert_called_once()
        mock_session_middleware.process.assert_called_once()
        mock_auth_middleware.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_request_rate_limit_blocked(self, coordinator):
        mock_rate_middleware = AsyncMock()
        mock_rate_middleware.process.return_value = {"error": "Too Many Requests"}

        coordinator.rate_limit_middleware = mock_rate_middleware
        # Session and Auth should not be called
        coordinator.session_middleware = AsyncMock()
        coordinator.auth_middleware = AsyncMock()

        ctx = {"path": "/api/test"}
        result = await coordinator.process_request(ctx)

        assert result == {"error": "Too Many Requests"}
        mock_rate_middleware.process.assert_called_once()
        coordinator.session_middleware.process.assert_not_called()
        coordinator.auth_middleware.process.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_request(self, coordinator):
        mock_auth_middleware = AsyncMock()
        mock_auth_middleware._authenticate_request.return_value = {"user": "test"}
        coordinator.auth_middleware = mock_auth_middleware

        ctx = {"headers": {"Authorization": "Bearer token"}}
        result = await coordinator.authenticate_request(ctx)

        assert result == {"user": "test"}
        mock_auth_middleware._authenticate_request.assert_called_once_with(ctx)

    @pytest.mark.asyncio
    async def test_authorize_request(self, coordinator):
        # Currently a placeholder, just returns context
        ctx = {"user": "test", "role": "admin"}
        result = await coordinator.authorize_request(ctx)
        assert result == ctx

    @pytest.mark.asyncio
    async def test_apply_security_headers(self, coordinator):
        ctx = {}
        result = await coordinator.apply_security_headers(ctx)

        headers = result["headers"]
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-XSS-Protection"] == "1; mode=block"
        assert headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"

    @pytest.mark.asyncio
    async def test_apply_security_headers_existing_headers(self, coordinator):
        ctx = {"headers": {"Content-Type": "application/json"}}
        result = await coordinator.apply_security_headers(ctx)

        headers = result["headers"]
        assert headers["Content-Type"] == "application/json"
        assert headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_check_rate_limits(self, coordinator, mock_rate_limiter):
        from datetime import datetime

        from mmf.core.security.domain.models.rate_limit import RateLimitResult

        expected_result = RateLimitResult(
            allowed=True,
            rule_name="default",
            current_count=1,
            limit=100,
            reset_time=datetime.utcnow(),
        )
        mock_rate_limiter.check_rate_limit.return_value = expected_result

        ctx = {"ip_address": "127.0.0.1", "path": "/api/test"}
        result = await coordinator.check_rate_limits(ctx)

        assert result == expected_result
        mock_rate_limiter.check_rate_limit.assert_called_once()

    @pytest.mark.asyncio
    async def test_manage_session_found(self, coordinator, mock_session_manager):
        from datetime import datetime

        from mmf.core.security.domain.models.session import SessionData

        expected_session = SessionData(
            session_id="test_session",
            user_id="user123",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow(),
            last_accessed=datetime.utcnow(),
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )
        mock_session_manager.get_session.return_value = expected_session

        ctx = {"cookies": {"session_id": "test_session"}}
        result = await coordinator.manage_session(ctx)

        assert result == expected_session
        mock_session_manager.get_session.assert_called_once_with("test_session")

    @pytest.mark.asyncio
    async def test_manage_session_not_found(self, coordinator, mock_session_manager):
        mock_session_manager.get_session.return_value = None

        ctx = {"cookies": {"session_id": "invalid_session"}}
        result = await coordinator.manage_session(ctx)

        assert result is None
        mock_session_manager.get_session.assert_called_once_with("invalid_session")

    @pytest.mark.asyncio
    async def test_manage_session_no_cookie(self, coordinator, mock_session_manager):
        ctx = {"cookies": {}}
        result = await coordinator.manage_session(ctx)

        assert result is None
        mock_session_manager.get_session.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_security_event(self, coordinator):
        with patch(
            "mmf.core.security.domain.services.middleware_coordinator.logger"
        ) as mock_logger:
            result = await coordinator.log_security_event("TEST_EVENT", {}, {"detail": "info"})
            assert result is True
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check(self, coordinator):
        result = await coordinator.health_check()
        assert result["status"] == "healthy"
        assert result["components"]["rate_limiter"] == "ok"
        assert result["components"]["session_manager"] == "ok"
