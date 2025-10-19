"""
Routing Engine for API Gateway

Advanced routing system with path matching, host-based routing, header-based routing,
and composite routing strategies for sophisticated request routing capabilities.
"""

import builtins
import fnmatch
import logging
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from re import Pattern
from typing import Any

from .core import GatewayRequest, HTTPMethod, Route, RouteConfig, RouteGroup

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Routing strategy types."""

    PATH_BASED = "path_based"
    HOST_BASED = "host_based"
    HEADER_BASED = "header_based"
    WEIGHT_BASED = "weight_based"
    CANARY = "canary"
    AB_TEST = "ab_test"


class MatchType(Enum):
    """Route matching types."""

    EXACT = "exact"
    PREFIX = "prefix"
    REGEX = "regex"
    WILDCARD = "wildcard"
    TEMPLATE = "template"


@dataclass
class RoutingRule:
    """Rule for routing decisions."""

    match_type: MatchType
    pattern: str
    weight: float = 1.0
    conditions: builtins.dict[str, Any] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingConfig:
    """Configuration for routing behavior."""

    strategy: RoutingStrategy = RoutingStrategy.PATH_BASED
    case_sensitive: bool = True
    strict_slashes: bool = False
    merge_slashes: bool = True
    default_route: str | None = None

    # Advanced routing features
    enable_canary: bool = False
    canary_header: str = "X-Canary"
    enable_ab_testing: bool = False
    ab_test_header: str = "X-AB-Test"

    # Performance settings
    cache_compiled_patterns: bool = True
    max_cache_size: int = 1000


class RouteMatcher(ABC):
    """Abstract route matcher interface."""

    @abstractmethod
    def matches(self, pattern: str, path: str) -> bool:
        """Check if pattern matches path."""
        raise NotImplementedError

    @abstractmethod
    def extract_params(self, pattern: str, path: str) -> builtins.dict[str, str]:
        """Extract parameters from matched path."""
        raise NotImplementedError


class ExactMatcher(RouteMatcher):
    """Exact path matching."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive

    def matches(self, pattern: str, path: str) -> bool:
        """Check exact match."""
        if not self.case_sensitive:
            pattern = pattern.lower()
            path = path.lower()
        return pattern == path

    def extract_params(self, pattern: str, path: str) -> builtins.dict[str, str]:
        """No parameters for exact match."""
        return {}


class PrefixMatcher(RouteMatcher):
    """Prefix path matching."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive

    def matches(self, pattern: str, path: str) -> bool:
        """Check prefix match."""
        if not self.case_sensitive:
            pattern = pattern.lower()
            path = path.lower()
        return path.startswith(pattern)

    def extract_params(self, pattern: str, path: str) -> builtins.dict[str, str]:
        """Extract remaining path as parameter."""
        if self.matches(pattern, path):
            remaining = path[len(pattern) :].lstrip("/")
            return {"*": remaining} if remaining else {}
        return {}


class RegexMatcher(RouteMatcher):
    """Regular expression path matching."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive
        self._compiled_patterns: builtins.dict[str, Pattern] = {}

    def _compile_pattern(self, pattern: str) -> Pattern:
        """Compile regex pattern with caching."""
        if pattern not in self._compiled_patterns:
            flags = 0 if self.case_sensitive else re.IGNORECASE
            self._compiled_patterns[pattern] = re.compile(pattern, flags)
        return self._compiled_patterns[pattern]

    def matches(self, pattern: str, path: str) -> bool:
        """Check regex match."""
        compiled = self._compile_pattern(pattern)
        return bool(compiled.match(path))

    def extract_params(self, pattern: str, path: str) -> builtins.dict[str, str]:
        """Extract named groups as parameters."""
        compiled = self._compile_pattern(pattern)
        match = compiled.match(path)
        return match.groupdict() if match else {}


class WildcardMatcher(RouteMatcher):
    """Wildcard path matching using shell-style patterns."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive

    def matches(self, pattern: str, path: str) -> bool:
        """Check wildcard match."""
        if not self.case_sensitive:
            pattern = pattern.lower()
            path = path.lower()
        return fnmatch.fnmatch(path, pattern)

    def extract_params(self, pattern: str, path: str) -> builtins.dict[str, str]:
        """Limited parameter extraction for wildcards."""
        # Simple implementation - could be enhanced
        if "*" in pattern:
            return {"wildcard": path}
        return {}


class TemplateMatcher(RouteMatcher):
    """Template-based path matching with parameter extraction."""

    def __init__(self, case_sensitive: bool = True):
        self.case_sensitive = case_sensitive
        self._compiled_patterns: builtins.dict[
            str, builtins.tuple[Pattern, builtins.list[str]]
        ] = {}

    def _compile_template(self, template: str) -> builtins.tuple[Pattern, builtins.list[str]]:
        """Compile template pattern with parameter names."""
        if template not in self._compiled_patterns:
            # Convert template to regex pattern
            # e.g., "/users/{id}/posts/{post_id}" -> r"/users/(?P<id>[^/]+)/posts/(?P<post_id>[^/]+)"

            param_names = []
            pattern = template

            # Find all parameters in {name} format
            for match in re.finditer(r"\{([^}]+)\}", template):
                param_name = match.group(1)
                param_names.append(param_name)

                # Replace with named regex group
                pattern = pattern.replace(f"{{{param_name}}}", f"(?P<{param_name}>[^/]+)")

            # Escape other regex characters
            pattern = pattern.replace(".", r"\.")
            pattern = f"^{pattern}$"

            flags = 0 if self.case_sensitive else re.IGNORECASE
            compiled = re.compile(pattern, flags)

            self._compiled_patterns[template] = (compiled, param_names)

        return self._compiled_patterns[template]

    def matches(self, pattern: str, path: str) -> bool:
        """Check template match."""
        compiled, _ = self._compile_template(pattern)
        return bool(compiled.match(path))

    def extract_params(self, pattern: str, path: str) -> builtins.dict[str, str]:
        """Extract template parameters."""
        compiled, param_names = self._compile_template(pattern)
        match = compiled.match(path)

        if match:
            return {name: match.group(name) for name in param_names}

        return {}


class PathRouter(ABC):
    """Abstract path router interface."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self.routes: builtins.list[Route] = []
        self._matcher = self._create_matcher()

    @abstractmethod
    def _create_matcher(self) -> RouteMatcher:
        """Create appropriate matcher for this router."""
        raise NotImplementedError

    def add_route(self, route: Route):
        """Add route to router."""
        self.routes.append(route)

    def remove_route(self, route: Route):
        """Remove route from router."""
        if route in self.routes:
            self.routes.remove(route)

    def find_route(
        self, request: GatewayRequest
    ) -> builtins.tuple[Route, builtins.dict[str, str]] | None:
        """Find matching route and extract parameters."""
        path = self._normalize_path(request.path)

        for route in self.routes:
            if self._route_matches(route, request, path):
                params = self._matcher.extract_params(route.config.path, path)
                return route, params

        return None

    def _route_matches(self, route: Route, request: GatewayRequest, path: str) -> bool:
        """Check if route matches request."""
        # Check HTTP method
        if request.method not in route.config.methods:
            return False

        # Check path pattern
        if not self._matcher.matches(route.config.path, path):
            return False

        # Check host if specified
        if route.config.host:
            host_header = request.get_header("Host")
            if host_header != route.config.host:
                return False

        # Check required headers
        for name, value in route.config.headers.items():
            if request.get_header(name) != value:
                return False

        return True

    def _normalize_path(self, path: str) -> str:
        """Normalize path according to configuration."""
        if self.config.merge_slashes:
            # Replace multiple slashes with single slash
            path = re.sub(r"/+", "/", path)

        if not self.config.strict_slashes:
            # Remove trailing slash (except for root)
            if len(path) > 1 and path.endswith("/"):
                path = path[:-1]

        return path


class ExactPathRouter(PathRouter):
    """Router using exact path matching."""

    def _create_matcher(self) -> RouteMatcher:
        return ExactMatcher(self.config.case_sensitive)


class PrefixPathRouter(PathRouter):
    """Router using prefix path matching."""

    def _create_matcher(self) -> RouteMatcher:
        return PrefixMatcher(self.config.case_sensitive)


class RegexPathRouter(PathRouter):
    """Router using regex path matching."""

    def _create_matcher(self) -> RouteMatcher:
        return RegexMatcher(self.config.case_sensitive)


class TemplatePathRouter(PathRouter):
    """Router using template path matching."""

    def _create_matcher(self) -> RouteMatcher:
        return TemplateMatcher(self.config.case_sensitive)


class HostRouter:
    """Host-based router for virtual hosting."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self.host_routes: builtins.dict[str, PathRouter] = {}
        self.default_router: PathRouter | None = None

    def add_host_router(self, host: str, router: PathRouter):
        """Add router for specific host."""
        self.host_routes[host] = router

    def set_default_router(self, router: PathRouter):
        """Set default router for unmatched hosts."""
        self.default_router = router

    def find_route(
        self, request: GatewayRequest
    ) -> builtins.tuple[Route, builtins.dict[str, str]] | None:
        """Find route based on host header."""
        host_header = request.get_header("Host")

        if host_header:
            # Remove port from host header
            host = host_header.split(":")[0]

            # Try exact host match
            router = self.host_routes.get(host)
            if router:
                return router.find_route(request)

            # Try wildcard host matches
            for pattern, router in self.host_routes.items():
                if "*" in pattern and fnmatch.fnmatch(host, pattern):
                    return router.find_route(request)

        # Use default router
        if self.default_router:
            return self.default_router.find_route(request)

        return None


class HeaderRouter:
    """Header-based router for routing based on request headers."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self.header_routes: builtins.dict[str, builtins.dict[str, PathRouter]] = {}
        self.default_router: PathRouter | None = None

    def add_header_router(self, header_name: str, header_value: str, router: PathRouter):
        """Add router for specific header value."""
        if header_name not in self.header_routes:
            self.header_routes[header_name] = {}
        self.header_routes[header_name][header_value] = router

    def set_default_router(self, router: PathRouter):
        """Set default router for unmatched headers."""
        self.default_router = router

    def find_route(
        self, request: GatewayRequest
    ) -> builtins.tuple[Route, builtins.dict[str, str]] | None:
        """Find route based on headers."""
        for header_name, value_routers in self.header_routes.items():
            header_value = request.get_header(header_name)

            if header_value:
                router = value_routers.get(header_value)
                if router:
                    result = router.find_route(request)
                    if result:
                        return result

        # Use default router
        if self.default_router:
            return self.default_router.find_route(request)

        return None


class WeightedRouter:
    """Weighted router for canary deployments and A/B testing."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self.weighted_routes: builtins.list[builtins.tuple[PathRouter, float]] = []
        self._total_weight = 0.0

    def add_weighted_router(self, router: PathRouter, weight: float):
        """Add router with weight."""
        self.weighted_routes.append((router, weight))
        self._total_weight += weight

        # Sort by weight (descending)
        self.weighted_routes.sort(key=lambda x: x[1], reverse=True)

    def find_route(
        self, request: GatewayRequest
    ) -> builtins.tuple[Route, builtins.dict[str, str]] | None:
        """Find route using weighted selection."""
        if not self.weighted_routes:
            return None

        # For canary deployments, check for canary header
        if self.config.enable_canary:
            canary_header = request.get_header(self.config.canary_header)
            if canary_header == "true":
                # Route to first (highest weight) router
                return self.weighted_routes[0][0].find_route(request)

        # For A/B testing, check for test group header
        if self.config.enable_ab_testing:
            ab_header = request.get_header(self.config.ab_test_header)
            if ab_header:
                # Map test group to router index
                try:
                    group_index = int(ab_header) % len(self.weighted_routes)
                    return self.weighted_routes[group_index][0].find_route(request)
                except (ValueError, IndexError):
                    pass

        # Use weighted random selection

        if self._total_weight <= 0:
            return self.weighted_routes[0][0].find_route(request)

        random_weight = random.uniform(0, self._total_weight)
        current_weight = 0.0

        for router, weight in self.weighted_routes:
            current_weight += weight
            if random_weight <= current_weight:
                result = router.find_route(request)
                if result:
                    return result

        # Fallback to first router
        return self.weighted_routes[0][0].find_route(request)


class CompositeRouter:
    """Composite router combining multiple routing strategies."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self.routers: builtins.list[PathRouter | HostRouter | HeaderRouter | WeightedRouter] = []
        self.fallback_router: PathRouter | None = None

    def add_router(self, router: PathRouter | HostRouter | HeaderRouter | WeightedRouter):
        """Add router to composite."""
        self.routers.append(router)

    def set_fallback_router(self, router: PathRouter):
        """Set fallback router."""
        self.fallback_router = router

    def find_route(
        self, request: GatewayRequest
    ) -> builtins.tuple[Route, builtins.dict[str, str]] | None:
        """Find route using all registered routers."""
        for router in self.routers:
            result = router.find_route(request)
            if result:
                return result

        # Try fallback router
        if self.fallback_router:
            return self.fallback_router.find_route(request)

        return None


class Router:
    """Main router class orchestrating all routing strategies."""

    def __init__(self, config: RoutingConfig | None = None):
        self.config = config or RoutingConfig()
        self.composite_router = CompositeRouter(self.config)
        self._route_cache: builtins.dict[str, builtins.tuple[Route, builtins.dict[str, str]]] = {}

        # Initialize default routers
        self._setup_default_routers()

    def _setup_default_routers(self):
        """Setup default routing configuration."""
        # Create template router as primary
        template_router = TemplatePathRouter(self.config)
        self.composite_router.add_router(template_router)

        # Set fallback router
        exact_router = ExactPathRouter(self.config)
        self.composite_router.set_fallback_router(exact_router)

        self.primary_router = template_router
        self.fallback_router = exact_router

    def add_route(self, route: Route):
        """Add route to primary router."""
        self.primary_router.add_route(route)
        self._clear_cache()

    def add_route_group(self, group: RouteGroup):
        """Add all routes from group."""
        for route in group.routes:
            self.add_route(route)

    def add_host_router(self, host: str, router: PathRouter):
        """Add host-based routing."""
        host_router = HostRouter(self.config)
        host_router.add_host_router(host, router)
        self.composite_router.add_router(host_router)
        self._clear_cache()

    def add_header_router(self, header_name: str, header_value: str, router: PathRouter):
        """Add header-based routing."""
        header_router = HeaderRouter(self.config)
        header_router.add_header_router(header_name, header_value, router)
        self.composite_router.add_router(header_router)
        self._clear_cache()

    def add_weighted_router(self, routers: builtins.list[builtins.tuple[PathRouter, float]]):
        """Add weighted routing for canary/A/B testing."""
        weighted_router = WeightedRouter(self.config)
        for router, weight in routers:
            weighted_router.add_weighted_router(router, weight)
        self.composite_router.add_router(weighted_router)
        self._clear_cache()

    def find_route(
        self, request: GatewayRequest
    ) -> builtins.tuple[Route, builtins.dict[str, str]] | None:
        """Find matching route for request."""
        # Generate cache key
        cache_key = self._generate_cache_key(request)

        # Check cache
        if self.config.cache_compiled_patterns and cache_key in self._route_cache:
            return self._route_cache[cache_key]

        # Find route
        result = self.composite_router.find_route(request)

        # Cache result
        if (
            self.config.cache_compiled_patterns
            and result is not None
            and len(self._route_cache) < self.config.max_cache_size
        ):
            self._route_cache[cache_key] = result

        return result

    def _generate_cache_key(self, request: GatewayRequest) -> str:
        """Generate cache key for request."""
        # Include method, path, and relevant headers
        key_parts = [
            request.method.value,
            request.path,
            request.get_header("Host", ""),
        ]

        # Include headers used in routing
        for route in self.primary_router.routes:
            for header_name in route.config.headers.keys():
                header_value = request.get_header(header_name, "")
                key_parts.append(f"{header_name}:{header_value}")

        return "|".join(key_parts)

    def _clear_cache(self):
        """Clear route cache."""
        self._route_cache.clear()

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get router statistics."""
        total_routes = len(self.primary_router.routes)

        return {
            "total_routes": total_routes,
            "cache_size": len(self._route_cache),
            "cache_hit_rate": 0.0,  # Would track this in real implementation
            "config": {
                "strategy": self.config.strategy.value,
                "case_sensitive": self.config.case_sensitive,
                "strict_slashes": self.config.strict_slashes,
                "cache_enabled": self.config.cache_compiled_patterns,
            },
        }


class RouteBuilder:
    """Builder for creating routes with fluent API."""

    def __init__(self):
        self._config = RouteConfig(path="", upstream="")
        self._middleware: builtins.list[str] = []

    def path(self, path: str) -> "RouteBuilder":
        """Set route path."""
        self._config.path = path
        return self

    def methods(self, *methods: HTTPMethod) -> "RouteBuilder":
        """Set allowed HTTP methods."""
        self._config.methods = list(methods)
        return self

    def get(self) -> "RouteBuilder":
        """Set GET method."""
        return self.methods(HTTPMethod.GET)

    def post(self) -> "RouteBuilder":
        """Set POST method."""
        return self.methods(HTTPMethod.POST)

    def put(self) -> "RouteBuilder":
        """Set PUT method."""
        return self.methods(HTTPMethod.PUT)

    def delete(self) -> "RouteBuilder":
        """Set DELETE method."""
        return self.methods(HTTPMethod.DELETE)

    def host(self, host: str) -> "RouteBuilder":
        """Set required host header."""
        self._config.host = host
        return self

    def header(self, name: str, value: str) -> "RouteBuilder":
        """Add required header."""
        self._config.headers[name] = value
        return self

    def upstream(self, upstream: str) -> "RouteBuilder":
        """Set upstream service."""
        self._config.upstream = upstream
        return self

    def rewrite(self, rewrite_path: str) -> "RouteBuilder":
        """Set path rewriting."""
        self._config.rewrite_path = rewrite_path
        return self

    def timeout(self, timeout: float) -> "RouteBuilder":
        """Set request timeout."""
        self._config.timeout = timeout
        return self

    def retries(self, retries: int) -> "RouteBuilder":
        """Set retry count."""
        self._config.retries = retries
        return self

    def auth(self, required: bool = True) -> "RouteBuilder":
        """Set authentication requirement."""
        self._config.auth_required = required
        return self

    def rate_limit(self, rate_limit: builtins.dict[str, Any]) -> "RouteBuilder":
        """Set rate limiting configuration."""
        self._config.rate_limit = rate_limit
        return self

    def middleware(self, *middleware: str) -> "RouteBuilder":
        """Add middleware to route."""
        self._middleware.extend(middleware)
        return self

    def name(self, name: str) -> "RouteBuilder":
        """Set route name."""
        self._config.name = name
        return self

    def description(self, description: str) -> "RouteBuilder":
        """Set route description."""
        self._config.description = description
        return self

    def tags(self, *tags: str) -> "RouteBuilder":
        """Add tags to route."""
        self._config.tags.extend(tags)
        return self

    def build(self) -> Route:
        """Build the route."""
        if not self._config.path:
            raise ValueError("Route path is required")
        if not self._config.upstream:
            raise ValueError("Route upstream is required")

        route = Route(self._config)

        # Add middleware would be handled by the gateway
        # when registering the route

        return route


class RouterBuilder:
    """Builder for creating routers with fluent API."""

    def __init__(self):
        self._config = RoutingConfig()
        self._routes: builtins.list[Route] = []

    def strategy(self, strategy: RoutingStrategy) -> "RouterBuilder":
        """Set routing strategy."""
        self._config.strategy = strategy
        return self

    def case_sensitive(self, enabled: bool = True) -> "RouterBuilder":
        """Set case sensitivity."""
        self._config.case_sensitive = enabled
        return self

    def strict_slashes(self, enabled: bool = True) -> "RouterBuilder":
        """Set strict slash handling."""
        self._config.strict_slashes = enabled
        return self

    def merge_slashes(self, enabled: bool = True) -> "RouterBuilder":
        """Set slash merging."""
        self._config.merge_slashes = enabled
        return self

    def cache_patterns(self, enabled: bool = True) -> "RouterBuilder":
        """Enable pattern caching."""
        self._config.cache_compiled_patterns = enabled
        return self

    def canary(self, enabled: bool = True, header: str = "X-Canary") -> "RouterBuilder":
        """Enable canary deployments."""
        self._config.enable_canary = enabled
        self._config.canary_header = header
        return self

    def ab_testing(self, enabled: bool = True, header: str = "X-AB-Test") -> "RouterBuilder":
        """Enable A/B testing."""
        self._config.enable_ab_testing = enabled
        self._config.ab_test_header = header
        return self

    def add_route(self, route: Route) -> "RouterBuilder":
        """Add route to router."""
        self._routes.append(route)
        return self

    def route(self) -> RouteBuilder:
        """Create new route builder."""
        return RouteBuilder()

    def build(self) -> Router:
        """Build the router."""
        router = Router(self._config)

        for route in self._routes:
            router.add_route(route)

        return router


# Convenience functions
def create_router(strategy: RoutingStrategy = RoutingStrategy.PATH_BASED) -> Router:
    """Create router with specified strategy."""
    config = RoutingConfig(strategy=strategy)
    return Router(config)


def create_template_router() -> Router:
    """Create router with template matching."""
    return create_router(RoutingStrategy.PATH_BASED)


def create_host_router() -> HostRouter:
    """Create host-based router."""
    config = RoutingConfig(strategy=RoutingStrategy.HOST_BASED)
    return HostRouter(config)


def create_header_router() -> HeaderRouter:
    """Create header-based router."""
    config = RoutingConfig(strategy=RoutingStrategy.HEADER_BASED)
    return HeaderRouter(config)
