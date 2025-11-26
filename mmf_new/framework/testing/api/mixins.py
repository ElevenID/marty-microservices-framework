from typing import Any
from unittest.mock import AsyncMock, Mock

class ServiceTestMixin:
    """Mixin class providing common test patterns for services."""

    def setup_service_test_environment(self, service_name: str) -> dict[str, Any]:
        """Set up standardized test environment for a service."""
        return {
            "service_name": service_name,
            "environment": "testing",
            "debug": True,
            "database_url": "sqlite+aiosqlite:///:memory:",
        }

    def create_mock_dependencies(self, service_name: str) -> dict[str, Mock]:
        """Create mock dependencies for a service."""
        dependencies = {}

        # Common dependencies for all services
        dependencies["database"] = AsyncMock()
        dependencies["cache"] = Mock()
        dependencies["metrics_collector"] = Mock()
        dependencies["health_checker"] = Mock()

        # Service-specific dependencies based on patterns
        if "auth" in service_name.lower():
            dependencies["token_service"] = Mock()
            dependencies["user_repository"] = AsyncMock()

        if "notification" in service_name.lower():
            dependencies["email_service"] = Mock()
            dependencies["sms_service"] = Mock()

        if "payment" in service_name.lower():
            dependencies["payment_gateway"] = Mock()
            dependencies["fraud_detector"] = Mock()

        return dependencies

    def assert_standard_service_health(self, service_response: Any) -> None:
        """Standard assertions for service health checks."""
        assert service_response is not None
        assert hasattr(service_response, "status") or "status" in service_response

    def assert_standard_metrics_response(self, metrics_response: Any) -> None:
        """Standard assertions for metrics endpoints."""
        assert metrics_response is not None
        if isinstance(metrics_response, dict):
            assert "service" in metrics_response
            assert "metrics_count" in metrics_response
