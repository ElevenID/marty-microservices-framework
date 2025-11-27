"""
Middleware Coordination Port

Interface for security middleware coordination.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..domain.models.rate_limit import RateLimitResult
from ..domain.models.session import SessionData


class IMiddlewareCoordinator(ABC):
    """Interface for coordinating security middleware components."""

    @abstractmethod
    async def process_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process incoming request through security pipeline.

        Args:
            request_context: Request context with headers, user info, etc.

        Returns:
            Processed context with security decisions
        """
        pass

    @abstractmethod
    async def authenticate_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Authenticate incoming request.

        Args:
            request_context: Request context

        Returns:
            Context with authentication result
        """
        pass

    @abstractmethod
    async def authorize_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Authorize incoming request.

        Args:
            request_context: Request context with authenticated user

        Returns:
            Context with authorization result
        """
        pass

    @abstractmethod
    async def check_rate_limits(
        self,
        request_context: dict[str, Any],
    ) -> RateLimitResult:
        """
        Check rate limits for request.

        Args:
            request_context: Request context

        Returns:
            Rate limit check result
        """
        pass

    @abstractmethod
    async def manage_session(
        self,
        request_context: dict[str, Any],
    ) -> SessionData | None:
        """
        Manage session for request.

        Args:
            request_context: Request context

        Returns:
            Session data if valid session exists
        """
        pass

    @abstractmethod
    async def apply_security_headers(
        self,
        response_context: dict[str, Any],
    ) -> dict[str, str]:
        """
        Generate security headers for response.

        Args:
            response_context: Response context

        Returns:
            Dictionary of security headers
        """
        pass

    @abstractmethod
    async def log_security_event(
        self,
        event_type: str,
        request_context: dict[str, Any],
        details: dict[str, Any] | None = None,
    ) -> bool:
        """
        Log security event.

        Args:
            event_type: Type of security event
            request_context: Request context
            details: Additional event details

        Returns:
            True if logging was successful
        """
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """
        Check health of all middleware components.

        Returns:
            Health status of all components
        """
        pass
