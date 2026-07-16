"""
Unit tests for core gateway module.

Tests GatewayRequest, GatewayResponse, enums, and related data structures.
"""

import json
import time
import uuid

import pytest

from mmf.core.gateway import (
    AuthenticationType,
    GatewayRequest,
    GatewayResponse,
    HealthStatus,
    HTTPMethod,
    LoadBalancingAlgorithm,
    MatchType,
    MessagePattern,
    ProtocolType,
    RateLimitAction,
    RateLimitAlgorithm,
    RateLimitConfig,
    RouteConfig,
    RoutingRule,
    RoutingStrategy,
    UpstreamGroup,
    UpstreamServer,
)


class TestHTTPMethod:
    """Tests for HTTPMethod enum."""

    def test_method_values(self):
        """Test HTTP method string values."""
        assert HTTPMethod.GET.value == "GET"
        assert HTTPMethod.POST.value == "POST"
        assert HTTPMethod.PUT.value == "PUT"
        assert HTTPMethod.DELETE.value == "DELETE"
        assert HTTPMethod.PATCH.value == "PATCH"
        assert HTTPMethod.HEAD.value == "HEAD"
        assert HTTPMethod.OPTIONS.value == "OPTIONS"
        assert HTTPMethod.TRACE.value == "TRACE"
        assert HTTPMethod.CONNECT.value == "CONNECT"

    def test_all_methods_exist(self):
        """Test all expected methods are defined."""
        methods = list(HTTPMethod)
        assert len(methods) == 9


class TestProtocolType:
    """Tests for ProtocolType enum."""

    def test_protocol_values(self):
        """Test protocol string values."""
        assert ProtocolType.HTTP.value == "http"
        assert ProtocolType.HTTPS.value == "https"
        assert ProtocolType.GRPC.value == "grpc"
        assert ProtocolType.WEBSOCKET.value == "websocket"
        assert ProtocolType.KAFKA.value == "kafka"
        assert ProtocolType.RABBITMQ.value == "rabbitmq"

    def test_all_protocols_exist(self):
        """Test all expected protocols are defined."""
        protocols = list(ProtocolType)
        assert len(protocols) >= 10


class TestAuthenticationType:
    """Tests for AuthenticationType enum."""

    def test_auth_type_values(self):
        """Test authentication type string values."""
        assert AuthenticationType.NONE.value == "none"
        assert AuthenticationType.API_KEY.value == "api_key"
        assert AuthenticationType.BEARER_TOKEN.value == "bearer_token"
        assert AuthenticationType.JWT.value == "jwt"
        assert AuthenticationType.OAUTH2.value == "oauth2"
        assert AuthenticationType.BASIC_AUTH.value == "basic_auth"
        assert AuthenticationType.MTLS.value == "mtls"
        assert AuthenticationType.CUSTOM.value == "custom"

    def test_all_auth_types_exist(self):
        """Test all expected auth types are defined."""
        auth_types = list(AuthenticationType)
        assert len(auth_types) == 8


class TestMessagePattern:
    """Tests for MessagePattern enum."""

    def test_pattern_values(self):
        """Test message pattern string values."""
        assert MessagePattern.REQUEST_REPLY.value == "request_reply"
        assert MessagePattern.FIRE_AND_FORGET.value == "fire_and_forget"
        assert MessagePattern.PUBLISH_SUBSCRIBE.value == "publish_subscribe"
        assert MessagePattern.POINT_TO_POINT.value == "point_to_point"


class TestRoutingStrategy:
    """Tests for RoutingStrategy enum."""

    def test_strategy_values(self):
        """Test routing strategy string values."""
        assert RoutingStrategy.PATH_BASED.value == "path_based"
        assert RoutingStrategy.HOST_BASED.value == "host_based"
        assert RoutingStrategy.HEADER_BASED.value == "header_based"
        assert RoutingStrategy.WEIGHT_BASED.value == "weight_based"
        assert RoutingStrategy.CANARY.value == "canary"
        assert RoutingStrategy.AB_TEST.value == "ab_test"


class TestMatchType:
    """Tests for MatchType enum."""

    def test_match_type_values(self):
        """Test match type string values."""
        assert MatchType.EXACT.value == "exact"
        assert MatchType.PREFIX.value == "prefix"
        assert MatchType.REGEX.value == "regex"
        assert MatchType.WILDCARD.value == "wildcard"
        assert MatchType.TEMPLATE.value == "template"


class TestLoadBalancingAlgorithm:
    """Tests for LoadBalancingAlgorithm enum."""

    def test_algorithm_values(self):
        """Test load balancing algorithm string values."""
        assert LoadBalancingAlgorithm.ROUND_ROBIN.value == "round_robin"
        assert LoadBalancingAlgorithm.WEIGHTED_ROUND_ROBIN.value == "weighted_round_robin"
        assert LoadBalancingAlgorithm.LEAST_CONNECTIONS.value == "least_connections"
        assert LoadBalancingAlgorithm.RANDOM.value == "random"
        assert LoadBalancingAlgorithm.CONSISTENT_HASH.value == "consistent_hash"
        assert LoadBalancingAlgorithm.IP_HASH.value == "ip_hash"
        assert LoadBalancingAlgorithm.LEAST_RESPONSE_TIME.value == "least_response_time"

    def test_all_algorithms_exist(self):
        """Test all expected algorithms are defined."""
        algorithms = list(LoadBalancingAlgorithm)
        assert len(algorithms) >= 7


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self):
        """Test health status string values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"
        assert HealthStatus.MAINTENANCE.value == "maintenance"


class TestRateLimitAlgorithm:
    """Tests for RateLimitAlgorithm enum."""

    def test_algorithm_values(self):
        """Test rate limit algorithm string values."""
        assert RateLimitAlgorithm.TOKEN_BUCKET.value == "token_bucket"
        assert RateLimitAlgorithm.LEAKY_BUCKET.value == "leaky_bucket"
        assert RateLimitAlgorithm.FIXED_WINDOW.value == "fixed_window"
        assert RateLimitAlgorithm.SLIDING_WINDOW_LOG.value == "sliding_window_log"
        assert RateLimitAlgorithm.SLIDING_WINDOW_COUNTER.value == "sliding_window_counter"


class TestRateLimitAction:
    """Tests for RateLimitAction enum."""

    def test_action_values(self):
        """Test rate limit action string values."""
        assert RateLimitAction.REJECT.value == "reject"
        assert RateLimitAction.DELAY.value == "delay"
        assert RateLimitAction.THROTTLE.value == "throttle"
        assert RateLimitAction.LOG_ONLY.value == "log_only"


class TestGatewayRequest:
    """Tests for GatewayRequest class."""

    def test_request_defaults(self):
        """Test gateway request with minimal required fields."""
        request = GatewayRequest(method=HTTPMethod.GET, path="/api/test")

        assert request.method == HTTPMethod.GET
        assert request.path == "/api/test"
        assert request.query_params == {}
        assert request.headers == {}
        assert request.body is None
        assert request.client_ip is None
        assert request.user_agent is None
        assert request.request_id is not None
        assert uuid.UUID(request.request_id)  # Should be valid UUID
        assert request.timestamp > 0
        assert request.route_params == {}
        assert request.context == {}

    def test_request_with_headers(self):
        """Test request with headers."""
        headers = {"Content-Type": "application/json", "Authorization": "Bearer token"}
        request = GatewayRequest(
            method=HTTPMethod.POST,
            path="/api/users",
            headers=headers,
        )
        assert request.headers == headers

    def test_request_with_body(self):
        """Test request with body."""
        body = b'{"name": "test"}'
        request = GatewayRequest(
            method=HTTPMethod.POST,
            path="/api/users",
            body=body,
        )
        assert request.body == body

    def test_request_with_query_params(self):
        """Test request with query parameters."""
        query_params = {"page": ["1"], "limit": ["10"]}
        request = GatewayRequest(
            method=HTTPMethod.GET,
            path="/api/users",
            query_params=query_params,
        )
        assert request.query_params == query_params

    def test_request_with_client_info(self):
        """Test request with client information."""
        request = GatewayRequest(
            method=HTTPMethod.GET,
            path="/api/test",
            client_ip="192.168.1.100",
            user_agent="Test/1.0",
        )
        assert request.client_ip == "192.168.1.100"
        assert request.user_agent == "Test/1.0"

    def test_get_header_existing(self):
        """Test getting an existing header (case-insensitive)."""
        request = GatewayRequest(
            method=HTTPMethod.GET,
            path="/api/test",
            headers={"Content-Type": "application/json"},
        )
        assert request.get_header("Content-Type") == "application/json"
        assert request.get_header("content-type") == "application/json"
        assert request.get_header("CONTENT-TYPE") == "application/json"

    def test_get_header_missing_with_default(self):
        """Test getting a missing header with default."""
        request = GatewayRequest(method=HTTPMethod.GET, path="/api/test")
        assert request.get_header("Missing", "default") == "default"

    def test_get_header_missing_without_default(self):
        """Test getting a missing header without default."""
        request = GatewayRequest(method=HTTPMethod.GET, path="/api/test")
        assert request.get_header("Missing") is None

    def test_request_unique_ids(self):
        """Test that requests get unique IDs."""
        request1 = GatewayRequest(method=HTTPMethod.GET, path="/api/test")
        request2 = GatewayRequest(method=HTTPMethod.GET, path="/api/test")
        assert request1.request_id != request2.request_id

    def test_request_with_context(self):
        """Test request with context data."""
        context = {"user": {"id": "123", "roles": ["admin"]}}
        request = GatewayRequest(
            method=HTTPMethod.GET,
            path="/api/test",
            context=context,
        )
        assert request.context == context


class TestGatewayResponse:
    """Tests for GatewayResponse class."""

    def test_response_defaults(self):
        """Test gateway response defaults."""
        response = GatewayResponse()

        assert response.status_code == 200
        assert response.headers == {}
        assert response.body is None
        assert response.response_time is None
        assert response.upstream_service is None

    def test_response_with_status(self):
        """Test response with status code."""
        response = GatewayResponse(status_code=404)
        assert response.status_code == 404

    def test_response_with_body(self):
        """Test response with body."""
        body = b'{"status": "ok"}'
        response = GatewayResponse(body=body)
        assert response.body == body

    def test_response_set_header(self):
        """Test setting response header."""
        response = GatewayResponse()
        response.set_header("X-Custom", "value")
        assert response.headers["X-Custom"] == "value"

    def test_response_set_header_overwrites(self):
        """Test that setting header overwrites existing."""
        response = GatewayResponse(headers={"X-Custom": "old"})
        response.set_header("X-Custom", "new")
        assert response.headers["X-Custom"] == "new"

    def test_response_set_json_body(self):
        """Test setting JSON response body."""
        response = GatewayResponse()
        data = {"status": "ok", "data": [1, 2, 3]}
        response.set_json_body(data)

        assert response.body == json.dumps(data).encode("utf-8")
        assert response.headers["Content-Type"] == "application/json"
        assert response.headers["Content-Length"] == str(len(response.body))

    def test_response_with_metadata(self):
        """Test response with metadata."""
        response = GatewayResponse(
            status_code=200,
            response_time=0.05,
            upstream_service="user-service",
        )
        assert response.response_time == 0.05
        assert response.upstream_service == "user-service"


class TestRateLimitConfig:
    """Tests for RateLimitConfig class."""

    def test_config_defaults(self):
        """Test rate limit config defaults."""
        config = RateLimitConfig()

        assert config.requests_per_window == 100
        assert config.window_size_seconds == 60
        assert config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW_COUNTER
        assert config.action == RateLimitAction.REJECT
        assert config.delay_seconds == 1.0
        assert config.throttle_factor == 0.5

    def test_config_custom_values(self):
        """Test rate limit config with custom values."""
        config = RateLimitConfig(
            requests_per_window=10,
            window_size_seconds=10,
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            action=RateLimitAction.DELAY,
            delay_seconds=2.0,
        )
        assert config.requests_per_window == 10
        assert config.window_size_seconds == 10
        assert config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET
        assert config.action == RateLimitAction.DELAY
        assert config.delay_seconds == 2.0


class TestUpstreamServer:
    """Tests for UpstreamServer class."""

    def test_server_required_fields(self):
        """Test upstream server with required fields."""
        server = UpstreamServer(
            id="server-1",
            host="localhost",
            port=8080,
        )

        assert server.id == "server-1"
        assert server.host == "localhost"
        assert server.port == 8080
        assert server.protocol == ProtocolType.HTTP
        assert server.weight == 1
        assert server.max_connections == 1000
        assert server.health_check_enabled is True
        assert server.health_check_path == "/health"
        assert server.status == HealthStatus.UNKNOWN
        assert server.current_connections == 0

    def test_server_url_property(self):
        """Test upstream server URL property."""
        server = UpstreamServer(
            id="server-1",
            host="example.com",
            port=443,
            protocol=ProtocolType.HTTPS,
        )
        assert server.url == "https://example.com:443"

    def test_server_with_custom_protocol(self):
        """Test upstream server with custom protocol."""
        server = UpstreamServer(
            id="grpc-server",
            host="localhost",
            port=50051,
            protocol=ProtocolType.GRPC,
        )
        assert server.protocol == ProtocolType.GRPC
        assert server.url == "grpc://localhost:50051"

    def test_server_with_weight(self):
        """Test upstream server with custom weight."""
        server = UpstreamServer(
            id="heavy-server",
            host="localhost",
            port=8080,
            weight=5,
        )
        assert server.weight == 5


class TestUpstreamGroup:
    """Tests for UpstreamGroup class."""

    def test_group_defaults(self):
        """Test upstream group defaults."""
        group = UpstreamGroup(name="backend-group")

        assert group.name == "backend-group"
        assert group.servers == []
        assert group.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN
        assert group.health_check_enabled is True
        assert group.sticky_sessions is False
        assert group.session_cookie_name == "GATEWAY_SESSION"
        assert group.session_timeout == 3600
        assert group.retry_on_failure is True
        assert group.max_retries == 3
        assert group.retry_delay == 0.1
        assert group.current_index == 0
        assert group.sessions == {}

    def test_group_add_server(self):
        """Test adding server to group."""
        group = UpstreamGroup(name="test-group")
        server = UpstreamServer(id="s1", host="localhost", port=8080)

        group.add_server(server)

        assert len(group.servers) == 1
        assert group.servers[0] == server

    def test_group_remove_server(self):
        """Test removing server from group."""
        server1 = UpstreamServer(id="s1", host="localhost", port=8080)
        server2 = UpstreamServer(id="s2", host="localhost", port=8081)
        group = UpstreamGroup(name="test-group", servers=[server1, server2])

        group.remove_server("s1")

        assert len(group.servers) == 1
        assert group.servers[0].id == "s2"

    def test_group_remove_nonexistent_server(self):
        """Test removing non-existent server doesn't raise."""
        group = UpstreamGroup(name="test-group")
        group.remove_server("nonexistent")  # Should not raise

    def test_group_get_healthy_servers(self):
        """Test getting healthy servers."""
        server1 = UpstreamServer(id="s1", host="localhost", port=8080, status=HealthStatus.HEALTHY)
        server2 = UpstreamServer(
            id="s2", host="localhost", port=8081, status=HealthStatus.UNHEALTHY
        )
        server3 = UpstreamServer(id="s3", host="localhost", port=8082, status=HealthStatus.HEALTHY)
        group = UpstreamGroup(name="test-group", servers=[server1, server2, server3])

        healthy = group.get_healthy_servers()

        assert len(healthy) == 2
        assert server1 in healthy
        assert server3 in healthy
        assert server2 not in healthy

    def test_group_with_sticky_sessions(self):
        """Test group with sticky sessions enabled."""
        group = UpstreamGroup(
            name="sticky-group",
            sticky_sessions=True,
            session_cookie_name="STICKY_ID",
            session_timeout=7200,
        )
        assert group.sticky_sessions is True
        assert group.session_cookie_name == "STICKY_ID"
        assert group.session_timeout == 7200


class TestRouteConfig:
    """Tests for RouteConfig class."""

    def test_route_required_fields(self):
        """Test route config with required fields."""
        route = RouteConfig(path="/api/users", upstream="user-service")

        assert route.path == "/api/users"
        assert route.upstream == "user-service"
        assert route.methods == [HTTPMethod.GET]
        assert route.host is None
        assert route.headers == {}
        assert route.rewrite_path is None
        assert route.timeout == 30.0
        assert route.retries == 3
        assert route.rate_limit is None
        assert route.auth_required is True
        assert route.authentication_type == AuthenticationType.NONE
        assert route.name is None
        assert route.tags == []

    def test_route_with_multiple_methods(self):
        """Test route with multiple HTTP methods."""
        route = RouteConfig(
            path="/api/users",
            upstream="user-service",
            methods=[HTTPMethod.GET, HTTPMethod.POST, HTTPMethod.PUT],
        )
        assert len(route.methods) == 3

    def test_route_with_rewrite(self):
        """Test route with path rewrite."""
        route = RouteConfig(
            path="/v1/users",
            upstream="user-service",
            rewrite_path="/users",
        )
        assert route.rewrite_path == "/users"

    def test_route_with_auth(self):
        """Test route with authentication."""
        route = RouteConfig(
            path="/api/admin",
            upstream="admin-service",
            auth_required=True,
            authentication_type=AuthenticationType.JWT,
        )
        assert route.auth_required is True
        assert route.authentication_type == AuthenticationType.JWT

    def test_route_with_rate_limit(self):
        """Test route with rate limit config."""
        rate_limit = RateLimitConfig(requests_per_window=10)
        route = RouteConfig(
            path="/api/public",
            upstream="public-service",
            rate_limit=rate_limit,
        )
        assert route.rate_limit == rate_limit
        assert route.rate_limit.requests_per_window == 10


class TestRoutingRule:
    """Tests for RoutingRule class."""

    def test_rule_required_fields(self):
        """Test routing rule with required fields."""
        rule = RoutingRule(
            match_type=MatchType.PREFIX,
            pattern="/api",
        )

        assert rule.match_type == MatchType.PREFIX
        assert rule.pattern == "/api"
        assert rule.weight == 1.0
        assert rule.conditions == {}
        assert rule.metadata == {}

    def test_rule_with_weight(self):
        """Test routing rule with custom weight."""
        rule = RoutingRule(
            match_type=MatchType.EXACT,
            pattern="/api/v2",
            weight=0.8,
        )
        assert rule.weight == 0.8

    def test_rule_with_conditions(self):
        """Test routing rule with conditions."""
        rule = RoutingRule(
            match_type=MatchType.REGEX,
            pattern=r"/api/v\d+/.*",
            conditions={"header": "X-Version", "value": "2"},
        )
        assert rule.conditions["header"] == "X-Version"

    def test_rule_with_metadata(self):
        """Test routing rule with metadata."""
        rule = RoutingRule(
            match_type=MatchType.WILDCARD,
            pattern="/api/*/resource",
            metadata={"description": "Wildcard route"},
        )
        assert rule.metadata["description"] == "Wildcard route"
