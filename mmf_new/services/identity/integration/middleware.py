"""
JWT Authentication Middleware for FastAPI.

This module provides middleware for automatic JWT token extraction and validation
in FastAPI applications, enabling seamless authentication for protected routes.
"""

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, Response, status
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from mmf_new.services.identity.application.use_cases import (
    ValidateTokenRequest,
    ValidateTokenUseCase,
)
from mmf_new.services.identity.infrastructure.adapters import (
    JWTConfig,
    JWTTokenProvider,
)


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for JWT authentication.

    Automatically extracts and validates JWT tokens from Authorization headers,
    making authenticated user information available to downstream handlers.
    """

    def __init__(
        self,
        app,
        jwt_config: JWTConfig,
        excluded_paths: list[str] | None = None,
        optional_paths: list[str] | None = None
    ):
        """
        Initialize JWT authentication middleware.

        Args:
            app: FastAPI application instance
            jwt_config: JWT configuration
            excluded_paths: Paths that skip authentication entirely
            optional_paths: Paths where authentication is optional
        """
        super().__init__(app)
        self.token_provider = JWTTokenProvider(jwt_config)
        self.validate_use_case = ValidateTokenUseCase(self.token_provider)
        self.security = HTTPBearer(auto_error=False)

        # Default excluded paths (public endpoints)
        self.excluded_paths = set(excluded_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/auth/jwt/health",
        ])

        # Paths where authentication is optional
        self.optional_paths = set(optional_paths or [])

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process request with JWT authentication.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response

        Raises:
            HTTPException: For authentication failures on protected routes
        """
        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Extract token from Authorization header
        token = await self._extract_token(request)

        # Check if authentication is optional for this path
        is_optional = request.url.path in self.optional_paths

        if token:
            # Validate token and set user context
            user = await self._validate_token(token, is_optional)
            if user:
                # Add authenticated user to request state
                request.state.authenticated_user = user
                request.state.is_authenticated = True
            else:
                request.state.authenticated_user = None
                request.state.is_authenticated = False
        else:
            # No token provided
            if not is_optional:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            request.state.authenticated_user = None
            request.state.is_authenticated = False

        # Continue to next handler
        return await call_next(request)

    async def _extract_token(self, request: Request) -> str | None:
        """
        Extract JWT token from request Authorization header.

        Args:
            request: HTTP request

        Returns:
            JWT token if present, None otherwise
        """
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None

        # Parse Bearer token
        try:
            scheme, token = authorization.split(" ", 1)
            if scheme.lower() != "bearer":
                return None
            return token
        except ValueError:
            return None

    async def _validate_token(self, token: str, is_optional: bool = False) -> dict | None:
        """
        Validate JWT token and extract user information.

        Args:
            token: JWT token to validate
            is_optional: Whether validation failure should be ignored

        Returns:
            User information if token is valid, None otherwise

        Raises:
            HTTPException: For validation failures on required authentication
        """
        try:
            # Execute token validation
            request = ValidateTokenRequest(token=token)
            result = self.validate_use_case.execute(request)

            if result.is_valid and result.user:
                # Convert user to dict for easy access
                return {
                    "user_id": result.user.user_id,
                    "username": result.user.username,
                    "email": result.user.email,
                    "roles": list(result.user.roles),
                    "permissions": list(result.user.permissions),
                    "created_at": result.user.created_at,
                    "expires_at": result.user.expires_at,
                    "user_metadata": result.user.user_metadata,
                }
            else:
                if not is_optional:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid token: {result.error_message}",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return None

        except HTTPException:
            if not is_optional:
                raise
            return None
        except (ValueError, KeyError, TypeError) as e:
            if not is_optional:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Token validation failed: {str(e)}",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e
            return None


# Dependency function for accessing authenticated user
def get_current_user(request: Request) -> dict | None:
    """
    Get current authenticated user from request state.

    Args:
        request: HTTP request with authentication state

    Returns:
        Authenticated user information or None
    """
    return getattr(request.state, "authenticated_user", None)


def require_authenticated_user(request: Request) -> dict:
    """
    Get current authenticated user, raising exception if not authenticated.

    Args:
        request: HTTP request with authentication state

    Returns:
        Authenticated user information

    Raises:
        HTTPException: If user is not authenticated
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(permission: str) -> Callable[[Request], dict]:
    """
    Create dependency function that requires specific permission.

    Args:
        permission: Required permission

    Returns:
        Dependency function that validates permission
    """
    def check_permission(request: Request) -> dict:
        user = require_authenticated_user(request)
        if permission not in user.get("permissions", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return user

    return check_permission


def require_role(role: str) -> Callable[[Request], dict]:
    """
    Create dependency function that requires specific role.

    Args:
        role: Required role

    Returns:
        Dependency function that validates role
    """
    def check_role(request: Request) -> dict:
        user = require_authenticated_user(request)
        if role not in user.get("roles", []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required",
            )
        return user

    return check_role
