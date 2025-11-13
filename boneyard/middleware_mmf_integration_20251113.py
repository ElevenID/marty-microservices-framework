"""
JWT Authentication Middleware for FastAPI.

Provides automatic JWT token validation for protected routes
in the integration layer.
"""

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from .configuration import IntegrationConfig
from .http_endpoints import JWTService


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic JWT token validation.

    Validates JWT tokens on protected routes and injects
    the authenticated user into the request state.
    """

    def __init__(
        self,
        app,
        config: IntegrationConfig | None = None,
    ):
        """
        Initialize JWT authentication middleware.

        Args:
            app: FastAPI application instance
            config: JWT configuration (if None, loads from environment)
        """
        super().__init__(app)
        self.config = config or IntegrationConfig.from_environment()
        self.jwt_service = JWTService(self.config)

    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires authentication."""
        # Check if path is explicitly excluded
        for exclude_pattern in self.config.exclude_paths or []:
            if path.startswith(exclude_pattern):
                return False

        # Check if path is protected
        for protected_pattern in self.config.protected_paths or []:
            if path.startswith(protected_pattern):
                return True

        return False

    def _extract_token_from_request(self, request: Request) -> str | None:
        """Extract JWT token from request headers."""
        authorization = request.headers.get("Authorization")

        if not authorization:
            return None

        if not authorization.startswith("Bearer "):
            return None

        return authorization[7:]  # Remove "Bearer " prefix

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable]
    ) -> Awaitable:
        """Process request and validate JWT token if required."""
        # Check if this path requires authentication
        if not self._is_protected_path(request.url.path):
            return await call_next(request)

        # Extract token from request
        token = self._extract_token_from_request(request)

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Validate token and inject user into request state
            user = self.jwt_service.validate_token(token)
            request.state.user = user

            # Continue processing
            return await call_next(request)

        except HTTPException:
            # Re-raise HTTP exceptions (token validation errors)
            raise
        except Exception as error:
            # Handle unexpected errors
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token validation failed",
            ) from error
