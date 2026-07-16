from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, Request, Response
from starlette.datastructures import Headers

from mmf.services.identity.domain.models import AuthenticatedUser
from mmf.services.identity.infrastructure.adapters import JWTConfig
from mmf.services.identity.integration.middleware import JWTAuthenticationMiddleware


class TestJWTAuthenticationMiddleware:
    @pytest.fixture
    def mock_app(self):
        return Mock()

    @pytest.fixture
    def jwt_config(self):
        return JWTConfig(secret_key="test-secret")  # pragma: allowlist secret

    @pytest.fixture
    def middleware(self, mock_app, jwt_config):
        return JWTAuthenticationMiddleware(
            app=mock_app,
            jwt_config=jwt_config,
            excluded_paths=["/public"],
            optional_paths=["/optional"],
            use_pattern_matching=False,
        )

    @pytest.fixture
    def middleware_pattern(self, mock_app, jwt_config):
        return JWTAuthenticationMiddleware(
            app=mock_app,
            jwt_config=jwt_config,
            excluded_paths=["/public"],
            optional_paths=["/optional"],
            use_pattern_matching=True,
        )

    def test_is_excluded_path_exact(self, middleware):
        assert middleware._is_excluded_path("/public") is True
        assert middleware._is_excluded_path("/public/nested") is False
        assert middleware._is_excluded_path("/private") is False

    def test_is_excluded_path_pattern(self, middleware_pattern):
        assert middleware_pattern._is_excluded_path("/public") is True
        assert middleware_pattern._is_excluded_path("/public/nested") is True
        assert middleware_pattern._is_excluded_path("/private") is False

    def test_is_optional_path_exact(self, middleware):
        assert middleware._is_optional_path("/optional") is True
        assert middleware._is_optional_path("/optional/nested") is False
        assert middleware._is_optional_path("/private") is False

    @pytest.mark.asyncio
    async def test_dispatch_excluded_path(self, middleware):
        request = Mock(spec=Request)
        request.url.path = "/public"
        request.state = SimpleNamespace()
        call_next = AsyncMock(return_value=Response("OK"))

        response = await middleware.dispatch(request, call_next)

        assert response.body == b"OK"
        call_next.assert_called_once_with(request)
        # Should not attempt validation
        assert not hasattr(request.state, "authenticated_user")

    @pytest.mark.asyncio
    async def test_dispatch_protected_path_no_token(self, middleware):
        request = Mock(spec=Request)
        request.url.path = "/private"
        request.headers = Headers({})
        request.state = SimpleNamespace()
        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await middleware.dispatch(request, call_next)

        assert exc.value.status_code == 401
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_protected_path_valid_token(self, middleware):
        request = Mock(spec=Request)
        request.url.path = "/private"
        request.headers = Headers({"Authorization": "Bearer valid-token"})
        request.state = SimpleNamespace()

        call_next = AsyncMock(return_value=Response("OK"))

        # Mock the use case result
        mock_user = AuthenticatedUser(
            user_id="user123", username="testuser", email="test@example.com", roles=["user"]
        )
        mock_result = Mock()
        mock_result.is_valid = True
        mock_result.user = mock_user

        middleware.validate_use_case.execute = AsyncMock(return_value=mock_result)

        response = await middleware.dispatch(request, call_next)

        assert response.body == b"OK"
        call_next.assert_called_once()
        assert request.state.authenticated_user == mock_user
        assert request.state.is_authenticated is True

    @pytest.mark.asyncio
    async def test_dispatch_optional_path_no_token(self, middleware):
        request = Mock(spec=Request)
        request.url.path = "/optional"
        request.headers = Headers({})
        request.state = SimpleNamespace()
        call_next = AsyncMock(return_value=Response("OK"))

        response = await middleware.dispatch(request, call_next)

        assert response.body == b"OK"
        call_next.assert_called_once()
        # Should have None user
        assert request.state.authenticated_user is None
        assert request.state.is_authenticated is False

    @pytest.mark.asyncio
    async def test_dispatch_optional_path_valid_token(self, middleware):
        request = Mock(spec=Request)
        request.url.path = "/optional"
        request.headers = Headers({"Authorization": "Bearer valid-token"})
        request.state = SimpleNamespace()

        call_next = AsyncMock(return_value=Response("OK"))

        mock_user = AuthenticatedUser(
            user_id="user123", username="testuser", email="test@example.com", roles=["user"]
        )
        mock_result = Mock()
        mock_result.is_valid = True
        mock_result.user = mock_user

        middleware.validate_use_case.execute = AsyncMock(return_value=mock_result)

        response = await middleware.dispatch(request, call_next)

        assert response.body == b"OK"
        call_next.assert_called_once()
        assert request.state.authenticated_user == mock_user
        assert request.state.is_authenticated is True
