"""
SMS MFA adapter implementation (stub).

This provides a basic implementation for SMS-based MFA.
In production, integrate with actual SMS providers like Twilio, AWS SNS, etc.
"""

import re
from dataclasses import dataclass
from typing import Any

from ....application.ports_out.mfa_provider import (
    AuthenticationContext,
    MFAProviderError,
    SMSProvider,
)
from ....domain.models.mfa import (
    MFAChallenge,
    MFADevice,
    MFADeviceType,
    MFAMethod,
    MFAVerification,
    MFAVerificationResponse,
    MFAVerificationResult,
    generate_challenge_code,
)


@dataclass
class SMSMFAConfig:
    """Configuration for SMS MFA provider."""

    provider_name: str = "stub_sms"
    code_length: int = 6
    code_expiry_minutes: int = 5
    max_devices_per_user: int = 3
    phone_number_pattern: str = r"^\+[1-9]\d{1,14}$"  # E.164 format


class SMSMFAAdapter(SMSProvider):
    """
    SMS MFA adapter (stub implementation).

    This is a basic implementation for demonstration purposes.
    In production, replace with actual SMS service integration.
    """

    def __init__(self, config: SMSMFAConfig):
        """Initialize SMS MFA adapter."""
        self._config = config

        # In-memory storage (use proper persistence in production)
        self._devices: dict[str, MFADevice] = {}
        self._challenges: dict[str, MFAChallenge] = {}
        self._sent_codes: dict[str, str] = {}  # challenge_id -> code

    async def send_sms_code(
        self, phone_number: str, code: str, context: AuthenticationContext | None = None
    ) -> bool:
        """Send SMS code (stub - logs instead of sending)."""
        print(f"[SMS STUB] Sending code {code} to {phone_number}")
        # In production, integrate with SMS service here
        return True

    async def validate_phone_number(self, phone_number: str) -> bool:
        """Validate phone number format."""
        return bool(re.match(self._config.phone_number_pattern, phone_number))

    async def create_challenge(
        self,
        user_id: str,
        method: MFAMethod,
        device_id: str | None = None,
        context: AuthenticationContext | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MFAChallenge:
        """Create SMS challenge."""
        if method != MFAMethod.SMS:
            raise MFAProviderError(f"SMS provider does not support method: {method}")

        # Generate challenge code
        code = generate_challenge_code(self._config.code_length)

        # Create challenge
        challenge = MFAChallenge.create_new(
            user_id=user_id,
            method=method,
            expires_in_minutes=self._config.code_expiry_minutes,
            challenge_data={"device_id": device_id} if device_id else {},
            metadata=metadata or {},
        )

        # Store challenge and code
        self._challenges[challenge.challenge_id] = challenge
        self._sent_codes[challenge.challenge_id] = code

        # Send SMS (in stub mode, just log)
        if device_id:
            device = await self.get_device(device_id)
            phone_number = device.device_data.get("phone_number", "unknown")
            await self.send_sms_code(phone_number, code, context)

        return challenge

    async def verify_challenge(
        self, verification: MFAVerification, context: AuthenticationContext | None = None
    ) -> MFAVerificationResponse:
        """Verify SMS challenge (basic stub implementation)."""
        challenge = await self.get_challenge(verification.challenge_id)

        if not challenge.can_attempt():
            return MFAVerificationResponse.failure_response(
                challenge_id=verification.challenge_id,
                result=MFAVerificationResult.EXPIRED,
                error_message="Challenge expired or too many attempts",
            )

        expected_code = self._sent_codes.get(verification.challenge_id)
        if expected_code and verification.verification_code == expected_code:
            verified_challenge = challenge.mark_verified()
            self._challenges[challenge.challenge_id] = verified_challenge

            return MFAVerificationResponse.success_response(
                challenge_id=verification.challenge_id, metadata={"method": "sms"}
            )

        failed_challenge = challenge.increment_attempt()
        self._challenges[challenge.challenge_id] = failed_challenge

        return MFAVerificationResponse.failure_response(
            challenge_id=verification.challenge_id,
            result=MFAVerificationResult.INVALID_CODE,
            error_message="Invalid SMS code",
        )

    # Implement other required methods with basic functionality
    async def register_device(
        self,
        user_id: str,
        device_type: MFADeviceType,
        device_name: str,
        device_data: dict[str, Any],
        context: AuthenticationContext | None = None,
    ) -> MFADevice:
        """Register SMS device (stub)."""
        device = MFADevice.create_new(user_id, device_type, device_name, device_data)
        self._devices[device.device_id] = device
        return device

    async def verify_device(
        self, device_id: str, verification_code: str, context: AuthenticationContext | None = None
    ) -> MFADevice:
        """Verify SMS device (stub)."""
        device = self._devices[device_id]
        return device.mark_verified()

    async def get_user_devices(
        self, user_id: str, include_inactive: bool = False
    ) -> list[MFADevice]:
        """Get user SMS devices (stub)."""
        return [d for d in self._devices.values() if d.user_id == user_id]

    async def get_device(self, device_id: str) -> MFADevice:
        """Get SMS device (stub)."""
        return self._devices[device_id]

    async def update_device(
        self,
        device_id: str,
        device_name: str | None = None,
        status: str | None = None,
        context: AuthenticationContext | None = None,
    ) -> MFADevice:
        """Update SMS device (stub)."""
        return self._devices[device_id]

    async def revoke_device(
        self, device_id: str, context: AuthenticationContext | None = None
    ) -> bool:
        """Revoke SMS device (stub)."""
        if device_id in self._devices:
            device = self._devices[device_id]
            self._devices[device_id] = device.mark_revoked()
            return True
        return False

    async def generate_backup_codes(
        self, user_id: str, count: int = 8, context: AuthenticationContext | None = None
    ) -> list[str]:
        """Generate backup codes (stub)."""
        return [f"SMS-BACKUP-{i:04d}" for i in range(count)]

    async def verify_backup_code(
        self, user_id: str, backup_code: str, context: AuthenticationContext | None = None
    ) -> bool:
        """Verify backup code (stub)."""
        return backup_code.startswith("SMS-BACKUP-")

    async def get_challenge(self, challenge_id: str) -> MFAChallenge:
        """Get challenge (stub)."""
        return self._challenges[challenge_id]

    async def cleanup_expired_challenges(self) -> int:
        """Cleanup expired challenges (stub)."""
        return 0

    def supports_method(self, method: MFAMethod) -> bool:
        """Check if SMS method is supported."""
        return method == MFAMethod.SMS

    @property
    def supported_methods(self) -> set[MFAMethod]:
        """Get supported methods."""
        return {MFAMethod.SMS}

    @property
    def supported_device_types(self) -> set[MFADeviceType]:
        """Get supported device types."""
        return {MFADeviceType.SMS_PHONE}
