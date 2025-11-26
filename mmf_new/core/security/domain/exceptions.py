"""
Security Exceptions

This module defines exceptions for security operations.
"""


class SecurityError(Exception):
    """Base exception for security-related errors."""


class AuthenticationError(SecurityError):
    """Raised when authentication fails."""


class AuthorizationError(SecurityError):
    """Raised when authorization fails."""


class SecretManagerError(SecurityError):
    """Raised when secret management operations fail."""


class InsufficientPermissionsError(AuthorizationError):
    """Raised when user lacks required permissions."""


class PermissionDeniedError(AuthorizationError):
    """Raised when permission is explicitly denied."""


class RoleRequiredError(AuthorizationError):
    """Raised when a specific role is required but missing."""


class InvalidTokenError(AuthenticationError):
    """Raised when an authentication token is invalid."""


class RateLimitExceededError(SecurityError):
    """Raised when rate limit is exceeded."""


class CertificateValidationError(AuthenticationError):
    """Raised when certificate validation fails."""


def handle_security_exception(exc: Exception) -> None:
    """
    Helper to log or process security exceptions.

    Args:
        exc: The exception to handle
    """
    # This is a placeholder for centralized exception handling logic
    _ = exc

