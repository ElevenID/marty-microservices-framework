from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mmf.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)
from mmf.services.identity.integration.http_endpoints import (
    get_authenticate_use_case,
    get_validate_token_use_case,
    router,
)


class TestHTTPEndpoints:
    @pytest.fixture
    def app(self):
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        return TestClient(app)

    @pytest.fixture
    def mock_authenticate_use_case(self):
        return Mock()

    @pytest.fixture
    def mock_validate_use_case(self):
        return Mock()

    @pytest.fixture
    def override_dependencies(self, app, mock_authenticate_use_case, mock_validate_use_case):
        app.dependency_overrides[get_authenticate_use_case] = lambda: mock_authenticate_use_case
        app.dependency_overrides[get_validate_token_use_case] = lambda: mock_validate_use_case
        yield
        app.dependency_overrides = {}

    def test_health_check(self, client):
        response = client.get("/auth/jwt/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "jwt-authentication"}

    @pytest.mark.asyncio
    async def test_authenticate_success(
        self, client, mock_authenticate_use_case, override_dependencies
    ):
        mock_user = AuthenticatedUser(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            roles=["user"],
            created_at=datetime.now(timezone.utc),
        )
        mock_result = AuthenticationResult(
            status=AuthenticationStatus.SUCCESS, authenticated_user=mock_user
        )
        mock_authenticate_use_case.execute = AsyncMock(return_value=mock_result)

        response = client.post("/auth/jwt/authenticate", json={"token": "valid-token"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["user"]["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(
        self, client, mock_authenticate_use_case, override_dependencies
    ):
        mock_result = AuthenticationResult(
            status=AuthenticationStatus.FAILED,
            error_code=AuthenticationErrorCode.TOKEN_INVALID,
            error_message="Invalid signature",
        )
        mock_authenticate_use_case.execute = AsyncMock(return_value=mock_result)

        response = client.post("/auth/jwt/authenticate", json={"token": "invalid-token"})

        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_authenticate_expired_token(
        self, client, mock_authenticate_use_case, override_dependencies
    ):
        mock_result = AuthenticationResult(
            status=AuthenticationStatus.FAILED,
            error_code=AuthenticationErrorCode.TOKEN_EXPIRED,
            error_message="Token expired",
        )
        mock_authenticate_use_case.execute = AsyncMock(return_value=mock_result)

        response = client.post("/auth/jwt/authenticate", json={"token": "expired-token"})

        assert response.status_code == 401
        assert "Token has expired" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_authenticate_internal_error(
        self, client, mock_authenticate_use_case, override_dependencies
    ):
        mock_authenticate_use_case.execute = AsyncMock(side_effect=Exception("Database error"))

        response = client.post("/auth/jwt/authenticate", json={"token": "valid-token"})

        assert response.status_code == 500
        assert "Internal authentication error" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_validate_token_success(
        self, client, mock_validate_use_case, override_dependencies
    ):
        mock_user = AuthenticatedUser(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            roles=["user"],
            created_at=datetime.now(timezone.utc),
        )
        mock_result = Mock()
        mock_result.is_valid = True
        mock_result.user = mock_user

        mock_validate_use_case.execute = AsyncMock(return_value=mock_result)

        response = client.post("/auth/jwt/validate", json={"token": "valid-token"})

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert data["user"]["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_validate_token_invalid(
        self, client, mock_validate_use_case, override_dependencies
    ):
        mock_result = Mock()
        mock_result.is_valid = False
        mock_result.error_message = "Invalid token"
        mock_result.user = None

        mock_validate_use_case.execute = AsyncMock(return_value=mock_result)

        response = client.post("/auth/jwt/validate", json={"token": "invalid-token"})

        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert data["error_message"] == "Invalid token"
        assert data["user"] is None

    @pytest.mark.asyncio
    async def test_validate_token_internal_error(
        self, client, mock_validate_use_case, override_dependencies
    ):
        mock_validate_use_case.execute = AsyncMock(side_effect=Exception("Unexpected error"))

        response = client.post("/auth/jwt/validate", json={"token": "valid-token"})

        assert response.status_code == 500
        assert "Token validation error" in response.json()["detail"]
