from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.application.base import ValidationError
from mmf.services.identity.application.ports_out import (
    AuthenticationMethod,
    AuthenticationResult,
    BasicAuthenticationProvider,
)
from mmf.services.identity.application.use_cases.authenticate_with_basic import (
    AuthenticateWithBasicUseCase,
    BasicAuthenticationRequest,
    ChangePasswordRequest,
    ChangePasswordResult,
    ChangePasswordUseCase,
)


class TestBasicAuthenticationRequest:
    def test_valid_request(self):
        request = BasicAuthenticationRequest(
            username="user", password="password"
        )  # pragma: allowlist secret
        assert request.username == "user"
        assert request.password == "password"

    def test_missing_username(self):
        with pytest.raises(ValidationError, match="Username is required"):
            BasicAuthenticationRequest(username="", password="password")

    def test_missing_password(self):
        with pytest.raises(ValidationError, match="Password is required"):
            BasicAuthenticationRequest(username="user", password="")

    def test_invalid_username_type(self):
        with pytest.raises(ValidationError, match="Username must be a string"):
            BasicAuthenticationRequest(username=123, password="password")

    def test_invalid_password_type(self):
        with pytest.raises(ValidationError, match="Password must be a string"):
            BasicAuthenticationRequest(username="user", password=123)


class TestAuthenticateWithBasicUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=BasicAuthenticationProvider)
        provider.authenticate = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return AuthenticateWithBasicUseCase(mock_provider)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_provider):
        expected_result = Mock(spec=AuthenticationResult)
        expected_result.success = True
        mock_provider.authenticate.return_value = expected_result

        request = BasicAuthenticationRequest(username="user", password="password")
        result = await use_case.execute(request)

        assert result == expected_result
        mock_provider.authenticate.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_exception(self, use_case, mock_provider):
        mock_provider.authenticate.side_effect = Exception("Provider error")

        request = BasicAuthenticationRequest(username="user", password="password")
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "INTERNAL_ERROR"
        assert result.method_used == AuthenticationMethod.BASIC

    @pytest.mark.asyncio
    async def test_execute_validation_error(self, use_case, mock_provider):
        # Mock provider to raise ValidationError
        mock_provider.authenticate.side_effect = ValidationError("Invalid input")

        request = BasicAuthenticationRequest(username="user", password="password")

        with pytest.raises(ValidationError, match="Invalid input"):
            await use_case.execute(request)


class TestChangePasswordRequest:
    def test_valid_request(self):
        request = ChangePasswordRequest(
            username="user",
            current_password="old_password",
            new_password="new_password",  # pragma: allowlist secret
        )
        assert request.username == "user"

    def test_missing_username(self):
        with pytest.raises(ValidationError, match="Username is required"):
            ChangePasswordRequest(username="", current_password="old", new_password="new")

    def test_missing_current_password(self):
        with pytest.raises(ValidationError, match="Current password is required"):
            ChangePasswordRequest(
                username="user",
                current_password="",
                new_password="new",  # pragma: allowlist secret
            )

    def test_missing_new_password(self):
        with pytest.raises(ValidationError, match="New password is required"):
            ChangePasswordRequest(
                username="user",
                current_password="old",
                new_password="",  # pragma: allowlist secret
            )

    def test_short_new_password(self):
        with pytest.raises(
            ValidationError, match="New password must be at least 8 characters long"
        ):
            ChangePasswordRequest(username="user", current_password="old", new_password="short")


class TestChangePasswordUseCase:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock(spec=BasicAuthenticationProvider)
        provider.change_password = AsyncMock()
        return provider

    @pytest.fixture
    def use_case(self, mock_provider):
        return ChangePasswordUseCase(mock_provider)

    @pytest.mark.asyncio
    async def test_execute_success(self, use_case, mock_provider):
        mock_provider.change_password.return_value = True

        request = ChangePasswordRequest(
            username="user", current_password="old", new_password="new_password"
        )
        result = await use_case.execute(request)

        assert result.success
        assert result.message == "Password changed successfully"
        mock_provider.change_password.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_failure(self, use_case, mock_provider):
        mock_provider.change_password.return_value = False

        request = ChangePasswordRequest(
            username="user", current_password="old", new_password="new_password"
        )
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "CHANGE_FAILED"

    @pytest.mark.asyncio
    async def test_execute_validation_error(self, use_case, mock_provider):
        mock_provider.change_password.side_effect = ValidationError("Invalid password")

        request = ChangePasswordRequest(
            username="user", current_password="old", new_password="new_password"
        )
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "VALIDATION_ERROR"
        assert result.message == "Invalid password"

    @pytest.mark.asyncio
    async def test_execute_exception(self, use_case, mock_provider):
        mock_provider.change_password.side_effect = Exception("Unexpected error")

        request = ChangePasswordRequest(
            username="user", current_password="old", new_password="new_password"
        )
        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "INTERNAL_ERROR"
