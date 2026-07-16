"""
Unit tests for the MFAChallenge domain model.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mmf.services.identity.domain.models.mfa.mfa_challenge import (
    MFAChallenge,
    MFAChallengeStatus,
    MFAMethod,
)


class TestMFAChallenge:
    """Test suite for MFAChallenge domain model."""

    def test_create_new_challenge(self):
        """Test creating a new challenge via factory method."""
        challenge = MFAChallenge.create_new(
            user_id="user-123",
            method=MFAMethod.TOTP,
            expires_in_minutes=10,
            max_attempts=5,
            challenge_data={"qr_code": "data"},
            metadata={"ip": "127.0.0.1"},
        )

        assert challenge.user_id == "user-123"
        assert challenge.method == MFAMethod.TOTP
        assert challenge.status == MFAChallengeStatus.PENDING
        assert challenge.attempt_count == 0
        assert challenge.max_attempts == 5
        assert challenge.challenge_data == {"qr_code": "data"}
        assert challenge.metadata == {"ip": "127.0.0.1"}
        assert challenge.challenge_id.startswith("mfa_")

        # Check expiration
        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(minutes=10)
        # Allow small time difference
        assert abs((challenge.expires_at - expected_expiry).total_seconds()) < 5

    def test_validation_empty_challenge_id(self):
        """Test validation for empty challenge ID."""
        with pytest.raises(ValueError, match="Challenge ID cannot be empty"):
            MFAChallenge(challenge_id="", user_id="user-123", method=MFAMethod.TOTP)

    def test_validation_empty_user_id(self):
        """Test validation for empty user ID."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            MFAChallenge(challenge_id="id", user_id="", method=MFAMethod.TOTP)

    def test_validation_invalid_method(self):
        """Test validation for invalid method type."""
        with pytest.raises(TypeError, match="Method must be an MFAMethod enum"):
            MFAChallenge(
                challenge_id="id",
                user_id="user",
                method="TOTP",  # String instead of Enum
            )

    def test_validation_invalid_status(self):
        """Test validation for invalid status type."""
        with pytest.raises(TypeError, match="Status must be an MFAChallengeStatus enum"):
            MFAChallenge(
                challenge_id="id",
                user_id="user",
                method=MFAMethod.TOTP,
                status="PENDING",  # String instead of Enum
            )

    def test_validation_negative_attempts(self):
        """Test validation for negative attempt count."""
        with pytest.raises(ValueError, match="Attempt count cannot be negative"):
            MFAChallenge(challenge_id="id", user_id="user", method=MFAMethod.TOTP, attempt_count=-1)

    def test_is_expired(self):
        """Test is_expired method."""
        now = datetime.now(timezone.utc)

        # Future expiry
        challenge = MFAChallenge(
            challenge_id="id",
            user_id="user",
            method=MFAMethod.TOTP,
            expires_at=now + timedelta(minutes=5),
        )
        assert challenge.is_expired() is False

        # Past expiry
        challenge_expired = MFAChallenge(
            challenge_id="id",
            user_id="user",
            method=MFAMethod.TOTP,
            expires_at=now - timedelta(minutes=5),
        )
        assert challenge_expired.is_expired() is True

    def test_can_attempt(self):
        """Test can_attempt method."""
        # Valid case
        challenge = MFAChallenge.create_new("user", MFAMethod.TOTP)
        assert challenge.can_attempt() is True

        # Max attempts reached
        challenge_max = challenge._replace(attempt_count=3, max_attempts=3)
        assert challenge_max.can_attempt() is False

        # Expired
        challenge_expired = challenge._replace(
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        assert challenge_expired.can_attempt() is False

        # Not pending
        challenge_verified = challenge.mark_verified()
        assert challenge_verified.can_attempt() is False

    def test_increment_attempt(self):
        """Test increment_attempt method."""
        challenge = MFAChallenge.create_new("user", MFAMethod.TOTP, max_attempts=3)

        # First attempt
        c1 = challenge.increment_attempt()
        assert c1.attempt_count == 1
        assert c1.status == MFAChallengeStatus.PENDING

        # Second attempt
        c2 = c1.increment_attempt()
        assert c2.attempt_count == 2
        assert c2.status == MFAChallengeStatus.PENDING

        # Third attempt (max reached)
        c3 = c2.increment_attempt()
        assert c3.attempt_count == 3
        assert c3.status == MFAChallengeStatus.FAILED

    def test_state_transitions(self):
        """Test state transition methods."""
        challenge = MFAChallenge.create_new("user", MFAMethod.TOTP)

        assert challenge.mark_verified().status == MFAChallengeStatus.VERIFIED
        assert challenge.mark_failed().status == MFAChallengeStatus.FAILED
        assert challenge.mark_expired().status == MFAChallengeStatus.EXPIRED
        assert challenge.mark_cancelled().status == MFAChallengeStatus.CANCELLED

    def test_immutability(self):
        """Test that the object is immutable."""
        challenge = MFAChallenge.create_new("user", MFAMethod.TOTP)
        with pytest.raises(AttributeError):
            challenge.status = MFAChallengeStatus.VERIFIED
