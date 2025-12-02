"""
Gateway Application Service
"""

import logging

from mmf.core.security.ports.authentication import IAuthenticator

from .domain.exceptions import RouteNotFoundError, UpstreamError
from .domain.models import GatewayRequest, GatewayResponse, RouteConfig, UpstreamGroup
from .domain.rate_limit import GatewayRateLimiter
from .domain.security import GatewaySecurityHandler
from .domain.services import LoadBalancer, RouteMatcher
from .ports.input import RequestHandlerPort
from .ports.output import RateLimitStoragePort, ServiceRegistryPort, UpstreamClientPort

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
        rate_limit_storage: RateLimitStoragePort | None = None,
        authenticator: IAuthenticator | None = None,
    ):
        self.routes = routes
        self.matcher = matcher
        self.load_balancer = load_balancer
        self.upstream_client = upstream_client
        self.service_registry = service_registry
        self.rate_limit_storage = rate_limit_storage
        self.authenticator = authenticator
        self._upstream_groups: dict[str, UpstreamGroup] = {}

        # Initialize handlers
        self.security_handler = GatewaySecurityHandler(authenticator)
        self.rate_limiter = GatewayRateLimiter(rate_limit_storage)

    async def handle_request(self, request: GatewayRequest) -> GatewayResponse:
        # 1. Match Route
        route = self._match_route(request)
        if not route:
            raise RouteNotFoundError(request.path, request.method.value)

        # 2. Security Validation
        await self.security_handler.validate_security(route, request)

        # 3. Rate Limiting
        await self.rate_limiter.check_rate_limit(route, request)

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

    async def _get_upstream_group(self, service_name: str) -> UpstreamGroup:
        if service_name not in self._upstream_groups:
            servers = await self.service_registry.get_service_instances(service_name)
            group = UpstreamGroup(name=service_name, servers=servers)
            self._upstream_groups[service_name] = group
        else:
            # In a real implementation, we would refresh servers here
            pass
        return self._upstream_groups[service_name]
