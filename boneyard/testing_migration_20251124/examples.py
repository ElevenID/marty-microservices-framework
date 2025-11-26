"""
Example tests demonstrating DRY testing patterns for microservices.

These examples show how to use the testing framework infrastructure
for different types of tests (unit, integration, performance).
"""

import pytest

from marty_msf.framework.events import BaseEvent
from marty_msf.framework.testing.patterns import (
    AsyncTestCase,
    MockRepository,
    PerformanceTestMixin,
    ServiceTestMixin,
    TestEventCollector,
    create_test_config,
    integration_test,
    unit_test,
    wait_for_condition,
)


class UserCreatedEvent(BaseEvent):
    """Example domain event."""

    def __init__(self, user_id: str, email: str):
        super().__init__()
        self.user_id = user_id
        self.email = email
        self.event_type = "user.created"

    def to_dict(self) -> dict:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "email": self.email,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserCreatedEvent":
        """Create event from dictionary."""
        event = cls(data["user_id"], data["email"])
        event.event_id = data["event_id"]
        event.timestamp = data["timestamp"]
        return event


class TestEvent(BaseEvent):
    """Simple test event for general testing."""

    def __init__(self, event_type: str, data: dict | None = None):
        super().__init__()
        self.event_type = event_type
        self.data = data or {}

    def to_dict(self) -> dict:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TestEvent":
        """Create event from dictionary."""
        event = cls(data["event_type"], data.get("data"))
        event.event_id = data["event_id"]
        event.timestamp = data["timestamp"]
        return event


class User:
    """Example domain model."""

    def __init__(self, id: str | None = None, email: str | None = None, name: str | None = None):
        self.id = id
        self.email = email
        self.name = name


class UserService:
    """Example service for testing."""

    def __init__(self, repository, event_bus):
        self.repository = repository
        self.event_bus = event_bus

    async def create_user(self, email: str, name: str) -> User:
        """Create a new user."""
        user = User(id="user_123", email=email, name=name)
        await self.repository.create(user)

        # Publish domain event
        if user.id and user.email:  # Ensure values exist
            event = UserCreatedEvent(user.id, user.email)
            await self.event_bus.publish(event)

        return user

    async def get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        return await self.repository.get_by_id(user_id)

    async def health_check(self) -> dict:
        """Health check."""
        return {"status": "healthy", "service": "user_service"}


# Unit Tests
class TestUserServiceUnit(AsyncTestCase, ServiceTestMixin):
    """Unit tests for UserService."""

    async def setup_method(self):
        """Setup for each test."""
        await self.setup_async_test()

        # Setup mock dependencies
        self.mock_repository = MockRepository()
        self.user_service = UserService(
            repository=self.mock_repository,
            event_bus=self.test_event_bus,
        )

    @unit_test
    async def test_create_user_success(self):
        """Test successful user creation."""
        # Act
        user = await self.user_service.create_user("test@example.com", "Test User")

        # Assert
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert user.id == "user_123"

        # Verify event was published
        self.event_collector.assert_event_published("user.created")
        events = self.event_collector.get_events_of_type("user.created")
        # Cast to correct type for attribute access
        user_event = events[0]
        if isinstance(user_event, UserCreatedEvent):
            assert user_event.user_id == "user_123"
            assert user_event.email == "test@example.com"

    @unit_test
    async def test_get_user_existing(self):
        """Test getting existing user."""
        # Arrange
        user = User(id="user_123", email="test@example.com", name="Test User")
        await self.mock_repository.create(user)

        # Act
        result = await self.user_service.get_user("user_123")

        # Assert
        assert result is not None
        assert result.email == "test@example.com"
        assert result.name == "Test User"

    @unit_test
    async def test_get_user_not_found(self):
        """Test getting non-existent user."""
        # Act
        result = await self.user_service.get_user("non_existent")

        # Assert
        assert result is None

    @unit_test
    async def test_health_check(self):
        """Test service health check."""
        # Act
        health = await self.user_service.health_check()

        # Assert
        self.assert_standard_service_health(health)
        assert health["service"] == "user_service"


# Integration Tests
class TestUserServiceIntegration(AsyncTestCase, ServiceTestMixin):
    """Integration tests for UserService."""

    async def setup_method(self):
        """Setup for each test."""
        await self.setup_async_test()

        # Create mock repository for integration testing
        self.mock_repository = MockRepository()

        # Use real database session
        self.session = None
        async with self.test_db.get_session() as session:
            self.session = session

        # Setup service with real dependencies
        self.user_service = UserService(
            repository=self.mock_repository,  # Still mock for simplicity
            event_bus=self.test_event_bus,
        )

    @integration_test
    async def test_user_creation_flow(self):
        """Test complete user creation flow."""
        # Act - Create user
        user = await self.user_service.create_user("integration@example.com", "Integration Test")

        # Assert - User was created
        assert user.email == "integration@example.com"

        # Assert - Can retrieve created user
        if user.id:  # Ensure user.id is not None
            retrieved_user = await self.user_service.get_user(user.id)
            assert retrieved_user is not None
            assert retrieved_user.email == user.email

        # Assert - Event was published and processed
        self.event_collector.assert_event_published("user.created")

        # Verify event processing completed
        await wait_for_condition(
            lambda: len(self.event_collector.events) == 1,
            timeout=2.0,
        )

    @integration_test
    async def test_service_with_database_transaction(self, test_session):
        """Test service operations with database transactions."""
        # This would use real database operations in a real implementation
        # For now, demonstrating the pattern with mock repository

        # Act - Multiple operations in transaction
        user1 = await self.user_service.create_user("user1@example.com", "User 1")
        user2 = await self.user_service.create_user("user2@example.com", "User 2")

        # Assert - Both users exist
        if user1.id and user2.id:  # Ensure IDs are not None
            assert await self.user_service.get_user(user1.id) is not None
            assert await self.user_service.get_user(user2.id) is not None


# Performance Tests
@pytest.mark.skip(reason="Performance tests are expensive and should be run separately")
class TestUserServicePerformance(AsyncTestCase, ServiceTestMixin, PerformanceTestMixin):
    """Performance tests for UserService."""

    async def setup_method(self):
        """Setup for each test."""
        await self.setup_async_test()

        # Create mock repository for performance testing
        self.mock_repository = MockRepository()

        self.user_service = UserService(
            repository=self.mock_repository,
            event_bus=self.test_event_bus,
        )

        # Assert - Multiple events published
        assert len(self.event_collector.events) == 2


# Specialized Test Patterns
class TestEventDrivenPatterns(AsyncTestCase):
    """Test patterns for event-driven architecture."""

    @unit_test
    async def test_event_handler_registration(self):
        """Test event handler registration pattern."""
        # Setup custom event collector for specific events
        user_event_collector = TestEventCollector(event_types=["user.created", "user.updated"])
        await self.test_event_bus.subscribe(user_event_collector)

        # Act - Publish various events
        await self.test_event_bus.publish(UserCreatedEvent("user_1", "user1@example.com"))
        await self.test_event_bus.publish(TestEvent("system.startup"))

        # Wait for event processing
        await wait_for_condition(
            lambda: len(user_event_collector.events) >= 1,
            timeout=1.0,
        )

        # Assert - Only user events were collected
        assert len(user_event_collector.events) == 1
        assert user_event_collector.events[0].event_type == "user.created"

    @integration_test
    async def test_event_ordering(self):
        """Test event ordering in event-driven flows."""
        events_received = []

        class OrderTrackingCollector(TestEventCollector):
            async def handle(self, event):
                events_received.append(event.event_type)
                await super().handle(event)

        # Setup
        order_collector = OrderTrackingCollector()
        await self.test_event_bus.subscribe(order_collector)

        # Act - Publish events in order
        event_types = ["event.1", "event.2", "event.3"]
        for event_type in event_types:
            await self.test_event_bus.publish(TestEvent(event_type))

        # Wait for all events to be processed
        await wait_for_condition(
            lambda: len(events_received) == 3,
            timeout=2.0,
        )

        # Assert - Events processed in order
        assert events_received == event_types


class TestServiceConfiguration(ServiceTestMixin):
    """Test service configuration patterns."""

    @unit_test
    def test_service_config_creation(self):
        """Test service configuration creation."""
        # Act
        config = self.setup_service_test_environment("test_service")

        # Assert
        assert config["service_name"] == "test_service"
        assert config["environment"] == "testing"
        assert config["debug"] is True

    @unit_test
    def test_mock_dependencies_creation(self):
        """Test mock dependencies creation."""
        # Act
        deps = self.create_mock_dependencies("auth_service")

        # Assert - Common dependencies
        assert "database" in deps
        assert "cache" in deps
        assert "metrics_collector" in deps

        # Assert - Auth-specific dependencies
        assert "token_service" in deps
        assert "user_repository" in deps

    @unit_test
    def test_config_with_overrides(self):
        """Test configuration with custom overrides."""
        # Act
        config = create_test_config(
            service_name="custom_service",
            custom_setting="value",
        )

        # Assert
        assert config["service_name"] == "custom_service"
        assert config["custom_setting"] == "value"
        assert config["environment"] == "testing"  # Default preserved


# Pytest configuration for the examples
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "slow: mark test as slow test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add default markers."""
    for item in items:
        # Add unit marker if no other test type marker present
        test_markers = [mark.name for mark in item.iter_markers()]
        if not any(marker in test_markers for marker in ["unit", "integration", "performance"]):
            item.add_marker(pytest.mark.unit)
