"""
Core API Gateway Components

Fundamental abstractions, interfaces, and base classes for the API gateway
framework including request/response handling, routing, middleware, and plugins.
"""

import asyncio
import builtins
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HTTPMethod(Enum):
    """HTTP methods supported by the gateway."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"
    CONNECT = "CONNECT"


class GatewayError(Exception):
    """Base exception for gateway errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: builtins.dict[str, Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class RouteNotFoundError(GatewayError):
    """Raised when no route matches the request."""

    def __init__(self, path: str, method: str):
        super().__init__(f"No route found for {method} {path}", 404)
        self.path = path
        self.method = method


class AuthenticationError(GatewayError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401)


class AuthorizationError(GatewayError):
    """Raised when authorization fails."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message, 403)


class RateLimitExceededError(GatewayError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(message, 429)
        self.retry_after = retry_after


class UpstreamError(GatewayError):
    """Raised when upstream service fails."""

    def __init__(self, message: str, upstream_status: int = None):
        super().__init__(message, 502)
        self.upstream_status = upstream_status


@dataclass
class GatewayRequest:
    """Gateway request object."""

    # Basic request information
    method: HTTPMethod
    path: str
    query_params: builtins.dict[str, builtins.list[str]] = field(default_factory=dict)
    headers: builtins.dict[str, str] = field(default_factory=dict)
    body: bytes | None = None

    # Client information
    client_ip: str | None = None
    user_agent: str | None = None

    # Request metadata
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    # Processing context
    route_params: builtins.dict[str, str] = field(default_factory=dict)
    context: builtins.dict[str, Any] = field(default_factory=dict)

    def get_header(self, name: str, default: str = None) -> str | None:
        """Get header value (case-insensitive)."""
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value
        return default

    def get_query_param(self, name: str, default: str = None) -> str | None:
        """Get first query parameter value."""
        values = self.query_params.get(name, [])
        return values[0] if values else default

    def get_query_params(self, name: str) -> builtins.list[str]:
        """Get all query parameter values."""
        return self.query_params.get(name, [])

    def get_content_type(self) -> str | None:
        """Get content type header."""
        return self.get_header("Content-Type")

    def get_content_length(self) -> int:
        """Get content length."""
        length_str = self.get_header("Content-Length")
        return int(length_str) if length_str else 0

    def is_json(self) -> bool:
        """Check if request has JSON content type."""
        content_type = self.get_content_type()
        return content_type and "application/json" in content_type.lower()

    def is_form_data(self) -> bool:
        """Check if request has form data content type."""
        content_type = self.get_content_type()
        return content_type and "application/x-www-form-urlencoded" in content_type.lower()

    def is_multipart(self) -> bool:
        """Check if request has multipart content type."""
        content_type = self.get_content_type()
        return content_type and "multipart/" in content_type.lower()


@dataclass
class GatewayResponse:
    """Gateway response object."""

    # Response data
    status_code: int = 200
    headers: builtins.dict[str, str] = field(default_factory=dict)
    body: bytes | None = None

    # Response metadata
    response_time: float | None = None
    upstream_service: str | None = None

    def set_header(self, name: str, value: str):
        """Set response header."""
        self.headers[name] = value

    def add_header(self, name: str, value: str):
        """Add response header (allows duplicates)."""
        existing = self.headers.get(name)
        if existing:
            self.headers[name] = f"{existing}, {value}"
        else:
            self.headers[name] = value

    def set_json_body(self, data: Any):
        """Set JSON response body."""

        self.body = json.dumps(data).encode("utf-8")
        self.set_header("Content-Type", "application/json")
        self.set_header("Content-Length", str(len(self.body)))

    def set_text_body(self, text: str):
        """Set text response body."""
        self.body = text.encode("utf-8")
        self.set_header("Content-Type", "text/plain")
        self.set_header("Content-Length", str(len(self.body)))

    def set_html_body(self, html: str):
        """Set HTML response body."""
        self.body = html.encode("utf-8")
        self.set_header("Content-Type", "text/html")
        self.set_header("Content-Length", str(len(self.body)))


@dataclass
class RequestContext:
    """Context for processing a request through the gateway."""

    request: GatewayRequest
    response: GatewayResponse | None = None

    # Processing state
    route: Optional["Route"] = None
    upstream_url: str | None = None

    # Authentication/authorization
    user: builtins.dict[str, Any] | None = None
    permissions: builtins.set[str] = field(default_factory=set)

    # Rate limiting
    rate_limit_key: str | None = None
    rate_limit_remaining: int | None = None

    # Timing information
    start_time: float = field(default_factory=time.time)
    processing_time: float | None = None

    # Custom data for middleware/plugins
    data: builtins.dict[str, Any] = field(default_factory=dict)

    def set_response(self, response: GatewayResponse):
        """Set response and calculate processing time."""
        self.response = response
        self.processing_time = time.time() - self.start_time
        if response:
            response.response_time = self.processing_time


@dataclass
class RouteConfig:
    """Configuration for a route."""

    # Route matching
    path: str
    methods: builtins.list[HTTPMethod] = field(default_factory=lambda: [HTTPMethod.GET])
    host: str | None = None
    headers: builtins.dict[str, str] = field(default_factory=dict)

    # Upstream configuration
    upstream: str
    rewrite_path: str | None = None

    # Route-specific settings
    timeout: float = 30.0
    retries: int = 3
    rate_limit: builtins.dict[str, Any] | None = None
    auth_required: bool = True

    # Transformation rules
    request_transformers: builtins.list[str] = field(default_factory=list)
    response_transformers: builtins.list[str] = field(default_factory=list)

    # Metadata
    name: str | None = None
    description: str | None = None
    tags: builtins.list[str] = field(default_factory=list)


class Route:
    """Individual route configuration and handlers."""

    def __init__(self, config: RouteConfig):
        self.config = config
        self._middleware: builtins.list[Middleware] = []
        self._pre_handlers: builtins.list[Callable] = []
        self._post_handlers: builtins.list[Callable] = []

    def add_middleware(self, middleware: "Middleware"):
        """Add middleware to this route."""
        self._middleware.append(middleware)

    def add_pre_handler(self, handler: Callable):
        """Add pre-processing handler."""
        self._pre_handlers.append(handler)

    def add_post_handler(self, handler: Callable):
        """Add post-processing handler."""
        self._post_handlers.append(handler)

    async def process_request(self, context: RequestContext) -> bool:
        """Process request through route middleware and handlers."""

        # Run pre-handlers
        for handler in self._pre_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(context)
                else:
                    handler(context)
            except Exception as e:
                logger.error("Pre-handler failed: %s", e)
                return False

        # Run middleware
        for middleware in self._middleware:
            try:
                should_continue = await middleware.process_request(context)
                if not should_continue:
                    return False
            except Exception as e:
                logger.error("Route middleware failed: %s", e)
                return False

        return True

    async def process_response(self, context: RequestContext):
        """Process response through route middleware and handlers."""

        # Run middleware in reverse order
        for middleware in reversed(self._middleware):
            try:
                await middleware.process_response(context)
            except Exception as e:
                logger.error("Route middleware response processing failed: %s", e)

        # Run post-handlers
        for handler in self._post_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(context)
                else:
                    handler(context)
            except Exception as e:
                logger.error("Post-handler failed: %s", e)

    def matches(self, request: GatewayRequest) -> bool:
        """Check if this route matches the request."""
        # This is a basic implementation - would be enhanced by routing engine
        return (
            request.method in self.config.methods
            and self._path_matches(request.path)
            and self._host_matches(request)
            and self._headers_match(request)
        )

    def _path_matches(self, path: str) -> bool:
        """Check if path matches route pattern."""
        # Simple exact match - would be enhanced with pattern matching
        return path == self.config.path

    def _host_matches(self, request: GatewayRequest) -> bool:
        """Check if host matches route pattern."""
        if not self.config.host:
            return True

        host_header = request.get_header("Host")
        return host_header == self.config.host

    def _headers_match(self, request: GatewayRequest) -> bool:
        """Check if required headers match."""
        for name, value in self.config.headers.items():
            if request.get_header(name) != value:
                return False
        return True


class RouteGroup:
    """Group of routes with shared configuration."""

    def __init__(self, prefix: str = "", name: str = ""):
        self.prefix = prefix
        self.name = name
        self.routes: builtins.list[Route] = []
        self._middleware: builtins.list[Middleware] = []

    def add_route(self, route: Route):
        """Add route to group."""
        self.routes.append(route)

    def add_middleware(self, middleware: "Middleware"):
        """Add middleware to all routes in group."""
        self._middleware.append(middleware)

        # Apply to existing routes
        for route in self.routes:
            route.add_middleware(middleware)

    def create_route(self, config: RouteConfig) -> Route:
        """Create and add a new route to the group."""
        # Prepend group prefix to route path
        if self.prefix:
            config.path = self.prefix.rstrip("/") + "/" + config.path.lstrip("/")

        route = Route(config)

        # Apply group middleware
        for middleware in self._middleware:
            route.add_middleware(middleware)

        self.add_route(route)
        return route


class Middleware(ABC):
    """Abstract middleware interface."""

    @abstractmethod
    async def process_request(self, context: RequestContext) -> bool:
        """
        Process incoming request.

        Returns:
            True to continue processing, False to stop
        """

    async def process_response(self, context: RequestContext):
        """Process outgoing response."""


class MiddlewareChain:
    """Chain of middleware for processing requests."""

    def __init__(self):
        self.middleware: builtins.list[Middleware] = []

    def add(self, middleware: Middleware):
        """Add middleware to chain."""
        self.middleware.append(middleware)

    def remove(self, middleware: Middleware):
        """Remove middleware from chain."""
        if middleware in self.middleware:
            self.middleware.remove(middleware)

    async def process_request(self, context: RequestContext) -> bool:
        """Process request through middleware chain."""
        for middleware in self.middleware:
            try:
                should_continue = await middleware.process_request(context)
                if not should_continue:
                    return False
            except Exception as e:
                logger.error("Middleware %s failed: %s", type(middleware).__name__, e)
                return False

        return True

    async def process_response(self, context: RequestContext):
        """Process response through middleware chain (in reverse order)."""
        for middleware in reversed(self.middleware):
            try:
                await middleware.process_response(context)
            except Exception as e:
                logger.error(
                    "Middleware %s response processing failed: %s",
                    type(middleware).__name__,
                    e,
                )


class MiddlewareRegistry:
    """Registry for managing middleware instances."""

    def __init__(self):
        self._middleware: builtins.dict[str, Middleware] = {}
        self._factories: builtins.dict[str, Callable[[], Middleware]] = {}

    def register(self, name: str, middleware: Middleware):
        """Register middleware instance."""
        self._middleware[name] = middleware

    def register_factory(self, name: str, factory: Callable[[], Middleware]):
        """Register middleware factory."""
        self._factories[name] = factory

    def get(self, name: str) -> Middleware | None:
        """Get middleware by name."""
        middleware = self._middleware.get(name)
        if middleware:
            return middleware

        # Try to create from factory
        factory = self._factories.get(name)
        if factory:
            middleware = factory()
            self._middleware[name] = middleware
            return middleware

        return None

    def create_chain(self, names: builtins.list[str]) -> MiddlewareChain:
        """Create middleware chain from names."""
        chain = MiddlewareChain()

        for name in names:
            middleware = self.get(name)
            if middleware:
                chain.add(middleware)
            else:
                logger.warning("Middleware not found: %s", name)

        return chain


@dataclass
class PluginConfig:
    """Configuration for a plugin."""

    name: str
    enabled: bool = True
    priority: int = 100
    config: builtins.dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """Abstract plugin interface."""

    def __init__(self, config: PluginConfig):
        self.config = config
        self.name = config.name
        self.enabled = config.enabled
        self.priority = config.priority

    @abstractmethod
    async def initialize(self, gateway: "APIGateway"):
        """Initialize plugin with gateway instance."""

    async def startup(self):
        """Called when gateway starts up."""

    async def shutdown(self):
        """Called when gateway shuts down."""

    async def on_request(self, context: RequestContext):
        """Called for each request."""

    async def on_response(self, context: RequestContext):
        """Called for each response."""

    async def on_error(self, context: RequestContext, error: Exception):
        """Called when an error occurs."""


class PluginManager:
    """Manager for gateway plugins."""

    def __init__(self):
        self.plugins: builtins.list[Plugin] = []
        self._registry: builtins.dict[str, Plugin] = {}

    def add_plugin(self, plugin: Plugin):
        """Add plugin to manager."""
        if plugin.enabled:
            self.plugins.append(plugin)
            self._registry[plugin.name] = plugin

            # Sort by priority
            self.plugins.sort(key=lambda p: p.priority)

    def remove_plugin(self, name: str):
        """Remove plugin by name."""
        plugin = self._registry.pop(name, None)
        if plugin and plugin in self.plugins:
            self.plugins.remove(plugin)

    def get_plugin(self, name: str) -> Plugin | None:
        """Get plugin by name."""
        return self._registry.get(name)

    async def initialize_all(self, gateway: "APIGateway"):
        """Initialize all plugins."""
        for plugin in self.plugins:
            try:
                await plugin.initialize(gateway)
                logger.info("Initialized plugin: %s", plugin.name)
            except Exception as e:
                logger.error("Failed to initialize plugin %s: %s", plugin.name, e)

    async def startup_all(self):
        """Start up all plugins."""
        for plugin in self.plugins:
            try:
                await plugin.startup()
            except Exception as e:
                logger.error("Plugin %s startup failed: %s", plugin.name, e)

    async def shutdown_all(self):
        """Shut down all plugins."""
        for plugin in reversed(self.plugins):
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error("Plugin %s shutdown failed: %s", plugin.name, e)

    async def on_request(self, context: RequestContext):
        """Call on_request for all plugins."""
        for plugin in self.plugins:
            try:
                await plugin.on_request(context)
            except Exception as e:
                logger.error("Plugin %s on_request failed: %s", plugin.name, e)

    async def on_response(self, context: RequestContext):
        """Call on_response for all plugins."""
        for plugin in reversed(self.plugins):
            try:
                await plugin.on_response(context)
            except Exception as e:
                logger.error("Plugin %s on_response failed: %s", plugin.name, e)

    async def on_error(self, context: RequestContext, error: Exception):
        """Call on_error for all plugins."""
        for plugin in self.plugins:
            try:
                await plugin.on_error(context, error)
            except Exception as e:
                logger.error("Plugin %s on_error failed: %s", plugin.name, e)


@dataclass
class GatewayConfig:
    """Main configuration for the API gateway."""

    # Basic settings
    name: str = "api-gateway"
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False

    # Server configuration
    max_connections: int = 1000
    request_timeout: float = 30.0
    keep_alive_timeout: float = 75.0

    # Default upstream settings
    default_upstream_timeout: float = 30.0
    default_upstream_retries: int = 3

    # Middleware configuration
    middleware: builtins.list[str] = field(default_factory=list)

    # Plugin configuration
    plugins: builtins.list[PluginConfig] = field(default_factory=list)

    # Feature flags
    enable_cors: bool = True
    enable_metrics: bool = True
    enable_tracing: bool = False
    enable_rate_limiting: bool = True
    enable_auth: bool = True

    # Logging
    log_level: str = "INFO"
    access_log: bool = True
    error_log: bool = True


class GatewayContext:
    """Global context for the gateway instance."""

    def __init__(self, config: GatewayConfig):
        self.config = config
        self.middleware_registry = MiddlewareRegistry()
        self.plugin_manager = PluginManager()
        self.route_groups: builtins.list[RouteGroup] = []
        self._stats = {
            "requests_total": 0,
            "requests_successful": 0,
            "requests_failed": 0,
            "start_time": time.time(),
            "uptime": 0.0,
        }

    def add_route_group(self, group: RouteGroup):
        """Add route group to gateway."""
        self.route_groups.append(group)

    def get_all_routes(self) -> builtins.list[Route]:
        """Get all routes from all groups."""
        routes = []
        for group in self.route_groups:
            routes.extend(group.routes)
        return routes

    def update_stats(self, success: bool):
        """Update gateway statistics."""
        self._stats["requests_total"] += 1
        if success:
            self._stats["requests_successful"] += 1
        else:
            self._stats["requests_failed"] += 1

        self._stats["uptime"] = time.time() - self._stats["start_time"]

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get gateway statistics."""
        return self._stats.copy()


class APIGateway:
    """Main API Gateway class."""

    def __init__(self, config: GatewayConfig):
        self.config = config
        self.context = GatewayContext(config)
        self._running = False
        self._server = None

    async def start(self):
        """Start the API gateway."""
        if self._running:
            return

        logger.info("Starting API Gateway: %s", self.config.name)

        # Initialize plugins
        await self.context.plugin_manager.initialize_all(self)
        await self.context.plugin_manager.startup_all()

        # Start server (implementation would depend on web framework)
        # This would typically start an HTTP server using aiohttp, FastAPI, etc.

        self._running = True
        logger.info("API Gateway started on %s:%d", self.config.host, self.config.port)

    async def stop(self):
        """Stop the API gateway."""
        if not self._running:
            return

        logger.info("Stopping API Gateway: %s", self.config.name)

        # Stop server
        if self._server:
            # Implementation would stop HTTP server
            pass

        # Shutdown plugins
        await self.context.plugin_manager.shutdown_all()

        self._running = False
        logger.info("API Gateway stopped")

    async def handle_request(self, request: GatewayRequest) -> GatewayResponse:
        """Handle incoming request through the gateway."""
        context = RequestContext(request=request)

        try:
            # Plugin request hooks
            await self.context.plugin_manager.on_request(context)

            # Find matching route
            route = self._find_route(request)
            if not route:
                raise RouteNotFoundError(request.path, request.method.value)

            context.route = route

            # Process through global middleware
            global_chain = self.context.middleware_registry.create_chain(self.config.middleware)
            should_continue = await global_chain.process_request(context)

            if not should_continue:
                if not context.response:
                    context.response = GatewayResponse(status_code=500)
            else:
                # Process through route
                should_continue = await route.process_request(context)

                if not should_continue and not context.response:
                    context.response = GatewayResponse(status_code=500)
                elif not context.response:
                    # Forward to upstream (would be implemented by routing/load balancing modules)
                    context.response = await self._forward_to_upstream(context)

                # Process response through route
                await route.process_response(context)

            # Process response through global middleware
            await global_chain.process_response(context)

            # Plugin response hooks
            await self.context.plugin_manager.on_response(context)

            # Update stats
            self.context.update_stats(True)

            return context.response

        except Exception as e:
            logger.error("Request processing failed: %s", e)

            # Plugin error hooks
            await self.context.plugin_manager.on_error(context, e)

            # Update stats
            self.context.update_stats(False)

            # Create error response
            if isinstance(e, GatewayError):
                response = GatewayResponse(status_code=e.status_code)
                response.set_json_body({"error": e.message, "details": e.details})
            else:
                response = GatewayResponse(status_code=500)
                response.set_json_body({"error": "Internal server error"})

            context.set_response(response)
            return response

    def _find_route(self, request: GatewayRequest) -> Route | None:
        """Find route matching the request."""
        for route in self.context.get_all_routes():
            if route.matches(request):
                return route
        return None

    async def _forward_to_upstream(self, context: RequestContext) -> GatewayResponse:
        """Forward request to upstream service."""
        # This would be implemented by the load balancing module
        # For now, return a placeholder response
        return GatewayResponse(
            status_code=200, body=b'{"message": "Upstream response placeholder"}'
        )

    def add_route_group(self, group: RouteGroup):
        """Add route group to gateway."""
        self.context.add_route_group(group)

    def add_middleware(self, name: str, middleware: Middleware):
        """Add middleware to registry."""
        self.context.middleware_registry.register(name, middleware)

    def add_plugin(self, plugin: Plugin):
        """Add plugin to gateway."""
        self.context.plugin_manager.add_plugin(plugin)

    def get_health_status(self) -> builtins.dict[str, Any]:
        """Get gateway health status."""
        return {
            "status": "healthy" if self._running else "stopped",
            "name": self.config.name,
            "uptime": self.context.get_stats()["uptime"],
            "routes": len(self.context.get_all_routes()),
            "middleware_count": len(self.context.middleware_registry._middleware),
            "plugin_count": len(self.context.plugin_manager.plugins),
            "stats": self.context.get_stats(),
        }
