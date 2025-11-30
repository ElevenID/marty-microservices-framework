from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf_new.core.security.domain.models.result import AuthenticationResult
from mmf_new.core.security.domain.models.user import User
from mmf_new.core.security.ports.authentication import IAuthenticator
from mmf_new.framework.gateway.application import GatewayService
from mmf_new.framework.gateway.domain.exceptions import (
    AuthenticationError,
    RouteNotFoundError,
)
from mmf_new.framework.gateway.domain.models import (
    AuthenticationType,
    GatewayRequest,
    GatewayResponse,
    HTTPMethod,
    RouteConfig,
    UpstreamGroup,
)
from mmf_new.framework.gateway.domain.services import LoadBalancer, RouteMatcher
from mmf_new.framework.gateway.ports.output import (
    RateLimitStoragePort,
    ServiceRegistryPort,
    UpstreamClientPort,
)


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
def mock_authenticator():
    auth = AsyncMock(spec=IAuthenticator)
    return auth


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


@pytest.fixture
def gateway_service(
    route_config,
    mock_matcher,
    mock_load_balancer,
    mock_upstream_client,
    mock_registry,
    mock_authenticator,
):
    return GatewayService(
        routes=[route_config],
        matcher=mock_matcher,
        load_balancer=mock_load_balancer,
        upstream_client=mock_upstream_client,
        service_registry=mock_registry,
        authenticator=mock_authenticator,
    )


@pytest.mark.asyncio
async def test_handle_request_success(gateway_service, mock_upstream_client):
    request = GatewayRequest(
        method=HTTPMethod.GET, path="/test", headers={}, body=b"", query_params={}
    )

    response = await gateway_service.handle_request(request)

    assert response.status_code == 200
    assert response.body == b"OK"
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
async def test_handle_request_auth_bearer_success(
    gateway_service, route_config, mock_authenticator
):
    # Update route to require Bearer auth
    route_config.authentication_type = AuthenticationType.BEARER_TOKEN
    route_config.auth_required = True

    # Setup mock authenticator
    mock_user = User(user_id="user_123", username="testuser", roles={"user"}, permissions={"read"})
    mock_authenticator.validate_token.return_value = AuthenticationResult(
        success=True, user=mock_user
    )

    request = GatewayRequest(
        method=HTTPMethod.GET,
        path="/test",
        headers={"Authorization": "Bearer valid_token"},
        body=b"",
        query_params={},
    )

    response = await gateway_service.handle_request(request)

    assert response.status_code == 200
    assert request.context["user"]["user_id"] == "user_123"
    mock_authenticator.validate_token.assert_called_once_with("valid_token")


@pytest.mark.asyncio
async def test_handle_request_auth_bearer_failure(
    gateway_service, route_config, mock_authenticator
):
    # Update route to require Bearer auth
    route_config.authentication_type = AuthenticationType.BEARER_TOKEN
    route_config.auth_required = True

    # Setup mock authenticator failure
    mock_authenticator.validate_token.return_value = AuthenticationResult(
        success=False, error="Invalid token"
    )

    request = GatewayRequest(
        method=HTTPMethod.GET,
        path="/test",
        headers={"Authorization": "Bearer invalid_token"},
        body=b"",
        query_params={},
    )

    with pytest.raises(AuthenticationError) as exc:
        await gateway_service.handle_request(request)

    assert "Invalid token" in str(exc.value)


@pytest.mark.asyncio
async def test_handle_request_auth_api_key_success(
    gateway_service, route_config, mock_authenticator
):
    # Update route to require API Key auth
    route_config.authentication_type = AuthenticationType.API_KEY
    route_config.auth_required = True

    # Setup mock authenticator
    mock_user = User(
        user_id="user_456", username="apikeyuser", roles={"service"}, permissions={"write"}
    )
    mock_authenticator.authenticate.return_value = AuthenticationResult(
        success=True, user=mock_user
    )

    request = GatewayRequest(
        method=HTTPMethod.GET,
        path="/test",
        headers={"X-API-Key": "valid_api_key"},
        body=b"",
        query_params={},
    )

    response = await gateway_service.handle_request(request)

    assert response.status_code == 200
    assert request.context["user"]["user_id"] == "user_456"
    mock_authenticator.authenticate.assert_called_once_with(
        {"method": "api_key", "api_key": "valid_api_key"}  # pragma: allowlist secret
    )
