from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf.core.gateway import (
    AuthenticationType,
    GatewayRequest,
    HTTPMethod,
    IRateLimitStorage,
    RateLimitConfig,
    RateLimitExceededError,
    RouteConfig,
)
from mmf.framework.gateway.domain.rate_limit import GatewayRateLimiter


@pytest.fixture
def mock_storage():
    return AsyncMock(spec=IRateLimitStorage)


@pytest.fixture
def rate_limiter(mock_storage):
    return GatewayRateLimiter(storage=mock_storage)


@pytest.fixture
def route_config():
    return RouteConfig(
        name="test-route",
        path="/test",
        methods=[HTTPMethod.GET],
        upstream="test-service",
        authentication_type=AuthenticationType.NONE,
        auth_required=False,
    )


@pytest.mark.asyncio
async def test_check_rate_limit_no_limit_configured(rate_limiter, route_config):
    request = GatewayRequest(
        method=HTTPMethod.GET, path="/test", headers={}, body=b"", query_params={}
    )
    # Should not raise
    await rate_limiter.check_rate_limit(route_config, request)


@pytest.mark.asyncio
async def test_check_rate_limit_success(rate_limiter, route_config, mock_storage):
    # Configure rate limit
    route_config.rate_limit = RateLimitConfig(requests_per_window=10, window_size_seconds=60)

    mock_storage.increment_usage.return_value = 5

    request = GatewayRequest(
        method=HTTPMethod.GET,
        path="/test",
        headers={},
        body=b"",
        query_params={},
        client_ip="127.0.0.1",
    )

    await rate_limiter.check_rate_limit(route_config, request)

    mock_storage.increment_usage.assert_called_once_with("rl:test-route:127.0.0.1")


@pytest.mark.asyncio
async def test_check_rate_limit_exceeded(rate_limiter, route_config, mock_storage):
    # Configure rate limit
    route_config.rate_limit = RateLimitConfig(requests_per_window=10, window_size_seconds=60)

    mock_storage.increment_usage.return_value = 11

    request = GatewayRequest(
        method=HTTPMethod.GET,
        path="/test",
        headers={},
        body=b"",
        query_params={},
        client_ip="127.0.0.1",
    )

    with pytest.raises(RateLimitExceededError):
        await rate_limiter.check_rate_limit(route_config, request)
