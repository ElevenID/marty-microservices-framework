"""
Unit tests for Gateway Security components.
"""

import pytest

from mmf_new.framework.gateway.domain.models import (
    AuthenticationType,
    GatewayRequest,
    HTTPMethod,
)
from mmf_new.framework.gateway.domain.security import (
    ApiKeyExtractor,
    AuthenticationError,
    BearerTokenExtractor,
    CredentialExtractorFactory,
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
