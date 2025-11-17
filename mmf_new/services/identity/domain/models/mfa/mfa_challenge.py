"""
MFA Challenge domain model.

This module contains the domain model for MFA challenges that represent
a specific authentication challenge sent to a user.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from mmf_new.core.domain.entity import ValueObject


class MFAMethod(Enum):
    """Supported MFA methods."""

    TOTP = "totp"  # Time-based One-Time Password (Google Authenticator, etc.)
    SMS = "sms"  # SMS-based code
    EMAIL = "email"  # Email-based code
    PUSH = "push"  # Push notification
    BACKUP_CODES = "backup"  # Backup recovery codes
    HARDWARE_TOKEN = "hardware"  # Hardware security keys
    VOICE = "voice"  # Voice call verification


class MFAChallengeStatus(Enum):
    """Status of an MFA challenge."""

    PENDING = "pending"  # Challenge created, awaiting response
    VERIFIED = "verified"  # Challenge successfully verified
    FAILED = "failed"  # Challenge verification failed
    EXPIRED = "expired"  # Challenge expired without verification
    CANCELLED = "cancelled"  # Challenge cancelled by user or system


@dataclass(frozen=True)
class MFAChallenge(ValueObject):
    """
    Domain model representing an MFA challenge.

    An MFA challenge is created when additional authentication
    is required and tracks the challenge through its lifecycle.
    """

    challenge_id: str
    user_id: str
    method: MFAMethod
    status: MFAChallengeStatus = MFAChallengeStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(minutes=5)
    )
    attempt_count: int = 0
    max_attempts: int = 3
    challenge_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the MFA challenge data."""
        # Validate required fields
        if not isinstance(self.challenge_id, str) or not self.challenge_id.strip():
            raise ValueError("Challenge ID cannot be empty")

        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("User ID cannot be empty")

        if not isinstance(self.method, MFAMethod):
            raise TypeError("Method must be an MFAMethod enum")

        if not isinstance(self.status, MFAChallengeStatus):
            raise TypeError("Status must be an MFAChallengeStatus enum")

        # Ensure timezone awareness for datetime fields
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=timezone.utc))

        # Validate attempt counts
        if self.attempt_count < 0:
            raise ValueError("Attempt count cannot be negative")

        if self.max_attempts <= 0:
            raise ValueError("Max attempts must be positive")

    @classmethod
    def create_new(
        cls,
        user_id: str,
        method: MFAMethod,
        expires_in_minutes: int = 5,
        max_attempts: int = 3,
        challenge_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MFAChallenge:
        """Create a new MFA challenge."""
        challenge_id = f"mfa_{uuid4().hex[:16]}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

        return cls(
            challenge_id=challenge_id,
            user_id=user_id,
            method=method,
            expires_at=expires_at,
            max_attempts=max_attempts,
            challenge_data=challenge_data or {},
            metadata=metadata or {},
        )

    def is_expired(self) -> bool:
        """Check if the challenge has expired."""
        return datetime.now(timezone.utc) >= self.expires_at

    def can_attempt(self) -> bool:
        """Check if another verification attempt is allowed."""
        return (
            self.status == MFAChallengeStatus.PENDING
            and self.attempt_count < self.max_attempts
            and not self.is_expired()
        )

    def increment_attempt(self) -> MFAChallenge:
        """Create a new challenge with incremented attempt count."""
        new_count = self.attempt_count + 1
        new_status = self.status

        # Update status if max attempts reached
        if new_count >= self.max_attempts:
            new_status = MFAChallengeStatus.FAILED

        return self._replace(attempt_count=new_count, status=new_status)

    def mark_verified(self) -> MFAChallenge:
        """Create a new challenge marked as verified."""
        return self._replace(status=MFAChallengeStatus.VERIFIED)

    def mark_failed(self) -> MFAChallenge:
        """Create a new challenge marked as failed."""
        return self._replace(status=MFAChallengeStatus.FAILED)

    def mark_expired(self) -> MFAChallenge:
        """Create a new challenge marked as expired."""
        return self._replace(status=MFAChallengeStatus.EXPIRED)

    def mark_cancelled(self) -> MFAChallenge:
        """Create a new challenge marked as cancelled."""
        return self._replace(status=MFAChallengeStatus.CANCELLED)

    def with_data(self, **data: Any) -> MFAChallenge:
        """Create a new challenge with updated challenge data."""
        new_data = {**self.challenge_data, **data}
        return self._replace(challenge_data=new_data)

    def with_metadata(self, **metadata: Any) -> MFAChallenge:
        """Create a new challenge with updated metadata."""
        new_metadata = {**self.metadata, **metadata}
        return self._replace(metadata=new_metadata)

    def _replace(self, **changes) -> MFAChallenge:
        """Create a new challenge with the specified changes."""
        kwargs = {
            "challenge_id": self.challenge_id,
            "user_id": self.user_id,
            "method": self.method,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "challenge_data": self.challenge_data,
            "metadata": self.metadata,
        }
        kwargs.update(changes)
        return MFAChallenge(**kwargs)


def generate_challenge_code(length: int = 6) -> str:
    """Generate a secure random challenge code."""
    # Use only digits for better user experience
    return "".join(secrets.choice("0123456789") for _ in range(length))


def generate_backup_codes(count: int = 8, length: int = 8) -> list[str]:
    """Generate backup recovery codes."""
    codes = []
    for _ in range(count):
        # Use alphanumeric characters for backup codes
        code = "".join(
            secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(length)
        )
        # Format with dashes for readability
        formatted_code = f"{code[:4]}-{code[4:]}"
        codes.append(formatted_code)
    return codes
