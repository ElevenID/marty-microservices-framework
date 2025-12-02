from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from mmf.services.identity.application.ports_out import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationResult,
)
from mmf.services.identity.domain.models import AuthenticatedUser
from mmf.services.identity.infrastructure.adapters.out.auth.api_key_adapter import (
    APIKeyAdapter,
    APIKeyConfig,
)


class TestAPIKeyAdapter:
    @pytest.fixture
    def config(self):
        return APIKeyConfig(
            key_length=32,
            key_prefix="test_",
            default_expiry_days=30,
            enable_key_rotation=True,
            max_keys_per_user=5,
        )

    @pytest.fixture
    def adapter(self, config):
        return APIKeyAdapter(config)

    def test_init(self, adapter, config):
        assert adapter._config == config
        assert adapter._api_keys != {}  # Should have demo keys
        assert adapter._user_keys != {}

    @pytest.mark.asyncio
    async def test_create_api_key(self, adapter):
        user_id = "user123"
        key = await adapter.create_api_key(user_id, key_name="Test Key")

        assert key.startswith(adapter._config.key_prefix)
        assert key in adapter._api_keys
        assert user_id in adapter._user_keys
        assert key in adapter._user_keys[user_id]

        key_data = adapter._api_keys[key]
        assert key_data["user_id"] == user_id
        assert key_data["key_name"] == "Test Key"
        assert key_data["is_active"] is True

    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter):
        user_id = "user123"
        key = await adapter.create_api_key(user_id)

        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": key}
        )

        result = await adapter.authenticate(credentials)

        assert result.success is True
        assert result.user.user_id == user_id
        assert result.method_used == AuthenticationMethod.API_KEY

        # Check usage count updated
        key_data = adapter._api_keys[key]
        assert key_data["usage_count"] == 1
        assert key_data["last_used"] is not None

    @pytest.mark.asyncio
    async def test_authenticate_failure_invalid_key(self, adapter):
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY,
            credentials={"api_key": "invalid_key"},  # pragma: allowlist secret
        )

        result = await adapter.authenticate(credentials)

        assert result.success is False
        assert result.error_code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_authenticate_failure_expired_key(self, adapter):
        user_id = "user123"
        # Create expired key
        expired_at = datetime.now(timezone.utc) - timedelta(days=1)
        key = await adapter.create_api_key(user_id, expires_at=expired_at)

        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": key}
        )

        result = await adapter.authenticate(credentials)

        assert result.success is False
        assert result.error_code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, adapter):
        user_id = "user123"
        key = await adapter.create_api_key(user_id)

        # Revoke
        success = await adapter.revoke_api_key(key)
        assert success is True

        # Try to authenticate
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": key}
        )

        result = await adapter.authenticate(credentials)

        assert result.success is False
        assert result.error_code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_validate_credentials(self, adapter):
        valid_key = "test_" + "a" * 32
        invalid_prefix = "wrong_" + "a" * 32
        short_key = "test_short"

        creds_valid = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": valid_key}
        )
        assert await adapter.validate_credentials(creds_valid) is True

        creds_invalid_prefix = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": invalid_prefix}
        )
        assert await adapter.validate_credentials(creds_invalid_prefix) is False

        creds_short = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": short_key}
        )
        assert await adapter.validate_credentials(creds_short) is False

    @pytest.mark.asyncio
    async def test_refresh_authentication(self, adapter):
        user = AuthenticatedUser(
            user_id="user123",
            username="testuser",
            email="test@example.com",
            roles=set(),
            permissions=set(),
            auth_method="api_key",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
        )

        result = await adapter.refresh_authentication(user)

        assert result.success is True
        assert result.user.expires_at > user.expires_at
