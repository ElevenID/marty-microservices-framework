"""Core domain models for identity management."""

# Legacy domain models (will be phased out as we migrate)
from dataclasses import dataclass
from datetime import datetime

from .authenticated_user import AuthenticatedUser
from .authentication_result import (
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)


@dataclass(frozen=True)
class UserId:
    """Value object representing a user identifier."""
    value: str

    def __post_init__(self):
        if not self.value or not self.value.strip():
            raise ValueError("UserId cannot be empty")


@dataclass(frozen=True)
class Credentials:
    """Value object representing authentication credentials."""
    username: str
    password: str

    def __post_init__(self):
        if not self.username or not self.username.strip():
            raise ValueError("Username cannot be empty")
        if not self.password:
            raise ValueError("Password cannot be empty")


@dataclass
class Principal:
    """Entity representing an authenticated principal."""
    user_id: UserId
    username: str
    authenticated_at: datetime
    expires_at: datetime | None = None

    def is_expired(self, current_time: datetime) -> bool:
        """Check if the principal's authentication has expired."""
        if self.expires_at is None:
            return False
        return current_time >= self.expires_at


# Legacy AuthenticationResult - use the new one instead
@dataclass
class LegacyAuthenticationResult:
    """Legacy result of an authentication attempt."""
    status: AuthenticationStatus
    principal: Principal | None = None
    error_message: str | None = None

    def __post_init__(self):
        if self.status == AuthenticationStatus.SUCCESS and self.principal is None:
            raise ValueError("Successful authentication must include a principal")
        if self.status == AuthenticationStatus.FAILED and self.error_message is None:
            raise ValueError("Failed authentication must include an error message")


__all__ = [
    "AuthenticatedUser",
    "AuthenticationResult",
    "AuthenticationStatus",
    "AuthenticationErrorCode",
    "UserId",
    "Credentials",
    "Principal",
    "LegacyAuthenticationResult",  # Keep for backward compatibility during migration
]
