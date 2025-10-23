"""
Rate Limiting Middleware for Microservices Framework

Provides comprehensive rate limiting capabilities:
- Per-user rate limiting
- Per-IP rate limiting
- Per-endpoint rate limiting
- Sliding window algorithm
- Redis-based distributed rate limiting
- Custom rate limit configurations
"""

import asyncio
import builtins
import logging
import time
from dataclasses import dataclass

import redis.asyncio as redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    """Rate limit rule configuration"""

    requests: int  # Number of requests allowed
    window_seconds: int  # Time window in seconds
    burst_requests: int | None = None  # Burst limit
    burst_window_seconds: int | None = None  # Burst window


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""

    redis_url: str | None = None
    enabled: bool = True
    default_rule: RateLimitRule = None
    per_user_rules: builtins.dict[str, RateLimitRule] | None = None
    per_endpoint_rules: builtins.dict[str, RateLimitRule] | None = None
    per_ip_rules: builtins.dict[str, RateLimitRule] | None = None
    whitelist_ips: builtins.list[str] | None = None
    whitelist_users: builtins.list[str] | None = None
    enable_distributed: bool = True

    def __post_init__(self):
        if self.default_rule is None:
            self.default_rule = RateLimitRule(requests=100, window_seconds=3600)
        if self.per_user_rules is None:
            self.per_user_rules = {}
        if self.per_endpoint_rules is None:
            self.per_endpoint_rules = {}
        if self.per_ip_rules is None:
            self.per_ip_rules = {}
        if self.whitelist_ips is None:
            self.whitelist_ips = []
        if self.whitelist_users is None:
            self.whitelist_users = []


class SlidingWindowRateLimiter:
    """Sliding window rate limiter implementation"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.redis_client = None
        self.local_store = {}  # Fallback for non-distributed mode

        if config.redis_url and config.enable_distributed:
            self.redis_client = redis.from_url(config.redis_url)

    async def is_rate_limited(
        self, key: str, rule: RateLimitRule, current_time: float | None = None
    ) -> builtins.tuple[bool, builtins.dict[str, any]]:
        """
        Check if request should be rate limited

        Returns:
            Tuple of (is_limited, rate_limit_info)
        """
        if current_time is None:
            current_time = time.time()

        if self.redis_client:
            return await self._check_redis_rate_limit(key, rule, current_time)
        return await self._check_local_rate_limit(key, rule, current_time)

    async def _check_redis_rate_limit(
        self, key: str, rule: RateLimitRule, current_time: float
    ) -> builtins.tuple[bool, builtins.dict[str, any]]:
        """Redis-based rate limiting"""
        window_start = current_time - rule.window_seconds

        try:
            pipe = self.redis_client.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests
            pipe.zcard(key)

            # Add current request with score as timestamp
            pipe.zadd(key, {str(current_time): current_time})

            # Set expiration
            pipe.expire(key, rule.window_seconds)

            results = await pipe.execute()
            current_count = results[1] + 1  # +1 for the request we just added

            # Check burst limits if configured
            burst_limited = False
            if rule.burst_requests and rule.burst_window_seconds:
                burst_start = current_time - rule.burst_window_seconds
                burst_count = await self.redis_client.zcount(key, burst_start, current_time)
                if burst_count > rule.burst_requests:
                    burst_limited = True

            is_limited = current_count > rule.requests or burst_limited

            # If rate limited, remove the request we added
            if is_limited:
                await self.redis_client.zrem(key, str(current_time))

            rate_limit_info = {
                "limit": rule.requests,
                "remaining": max(0, rule.requests - current_count + (1 if is_limited else 0)),
                "reset_time": current_time + rule.window_seconds,
                "retry_after": rule.window_seconds if is_limited else 0,
                "burst_limited": burst_limited,
            }

            return is_limited, rate_limit_info

        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            # Fallback to allowing request on Redis errors
            return False, {"error": "Rate limiting unavailable"}

    async def _check_local_rate_limit(
        self, key: str, rule: RateLimitRule, current_time: float
    ) -> builtins.tuple[bool, builtins.dict[str, any]]:
        """Local in-memory rate limiting (fallback)"""
        if key not in self.local_store:
            self.local_store[key] = []

        requests = self.local_store[key]
        window_start = current_time - rule.window_seconds

        # Remove old requests
        requests[:] = [req_time for req_time in requests if req_time > window_start]

        # Check if rate limited
        current_count = len(requests)
        is_limited = current_count >= rule.requests

        # Add current request if not limited
        if not is_limited:
            requests.append(current_time)

        rate_limit_info = {
            "limit": rule.requests,
            "remaining": max(0, rule.requests - current_count),
            "reset_time": current_time + rule.window_seconds,
            "retry_after": rule.window_seconds if is_limited else 0,
        }

        return is_limited, rate_limit_info

    async def get_rate_limit_key(
        self, request: Request, user_id: str | None = None
    ) -> builtins.list[builtins.tuple[str, RateLimitRule]]:
        """Generate rate limit keys and rules for a request"""
        keys_and_rules = []

        # Client IP
        client_ip = request.client.host if request.client else "unknown"
        if client_ip not in self.config.whitelist_ips:
            # Per-IP rate limiting
            ip_rule = self.config.per_ip_rules.get(client_ip, self.config.default_rule)
            keys_and_rules.append((f"ip:{client_ip}", ip_rule))

        # User-based rate limiting
        if user_id and user_id not in self.config.whitelist_users:
            user_rule = self.config.per_user_rules.get(user_id, self.config.default_rule)
            keys_and_rules.append((f"user:{user_id}", user_rule))

        # Endpoint-based rate limiting
        endpoint = f"{request.method}:{request.url.path}"
        endpoint_rule = self.config.per_endpoint_rules.get(endpoint)
        if endpoint_rule:
            keys_and_rules.append((f"endpoint:{endpoint}", endpoint_rule))

        return keys_and_rules

    async def cleanup_expired_keys(self):
        """Clean up expired keys (for local storage)"""
        if self.redis_client:
            return  # Redis handles expiration automatically

        current_time = time.time()
        keys_to_remove = []

        for key, requests in self.local_store.items():
            # Find the latest window for any rule (use default rule window)
            window_start = current_time - self.config.default_rule.window_seconds
            active_requests = [req for req in requests if req > window_start]

            if not active_requests:
                keys_to_remove.append(key)
            else:
                self.local_store[key] = active_requests

        for key in keys_to_remove:
            del self.local_store[key]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""

    def __init__(
        self,
        app,
        config: RateLimitConfig,
        excluded_paths: builtins.list[str] | None = None,
    ):
        super().__init__(app)
        self.config = config
        self.rate_limiter = SlidingWindowRateLimiter(config)
        self.excluded_paths = excluded_paths or ["/health", "/metrics"]

        # Start cleanup task for local storage
        if not config.enable_distributed:
            asyncio.create_task(self._cleanup_task())

    async def dispatch(self, request: Request, call_next):
        """Main middleware dispatch method"""
        if not self.config.enabled:
            return await call_next(request)

        # Skip rate limiting for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)

        # Get user ID from request state (set by auth middleware)
        user_id = getattr(request.state, "user_id", None)

        try:
            # Get rate limit keys and rules
            keys_and_rules = await self.rate_limiter.get_rate_limit_key(request, user_id)

            # Check all applicable rate limits
            rate_limit_info = None
            for key, rule in keys_and_rules:
                is_limited, info = await self.rate_limiter.is_rate_limited(key, rule)

                if is_limited:
                    # Log rate limit hit
                    client_ip = request.client.host if request.client else "unknown"
                    logger.warning(
                        f"Rate limit exceeded - Key: {key}, IP: {client_ip}, "
                        f"User: {user_id}, Endpoint: {request.method} {request.url.path}"
                    )

                    return self._rate_limit_response(info, key)

                # Keep the most restrictive rate limit info for headers
                if rate_limit_info is None or info.get(
                    "remaining", float("inf")
                ) < rate_limit_info.get("remaining", float("inf")):
                    rate_limit_info = info

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            if rate_limit_info:
                response.headers["X-RateLimit-Limit"] = str(rate_limit_info.get("limit", "unknown"))
                response.headers["X-RateLimit-Remaining"] = str(
                    rate_limit_info.get("remaining", "unknown")
                )
                response.headers["X-RateLimit-Reset"] = str(
                    int(rate_limit_info.get("reset_time", 0))
                )

            return response

        except Exception as e:
            logger.error(f"Rate limiting middleware error: {e}")
            # Continue processing on rate limiting errors
            return await call_next(request)

    def _rate_limit_response(self, rate_limit_info: builtins.dict, key: str) -> JSONResponse:
        """Return rate limit exceeded response"""
        retry_after = rate_limit_info.get("retry_after", 60)

        response = JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests for {key}",
                "retry_after": retry_after,
                "limit": rate_limit_info.get("limit"),
                "reset_time": rate_limit_info.get("reset_time"),
            },
        )

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info.get("limit", "unknown"))
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(int(rate_limit_info.get("reset_time", 0)))
        response.headers["Retry-After"] = str(retry_after)

        return response

    async def _cleanup_task(self):
        """Background task to clean up expired local storage entries"""
        while True:
            try:
                await asyncio.sleep(300)  # Clean up every 5 minutes
                await self.rate_limiter.cleanup_expired_keys()
            except Exception as e:
                logger.error(f"Rate limiter cleanup task error: {e}")


def create_rate_limit_config(
    redis_url: str | None = None,
    default_requests_per_hour: int = 1000,
    enable_per_user_limits: bool = True,
    enable_per_ip_limits: bool = True,
    api_tier_limits: builtins.dict[str, RateLimitRule] | None = None,
) -> RateLimitConfig:
    """Factory function to create rate limit configuration"""

    # Default API tier limits
    if api_tier_limits is None:
        api_tier_limits = {
            "free": RateLimitRule(requests=100, window_seconds=3600),
            "premium": RateLimitRule(requests=1000, window_seconds=3600),
            "enterprise": RateLimitRule(requests=10000, window_seconds=3600),
        }

    # Common endpoint-specific limits
    endpoint_rules = {
        "POST:/auth/login": RateLimitRule(
            requests=5, window_seconds=300
        ),  # 5 login attempts per 5 min
        "POST:/auth/register": RateLimitRule(
            requests=3, window_seconds=3600
        ),  # 3 registrations per hour
        "POST:/api/upload": RateLimitRule(requests=10, window_seconds=3600),  # 10 uploads per hour
        "GET:/api/search": RateLimitRule(
            requests=100, window_seconds=300
        ),  # 100 searches per 5 min
    }

    config = RateLimitConfig(
        redis_url=redis_url,
        enabled=True,
        default_rule=RateLimitRule(requests=default_requests_per_hour, window_seconds=3600),
        per_endpoint_rules=endpoint_rules,
        enable_distributed=redis_url is not None,
    )

    return config


def create_rate_limit_middleware(
    redis_url: str | None = None,
    default_requests_per_hour: int = 1000,
    excluded_paths: builtins.list[str] | None = None,
) -> RateLimitMiddleware:
    """Factory function to create rate limiting middleware"""
    config = create_rate_limit_config(
        redis_url=redis_url, default_requests_per_hour=default_requests_per_hour
    )

    return RateLimitMiddleware(config, excluded_paths=excluded_paths)


# Decorator for custom endpoint rate limits
def rate_limit(requests: int, window_seconds: int, burst_requests: int | None = None):
    """Decorator to apply custom rate limits to specific endpoints"""

    def decorator(func):
        func._rate_limit_rule = RateLimitRule(
            requests=requests,
            window_seconds=window_seconds,
            burst_requests=burst_requests,
        )
        return func

    return decorator


# FastAPI dependency for rate limit information
async def get_rate_limit_info(request: Request) -> builtins.dict[str, any]:
    """FastAPI dependency to get current rate limit information"""
    return {
        "headers": {
            "limit": request.headers.get("X-RateLimit-Limit"),
            "remaining": request.headers.get("X-RateLimit-Remaining"),
            "reset": request.headers.get("X-RateLimit-Reset"),
        }
    }
