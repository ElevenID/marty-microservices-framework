"""Core domain models for identity management."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AuthenticationStatus(Enum):
    """Status of an authentication attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    EXPIRED = "expired"


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


@dataclass
class AuthenticationResult:
    """Result of an authentication attempt."""
    status: AuthenticationStatus
    principal: Principal | None = None
    error_message: str | None = None

    def __post_init__(self):
        if self.status == AuthenticationStatus.SUCCESS and self.principal is None:
            raise ValueError("Successful authentication must include a principal")
        if self.status == AuthenticationStatus.FAILED and self.error_message is None:
            raise ValueError("Failed authentication must include an error message")
