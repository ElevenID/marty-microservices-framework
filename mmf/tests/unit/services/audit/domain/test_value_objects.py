"""
Unit tests for Audit domain value objects.
"""

from datetime import datetime, timezone

from mmf.services.audit.domain.value_objects import (
    ActorInfo,
    PerformanceMetrics,
    RequestContext,
    ResponseMetadata,
)


class TestRequestContext:
    """Test suite for RequestContext value object."""

    def test_create_minimal(self):
        """Test creating with minimal fields."""
        ctx = RequestContext(method="GET", endpoint="/api/test")
        assert ctx.method == "GET"
        assert ctx.endpoint == "/api/test"
        assert ctx.source_ip is None
        assert ctx.request_id is None

    def test_create_full(self):
        """Test creating with all fields."""
        ctx = RequestContext(
            method="POST",
            endpoint="/api/users",
            source_ip="127.0.0.1",
            user_agent="TestAgent",
            request_id="req-123",
            correlation_id="corr-456",
            trace_id="trace-789",
            span_id="span-012",
            query_params={"q": "test"},
            headers={"Content-Type": "application/json"},
        )

        assert ctx.method == "POST"
        assert ctx.endpoint == "/api/users"
        assert ctx.source_ip == "127.0.0.1"
        assert ctx.headers["Content-Type"] == "application/json"

    def test_to_dict(self):
        """Test dictionary conversion."""
        ctx = RequestContext(method="GET", endpoint="/api/test", request_id="req-1")
        data = ctx.to_dict()

        assert data["method"] == "GET"
        assert data["endpoint"] == "/api/test"
        assert data["request_id"] == "req-1"
        assert data["source_ip"] is None


class TestResponseMetadata:
    """Test suite for ResponseMetadata value object."""

    def test_create_success(self):
        """Test creating success response metadata."""
        meta = ResponseMetadata(
            status_code=200, response_size=1024, headers={"Content-Type": "application/json"}
        )
        assert meta.status_code == 200
        assert meta.response_size == 1024
        assert meta.error_code is None

    def test_create_error(self):
        """Test creating error response metadata."""
        meta = ResponseMetadata(
            status_code=400, error_code="INVALID_INPUT", error_message="Bad request"
        )
        assert meta.status_code == 400
        assert meta.error_code == "INVALID_INPUT"
        assert meta.error_message == "Bad request"

    def test_to_dict(self):
        """Test dictionary conversion."""
        meta = ResponseMetadata(status_code=200, response_size=100)
        data = meta.to_dict()
        assert data["status_code"] == 200
        assert data["response_size"] == 100


class TestPerformanceMetrics:
    """Test suite for PerformanceMetrics value object."""

    def test_create(self):
        """Test creating performance metrics."""
        now = datetime.now(timezone.utc)
        metrics = PerformanceMetrics(
            duration_ms=150.5,
            started_at=now,
            completed_at=now,
            is_slow_request=True,
            is_large_response=False,
        )

        assert metrics.duration_ms == 150.5
        assert metrics.is_slow_request is True
        assert metrics.is_large_response is False

    def test_to_dict(self):
        """Test dictionary conversion."""
        now = datetime.now(timezone.utc)
        metrics = PerformanceMetrics(duration_ms=100.0, started_at=now, completed_at=now)
        data = metrics.to_dict()
        assert data["duration_ms"] == 100.0
        assert isinstance(data["started_at"], str)


class TestActorInfo:
    """Test suite for ActorInfo value object."""

    def test_create_user(self):
        """Test creating user actor info."""
        actor = ActorInfo(user_id="user-123", username="testuser", roles=("admin", "user"))
        assert actor.user_id == "user-123"
        assert actor.username == "testuser"
        assert "admin" in actor.roles

    def test_create_service(self):
        """Test creating service actor info."""
        actor = ActorInfo(client_id="service-abc", api_key_id="key-xyz")
        assert actor.client_id == "service-abc"
        assert actor.api_key_id == "key-xyz"
        assert actor.user_id is None

    def test_to_dict(self):
        """Test dictionary conversion."""
        actor = ActorInfo(user_id="u1", roles=("r1",))
        data = actor.to_dict()
        assert data["user_id"] == "u1"
        assert data["roles"] == ["r1"]
