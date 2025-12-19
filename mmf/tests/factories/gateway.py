"""
Gateway Factories

Provides factory_boy factories for gateway domain models.
"""

import time
import uuid

import factory

from mmf.core.gateway import (
    AuthenticationType,
    GatewayRequest,
    GatewayResponse,
    HealthStatus,
    HTTPMethod,
    LoadBalancingAlgorithm,
    MatchType,
    ProtocolType,
    RateLimitAction,
    RateLimitAlgorithm,
    RateLimitConfig,
    RouteConfig,
    RoutingRule,
    UpstreamGroup,
    UpstreamServer,
)


class GatewayRequestFactory(factory.Factory):
    """Factory for GatewayRequest objects."""

    class Meta:
        model = GatewayRequest

    method = HTTPMethod.GET
    path = factory.LazyAttribute(lambda o: f"/api/v1/resource/{uuid.uuid4().hex[:8]}")
    query_params = factory.LazyAttribute(lambda _: {})
    headers = factory.LazyAttribute(lambda _: {"Content-Type": "application/json"})
    body = None
    client_ip = factory.Faker("ipv4")
    user_agent = factory.Faker("user_agent")
    request_id = factory.LazyAttribute(lambda _: str(uuid.uuid4()))
    timestamp = factory.LazyAttribute(lambda _: time.time())
    route_params = factory.LazyAttribute(lambda _: {})
    context = factory.LazyAttribute(lambda _: {})

    class Params:
        """Traits for common request types."""

        # Create a POST request with JSON body
        with_json_body = factory.Trait(
            method=HTTPMethod.POST,
            body=b'{"key": "value"}',
            headers={"Content-Type": "application/json"},
        )

        # Create a request with authentication
        with_bearer_token = factory.Trait(
            headers=factory.LazyAttribute(
                lambda _: {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {uuid.uuid4().hex}",
                }
            )
        )

        # Create a request with API key
        with_api_key = factory.Trait(
            headers=factory.LazyAttribute(
                lambda _: {
                    "Content-Type": "application/json",
                    "X-API-Key": f"apikey_{uuid.uuid4().hex}",
                }
            )
        )


class GatewayResponseFactory(factory.Factory):
    """Factory for GatewayResponse objects."""

    class Meta:
        model = GatewayResponse

    status_code = 200
    headers = factory.LazyAttribute(lambda _: {"Content-Type": "application/json"})
    body = None
    response_time = factory.LazyAttribute(lambda _: 0.05)  # 50ms
    upstream_service = factory.Faker("domain_name")

    class Params:
        """Traits for common response types."""

        # Error response
        error = factory.Trait(
            status_code=500,
            body=b'{"error": "Internal Server Error"}',
        )

        # Not found response
        not_found = factory.Trait(
            status_code=404,
            body=b'{"error": "Not Found"}',
        )

        # Unauthorized response
        unauthorized = factory.Trait(
            status_code=401,
            body=b'{"error": "Unauthorized"}',
        )

        # Rate limited response
        rate_limited = factory.Trait(
            status_code=429,
            body=b'{"error": "Too Many Requests"}',
            headers={
                "Content-Type": "application/json",
                "Retry-After": "60",
            },
        )


class RateLimitConfigFactory(factory.Factory):
    """Factory for RateLimitConfig objects."""

    class Meta:
        model = RateLimitConfig

    requests_per_window = 100
    window_size_seconds = 60
    algorithm = RateLimitAlgorithm.SLIDING_WINDOW_COUNTER
    action = RateLimitAction.REJECT
    delay_seconds = 1.0
    throttle_factor = 0.5

    class Params:
        """Traits for common rate limit configurations."""

        # Strict rate limiting
        strict = factory.Trait(
            requests_per_window=10,
            window_size_seconds=60,
            action=RateLimitAction.REJECT,
        )

        # Lenient rate limiting
        lenient = factory.Trait(
            requests_per_window=1000,
            window_size_seconds=60,
            action=RateLimitAction.LOG_ONLY,
        )


class UpstreamServerFactory(factory.Factory):
    """Factory for UpstreamServer objects."""

    class Meta:
        model = UpstreamServer

    id = factory.LazyAttribute(lambda _: str(uuid.uuid4()))
    host = factory.Faker("domain_name")
    port = factory.Sequence(lambda n: 8080 + n)
    protocol = ProtocolType.HTTP
    weight = 1
    max_connections = 1000
    health_check_enabled = True
    health_check_path = "/health"
    status = HealthStatus.HEALTHY
    current_connections = 0

    class Params:
        """Traits for server states."""

        # Unhealthy server
        unhealthy = factory.Trait(
            status=HealthStatus.UNHEALTHY,
        )

        # Server under maintenance
        maintenance = factory.Trait(
            status=HealthStatus.MAINTENANCE,
        )

        # High load server
        high_load = factory.Trait(
            current_connections=900,
        )


class UpstreamGroupFactory(factory.Factory):
    """Factory for UpstreamGroup objects."""

    class Meta:
        model = UpstreamGroup

    name = factory.Sequence(lambda n: f"upstream-group-{n}")
    servers = factory.LazyAttribute(lambda _: [])
    algorithm = LoadBalancingAlgorithm.ROUND_ROBIN
    health_check_enabled = True
    sticky_sessions = False
    session_cookie_name = "GATEWAY_SESSION"
    session_timeout = 3600
    retry_on_failure = True
    max_retries = 3
    retry_delay = 0.1
    current_index = 0
    sessions = factory.LazyAttribute(lambda _: {})

    class Params:
        """Traits for group configurations."""

        # Group with multiple servers
        with_servers = factory.Trait(
            servers=factory.LazyAttribute(lambda _: UpstreamServerFactory.build_batch(3))
        )

        # Sticky session group
        sticky = factory.Trait(
            sticky_sessions=True,
            session_cookie_name="STICKY_SESSION",
        )


class RouteConfigFactory(factory.Factory):
    """Factory for RouteConfig objects."""

    class Meta:
        model = RouteConfig

    path = factory.Sequence(lambda n: f"/api/v1/resource{n}")
    upstream = factory.Sequence(lambda n: f"service-{n}")
    methods = factory.LazyAttribute(lambda _: [HTTPMethod.GET])
    host = None
    headers = factory.LazyAttribute(lambda _: {})
    rewrite_path = None
    timeout = 30.0
    retries = 3
    rate_limit = None
    auth_required = True
    authentication_type = AuthenticationType.NONE
    name = factory.Sequence(lambda n: f"route-{n}")
    tags = factory.LazyAttribute(lambda _: [])

    class Params:
        """Traits for route configurations."""

        # Public route (no auth)
        public = factory.Trait(
            auth_required=False,
            authentication_type=AuthenticationType.NONE,
        )

        # Bearer token protected route
        bearer_protected = factory.Trait(
            auth_required=True,
            authentication_type=AuthenticationType.BEARER_TOKEN,
        )

        # API key protected route
        api_key_protected = factory.Trait(
            auth_required=True,
            authentication_type=AuthenticationType.API_KEY,
        )

        # Rate limited route
        rate_limited = factory.Trait(
            rate_limit=factory.SubFactory(RateLimitConfigFactory),
        )


class RoutingRuleFactory(factory.Factory):
    """Factory for RoutingRule objects."""

    class Meta:
        model = RoutingRule

    match_type = MatchType.PREFIX
    pattern = factory.Sequence(lambda n: f"/api/v{n}")
    weight = 1.0
    conditions = factory.LazyAttribute(lambda _: {})
    metadata = factory.LazyAttribute(lambda _: {})

    class Params:
        """Traits for routing rules."""

        # Exact match rule
        exact = factory.Trait(
            match_type=MatchType.EXACT,
        )

        # Regex match rule
        regex = factory.Trait(
            match_type=MatchType.REGEX,
            pattern=r"/api/v\d+/.*",
        )

        # Wildcard match rule
        wildcard = factory.Trait(
            match_type=MatchType.WILDCARD,
            pattern="/api/*/resource",
        )
