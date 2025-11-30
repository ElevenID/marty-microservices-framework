from mmf_new.framework.gateway.domain.services import (
    ExactMatcher,
    PrefixMatcher,
    RegexMatcher,
    WildcardMatcher,
)


class TestExactMatcher:
    def test_matches_exact(self):
        matcher = ExactMatcher()
        assert matcher.matches("/api/v1/users", "/api/v1/users") is True
        assert matcher.matches("/api/v1/users", "/api/v1/users/") is False
        assert matcher.matches("/api/v1/users", "/api/v1/other") is False

    def test_matches_case_insensitive(self):
        matcher = ExactMatcher(case_sensitive=False)
        assert matcher.matches("/API/v1/Users", "/api/v1/users") is True

    def test_extract_params(self):
        matcher = ExactMatcher()
        assert matcher.extract_params("/api/v1/users", "/api/v1/users") == {}


class TestPrefixMatcher:
    def test_matches_prefix(self):
        matcher = PrefixMatcher()
        assert matcher.matches("/api/v1", "/api/v1/users") is True
        assert matcher.matches("/api/v1", "/api/v1") is True
        assert matcher.matches("/api/v1", "/api/v2/users") is False

    def test_extract_params(self):
        matcher = PrefixMatcher()
        params = matcher.extract_params("/api/v1", "/api/v1/users/123")
        assert params == {"*": "users/123"}

        params = matcher.extract_params("/api/v1", "/api/v1")
        assert params == {}


class TestRegexMatcher:
    def test_matches_regex(self):
        matcher = RegexMatcher()
        assert matcher.matches(r"^/users/\d+$", "/users/123") is True
        assert matcher.matches(r"^/users/\d+$", "/users/abc") is False

    def test_extract_params(self):
        matcher = RegexMatcher()
        pattern = r"^/users/(?P<id>\d+)$"
        params = matcher.extract_params(pattern, "/users/123")
        assert params == {"id": "123"}


class TestWildcardMatcher:
    def test_matches_wildcard(self):
        matcher = WildcardMatcher()
        assert matcher.matches("/users/*", "/users/123") is True
        assert matcher.matches("/users/*/profile", "/users/123/profile") is True
        assert matcher.matches("/users/*", "/other/123") is False
