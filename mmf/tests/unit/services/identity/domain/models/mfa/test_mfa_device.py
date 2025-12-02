"""
Unit tests for the MFADevice domain model.
"""

from datetime import datetime, timezone

import pytest

from mmf.services.identity.domain.models.mfa.mfa_device import (
    MFADevice,
    MFADeviceStatus,
    MFADeviceType,
)


class TestMFADevice:
    """Test suite for MFADevice domain model."""

    def test_create_new_device(self):
        """Test creating a new device via factory method."""
        device = MFADevice.create_new(
            user_id="user-123",
            device_type=MFADeviceType.TOTP_APP,
            device_name="My Phone",
            device_data={"secret": "ABC"},
            metadata={"os": "iOS"},
        )

        assert device.user_id == "user-123"
        assert device.device_type == MFADeviceType.TOTP_APP
        assert device.device_name == "My Phone"
        assert device.status == MFADeviceStatus.PENDING
        assert device.device_data == {"secret": "ABC"}
        assert device.metadata == {"os": "iOS"}
        assert device.device_id is not None
        assert device.use_count == 0
        assert device.verified_at is None

    def test_validation_empty_device_id(self):
        """Test validation for empty device ID."""
        with pytest.raises(ValueError, match="Device ID cannot be empty"):
            MFADevice(
                device_id="",
                user_id="user",
                device_type=MFADeviceType.TOTP_APP,
                device_name="Phone",
            )

    def test_validation_empty_user_id(self):
        """Test validation for empty user ID."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            MFADevice(
                device_id="id", user_id="", device_type=MFADeviceType.TOTP_APP, device_name="Phone"
            )

    def test_validation_invalid_type(self):
        """Test validation for invalid device type."""
        with pytest.raises(TypeError, match="Device type must be an MFADeviceType enum"):
            MFADevice(
                device_id="id",
                user_id="user",
                device_type="TOTP",  # String instead of Enum
                device_name="Phone",
            )

    def test_validation_invalid_status(self):
        """Test validation for invalid status type."""
        with pytest.raises(TypeError, match="Status must be an MFADeviceStatus enum"):
            MFADevice(
                device_id="id",
                user_id="user",
                device_type=MFADeviceType.TOTP_APP,
                device_name="Phone",
                status="PENDING",  # String instead of Enum
            )

    def test_validation_empty_name(self):
        """Test validation for empty device name."""
        with pytest.raises(ValueError, match="Device name cannot be empty"):
            MFADevice(
                device_id="id", user_id="user", device_type=MFADeviceType.TOTP_APP, device_name=""
            )

    def test_mark_verified(self):
        """Test mark_verified method."""
        device = MFADevice.create_new("user", MFADeviceType.TOTP_APP, "Phone")

        verified_device = device.mark_verified()

        assert verified_device.status == MFADeviceStatus.ACTIVE
        assert verified_device.verified_at is not None
        # Ensure timezone awareness
        assert verified_device.verified_at.tzinfo == timezone.utc

    def test_mark_used(self):
        """Test mark_used method."""
        device = MFADevice.create_new("user", MFADeviceType.TOTP_APP, "Phone")

        used_device = device.mark_used()

        assert used_device.use_count == 1
        assert used_device.last_used_at is not None
        assert used_device.last_used_at.tzinfo == timezone.utc

        # Use again
        used_twice = used_device.mark_used()
        assert used_twice.use_count == 2

    def test_status_transitions(self):
        """Test status transition methods."""
        device = MFADevice.create_new("user", MFADeviceType.TOTP_APP, "Phone")

        assert device.mark_revoked().status == MFADeviceStatus.REVOKED
        assert device.mark_compromised().status == MFADeviceStatus.COMPROMISED

        # Test mark_inactive
        assert device.mark_inactive().status == MFADeviceStatus.INACTIVE

    def test_is_active(self):
        """Test is_active method."""
        device = MFADevice.create_new("user", MFADeviceType.TOTP_APP, "Phone")
        assert device.is_active() is False  # Pending

        active_device = device.mark_verified()
        assert active_device.is_active() is True

        revoked_device = active_device.mark_revoked()
        assert revoked_device.is_active() is False

    def test_immutability(self):
        """Test that the object is immutable."""
        device = MFADevice.create_new("user", MFADeviceType.TOTP_APP, "Phone")
        with pytest.raises(AttributeError):
            device.status = MFADeviceStatus.ACTIVE
