"""
Unit tests for the MFAVerification domain model.
"""

from datetime import datetime, timezone

import pytest

from mmf.services.identity.domain.models.mfa.mfa_verification import MFAVerification


class TestMFAVerification:
    """Test suite for MFAVerification domain model."""

    def test_create_with_verification_code(self):
        """Test creating verification with code."""
        verification = MFAVerification.with_verification_code(
            challenge_id="chal-123",
            device_id="dev-456",
            verification_code="123456",
            metadata={"ip": "1.2.3.4"},
        )

        assert verification.challenge_id == "chal-123"
        assert verification.device_id == "dev-456"
        assert verification.verification_code == "123456"
        assert verification.backup_code is None
        assert verification.metadata == {"ip": "1.2.3.4"}
        assert verification.is_using_device_code() is True
        assert verification.is_using_backup_code() is False

    def test_create_with_backup_code(self):
        """Test creating verification with backup code."""
        verification = MFAVerification.with_backup_code(
            challenge_id="chal-123", backup_code="ABCD-1234", metadata={"ip": "1.2.3.4"}
        )

        assert verification.challenge_id == "chal-123"
        assert verification.device_id is None
        assert verification.verification_code is None
        assert verification.backup_code == "ABCD-1234"
        assert verification.metadata == {"ip": "1.2.3.4"}
        assert verification.is_using_device_code() is False
        assert verification.is_using_backup_code() is True

    def test_validation_empty_challenge_id(self):
        """Test validation for empty challenge ID."""
        with pytest.raises(ValueError, match="Challenge ID cannot be empty"):
            MFAVerification(challenge_id="", device_id="dev", verification_code="123")

    def test_validation_missing_codes(self):
        """Test validation when no code is provided."""
        with pytest.raises(
            ValueError, match="Either verification_code or backup_code must be provided"
        ):
            MFAVerification(challenge_id="chal", device_id="dev")

    def test_validation_both_codes(self):
        """Test validation when both codes are provided."""
        with pytest.raises(
            ValueError, match="Cannot provide both verification_code and backup_code"
        ):
            MFAVerification(
                challenge_id="chal", device_id="dev", verification_code="123", backup_code="ABC"
            )

    def test_validation_missing_device_id(self):
        """Test validation when device_id is missing for verification code."""
        with pytest.raises(ValueError, match="device_id is required when using verification_code"):
            MFAVerification(challenge_id="chal", verification_code="123")

    def test_immutability(self):
        """Test that the object is immutable."""
        verification = MFAVerification.with_verification_code("chal", "dev", "123")
        with pytest.raises(AttributeError):
            verification.verification_code = "456"
