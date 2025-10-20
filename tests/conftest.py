"""
Global pytest configuration and fixtures for MMF testing.

This module provides shared fixtures that can be used across
all test modules to ensure consistency and minimize code duplication.
"""

import asyncio
import os
import tempfile
import uuid
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# Framework imports
from marty_msf.framework.config import BaseServiceConfig
from marty_msf.framework.events.enhanced_event_bus import EnhancedEventBus
from marty_msf.framework.messaging.manager import MessagingManager as MessageBus
from marty_msf.framework.monitoring.core import MetricsCollector
from marty_msf.observability.logging import UnifiedServiceLogger as StructuredLogger

# Test configuration
TEST_CONFIG = {
    "environment": "test",
    "debug": True,
    "log_level": "DEBUG",
    "database_url": "sqlite:///:memory:",
    "redis_url": "redis://localhost:6379/1",
    "kafka_bootstrap_servers": ["localhost:9092"],
}


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def test_config() -> dict[str, Any]:
    """Provide test configuration."""
    return TEST_CONFIG.copy()


@pytest.fixture
def framework_config():
    """Provide test configuration."""
    return BaseServiceConfig(
        service_name="test-service", environment="test", debug=True, log_level="DEBUG"
    )


@pytest.fixture
def test_service_name() -> str:
    """Generate a unique test service name."""
    return f"test-service-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_user_id() -> str:
    """Generate a unique test user ID."""
    return f"user-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_correlation_id() -> str:
    """Generate a unique correlation ID for tracing."""
    return f"corr-{uuid.uuid4().hex[:8]}"


# Logging fixtures
@pytest.fixture
def logger(test_service_name: str) -> StructuredLogger:
    """Provide a structured logger for tests."""
    return StructuredLogger(
        service_name=test_service_name, level="DEBUG", correlation_id_key="correlation_id"
    )


# Metrics fixtures
@pytest.fixture
def metrics_collector(test_service_name: str) -> MetricsCollector:
    """Provide a metrics collector for tests."""
    return MetricsCollector(
        service_name=test_service_name,
        registry=None,  # Use default registry
        labels={"environment": "test"},
    )


# Event bus fixtures
@pytest.fixture
async def event_bus(
    test_service_name: str, test_config: dict[str, Any]
) -> AsyncGenerator[EnhancedEventBus, None]:
    """Provide an enhanced event bus for tests."""
    event_bus = EnhancedEventBus()

    try:
        await event_bus.start()
        yield event_bus
    finally:
        await event_bus.stop()


# Message bus fixtures
@pytest.fixture
async def message_bus(
    test_service_name: str, test_config: dict[str, Any]
) -> AsyncGenerator[MessageBus, None]:
    """Provide a message bus for tests."""
    message_bus = MessageBus(service_name=test_service_name, config=test_config)

    try:
        await message_bus.start()
        yield message_bus
    finally:
        await message_bus.stop()


# Database fixtures (when using real databases)
@pytest.fixture
async def database_connection(test_config: dict[str, Any]):
    """Provide a test database connection."""
    # This would be implemented based on your database layer
    # For now, return a mock that can be overridden in integration tests
    connection = MagicMock()
    connection.execute = AsyncMock()
    connection.fetch = AsyncMock(return_value=[])
    connection.fetchone = AsyncMock(return_value=None)
    yield connection


# Redis fixtures (when using real Redis)
@pytest.fixture
async def redis_client(test_config: dict[str, Any]):
    """Provide a Redis client for tests."""
    # This would be implemented based on your Redis layer
    # For now, return a mock that can be overridden in integration tests
    client = MagicMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    yield client


# Service fixtures
@pytest.fixture
def mock_service():
    """Provide a mock service for testing service interactions."""
    service = MagicMock()
    service.name = "mock-service"
    service.version = "1.0.0"
    service.health_check = AsyncMock(return_value={"status": "healthy"})
    service.start = AsyncMock()
    service.stop = AsyncMock()
    return service


# HTTP client fixtures
@pytest.fixture
async def http_client():
    """Provide an HTTP client for API testing."""
    # This would typically use httpx.AsyncClient or similar
    # For now, return a mock
    client = MagicMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    client.delete = AsyncMock()
    yield client


# Test data fixtures
@pytest.fixture
def sample_event_data() -> dict[str, Any]:
    """Provide sample event data for testing."""
    return {
        "event_type": "test.event",
        "event_id": str(uuid.uuid4()),
        "timestamp": "2025-10-10T15:30:00Z",
        "source": "test-service",
        "data": {
            "user_id": "test-user-123",
            "action": "test_action",
            "metadata": {"test": True, "environment": "test"},
        },
    }


@pytest.fixture
def sample_message_data() -> dict[str, Any]:
    """Provide sample message data for testing."""
    return {
        "message_id": str(uuid.uuid4()),
        "message_type": "test.message",
        "correlation_id": str(uuid.uuid4()),
        "timestamp": "2025-10-10T15:30:00Z",
        "payload": {"data": "test data", "count": 42, "active": True},
    }


# Environment setup
@pytest.fixture(autouse=True)
def setup_test_environment(test_config: dict[str, Any]):
    """Setup test environment variables."""
    original_env = {}

    # Set test environment variables
    test_env_vars = {
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "DEBUG",
        "DATABASE_URL": test_config["database_url"],
        "REDIS_URL": test_config["redis_url"],
    }

    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original environment
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


# Cleanup fixtures
@pytest.fixture(autouse=True)
async def cleanup_after_test():
    """Ensure proper cleanup after each test."""
    yield
    # Perform any necessary cleanup
    # This could include clearing test data, resetting connections, etc.
    await asyncio.sleep(0.1)  # Small delay for async cleanup


# Markers for test categorization
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.performance = pytest.mark.performance
pytest.mark.slow = pytest.mark.slow
pytest.mark.external = pytest.mark.external
pytest.mark.database = pytest.mark.database
pytest.mark.kafka = pytest.mark.kafka
pytest.mark.redis = pytest.mark.redis
pytest.mark.docker = pytest.mark.docker
pytest.mark.chaos = pytest.mark.chaos
pytest.mark.security = pytest.mark.security


# Utility functions for tests
def assert_event_structure(event: dict[str, Any], required_fields: list | None = None):
    """Assert that an event has the required structure."""
    default_fields = ["event_type", "event_id", "timestamp", "source"]
    fields_to_check = required_fields or default_fields

    for field in fields_to_check:
        assert field in event, f"Event missing required field: {field}"
        assert event[field] is not None, f"Event field {field} cannot be None"


def assert_message_structure(message: dict[str, Any], required_fields: list | None = None):
    """Assert that a message has the required structure."""
    default_fields = ["message_id", "message_type", "timestamp"]
    fields_to_check = required_fields or default_fields

    for field in fields_to_check:
        assert field in message, f"Message missing required field: {field}"
        assert message[field] is not None, f"Message field {field} cannot be None"


async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
    """Wait for a condition to become true."""
    elapsed = 0.0
    while elapsed < timeout:
        if (
            await condition_func()
            if asyncio.iscoroutinefunction(condition_func)
            else condition_func()
        ):
            return True
        await asyncio.sleep(interval)
        elapsed += interval
    return False
