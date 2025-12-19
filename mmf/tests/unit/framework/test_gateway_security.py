"""
Unit tests for Gateway Security components.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf.core.gateway import (
    AuthenticationError,
    AuthenticationType,
    GatewayRequest,
    HTTPMethod,
    RouteConfig,
)
from mmf.core.security.domain.models.result import AuthenticationResult
from mmf.core.security.domain.models.user import User
from mmf.core.security.ports.authentication import IAuthenticator
from mmf.framework.gateway.domain.security import (
    ApiKeyExtractor,
    BearerTokenExtractor,
    CredentialExtractorFactory,
    GatewaySecurityHandler,
)


class TestApiKeyExtractor:
    def test_extract_from_header_x_api_key(self):
        request = GatewayRequest(
            path="/test",
            method=HTTPMethod.GET,
            headers={"X-API-Key": "my-secret-key"},
            client_ip="127.0.0.1",
        )
        extractor = ApiKeyExtractor()
        credentials = extractor.extract(request)
        assert credentials == {
            "method": "api_key",
            "api_key": "my-secret-key",  # pragma: allowlist secret
        }

    def test_extract_from_header_authorization(self):
        request = GatewayRequest(
            path="/test",
            method=HTTPMethod.GET,
            headers={"Authorization": "ApiKey my-secret-key"},
            client_ip="127.0.0.1",
        )
        extractor = ApiKeyExtractor()
        credentials = extractor.extract(request)
        assert credentials == {
            "method": "api_key",
            "api_key": "my-secret-key",  # pragma: allowlist secret
        }

    def test_extract_missing_key(self):
        request = GatewayRequest(
            path="/test",
            method=HTTPMethod.GET,
            headers={},
            client_ip="127.0.0.1",
        )
        extractor = ApiKeyExtractor()
        with pytest.raises(AuthenticationError, match="API key required"):
            extractor.extract(request)


class TestBearerTokenExtractor:
    def test_extract_success(self):
        request = GatewayRequest(
            path="/test",
            method=HTTPMethod.GET,
            headers={"Authorization": "Bearer my-token"},
            client_ip="127.0.0.1",
        )
        extractor = BearerTokenExtractor()
        credentials = extractor.extract(request)
        assert credentials == {"method": "bearer", "token": "my-token"}

    def test_extract_missing_header(self):
        request = GatewayRequest(
            path="/test",
            method=HTTPMethod.GET,
            headers={},
            client_ip="127.0.0.1",
        )
        extractor = BearerTokenExtractor()
        with pytest.raises(AuthenticationError, match="Bearer token required"):
            extractor.extract(request)

    def test_extract_invalid_scheme(self):
        request = GatewayRequest(
            path="/test",
            method=HTTPMethod.GET,
            headers={"Authorization": "Basic user:pass"},
            client_ip="127.0.0.1",
        )
        extractor = BearerTokenExtractor()
        with pytest.raises(AuthenticationError, match="Bearer token required"):
            extractor.extract(request)


class TestCredentialExtractorFactory:
    def test_get_extractor_api_key(self):
        extractor = CredentialExtractorFactory.get_extractor(AuthenticationType.API_KEY)
        assert isinstance(extractor, ApiKeyExtractor)

    def test_get_extractor_bearer_token(self):
        extractor = CredentialExtractorFactory.get_extractor(AuthenticationType.BEARER_TOKEN)
        assert isinstance(extractor, BearerTokenExtractor)

    def test_get_extractor_none(self):
        extractor = CredentialExtractorFactory.get_extractor(AuthenticationType.NONE)
        assert extractor is None


class TestGatewaySecurityHandler:
    @pytest.fixture
    def mock_authenticator(self):
        return AsyncMock(spec=IAuthenticator)

    @pytest.fixture
    def security_handler(self, mock_authenticator):
        return GatewaySecurityHandler(authenticator=mock_authenticator)

    @pytest.fixture
    def route_config(self):
        return RouteConfig(
            name="test-route",
            path="/test",
            methods=[HTTPMethod.GET],
            upstream="test-service",
            authentication_type=AuthenticationType.NONE,
            auth_required=False,
        )

    @pytest.mark.asyncio
    async def test_validate_security_no_auth_required(self, security_handler, route_config):
        request = GatewayRequest(
            method=HTTPMethod.GET, path="/test", headers={}, body=b"", query_params={}
        )
        # Should not raise
        await security_handler.validate_security(route_config, request)

    @pytest.mark.asyncio
    async def test_validate_security_bearer_success(
        self, security_handler, route_config, mock_authenticator
    ):
        route_config.authentication_type = AuthenticationType.BEARER_TOKEN
        route_config.auth_required = True

        mock_user = User(
            user_id="user_123", username="testuser", roles={"user"}, permissions={"read"}
        )
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

        await security_handler.validate_security(route_config, request)

        assert request.context["user"]["user_id"] == "user_123"
        mock_authenticator.validate_token.assert_called_once_with("valid_token")

    @pytest.mark.asyncio
    async def test_validate_security_bearer_failure(
        self, security_handler, route_config, mock_authenticator
    ):
        route_config.authentication_type = AuthenticationType.BEARER_TOKEN
        route_config.auth_required = True

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

        with pytest.raises(AuthenticationError, match="Invalid token"):
            await security_handler.validate_security(route_config, request)

    @pytest.mark.asyncio
    async def test_validate_security_api_key_success(
        self, security_handler, route_config, mock_authenticator
    ):
        route_config.authentication_type = AuthenticationType.API_KEY
        route_config.auth_required = True

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

        await security_handler.validate_security(route_config, request)

        assert request.context["user"]["user_id"] == "user_456"
        mock_authenticator.authenticate.assert_called_once_with(
            {"method": "api_key", "api_key": "valid_api_key"}  # pragma: allowlist secret
        )

    @pytest.mark.asyncio
    async def test_validate_security_missing_auth_when_required(
        self, security_handler, route_config
    ):
        route_config.authentication_type = AuthenticationType.BEARER_TOKEN
        route_config.auth_required = True

        request = GatewayRequest(
            method=HTTPMethod.GET, path="/test", headers={}, body=b"", query_params={}
        )

        with pytest.raises(AuthenticationError):
            await security_handler.validate_security(route_config, request)
