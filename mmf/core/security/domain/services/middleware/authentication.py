"""
Authentication Middleware

Middleware for authenticating requests when no session is present.
"""

from typing import Any

import jwt

from mmf.core.security.domain.config import JWTConfig
from mmf.core.security.domain.services.middleware.base import BaseMiddleware


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
        if not self.jwt_config:
            return request_context

        headers = request_context.get("headers", {})
        auth_header = headers.get("authorization") or headers.get("Authorization")

        if not auth_header:
            return request_context

        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return request_context

            payload = jwt.decode(
                token,
                self.jwt_config.secret_key,
                algorithms=[self.jwt_config.algorithm],
                audience=self.jwt_config.audience,
                issuer=self.jwt_config.issuer,
            )

            return {"user": payload}

        except (ValueError, jwt.PyJWTError):
            # Invalid token or header format
            # We don't raise here to allow other auth methods or public access
            return request_context
