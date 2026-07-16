from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mmf.services.identity.infrastructure.adapters.inbound.web.router import (
    router,
    get_jwt_config,
    get_basic_auth_config,
    get_token_provider,
    get_basic_auth_provider,
    get_auth_use_case,
    get_basic_auth_use_case,
    get_validate_use_case,
)

from mmf.services.identity.application.use_cases import (
    AuthenticateWithBasicUseCase,
    AuthenticateWithJWTUseCase,
    ValidateTokenUseCase,
)
from mmf.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)
from mmf.services.identity.infrastructure.adapters import (
    BasicAuthAdapter,
    BasicAuthConfig,
    JWTConfig,
    JWTTokenProvider,
)

# Create a FastAPI app for testing
app = FastAPI()
app.include_router(router)


@pytest.fixture
def mock_jwt_config():
    return MagicMock(spec=JWTConfig)


@pytest.fixture
def mock_basic_auth_config():
    return MagicMock(spec=BasicAuthConfig)


@pytest.fixture
def mock_token_provider():
    provider = MagicMock(spec=JWTTokenProvider)
    provider.create_token = AsyncMock()
    provider.validate_token = AsyncMock()
    provider.refresh_token = AsyncMock()
    return provider


@pytest.fixture
def mock_basic_auth_provider():
    return MagicMock(spec=BasicAuthAdapter)


@pytest.fixture
def mock_auth_jwt_use_case():
    use_case = MagicMock(spec=AuthenticateWithJWTUseCase)
    use_case.execute = AsyncMock()
    return use_case


@pytest.fixture
def mock_auth_basic_use_case():
    use_case = MagicMock(spec=AuthenticateWithBasicUseCase)
    use_case.execute = AsyncMock()
    return use_case


@pytest.fixture
def mock_validate_use_case():
    use_case = MagicMock(spec=ValidateTokenUseCase)
    use_case.execute = AsyncMock()
    return use_case


@pytest.fixture
def client(
    mock_jwt_config,
    mock_basic_auth_config,
    mock_token_provider,
    mock_basic_auth_provider,
    mock_auth_jwt_use_case,
    mock_auth_basic_use_case,
    mock_validate_use_case,
):
    # Override dependencies
    app.dependency_overrides[get_jwt_config] = lambda: mock_jwt_config
    app.dependency_overrides[get_basic_auth_config] = lambda: mock_basic_auth_config
    app.dependency_overrides[get_token_provider] = lambda: mock_token_provider
    app.dependency_overrides[get_basic_auth_provider] = lambda: mock_basic_auth_provider
    app.dependency_overrides[get_auth_use_case] = lambda: mock_auth_jwt_use_case
    app.dependency_overrides[get_basic_auth_use_case] = lambda: mock_auth_basic_use_case
    app.dependency_overrides[get_validate_use_case] = lambda: mock_validate_use_case

    with TestClient(app) as client:
        yield client

    # Clear overrides
    app.dependency_overrides = {}


@pytest.fixture
def sample_user():
    return AuthenticatedUser(
        user_id="user123",
        username="testuser",
        email="test@example.com",
        roles={"user"},
        permissions={"read"},
        auth_method="password",
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(hours=1),
    )


class TestAuthRouter:
    def test_login_success(
        self, client, mock_auth_basic_use_case, mock_token_provider, sample_user
    ):
        # Setup
        mock_auth_basic_use_case.execute.return_value = AuthenticationResult(
            status=AuthenticationStatus.SUCCESS, authenticated_user=sample_user
        )
        mock_token_provider.create_token.return_value = "valid.jwt.token"

        # Execute
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "password123"},  # pragma: allowlist secret
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "valid.jwt.token"
        assert data["user_id"] == "user123"
        assert data["username"] == "testuser"

        mock_auth_basic_use_case.execute.assert_called_once()
        mock_token_provider.create_token.assert_called_once_with(sample_user)

    def test_login_failure(self, client, mock_auth_basic_use_case):
        # Setup
        mock_auth_basic_use_case.execute.return_value = AuthenticationResult(
            status=AuthenticationStatus.FAILED,
            error_code=AuthenticationErrorCode.INVALID_PASSWORD,
            error_message="Invalid username or password",
        )

        # Execute
        response = client.post(
            "/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},  # pragma: allowlist secret
        )

        # Verify
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid username or password"

    def test_validate_token_success(self, client, mock_validate_use_case, sample_user):
        # Setup
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_result.user = sample_user
        mock_validate_use_case.execute.return_value = mock_result

        # Execute
        response = client.post("/auth/validate", headers={"Authorization": "Bearer valid.token"})

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["user_id"] == "user123"
        assert data["username"] == "testuser"

    def test_validate_token_invalid(self, client, mock_validate_use_case):
        # Setup
        mock_result = MagicMock()
        mock_result.is_valid = False
        mock_result.user = None
        mock_validate_use_case.execute.return_value = mock_result

        # Execute
        response = client.post("/auth/validate", headers={"Authorization": "Bearer invalid.token"})

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["user_id"] is None

    def test_get_current_user_success(self, client, mock_auth_jwt_use_case, sample_user):
        # Setup
        mock_auth_jwt_use_case.execute.return_value = AuthenticationResult(
            status=AuthenticationStatus.SUCCESS, authenticated_user=sample_user
        )

        # Execute
        response = client.get("/auth/me", headers={"Authorization": "Bearer valid.token"})

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user123"
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_get_current_user_unauthorized(self, client, mock_auth_jwt_use_case):
        # Setup
        mock_auth_jwt_use_case.execute.return_value = AuthenticationResult(
            status=AuthenticationStatus.FAILED,
            error_message="Token expired",
            error_code=AuthenticationErrorCode.TOKEN_EXPIRED,
        )

        # Execute
        response = client.get("/auth/me", headers={"Authorization": "Bearer expired.token"})

        # Verify
        assert response.status_code == 401
        assert response.json()["detail"] == "Token expired"

    def test_refresh_token_success(self, client, mock_token_provider, sample_user):
        # Setup
        mock_token_provider.refresh_token.return_value = "new.refreshed.token"
        mock_token_provider.validate_token.return_value = sample_user

        # Execute
        response = client.post("/auth/refresh", headers={"Authorization": "Bearer old.token"})

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "new.refreshed.token"
        assert data["user_id"] == "user123"

        mock_token_provider.refresh_token.assert_called_once_with("old.token")

    def test_refresh_token_failure(self, client, mock_token_provider):
        # Setup
        mock_token_provider.refresh_token.side_effect = Exception("Invalid token")

        # Execute
        response = client.post("/auth/refresh", headers={"Authorization": "Bearer invalid.token"})

        # Verify
        assert response.status_code == 401
        assert "Token refresh failed" in response.json()["detail"]

    def test_logout(self, client):
        # Execute
        response = client.post("/auth/logout")

        # Verify
        assert response.status_code == 200
        assert response.json() == {"message": "Successfully logged out"}

    def test_missing_auth_header(self, client):
        # Execute
        response = client.get("/auth/me")

        # Verify
        assert response.status_code == 401
        assert response.json()["detail"] == "Authorization header required"

    def test_invalid_auth_header_format(self, client):
        # Execute
        response = client.get("/auth/me", headers={"Authorization": "InvalidFormat token"})

        # Verify
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authorization header format"
