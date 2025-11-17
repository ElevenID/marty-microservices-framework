"""
MFA (Multi-Factor Authentication) infrastructure adapters.

This module contains concrete implementations of MFA providers
including TOTP, SMS, and email-based authentication.
"""

from .email_mfa_adapter import EmailMFAAdapter, EmailMFAConfig
from .sms_mfa_adapter import SMSMFAAdapter, SMSMFAConfig
from .totp_adapter import TOTPAdapter, TOTPConfig

__all__ = [
    # TOTP
    "TOTPAdapter",
    "TOTPConfig",
    # Email MFA
    "EmailMFAAdapter",
    "EmailMFAConfig",
    # SMS MFA
    "SMSMFAAdapter",
    "SMSMFAConfig",
]
