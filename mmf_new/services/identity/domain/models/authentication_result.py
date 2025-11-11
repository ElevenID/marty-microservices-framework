"""
Authentication Result domain model for the identity service.

This model represents the outcome of an authentication attempt,
containing either success with user information or failure details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from mmf_new.core.domain.entity import ValueObject

from .authenticated_user import AuthenticatedUser


class AuthenticationStatus(Enum):
    """Status of an authentication attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    EXPIRED = "expired"
    LOCKED = "locked"
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_DISABLED = "account_disabled"
    REQUIRES_MFA = "requires_mfa"


class AuthenticationErrorCode(Enum):
    """Specific error codes for authentication failures."""

    MISSING_CREDENTIALS = "MISSING_CREDENTIALS"
    INVALID_USERNAME = "INVALID_USERNAME"
    INVALID_PASSWORD = "INVALID_PASSWORD"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    ACCOUNT_DISABLED = "ACCOUNT_DISABLED"
    ACCOUNT_EXPIRED = "ACCOUNT_EXPIRED"
    PASSWORD_EXPIRED = "PASSWORD_EXPIRED"
    TOO_MANY_ATTEMPTS = "TOO_MANY_ATTEMPTS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    MFA_REQUIRED = "MFA_REQUIRED"
    MFA_INVALID = "MFA_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


@dataclass(frozen=True)
class AuthenticationResult(ValueObject):
    """
    Domain model representing the result of an authentication attempt.

    This is a value object that encapsulates the outcome of authentication,
    whether successful or failed, with appropriate details for each case.
    """

    status: AuthenticationStatus
    authenticated_user: AuthenticatedUser | None = None
    error_message: str | None = None
    error_code: AuthenticationErrorCode | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    attempted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        """Validate the authentication result data."""
        # Ensure timezone awareness
        if self.attempted_at.tzinfo is None:
            object.__setattr__(self, "attempted_at", self.attempted_at.replace(tzinfo=timezone.utc))

        # Validation rules for successful authentication
        if self.status == AuthenticationStatus.SUCCESS:
            if self.authenticated_user is None:
                raise ValueError("Successful authentication must include an authenticated user")
            if self.error_message is not None or self.error_code is not None:
                raise ValueError("Successful authentication should not include error details")

        # Validation rules for failed authentication
        elif self.status in {
            AuthenticationStatus.FAILED,
            AuthenticationStatus.EXPIRED,
            AuthenticationStatus.LOCKED,
            AuthenticationStatus.INVALID_CREDENTIALS,
            AuthenticationStatus.ACCOUNT_DISABLED,
        }:
            if self.authenticated_user is not None:
                raise ValueError("Failed authentication should not include user details")
            if self.error_message is None:
                raise ValueError("Failed authentication must include an error message")
            if self.error_code is None:
                raise ValueError("Failed authentication must include an error code")

        # Validation for pending state
        elif self.status == AuthenticationStatus.PENDING:
            if self.authenticated_user is not None:
                raise ValueError("Pending authentication should not include user details")
            # Pending may or may not have error details depending on context

        # Special case for MFA required
        elif self.status == AuthenticationStatus.REQUIRES_MFA:
            # May include partial user info for MFA context
            if self.error_code is None:
                object.__setattr__(self, "error_code", AuthenticationErrorCode.MFA_REQUIRED)

    @property
    def is_successful(self) -> bool:
        """Check if authentication was successful."""
        return self.status == AuthenticationStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """Check if authentication failed."""
        return self.status in {
            AuthenticationStatus.FAILED,
            AuthenticationStatus.EXPIRED,
            AuthenticationStatus.LOCKED,
            AuthenticationStatus.INVALID_CREDENTIALS,
            AuthenticationStatus.ACCOUNT_DISABLED,
        }

    @property
    def requires_action(self) -> bool:
        """Check if authentication requires further action (MFA, etc.)."""
        return self.status in {
            AuthenticationStatus.PENDING,
            AuthenticationStatus.REQUIRES_MFA,
        }

    def with_user(self, user: AuthenticatedUser) -> AuthenticationResult:
        """Create a new result with an authenticated user (for success cases)."""
        if not self.is_successful:
            raise ValueError("Cannot add user to non-successful authentication result")

        return AuthenticationResult(
            status=self.status,
            authenticated_user=user,
            error_message=None,
            error_code=None,
            metadata=self.metadata,
            attempted_at=self.attempted_at,
        )

    def with_error(self, message: str, code: AuthenticationErrorCode) -> AuthenticationResult:
        """Create a new result with error details (for failure cases)."""
        if self.is_successful:
            raise ValueError("Cannot add error to successful authentication result")

        return AuthenticationResult(
            status=self.status,
            authenticated_user=None,
            error_message=message,
            error_code=code,
            metadata=self.metadata,
            attempted_at=self.attempted_at,
        )

    def with_metadata(self, key: str, value: Any) -> AuthenticationResult:
        """Create a new result with additional metadata."""
        new_metadata = self.metadata.copy()
        new_metadata[key] = value

        return AuthenticationResult(
            status=self.status,
            authenticated_user=self.authenticated_user,
            error_message=self.error_message,
            error_code=self.error_code,
            metadata=new_metadata,
            attempted_at=self.attempted_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "status": self.status.value,
            "success": self.is_successful,
            "attempted_at": self.attempted_at.isoformat(),
            "metadata": self.metadata,
        }

        if self.authenticated_user:
            result["authenticated_user"] = self.authenticated_user.to_dict()

        if self.error_message:
            result["error_message"] = self.error_message

        if self.error_code:
            result["error_code"] = self.error_code.value

        return result

    @classmethod
    def create_success(
        cls, user: AuthenticatedUser, metadata: dict[str, Any] | None = None
    ) -> AuthenticationResult:
        """Create a successful authentication result."""
        return cls(
            status=AuthenticationStatus.SUCCESS,
            authenticated_user=user,
            metadata=metadata or {},
        )

    @classmethod
    def failure(
        cls,
        message: str,
        code: AuthenticationErrorCode,
        status: AuthenticationStatus = AuthenticationStatus.FAILED,
        metadata: dict[str, Any] | None = None,
    ) -> AuthenticationResult:
        """Create a failed authentication result."""
        return cls(
            status=status,
            error_message=message,
            error_code=code,
            metadata=metadata or {},
        )

    @classmethod
    def pending_mfa(
        cls,
        message: str = "Multi-factor authentication required",
        partial_user: AuthenticatedUser | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuthenticationResult:
        """Create a result for MFA-required state."""
        return cls(
            status=AuthenticationStatus.REQUIRES_MFA,
            authenticated_user=partial_user,
            error_message=message,
            error_code=AuthenticationErrorCode.MFA_REQUIRED,
            metadata=metadata or {},
        )

    @classmethod
    def from_legacy(cls, legacy_result: dict[str, Any]) -> AuthenticationResult:
        """Convert from legacy authentication result format."""
        success = legacy_result.get("success", False)

        if success:
            # Extract user data and create AuthenticatedUser
            user_data = legacy_result.get("user")
            if user_data:
                # Convert legacy user to AuthenticatedUser
                authenticated_user = AuthenticatedUser(
                    user_id=user_data.get("user_id", ""),
                    username=user_data.get("username"),
                    email=user_data.get("email"),
                    roles=set(user_data.get("roles", [])),
                    permissions=set(user_data.get("permissions", [])),
                    session_id=user_data.get("session_id"),
                    auth_method=user_data.get("auth_method"),
                    expires_at=user_data.get("expires_at"),
                    metadata=user_data.get("metadata", {}),
                )

                return cls.create_success(
                    user=authenticated_user, metadata=legacy_result.get("metadata", {})
                )
            else:
                raise ValueError("Legacy successful result missing user data")
        else:
            # Handle failure case
            error_message = legacy_result.get("error", "Authentication failed")
            error_code_str = legacy_result.get("error_code", "INVALID_CREDENTIALS")

            # Map legacy error codes to new enum
            try:
                error_code = AuthenticationErrorCode(error_code_str)
            except ValueError:
                error_code = AuthenticationErrorCode.INTERNAL_ERROR

            return cls.failure(
                message=error_message,
                code=error_code,
                metadata=legacy_result.get("metadata", {}),
            )
