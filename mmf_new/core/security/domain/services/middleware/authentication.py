"""
Authentication Middleware

Middleware for authenticating requests when no session is present.
"""

from typing import Any

from mmf_new.core.security.domain.config import JWTConfig
from mmf_new.core.security.domain.services.middleware.base import BaseMiddleware


class AuthenticationMiddleware(BaseMiddleware):
    """Middleware for authentication."""

    def __init__(self, jwt_config: JWTConfig | None = None):
        self.jwt_config = jwt_config

    async def process(
        self,
        request_context: dict[str, Any],
        next_middleware: Any = None,
    ) -> dict[str, Any]:
        """
        Authenticate request if user is not already present.
        """
        if "user" not in request_context:
            auth_result = await self._authenticate_request(request_context)
            if "user" in auth_result:
                request_context["user"] = auth_result["user"]

        if next_middleware:
            return await next_middleware(request_context)

        return request_context

    async def _authenticate_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Authenticate incoming request."""
        # Placeholder for JWT/API Key auth logic
        # In a real implementation, we would parse headers and validate tokens
        return request_context
