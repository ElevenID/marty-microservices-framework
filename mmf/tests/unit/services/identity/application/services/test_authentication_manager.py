from unittest.mock import AsyncMock, Mock

import pytest

from mmf.services.identity.application.ports_out import (
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationProvider,
    AuthenticationResult,
)
from mmf.services.identity.application.services.authentication_manager import (
    AuthenticationManager,
    AuthenticationManagerError,
)


class TestAuthenticationManager:
    @pytest.fixture
    def manager(self):
        return AuthenticationManager()

    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=AuthenticationProvider)
        provider.supports_method.return_value = True
        provider.authenticate = AsyncMock()
        return provider

    def test_register_provider_success(self, manager, mock_provider):
        """Test successful provider registration."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

        assert manager.get_provider(AuthenticationMethod.BASIC) == mock_provider
        assert manager._default_provider == mock_provider

    def test_register_provider_unsupported_method(self, manager, mock_provider):
        """Test registering a provider that doesn't support the method."""
        mock_provider.supports_method.return_value = False

        with pytest.raises(AuthenticationManagerError, match="does not support method"):
            manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

    def test_register_default_provider(self, manager):
        """Test default provider logic."""
        provider1 = Mock(spec=AuthenticationProvider)
        provider1.supports_method.return_value = True

        provider2 = Mock(spec=AuthenticationProvider)
        provider2.supports_method.return_value = True

        # First registered becomes default
        manager.register_provider(AuthenticationMethod.BASIC, provider1)
        assert manager._default_provider == provider1

        # Second registered doesn't override default unless specified
        manager.register_provider(AuthenticationMethod.API_KEY, provider2)
        assert manager._default_provider == provider1

        # Explicitly setting default
        manager.register_provider(AuthenticationMethod.JWT, provider2, is_default=True)
        assert manager._default_provider == provider2

    def test_unregister_provider(self, manager, mock_provider):
        """Test unregistering a provider."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)
        assert manager.get_provider(AuthenticationMethod.BASIC) is not None

        manager.unregister_provider(AuthenticationMethod.BASIC)
        assert manager.get_provider(AuthenticationMethod.BASIC) is None
        assert manager._default_provider is None

    def test_unregister_default_provider_fallback(self, manager):
        """Test default provider fallback when unregistering."""
        provider1 = Mock(spec=AuthenticationProvider)
        provider1.supports_method.return_value = True

        provider2 = Mock(spec=AuthenticationProvider)
        provider2.supports_method.return_value = True

        manager.register_provider(AuthenticationMethod.BASIC, provider1)
        manager.register_provider(AuthenticationMethod.API_KEY, provider2)

        assert manager._default_provider == provider1

        manager.unregister_provider(AuthenticationMethod.BASIC)

        # Should fallback to the other provider
        assert manager._default_provider == provider2

    def test_get_provider_not_found(self, manager):
        """Test getting a non-existent provider."""
        assert manager.get_provider(AuthenticationMethod.BASIC) is None

    def test_has_provider(self, manager, mock_provider):
        """Test checking if provider exists."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)
        assert manager.has_provider(AuthenticationMethod.BASIC)
        assert not manager.has_provider(AuthenticationMethod.JWT)

    def test_get_supported_methods(self, manager, mock_provider):
        """Test getting supported methods."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)
        methods = manager.get_supported_methods()
        assert AuthenticationMethod.BASIC in methods
        assert len(methods) == 1

    @pytest.mark.asyncio
    async def test_authenticate_success(self, manager, mock_provider):
        """Test successful authentication."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

        credentials = Mock(spec=AuthenticationCredentials)
        credentials.method = AuthenticationMethod.BASIC

        expected_result = Mock(spec=AuthenticationResult)
        expected_result.success = True
        expected_result.user = Mock()
        expected_result.user.user_id = "user123"
        mock_provider.authenticate.return_value = expected_result

        result = await manager.authenticate(credentials)

        assert result == expected_result
        mock_provider.authenticate.assert_called_once_with(credentials, None)

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, manager, mock_provider):
        """Test failed authentication."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

        credentials = Mock(spec=AuthenticationCredentials)
        credentials.method = AuthenticationMethod.BASIC

        expected_result = Mock(spec=AuthenticationResult)
        expected_result.success = False
        mock_provider.authenticate.return_value = expected_result

        result = await manager.authenticate(credentials)

        assert result == expected_result

    @pytest.mark.asyncio
    async def test_authenticate_no_provider(self, manager):
        """Test authentication with no provider registered."""
        credentials = Mock(spec=AuthenticationCredentials)
        credentials.method = AuthenticationMethod.BASIC

        result = await manager.authenticate(credentials)

        assert not result.success
        assert result.error_code == "METHOD_NOT_SUPPORTED"

    @pytest.mark.asyncio
    async def test_authenticate_exception(self, manager, mock_provider):
        """Test authentication when provider raises exception."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

        credentials = Mock(spec=AuthenticationCredentials)
        credentials.method = AuthenticationMethod.BASIC

        mock_provider.authenticate.side_effect = Exception("Provider error")

        result = await manager.authenticate(credentials)

        assert not result.success
        assert result.error_code == "INTERNAL_ERROR"

    @pytest.mark.asyncio
    async def test_validate_credentials_success(self, manager, mock_provider):
        """Test successful credential validation."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)
        mock_provider.validate_credentials = AsyncMock(return_value=True)

        credentials = Mock(spec=AuthenticationCredentials)
        credentials.method = AuthenticationMethod.BASIC

        result = await manager.validate_credentials(credentials)

        assert result is True
        mock_provider.validate_credentials.assert_called_once_with(credentials, None)

    @pytest.mark.asyncio
    async def test_validate_credentials_no_provider(self, manager):
        """Test credential validation with no provider."""
        credentials = Mock(spec=AuthenticationCredentials)
        credentials.method = AuthenticationMethod.BASIC

        result = await manager.validate_credentials(credentials)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_credentials_exception(self, manager, mock_provider):
        """Test credential validation exception."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)
        mock_provider.validate_credentials = AsyncMock(side_effect=Exception("Error"))

        credentials = Mock(spec=AuthenticationCredentials)
        credentials.method = AuthenticationMethod.BASIC

        result = await manager.validate_credentials(credentials)

        assert result is False

    @pytest.mark.asyncio
    async def test_refresh_authentication_success(self, manager, mock_provider):
        """Test successful token refresh."""
        manager.register_provider(AuthenticationMethod.JWT, mock_provider)

        user = Mock()
        user.auth_method = "jwt"

        expected_result = Mock(spec=AuthenticationResult)
        mock_provider.refresh_authentication = AsyncMock(return_value=expected_result)

        result = await manager.refresh_authentication(user)

        assert result == expected_result
        mock_provider.refresh_authentication.assert_called_once_with(user, None)

    @pytest.mark.asyncio
    async def test_refresh_authentication_unknown_method(self, manager):
        """Test refresh with unknown method."""
        user = Mock()
        user.auth_method = "unknown_method"

        result = await manager.refresh_authentication(user)

        assert not result.success
        assert result.error_code == "UNKNOWN_AUTH_METHOD"

    @pytest.mark.asyncio
    async def test_refresh_authentication_no_provider(self, manager):
        """Test refresh with no provider."""
        user = Mock()
        user.auth_method = "jwt"

        result = await manager.refresh_authentication(user)

        assert not result.success
        assert result.error_code == "PROVIDER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_refresh_authentication_exception(self, manager, mock_provider):
        """Test refresh exception."""
        manager.register_provider(AuthenticationMethod.JWT, mock_provider)

        user = Mock()
        user.auth_method = "jwt"

        mock_provider.refresh_authentication = AsyncMock(side_effect=Exception("Error"))

        result = await manager.refresh_authentication(user)

        assert not result.success
        assert result.error_code == "REFRESH_FAILED"

    @pytest.mark.asyncio
    async def test_try_multiple_methods_success_first(self, manager, mock_provider):
        """Test multiple methods where first one succeeds."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

        creds1 = Mock(spec=AuthenticationCredentials)
        creds1.method = AuthenticationMethod.BASIC

        success_result = Mock(spec=AuthenticationResult)
        success_result.success = True
        mock_provider.authenticate.return_value = success_result

        result = await manager.try_multiple_methods([creds1])

        assert result == success_result
        assert result.success

    @pytest.mark.asyncio
    async def test_try_multiple_methods_success_second(self, manager, mock_provider):
        """Test multiple methods where second one succeeds."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

        creds1 = Mock(spec=AuthenticationCredentials)
        creds1.method = AuthenticationMethod.BASIC

        creds2 = Mock(spec=AuthenticationCredentials)
        creds2.method = AuthenticationMethod.BASIC

        fail_result = Mock(spec=AuthenticationResult)
        fail_result.success = False

        success_result = Mock(spec=AuthenticationResult)
        success_result.success = True

        mock_provider.authenticate.side_effect = [fail_result, success_result]

        result = await manager.try_multiple_methods([creds1, creds2])

        assert result == success_result
        assert result.success

    @pytest.mark.asyncio
    async def test_try_multiple_methods_all_fail(self, manager, mock_provider):
        """Test multiple methods where all fail."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

        creds1 = Mock(spec=AuthenticationCredentials)
        creds1.method = AuthenticationMethod.BASIC

        fail_result = Mock(spec=AuthenticationResult)
        fail_result.success = False

        mock_provider.authenticate.return_value = fail_result

        result = await manager.try_multiple_methods([creds1])

        assert result == fail_result
        assert not result.success

    @pytest.mark.asyncio
    async def test_try_multiple_methods_empty_list(self, manager):
        """Test multiple methods with empty list."""
        result = await manager.try_multiple_methods([])

        assert not result.success
        assert result.error_code == "NO_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_try_multiple_methods_exception(self, manager, mock_provider):
        """Test multiple methods exception."""
        manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

        creds1 = Mock(spec=AuthenticationCredentials)
        creds1.method = AuthenticationMethod.BASIC

        mock_provider.authenticate.side_effect = Exception("Error")

        result = await manager.try_multiple_methods([creds1])

        assert not result.success
        assert result.error_code == "INTERNAL_ERROR"

    def test_register_provider_exception(self, manager, mock_provider):
        """Test exception during provider registration."""
        # Mock supports_method to raise an exception
        mock_provider.supports_method.side_effect = Exception("Unexpected error")

        with pytest.raises(AuthenticationManagerError, match="Failed to register provider"):
            manager.register_provider(AuthenticationMethod.BASIC, mock_provider)

    def test_unregister_non_default_provider(self, manager):
        """Test unregistering a provider that is not the default."""
        provider1 = Mock(spec=AuthenticationProvider)
        provider1.supports_method.return_value = True

        provider2 = Mock(spec=AuthenticationProvider)
        provider2.supports_method.return_value = True

        manager.register_provider(AuthenticationMethod.BASIC, provider1)
        manager.register_provider(AuthenticationMethod.API_KEY, provider2)

        # provider1 is default
        assert manager._default_provider == provider1

        manager.unregister_provider(AuthenticationMethod.API_KEY)

        # provider1 should still be default
        assert manager._default_provider == provider1
        assert manager.get_provider(AuthenticationMethod.API_KEY) is None

    def test_get_provider_info_multiple(self, manager):
        """Test getting provider info with multiple providers."""
        provider1 = Mock(spec=AuthenticationProvider)
        provider1.supported_methods = [AuthenticationMethod.BASIC]

        provider2 = Mock(spec=AuthenticationProvider)
        provider2.supported_methods = [AuthenticationMethod.API_KEY]

        manager.register_provider(AuthenticationMethod.BASIC, provider1)
        manager.register_provider(AuthenticationMethod.API_KEY, provider2)

        info = manager.get_provider_info()

        assert len(info) == 2
        assert AuthenticationMethod.BASIC.value in info
        assert AuthenticationMethod.API_KEY.value in info
        assert info[AuthenticationMethod.BASIC.value]["is_default"] is True
        assert info[AuthenticationMethod.API_KEY.value]["is_default"] is False
