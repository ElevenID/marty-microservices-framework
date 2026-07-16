"""
MFA (Multi-Factor Authentication) domain models.

This module contains all domain models related to multi-factor authentication
including MFA challenges, methods, and verification results.
"""

from .mfa_challenge import (
    MFAChallenge,
    MFAChallengeStatus,
    MFAMethod,
    generate_backup_codes,
    generate_challenge_code,
)
from .mfa_device import MFADevice, MFADeviceStatus, MFADeviceType, generate_totp_secret
from .mfa_verification import (
    MFAVerification,
    MFAVerificationResponse,
    MFAVerificationResult,
)

__all__ = [
    # Challenge models
    "MFAChallenge",
    "MFAChallengeStatus",
    "MFAMethod",
    "generate_challenge_code",
    "generate_backup_codes",
    # Device models
    "MFADevice",
    "MFADeviceStatus",
    "MFADeviceType",
    "generate_totp_secret",
    # Verification models
    "MFAVerification",
    "MFAVerificationResult",
    "MFAVerificationResponse",
]
