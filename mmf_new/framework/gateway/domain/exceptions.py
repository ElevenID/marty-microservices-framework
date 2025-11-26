"""
Gateway Domain Exceptions
"""

from typing import Any

class GatewayError(Exception):
    """Base exception for gateway errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class RouteNotFoundError(GatewayError):
    """Raised when no route matches the request."""

    def __init__(self, path: str, method: str):
        super().__init__(f"No route found for {method} {path}", 404)
        self.path = path
        self.method = method


class AuthenticationError(GatewayError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)


class AuthorizationError(GatewayError):
    """Raised when authorization fails."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message, 403)


class RateLimitExceededError(GatewayError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int | None = None):
        super().__init__(message, 429)
        self.retry_after = retry_after


class UpstreamError(GatewayError):
    """Raised when upstream service fails."""

    def __init__(self, message: str, upstream_status: int | None = None):
        super().__init__(message, 502)
        self.upstream_status = upstream_status
