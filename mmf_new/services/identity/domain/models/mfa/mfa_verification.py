"""
MFA Verification domain model.

This module contains domain models for MFA verification requests
and results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from mmf_new.core.domain.entity import ValueObject


class MFAVerificationResult(Enum):
    """Result of MFA verification."""

    SUCCESS = "success"  # Verification successful
    INVALID_CODE = "invalid_code"  # Provided code is invalid
    EXPIRED = "expired"  # Challenge or code has expired
    DEVICE_INACTIVE = "device_inactive"  # Device is not active
    TOO_MANY_ATTEMPTS = "too_many_attempts"  # Exceeded attempt limit
    UNKNOWN_CHALLENGE = "unknown_challenge"  # Challenge not found
    UNKNOWN_DEVICE = "unknown_device"  # Device not found
    METHOD_MISMATCH = "method_mismatch"  # Wrong verification method
    SYSTEM_ERROR = "system_error"  # Internal system error


@dataclass(frozen=True)
class MFAVerification(ValueObject):
    """
    Domain model representing an MFA verification request.

    This encapsulates the data needed to verify an MFA challenge
    including the challenge ID, device, and verification code.
    """

    challenge_id: str
    device_id: str | None = None
    verification_code: str | None = None
    backup_code: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate the MFA verification data."""
        # Validate required fields
        if not isinstance(self.challenge_id, str) or not self.challenge_id.strip():
            raise ValueError("Challenge ID cannot be empty")

        # Must have either verification code or backup code
        if not self.verification_code and not self.backup_code:
            raise ValueError("Either verification_code or backup_code must be provided")

        # Cannot have both verification code and backup code
        if self.verification_code and self.backup_code:
            raise ValueError("Cannot provide both verification_code and backup_code")

        # If using verification code, device_id is required
        if self.verification_code and not self.device_id:
            raise ValueError("device_id is required when using verification_code")

        # Ensure timezone awareness for timestamp
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))

    @classmethod
    def with_verification_code(
        cls,
        challenge_id: str,
        device_id: str,
        verification_code: str,
        metadata: dict[str, Any] | None = None,
    ) -> MFAVerification:
        """Create verification request with verification code."""
        return cls(
            challenge_id=challenge_id,
            device_id=device_id,
            verification_code=verification_code,
            metadata=metadata or {},
        )

    @classmethod
    def with_backup_code(
        cls, challenge_id: str, backup_code: str, metadata: dict[str, Any] | None = None
    ) -> MFAVerification:
        """Create verification request with backup code."""
        return cls(challenge_id=challenge_id, backup_code=backup_code, metadata=metadata or {})

    def is_using_backup_code(self) -> bool:
        """Check if verification is using a backup code."""
        return self.backup_code is not None

    def is_using_device_code(self) -> bool:
        """Check if verification is using a device verification code."""
        return self.verification_code is not None

    def get_code(self) -> str:
        """Get the verification code (either regular or backup)."""
        if self.verification_code:
            return self.verification_code
        elif self.backup_code:
            return self.backup_code
        else:
            raise ValueError("No verification code available")

    def with_metadata(self, **metadata: Any) -> MFAVerification:
        """Create a new verification with updated metadata."""
        new_metadata = {**self.metadata, **metadata}
        return MFAVerification(
            challenge_id=self.challenge_id,
            device_id=self.device_id,
            verification_code=self.verification_code,
            backup_code=self.backup_code,
            metadata=new_metadata,
            timestamp=self.timestamp,
        )


@dataclass(frozen=True)
class MFAVerificationResponse(ValueObject):
    """
    Response from MFA verification operation.

    Contains the result of the verification attempt and any
    relevant metadata.
    """

    challenge_id: str
    result: MFAVerificationResult
    success: bool
    error_message: str | None = None
    remaining_attempts: int | None = None
    device_id: str | None = None
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate the verification response."""
        if not isinstance(self.challenge_id, str) or not self.challenge_id.strip():
            raise ValueError("Challenge ID cannot be empty")

        if not isinstance(self.result, MFAVerificationResult):
            raise TypeError("Result must be an MFAVerificationResult enum")

        # Ensure timezone awareness for verified_at
        if self.verified_at.tzinfo is None:
            object.__setattr__(self, "verified_at", self.verified_at.replace(tzinfo=timezone.utc))

        # Validate consistency
        if self.success and self.result != MFAVerificationResult.SUCCESS:
            raise ValueError("Success flag must match result")

        if not self.success and self.result == MFAVerificationResult.SUCCESS:
            raise ValueError("Result must not be SUCCESS when success is False")

    @classmethod
    def success_response(
        cls, challenge_id: str, device_id: str | None = None, metadata: dict[str, Any] | None = None
    ) -> MFAVerificationResponse:
        """Create a successful verification response."""
        return cls(
            challenge_id=challenge_id,
            result=MFAVerificationResult.SUCCESS,
            success=True,
            device_id=device_id,
            metadata=metadata or {},
        )

    @classmethod
    def failure_response(
        cls,
        challenge_id: str,
        result: MFAVerificationResult,
        error_message: str,
        remaining_attempts: int | None = None,
        device_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MFAVerificationResponse:
        """Create a failed verification response."""
        if result == MFAVerificationResult.SUCCESS:
            raise ValueError("Cannot create failure response with SUCCESS result")

        return cls(
            challenge_id=challenge_id,
            result=result,
            success=False,
            error_message=error_message,
            remaining_attempts=remaining_attempts,
            device_id=device_id,
            metadata=metadata or {},
        )

    def is_retriable(self) -> bool:
        """Check if verification can be retried."""
        non_retriable_results = {
            MFAVerificationResult.EXPIRED,
            MFAVerificationResult.DEVICE_INACTIVE,
            MFAVerificationResult.TOO_MANY_ATTEMPTS,
            MFAVerificationResult.UNKNOWN_CHALLENGE,
            MFAVerificationResult.UNKNOWN_DEVICE,
            MFAVerificationResult.METHOD_MISMATCH,
        }
        return self.result not in non_retriable_results

    def with_metadata(self, **metadata: Any) -> MFAVerificationResponse:
        """Create a new response with updated metadata."""
        new_metadata = {**self.metadata, **metadata}
        return MFAVerificationResponse(
            challenge_id=self.challenge_id,
            result=self.result,
            success=self.success,
            error_message=self.error_message,
            remaining_attempts=self.remaining_attempts,
            device_id=self.device_id,
            verified_at=self.verified_at,
            metadata=new_metadata,
        )
