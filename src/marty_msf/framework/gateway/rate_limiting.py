"""
Rate Limiting Module for API Gateway

Advanced rate limiting implementation with multiple algorithms, storage backends,
and sophisticated quota management for API traffic control.
"""

import builtins
import datetime
import hashlib
import io
import logging
import math
import pickle
import sys
import threading
import time
import warnings
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .core import GatewayRequest, GatewayResponse

logger = logging.getLogger(__name__)


class RestrictedUnpickler(pickle.Unpickler):
    """Restricted unpickler that only allows safe types to prevent code execution."""

    SAFE_BUILTINS = {
        "str",
        "int",
        "float",
        "bool",
        "list",
        "tuple",
        "dict",
        "set",
        "frozenset",
        "bytes",
        "bytearray",
        "complex",
        "type",
        "slice",
        "range",
    }

    def find_class(self, module, name):
        # Only allow safe built-in types and specific allowed modules
        if module == "builtins" and name in self.SAFE_BUILTINS:
            return getattr(builtins, name)
        # Allow datetime objects which are commonly used in rate limiting
        if module == "datetime" and name in {"datetime", "date", "time", "timedelta"}:

            return getattr(datetime, name)
        # Allow rate limiting state classes
        if module.endswith("rate_limiting") and name in {"RateLimitState"}:
            # Allow our own rate limiting classes

            return getattr(sys.modules[module], name)
        # Block everything else
        raise pickle.UnpicklingError(f"Forbidden class {module}.{name}")


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithm types."""

    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW_LOG = "sliding_window_log"
    SLIDING_WINDOW_COUNTER = "sliding_window_counter"


class RateLimitAction(Enum):
    """Actions to take when rate limit is exceeded."""

    REJECT = "reject"
    DELAY = "delay"
    THROTTLE = "throttle"
    LOG_ONLY = "log_only"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    # Basic settings
    requests_per_window: int = 100
    window_size_seconds: int = 60
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW_COUNTER

    # Action settings
    action: RateLimitAction = RateLimitAction.REJECT
    delay_seconds: float = 1.0
    throttle_factor: float = 0.5

    # Key generation
    key_function: Callable[[GatewayRequest], str] | None = None
    include_ip: bool = True
    include_user_id: bool = True
    include_api_key: bool = True
    include_path: bool = False

    # Advanced settings
    burst_size: int = 0  # For token bucket (0 = no burst)
    leak_rate: float = 1.0  # For leaky bucket
    backoff_factor: float = 2.0
    max_delay: float = 60.0

    # Headers
    include_limit_headers: bool = True
    retry_after_header: bool = True

    # Storage
    storage_key_prefix: str = "rate_limit"
    cleanup_interval: int = 300  # 5 minutes


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_time: float
    retry_after: float | None = None
    delay_seconds: float | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitState:
    """Current state of rate limiting for a key."""

    requests: int = 0
    tokens: float = 0.0
    last_request_time: float = 0.0
    window_start: float = 0.0
    request_times: builtins.list[float] = field(default_factory=list)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


class RateLimitStorage(ABC):
    """Abstract storage backend for rate limiting."""

    @abstractmethod
    def get_state(self, key: str) -> RateLimitState | None:
        """Get rate limit state for key."""
        raise NotImplementedError

    @abstractmethod
    def set_state(self, key: str, state: RateLimitState, ttl: int | None = None):
        """Set rate limit state for key."""
        raise NotImplementedError

    @abstractmethod
    def delete_state(self, key: str):
        """Delete rate limit state for key."""
        raise NotImplementedError

    @abstractmethod
    def cleanup_expired(self):
        """Clean up expired state entries."""
        raise NotImplementedError


class MemoryRateLimitStorage(RateLimitStorage):
    """In-memory storage for rate limiting (single instance only)."""

    def __init__(self):
        self._storage: builtins.dict[str, builtins.tuple[RateLimitState, float]] = {}
        self._lock = threading.RLock()

    def get_state(self, key: str) -> RateLimitState | None:
        """Get state from memory."""
        with self._lock:
            entry = self._storage.get(key)
            if entry:
                state, expires_at = entry
                if time.time() < expires_at:
                    return state
                # Expired, remove it
                del self._storage[key]
        return None

    def set_state(self, key: str, state: RateLimitState, ttl: int | None = None):
        """Set state in memory."""
        expires_at = time.time() + (ttl or 3600)  # Default 1 hour TTL
        with self._lock:
            self._storage[key] = (state, expires_at)

    def delete_state(self, key: str):
        """Delete state from memory."""
        with self._lock:
            self._storage.pop(key, None)

    def cleanup_expired(self):
        """Clean up expired entries."""
        current_time = time.time()
        with self._lock:
            expired_keys = [
                key for key, (_, expires_at) in self._storage.items() if current_time >= expires_at
            ]
            for key in expired_keys:
                del self._storage[key]


class RedisRateLimitStorage(RateLimitStorage):
    """Redis storage for rate limiting (distributed)."""

    def __init__(self, redis_client, key_prefix: str = "rate_limit"):
        self.redis = redis_client
        self.key_prefix = key_prefix

    def _make_key(self, key: str) -> str:
        """Create Redis key."""
        return f"{self.key_prefix}:{key}"

    def get_state(self, key: str) -> RateLimitState | None:
        """Get state from Redis."""
        try:
            data = self.redis.get(self._make_key(key))
            if data:
                # Security: Use restricted unpickler to prevent arbitrary code execution
                warnings.warn(
                    "Pickle deserialization is potentially unsafe. Consider using JSON for better security.",
                    UserWarning,
                    stacklevel=2,
                )
                return RestrictedUnpickler(io.BytesIO(data)).load()
        except Exception as e:
            logger.error(f"Error getting rate limit state: {e}")
        return None

    def set_state(self, key: str, state: RateLimitState, ttl: int | None = None):
        """Set state in Redis."""
        try:

            data = pickle.dumps(state)
            redis_key = self._make_key(key)
            if ttl:
                self.redis.setex(redis_key, ttl, data)
            else:
                self.redis.set(redis_key, data)
        except Exception as e:
            logger.error(f"Error setting rate limit state: {e}")

    def delete_state(self, key: str):
        """Delete state from Redis."""
        try:
            self.redis.delete(self._make_key(key))
        except Exception as e:
            logger.error(f"Error deleting rate limit state: {e}")

    def cleanup_expired(self):
        """Redis handles expiration automatically."""


class RateLimiter(ABC):
    """Abstract rate limiter interface."""

    def __init__(self, config: RateLimitConfig, storage: RateLimitStorage):
        self.config = config
        self.storage = storage

    @abstractmethod
    def check_rate_limit(self, key: str, request_time: float = None) -> RateLimitResult:
        """Check if request is within rate limit."""
        raise NotImplementedError

    def generate_key(self, request: GatewayRequest) -> str:
        """Generate rate limiting key for request."""
        if self.config.key_function:
            return self.config.key_function(request)

        key_parts = []

        if self.config.include_ip:
            ip = request.get_header("X-Forwarded-For") or request.get_header("X-Real-IP")
            if ip:
                # Take first IP in case of comma-separated list
                ip = ip.split(",")[0].strip()
                key_parts.append(f"ip:{ip}")

        if self.config.include_user_id:
            user_id = request.get_header("X-User-ID") or request.get_header("Authorization")
            if user_id:
                # Hash authorization header for privacy
                if user_id.startswith("Bearer "):
                    user_id = hashlib.sha256(user_id.encode()).hexdigest()[:16]
                key_parts.append(f"user:{user_id}")

        if self.config.include_api_key:
            api_key = request.get_header("X-API-Key")
            if api_key:
                key_parts.append(f"key:{api_key}")

        if self.config.include_path:
            key_parts.append(f"path:{request.path}")

        # Fallback to IP if no other identifiers
        if not key_parts and self.config.include_ip:
            ip = "unknown"
            key_parts.append(f"ip:{ip}")

        return ":".join(key_parts)


class TokenBucketRateLimiter(RateLimiter):
    """Token bucket rate limiting algorithm."""

    def check_rate_limit(self, key: str, request_time: float = None) -> RateLimitResult:
        """Check rate limit using token bucket algorithm."""
        if request_time is None:
            request_time = time.time()

        state = self.storage.get_state(key) or RateLimitState()

        # Initialize if first request
        if state.last_request_time == 0:
            state.tokens = float(self.config.requests_per_window)
            state.last_request_time = request_time

        # Calculate tokens to add based on time elapsed
        time_elapsed = request_time - state.last_request_time
        tokens_to_add = time_elapsed * (
            self.config.requests_per_window / self.config.window_size_seconds
        )

        # Determine bucket capacity
        bucket_capacity = self.config.requests_per_window
        if self.config.burst_size > 0:
            bucket_capacity += self.config.burst_size

        # Add tokens and cap at bucket capacity
        state.tokens = min(bucket_capacity, state.tokens + tokens_to_add)
        state.last_request_time = request_time

        # Check if we have tokens available
        if state.tokens >= 1.0:
            # Allow request and consume token
            state.tokens -= 1.0
            allowed = True
            remaining = int(state.tokens)
        else:
            # Rate limit exceeded
            allowed = False
            remaining = 0

        # Calculate reset time (when bucket will have tokens again)
        if state.tokens < 1.0:
            time_to_token = (1.0 - state.tokens) / (
                self.config.requests_per_window / self.config.window_size_seconds
            )
            reset_time = request_time + time_to_token
        else:
            reset_time = request_time

        # Save state
        self.storage.set_state(key, state, self.config.window_size_seconds * 2)

        return RateLimitResult(
            allowed=allowed,
            limit=self.config.requests_per_window,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=reset_time - request_time if not allowed else None,
        )


class LeakyBucketRateLimiter(RateLimiter):
    """Leaky bucket rate limiting algorithm."""

    def check_rate_limit(self, key: str, request_time: float = None) -> RateLimitResult:
        """Check rate limit using leaky bucket algorithm."""
        if request_time is None:
            request_time = time.time()

        state = self.storage.get_state(key) or RateLimitState()

        # Initialize if first request
        if state.last_request_time == 0:
            state.requests = 0
            state.last_request_time = request_time

        # Calculate requests leaked since last check
        time_elapsed = request_time - state.last_request_time
        leaked_requests = time_elapsed * self.config.leak_rate

        # Remove leaked requests
        state.requests = max(0, state.requests - leaked_requests)
        state.last_request_time = request_time

        # Check if bucket has capacity
        if state.requests < self.config.requests_per_window:
            # Allow request and add to bucket
            state.requests += 1
            allowed = True
            remaining = int(self.config.requests_per_window - state.requests)
        else:
            # Bucket is full
            allowed = False
            remaining = 0

        # Calculate reset time (when bucket will have capacity)
        if state.requests >= self.config.requests_per_window:
            time_to_capacity = (
                state.requests - self.config.requests_per_window + 1
            ) / self.config.leak_rate
            reset_time = request_time + time_to_capacity
        else:
            reset_time = request_time

        # Save state
        self.storage.set_state(key, state, self.config.window_size_seconds * 2)

        return RateLimitResult(
            allowed=allowed,
            limit=self.config.requests_per_window,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=reset_time - request_time if not allowed else None,
        )


class FixedWindowRateLimiter(RateLimiter):
    """Fixed window rate limiting algorithm."""

    def check_rate_limit(self, key: str, request_time: float = None) -> RateLimitResult:
        """Check rate limit using fixed window algorithm."""
        if request_time is None:
            request_time = time.time()

        # Calculate current window
        window_start = (
            int(request_time // self.config.window_size_seconds) * self.config.window_size_seconds
        )

        state = self.storage.get_state(key) or RateLimitState()

        # Reset if new window
        if state.window_start != window_start:
            state.window_start = window_start
            state.requests = 0

        # Check if within limit
        if state.requests < self.config.requests_per_window:
            # Allow request
            state.requests += 1
            allowed = True
            remaining = self.config.requests_per_window - state.requests
        else:
            # Rate limit exceeded
            allowed = False
            remaining = 0

        # Calculate reset time (start of next window)
        reset_time = window_start + self.config.window_size_seconds

        # Save state
        self.storage.set_state(key, state, self.config.window_size_seconds + 60)

        return RateLimitResult(
            allowed=allowed,
            limit=self.config.requests_per_window,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=reset_time - request_time if not allowed else None,
        )


class SlidingWindowLogRateLimiter(RateLimiter):
    """Sliding window log rate limiting algorithm."""

    def check_rate_limit(self, key: str, request_time: float = None) -> RateLimitResult:
        """Check rate limit using sliding window log algorithm."""
        if request_time is None:
            request_time = time.time()

        state = self.storage.get_state(key) or RateLimitState()

        # Remove requests outside current window
        window_start = request_time - self.config.window_size_seconds
        state.request_times = [t for t in state.request_times if t > window_start]

        # Check if within limit
        if len(state.request_times) < self.config.requests_per_window:
            # Allow request
            state.request_times.append(request_time)
            allowed = True
            remaining = self.config.requests_per_window - len(state.request_times)
        else:
            # Rate limit exceeded
            allowed = False
            remaining = 0

        # Calculate reset time (when oldest request falls out of window)
        if state.request_times:
            reset_time = state.request_times[0] + self.config.window_size_seconds
        else:
            reset_time = request_time

        # Save state
        self.storage.set_state(key, state, self.config.window_size_seconds + 60)

        return RateLimitResult(
            allowed=allowed,
            limit=self.config.requests_per_window,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=reset_time - request_time if not allowed else None,
        )


class SlidingWindowCounterRateLimiter(RateLimiter):
    """Sliding window counter rate limiting algorithm."""

    def check_rate_limit(self, key: str, request_time: float = None) -> RateLimitResult:
        """Check rate limit using sliding window counter algorithm."""
        if request_time is None:
            request_time = time.time()

        # Calculate current and previous windows
        window_size = self.config.window_size_seconds
        current_window = int(request_time // window_size) * window_size
        previous_window = current_window - window_size

        # Get or create state
        state = self.storage.get_state(key) or RateLimitState()

        # Initialize window tracking if needed
        if not hasattr(state, "current_window_count"):
            state.current_window_count = 0
            state.previous_window_count = 0
            state.current_window_start = current_window
            state.previous_window_start = previous_window

        # Update window counts if we've moved to a new window
        if current_window != state.current_window_start:
            state.previous_window_count = state.current_window_count
            state.previous_window_start = state.current_window_start
            state.current_window_count = 0
            state.current_window_start = current_window

        # Calculate weighted count using sliding window
        time_in_current_window = request_time - current_window
        weight_for_previous = 1.0 - (time_in_current_window / window_size)

        weighted_count = state.current_window_count + (
            state.previous_window_count * weight_for_previous
        )

        # Check if within limit
        if weighted_count < self.config.requests_per_window:
            # Allow request
            state.current_window_count += 1
            allowed = True
            remaining = max(0, int(self.config.requests_per_window - weighted_count - 1))
        else:
            # Rate limit exceeded
            allowed = False
            remaining = 0

        # Calculate reset time (start of next window)
        reset_time = current_window + window_size

        # Save state
        self.storage.set_state(key, state, window_size * 2)

        return RateLimitResult(
            allowed=allowed,
            limit=self.config.requests_per_window,
            remaining=remaining,
            reset_time=reset_time,
            retry_after=reset_time - request_time if not allowed else None,
        )


class RateLimitMiddleware:
    """Rate limiting middleware for API Gateway."""

    def __init__(self, config: RateLimitConfig, storage: RateLimitStorage = None):
        self.config = config
        self.storage = storage or MemoryRateLimitStorage()
        self.rate_limiter = self._create_rate_limiter()
        self._cleanup_timer = None
        self._start_cleanup_timer()

    def _create_rate_limiter(self) -> RateLimiter:
        """Create rate limiter based on algorithm."""
        algorithm_map = {
            RateLimitAlgorithm.TOKEN_BUCKET: TokenBucketRateLimiter,
            RateLimitAlgorithm.LEAKY_BUCKET: LeakyBucketRateLimiter,
            RateLimitAlgorithm.FIXED_WINDOW: FixedWindowRateLimiter,
            RateLimitAlgorithm.SLIDING_WINDOW_LOG: SlidingWindowLogRateLimiter,
            RateLimitAlgorithm.SLIDING_WINDOW_COUNTER: SlidingWindowCounterRateLimiter,
        }

        limiter_class = algorithm_map.get(self.config.algorithm)
        if not limiter_class:
            raise ValueError(f"Unsupported rate limiting algorithm: {self.config.algorithm}")

        return limiter_class(self.config, self.storage)

    def _start_cleanup_timer(self):
        """Start periodic cleanup of expired entries."""

        def cleanup():
            try:
                self.storage.cleanup_expired()
            except Exception as e:
                logger.error(f"Error during rate limit cleanup: {e}")
            finally:
                # Schedule next cleanup

                self._cleanup_timer = threading.Timer(self.config.cleanup_interval, cleanup)
                self._cleanup_timer.daemon = True
                self._cleanup_timer.start()

        if self.config.cleanup_interval > 0:
            cleanup()

    def process_request(self, request: GatewayRequest) -> GatewayResponse | None:
        """Process request for rate limiting."""
        try:
            # Generate rate limiting key
            key = self.rate_limiter.generate_key(request)

            # Check rate limit
            result = self.rate_limiter.check_rate_limit(key)

            # Add rate limit headers if configured
            if self.config.include_limit_headers:
                request.context.metadata["rate_limit_headers"] = {
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": str(result.remaining),
                    "X-RateLimit-Reset": str(int(result.reset_time)),
                }

            # Handle rate limit exceeded
            if not result.allowed:
                logger.warning(f"Rate limit exceeded for key: {key}")

                # Add retry-after header
                if self.config.retry_after_header and result.retry_after:
                    headers = request.context.metadata.get("rate_limit_headers", {})
                    headers["Retry-After"] = str(int(math.ceil(result.retry_after)))
                    request.context.metadata["rate_limit_headers"] = headers

                # Take action based on configuration
                if self.config.action == RateLimitAction.REJECT:
                    return self._create_rate_limit_response(result)
                if self.config.action == RateLimitAction.DELAY:
                    return self._handle_delay(request, result)
                if self.config.action == RateLimitAction.THROTTLE:
                    return self._handle_throttle(request, result)
                # LOG_ONLY: just log and continue

            return None  # Continue processing

        except Exception as e:
            logger.error(f"Error in rate limiting middleware: {e}")
            # Continue processing on error to avoid blocking requests
            return None

    def _create_rate_limit_response(self, result: RateLimitResult) -> GatewayResponse:
        """Create rate limit exceeded response."""

        response = GatewayResponse(
            status_code=429,
            body="Rate limit exceeded. Please try again later.",
            content_type="text/plain",
        )

        # Add rate limit headers
        if result.retry_after:
            response.set_header("Retry-After", str(int(math.ceil(result.retry_after))))

        response.set_header("X-RateLimit-Limit", str(result.limit))
        response.set_header("X-RateLimit-Remaining", str(result.remaining))
        response.set_header("X-RateLimit-Reset", str(int(result.reset_time)))

        return response

    def _handle_delay(
        self, request: GatewayRequest, result: RateLimitResult
    ) -> GatewayResponse | None:
        """Handle delay action."""
        delay = min(self.config.delay_seconds, self.config.max_delay)

        # Store delay in request context for processing
        request.context.metadata["rate_limit_delay"] = delay

        # Continue processing (delay would be handled by gateway)
        return None

    def _handle_throttle(
        self, request: GatewayRequest, result: RateLimitResult
    ) -> GatewayResponse | None:
        """Handle throttle action."""
        # Store throttle factor in request context
        request.context.metadata["rate_limit_throttle"] = self.config.throttle_factor

        # Continue processing (throttling would be handled by gateway)
        return None

    def stop(self):
        """Stop the middleware and cleanup."""
        if self._cleanup_timer:
            self._cleanup_timer.cancel()


class RateLimitManager:
    """Manager for multiple rate limiters with different policies."""

    def __init__(self):
        self.limiters: builtins.dict[str, RateLimitMiddleware] = {}
        self.rules: builtins.list[builtins.tuple[Callable[[GatewayRequest], bool], str]] = []

    def add_limiter(self, name: str, config: RateLimitConfig, storage: RateLimitStorage = None):
        """Add rate limiter with given name."""
        self.limiters[name] = RateLimitMiddleware(config, storage)

    def add_rule(self, predicate: Callable[[GatewayRequest], bool], limiter_name: str):
        """Add rule for selecting rate limiter."""
        self.rules.append((predicate, limiter_name))

    def process_request(self, request: GatewayRequest) -> GatewayResponse | None:
        """Process request with appropriate rate limiter."""
        # Find matching rule
        for predicate, limiter_name in self.rules:
            if predicate(request):
                limiter = self.limiters.get(limiter_name)
                if limiter:
                    return limiter.process_request(request)

        # No matching rule
        return None

    def stop_all(self):
        """Stop all rate limiters."""
        for limiter in self.limiters.values():
            limiter.stop()


# Convenience functions
def create_token_bucket_limiter(
    requests_per_minute: int = 60,
    burst_size: int = 10,
    storage: RateLimitStorage = None,
) -> RateLimitMiddleware:
    """Create token bucket rate limiter."""
    config = RateLimitConfig(
        requests_per_window=requests_per_minute,
        window_size_seconds=60,
        algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
        burst_size=burst_size,
    )
    return RateLimitMiddleware(config, storage)


def create_sliding_window_limiter(
    requests_per_minute: int = 60, storage: RateLimitStorage = None
) -> RateLimitMiddleware:
    """Create sliding window counter rate limiter."""
    config = RateLimitConfig(
        requests_per_window=requests_per_minute,
        window_size_seconds=60,
        algorithm=RateLimitAlgorithm.SLIDING_WINDOW_COUNTER,
    )
    return RateLimitMiddleware(config, storage)


def create_per_ip_limiter(
    requests_per_minute: int = 60, storage: RateLimitStorage = None
) -> RateLimitMiddleware:
    """Create per-IP rate limiter."""
    config = RateLimitConfig(
        requests_per_window=requests_per_minute,
        window_size_seconds=60,
        include_ip=True,
        include_user_id=False,
        include_api_key=False,
    )
    return RateLimitMiddleware(config, storage)


def create_per_user_limiter(
    requests_per_minute: int = 1000, storage: RateLimitStorage = None
) -> RateLimitMiddleware:
    """Create per-user rate limiter."""
    config = RateLimitConfig(
        requests_per_window=requests_per_minute,
        window_size_seconds=60,
        include_ip=False,
        include_user_id=True,
        include_api_key=False,
    )
    return RateLimitMiddleware(config, storage)
