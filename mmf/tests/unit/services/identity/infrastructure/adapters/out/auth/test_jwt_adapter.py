"""
Unit tests for JWT Token Provider Infrastructure Adapter.

Tests the JWT implementation of the TokenProvider port,
including token creation, validation, and error handling.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest

from mmf.services.identity.application.ports_out import (
    TokenCreationError,
    TokenValidationError,
)
from mmf.services.identity.domain.models import AuthenticatedUser
from mmf.services.identity.infrastructure.adapters import JWTConfig, JWTTokenProvider


class TestJWTConfig:
    """Test suite for JWTConfig."""

    def test_minimal_config(self):
        """Test creating JWT config with minimal required fields."""
        config = JWTConfig(secret_key="test-secret")  # pragma: allowlist secret

        assert config.secret_key == "test-secret"
        assert config.algorithm == "HS256"
        assert config.access_token_expire_minutes == 30
        assert config.issuer is None
        assert config.audience is None

    def test_complete_config(self):
        """Test creating JWT config with all fields."""
        config = JWTConfig(
            secret_key="test-secret",
            algorithm="HS512",
            access_token_expire_minutes=60,
            issuer="test-issuer",
            audience="test-audience",
        )

        assert config.secret_key == "test-secret"
        assert config.algorithm == "HS512"
        assert config.access_token_expire_minutes == 60
        assert config.issuer == "test-issuer"
        assert config.audience == "test-audience"

    def test_empty_secret_key_validation(self):
        """Test that empty secret key raises ValueError."""
        with pytest.raises(ValueError, match="Secret key is required"):
            JWTConfig(secret_key="")

    def test_none_secret_key_validation(self):
        """Test that None secret key raises ValueError."""
        with pytest.raises(ValueError, match="Secret key is required"):
            JWTConfig(secret_key=None)


class TestJWTTokenProvider:
    """Test suite for JWTTokenProvider."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = JWTConfig(
            secret_key="test-secret-key-123",  # pragma: allowlist secret
            access_token_expire_minutes=30,
            issuer="test-issuer",
            audience="test-audience",
        )
        self.provider = JWTTokenProvider(self.config)

        self.test_user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            email="test@example.com",
            roles={"admin", "user"},
            permissions={"read", "write"},
            auth_method="jwt",
            metadata={"department": "IT"},
        )

    @pytest.mark.asyncio
    async def test_create_token_minimal(self):
        """Test creating a JWT token with minimal user data."""
        user = AuthenticatedUser(user_id="simple-user", username="simpleuser", auth_method="jwt")

        token = await self.provider.create_token(user)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode token to verify structure
        payload = jwt.decode(
            token,
            self.config.secret_key,
            algorithms=[self.config.algorithm],
            audience=self.config.audience,
            issuer=self.config.issuer,
        )

        assert payload["sub"] == "simple-user"
        assert payload["username"] == "simpleuser"
        assert payload["iss"] == "test-issuer"
        assert payload["aud"] == "test-audience"

    @pytest.mark.asyncio
    async def test_create_token_complete(self):
        """Test creating a JWT token with complete user data."""
        token = await self.provider.create_token(self.test_user)

        # Decode token to verify all fields
        payload = jwt.decode(
            token,
            self.config.secret_key,
            algorithms=[self.config.algorithm],
            audience=self.config.audience,
            issuer=self.config.issuer,
        )

        assert payload["sub"] == "test-123"
        assert payload["username"] == "testuser"
        assert payload["email"] == "test@example.com"
        assert set(payload["roles"]) == {"admin", "user"}
        assert set(payload["permissions"]) == {"read", "write"}
        assert payload["user_metadata"] == {"department": "IT"}
        assert payload["iss"] == "test-issuer"
        assert payload["aud"] == "test-audience"

    @pytest.mark.asyncio
    async def test_create_token_with_custom_expiration(self):
        """Test creating a token with custom expiration time."""
        custom_expiry = datetime.now(timezone.utc) + timedelta(hours=2)

        token = await self.provider.create_token(self.test_user, expires_at=custom_expiry)

        payload = jwt.decode(
            token,
            self.config.secret_key,
            algorithms=[self.config.algorithm],
            audience=self.config.audience,
            issuer=self.config.issuer,
        )

        # Verify custom expiration (with small tolerance for timing)
        token_exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert abs((token_exp - custom_expiry).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_create_token_with_additional_claims(self):
        """Test creating a token with additional claims."""
        additional_claims = {"custom_field": "custom_value", "session_id": "session-123"}

        token = await self.provider.create_token(
            self.test_user, additional_claims=additional_claims
        )

        payload = jwt.decode(
            token,
            self.config.secret_key,
            algorithms=[self.config.algorithm],
            audience=self.config.audience,
            issuer=self.config.issuer,
        )

        assert payload["custom_field"] == "custom_value"
        assert payload["session_id"] == "session-123"

    @pytest.mark.asyncio
    async def test_create_token_timezone_handling(self):
        """Test that naive datetime is converted to UTC."""
        naive_expiry = datetime(2026, 1, 1, 12, 0, 0)  # No timezone, future date

        token = await self.provider.create_token(self.test_user, expires_at=naive_expiry)

        payload = jwt.decode(
            token,
            self.config.secret_key,
            algorithms=[self.config.algorithm],
            audience=self.config.audience,
            issuer=self.config.issuer,
        )

        # Should be treated as UTC
        expected_timestamp = naive_expiry.replace(tzinfo=timezone.utc).timestamp()
        assert payload["exp"] == expected_timestamp

    @pytest.mark.asyncio
    async def test_validate_token_success(self):
        """Test successful token validation."""
        token = await self.provider.create_token(self.test_user)

        validated_user = await self.provider.validate_token(token)

        assert validated_user.user_id == "test-123"
        assert validated_user.username == "testuser"
        assert validated_user.email == "test@example.com"
        assert validated_user.roles == {"admin", "user"}
        assert validated_user.permissions == {"read", "write"}
        assert validated_user.metadata["department"] == "IT"
        assert validated_user.auth_method == "jwt"

    @pytest.mark.asyncio
    async def test_validate_token_with_metadata(self):
        """Test that token metadata is properly included."""
        token = await self.provider.create_token(self.test_user)

        validated_user = await self.provider.validate_token(token)

        # Check token-specific metadata
        assert "token_issued_at" in validated_user.metadata
        assert "token_expires_at" in validated_user.metadata
        assert validated_user.metadata["token_issuer"] == "test-issuer"
        assert validated_user.metadata["token_audience"] == "test-audience"

    @pytest.mark.asyncio
    async def test_validate_expired_token(self):
        """Test validation of an expired token."""
        # Create token with past expiration
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        token = await self.provider.create_token(self.test_user, expires_at=past_expiry)

        with pytest.raises(TokenValidationError, match="JWT token has expired"):
            await self.provider.validate_token(token)

    @pytest.mark.asyncio
    async def test_validate_invalid_token(self):
        """Test validation of an invalid token."""
        invalid_token = "invalid.jwt.token"

        with pytest.raises(TokenValidationError, match="Invalid JWT token"):
            await self.provider.validate_token(invalid_token)

    @pytest.mark.asyncio
    async def test_validate_token_wrong_secret(self):
        """Test validation with wrong secret key."""
        token = await self.provider.create_token(self.test_user)

        # Create provider with different secret
        wrong_config = JWTConfig(secret_key="wrong-secret")
        wrong_provider = JWTTokenProvider(wrong_config)

        with pytest.raises(TokenValidationError, match="Invalid JWT token"):
            await wrong_provider.validate_token(token)

    @pytest.mark.asyncio
    async def test_validate_token_missing_required_claims(self):
        """Test validation of token missing required claims."""
        # Create token with issuer/audience but missing 'sub' claim
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iss": self.config.issuer,
            "aud": self.config.audience,
        }
        token = jwt.encode(payload, self.config.secret_key, algorithm=self.config.algorithm)

        with pytest.raises(TokenValidationError, match="Token missing 'sub' claim"):
            await self.provider.validate_token(token)

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """Test successful token refresh."""
        original_token = await self.provider.create_token(self.test_user)

        new_token = await self.provider.refresh_token(original_token)

        assert new_token != original_token

        # Validate new token works
        validated_user = await self.provider.validate_token(new_token)
        assert validated_user.user_id == self.test_user.user_id

    @pytest.mark.asyncio
    async def test_refresh_token_with_custom_expiry(self):
        """Test token refresh with custom expiration."""
        original_token = await self.provider.create_token(self.test_user)
        custom_expiry = datetime.now(timezone.utc) + timedelta(hours=4)

        new_token = await self.provider.refresh_token(original_token, new_expires_at=custom_expiry)

        payload = jwt.decode(
            new_token,
            self.config.secret_key,
            algorithms=[self.config.algorithm],
            audience=self.config.audience,
            issuer=self.config.issuer,
        )

        token_exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert abs((token_exp - custom_expiry).total_seconds()) < 5

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self):
        """Test refresh with invalid token."""
        invalid_token = "invalid.jwt.token"

        with pytest.raises(TokenValidationError):
            await self.provider.refresh_token(invalid_token)

    @pytest.mark.asyncio
    @patch("jwt.encode")
    async def test_create_token_error_handling(self, mock_encode):
        """Test error handling during token creation."""
        mock_encode.side_effect = Exception("JWT encoding failed")

        with pytest.raises(TokenCreationError, match="Failed to create JWT token"):
            await self.provider.create_token(self.test_user)

    @pytest.mark.asyncio
    async def test_validate_token_generic_error_handling(self):
        """Test generic error handling during token validation."""
        with patch("jwt.decode") as mock_decode:
            mock_decode.side_effect = Exception("Unexpected error")

            token = "some.jwt.token"
            with pytest.raises(TokenValidationError, match="Token validation failed"):
                await self.provider.validate_token(token)

    @pytest.mark.asyncio
    async def test_config_without_issuer_audience(self):
        """Test provider with config that has no issuer/audience."""
        simple_config = JWTConfig(secret_key="simple-secret")
        simple_provider = JWTTokenProvider(simple_config)

        token = await simple_provider.create_token(self.test_user)

        payload = jwt.decode(token, simple_config.secret_key, algorithms=[simple_config.algorithm])

        assert "iss" not in payload
        assert "aud" not in payload

    @pytest.mark.asyncio
    async def test_roundtrip_token_operations(self):
        """Test complete roundtrip: create -> validate -> refresh -> validate."""
        # Create initial token
        token1 = await self.provider.create_token(self.test_user)

        # Validate initial token
        user1 = await self.provider.validate_token(token1)
        assert user1.user_id == self.test_user.user_id

        # Refresh token
        token2 = await self.provider.refresh_token(token1)

        # Validate refreshed token
        user2 = await self.provider.validate_token(token2)
        assert user2.user_id == self.test_user.user_id
        assert user2.username == self.test_user.username
