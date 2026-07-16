from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.application.base import ValidationError
from mmf.services.identity.application.ports_out.authentication_provider import (
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationProvider,
)
from mmf.services.identity.application.ports_out.authentication_provider import (
    AuthenticationResult as ProviderResult,
)
from mmf.services.identity.application.use_cases.authenticate_user import (
    AuthenticateUserRequest,
    AuthenticateUserUseCase,
)


class TestAuthenticateUserUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=AuthenticationProvider)
        provider.supported_methods = [AuthenticationMethod.BASIC]
        provider.authenticate = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return AuthenticateUserUseCase([mock_provider])

    @pytest.fixture
    def basic_credentials(self):
        return AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={"username": "user", "password": "pw"},  # pragma: allowlist secret
        )

    def test_initialization(self, mock_provider):
        """Test use case initialization and provider mapping."""
        use_case = AuthenticateUserUseCase([mock_provider])
        assert AuthenticationMethod.BASIC in use_case._provider_map
        assert use_case._provider_map[AuthenticationMethod.BASIC] == [mock_provider]

    async def test_execute_success(self, use_case, mock_provider, basic_credentials):
        """Test successful authentication."""
        expected_result = Mock(spec=ProviderResult)
        expected_result.success = True
        mock_provider.authenticate.return_value = expected_result

        request = AuthenticateUserRequest(credentials=basic_credentials)
        result = await use_case.execute(request)

        assert result == expected_result
        mock_provider.authenticate.assert_awaited_once_with(basic_credentials, None)

    async def test_execute_unsupported_method(self, use_case, basic_credentials):
        """Test authentication with unsupported method."""
        basic_credentials.method = AuthenticationMethod.API_KEY
        request = AuthenticateUserRequest(credentials=basic_credentials)

        result = await use_case.execute(request)

        # Note: The use case returns a failure result, not raises an exception
        assert result.success is False
        assert result.error_code == "METHOD_NOT_SUPPORTED"

    async def test_execute_provider_failure(self, use_case, mock_provider, basic_credentials):
        """Test authentication failure from provider."""
        failure_result = Mock(spec=ProviderResult)
        failure_result.success = False
        failure_result.error_message = "Invalid credentials"
        mock_provider.authenticate.return_value = failure_result

        request = AuthenticateUserRequest(credentials=basic_credentials)
        result = await use_case.execute(request)

        assert result.success is False
        assert result.error_message == "Invalid credentials"
        assert result.error_code == "AUTHENTICATION_FAILED"

    async def test_execute_provider_exception(self, use_case, mock_provider, basic_credentials):
        """Test provider raising an exception."""
        mock_provider.authenticate.side_effect = Exception("Provider error")

        request = AuthenticateUserRequest(credentials=basic_credentials)
        result = await use_case.execute(request)

        assert result.success is False
        assert result.error_message == "Provider error"
        assert result.error_code == "AUTHENTICATION_FAILED"

    async def test_multiple_providers_fallback(self, basic_credentials):
        """Test fallback to second provider if first fails."""
        provider1 = Mock(spec=AuthenticationProvider)
        provider1.supported_methods = [AuthenticationMethod.BASIC]
        provider1.authenticate = AsyncMock()
        provider1.authenticate.return_value = Mock(
            spec=ProviderResult, success=False, error_message="Fail 1"
        )

        provider2 = Mock(spec=AuthenticationProvider)
        provider2.supported_methods = [AuthenticationMethod.BASIC]
        provider2.authenticate = AsyncMock()
        success_result = Mock(spec=ProviderResult, success=True)
        provider2.authenticate.return_value = success_result

        use_case = AuthenticateUserUseCase([provider1, provider2])
        request = AuthenticateUserRequest(credentials=basic_credentials)

        result = await use_case.execute(request)

        assert result == success_result
        provider1.authenticate.assert_awaited_once()
        provider2.authenticate.assert_awaited_once()

    def test_request_validation(self):
        """Test request validation."""
        with pytest.raises(ValidationError, match="Credentials are required"):
            AuthenticateUserRequest(credentials=None)

        with pytest.raises(ValidationError, match="Valid authentication method is required"):
            AuthenticateUserRequest(credentials=Mock(method="invalid"))

    def test_get_supported_methods(self, use_case):
        """Test getting supported methods."""
        methods = use_case.get_supported_methods()
        assert AuthenticationMethod.BASIC in methods
        assert len(methods) == 1

    def test_get_providers_for_method(self, use_case, mock_provider):
        """Test getting providers for a method."""
        providers = use_case.get_providers_for_method(AuthenticationMethod.BASIC)
        assert providers == [mock_provider]

        providers_empty = use_case.get_providers_for_method(AuthenticationMethod.JWT)
        assert providers_empty == []
