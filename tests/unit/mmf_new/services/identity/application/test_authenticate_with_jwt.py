"""
Unit tests for JWT Authentication Use Case.

Tests the business logic for JWT authentication use case
following hexagonal architecture principles.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from mmf_new.services.identity.application.ports_out import (
    TokenProvider,
    TokenValidationError,
)
from mmf_new.services.identity.application.use_cases import (
    AuthenticateWithJWTRequest,
    AuthenticateWithJWTUseCase,
)
from mmf_new.services.identity.domain.models import (
    AuthenticatedUser,
    AuthenticationErrorCode,
)


class TestAuthenticateWithJWTRequest:
    """Test suite for AuthenticateWithJWTRequest."""

    def test_valid_request(self):
        """Test creating a valid JWT authentication request."""
        request = AuthenticateWithJWTRequest(token="valid.jwt.token")
        assert request.token == "valid.jwt.token"

    def test_empty_token_validation(self):
        """Test that empty token raises ValueError."""
        with pytest.raises(ValueError, match="Token is required"):
            AuthenticateWithJWTRequest(token="")

    def test_none_token_validation(self):
        """Test that None token raises ValueError."""
        with pytest.raises(ValueError, match="Token is required"):
            AuthenticateWithJWTRequest(token=None)

    def test_non_string_token_validation(self):
        """Test that non-string token raises TypeError."""
        with pytest.raises(TypeError, match="Token must be a string"):
            AuthenticateWithJWTRequest(token=123)


class TestAuthenticateWithJWTUseCase:
    """Test suite for AuthenticateWithJWTUseCase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_token_provider = Mock(spec=TokenProvider)
        self.use_case = AuthenticateWithJWTUseCase(self.mock_token_provider)

        self.test_user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            email="test@example.com",
            auth_method="jwt"
        )

    @pytest.mark.asyncio
    async def test_successful_authentication(self):
        """Test successful JWT authentication."""
        # Arrange
        token = "valid.jwt.token"
        self.mock_token_provider.validate_token = AsyncMock(return_value=self.test_user)
        request = AuthenticateWithJWTRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_successful is True
        assert result.authenticated_user == self.test_user
        assert result.error_message is None
        assert result.error_code is None
        assert result.metadata["token"] == token
        assert result.metadata["auth_method"] == "JWT"

        self.mock_token_provider.validate_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_token_validation_error(self):
        """Test handling of token validation errors."""
        # Arrange
        token = "invalid.jwt.token"
        validation_error = TokenValidationError("Token is expired")
        self.mock_token_provider.validate_token = AsyncMock(side_effect=validation_error)
        request = AuthenticateWithJWTRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_successful is False
        assert result.authenticated_user is None
        assert "Token validation failed: Token is expired" in result.error_message
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID
        assert result.metadata["original_error"] == "Token is expired"

        self.mock_token_provider.validate_token.assert_called_once_with(token)

    @pytest.mark.asyncio
    async def test_value_error_handling(self):
        """Test handling of ValueError exceptions."""
        # Arrange
        token = "malformed.token"
        value_error = ValueError("Invalid token format")
        self.mock_token_provider.validate_token = AsyncMock(side_effect=value_error)
        request = AuthenticateWithJWTRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_successful is False
        assert result.authenticated_user is None
        assert "Token validation failed: Invalid token format" in result.error_message
        assert result.error_code == AuthenticationErrorCode.TOKEN_INVALID
        assert result.metadata["original_error"] == "Invalid token format"

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self):
        """Test handling of unexpected errors."""
        # Arrange
        token = "valid.jwt.token"
        unexpected_error = RuntimeError("Database connection failed")
        self.mock_token_provider.validate_token = AsyncMock(side_effect=unexpected_error)
        request = AuthenticateWithJWTRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_successful is False
        assert result.authenticated_user is None
        assert result.error_message == "Unexpected error during JWT authentication"
        assert result.error_code == AuthenticationErrorCode.INTERNAL_ERROR
        assert result.metadata["original_error"] == "Database connection failed"

    @pytest.mark.asyncio
    async def test_multiple_authentication_calls(self):
        """Test that multiple authentication calls work independently."""
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
        result1 = await self.use_case.execute(AuthenticateWithJWTRequest(token=token1))
        result2 = await self.use_case.execute(AuthenticateWithJWTRequest(token=token2))

        # Assert
        assert result1.is_successful is True
        assert result1.authenticated_user == user1
        assert result2.is_successful is True
        assert result2.authenticated_user == user2

        assert self.mock_token_provider.validate_token.call_count == 2

    def test_use_case_initialization(self):
        """Test that use case initializes correctly with token provider."""
        provider = Mock(spec=TokenProvider)
        use_case = AuthenticateWithJWTUseCase(provider)

        assert use_case._token_provider == provider

    @pytest.mark.asyncio
    async def test_authentication_preserves_user_data(self):
        """Test that authentication preserves all user data from token."""
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
        request = AuthenticateWithJWTRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_successful is True
        assert result.authenticated_user.user_id == "test-123"
        assert result.authenticated_user.username == "testuser"
        assert result.authenticated_user.email == "test@example.com"
        assert result.authenticated_user.roles == {"admin", "user"}
        assert result.authenticated_user.permissions == {"read", "write", "delete"}
        assert result.authenticated_user.metadata == {"department": "IT", "level": "senior"}

    @pytest.mark.asyncio
    async def test_error_details_preserved(self):
        """Test that error details are properly preserved and formatted."""
        # Arrange
        token = "expired.jwt.token"
        detailed_error = TokenValidationError("JWT token expired at 2023-01-01T00:00:00Z")
        self.mock_token_provider.validate_token = AsyncMock(side_effect=detailed_error)
        request = AuthenticateWithJWTRequest(token=token)

        # Act
        result = await self.use_case.execute(request)

        # Assert
        assert result.is_successful is False
        assert "JWT token expired at 2023-01-01T00:00:00Z" in result.error_message
        assert result.metadata["original_error"] == "JWT token expired at 2023-01-01T00:00:00Z"
