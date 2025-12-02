from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mmf.framework.gateway.application import GatewayService
from mmf.framework.gateway.domain.exceptions import RouteNotFoundError, UpstreamError
from mmf.framework.gateway.domain.models import (
    GatewayRequest,
    GatewayResponse,
    HTTPMethod,
    RouteConfig,
)
from mmf.framework.gateway.domain.services import LoadBalancer, RouteMatcher
from mmf.framework.gateway.ports.output import ServiceRegistryPort, UpstreamClientPort


@pytest.fixture
def mock_matcher():
    matcher = MagicMock(spec=RouteMatcher)
    matcher.matches.return_value = True
    return matcher


@pytest.fixture
def mock_load_balancer():
    lb = MagicMock(spec=LoadBalancer)
    lb.select_server.return_value = "http://upstream:8080"
    return lb


@pytest.fixture
def mock_upstream_client():
    client = AsyncMock(spec=UpstreamClientPort)
    client.send_request.return_value = GatewayResponse(status_code=200, body=b"OK", headers={})
    return client


@pytest.fixture
def mock_registry():
    registry = AsyncMock(spec=ServiceRegistryPort)
    registry.get_service_instances.return_value = ["http://upstream:8080"]
    return registry


@pytest.fixture
def route_config():
    return RouteConfig(
        name="test-route",
        path="/test",
        methods=[HTTPMethod.GET],
        upstream="test-service",
        auth_required=False,
    )


@pytest.fixture
def mock_security_handler():
    return AsyncMock()


@pytest.fixture
def mock_rate_limiter():
    return AsyncMock()


@pytest.fixture
def gateway_service(
    route_config,
    mock_matcher,
    mock_load_balancer,
    mock_upstream_client,
    mock_registry,
    mock_security_handler,
    mock_rate_limiter,
):
    with (
        patch(
            "mmf.framework.gateway.application.GatewaySecurityHandler",
            return_value=mock_security_handler,
        ),
        patch(
            "mmf.framework.gateway.application.GatewayRateLimiter",
            return_value=mock_rate_limiter,
        ),
    ):
        service = GatewayService(
            routes=[route_config],
            matcher=mock_matcher,
            load_balancer=mock_load_balancer,
            upstream_client=mock_upstream_client,
            service_registry=mock_registry,
        )
        return service


@pytest.mark.asyncio
async def test_handle_request_flow(
    gateway_service,
    mock_upstream_client,
    mock_security_handler,
    mock_rate_limiter,
    route_config,
):
    request = GatewayRequest(
        method=HTTPMethod.GET, path="/test", headers={}, body=b"", query_params={}
    )

    response = await gateway_service.handle_request(request)

    assert response.status_code == 200
    assert response.body == b"OK"

    # Verify flow
    mock_security_handler.validate_security.assert_called_once_with(route_config, request)
    mock_rate_limiter.check_rate_limit.assert_called_once_with(route_config, request)
    mock_upstream_client.send_request.assert_called_once()


@pytest.mark.asyncio
async def test_handle_request_route_not_found(gateway_service, mock_matcher):
    mock_matcher.matches.return_value = False

    request = GatewayRequest(
        method=HTTPMethod.GET, path="/unknown", headers={}, body=b"", query_params={}
    )

    with pytest.raises(RouteNotFoundError):
        await gateway_service.handle_request(request)


@pytest.mark.asyncio
async def test_handle_request_upstream_error(gateway_service, mock_upstream_client):
    mock_upstream_client.send_request.side_effect = Exception("Connection failed")

    request = GatewayRequest(
        method=HTTPMethod.GET, path="/test", headers={}, body=b"", query_params={}
    )

    with pytest.raises(UpstreamError):
        await gateway_service.handle_request(request)
