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
