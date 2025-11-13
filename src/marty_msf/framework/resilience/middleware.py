"""
Resilience Middleware Framework

Provides middleware components to integrate resilience patterns
(circuit breakers, bulkheads, connection pools) into FastAPI
and other service frameworks seamlessly.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from marty_msf.core.enhanced_di import get_service

from .api import IResilienceManager, ResilienceStrategy
from .bulkhead import BulkheadConfig, BulkheadError, SemaphoreBulkhead
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerError
from .connection_pools.http_pool import HTTPConnectionPool
from .connection_pools.manager import ConnectionPoolManager, get_pool_manager
from .connection_pools.redis_pool import RedisConnectionPool

logger = logging.getLogger(__name__)


@dataclass
class ResilienceConfig:
    """Configuration for resilience middleware"""

    # Circuit breaker settings
    enable_circuit_breaker: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    circuit_breaker_timeout: float = 30.0

    # Bulkhead settings
    enable_bulkhead: bool = True
    bulkhead_max_concurrent: int = 100
    bulkhead_timeout: float = 30.0

    # Connection pool settings
    enable_connection_pools: bool = True
    http_pool_name: str = "default"
    redis_pool_name: str = "default"

    # Rate limiting
    enable_rate_limiting: bool = True
    rate_limit_requests_per_minute: int = 1000
    rate_limit_burst_size: int = 100

    # Timeout settings
    request_timeout: float = 30.0

    # Metrics and monitoring
    enable_metrics: bool = True
    metrics_prefix: str = "resilience"

    # Excluded paths (don't apply resilience patterns)
    excluded_paths: list[str] = field(default_factory=lambda: ["/health", "/metrics", "/docs"])


class ResilienceMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for applying resilience patterns"""

    def __init__(self, app: FastAPI, config: ResilienceConfig):
        super().__init__(app)
        self.config = config
        self.circuit_breaker: CircuitBreaker | None = None
        self.bulkhead: SemaphoreBulkhead | None = None
        self.pool_manager: ConnectionPoolManager | None = None

        # Rate limiting state
        self._rate_limit_state: dict[str, list[float]] = {}
        self._rate_limit_lock = asyncio.Lock()

        # Metrics
        self.request_count = 0
        self.error_count = 0
        self.timeout_count = 0
        self.circuit_breaker_open_count = 0
        self.bulkhead_reject_count = 0
        self.rate_limit_reject_count = 0

        self._initialize_resilience_components()

    def _initialize_resilience_components(self):
        """Initialize resilience components"""
        try:
            # Initialize circuit breaker
            if self.config.enable_circuit_breaker:
                cb_config = CircuitBreakerConfig(
                    failure_threshold=self.config.circuit_breaker_failure_threshold,
                    timeout_seconds=int(self.config.circuit_breaker_recovery_timeout),
                )
                self.circuit_breaker = CircuitBreaker("middleware_cb", cb_config)

            # Initialize bulkhead
            if self.config.enable_bulkhead:
                bulkhead_config = BulkheadConfig(
                    max_concurrent=self.config.bulkhead_max_concurrent,
                    timeout_seconds=self.config.bulkhead_timeout,
                )
                self.bulkhead = SemaphoreBulkhead("middleware_bulkhead", bulkhead_config)

            logger.info("Resilience middleware components initialized")

        except Exception as e:
            logger.error(f"Failed to initialize resilience components: {e}")
            raise

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch method"""
        start_time = time.time()

        try:
            # Skip resilience patterns for excluded paths
            if any(request.url.path.startswith(path) for path in self.config.excluded_paths):
                return await call_next(request)

            self.request_count += 1

            # Apply rate limiting
            if self.config.enable_rate_limiting:
                if not await self._check_rate_limit(request):
                    self.rate_limit_reject_count += 1
                    raise HTTPException(status_code=429, detail="Rate limit exceeded")

            # Apply resilience patterns
            response = await self._handle_with_resilience(request, call_next)

            # Add resilience metrics to response headers
            if self.config.enable_metrics:
                self._add_metrics_headers(response)

            return response

        except HTTPException:
            raise
        except CircuitBreakerError:
            self.circuit_breaker_open_count += 1
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        except BulkheadError:
            self.bulkhead_reject_count += 1
            raise HTTPException(status_code=503, detail="Service at capacity")
        except asyncio.TimeoutError:
            self.timeout_count += 1
            raise HTTPException(status_code=504, detail="Request timeout")
        except Exception as e:
            self.error_count += 1
            logger.error(f"Resilience middleware error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        finally:
            duration = time.time() - start_time
            logger.debug(f"Request processed in {duration:.3f}s")

    async def _handle_with_resilience(self, request: Request, call_next: Callable) -> Response:
        """Apply resilience patterns to request handling"""

        async def execute_request():
            return await asyncio.wait_for(call_next(request), timeout=self.config.request_timeout)

        # Apply bulkhead isolation
        if self.config.enable_bulkhead and self.bulkhead:
            return await self.bulkhead.execute_async(execute_request)
        else:
            return await execute_request()

    async def _check_rate_limit(self, request: Request) -> bool:
        """Check if request is within rate limits"""
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        async with self._rate_limit_lock:
            # Clean old entries
            if client_ip in self._rate_limit_state:
                cutoff_time = current_time - 60  # 1 minute window
                self._rate_limit_state[client_ip] = [
                    req_time
                    for req_time in self._rate_limit_state[client_ip]
                    if req_time > cutoff_time
                ]
            else:
                self._rate_limit_state[client_ip] = []

            # Check rate limit
            request_times = self._rate_limit_state[client_ip]

            if len(request_times) >= self.config.rate_limit_requests_per_minute:
                return False

            # Add current request
            request_times.append(current_time)
            return True

    def _add_metrics_headers(self, response: Response):
        """Add resilience metrics to response headers"""
        headers = {
            f"X-{self.config.metrics_prefix}-Requests": str(self.request_count),
            f"X-{self.config.metrics_prefix}-Errors": str(self.error_count),
            f"X-{self.config.metrics_prefix}-Circuit-Breaker-Status": self.circuit_breaker.state.value
            if self.circuit_breaker
            else "disabled",
        }

        for key, value in headers.items():
            response.headers[key] = value

    def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive resilience metrics"""
        metrics = {
            "requests": {
                "total": self.request_count,
                "errors": self.error_count,
                "error_rate": self.error_count / max(self.request_count, 1),
            },
            "timeouts": self.timeout_count,
            "rate_limiting": {
                "rejections": self.rate_limit_reject_count,
                "active_clients": len(self._rate_limit_state),
            },
        }

        if self.circuit_breaker:
            metrics["circuit_breaker"] = {
                "state": self.circuit_breaker.state.value,
                "opens": self.circuit_breaker_open_count,
            }

        if self.bulkhead:
            stats = self.bulkhead.get_stats()
            metrics["bulkhead"] = {
                "rejections": self.bulkhead_reject_count,
                "active_requests": stats.get("active_requests", 0),
                "successful_requests": stats.get("successful_requests", 0),
                "failed_requests": stats.get("failed_requests", 0),
            }

        return metrics


class ResilienceService:
    """Service class for managing resilience components across the application"""

    def __init__(self, config: ResilienceConfig):
        self.config = config
        self.pool_manager: ConnectionPoolManager | None = None
        self._initialized = False

    async def initialize(self):
        """Initialize resilience service"""
        if self._initialized:
            return

        try:
            # Initialize connection pool manager if enabled
            if self.config.enable_connection_pools:
                self.pool_manager = get_pool_manager()

            self._initialized = True
            logger.info("Resilience service initialized")

        except Exception as e:
            logger.error(f"Failed to initialize resilience service: {e}")
            raise

    async def get_http_client(self) -> HTTPConnectionPool:
        """Get HTTP client with connection pooling"""
        if not self.pool_manager:
            raise RuntimeError("Connection pools not enabled")

        return await self.pool_manager.get_http_pool(self.config.http_pool_name)

    async def get_redis_client(self) -> RedisConnectionPool:
        """Get Redis client with connection pooling"""
        if not self.pool_manager:
            raise RuntimeError("Connection pools not enabled")

        return await self.pool_manager.get_redis_pool(self.config.redis_pool_name)

    @asynccontextmanager
    async def http_request(self, method: str, url: str, **kwargs):
        """Make HTTP request with resilience patterns"""
        http_pool = await self.get_http_client()

        try:
            response = await http_pool.request(method, url, **kwargs)
            yield response
        finally:
            if "response" in locals():
                response.close()

    async def close(self):
        """Close resilience service and cleanup resources"""
        if self.pool_manager:
            await self.pool_manager.close()

        self._initialized = False
        logger.info("Resilience service closed")


# Decorator for applying resilience patterns to functions
def resilient(
    circuit_breaker_config: CircuitBreakerConfig | None = None,
    bulkhead_config: BulkheadConfig | None = None,
    timeout: float | None = None,
    _retries: int = 0,
    _retry_delay: float = 1.0,
):
    """
    Decorator to apply resilience patterns to functions (not supported).

    This decorator is not supported. Use ConsolidatedResilienceManager.resilient_call() instead.
    """

    def decorator(func: Callable):
        raise NotImplementedError(
            "The resilient decorator is not supported. "
            "Use ConsolidatedResilienceManager.resilient_call() instead."
        )

    return decorator


# Service-based resilience service access


def get_resilience_service():
    """Get resilience service with pure interface approach (breaks circular dependency)."""

    # Create a basic resilience implementation inline to avoid imports
    class BasicResilienceManager(IResilienceManager):
        def __init__(self):
            self._metrics = {"total_operations": 0, "success_count": 0, "failure_count": 0}

        async def execute_resilient(
            self,
            func,
            strategy=ResilienceStrategy.INTERNAL_SERVICE,
            config_override=None,
            operation_name=None,
        ):
            try:
                result = await func() if asyncio.iscoroutinefunction(func) else func()
                self._metrics["success_count"] += 1
                return result
            except Exception:
                self._metrics["failure_count"] += 1
                raise
            finally:
                self._metrics["total_operations"] += 1

        def execute_resilient_sync(self, func, *args, **kwargs):
            try:
                result = func(*args, **kwargs)
                self._metrics["success_count"] += 1
                return result
            except Exception:
                self._metrics["failure_count"] += 1
                raise
            finally:
                self._metrics["total_operations"] += 1

        async def apply_resilience(self, func, *args, **kwargs):
            return await self.execute_resilient(lambda: func(*args, **kwargs))

        def get_metrics(self):
            return self._metrics.copy()

        async def health_check(self):
            return {"status": "healthy", "metrics": self.get_metrics()}

        def reset_metrics(self):
            self._metrics = {"total_operations": 0, "success_count": 0, "failure_count": 0}

        def update_config(self, config):
            pass

    return BasicResilienceManager()


async def close_resilience_service():
    """Close the resilience service (not supported - managed by DI container)."""
    raise NotImplementedError(
        "close_resilience_service is not supported. Use the DI container lifecycle management instead."
    )
