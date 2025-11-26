# DRY Testing Infrastructure

This comprehensive testing infrastructure provides DRY (Don't Repeat Yourself) patterns and utilities for microservices testing, from simple unit tests to complex integration and performance testing.

## Overview

The framework provides two levels of testing infrastructure:

1. **DRY Testing Patterns** - Simple, reusable patterns for common testing scenarios
2. **Advanced Testing Framework** - Comprehensive testing capabilities including contract testing, chaos engineering, and automation

## Quick Start - DRY Testing Patterns

### Basic Test Structure

```python
from framework.testing import (
    AsyncTestCase,
    ServiceTestMixin,
    TestEventCollector,
    MockRepository,
    unit_test,
    integration_test,
)

class TestUserService(AsyncTestCase, ServiceTestMixin):
    """Example test class using DRY patterns."""

    async def setup_method(self):
        """Setup for each test method."""
        await self.setup_async_test()

        # Setup service with mocked dependencies
        self.user_service = UserService(
            repository=MockRepository(),
            event_bus=self.test_event_bus,
        )

    @unit_test
    async def test_create_user(self):
        """Test user creation."""
        # Act
        user = await self.user_service.create_user("test@example.com", "Test User")

        # Assert
        assert user.email == "test@example.com"
        assert user.name == "Test User"

        # Verify events
        self.event_collector.assert_event_published("user.created")

    @integration_test
    async def test_user_creation_flow(self):
        """Test complete user creation flow."""
        # Act
        user = await self.user_service.create_user("integration@example.com", "Integration Test")

        # Assert
        assert user.email == "integration@example.com"

        # Verify persistence
        if user.id:
            retrieved_user = await self.user_service.get_user(user.id)
            assert retrieved_user is not None
            assert retrieved_user.email == user.email
```

### Key Components

#### Base Classes

- **`AsyncTestCase`** - Base class for async tests with automatic setup/teardown
- **`ServiceTestMixin`** - Mixin providing common service testing patterns
- **`PerformanceTestMixin`** - Mixin for performance testing utilities
- **`IntegrationTestBase`** - Base class for integration tests

#### Test Utilities

- **`TestDatabaseManager`** - In-memory SQLite database for testing
- **`TestEventCollector`** - Collects and validates published events
- **`MockRepository`** - Generic mock repository implementation

#### Test Markers

- **`@unit_test`** - Mark tests as unit tests
- **`@integration_test`** - Mark tests as integration tests
- **`@performance_test`** - Mark tests as performance tests
- **`@slow_test`** - Mark tests as slow-running tests

### Event Testing

```python
class TestEventDrivenFlow(AsyncTestCase):
    """Test event-driven patterns."""

    @unit_test
    async def test_event_publishing(self):
        """Test event publishing and handling."""
        # Setup event collector for specific events
        user_events = TestEventCollector(event_types=["user.created", "user.updated"])
        await self.test_event_bus.subscribe(user_events)

        # Publish events
        await self.test_event_bus.publish(UserCreatedEvent("user_1", "test@example.com"))

        # Assert events were collected
        user_events.assert_event_published("user.created")
        assert len(user_events.events) == 1
```

### Database Testing

```python
class TestWithDatabase(AsyncTestCase):
    """Test with database integration."""

    @integration_test
    async def test_database_operations(self, test_session):
        """Test operations with database session."""
        # Use test_session fixture for database operations
        # Database is automatically cleaned up after test

        async with self.test_db.get_session() as session:
            # Perform database operations
            result = await session.execute(select(User))
            users = result.scalars().all()
            assert len(users) == 0
```

### Performance Testing

```python
class TestPerformance(AsyncTestCase, PerformanceTestMixin):
    """Performance tests."""

    @performance_test
    async def test_service_performance(self):
        """Test service performance under load."""
        async def operation():
            return await self.service.process_request()

        # Run load test
        results = await self.run_load_test(
            operation=operation,
            concurrent_requests=10,
            total_requests=100,
        )

        # Assert performance criteria
        assert results["successful"] >= 95
        assert results["requests_per_second"] >= 50
        assert results["average_time"] <= 0.1
```

## Configuration

### Pytest Configuration

The framework includes pytest configuration in `conftest.py`:

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests", "src/framework/testing/examples.py"]
markers = [
    "unit: mark test as unit test",
    "integration: mark test as integration test",
    "performance: mark test as performance test",
    "slow: mark test as slow test",
]
```

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run integration tests
pytest -m integration

# Run performance tests (slow)
pytest -m performance --run-slow

# Run specific test file
pytest tests/test_user_service.py

# Run with coverage
pytest --cov=src/framework --cov-report=html
```

### Test Environment Variables

```bash
# Set test database URL (defaults to in-memory SQLite)
export TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:"

# Set logging level for tests
export TEST_LOG_LEVEL="WARNING"

# Enable/disable test features
export SKIP_INTEGRATION_TESTS="false"
export SKIP_PERFORMANCE_TESTS="true"
```

## Advanced Features

The framework also includes advanced testing capabilities:

### Contract Testing

```python
from framework.testing import ContractBuilder, verify_contracts_for_provider

# Create consumer-driven contract
contract = (ContractBuilder("user-frontend", "user-service")
            .interaction("Get user by ID")
            .with_request("GET", "/users/123")
            .will_respond_with(200, body={"id": 123, "name": "John"})
            .build())

# Verify provider compliance
await verify_contracts_for_provider("user-service", "http://localhost:8080")
```

### Chaos Engineering

```python
from framework.testing import create_service_kill_experiment, ChaosTestCase

# Create chaos experiment
experiment = create_service_kill_experiment("user-service", duration=60)
chaos_test = ChaosTestCase(experiment)

# Run chaos test
await chaos_test.execute()
```

### Load Testing

```python
from framework.testing import create_load_test

# Create load test
load_test = create_load_test(
    name="User API Load Test",
    url="http://localhost:8080/api/users",
    users=50,
    duration=120,
    criteria={
        "max_response_time": 1.0,
        "min_requests_per_second": 100,
        "max_error_rate": 0.05,
    }
)

# Execute load test
results = await load_test.execute()
```

### Test Automation

```python
from framework.testing import setup_basic_test_automation

# Setup automated testing
orchestrator = setup_basic_test_automation(
    test_dirs=["./tests"],
    environments=["development", "testing", "staging"]
)

# Run automated test suite
await orchestrator.run_continuous_testing()
```

## Best Practices

### 1. Test Organization

```
tests/
├── unit/
│   ├── test_user_service.py
│   ├── test_auth_service.py
│   └── ...
├── integration/
│   ├── test_user_api_integration.py
│   ├── test_database_integration.py
│   └── ...
├── performance/
│   ├── test_load.py
│   ├── test_stress.py
│   └── ...
└── e2e/
    ├── test_user_journey.py
    └── ...
```

### 2. Service Testing Pattern

```python
class TestServicePattern(AsyncTestCase, ServiceTestMixin):
    """Standard pattern for service testing."""

    async def setup_method(self):
        """Setup with standard dependencies."""
        await self.setup_async_test()

        # Create standard test environment
        config = self.setup_service_test_environment("my_service")
        dependencies = self.create_mock_dependencies("my_service")

        # Initialize service
        self.service = MyService(**dependencies)

    @unit_test
    async def test_health_check(self):
        """Standard health check test."""
        health = await self.service.health_check()
        self.assert_standard_service_health(health)

    @unit_test
    async def test_metrics(self):
        """Standard metrics test."""
        metrics = await self.service.get_metrics()
        self.assert_standard_metrics_response(metrics)
```

### 3. Event Testing Pattern

```python
class TestEventPattern(AsyncTestCase):
    """Standard pattern for event testing."""

    @unit_test
    async def test_event_flow(self):
        """Test complete event flow."""
        # Setup event collectors
        collectors = {
            "user": TestEventCollector(["user.created", "user.updated"]),
            "audit": TestEventCollector(["audit.log"]),
        }

        for collector in collectors.values():
            await self.test_event_bus.subscribe(collector)

        # Execute operation
        await self.service.create_user("test@example.com", "Test User")

        # Verify events
        collectors["user"].assert_event_published("user.created")
        collectors["audit"].assert_event_published("audit.log")
```

### 4. Database Testing Pattern

```python
class TestDatabasePattern(AsyncTestCase):
    """Standard pattern for database testing."""

    @integration_test
    async def test_with_transaction(self):
        """Test with database transaction."""
        async with self.test_db.get_session() as session:
            # Create test data
            user = User(email="test@example.com", name="Test User")
            session.add(user)
            await session.commit()

            # Test operations
            result = await self.repository.get_by_email("test@example.com", session)
            assert result is not None
            assert result.email == "test@example.com"
```

## Troubleshooting

### Common Issues

1. **Async test setup issues**: Ensure `await self.setup_async_test()` is called in `setup_method()`

2. **Event collection not working**: Check that event collector is subscribed before publishing events

3. **Database tests failing**: Verify that `test_database` fixture is used and tables are created

4. **Performance tests timing out**: Increase timeout values or reduce test load

5. **Import errors**: Ensure all dependencies are installed: `pip install pytest pytest-asyncio`

### Debugging

```python
# Enable debug logging in tests
import logging
logging.getLogger("src.framework").setLevel(logging.DEBUG)

# Add debug assertions
assert len(self.event_collector.events) > 0, f"No events collected, available: {self.event_collector.events}"

# Use wait_for_condition for async operations
await wait_for_condition(
    lambda: len(self.event_collector.events) >= expected_count,
    timeout=5.0,
    interval=0.1,
)
```

This testing infrastructure provides a solid foundation for comprehensive microservices testing while maintaining DRY principles and enterprise-grade capabilities.
