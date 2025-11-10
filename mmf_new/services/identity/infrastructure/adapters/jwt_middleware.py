"""
JWT Authentication Middleware.

Provides automatic JWT token validation for FastAPI applications
using the hexagonal architecture JWT components.
"""

from collections.abc import Callable

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from mmf_new.services.identity.application.use_cases import (
    ValidateTokenRequest,
    ValidateTokenUseCase,
)
from mmf_new.services.identity.domain.models import AuthenticatedUser
from mmf_new.services.identity.infrastructure.adapters import (
    JWTConfig,
    JWTTokenProvider,
)


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic JWT token validation.

    Validates JWT tokens on protected routes and injects
    the authenticated user into the request state.
    """

    def __init__(
        self,
        app,
        jwt_config: JWTConfig,
        protected_paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
    ):
        """
        Initialize JWT authentication middleware.

        Args:
            app: FastAPI application instance
            jwt_config: JWT configuration
            protected_paths: List of path patterns that require authentication
            exclude_paths: List of path patterns to exclude from authentication
        """
        super().__init__(app)
        self.token_provider = JWTTokenProvider(jwt_config)
        self.validate_use_case = ValidateTokenUseCase(self.token_provider)
        self.protected_paths = protected_paths or ["/api/", "/admin/"]
        self.exclude_paths = exclude_paths or [
            "/auth/",
            "/health",
            "/docs",
            "/openapi.json",
        ]

    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires authentication."""
        # Check if path is explicitly excluded
        for exclude_pattern in self.exclude_paths:
            if path.startswith(exclude_pattern):
                return False

        # Check if path is protected
        for protected_pattern in self.protected_paths:
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

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and validate JWT token if required."""
        # Check if this path requires authentication
        if not self._is_protected_path(request.url.path):
            return await call_next(request)

        # Extract token from request
        token = self._extract_token_from_request(request)

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Validate token
            validate_request = ValidateTokenRequest(token=token)
            result = await self.validate_use_case.execute(validate_request)

            if not result.is_valid or not result.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Add authenticated user to request state
            request.state.authenticated_user = result.user
            request.state.jwt_token = token

            return await call_next(request)

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Authentication error: {str(e)}",
            ) from e


class JWTBearer(HTTPBearer):
    """
    JWT Bearer token dependency for FastAPI.

    Provides a dependency for extracting and validating JWT tokens
    in individual route handlers.
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
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

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


def get_current_user_from_state(request: Request) -> AuthenticatedUser:
    """
    Get authenticated user from request state.

    This dependency can be used with JWTAuthenticationMiddleware
    to access the authenticated user in route handlers.

    Args:
        request: FastAPI request object

    Returns:
        AuthenticatedUser object from request state

    Raises:
        HTTPException: If user is not found in request state
    """
    user = getattr(request.state, "authenticated_user", None)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_permissions(*required_permissions: str) -> Callable:
    """
    Dependency factory for permission-based authorization.

    Args:
        required_permissions: Permission strings that the user must have

    Returns:
        Dependency function that validates user permissions
    """

    def permission_checker(user: AuthenticatedUser = None) -> AuthenticatedUser:
        """Check if user has required permissions."""
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        missing_permissions = set(required_permissions) - user.permissions

        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {', '.join(missing_permissions)}",
            )

        return user

    return permission_checker


def require_roles(*required_roles: str) -> Callable:
    """
    Dependency factory for role-based authorization.

    Args:
        required_roles: Role strings that the user must have

    Returns:
        Dependency function that validates user roles
    """

    def role_checker(user: AuthenticatedUser = None) -> AuthenticatedUser:
        """Check if user has required roles."""
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        if not user.has_any_role(set(required_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required roles: {', '.join(required_roles)}",
            )

        return user

    return role_checker
