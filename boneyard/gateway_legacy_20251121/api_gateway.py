"""
Enterprise API Gateway Infrastructure.

Provides comprehensive API gateway capabilities for microservices architecture
including routing, rate limiting, authentication, load balancing, and service aggregation.

Features:
- Dynamic routing with path/host-based rules
- Rate limiting with multiple algorithms (token bucket, sliding window)
- Authentication and authorization (JWT, API keys, OAuth2)
- Load balancing across service instances
- Request/response transformation
- Circuit breaker pattern for resilience
- Metrics and monitoring
- Service discovery integration
- WebSocket support
- API versioning
"""

import asyncio
import builtins
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# HTTP client imports
import aiohttp
import jwt
from marty_msf.framework.config.injection import container

logger = logging.getLogger(__name__)


class RoutingMethod(Enum):
    """HTTP methods for routing."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    ANY = "*"


class LoadBalancingAlgorithm(Enum):
    """Load balancing algorithms."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    IP_HASH = "ip_hash"
    HEALTH_BASED = "health_based"


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithms."""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class AuthenticationType(Enum):
    """Authentication types."""

    NONE = "none"
    API_KEY = "api_key"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    BASIC_AUTH = "basic_auth"
    CUSTOM = "custom"


@dataclass
class ServiceInstance:
    """Service instance configuration."""

    id: str
    host: str
    port: int
    weight: int = 1
    healthy: bool = True
    connections: int = 0
    last_health_check: float = field(default_factory=time.time)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    @property
    def url(self) -> str:
        """Get service URL."""
        return f"http://{self.host}:{self.port}"

    def increment_connections(self) -> None:
        """Increment connection count."""
        self.connections += 1

    def decrement_connections(self) -> None:
        """Decrement connection count."""
        self.connections = max(0, self.connections - 1)


@dataclass
class RouteRule:
    """Route matching rule."""

    path_pattern: str
    methods: builtins.list[RoutingMethod] = field(default_factory=lambda: [RoutingMethod.ANY])
    host_pattern: str | None = None
    headers: builtins.dict[str, str] = field(default_factory=dict)
    query_params: builtins.dict[str, str] = field(default_factory=dict)
    priority: int = 0

    def matches(
        self,
        method: str,
        path: str,
        host: str | None = None,
        headers: builtins.dict[str, str] | None = None,
        query_params: builtins.dict[str, str] | None = None,
    ) -> bool:
        """Check if request matches this rule."""
        # Check method
        if (
            RoutingMethod.ANY not in self.methods
            and RoutingMethod(method.upper()) not in self.methods
        ):
            return False

        # Check path pattern
        if not re.match(self.path_pattern, path):
            return False

        # Check host pattern
        if self.host_pattern and host:
            if not re.match(self.host_pattern, host):
                return False

        # Check headers
        if self.headers and headers:
            for key, pattern in self.headers.items():
                if key not in headers or not re.match(pattern, headers[key]):
                    return False

        # Check query parameters
        if self.query_params and query_params:
            for key, pattern in self.query_params.items():
                if key not in query_params or not re.match(pattern, query_params[key]):
                    return False

        return True


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    requests_per_second: float = 100.0
    burst_size: int = 200
    window_size: int = 60
    key_extractor: Callable | None = None

    def get_key(self, request_data: builtins.dict[str, Any]) -> str:
        """Extract rate limiting key from request."""
        if self.key_extractor:
            return self.key_extractor(request_data)

        # Default to client IP
        return request_data.get("client_ip", "unknown")


@dataclass
class AuthConfig:
    """Authentication configuration."""

    type: AuthenticationType = AuthenticationType.NONE
    secret_key: str | None = None
    api_key_header: str = "X-API-Key"
    jwt_algorithm: str = "HS256"
    jwt_expiry: int = 3600
    oauth2_endpoint: str | None = None
    custom_validator: Callable | None = None


@dataclass
class RouteConfig:
    """Route configuration."""

    name: str
    rule: RouteRule
    target_service: str
    path_rewrite: str | None = None
    timeout: float = 30.0
    retries: int = 3
    auth: AuthConfig = field(default_factory=AuthConfig)
    rate_limit: RateLimitConfig | None = None
    load_balancing: LoadBalancingAlgorithm = LoadBalancingAlgorithm.ROUND_ROBIN
    circuit_breaker: bool = True
    request_transformers: builtins.list[Callable] = field(default_factory=list)
    response_transformers: builtins.list[Callable] = field(default_factory=list)


@dataclass
class GatewayStats:
    """API Gateway statistics."""

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    avg_response_time: float = 0.0
    active_connections: int = 0

    def record_request(self, success: bool, response_time: float) -> None:
        """Record request statistics."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        # Update average response time
        self.avg_response_time = (
            self.avg_response_time * (self.total_requests - 1) + response_time
        ) / self.total_requests


class RateLimiter(ABC):
    """Abstract rate limiter interface."""

    @abstractmethod
    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset rate limiter for key."""


class TokenBucketRateLimiter(RateLimiter):
    """Token bucket rate limiter."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.buckets: builtins.dict[str, builtins.dict[str, float]] = {}

    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""
        now = time.time()

        if key not in self.buckets:
            self.buckets[key] = {
                "tokens": float(self.config.burst_size),
                "last_refill": now,
            }

        bucket = self.buckets[key]

        # Refill tokens
        time_passed = now - bucket["last_refill"]
        tokens_to_add = time_passed * self.config.requests_per_second
        bucket["tokens"] = min(self.config.burst_size, bucket["tokens"] + tokens_to_add)
        bucket["last_refill"] = now

        # Check if request is allowed
        if bucket["tokens"] >= 1.0:
            bucket["tokens"] -= 1.0
            return True

        return False

    async def reset(self, key: str) -> None:
        """Reset rate limiter for key."""
        if key in self.buckets:
            del self.buckets[key]


class LoadBalancer(ABC):
    """Abstract load balancer interface."""

    @abstractmethod
    async def select_instance(
        self,
        instances: builtins.list[ServiceInstance],
        request_data: builtins.dict[str, Any] | None = None,
    ) -> ServiceInstance | None:
        """Select service instance."""


class RoundRobinLoadBalancer(LoadBalancer):
    """Round robin load balancer."""

    def __init__(self):
        self.counters: builtins.dict[str, int] = {}

    async def select_instance(
        self,
        instances: builtins.list[ServiceInstance],
        request_data: builtins.dict[str, Any] | None = None,
    ) -> ServiceInstance | None:
        """Select service instance using round robin."""
        healthy_instances = [i for i in instances if i.healthy]

        if not healthy_instances:
            return None

        service_key = f"{healthy_instances[0].host}:{healthy_instances[0].port}"

        if service_key not in self.counters:
            self.counters[service_key] = 0

        instance = healthy_instances[self.counters[service_key] % len(healthy_instances)]
        self.counters[service_key] += 1

        return instance


class LeastConnectionsLoadBalancer(LoadBalancer):
    """Least connections load balancer."""

    async def select_instance(
        self,
        instances: builtins.list[ServiceInstance],
        request_data: builtins.dict[str, Any] | None = None,
    ) -> ServiceInstance | None:
        """Select instance with least connections."""
        healthy_instances = [i for i in instances if i.healthy]

        if not healthy_instances:
            return None

        return min(healthy_instances, key=lambda i: i.connections)


class Authenticator(ABC):
    """Abstract authenticator interface."""

    @abstractmethod
    async def authenticate(
        self, request_data: builtins.dict[str, Any]
    ) -> builtins.tuple[bool, builtins.dict[str, Any] | None]:
        """Authenticate request. Returns (success, user_context)."""


class JWTAuthenticator(Authenticator):
    """JWT token authenticator."""

    def __init__(self, config: AuthConfig):
        self.config = config
        try:
            self.jwt = jwt
        except ImportError:
            raise ImportError("JWT authentication requires PyJWT: pip install PyJWT")

    async def authenticate(
        self, request_data: builtins.dict[str, Any]
    ) -> builtins.tuple[bool, builtins.dict[str, Any] | None]:
        """Authenticate JWT token."""
        try:
            auth_header = request_data.get("headers", {}).get("Authorization", "")

            if not auth_header.startswith("Bearer "):
                return False, None

            token = auth_header[7:]  # Remove 'Bearer ' prefix

            payload = self.jwt.decode(
                token, self.config.secret_key, algorithms=[self.config.jwt_algorithm]
            )

            return True, payload

        except Exception as e:
            logger.warning(f"JWT authentication failed: {e}")
            return False, None


class APIKeyAuthenticator(Authenticator):
    """API key authenticator."""

    def __init__(
        self,
        config: AuthConfig,
        valid_keys: builtins.dict[str, builtins.dict[str, Any]],
    ):
        self.config = config
        self.valid_keys = valid_keys  # key -> user_context mapping

    async def authenticate(
        self, request_data: builtins.dict[str, Any]
    ) -> builtins.tuple[bool, builtins.dict[str, Any] | None]:
        """Authenticate API key."""
        headers = request_data.get("headers", {})
        api_key = headers.get(self.config.api_key_header)

        if not api_key:
            return False, None

        if api_key in self.valid_keys:
            return True, self.valid_keys[api_key]

        return False, None


class CircuitBreaker:
    """Circuit breaker for service resilience."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)

            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"

            raise e


class ServiceRegistry:
    """Service discovery and registry."""

    def __init__(self):
        self.services: builtins.dict[str, builtins.list[ServiceInstance]] = {}
        self.health_check_interval = 30.0
        self._health_check_task: asyncio.Task | None = None

    async def register_service(self, service_name: str, instance: ServiceInstance) -> None:
        """Register service instance."""
        if service_name not in self.services:
            self.services[service_name] = []

        # Remove existing instance with same ID
        self.services[service_name] = [
            i for i in self.services[service_name] if i.id != instance.id
        ]

        self.services[service_name].append(instance)
        logger.info(f"Registered service instance: {service_name}/{instance.id}")

    async def deregister_service(self, service_name: str, instance_id: str) -> None:
        """Deregister service instance."""
        if service_name in self.services:
            self.services[service_name] = [
                i for i in self.services[service_name] if i.id != instance_id
            ]
            logger.info(f"Deregistered service instance: {service_name}/{instance_id}")

    async def get_service_instances(self, service_name: str) -> builtins.list[ServiceInstance]:
        """Get healthy service instances."""
        return self.services.get(service_name, [])

    async def start_health_checks(self) -> None:
        """Start background health checks."""
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop_health_checks(self) -> None:
        """Stop background health checks."""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                for _service_name, instances in self.services.items():
                    for instance in instances:
                        await self._check_instance_health(instance)

                await asyncio.sleep(self.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(5.0)

    async def _check_instance_health(self, instance: ServiceInstance) -> None:
        """Check individual instance health."""
        try:
            async with aiohttp.ClientSession() as session:
                health_url = f"{instance.url}/health"
                async with session.get(health_url, timeout=5.0) as response:
                    instance.healthy = response.status == 200
                    instance.last_health_check = time.time()

        except Exception:
            instance.healthy = False
            instance.last_health_check = time.time()


class APIGateway:
    """Enterprise API Gateway."""

    def __init__(self):
        self.routes: builtins.list[RouteConfig] = []
        self.service_registry = ServiceRegistry()
        self.load_balancers: builtins.dict[LoadBalancingAlgorithm, LoadBalancer] = {
            LoadBalancingAlgorithm.ROUND_ROBIN: RoundRobinLoadBalancer(),
            LoadBalancingAlgorithm.LEAST_CONNECTIONS: LeastConnectionsLoadBalancer(),
        }
        self.rate_limiters: builtins.dict[str, RateLimiter] = {}
        self.authenticators: builtins.dict[str, Authenticator] = {}
        self.circuit_breakers: builtins.dict[str, CircuitBreaker] = {}
        self.stats = GatewayStats()

    async def start(self) -> None:
        """Start API Gateway."""
        await self.service_registry.start_health_checks()
        logger.info("API Gateway started")

    async def stop(self) -> None:
        """Stop API Gateway."""
        await self.service_registry.stop_health_checks()
        logger.info("API Gateway stopped")

    def add_route(self, route: RouteConfig) -> None:
        """Add route configuration."""
        # Sort routes by priority (higher priority first)
        self.routes.append(route)
        self.routes.sort(key=lambda r: r.rule.priority, reverse=True)

        # Initialize rate limiter if needed
        if route.rate_limit:
            self.rate_limiters[route.name] = TokenBucketRateLimiter(route.rate_limit)

        # Initialize circuit breaker if needed
        if route.circuit_breaker:
            self.circuit_breakers[route.name] = CircuitBreaker()

        logger.info(f"Added route: {route.name}")

    def add_authenticator(self, name: str, authenticator: Authenticator) -> None:
        """Add authenticator."""
        self.authenticators[name] = authenticator

    async def register_service(self, service_name: str, instance: ServiceInstance) -> None:
        """Register service instance."""
        await self.service_registry.register_service(service_name, instance)

    async def handle_request(
        self, request_data: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Handle incoming request."""
        start_time = time.time()

        try:
            # Find matching route
            route = await self._find_route(request_data)
            if not route:
                return self._create_error_response(404, "Route not found")

            # Rate limiting
            if route.rate_limit and not await self._check_rate_limit(route, request_data):
                self.stats.rate_limited_requests += 1
                return self._create_error_response(429, "Rate limit exceeded")

            # Authentication
            if not await self._authenticate_request(route, request_data):
                return self._create_error_response(401, "Authentication failed")

            # Load balancing
            instance = await self._select_service_instance(route, request_data)
            if not instance:
                return self._create_error_response(503, "Service unavailable")

            # Forward request
            response = await self._forward_request(route, instance, request_data)

            # Record success
            response_time = time.time() - start_time
            self.stats.record_request(True, response_time)

            return response

        except Exception as e:
            logger.error(f"Request handling error: {e}")
            response_time = time.time() - start_time
            self.stats.record_request(False, response_time)
            return self._create_error_response(500, "Internal server error")

    async def _find_route(self, request_data: builtins.dict[str, Any]) -> RouteConfig | None:
        """Find matching route for request."""
        method = request_data.get("method", "GET")
        path = request_data.get("path", "/")
        host = request_data.get("host")
        headers = request_data.get("headers", {})
        query_params = request_data.get("query_params", {})

        for route in self.routes:
            if route.rule.matches(method, path, host, headers, query_params):
                return route

        return None

    async def _check_rate_limit(
        self, route: RouteConfig, request_data: builtins.dict[str, Any]
    ) -> bool:
        """Check rate limiting."""
        if not route.rate_limit:
            return True

        rate_limiter = self.rate_limiters.get(route.name)
        if not rate_limiter:
            return True

        key = route.rate_limit.get_key(request_data)
        return await rate_limiter.is_allowed(key)

    async def _authenticate_request(
        self, route: RouteConfig, request_data: builtins.dict[str, Any]
    ) -> bool:
        """Authenticate request."""
        if route.auth.type == AuthenticationType.NONE:
            return True

        authenticator_name = f"{route.name}_{route.auth.type.value}"
        authenticator = self.authenticators.get(authenticator_name)

        if not authenticator:
            return False

        success, user_context = await authenticator.authenticate(request_data)

        if success and user_context:
            request_data["user_context"] = user_context

        return success

    async def _select_service_instance(
        self, route: RouteConfig, request_data: builtins.dict[str, Any]
    ) -> ServiceInstance | None:
        """Select service instance using load balancing."""
        instances = await self.service_registry.get_service_instances(route.target_service)

        if not instances:
            return None

        load_balancer = self.load_balancers.get(route.load_balancing)
        if not load_balancer:
            load_balancer = self.load_balancers[LoadBalancingAlgorithm.ROUND_ROBIN]

        return await load_balancer.select_instance(instances, request_data)

    async def _forward_request(
        self,
        route: RouteConfig,
        instance: ServiceInstance,
        request_data: builtins.dict[str, Any],
    ) -> builtins.dict[str, Any]:
        """Forward request to service instance."""
        # aiohttp is required for HTTP client functionality

        # Transform request
        for transformer in route.request_transformers:
            request_data = transformer(request_data)

        # Build target URL
        path = request_data.get("path", "/")
        if route.path_rewrite:
            path = route.path_rewrite

        target_url = f"{instance.url}{path}"

        # Add query parameters
        query_params = request_data.get("query_params", {})
        if query_params:
            query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
            target_url += f"?{query_string}"

        instance.increment_connections()

        try:
            # Execute with circuit breaker
            circuit_breaker = self.circuit_breakers.get(route.name)

            if circuit_breaker:
                response_data = await circuit_breaker.call(
                    self._make_http_request, target_url, request_data, route.timeout
                )
            else:
                response_data = await self._make_http_request(
                    target_url, request_data, route.timeout
                )

            # Transform response
            for transformer in route.response_transformers:
                response_data = transformer(response_data)

            return response_data

        finally:
            instance.decrement_connections()

    async def _make_http_request(
        self, url: str, request_data: builtins.dict[str, Any], timeout: float
    ) -> builtins.dict[str, Any]:
        """Make HTTP request to service."""
        method = request_data.get("method", "GET")
        headers = request_data.get("headers", {})
        body = request_data.get("body")

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                data=body,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                response_body = await response.text()

                return {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response_body,
                }

    def _create_error_response(self, status: int, message: str) -> builtins.dict[str, Any]:
        """Create error response."""
        return {
            "status": status,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": message}),
        }

    async def get_stats(self) -> GatewayStats:
        """Get gateway statistics."""
        return self.stats


def get_gateway() -> APIGateway | None:
    """Get API gateway from container."""
    return container.get("api_gateway")


def create_gateway() -> APIGateway:
    """Create and register API gateway with container."""
    return container.get_or_create("api_gateway", lambda: APIGateway())


@asynccontextmanager
async def gateway_context():
    """Context manager for API gateway lifecycle."""
    gateway = create_gateway()
    await gateway.start()

    try:
        yield gateway
    finally:
        await gateway.stop()


# Utility functions for common patterns
def create_jwt_auth_route(
    name: str,
    path_pattern: str,
    target_service: str,
    secret_key: str,
    methods: builtins.list[RoutingMethod] = None,
) -> RouteConfig:
    """Create route with JWT authentication."""
    return RouteConfig(
        name=name,
        rule=RouteRule(path_pattern=path_pattern, methods=methods or [RoutingMethod.ANY]),
        target_service=target_service,
        auth=AuthConfig(type=AuthenticationType.JWT, secret_key=secret_key),
    )


def create_rate_limited_route(
    name: str,
    path_pattern: str,
    target_service: str,
    requests_per_second: float = 100.0,
    methods: builtins.list[RoutingMethod] = None,
) -> RouteConfig:
    """Create route with rate limiting."""
    return RouteConfig(
        name=name,
        rule=RouteRule(path_pattern=path_pattern, methods=methods or [RoutingMethod.ANY]),
        target_service=target_service,
        rate_limit=RateLimitConfig(requests_per_second=requests_per_second),
    )
