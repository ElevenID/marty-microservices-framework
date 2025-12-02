"""
JWT Authentication Middleware for FastAPI.

This module provides middleware for automatic JWT token extraction and validation
in FastAPI applications, enabling seamless authentication for protected routes.

# NOTE: For advanced authorization scenarios including RBAC hierarchies, ABAC policies,
# and policy engines, see mmf.framework.authorization module. This module provides
# decorator-based authorization (@require_role, @require_permission, @require_rbac, @require_abac)
# that can be used as alternatives to the inline checks in this middleware.

"""

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from mmf.services.identity.application.use_cases import (
    ValidateTokenRequest,
    ValidateTokenUseCase,
)
from mmf.services.identity.domain.models import AuthenticatedUser
from mmf.services.identity.infrastructure.adapters import JWTConfig, JWTTokenProvider


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for JWT authentication.

    Automatically extracts and validates JWT tokens from Authorization headers,
    making authenticated user information available to downstream handlers.

    Supports both exact path matching and pattern-based matching for flexible
    route protection.
    """

    def __init__(
        self,
        app,
        jwt_config: JWTConfig,
        excluded_paths: list[str] | None = None,
        optional_paths: list[str] | None = None,
        use_pattern_matching: bool = False,
    ):
        """
        Initialize JWT authentication middleware.

        Args:
            app: FastAPI application instance
            jwt_config: JWT configuration
            excluded_paths: Paths that skip authentication entirely
            optional_paths: Paths where authentication is optional (token validated if present)
            use_pattern_matching: If True, use startswith pattern matching instead of exact matches
        """
        super().__init__(app)
        self.token_provider = JWTTokenProvider(jwt_config)
        self.validate_use_case = ValidateTokenUseCase(self.token_provider)
        self.use_pattern_matching = use_pattern_matching

        # Default excluded paths (public endpoints)
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/auth/jwt/health",
        ]

        # Paths where authentication is optional
        self.optional_paths = optional_paths or []

    def _is_excluded_path(self, path: str) -> bool:
        """Check if path is excluded from authentication."""
        if self.use_pattern_matching:
            return any(path.startswith(pattern) for pattern in self.excluded_paths)
        return path in self.excluded_paths

    def _is_optional_path(self, path: str) -> bool:
        """Check if authentication is optional for this path."""
        if self.use_pattern_matching:
            return any(path.startswith(pattern) for pattern in self.optional_paths)
        return path in self.optional_paths

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
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
        if self._is_excluded_path(request.url.path):
            return await call_next(request)

        # Extract token from Authorization header
        token = await self._extract_token(request)

        # Check if authentication is optional for this path
        is_optional = self._is_optional_path(request.url.path)

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

    async def _validate_token(
        self, token: str, is_optional: bool = False
    ) -> AuthenticatedUser | None:
        """
        Validate JWT token and extract user information.

        Args:
            token: JWT token to validate
            is_optional: Whether validation failure should be ignored

        Returns:
            AuthenticatedUser object if token is valid, None otherwise

        Raises:
            HTTPException: For validation failures on required authentication
        """
        try:
            # Execute token validation
            request = ValidateTokenRequest(token=token)
            result = await self.validate_use_case.execute(request)

            if result.is_valid and result.user:
                return result.user
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


class JWTBearer(HTTPBearer):
    """
    JWT Bearer token dependency for FastAPI route handlers.

    Provides a dependency for extracting and validating JWT tokens
    at the individual route level, useful when you need more fine-grained
    control over authentication than middleware provides.

    Example:
        ```python
        from fastapi import Depends

        jwt_bearer = JWTBearer(jwt_config)

        @app.get("/protected")
        async def protected_route(user: AuthenticatedUser = Depends(jwt_bearer)):
            return {"user_id": user.user_id}
        ```
    """

    def __init__(self, jwt_config: JWTConfig, auto_error: bool = True):
        """
        Initialize JWT Bearer dependency.

        Args:
            jwt_config: JWT configuration
            auto_error: Whether to automatically raise HTTPException on validation failure
        """
        super().__init__(auto_error=auto_error)
        self.token_provider = JWTTokenProvider(jwt_config)
        self.validate_use_case = ValidateTokenUseCase(self.token_provider)

    async def __call__(self, request: Request) -> AuthenticatedUser:
        """
        Validate JWT token and return authenticated user.

        Args:
            request: FastAPI request object

        Returns:
            AuthenticatedUser object if token is valid

        Raises:
            HTTPException: If token is invalid or missing
        """
        # Get token from request
        credentials: HTTPAuthorizationCredentials | None = await super().__call__(request)

        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Validate token
            validate_request = ValidateTokenRequest(token=credentials.credentials)
            result = await self.validate_use_case.execute(validate_request)

            if not result.is_valid or not result.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return result.user

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Token validation failed: {str(e)}",
            ) from e


# Dependency functions for accessing authenticated user
def get_current_user(request: Request) -> AuthenticatedUser | None:
    """
    Get current authenticated user from request state.

    Args:
        request: HTTP request with authentication state

    Returns:
        Authenticated user information or None
    """
    return getattr(request.state, "authenticated_user", None)


def require_authenticated_user(request: Request) -> AuthenticatedUser:
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


def require_permission(permission: str) -> Callable[[Request], AuthenticatedUser]:
    """
    Create dependency function that requires specific permission.

    Args:
        permission: Required permission

    Returns:
        Dependency function that validates permission
    """

    def check_permission(request: Request) -> AuthenticatedUser:
        user = require_authenticated_user(request)
        if permission not in user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return user

    return check_permission


def require_role(role: str) -> Callable[[Request], AuthenticatedUser]:
    """
    Create dependency function that requires specific role.

    Args:
        role: Required role

    Returns:
        Dependency function that validates role
    """

    def check_role(request: Request) -> AuthenticatedUser:
        user = require_authenticated_user(request)
        if role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required",
            )
        return user

    return check_role
