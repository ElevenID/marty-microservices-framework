"""Unit tests for Gateway Domain Services - Route Matchers and Load Balancers."""

import pytest

from mmf.core.gateway import GatewayRequest, HealthStatus, UpstreamGroup, UpstreamServer
from mmf.framework.gateway.domain.services import (
    ExactMatcher,
    LeastConnectionsBalancer,
    PrefixMatcher,
    RandomBalancer,
    RegexMatcher,
    RoundRobinBalancer,
    TemplateMatcher,
    WeightedRoundRobinBalancer,
    WildcardMatcher,
)

# --- Route Matcher Tests ---


@pytest.mark.unit
class TestExactMatcher:
    """Tests for ExactMatcher class."""

    def test_matches_exact_path(self):
        matcher = ExactMatcher()
        assert matcher.matches("/users", "/users") is True

    def test_no_match_different_path(self):
        matcher = ExactMatcher()
        assert matcher.matches("/users", "/posts") is False

    def test_no_match_partial_path(self):
        matcher = ExactMatcher()
        assert matcher.matches("/users", "/users/123") is False

    def test_case_sensitive_by_default(self):
        matcher = ExactMatcher()
        assert matcher.matches("/Users", "/users") is False

    def test_case_insensitive_when_configured(self):
        matcher = ExactMatcher(case_sensitive=False)
        assert matcher.matches("/Users", "/users") is True

    def test_extract_params_returns_empty(self):
        matcher = ExactMatcher()
        assert matcher.extract_params("/users", "/users") == {}


@pytest.mark.unit
class TestPrefixMatcher:
    """Tests for PrefixMatcher class."""

    def test_matches_prefix(self):
        matcher = PrefixMatcher()
        assert matcher.matches("/api", "/api/users") is True

    def test_matches_exact_prefix(self):
        matcher = PrefixMatcher()
        assert matcher.matches("/api", "/api") is True

    def test_no_match_wrong_prefix(self):
        matcher = PrefixMatcher()
        assert matcher.matches("/api", "/admin/users") is False

    def test_case_insensitive(self):
        matcher = PrefixMatcher(case_sensitive=False)
        assert matcher.matches("/API", "/api/users") is True

    def test_extract_params_returns_remaining_path(self):
        matcher = PrefixMatcher()
        params = matcher.extract_params("/api", "/api/users/123")
        assert params == {"*": "users/123"}

    def test_extract_params_returns_empty_when_no_remaining(self):
        matcher = PrefixMatcher()
        params = matcher.extract_params("/api", "/api")
        assert params == {}


@pytest.mark.unit
class TestRegexMatcher:
    """Tests for RegexMatcher class."""

    def test_matches_simple_regex(self):
        matcher = RegexMatcher()
        assert matcher.matches(r"/users/\d+", "/users/123") is True

    def test_no_match_invalid_pattern(self):
        matcher = RegexMatcher()
        assert matcher.matches(r"/users/\d+", "/users/abc") is False

    def test_case_insensitive(self):
        matcher = RegexMatcher(case_sensitive=False)
        assert matcher.matches(r"/USERS/\d+", "/users/123") is True

    def test_caches_compiled_patterns(self):
        matcher = RegexMatcher()
        matcher.matches(r"/users/\d+", "/users/123")
        matcher.matches(r"/users/\d+", "/users/456")
        assert r"/users/\d+" in matcher._compiled_patterns

    def test_extract_params_with_named_groups(self):
        matcher = RegexMatcher()
        params = matcher.extract_params(r"/users/(?P<id>\d+)", "/users/123")
        assert params == {"id": "123"}

    def test_handles_invalid_regex_gracefully(self):
        matcher = RegexMatcher()
        assert matcher.matches(r"[invalid(regex", "/test") is False
        assert matcher.extract_params(r"[invalid(regex", "/test") == {}


@pytest.mark.unit
class TestWildcardMatcher:
    """Tests for WildcardMatcher class."""

    def test_matches_star_wildcard(self):
        matcher = WildcardMatcher()
        assert matcher.matches("/api/*", "/api/users") is True

    def test_matches_double_star(self):
        matcher = WildcardMatcher()
        assert matcher.matches("/api/**", "/api/users/123") is True

    def test_matches_question_mark(self):
        matcher = WildcardMatcher()
        assert matcher.matches("/api/user?", "/api/users") is True

    def test_no_match_different_path(self):
        matcher = WildcardMatcher()
        assert matcher.matches("/api/*", "/admin/users") is False

    def test_case_insensitive(self):
        matcher = WildcardMatcher(case_sensitive=False)
        assert matcher.matches("/API/*", "/api/users") is True

    def test_extract_params_returns_wildcard_path(self):
        matcher = WildcardMatcher()
        params = matcher.extract_params("/api/*", "/api/users")
        assert params == {"wildcard": "/api/users"}


@pytest.mark.unit
class TestTemplateMatcher:
    """Tests for TemplateMatcher class."""

    def test_matches_template_with_param(self):
        matcher = TemplateMatcher()
        assert matcher.matches("/users/{id}", "/users/123") is True

    def test_matches_template_with_multiple_params(self):
        matcher = TemplateMatcher()
        assert matcher.matches("/users/{user_id}/posts/{post_id}", "/users/1/posts/2") is True

    def test_no_match_wrong_path_structure(self):
        matcher = TemplateMatcher()
        assert matcher.matches("/users/{id}", "/posts/123") is False

    def test_case_insensitive(self):
        matcher = TemplateMatcher(case_sensitive=False)
        assert matcher.matches("/USERS/{id}", "/users/123") is True

    def test_extract_params_single_param(self):
        matcher = TemplateMatcher()
        params = matcher.extract_params("/users/{id}", "/users/123")
        assert params == {"id": "123"}

    def test_extract_params_multiple_params(self):
        matcher = TemplateMatcher()
        params = matcher.extract_params("/users/{user_id}/posts/{post_id}", "/users/1/posts/2")
        assert params == {"user_id": "1", "post_id": "2"}

    def test_caches_compiled_templates(self):
        matcher = TemplateMatcher()
        matcher.matches("/users/{id}", "/users/123")
        matcher.matches("/users/{id}", "/users/456")
        assert "/users/{id}" in matcher._compiled_patterns


# --- Load Balancer Tests ---


@pytest.fixture
def healthy_servers():
    """Create a list of healthy upstream servers."""
    return [
        UpstreamServer(id="s1", host="server1", port=8080, status=HealthStatus.HEALTHY, weight=1),
        UpstreamServer(id="s2", host="server2", port=8080, status=HealthStatus.HEALTHY, weight=2),
        UpstreamServer(id="s3", host="server3", port=8080, status=HealthStatus.HEALTHY, weight=1),
    ]


@pytest.fixture
def upstream_group(healthy_servers):
    """Create an upstream group with healthy servers."""
    group = UpstreamGroup(name="test-group", servers=healthy_servers)
    return group


@pytest.fixture
def gateway_request():
    """Create a sample gateway request."""
    return GatewayRequest(method="GET", path="/test")


@pytest.mark.unit
class TestRoundRobinBalancer:
    """Tests for RoundRobinBalancer class."""

    def test_selects_servers_in_order(self, upstream_group, gateway_request):
        balancer = RoundRobinBalancer()

        first = balancer.select_server(upstream_group, gateway_request)
        second = balancer.select_server(upstream_group, gateway_request)
        third = balancer.select_server(upstream_group, gateway_request)
        fourth = balancer.select_server(upstream_group, gateway_request)

        assert first.host == "server1"
        assert second.host == "server2"
        assert third.host == "server3"
        assert fourth.host == "server1"  # Wraps around

    def test_returns_none_when_no_healthy_servers(self, gateway_request):
        group = UpstreamGroup(
            name="unhealthy",
            servers=[UpstreamServer(id="s1", host="s1", port=80, status=HealthStatus.UNHEALTHY)],
        )
        balancer = RoundRobinBalancer()

        result = balancer.select_server(group, gateway_request)
        assert result is None


@pytest.mark.unit
class TestRandomBalancer:
    """Tests for RandomBalancer class."""

    def test_selects_from_healthy_servers(self, upstream_group, gateway_request):
        balancer = RandomBalancer()

        # Run multiple times to ensure it works
        for _ in range(10):
            server = balancer.select_server(upstream_group, gateway_request)
            assert server is not None
            assert server.status == HealthStatus.HEALTHY

    def test_returns_none_when_no_healthy_servers(self, gateway_request):
        group = UpstreamGroup(
            name="unhealthy",
            servers=[UpstreamServer(id="s1", host="s1", port=80, status=HealthStatus.UNHEALTHY)],
        )
        balancer = RandomBalancer()

        result = balancer.select_server(group, gateway_request)
        assert result is None


@pytest.mark.unit
class TestLeastConnectionsBalancer:
    """Tests for LeastConnectionsBalancer class."""

    def test_selects_server_with_least_connections(self, gateway_request):
        servers = [
            UpstreamServer(
                id="s1", host="s1", port=80, status=HealthStatus.HEALTHY, current_connections=10
            ),
            UpstreamServer(
                id="s2", host="s2", port=80, status=HealthStatus.HEALTHY, current_connections=2
            ),
            UpstreamServer(
                id="s3", host="s3", port=80, status=HealthStatus.HEALTHY, current_connections=5
            ),
        ]
        group = UpstreamGroup(name="test", servers=servers)
        balancer = LeastConnectionsBalancer()

        server = balancer.select_server(group, gateway_request)
        assert server.host == "s2"

    def test_returns_none_when_no_healthy_servers(self, gateway_request):
        group = UpstreamGroup(
            name="unhealthy",
            servers=[UpstreamServer(id="s1", host="s1", port=80, status=HealthStatus.UNHEALTHY)],
        )
        balancer = LeastConnectionsBalancer()

        result = balancer.select_server(group, gateway_request)
        assert result is None


@pytest.mark.unit
class TestWeightedRoundRobinBalancer:
    """Tests for WeightedRoundRobinBalancer class."""

    def test_selects_from_healthy_servers(self, upstream_group, gateway_request):
        balancer = WeightedRoundRobinBalancer()

        # Run multiple times, higher weight servers should be selected more often
        selections = {"server1": 0, "server2": 0, "server3": 0}
        for _ in range(100):
            server = balancer.select_server(upstream_group, gateway_request)
            selections[server.host] += 1

        # Server2 has weight 2, should be selected roughly twice as often
        # We use a loose assertion since it's probabilistic
        assert selections["server2"] > selections["server1"]

    def test_returns_none_when_no_healthy_servers(self, gateway_request):
        group = UpstreamGroup(
            name="unhealthy",
            servers=[UpstreamServer(id="s1", host="s1", port=80, status=HealthStatus.UNHEALTHY)],
        )
        balancer = WeightedRoundRobinBalancer()

        result = balancer.select_server(group, gateway_request)
        assert result is None

    def test_handles_zero_weight_servers(self, gateway_request):
        servers = [
            UpstreamServer(id="s1", host="s1", port=80, status=HealthStatus.HEALTHY, weight=0),
            UpstreamServer(id="s2", host="s2", port=80, status=HealthStatus.HEALTHY, weight=0),
        ]
        group = UpstreamGroup(name="zero-weight", servers=servers)
        balancer = WeightedRoundRobinBalancer()

        # Should still return a server (first one)
        server = balancer.select_server(group, gateway_request)
        assert server is not None
