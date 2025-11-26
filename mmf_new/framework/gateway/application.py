"""
Gateway Application Service
"""

import logging

from typing import Any
from .ports.input import RequestHandlerPort
from .ports.output import UpstreamClientPort, ServiceRegistryPort, RateLimitStoragePort
from .domain.models import GatewayRequest, GatewayResponse, RouteConfig, UpstreamGroup, AuthenticationType
from .domain.services import RouteMatcher, LoadBalancer
from .domain.exceptions import RouteNotFoundError, UpstreamError, RateLimitExceededError, AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)

class GatewayService(RequestHandlerPort):
    """Implementation of the Gateway Request Handler."""

    def __init__(
        self,
        routes: list[RouteConfig],
        matcher: RouteMatcher,
        load_balancer: LoadBalancer,
        upstream_client: UpstreamClientPort,
        service_registry: ServiceRegistryPort,
        rate_limit_storage: RateLimitStoragePort | None = None
    ):
        self.routes = routes
        self.matcher = matcher
        self.load_balancer = load_balancer
        self.upstream_client = upstream_client
        self.service_registry = service_registry
        self.rate_limit_storage = rate_limit_storage
        self._upstream_groups: dict[str, UpstreamGroup] = {}

    async def handle_request(self, request: GatewayRequest) -> GatewayResponse:
        # 1. Match Route
        route = self._match_route(request)
        if not route:
            raise RouteNotFoundError(request.path, request.method.value)

        # 2. Security Validation
        await self._validate_security(route, request)

        # 3. Rate Limiting
        if route.rate_limit and self.rate_limit_storage:
            await self._check_rate_limit(route, request)

        # 4. Resolve Upstream
        upstream_group = await self._get_upstream_group(route.upstream)
        server = self.load_balancer.select_server(upstream_group, request)

        if not server:
            raise UpstreamError(f"No healthy upstream servers for {route.upstream}")

        # 4. Forward Request
        try:
            response = await self.upstream_client.send_request(server, request)
            return response
        except Exception as e:
            logger.error("Upstream request failed: %s", e)
            raise UpstreamError(f"Upstream request failed: {str(e)}") from e

    def _match_route(self, request: GatewayRequest) -> RouteConfig | None:
        for route in self.routes:
            if self.matcher.matches(route.path, request.path):
                if request.method in route.methods:
                    return route
        return None

    async def _check_rate_limit(self, route: RouteConfig, request: GatewayRequest):
        # Simple implementation
        if not route.rate_limit or not self.rate_limit_storage:
            return

        key = f"rl:{route.name}:{request.client_ip}"
        usage = await self.rate_limit_storage.increment_usage(key)
        if usage > route.rate_limit.requests_per_window:
            raise RateLimitExceededError()

    async def _get_upstream_group(self, service_name: str) -> UpstreamGroup:
        if service_name not in self._upstream_groups:
            servers = await self.service_registry.get_service_instances(service_name)
            group = UpstreamGroup(name=service_name, servers=servers)
            self._upstream_groups[service_name] = group
        else:
            # In a real implementation, we would refresh servers here
            pass
        return self._upstream_groups[service_name]

    async def _validate_security(self, route: RouteConfig, request: GatewayRequest):
        """Validate security for request."""
        if route.authentication_type != AuthenticationType.NONE:
            user_context = await self._authenticate_request(route.authentication_type, request)
            if user_context:
                request.context["user"] = user_context

        if route.auth_required and not request.context.get("user"):
            raise AuthenticationError("Authentication required")

    async def _authenticate_request(self, auth_type: AuthenticationType, request: GatewayRequest) -> dict[str, Any] | None:
        """Authenticate request based on authentication type."""
        if auth_type == AuthenticationType.API_KEY:
            auth_header = request.get_header("Authorization") or ""
            api_key = request.get_header("X-API-Key") or auth_header.replace("ApiKey ", "")

            if not api_key:
                raise AuthenticationError("API key required")

            # Validate API key (stub - in real world check DB/Cache)
            if api_key.startswith("ak_"):
                return {"user_id": f"user_{api_key[-8:]}", "scopes": ["read", "write"]}
            raise AuthenticationError("Invalid API key")

        if auth_type == AuthenticationType.BEARER_TOKEN:
            auth_header = request.get_header("Authorization") or ""
            if not auth_header.startswith("Bearer "):
                raise AuthenticationError("Bearer token required")

            token = auth_header[7:]
            # Validate token (stub)
            if len(token) >= 32:
                return {"user_id": f"user_{token[-8:]}", "scopes": ["read", "write"]}
            raise AuthenticationError("Invalid bearer token")

        return None
