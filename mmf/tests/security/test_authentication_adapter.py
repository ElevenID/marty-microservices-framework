from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf.framework.security.adapters.authentication.adapter import (
    IdentityServiceAuthenticator,
)
from mmf.services.identity.application.ports_out import (
    AuthenticationResult as IdentityAuthenticationResult,
)
from mmf.services.identity.application.services.authentication_manager import (
    AuthenticationManager,
)
from mmf.services.identity.domain.models import (
    AuthenticatedUser as IdentityAuthenticatedUser,
)


@pytest.fixture
def mock_auth_manager():
    return AsyncMock(spec=AuthenticationManager)


@pytest.fixture
def authenticator(mock_auth_manager):
    return IdentityServiceAuthenticator(mock_auth_manager)


@pytest.mark.asyncio
async def test_authenticate_success(authenticator, mock_auth_manager):
    # Setup mock response
    mock_user = IdentityAuthenticatedUser(
        user_id="user123",
        username="testuser",
        email="test@example.com",
        roles={"admin"},
        permissions={"read", "write"},
        metadata={},
    )
    mock_result = IdentityAuthenticationResult(
        success=True, user=mock_user, error_message=None, metadata={}
    )
    mock_auth_manager.authenticate.return_value = mock_result

    # Call authenticate
    credentials = {
        "username": "testuser",
        "password": "password",  # pragma: allowlist secret
        "method": "basic",
    }
    result = await authenticator.authenticate(credentials)

    # Assertions
    assert result.success is True
    assert result.user is not None
    assert result.user.user_id == "user123"
    assert result.user.username == "testuser"
    assert result.error is None
    mock_auth_manager.authenticate.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_failure(authenticator, mock_auth_manager):
    # Setup mock response for failure
    mock_result = IdentityAuthenticationResult(
        success=False, user=None, error_message="Invalid credentials", metadata={}
    )
    mock_auth_manager.authenticate.return_value = mock_result

    # Call authenticate
    credentials = {"username": "testuser", "password": "wrongpassword"}  # pragma: allowlist secret
    result = await authenticator.authenticate(credentials)

    # Assertions
    assert result.success is False
    assert result.user is None
    assert result.error == "Invalid credentials"


@pytest.mark.asyncio
async def test_authenticate_exception(authenticator, mock_auth_manager):
    # Setup mock to raise exception
    mock_auth_manager.authenticate.side_effect = Exception("Database error")

    # Call authenticate
    credentials = {"username": "testuser", "password": "password"}  # pragma: allowlist secret
    result = await authenticator.authenticate(credentials)

    # Assertions
    assert result.success is False
    assert "Database error" in result.error


@pytest.mark.asyncio
async def test_validate_token_not_implemented(authenticator):
    result = await authenticator.validate_token("some-token")
    assert result.success is False
    assert result.error == "Not implemented"
