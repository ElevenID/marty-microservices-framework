"""
Gateway Application Service
"""

import logging
from typing import Any

from mmf_new.core.security.ports.authentication import IAuthenticator

from .domain.exceptions import (
    AuthenticationError,
    AuthorizationError,
    RateLimitExceededError,
    RouteNotFoundError,
    UpstreamError,
)
from .domain.models import (
    AuthenticationType,
    GatewayRequest,
    GatewayResponse,
    RouteConfig,
    UpstreamGroup,
)
from .domain.security import CredentialExtractorFactory
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

    async def _authenticate_request(
        self, auth_type: AuthenticationType, request: GatewayRequest
    ) -> dict[str, Any] | None:
        """Authenticate request based on authentication type."""
        if not self.authenticator:
            # If no authenticator is configured but auth is required, we must fail secure
            # or return None if auth is optional (handled by caller)
            return None

        extractor = CredentialExtractorFactory.get_extractor(auth_type)
        if not extractor:
            return None

        credentials = extractor.extract(request)

        if auth_type == AuthenticationType.BEARER_TOKEN:
            # Use validate_token for Bearer tokens
            result = await self.authenticator.validate_token(credentials["token"])
            if not result.success:
                raise AuthenticationError(result.error or "Invalid bearer token")

            # Map user to dict context
            if result.user:
                return {
                    "user_id": result.user.user_id,
                    "username": result.user.username,
                    "roles": list(result.user.roles),
                    "permissions": list(result.user.permissions),
                }
            return {}

        # For other types, use authenticate method
        if credentials:
            result = await self.authenticator.authenticate(credentials)
            if not result.success:
                raise AuthenticationError(result.error or "Authentication failed")

            if result.user:
                return {
                    "user_id": result.user.user_id,
                    "username": result.user.username,
                    "roles": list(result.user.roles),
                    "permissions": list(result.user.permissions),
                }
            return {}

        return None
