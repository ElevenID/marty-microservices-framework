"""
MFA Device domain model.

This module contains the domain model for MFA devices that users
register to enable multi-factor authentication.
"""

from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from mmf.core.domain.entity import ValueObject


class MFADeviceType(Enum):
    """Types of MFA devices."""

    TOTP_APP = "totp_app"  # Authenticator app (Google Auth, Authy, etc.)
    SMS_PHONE = "sms_phone"  # SMS-capable phone number
    EMAIL = "email"  # Email address
    HARDWARE_TOKEN = "hardware"  # Hardware security key
    VOICE_PHONE = "voice_phone"  # Voice-call capable phone
    PUSH_DEVICE = "push_device"  # Push notification device


class MFADeviceStatus(Enum):
    """Status of an MFA device."""

    PENDING = "pending"  # Device registered but not yet verified
    ACTIVE = "active"  # Device verified and active
    INACTIVE = "inactive"  # Device temporarily disabled
    COMPROMISED = "compromised"  # Device suspected of being compromised
    REVOKED = "revoked"  # Device permanently revoked


@dataclass(frozen=True)
class MFADevice(ValueObject):
    """
    Domain model representing an MFA device.

    An MFA device represents a method/device that a user has registered
    for multi-factor authentication.
    """

    device_id: str
    user_id: str
    device_type: MFADeviceType
    device_name: str
    status: MFADeviceStatus = MFADeviceStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: datetime | None = None
    verified_at: datetime | None = None
    use_count: int = 0
    device_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the MFA device data."""
        # Validate required fields
        if not isinstance(self.device_id, str) or not self.device_id.strip():
            raise ValueError("Device ID cannot be empty")

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("User ID cannot be empty")

        if not isinstance(self.device_type, MFADeviceType):
            raise TypeError("Device type must be an MFADeviceType enum")

        if not isinstance(self.status, MFADeviceStatus):
            raise TypeError("Status must be an MFADeviceStatus enum")

        if not isinstance(self.device_name, str) or not self.device_name.strip():
            raise ValueError("Device name cannot be empty")

        # Ensure timezone awareness for datetime fields
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.last_used_at and self.last_used_at.tzinfo is None:
            object.__setattr__(self, "last_used_at", self.last_used_at.replace(tzinfo=timezone.utc))

        if self.verified_at and self.verified_at.tzinfo is None:
            object.__setattr__(self, "verified_at", self.verified_at.replace(tzinfo=timezone.utc))

        # Validate use count
        if self.use_count < 0:
            raise ValueError("Use count cannot be negative")

    @classmethod
    def create_new(
        cls,
        user_id: str,
        device_type: MFADeviceType,
        device_name: str,
        device_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MFADevice:
        """Create a new MFA device."""
        device_id = f"mfa_device_{uuid4().hex[:16]}"

        return cls(
            device_id=device_id,
            user_id=user_id,
            device_type=device_type,
            device_name=device_name,
            device_data=device_data or {},
            metadata=metadata or {},
        )

    def is_active(self) -> bool:
        """Check if the device is active and can be used."""
        return self.status == MFADeviceStatus.ACTIVE

    def is_verified(self) -> bool:
        """Check if the device has been verified."""
        return self.verified_at is not None

    def can_be_used(self) -> bool:
        """Check if the device can be used for authentication."""
        return self.status == MFADeviceStatus.ACTIVE and self.is_verified()

    def mark_verified(self) -> MFADevice:
        """Create a new device marked as verified and active."""
        now = datetime.now(timezone.utc)
        return self._replace(status=MFADeviceStatus.ACTIVE, verified_at=now)

    def mark_used(self) -> MFADevice:
        """Create a new device with updated last used timestamp."""
        now = datetime.now(timezone.utc)
        return self._replace(last_used_at=now, use_count=self.use_count + 1)

    def mark_inactive(self) -> MFADevice:
        """Create a new device marked as inactive."""
        return self._replace(status=MFADeviceStatus.INACTIVE)

    def mark_active(self) -> MFADevice:
        """Create a new device marked as active (if verified)."""
        if not self.is_verified():
            raise ValueError("Cannot activate unverified device")
        return self._replace(status=MFADeviceStatus.ACTIVE)

    def mark_compromised(self) -> MFADevice:
        """Create a new device marked as compromised."""
        return self._replace(status=MFADeviceStatus.COMPROMISED)

    def mark_revoked(self) -> MFADevice:
        """Create a new device marked as revoked."""
        return self._replace(status=MFADeviceStatus.REVOKED)

    def with_data(self, **data: Any) -> MFADevice:
        """Create a new device with updated device data."""
        new_data = {**self.device_data, **data}
        return self._replace(device_data=new_data)

    def with_metadata(self, **metadata: Any) -> MFADevice:
        """Create a new device with updated metadata."""
        new_metadata = {**self.metadata, **metadata}
        return self._replace(metadata=new_metadata)

    def update_name(self, new_name: str) -> MFADevice:
        """Create a new device with updated name."""
        if not new_name or not new_name.strip():
            raise ValueError("Device name cannot be empty")
        return self._replace(device_name=new_name.strip())

    def _replace(self, **changes) -> MFADevice:
        """Create a new device with the specified changes."""
        kwargs = {
            "device_id": self.device_id,
            "user_id": self.user_id,
            "device_type": self.device_type,
            "device_name": self.device_name,
            "status": self.status,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "verified_at": self.verified_at,
            "use_count": self.use_count,
            "device_data": self.device_data,
            "metadata": self.metadata,
        }
        kwargs.update(changes)
        return MFADevice(**kwargs)


def generate_device_secret(length: int = 32) -> str:
    """Generate a secure random secret for device registration."""
    # Use URL-safe base64 characters for secrets
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"  # pragma: allowlist secret
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_totp_secret() -> str:
    """Generate a TOTP secret in base32 format."""
    # Generate 20 random bytes (160 bits) for TOTP secret
    secret_bytes = secrets.token_bytes(20)
    # Convert to base32 (RFC 3548)
    return base64.b32encode(secret_bytes).decode("ascii")
