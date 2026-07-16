"""
Email MFA adapter implementation (stub).

This provides a basic implementation for email-based MFA.
In production, integrate with actual email services.
"""

import re
from dataclasses import dataclass
from typing import Any

from mmf.services.identity.application.ports_out.mfa_provider import (
    AuthenticationContext,
    EmailMFAProvider,
    MFAProviderError,
)
from mmf.services.identity.domain.models.mfa import (
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
class EmailMFAConfig:
    """Configuration for Email MFA provider."""

    provider_name: str = "stub_email"
    code_length: int = 8
    code_expiry_minutes: int = 10
    max_devices_per_user: int = 3
    email_pattern: str = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


class EmailMFAAdapter(EmailMFAProvider):
    """
    Email MFA adapter (stub implementation).

    This is a basic implementation for demonstration purposes.
    In production, replace with actual email service integration.
    """

    def __init__(self, config: EmailMFAConfig):
        """Initialize Email MFA adapter."""
        self._config = config

        # In-memory storage (use proper persistence in production)
        self._devices: dict[str, MFADevice] = {}
        self._challenges: dict[str, MFAChallenge] = {}
        self._sent_codes: dict[str, str] = {}  # challenge_id -> code

    async def send_email_code(
        self, email_address: str, code: str, context: AuthenticationContext | None = None
    ) -> bool:
        """Send email code (stub - logs instead of sending)."""
        print(f"[EMAIL STUB] Sending code {code} to {email_address}")
        # In production, integrate with email service here
        return True

    async def validate_email_address(self, email_address: str) -> bool:
        """Validate email address format."""
        return bool(re.match(self._config.email_pattern, email_address))

    async def create_challenge(
        self,
        user_id: str,
        method: MFAMethod,
        device_id: str | None = None,
        context: AuthenticationContext | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MFAChallenge:
        """Create email challenge."""
        if method != MFAMethod.EMAIL:
            raise MFAProviderError(f"Email provider does not support method: {method}")

        # Generate challenge code (alphanumeric for email)
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

        # Send email (in stub mode, just log)
        if device_id:
            device = await self.get_device(device_id)
            email_address = device.device_data.get("email_address", "unknown")
            await self.send_email_code(email_address, code, context)

        return challenge

    async def verify_challenge(
        self, verification: MFAVerification, context: AuthenticationContext | None = None
    ) -> MFAVerificationResponse:
        """Verify email challenge (basic stub implementation)."""
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
                challenge_id=verification.challenge_id, metadata={"method": "email"}
            )

        failed_challenge = challenge.increment_attempt()
        self._challenges[challenge.challenge_id] = failed_challenge

        return MFAVerificationResponse.failure_response(
            challenge_id=verification.challenge_id,
            result=MFAVerificationResult.INVALID_CODE,
            error_message="Invalid email code",
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
        """Register email device (stub)."""
        device = MFADevice.create_new(user_id, device_type, device_name, device_data)
        self._devices[device.device_id] = device
        return device

    async def verify_device(
        self, device_id: str, verification_code: str, context: AuthenticationContext | None = None
    ) -> MFADevice:
        """Verify email device (stub)."""
        device = self._devices[device_id]
        return device.mark_verified()

    async def get_user_devices(
        self, user_id: str, include_inactive: bool = False
    ) -> list[MFADevice]:
        """Get user email devices (stub)."""
        return [d for d in self._devices.values() if d.user_id == user_id]

    async def get_device(self, device_id: str) -> MFADevice:
        """Get email device (stub)."""
        return self._devices[device_id]

    async def update_device(
        self,
        device_id: str,
        device_name: str | None = None,
        status: str | None = None,
        context: AuthenticationContext | None = None,
    ) -> MFADevice:
        """Update email device (stub)."""
        return self._devices[device_id]

    async def revoke_device(
        self, device_id: str, context: AuthenticationContext | None = None
    ) -> bool:
        """Revoke email device (stub)."""
        if device_id in self._devices:
            device = self._devices[device_id]
            self._devices[device_id] = device.mark_revoked()
            return True
        return False

    async def generate_backup_codes(
        self, user_id: str, count: int = 8, context: AuthenticationContext | None = None
    ) -> list[str]:
        """Generate backup codes (stub)."""
        return [f"EMAIL-BACKUP-{i:04d}" for i in range(count)]

    async def verify_backup_code(
        self, user_id: str, backup_code: str, context: AuthenticationContext | None = None
    ) -> bool:
        """Verify backup code (stub)."""
        return backup_code.startswith("EMAIL-BACKUP-")

    async def get_challenge(self, challenge_id: str) -> MFAChallenge:
        """Get challenge (stub)."""
        return self._challenges[challenge_id]

    async def cleanup_expired_challenges(self) -> int:
        """Cleanup expired challenges (stub)."""
        return 0

    def supports_method(self, method: MFAMethod) -> bool:
        """Check if email method is supported."""
        return method == MFAMethod.EMAIL

    @property
    def supported_methods(self) -> set[MFAMethod]:
        """Get supported methods."""
        return {MFAMethod.EMAIL}

    @property
    def supported_device_types(self) -> set[MFADeviceType]:
        """Get supported device types."""
        return {MFADeviceType.EMAIL}
