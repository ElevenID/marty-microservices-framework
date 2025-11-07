"""
Unit tests for JWT Token Validation Use Case.

Tests the business logic for standalone token validation use case
following hexagonal architecture principles.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from mmf_new.services.identity.application.ports_out import (
    TokenProvider,
    TokenValidationError,
)
from mmf_new.services.identity.application.use_cases import (
    TokenValidationResult,
    ValidateTokenRequest,
    ValidateTokenUseCase,
)
from mmf_new.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
)


class TestValidateTokenRequest:
    """Test suite for ValidateTokenRequest."""

    def test_valid_request(self):
        """Test creating a valid token validation request."""
        request = ValidateTokenRequest(token="valid.jwt.token")
        assert request.token == "valid.jwt.token"

    def test_empty_token_validation(self):
        """Test that empty token raises ValueError."""
        with pytest.raises(ValueError, match="Token is required"):
            ValidateTokenRequest(token="")

    def test_none_token_validation(self):
        """Test that None token raises ValueError."""
        with pytest.raises(ValueError, match="Token is required"):
            ValidateTokenRequest(token=None)

    def test_non_string_token_validation(self):
        """Test that non-string token raises TypeError."""
        with pytest.raises(TypeError, match="Token must be a string"):
            ValidateTokenRequest(token=123)


class TestTokenValidationResult:
    """Test suite for TokenValidationResult."""

    def test_success_result(self):
        """Test creating a successful validation result."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            auth_method="jwt"
        )

        result = TokenValidationResult.success(user)

        assert result.is_valid is True
        assert result.user == user
        assert result.error_message is None
        assert result.error_code is None

    def test_failure_result(self):
        """Test creating a failed validation result."""
        result = TokenValidationResult.failure(
            message="Token expired",
            code=AuthenticationErrorCode.TOKEN_INVALID
        )

        assert result.is_valid is False
        assert result.user is None
        assert result.error_message == "Token expired"
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID


class TestValidateTokenUseCase:
    """Test suite for ValidateTokenUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_token_provider = Mock(spec=TokenProvider)
        self.use_case = ValidateTokenUseCase(self.mock_token_provider)

        self.test_user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            email="test@example.com",
            auth_method="jwt"
        )

    @pytest.mark.asyncio
    async def test_successful_validation(self):
        """Test successful token validation."""
        # Arrange
        token = "valid.jwt.token"
        self.mock_token_provider.validate_token = AsyncMock(return_value=self.test_user)
        request = ValidateTokenRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_valid is True
        assert result.user == self.test_user
        assert result.error_message is None
        assert result.error_code is None

        self.mock_token_provider.validate_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_token_validation_error(self):
        """Test handling of token validation errors."""
        # Arrange
        token = "invalid.jwt.token"
        validation_error = TokenValidationError("Token is expired")
        self.mock_token_provider.validate_token = AsyncMock(side_effect=validation_error)
        request = ValidateTokenRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_valid is False
        assert result.user is None
        assert "Token validation failed: Token is expired" in result.error_message
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID

        self.mock_token_provider.validate_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_value_error_handling(self):
        """Test handling of ValueError exceptions."""
        # Arrange
        token = "malformed.token"
        value_error = ValueError("Invalid token format")
        self.mock_token_provider.validate_token = AsyncMock(side_effect=value_error)
        request = ValidateTokenRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_valid is False
        assert result.user is None
        assert "Invalid request: Invalid token format" in result.error_message
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID

    @pytest.mark.asyncio
    async def test_type_error_handling(self):
        """Test handling of TypeError exceptions."""
        # Arrange
        token = "valid.token"
        type_error = TypeError("Expected string")
        self.mock_token_provider.validate_token = AsyncMock(side_effect=type_error)
        request = ValidateTokenRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_valid is False
        assert result.user is None
        assert "Invalid request: Expected string" in result.error_message
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self):
        """Test handling of unexpected errors."""
        # Arrange
        token = "valid.jwt.token"
        unexpected_error = RuntimeError("Database connection failed")
        self.mock_token_provider.validate_token = AsyncMock(side_effect=unexpected_error)
        request = ValidateTokenRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_valid is False
        assert result.user is None
        assert result.error_message == "Unexpected error during token validation"
        assert result.error_code == AuthenticationErrorCode.INTERNAL_ERROR

    @pytest.mark.asyncio
    async def test_multiple_validation_calls(self):
        """Test that multiple validation calls work independently."""
        # Arrange
        token1 = "token1.jwt"
        token2 = "token2.jwt"

        user1 = AuthenticatedUser(
            user_id="user1",
            username="user1",
            auth_method="jwt"
        )
        user2 = AuthenticatedUser(
            user_id="user2",
            username="user2",
            auth_method="jwt"
        )

        self.mock_token_provider.validate_token = AsyncMock()
        self.mock_token_provider.validate_token.side_effect = [user1, user2]

        # Act
        result1 = await self.use_case.execute(ValidateTokenRequest(token=token1))
        result2 = await self.use_case.execute(ValidateTokenRequest(token=token2))

        # Assert
        assert result1.is_valid is True
        assert result1.user == user1
        assert result2.is_valid is True
        assert result2.user == user2

        assert self.mock_token_provider.validate_token.call_count == 2

    def test_use_case_initialization(self):
        """Test that use case initializes correctly with token provider."""
        provider = Mock(spec=TokenProvider)
        use_case = ValidateTokenUseCase(provider)

        assert use_case._token_provider == provider

    @pytest.mark.asyncio
    async def test_validation_preserves_user_data(self):
        """Test that validation preserves all user data from token."""
        # Arrange
        token = "valid.jwt.token"
        user_with_roles = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            email="test@example.com",
            roles={"admin", "user"},
            permissions={"read", "write", "delete"},
            auth_method="jwt",
            metadata={"department": "IT", "level": "senior"}
        )

        self.mock_token_provider.validate_token = AsyncMock(return_value=user_with_roles)
        request = ValidateTokenRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_valid is True
        assert result.user.user_id == "test-123"
        assert result.user.username == "testuser"
        assert result.user.email == "test@example.com"
        assert result.user.roles == {"admin", "user"}
        assert result.user.permissions == {"read", "write", "delete"}
        assert result.user.metadata == {"department": "IT", "level": "senior"}

    @pytest.mark.asyncio
    async def test_different_error_scenarios(self):
        """Test different error scenarios produce appropriate error codes."""
        token = "test.token"

        # Token validation error
        self.mock_token_provider.validate_token = AsyncMock(
            side_effect=TokenValidationError("Expired")
        )
        result = await self.use_case.execute(ValidateTokenRequest(token=token))
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID

        # Value error
        self.mock_token_provider.validate_token = AsyncMock(
            side_effect=ValueError("Bad format")
        )
        result = await self.use_case.execute(ValidateTokenRequest(token=token))
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID

        # Unexpected error
        self.mock_token_provider.validate_token = AsyncMock(
            side_effect=RuntimeError("System error")
        )
        result = await self.use_case.execute(ValidateTokenRequest(token=token))
        assert result.error_code == AuthenticationErrorCode.INTERNAL_ERROR

    @pytest.mark.asyncio
    async def test_validates_without_authentication_metadata(self):
        """Test that validation works without authentication-specific metadata."""
        # Arrange
        token = "valid.jwt.token"
        self.mock_token_provider.validate_token = AsyncMock(return_value=self.test_user)
        request = ValidateTokenRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_valid is True
        assert result.user == self.test_user
        # Note: Unlike authentication use case, this doesn't add auth metadata
