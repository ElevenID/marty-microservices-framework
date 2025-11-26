"""
Security middleware for FastAPI and gRPC services.
"""

import builtins
import logging
from collections.abc import Callable
from typing import Any

import grpc
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..authentication.auth import (
    APIKeyAuthenticator,
    AuthenticatedUser,
    JWTAuthenticator,
    MTLSAuthenticator,
)

from mmf_new.infrastructure.dependency_injection import get_service, has_service
from mmf_new.core.security.ports.authentication import IAuthenticator
from mmf_new.core.security.ports.authorization import IAuthorizer
from mmf_new.core.security.domain.models.user import User, AuthenticatedUser
from mmf_new.core.security.domain.models.context import AuthorizationContext
from mmf_new.core.security.domain.config import SecurityConfig
from mmf_new.core.security.domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
)
from mmf_new.core.security.adapters.security_framework import initialize_security_system
from ..threat_management.rate_limiting import get_rate_limiter

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """Core security middleware that coordinates all security components."""

    def __init__(self, config: SecurityConfig):
        self.config = config

        # Ensure security services are initialized
        if not has_service(IAuthenticator):
            initialize_security_system(config)

        # Use DI container for RBAC if available
        self.rbac = None
        if has_service(IAuthorizer):
            self.rbac = get_service(IAuthorizer)

        self.rate_limiter = get_rate_limiter()

    async def authenticate_request(
        self, request_info: builtins.dict[str, Any]
    ) -> AuthenticatedUser | None:
        """Authenticate a request using available authenticators."""

        # Extract credentials
        credentials = self._extract_credentials_from_request(request_info)
        if credentials:
            authenticator = get_service(IAuthenticator)
            result = await authenticator.authenticate(credentials)
            if result.success and result.user:
                return result.user

        return None

    def _extract_credentials_from_request(
        self, request_info: builtins.dict[str, Any]
    ) -> dict[str, Any] | None:
        """Extract credentials from request info for canonical authentication."""
        credentials = {}

        # Extract authorization header
        auth_header = request_info.get("authorization")
        if auth_header:
            if auth_header.startswith("Bearer "):
                credentials["token"] = auth_header[7:]
                credentials["auth_type"] = "bearer"
                credentials["method"] = "JWT"
            elif auth_header.startswith("Basic "):
                credentials["token"] = auth_header[6:]
                credentials["auth_type"] = "basic"
                credentials["method"] = "BASIC"

        # Extract API key
        headers = request_info.get("headers", {})
        query_params = request_info.get("query_params", {})

        api_key = headers.get("x-api-key") or query_params.get("api_key")
        if api_key:
            credentials["api_key"] = api_key
            credentials["auth_type"] = "api_key"
            credentials["method"] = "API_KEY"

        # Extract client certificate for mTLS
        client_cert = request_info.get("client_cert")
        if client_cert:
            credentials["client_cert"] = client_cert
            credentials["auth_type"] = "mtls"

        return credentials if credentials else None

    async def check_rate_limit(
        self, request_info: builtins.dict[str, Any], user: AuthenticatedUser | None
    ) -> tuple[bool, builtins.dict[str, Any]]:
        """Check rate limits for the request."""
        if not self.rate_limiter or not self.rate_limiter.enabled:
            return True, {}

        # Use client IP as default identifier
        identifier = request_info.get("client_ip", "unknown")
        endpoint = request_info.get("endpoint")
        user_id = user.user_id if user else None

        return await self.rate_limiter.check_rate_limit(
            identifier=identifier, endpoint=endpoint, user_id=user_id
        )

    def add_security_headers(self, response: Response) -> None:
        """Add security headers to response."""
        for header, value in self.config.security_headers.items():
            response.headers[header] = value


class FastAPISecurityMiddleware(BaseHTTPMiddleware):
    """FastAPI-specific security middleware."""

    def __init__(self, app, config: SecurityConfig):
        super().__init__(app)
        self.security = SecurityMiddleware(config)
        self.config = config

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security pipeline."""

        # Skip security for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            response = await call_next(request)
            self.security.add_security_headers(response)
            return response

        try:
            # Extract request information
            request_info = {
                "authorization": request.headers.get("authorization"),
                "headers": dict(request.headers),
                "query_params": dict(request.query_params),
                "client_ip": getattr(request.client, "host", "unknown")
                if request.client
                else "unknown",
                "endpoint": request.url.path,
                "method": request.method,
            }

            # Add client certificate if available (for mTLS)
            if hasattr(request, "scope") and "client" in request.scope:
                client_info = request.scope.get("client", {})
                if "peercert" in client_info:
                    request_info["client_cert"] = client_info["peercert"]

            # Authenticate request
            user = await self.security.authenticate_request(request_info)

            # Check rate limits
            rate_limit_allowed, rate_limit_info = await self.security.check_rate_limit(
                request_info, user
            )
            if not rate_limit_allowed:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": rate_limit_info.get("retry_after", 60),
                    },
                    headers={
                        "Retry-After": str(rate_limit_info.get("retry_after", 60)),
                        "X-RateLimit-Limit": str(rate_limit_info.get("limit", "")),
                        "X-RateLimit-Remaining": str(rate_limit_info.get("remaining", "")),
                        "X-RateLimit-Reset": str(rate_limit_info.get("reset_time", "")),
                    },
                )

            # Store user in request state for use in endpoints
            if user:
                request.state.user = user
                request.state.authenticated = True
            else:
                request.state.user = None
                request.state.authenticated = False

            # Process request
            response = await call_next(request)

            # Add security headers
            self.security.add_security_headers(response)

            # Add rate limit headers
            if rate_limit_info:
                response.headers["X-RateLimit-Limit"] = str(rate_limit_info.get("limit", ""))
                response.headers["X-RateLimit-Remaining"] = str(
                    rate_limit_info.get("remaining", "")
                )
                response.headers["X-RateLimit-Reset"] = str(rate_limit_info.get("reset_time", ""))

            return response

        except Exception as e:
            logger.warning("Security error: %s", str(e))
            return JSONResponse(
                status_code=401,
                content={
                    "error": str(e),
                    "error_code": "SECURITY_ERROR",
                    "details": {},
                },
            )


class GRPCSecurityInterceptor(grpc.aio.ServerInterceptor):
    """gRPC security interceptor."""

    def __init__(self, config: SecurityConfig):
        self.security = SecurityMiddleware(config)
        self.config = config

    async def intercept_service(self, continuation, handler_call_details):
        """Intercept gRPC calls for security processing."""

        try:
            # Extract metadata
            metadata = dict(handler_call_details.invocation_metadata)

            # Extract request information
            request_info = {
                "authorization": metadata.get("authorization"),
                "headers": metadata,
                "query_params": {},
                "client_ip": "grpc_client",  # In real implementation, extract from context
                "endpoint": handler_call_details.method,
                "method": "GRPC",
            }

            # Authenticate request
            user = await self.security.authenticate_request(request_info)

            # Check rate limits
            rate_limit_allowed, rate_limit_info = await self.security.check_rate_limit(
                request_info, user
            )
            if not rate_limit_allowed:
                context = grpc.aio.ServicerContext()
                await context.abort(
                    grpc.StatusCode.RESOURCE_EXHAUSTED,
                    f"Rate limit exceeded. Retry after {rate_limit_info.get('retry_after', 60)} seconds",
                )

            # Store user context for use in service methods
            if user:
                # In a real implementation, you'd store this in the gRPC context
                # For now, we'll add it to the metadata
                pass

            # Continue with the request
            return await continuation(handler_call_details)

        except Exception as e:
            context = grpc.aio.ServicerContext()
            if isinstance(e, AuthenticationError):
                await context.abort(grpc.StatusCode.UNAUTHENTICATED, str(e))
            elif isinstance(e, AuthorizationError):
                await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(e))
            else:
                logger.error("Unexpected gRPC security error: %s", e)
                await context.abort(grpc.StatusCode.INTERNAL, "Security error")


class HTTPBearerOptional(HTTPBearer):
    """Optional HTTP Bearer authentication for FastAPI dependencies."""

    def __init__(self, auto_error: bool = False):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials | None:
        try:
            return await super().__call__(request)
        except HTTPException:
            return None


# Dependency functions for FastAPI
async def get_current_user(request: Request) -> AuthenticatedUser | None:
    """FastAPI dependency to get the current authenticated user."""
    return getattr(request.state, "user", None)


async def require_authentication(request: Request) -> AuthenticatedUser:
    """FastAPI dependency that requires authentication."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission_dependency(permission: str):
    """Create a FastAPI dependency that requires a specific permission."""

    async def dependency(
        user: AuthenticatedUser = Depends(require_authentication),
    ) -> AuthenticatedUser:
        # Use IAuthorizer
        if not has_service(IAuthorizer):
            return user

        authorizer = get_service(IAuthorizer)
        security_user = User(
            user_id=user.user_id, username=user.username or user.user_id, roles=user.roles
        )

        context = AuthorizationContext(
            user=security_user,
            resource="api",
            action=permission
        )
        result = authorizer.authorize(context)

        if not result.allowed:
            raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
        return user

    return dependency


def require_role_dependency(role: str):
    """Create a FastAPI dependency that requires a specific role."""

    async def dependency(
        user: AuthenticatedUser = Depends(require_authentication),
    ) -> AuthenticatedUser:
        # Use IAuthorizer
        if not has_service(IAuthorizer):
            return user

        authorizer = get_service(IAuthorizer)
        security_user = User(
            user_id=user.user_id, username=user.username or user.user_id, roles=user.roles
        )

        context = AuthorizationContext(
            user=security_user,
            resource="api",
            action=f"role:{role}"
        )
        result = authorizer.authorize(context)

        if not result.allowed:
            raise HTTPException(status_code=403, detail=f"Role required: {role}")
        return user

    return dependency
