from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.application.base import ValidationError
from mmf.services.identity.application.ports_out import (
    APIKeyAuthenticationProvider,
    AuthenticationMethod,
    AuthenticationResult,
    BasicAuthenticationProvider,
)
from mmf.services.identity.application.ports_out.token_provider import (
    TokenProvider,
    TokenValidationError,
)
from mmf.services.identity.application.use_cases.authenticate_with_api_key import (
    APIKeyAuthenticationRequest,
    AuthenticateWithAPIKeyUseCase,
)
from mmf.services.identity.application.use_cases.authenticate_with_basic import (
    AuthenticateWithBasicUseCase,
    BasicAuthenticationRequest,
)
from mmf.services.identity.application.use_cases.authenticate_with_jwt import (
    AuthenticateWithJWTRequest,
    AuthenticateWithJWTUseCase,
)
from mmf.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
)


class TestAuthenticateWithBasicUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=BasicAuthenticationProvider)
        provider.authenticate = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return AuthenticateWithBasicUseCase(mock_provider)

    async def test_execute_success(self, use_case, mock_provider):
        """Test successful basic authentication."""
        expected_result = Mock(spec=AuthenticationResult)
        expected_result.success = True
        mock_provider.authenticate.return_value = expected_result

        request = BasicAuthenticationRequest(username="user", password="pw")
        result = await use_case.execute(request)

        assert result == expected_result
        mock_provider.authenticate.assert_awaited_once()

        # Verify credentials passed to provider
        call_args = mock_provider.authenticate.call_args
        credentials = call_args[0][0]
        assert credentials.method == AuthenticationMethod.BASIC
        assert credentials.credentials["username"] == "user"
        assert credentials.credentials["password"] == "pw"  # pragma: allowlist secret

    async def test_execute_validation_error(self, use_case):
        """Test validation error handling."""
        with pytest.raises(ValidationError, match="Username is required"):
            BasicAuthenticationRequest(username="", password="pw")  # pragma: allowlist secret

    async def test_execute_unexpected_error(self, use_case, mock_provider):
        """Test unexpected error handling."""
        mock_provider.authenticate.side_effect = Exception("Unexpected")

        request = BasicAuthenticationRequest(
            username="user",
            password="pw",  # pragma: allowlist secret
        )
        result = await use_case.execute(request)

        assert result.success is False
        assert result.error_code == "INTERNAL_ERROR"
        assert "Unexpected" in result.metadata["original_error"]


class TestAuthenticateWithJWTUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=TokenProvider)
        provider.validate_token = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return AuthenticateWithJWTUseCase(mock_provider)

    async def test_execute_success(self, use_case, mock_provider):
        """Test successful JWT authentication."""
        user = AuthenticatedUser(user_id="user1")
        mock_provider.validate_token.return_value = user

        request = AuthenticateWithJWTRequest(token="valid.token")
        result = await use_case.execute(request)

        assert result.status.value == "success"
        assert result.authenticated_user == user
        assert result.metadata["token"] == "valid.token"

    async def test_execute_token_validation_error(self, use_case, mock_provider):
        """Test token validation error."""
        mock_provider.validate_token.side_effect = TokenValidationError("Invalid token")

        request = AuthenticateWithJWTRequest(token="invalid.token")
        result = await use_case.execute(request)

        assert result.status.value == "failed"
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID
        assert "Invalid token" in result.error_message

    async def test_execute_unexpected_error(self, use_case, mock_provider):
        """Test unexpected error handling."""
        mock_provider.validate_token.side_effect = Exception("Unexpected")

        request = AuthenticateWithJWTRequest(token="valid.token")
        result = await use_case.execute(request)

        assert result.status.value == "failed"
        assert result.error_code == AuthenticationErrorCode.INTERNAL_ERROR


class TestAuthenticateWithAPIKeyUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=APIKeyAuthenticationProvider)
        provider.authenticate = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return AuthenticateWithAPIKeyUseCase(mock_provider)

    async def test_execute_success(self, use_case, mock_provider):
        """Test successful API key authentication."""
        expected_result = Mock(spec=AuthenticationResult)
        expected_result.success = True
        mock_provider.authenticate.return_value = expected_result

        request = APIKeyAuthenticationRequest(api_key="valid-key")
        result = await use_case.execute(request)

        assert result == expected_result
        mock_provider.authenticate.assert_awaited_once()

        # Verify credentials passed to provider
        call_args = mock_provider.authenticate.call_args
        credentials = call_args[0][0]
        assert credentials.method == AuthenticationMethod.API_KEY
        assert credentials.credentials["api_key"] == "valid-key"  # pragma: allowlist secret

    async def test_execute_validation_error(self, use_case):
        """Test validation error handling."""
        with pytest.raises(ValidationError, match="API key is required"):
            APIKeyAuthenticationRequest(api_key="")

    async def test_execute_unexpected_error(self, use_case, mock_provider):
        """Test unexpected error handling."""
        mock_provider.authenticate.side_effect = Exception("Unexpected")

        request = APIKeyAuthenticationRequest(api_key="valid-key")
        result = await use_case.execute(request)

        assert result.success is False
        assert result.error_code == "INTERNAL_ERROR"
