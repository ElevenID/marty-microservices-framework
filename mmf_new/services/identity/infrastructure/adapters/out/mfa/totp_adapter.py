"""
TOTP (Time-based One-Time Password) adapter implementation.

This adapter provides TOTP-based multi-factor authentication using
standard TOTP algorithms compatible with Google Authenticator, Authy, etc.
"""

import base64
import hashlib
import hmac
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from mmf_new.services.identity.application.ports_out.mfa_provider import (
    AuthenticationContext,
    MFAChallengeNotFoundError,
    MFADeviceLimitExceededError,
    MFADeviceNotFoundError,
    MFAProviderError,
    TOTPProvider,
)
from mmf_new.services.identity.domain.models.mfa import (
    MFAChallenge,
    MFADevice,
    MFADeviceStatus,
    MFADeviceType,
    MFAMethod,
    MFAVerification,
    MFAVerificationResponse,
    MFAVerificationResult,
    generate_backup_codes,
    generate_totp_secret,
)


@dataclass
class TOTPConfig:
    """Configuration for TOTP provider."""

    issuer: str = "MMF Identity Service"
    period: int = 30  # Time step in seconds (standard is 30)
    digits: int = 6  # Number of digits in code (standard is 6)
    algorithm: str = "SHA1"  # Hash algorithm (SHA1, SHA256, SHA512)
    window: int = 1  # Time window tolerance (±periods)
    max_devices_per_user: int = 5  # Maximum TOTP devices per user
    challenge_expiry_minutes: int = 5  # MFA challenge expiry time
    backup_codes_count: int = 8  # Number of backup codes to generate
    rate_limit_window: int = 60  # Rate limiting window in seconds
    max_attempts_per_window: int = 5  # Max verification attempts per window


class TOTPAdapter(TOTPProvider):
    """
    TOTP adapter providing time-based one-time password authentication.

    Implements TOTP according to RFC 6238 with support for:
    - Standard TOTP generation and verification
    - QR code URLs for authenticator app setup
    - Device registration and management
    - Backup recovery codes
    - Rate limiting and security controls
    """

    def __init__(self, config: TOTPConfig):
        """Initialize TOTP adapter with configuration."""
        self._config = config

        # In-memory storage (in production, use proper persistence)
        self._devices: dict[str, MFADevice] = {}
        self._challenges: dict[str, MFAChallenge] = {}
        self._backup_codes: dict[str, set[str]] = {}  # user_id -> set of codes
        self._used_codes: dict[str, set[str]] = {}  # device_id -> set of used codes
        self._rate_limits: dict[str, list[datetime]] = {}  # user_id -> list of attempt times

        # Algorithm mapping
        self._algorithms = {
            "SHA1": hashlib.sha1,
            "SHA256": hashlib.sha256,
            "SHA512": hashlib.sha512,
        }

        if config.algorithm not in self._algorithms:
            raise ValueError(f"Unsupported algorithm: {config.algorithm}")

    async def create_challenge(
        self,
        user_id: str,
        method: MFAMethod,
        device_id: str | None = None,
        context: AuthenticationContext | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MFAChallenge:
        """Create a new TOTP challenge."""
        if method != MFAMethod.TOTP:
            raise MFAProviderError(f"TOTP provider does not support method: {method}")

        # Verify device exists if specified
        if device_id:
            device = await self.get_device(device_id)
            if device.user_id != user_id:
                raise MFAProviderError("Device does not belong to user")
            if not device.can_be_used():
                raise MFAProviderError("Device is not active")

        # Create challenge
        challenge = MFAChallenge.create_new(
            user_id=user_id,
            method=method,
            expires_in_minutes=self._config.challenge_expiry_minutes,
            challenge_data={"device_id": device_id} if device_id else {},
            metadata=metadata or {},
        )

        # Store challenge
        self._challenges[challenge.challenge_id] = challenge

        return challenge

    async def verify_challenge(
        self, verification: MFAVerification, context: AuthenticationContext | None = None
    ) -> MFAVerificationResponse:
        """Verify a TOTP challenge."""
        try:
            # Get challenge
            challenge = await self.get_challenge(verification.challenge_id)

            # Check if challenge can be attempted
            if not challenge.can_attempt():
                if challenge.is_expired():
                    result = MFAVerificationResult.EXPIRED
                    message = "Challenge has expired"
                else:
                    result = MFAVerificationResult.TOO_MANY_ATTEMPTS
                    message = "Too many verification attempts"

                return MFAVerificationResponse.failure_response(
                    challenge_id=verification.challenge_id, result=result, error_message=message
                )

            # Handle backup code verification
            if verification.is_using_backup_code():
                is_valid = await self.verify_backup_code(
                    user_id=challenge.user_id, backup_code=verification.backup_code, context=context
                )

                if is_valid:
                    # Mark challenge as verified
                    verified_challenge = challenge.mark_verified()
                    self._challenges[challenge.challenge_id] = verified_challenge

                    return MFAVerificationResponse.success_response(
                        challenge_id=verification.challenge_id, metadata={"method": "backup_code"}
                    )
                else:
                    # Increment attempt count
                    failed_challenge = challenge.increment_attempt()
                    self._challenges[challenge.challenge_id] = failed_challenge

                    return MFAVerificationResponse.failure_response(
                        challenge_id=verification.challenge_id,
                        result=MFAVerificationResult.INVALID_CODE,
                        error_message="Invalid backup code",
                        remaining_attempts=failed_challenge.max_attempts
                        - failed_challenge.attempt_count,
                    )

            # Handle TOTP code verification
            if verification.is_using_device_code():
                device_id = verification.device_id
                if not device_id:
                    return MFAVerificationResponse.failure_response(
                        challenge_id=verification.challenge_id,
                        result=MFAVerificationResult.UNKNOWN_DEVICE,
                        error_message="Device ID is required for TOTP verification",
                    )

                try:
                    device = await self.get_device(device_id)
                except MFADeviceNotFoundError:
                    return MFAVerificationResponse.failure_response(
                        challenge_id=verification.challenge_id,
                        result=MFAVerificationResult.UNKNOWN_DEVICE,
                        error_message="Device not found",
                    )

                if not device.can_be_used():
                    return MFAVerificationResponse.failure_response(
                        challenge_id=verification.challenge_id,
                        result=MFAVerificationResult.DEVICE_INACTIVE,
                        error_message="Device is not active",
                    )

                # Check rate limiting
                if not await self._check_rate_limit(challenge.user_id):
                    return MFAVerificationResponse.failure_response(
                        challenge_id=verification.challenge_id,
                        result=MFAVerificationResult.TOO_MANY_ATTEMPTS,
                        error_message="Too many verification attempts, please wait",
                    )

                # Record attempt for rate limiting
                await self._record_attempt(challenge.user_id)

                # Verify TOTP code
                secret = device.device_data.get("secret")
                if not secret:
                    return MFAVerificationResponse.failure_response(
                        challenge_id=verification.challenge_id,
                        result=MFAVerificationResult.SYSTEM_ERROR,
                        error_message="Device secret not found",
                    )

                is_valid = await self.verify_totp_code(
                    secret=secret, code=verification.verification_code, window=self._config.window
                )

                if is_valid:
                    # Check for code reuse
                    if await self._is_code_used(device_id, verification.verification_code):
                        return MFAVerificationResponse.failure_response(
                            challenge_id=verification.challenge_id,
                            result=MFAVerificationResult.INVALID_CODE,
                            error_message="Code has already been used",
                        )

                    # Mark code as used
                    await self._mark_code_used(device_id, verification.verification_code)

                    # Update device usage
                    updated_device = device.mark_used()
                    self._devices[device_id] = updated_device

                    # Mark challenge as verified
                    verified_challenge = challenge.mark_verified()
                    self._challenges[challenge.challenge_id] = verified_challenge

                    return MFAVerificationResponse.success_response(
                        challenge_id=verification.challenge_id,
                        device_id=device_id,
                        metadata={"method": "totp"},
                    )
                else:
                    # Increment attempt count
                    failed_challenge = challenge.increment_attempt()
                    self._challenges[challenge.challenge_id] = failed_challenge

                    return MFAVerificationResponse.failure_response(
                        challenge_id=verification.challenge_id,
                        result=MFAVerificationResult.INVALID_CODE,
                        error_message="Invalid verification code",
                        remaining_attempts=failed_challenge.max_attempts
                        - failed_challenge.attempt_count,
                        device_id=device_id,
                    )

            # Neither backup code nor device code provided
            return MFAVerificationResponse.failure_response(
                challenge_id=verification.challenge_id,
                result=MFAVerificationResult.INVALID_CODE,
                error_message="No valid verification method provided",
            )

        except Exception as e:
            return MFAVerificationResponse.failure_response(
                challenge_id=verification.challenge_id,
                result=MFAVerificationResult.SYSTEM_ERROR,
                error_message=f"Verification error: {str(e)}",
            )

    async def register_device(
        self,
        user_id: str,
        device_type: MFADeviceType,
        device_name: str,
        device_data: dict[str, Any],
        context: AuthenticationContext | None = None,
    ) -> MFADevice:
        """Register a new TOTP device."""
        if device_type != MFADeviceType.TOTP_APP:
            raise MFAProviderError(f"TOTP provider does not support device type: {device_type}")

        # Check device limit
        user_devices = await self.get_user_devices(user_id, include_inactive=True)
        if len(user_devices) >= self._config.max_devices_per_user:
            raise MFADeviceLimitExceededError(
                f"User has reached maximum TOTP device limit ({self._config.max_devices_per_user})"
            )

        # Generate TOTP secret if not provided
        secret = device_data.get("secret")
        if not secret:
            secret = generate_totp_secret()

        # Create device
        device = MFADevice.create_new(
            user_id=user_id,
            device_type=device_type,
            device_name=device_name,
            device_data={
                "secret": secret,
                "algorithm": self._config.algorithm,
                "period": self._config.period,
                "digits": self._config.digits,
                **device_data,
            },
        )

        # Store device
        self._devices[device.device_id] = device

        return device

    async def verify_device(
        self, device_id: str, verification_code: str, context: AuthenticationContext | None = None
    ) -> MFADevice:
        """Verify a pending TOTP device."""
        device = await self.get_device(device_id)

        if device.status != MFADeviceStatus.PENDING:
            raise MFAProviderError("Device is not in pending status")

        # Verify TOTP code
        secret = device.device_data.get("secret")
        if not secret:
            raise MFAProviderError("Device secret not found")

        is_valid = await self.verify_totp_code(secret, verification_code)
        if not is_valid:
            raise MFAProviderError("Invalid verification code")

        # Mark device as verified and active
        verified_device = device.mark_verified()
        self._devices[device_id] = verified_device

        return verified_device

    async def get_user_devices(
        self, user_id: str, include_inactive: bool = False
    ) -> list[MFADevice]:
        """Get all TOTP devices for a user."""
        devices = []
        for device in self._devices.values():
            if device.user_id == user_id and device.device_type == MFADeviceType.TOTP_APP:
                if include_inactive or device.is_active():
                    devices.append(device)

        return sorted(devices, key=lambda d: d.created_at)

    async def get_device(self, device_id: str) -> MFADevice:
        """Get a specific TOTP device."""
        device = self._devices.get(device_id)
        if not device:
            raise MFADeviceNotFoundError(f"Device not found: {device_id}")

        if device.device_type != MFADeviceType.TOTP_APP:
            raise MFADeviceNotFoundError(f"Device is not a TOTP device: {device_id}")

        return device

    async def update_device(
        self,
        device_id: str,
        device_name: str | None = None,
        status: str | None = None,
        context: AuthenticationContext | None = None,
    ) -> MFADevice:
        """Update a TOTP device."""
        device = await self.get_device(device_id)

        updated_device = device

        if device_name is not None:
            updated_device = updated_device.update_name(device_name)

        if status is not None:
            status_enum = MFADeviceStatus(status)
            if status_enum == MFADeviceStatus.ACTIVE:
                updated_device = updated_device.mark_active()
            elif status_enum == MFADeviceStatus.INACTIVE:
                updated_device = updated_device.mark_inactive()
            elif status_enum == MFADeviceStatus.REVOKED:
                updated_device = updated_device.mark_revoked()
            elif status_enum == MFADeviceStatus.COMPROMISED:
                updated_device = updated_device.mark_compromised()

        self._devices[device_id] = updated_device
        return updated_device

    async def revoke_device(
        self, device_id: str, context: AuthenticationContext | None = None
    ) -> bool:
        """Revoke a TOTP device."""
        device = await self.get_device(device_id)
        revoked_device = device.mark_revoked()
        self._devices[device_id] = revoked_device

        # Clean up used codes for this device
        if device_id in self._used_codes:
            del self._used_codes[device_id]

        return True

    async def generate_backup_codes(
        self, user_id: str, count: int = 8, context: AuthenticationContext | None = None
    ) -> list[str]:
        """Generate backup recovery codes."""
        if count <= 0:
            count = self._config.backup_codes_count

        codes = generate_backup_codes(count=count)
        self._backup_codes[user_id] = set(codes)

        return codes

    async def verify_backup_code(
        self, user_id: str, backup_code: str, context: AuthenticationContext | None = None
    ) -> bool:
        """Verify and consume a backup code."""
        user_codes = self._backup_codes.get(user_id, set())

        if backup_code in user_codes:
            # Remove the used code
            user_codes.remove(backup_code)
            self._backup_codes[user_id] = user_codes
            return True

        return False

    async def get_challenge(self, challenge_id: str) -> MFAChallenge:
        """Get a specific MFA challenge."""
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            raise MFAChallengeNotFoundError(f"Challenge not found: {challenge_id}")

        return challenge

    async def cleanup_expired_challenges(self) -> int:
        """Clean up expired MFA challenges."""
        expired_ids = []
        for challenge_id, challenge in self._challenges.items():
            if challenge.is_expired():
                expired_ids.append(challenge_id)

        for challenge_id in expired_ids:
            del self._challenges[challenge_id]

        return len(expired_ids)

    def supports_method(self, method: MFAMethod) -> bool:
        """Check if TOTP method is supported."""
        return method == MFAMethod.TOTP

    @property
    def supported_methods(self) -> set[MFAMethod]:
        """Get supported MFA methods."""
        return {MFAMethod.TOTP}

    @property
    def supported_device_types(self) -> set[MFADeviceType]:
        """Get supported device types."""
        return {MFADeviceType.TOTP_APP}

    # TOTP-specific methods

    async def generate_totp_secret(self, user_id: str) -> str:
        """Generate a TOTP secret."""
        return generate_totp_secret()

    async def generate_qr_code_url(
        self, secret: str, user_identifier: str, issuer: str | None = None
    ) -> str:
        """Generate QR code URL for TOTP setup."""
        if issuer is None:
            issuer = self._config.issuer

        # Create otpauth URL according to Google Authenticator spec
        url = (
            f"otpauth://totp/{quote(issuer)}:{quote(user_identifier)}"
            f"?secret={secret}"
            f"&issuer={quote(issuer)}"
            f"&algorithm={self._config.algorithm}"
            f"&digits={self._config.digits}"
            f"&period={self._config.period}"
        )

        return url

    async def verify_totp_code(self, secret: str, code: str, window: int | None = None) -> bool:
        """Verify a TOTP code."""
        if window is None:
            window = self._config.window

        # Validate input
        if not code or not code.isdigit():
            return False

        if len(code) != self._config.digits:
            return False

        # Get current time window
        current_time = int(time.time())
        current_window = current_time // self._config.period

        # Try codes for the current window and nearby windows
        for offset in range(-window, window + 1):
            test_window = current_window + offset
            expected_code = self._generate_totp_code(secret, test_window)
            if code == expected_code:
                return True

        return False

    def _generate_totp_code(self, secret: str, time_window: int) -> str:
        """Generate a TOTP code for a specific time window."""
        # Decode base32 secret
        try:
            secret_bytes = base64.b32decode(secret.upper())
        except Exception:
            raise ValueError("Invalid secret format")

        # Create time counter as 8-byte big-endian integer
        counter = struct.pack(">Q", time_window)

        # Calculate HMAC
        algorithm = self._algorithms[self._config.algorithm]
        hmac_digest = hmac.new(secret_bytes, counter, algorithm).digest()

        # Dynamic truncation
        offset = hmac_digest[-1] & 0xF
        code_bytes = hmac_digest[offset : offset + 4]
        code_int = struct.unpack(">I", code_bytes)[0] & 0x7FFFFFFF

        # Generate code with specified number of digits
        code = str(code_int % (10**self._config.digits))
        return code.zfill(self._config.digits)

    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limits."""
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=self._config.rate_limit_window)

        # Get recent attempts for this user
        attempts = self._rate_limits.get(user_id, [])

        # Filter to only recent attempts
        recent_attempts = [attempt for attempt in attempts if attempt >= window_start]

        # Update the stored attempts
        self._rate_limits[user_id] = recent_attempts

        # Check if within limit
        return len(recent_attempts) < self._config.max_attempts_per_window

    async def _record_attempt(self, user_id: str) -> None:
        """Record a verification attempt for rate limiting."""
        now = datetime.now(timezone.utc)

        if user_id not in self._rate_limits:
            self._rate_limits[user_id] = []

        self._rate_limits[user_id].append(now)

    async def _is_code_used(self, device_id: str, code: str) -> bool:
        """Check if a code has already been used for this device."""
        used_codes = self._used_codes.get(device_id, set())
        return code in used_codes

    async def _mark_code_used(self, device_id: str, code: str) -> None:
        """Mark a code as used for this device."""
        if device_id not in self._used_codes:
            self._used_codes[device_id] = set()

        self._used_codes[device_id].add(code)

        # Keep only recent codes to prevent memory bloat
        # In production, implement proper cleanup based on time
        if len(self._used_codes[device_id]) > 100:
            # Remove oldest codes (this is a simple approach)
            codes_list = list(self._used_codes[device_id])
            self._used_codes[device_id] = set(codes_list[-50:])
