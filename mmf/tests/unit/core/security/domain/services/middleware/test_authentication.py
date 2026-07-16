from unittest.mock import Mock, patch

import jwt
import pytest

from mmf.core.security.domain.config import JWTConfig
from mmf.core.security.domain.services.middleware.authentication import (
    AuthenticationMiddleware,
)


@pytest.fixture
def jwt_config():
    return JWTConfig(
        secret_key="secret",  # pragma: allowlist secret
        algorithm="HS256",
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
        issuer="test-issuer",
        audience="test-audience",
    )


@pytest.fixture
def middleware(jwt_config):
    return AuthenticationMiddleware(jwt_config=jwt_config)


@pytest.mark.asyncio
class TestAuthenticationMiddleware:
    async def test_process_existing_user(self, middleware):
        context = {"user": {"id": "123"}}
        result = await middleware.process(context)
        assert result == context

    async def test_process_no_config(self):
        middleware = AuthenticationMiddleware(jwt_config=None)
        context = {"headers": {"Authorization": "Bearer token"}}
        result = await middleware.process(context)
        assert "user" not in result

    async def test_process_no_header(self, middleware):
        context = {"headers": {}}
        result = await middleware.process(context)
        assert "user" not in result

    async def test_process_invalid_scheme(self, middleware):
        context = {"headers": {"Authorization": "Basic token"}}
        result = await middleware.process(context)
        assert "user" not in result

    async def test_process_valid_token(self, middleware, jwt_config):
        token = jwt.encode(
            {"sub": "user-123", "iss": jwt_config.issuer, "aud": jwt_config.audience},
            jwt_config.secret_key,
            algorithm=jwt_config.algorithm,
        )
        context = {"headers": {"Authorization": f"Bearer {token}"}}

        result = await middleware.process(context)

        assert "user" in result
        assert result["user"]["sub"] == "user-123"

    async def test_process_invalid_token(self, middleware):
        context = {"headers": {"Authorization": "Bearer invalid-token"}}
        result = await middleware.process(context)
        assert "user" not in result

    async def test_process_next_middleware(self, middleware):
        context = {"user": {"id": "123"}}
        next_called = False

        async def next_mw(ctx):
            nonlocal next_called
            next_called = True
            return ctx

        await middleware.process(context, next_middleware=next_mw)
        assert next_called
