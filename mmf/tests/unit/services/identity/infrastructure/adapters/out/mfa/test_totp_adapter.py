import base64
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mmf.services.identity.application.ports_out.mfa_provider import (
    MFAChallengeNotFoundError,
    MFADeviceLimitExceededError,
    MFADeviceNotFoundError,
    MFAProviderError,
)
from mmf.services.identity.domain.models.mfa import (
    MFAChallenge,
    MFAChallengeStatus,
    MFADevice,
    MFADeviceStatus,
    MFADeviceType,
    MFAMethod,
    MFAVerification,
    MFAVerificationResponse,
    MFAVerificationResult,
)
from mmf.services.identity.infrastructure.adapters.out.mfa.totp_adapter import (
    TOTPAdapter,
    TOTPConfig,
)


@pytest.fixture
def totp_config():
    return TOTPConfig(
        issuer="Test Issuer",
        period=30,
        digits=6,
        algorithm="SHA1",
        window=1,
        max_devices_per_user=2,
        challenge_expiry_minutes=5,
        rate_limit_window=60,
        max_attempts_per_window=3,
    )


@pytest.fixture
def adapter(totp_config):
    return TOTPAdapter(totp_config)


@pytest.fixture
def sample_secret():
    # "TestSecret" in base32
    return "KRSXG5CTMVRXEZLU"


@pytest.fixture
def mock_context():
    return MagicMock()


class TestTOTPAdapter:
    def test_init(self, totp_config):
        adapter = TOTPAdapter(totp_config)
        assert adapter._config == totp_config
        assert adapter.supported_methods == {MFAMethod.TOTP}
        assert adapter.supported_device_types == {MFADeviceType.TOTP_APP}

    def test_init_invalid_algorithm(self):
        config = TOTPConfig(algorithm="INVALID")
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            TOTPAdapter(config)

    @pytest.mark.asyncio
    async def test_create_challenge_success(self, adapter):
        challenge = await adapter.create_challenge(user_id="user123", method=MFAMethod.TOTP)

        assert challenge.user_id == "user123"
        assert challenge.method == MFAMethod.TOTP
        assert challenge.challenge_id in adapter._challenges

    @pytest.mark.asyncio
    async def test_create_challenge_invalid_method(self, adapter):
        with pytest.raises(MFAProviderError, match="does not support method"):
            await adapter.create_challenge(user_id="user123", method=MFAMethod.SMS)

    @pytest.mark.asyncio
    async def test_register_device_success(self, adapter, sample_secret):
        device = await adapter.register_device(
            user_id="user123",
            device_type=MFADeviceType.TOTP_APP,
            device_name="My Phone",
            device_data={"secret": sample_secret},
        )

        assert device.user_id == "user123"
        assert device.device_name == "My Phone"
        assert device.device_data["secret"] == sample_secret
        assert device.device_id in adapter._devices

    @pytest.mark.asyncio
    async def test_register_device_limit_exceeded(self, adapter, sample_secret):
        # Register max devices (2)
        await adapter.register_device(
            "user123", MFADeviceType.TOTP_APP, "Device 1", {"secret": sample_secret}
        )
        await adapter.register_device(
            "user123", MFADeviceType.TOTP_APP, "Device 2", {"secret": sample_secret}
        )

        # Try to register 3rd
        with pytest.raises(MFADeviceLimitExceededError):
            await adapter.register_device(
                "user123", MFADeviceType.TOTP_APP, "Device 3", {"secret": sample_secret}
            )

    @pytest.mark.asyncio
    async def test_verify_challenge_success(self, adapter, sample_secret):
        # Register device
        device = await adapter.register_device(
            "user123", MFADeviceType.TOTP_APP, "My Phone", {"secret": sample_secret}
        )
        # Manually activate device for testing
        verified_device = device._replace(
            status=MFADeviceStatus.ACTIVE, verified_at=datetime.now(timezone.utc)
        )
        adapter._devices[device.device_id] = verified_device

        # Create challenge
        challenge = await adapter.create_challenge(
            "user123", MFAMethod.TOTP, device_id=device.device_id
        )

        # Generate valid code
        # We need to mock time to ensure the code matches
        with patch("time.time", return_value=1000000):
            # Calculate expected code for timestamp 1000000
            # 1000000 // 30 = 33333
            # We can use the internal helper to generate the code
            valid_code = adapter._generate_totp_code(sample_secret, 33333)

            verification = MFAVerification(
                challenge_id=challenge.challenge_id,
                verification_code=valid_code,
                device_id=device.device_id,
            )

            response = await adapter.verify_challenge(verification)

            assert response.success is True
            assert response.metadata["method"] == "totp"

        # Verify challenge is marked verified
        stored_challenge = await adapter.get_challenge(challenge.challenge_id)
        assert stored_challenge.status == MFAChallengeStatus.VERIFIED

    @pytest.mark.asyncio
    async def test_verify_challenge_invalid_code(self, adapter, sample_secret):
        # Register device
        device = await adapter.register_device(
            "user123", MFADeviceType.TOTP_APP, "My Phone", {"secret": sample_secret}
        )
        # Manually activate device for testing
        verified_device = device._replace(
            status=MFADeviceStatus.ACTIVE, verified_at=datetime.now(timezone.utc)
        )
        adapter._devices[device.device_id] = verified_device

        # Create challenge
        challenge = await adapter.create_challenge(
            "user123", MFAMethod.TOTP, device_id=device.device_id
        )

        verification = MFAVerification(
            challenge_id=challenge.challenge_id,
            verification_code="000000",  # Invalid code
            device_id=device.device_id,
        )

        response = await adapter.verify_challenge(verification)

        assert response.success is False
        assert response.result == MFAVerificationResult.INVALID_CODE

        # Verify attempt count incremented
        stored_challenge = await adapter.get_challenge(challenge.challenge_id)
        assert stored_challenge.attempt_count == 1

    @pytest.mark.asyncio
    async def test_verify_challenge_expired(self, adapter, sample_secret):
        # Register device
        device = await adapter.register_device(
            "user123", MFADeviceType.TOTP_APP, "My Phone", {"secret": sample_secret}
        )
        # Manually activate device for testing
        verified_device = device._replace(
            status=MFADeviceStatus.ACTIVE, verified_at=datetime.now(timezone.utc)
        )
        adapter._devices[device.device_id] = verified_device

        # Create challenge
        challenge = await adapter.create_challenge(
            "user123", MFAMethod.TOTP, device_id=device.device_id
        )

        # Manually expire it
        expired_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        expired_challenge = challenge._replace(expires_at=expired_at)
        adapter._challenges[challenge.challenge_id] = expired_challenge

        verification = MFAVerification(
            challenge_id=challenge.challenge_id,
            verification_code="123456",
            device_id=device.device_id,
        )

        response = await adapter.verify_challenge(verification)

        assert response.success is False
        assert response.result == MFAVerificationResult.EXPIRED

    @pytest.mark.asyncio
    async def test_verify_challenge_backup_code(self, adapter):
        # Generate backup codes
        codes = await adapter.generate_backup_codes("user123", count=1)
        backup_code = codes[0]

        # Create challenge
        challenge = await adapter.create_challenge("user123", MFAMethod.TOTP)

        verification = MFAVerification(challenge_id=challenge.challenge_id, backup_code=backup_code)

        response = await adapter.verify_challenge(verification)

        assert response.success is True
        assert response.metadata["method"] == "backup_code"

        # Verify code is consumed
        assert await adapter.verify_backup_code("user123", backup_code) is False

    @pytest.mark.asyncio
    async def test_verify_challenge_rate_limit(self, adapter, sample_secret):
        # Register device
        device = await adapter.register_device(
            "user123", MFADeviceType.TOTP_APP, "My Phone", {"secret": sample_secret}
        )
        # Manually activate device for testing
        verified_device = device._replace(
            status=MFADeviceStatus.ACTIVE, verified_at=datetime.now(timezone.utc)
        )
        adapter._devices[device.device_id] = verified_device

        challenge = await adapter.create_challenge(
            "user123", MFAMethod.TOTP, device_id=device.device_id
        )

        verification = MFAVerification(
            challenge_id=challenge.challenge_id,
            verification_code="000000",
            device_id=device.device_id,
        )

        # Fail 3 times (max attempts per window is 3)
        await adapter.verify_challenge(verification)
        await adapter.verify_challenge(verification)
        await adapter.verify_challenge(verification)

        # 4th attempt should be rate limited
        response = await adapter.verify_challenge(verification)

        assert response.success is False
        assert response.result == MFAVerificationResult.TOO_MANY_ATTEMPTS

    @pytest.mark.asyncio
    async def test_generate_qr_code_url(self, adapter, sample_secret):
        url = await adapter.generate_qr_code_url(sample_secret, "user@example.com")

        assert "otpauth://totp/" in url
        assert "secret=" + sample_secret in url
        assert "issuer=Test%20Issuer" in url

    @pytest.mark.asyncio
    async def test_verify_totp_code_window(self, adapter, sample_secret):
        # Mock time to 1000000
        with patch("time.time", return_value=1000000):
            # Current window code
            code_now = adapter._generate_totp_code(sample_secret, 33333)
            assert await adapter.verify_totp_code(sample_secret, code_now) is True

            # Previous window code (window=1)
            code_prev = adapter._generate_totp_code(sample_secret, 33332)
            assert await adapter.verify_totp_code(sample_secret, code_prev) is True

            # Next window code (window=1)
            code_next = adapter._generate_totp_code(sample_secret, 33334)
            assert await adapter.verify_totp_code(sample_secret, code_next) is True

            # Outside window code
            code_far = adapter._generate_totp_code(sample_secret, 33335)
            assert await adapter.verify_totp_code(sample_secret, code_far) is False

    @pytest.mark.asyncio
    async def test_replay_attack_prevention(self, adapter, sample_secret):
        device = await adapter.register_device(
            "user123", MFADeviceType.TOTP_APP, "My Phone", {"secret": sample_secret}
        )
        # Manually activate device for testing
        verified_device = device._replace(
            status=MFADeviceStatus.ACTIVE, verified_at=datetime.now(timezone.utc)
        )
        adapter._devices[device.device_id] = verified_device

        challenge = await adapter.create_challenge(
            "user123", MFAMethod.TOTP, device_id=device.device_id
        )

        with patch("time.time", return_value=1000000):
            valid_code = adapter._generate_totp_code(sample_secret, 33333)

            verification = MFAVerification(
                challenge_id=challenge.challenge_id,
                verification_code=valid_code,
                device_id=device.device_id,
            )

            # First use - success
            response1 = await adapter.verify_challenge(verification)
            assert response1.success is True

            # Second use - failure (replay)
            # We need a new challenge because the previous one is verified
            challenge2 = await adapter.create_challenge(
                "user123", MFAMethod.TOTP, device_id=device.device_id
            )
            verification2 = MFAVerification(
                challenge_id=challenge2.challenge_id,
                verification_code=valid_code,
                device_id=device.device_id,
            )

            response2 = await adapter.verify_challenge(verification2)
            assert response2.success is False
            assert response2.result == MFAVerificationResult.INVALID_CODE
            assert "already been used" in response2.error_message
