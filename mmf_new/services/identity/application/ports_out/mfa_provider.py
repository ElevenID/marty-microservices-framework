"""
MFA Provider outbound port for multi-factor authentication operations.

This port defines the interface for MFA operations including challenge
creation, verification, device management, and backup codes.
"""

from abc import ABC, abstractmethod
from typing import Any

from ...domain.models.mfa import (
    MFAChallenge,
    MFADevice,
    MFADeviceType,
    MFAMethod,
    MFAVerification,
    MFAVerificationResponse,
)
from ..ports_out.authentication_provider import AuthenticationContext


class MFAProviderError(Exception):
    """Base exception for MFA provider errors."""


class MFADeviceNotFoundError(MFAProviderError):
    """Raised when an MFA device is not found."""


class MFAChallengeNotFoundError(MFAProviderError):
    """Raised when an MFA challenge is not found."""


class MFADeviceLimitExceededError(MFAProviderError):
    """Raised when the user has reached the maximum number of MFA devices."""


class MFAProvider(ABC):
    """
    Abstract base class for MFA providers.

    Defines the interface for multi-factor authentication operations
    including device registration, challenge creation and verification.
    """

    @abstractmethod
    async def create_challenge(
        self,
        user_id: str,
        method: MFAMethod,
        device_id: str | None = None,
        context: AuthenticationContext | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MFAChallenge:
        """
        Create a new MFA challenge.

        Args:
            user_id: ID of the user requesting MFA
            method: MFA method to use for the challenge
            device_id: Optional device ID for device-specific challenges
            context: Authentication context
            metadata: Additional metadata for the challenge

        Returns:
            Created MFA challenge

        Raises:
            MFADeviceNotFoundError: If device_id is provided but device not found
            MFAProviderError: For other MFA-related errors
        """
        pass

    @abstractmethod
    async def verify_challenge(
        self, verification: MFAVerification, context: AuthenticationContext | None = None
    ) -> MFAVerificationResponse:
        """
        Verify an MFA challenge.

        Args:
            verification: MFA verification request
            context: Authentication context

        Returns:
            Verification response with result
        """
        pass

    @abstractmethod
    async def register_device(
        self,
        user_id: str,
        device_type: MFADeviceType,
        device_name: str,
        device_data: dict[str, Any],
        context: AuthenticationContext | None = None,
    ) -> MFADevice:
        """
        Register a new MFA device for a user.

        Args:
            user_id: ID of the user registering the device
            device_type: Type of device being registered
            device_name: User-friendly name for the device
            device_data: Device-specific configuration data
            context: Authentication context

        Returns:
            Registered MFA device (pending verification)

        Raises:
            MFADeviceLimitExceededError: If user has reached device limit
            MFAProviderError: For other registration errors
        """
        pass

    @abstractmethod
    async def verify_device(
        self, device_id: str, verification_code: str, context: AuthenticationContext | None = None
    ) -> MFADevice:
        """
        Verify a pending MFA device.

        Args:
            device_id: ID of the device to verify
            verification_code: Verification code from the device
            context: Authentication context

        Returns:
            Verified and activated MFA device

        Raises:
            MFADeviceNotFoundError: If device not found
            MFAProviderError: For verification errors
        """
        pass

    @abstractmethod
    async def get_user_devices(
        self, user_id: str, include_inactive: bool = False
    ) -> list[MFADevice]:
        """
        Get all MFA devices for a user.

        Args:
            user_id: ID of the user
            include_inactive: Whether to include inactive devices

        Returns:
            List of user's MFA devices
        """
        pass

    @abstractmethod
    async def get_device(self, device_id: str) -> MFADevice:
        """
        Get a specific MFA device.

        Args:
            device_id: ID of the device

        Returns:
            MFA device

        Raises:
            MFADeviceNotFoundError: If device not found
        """
        pass

    @abstractmethod
    async def update_device(
        self,
        device_id: str,
        device_name: str | None = None,
        status: str | None = None,
        context: AuthenticationContext | None = None,
    ) -> MFADevice:
        """
        Update an MFA device.

        Args:
            device_id: ID of the device to update
            device_name: New device name (optional)
            status: New device status (optional)
            context: Authentication context

        Returns:
            Updated MFA device

        Raises:
            MFADeviceNotFoundError: If device not found
        """
        pass

    @abstractmethod
    async def revoke_device(
        self, device_id: str, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Revoke an MFA device.

        Args:
            device_id: ID of the device to revoke
            context: Authentication context

        Returns:
            True if device was revoked successfully

        Raises:
            MFADeviceNotFoundError: If device not found
        """
        pass

    @abstractmethod
    async def generate_backup_codes(
        self, user_id: str, count: int = 8, context: AuthenticationContext | None = None
    ) -> list[str]:
        """
        Generate backup recovery codes for a user.

        Args:
            user_id: ID of the user
            count: Number of backup codes to generate
            context: Authentication context

        Returns:
            List of backup codes
        """
        pass

    @abstractmethod
    async def verify_backup_code(
        self, user_id: str, backup_code: str, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Verify and consume a backup code.

        Args:
            user_id: ID of the user
            backup_code: Backup code to verify
            context: Authentication context

        Returns:
            True if backup code is valid and was consumed
        """
        pass

    @abstractmethod
    async def get_challenge(self, challenge_id: str) -> MFAChallenge:
        """
        Get a specific MFA challenge.

        Args:
            challenge_id: ID of the challenge

        Returns:
            MFA challenge

        Raises:
            MFAChallengeNotFoundError: If challenge not found
        """
        pass

    @abstractmethod
    async def cleanup_expired_challenges(self) -> int:
        """
        Clean up expired MFA challenges.

        Returns:
            Number of challenges cleaned up
        """
        pass

    @abstractmethod
    def supports_method(self, method: MFAMethod) -> bool:
        """
        Check if the provider supports a specific MFA method.

        Args:
            method: MFA method to check

        Returns:
            True if method is supported
        """
        pass

    @property
    @abstractmethod
    def supported_methods(self) -> set[MFAMethod]:
        """Get the set of supported MFA methods."""
        pass

    @property
    @abstractmethod
    def supported_device_types(self) -> set[MFADeviceType]:
        """Get the set of supported MFA device types."""
        pass


class TOTPProvider(MFAProvider):
    """
    Abstract TOTP (Time-based One-Time Password) provider.

    Specializes MFAProvider for TOTP-specific operations.
    """

    @abstractmethod
    async def generate_totp_secret(self, user_id: str) -> str:
        """
        Generate a TOTP secret for a user.

        Args:
            user_id: ID of the user

        Returns:
            Base32-encoded TOTP secret
        """
        pass

    @abstractmethod
    async def generate_qr_code_url(
        self, secret: str, user_identifier: str, issuer: str = "MMF Identity Service"
    ) -> str:
        """
        Generate QR code URL for TOTP setup.

        Args:
            secret: TOTP secret
            user_identifier: User identifier (email or username)
            issuer: Service name

        Returns:
            QR code URL for authenticator apps
        """
        pass

    @abstractmethod
    async def verify_totp_code(self, secret: str, code: str, window: int = 1) -> bool:
        """
        Verify a TOTP code.

        Args:
            secret: TOTP secret
            code: Code to verify
            window: Time window for verification (default 1 = ±30 seconds)

        Returns:
            True if code is valid
        """
        pass


class SMSProvider(MFAProvider):
    """
    Abstract SMS provider for SMS-based MFA.

    Specializes MFAProvider for SMS-specific operations.
    """

    @abstractmethod
    async def send_sms_code(
        self, phone_number: str, code: str, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Send an SMS verification code.

        Args:
            phone_number: Phone number to send to
            code: Verification code
            context: Authentication context

        Returns:
            True if SMS was sent successfully
        """
        pass

    @abstractmethod
    async def validate_phone_number(self, phone_number: str) -> bool:
        """
        Validate a phone number format.

        Args:
            phone_number: Phone number to validate

        Returns:
            True if phone number is valid
        """
        pass


class EmailMFAProvider(MFAProvider):
    """
    Abstract email provider for email-based MFA.

    Specializes MFAProvider for email-specific operations.
    """

    @abstractmethod
    async def send_email_code(
        self, email_address: str, code: str, context: AuthenticationContext | None = None
    ) -> bool:
        """
        Send an email verification code.

        Args:
            email_address: Email address to send to
            code: Verification code
            context: Authentication context

        Returns:
            True if email was sent successfully
        """
        pass

    @abstractmethod
    async def validate_email_address(self, email_address: str) -> bool:
        """
        Validate an email address format.

        Args:
            email_address: Email address to validate

        Returns:
            True if email address is valid
        """
        pass
