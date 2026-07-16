from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.application.base import ValidationError
from mmf.services.identity.application.ports_out import (
    APIKeyAuthenticationProvider,
    AuthenticationMethod,
    AuthenticationResult,
)
from mmf.services.identity.application.use_cases.authenticate_with_api_key import (
    APIKeyAuthenticationRequest,
    AuthenticateWithAPIKeyUseCase,
    CreateAPIKeyRequest,
    CreateAPIKeyUseCase,
    RevokeAPIKeyRequest,
    RevokeAPIKeyUseCase,
)


class TestAPIKeyAuthenticationRequest:
    def test_valid_request(self):
        request = APIKeyAuthenticationRequest(api_key="valid_key")  # pragma: allowlist secret
        assert request.api_key == "valid_key"

    def test_missing_api_key(self):
        with pytest.raises(ValidationError, match="API key is required"):
            APIKeyAuthenticationRequest(api_key="")

    def test_invalid_api_key_type(self):
        with pytest.raises(ValidationError, match="API key must be a string"):
            APIKeyAuthenticationRequest(api_key=123)


class TestAuthenticateWithAPIKeyUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=APIKeyAuthenticationProvider)
        provider.authenticate = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return AuthenticateWithAPIKeyUseCase(mock_provider)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_provider):
        expected_result = Mock(spec=AuthenticationResult)
        expected_result.success = True
        mock_provider.authenticate.return_value = expected_result

        request = APIKeyAuthenticationRequest(api_key="valid_key")
        result = await use_case.execute(request)

        assert result == expected_result
        mock_provider.authenticate.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_exception(self, use_case, mock_provider):
        mock_provider.authenticate.side_effect = Exception("Provider error")

        request = APIKeyAuthenticationRequest(api_key="valid_key")
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "INTERNAL_ERROR"
        assert result.method_used == AuthenticationMethod.API_KEY

    @pytest.mark.asyncio
    async def test_execute_validation_error(self, use_case, mock_provider):
        mock_provider.authenticate.side_effect = ValidationError("Invalid input")

        request = APIKeyAuthenticationRequest(api_key="valid_key")

        with pytest.raises(ValidationError, match="Invalid input"):
            await use_case.execute(request)


class TestCreateAPIKeyRequest:
    def test_valid_request(self):
        request = CreateAPIKeyRequest(user_id="user123")
        assert request.user_id == "user123"

    def test_missing_user_id(self):
        with pytest.raises(ValidationError, match="User ID is required"):
            CreateAPIKeyRequest(user_id="")

    def test_invalid_key_name_type(self):
        with pytest.raises(ValidationError, match="Key name must be a string"):
            CreateAPIKeyRequest(user_id="user123", key_name=123)

    def test_invalid_permissions_type(self):
        with pytest.raises(ValidationError, match="Permissions must be a list"):
            CreateAPIKeyRequest(user_id="user123", permissions="read")


class TestCreateAPIKeyUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=APIKeyAuthenticationProvider)
        provider.create_api_key = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return CreateAPIKeyUseCase(mock_provider)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_provider):
        mock_provider.create_api_key.return_value = "new_api_key"

        request = CreateAPIKeyRequest(user_id="user123")
        result = await use_case.execute(request)

        assert result.success
        assert result.api_key == "new_api_key"  # pragma: allowlist secret
        assert result.message == "API key created successfully"
        mock_provider.create_api_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_validation_error(self, use_case, mock_provider):
        mock_provider.create_api_key.side_effect = ValidationError("Invalid input")

        request = CreateAPIKeyRequest(user_id="user123")
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "VALIDATION_ERROR"
        assert "Invalid input" in result.message

    @pytest.mark.asyncio
    async def test_execute_exception(self, use_case, mock_provider):
        mock_provider.create_api_key.side_effect = Exception("Unexpected error")

        request = CreateAPIKeyRequest(user_id="user123")
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "INTERNAL_ERROR"
        assert "Unexpected error" in result.message


class TestRevokeAPIKeyRequest:
    def test_valid_request(self):
        request = RevokeAPIKeyRequest(api_key="key_to_revoke")  # pragma: allowlist secret
        assert request.api_key == "key_to_revoke"

    def test_missing_api_key(self):
        with pytest.raises(ValidationError, match="API key is required"):
            RevokeAPIKeyRequest(api_key="")


class TestRevokeAPIKeyUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=APIKeyAuthenticationProvider)
        provider.revoke_api_key = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return RevokeAPIKeyUseCase(mock_provider)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_provider):
        mock_provider.revoke_api_key.return_value = True

        request = RevokeAPIKeyRequest(api_key="key_to_revoke")
        result = await use_case.execute(request)

        assert result.success
        assert result.message == "API key revoked successfully"
        mock_provider.revoke_api_key.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_not_found(self, use_case, mock_provider):
        mock_provider.revoke_api_key.return_value = False

        request = RevokeAPIKeyRequest(api_key="key_to_revoke")
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "KEY_NOT_FOUND"
        assert "API key not found" in result.message

    @pytest.mark.asyncio
    async def test_execute_validation_error(self, use_case, mock_provider):
        mock_provider.revoke_api_key.side_effect = ValidationError("Invalid input")

        request = RevokeAPIKeyRequest(api_key="key_to_revoke")
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "VALIDATION_ERROR"
        assert "Invalid input" in result.message

    @pytest.mark.asyncio
    async def test_execute_exception(self, use_case, mock_provider):
        mock_provider.revoke_api_key.side_effect = Exception("Unexpected error")

        request = RevokeAPIKeyRequest(api_key="key_to_revoke")
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "INTERNAL_ERROR"
        assert "Unexpected error" in result.message
