"""
Authentication Middleware for Microservices Framework

Provides JWT-based authentication middleware with support for:
- JWT token validation
- Role-based access control (RBAC)
- Rate limiting per user
- Security headers
- Audit logging
"""

import builtins
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

import jwt
import redis.asyncio as redis
from fastapi import HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class SecurityConfig:
    """Security configuration for authentication middleware"""

    def __init__(
        self,
        jwt_secret_key: str,
        jwt_algorithm: str = "HS256",
        jwt_expiration_hours: int = 24,
        rate_limit_requests: int = 100,
        rate_limit_window_seconds: int = 3600,
        redis_url: str | None = None,
        enable_audit_logging: bool = True,
        allowed_origins: builtins.list[str] | None = None,
    ):
        self.jwt_secret_key = jwt_secret_key
        self.jwt_algorithm = jwt_algorithm
        self.jwt_expiration_hours = jwt_expiration_hours
        self.rate_limit_requests = rate_limit_requests
        self.rate_limit_window_seconds = rate_limit_window_seconds
        self.redis_url = redis_url
        self.enable_audit_logging = enable_audit_logging
        self.allowed_origins = allowed_origins or ["*"]


class JWTAuthenticator:
    """JWT token authentication and validation"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.security = HTTPBearer()

    def create_access_token(
        self,
        user_id: str,
        roles: builtins.list[str],
        extra_claims: builtins.dict | None = None,
    ) -> str:
        """Create a JWT access token"""
        to_encode = {
            "sub": user_id,
            "roles": roles,
            "exp": datetime.utcnow() + timedelta(hours=self.config.jwt_expiration_hours),
            "iat": datetime.utcnow(),
            "type": "access_token",
        }

        if extra_claims:
            to_encode.update(extra_claims)

        encoded_jwt = jwt.encode(
            to_encode, self.config.jwt_secret_key, algorithm=self.config.jwt_algorithm
        )
        return encoded_jwt

    def verify_token(self, token: str) -> builtins.dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret_key,
                algorithms=[self.config.jwt_algorithm],
            )

            # Validate token type
            if payload.get("type") != "access_token":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        except jwt.JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e!s}",
            )

    async def get_current_user(
        self, credentials: HTTPAuthorizationCredentials
    ) -> builtins.dict[str, Any]:
        """Extract and validate current user from JWT token"""
        token = credentials.credentials
        payload = self.verify_token(token)

        user_data = {
            "user_id": payload.get("sub"),
            "roles": payload.get("roles", []),
            "claims": payload,
        }

        return user_data


class RateLimiter:
    """Redis-based rate limiter"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.redis_client = None
        if config.redis_url:
            self.redis_client = redis.from_url(config.redis_url)

    async def is_rate_limited(self, user_id: str, endpoint: str) -> bool:
        """Check if user is rate limited for specific endpoint"""
        if not self.redis_client:
            return False

        key = f"rate_limit:{user_id}:{endpoint}"
        current_time = int(time.time())
        window_start = current_time - self.config.rate_limit_window_seconds

        try:
            # Clean old entries
            await self.redis_client.zremrangebyscore(key, 0, window_start)

            # Count current requests
            current_count = await self.redis_client.zcard(key)

            if current_count >= self.config.rate_limit_requests:
                return True

            # Add current request
            await self.redis_client.zadd(key, {str(current_time): current_time})
            await self.redis_client.expire(key, self.config.rate_limit_window_seconds)

            return False

        except Exception as e:
            logger.error(f"Rate limiting error: {e}")
            return False


class SecurityAuditor:
    """Security audit logging"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.audit_logger = logging.getLogger("security.audit")

    async def log_authentication(
        self,
        user_id: str,
        endpoint: str,
        method: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        reason: str | None = None,
    ):
        """Log authentication attempt"""
        if not self.config.enable_audit_logging:
            return

        audit_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "authentication",
            "user_id": user_id,
            "endpoint": endpoint,
            "method": method,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "reason": reason,
        }

        self.audit_logger.info(f"AUTH_EVENT: {audit_event}")

    async def log_authorization(
        self,
        user_id: str,
        endpoint: str,
        required_roles: builtins.list[str],
        user_roles: builtins.list[str],
        success: bool,
    ):
        """Log authorization attempt"""
        if not self.config.enable_audit_logging:
            return

        audit_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "authorization",
            "user_id": user_id,
            "endpoint": endpoint,
            "required_roles": required_roles,
            "user_roles": user_roles,
            "success": success,
        }

        self.audit_logger.info(f"AUTHZ_EVENT: {audit_event}")


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Main authentication middleware"""

    def __init__(
        self,
        app,
        config: SecurityConfig,
        excluded_paths: builtins.list[str] | None = None,
    ):
        super().__init__(app)
        self.config = config
        self.authenticator = JWTAuthenticator(config)
        self.rate_limiter = RateLimiter(config)
        self.auditor = SecurityAuditor(config)
        self.excluded_paths = excluded_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch method"""
        start_time = time.time()

        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths:
            response = await call_next(request)
            return self._add_security_headers(response)

        # Extract client info
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        try:
            # Extract and validate JWT token
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                await self.auditor.log_authentication(
                    "anonymous",
                    request.url.path,
                    request.method,
                    client_ip,
                    user_agent,
                    False,
                    "Missing authorization header",
                )
                return self._unauthorized_response("Missing authorization header")

            token = auth_header.split(" ")[1]
            user_data = self.authenticator.verify_token(token)
            user_id = user_data.get("sub")

            # Check rate limiting
            if await self.rate_limiter.is_rate_limited(user_id, request.url.path):
                await self.auditor.log_authentication(
                    user_id,
                    request.url.path,
                    request.method,
                    client_ip,
                    user_agent,
                    False,
                    "Rate limit exceeded",
                )
                return self._rate_limit_response()

            # Add user context to request
            request.state.user = user_data
            request.state.user_id = user_id
            request.state.user_roles = user_data.get("roles", [])

            # Log successful authentication
            await self.auditor.log_authentication(
                user_id, request.url.path, request.method, client_ip, user_agent, True
            )

            # Continue to next middleware/route
            response = await call_next(request)

            # Add timing header
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)

            return self._add_security_headers(response)

        except HTTPException as e:
            await self.auditor.log_authentication(
                "unknown",
                request.url.path,
                request.method,
                client_ip,
                user_agent,
                False,
                str(e.detail),
            )
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            await self.auditor.log_authentication(
                "unknown",
                request.url.path,
                request.method,
                client_ip,
                user_agent,
                False,
                f"Internal error: {e!s}",
            )
            return JSONResponse(
                status_code=500, content={"detail": "Internal authentication error"}
            )

    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    def _unauthorized_response(self, detail: str) -> JSONResponse:
        """Return unauthorized response"""
        return JSONResponse(status_code=401, content={"detail": detail})

    def _rate_limit_response(self) -> JSONResponse:
        """Return rate limit exceeded response"""
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded",
                "retry_after": self.config.rate_limit_window_seconds,
            },
        )


def require_roles(required_roles: builtins.list[str]):
    """Decorator to require specific roles for endpoint access"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user_roles = getattr(request.state, "user_roles", [])
            user_id = getattr(request.state, "user_id", "unknown")

            # Check if user has required roles
            if not any(role in user_roles for role in required_roles):
                # Log authorization failure
                config = SecurityConfig(jwt_secret_key="dummy")  # This should be injected properly
                auditor = SecurityAuditor(config)
                await auditor.log_authorization(
                    user_id, request.url.path, required_roles, user_roles, False
                )

                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required roles: {required_roles}",
                )

            # Log successful authorization
            config = SecurityConfig(jwt_secret_key="dummy")  # This should be injected properly
            auditor = SecurityAuditor(config)
            await auditor.log_authorization(
                user_id, request.url.path, required_roles, user_roles, True
            )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def get_current_user_dependency(config: SecurityConfig):
    """FastAPI dependency to get current user"""
    authenticator = JWTAuthenticator(config)

    async def get_current_user(credentials: HTTPAuthorizationCredentials = None):
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication credentials",
            )
        return await authenticator.get_current_user(credentials)

    return get_current_user


# Example usage functions
def create_authentication_middleware(
    jwt_secret_key: str,
    redis_url: str | None = None,
    excluded_paths: builtins.list[str] | None = None,
) -> AuthenticationMiddleware:
    """Factory function to create authentication middleware"""
    config = SecurityConfig(jwt_secret_key=jwt_secret_key, redis_url=redis_url)
    return AuthenticationMiddleware(config, excluded_paths=excluded_paths)


def setup_security_logging():
    """Setup security audit logging"""
    # Create security audit logger
    audit_logger = logging.getLogger("security.audit")
    audit_logger.setLevel(logging.INFO)

    # Create formatter for audit logs
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Create file handler for audit logs
    handler = logging.FileHandler("logs/security_audit.log")
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)

    return audit_logger
