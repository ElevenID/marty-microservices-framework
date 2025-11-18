"""Core domain models for identity management."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# Import from existing modules only
from .authenticated_user import AuthenticatedUser
from .authentication_result import (
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)

# Note: MFA, Session, OAuth2, OIDC, and MTLS subpackages are available
# but not imported here to avoid circular dependencies with core infrastructure.
# Import them directly from their subpackages when needed:
# from .mfa import MFAChallenge, ...
# from .session import Session, ...
# from .oauth2 import OAuth2Client, ...
# from .oidc import JWK, ...
# from .mtls import MTLSConfiguration, ...


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


# MFA domain models

# mTLS models

# OAuth2 models

# OIDC models

# User and authentication models

__all__ = [
    # Core authentication models
    "AuthenticationErrorCode",
    "AuthenticationResult",
    "AuthenticationStatus",
    "AuthenticatedUser",
    # Value objects
    "UserId",
    "Credentials",
    "Principal",
    "LegacyAuthenticationResult",
    # Note: MFA, Session, OAuth2, OIDC, and MTLS models are available
    # in their respective subpackages but not exported here to avoid
    # circular dependencies. Import them directly when needed.
]

# Note: OAuth2, mTLS, and OIDC models are included via wildcard imports above
# This provides all the models while maintaining clean separation of concerns
