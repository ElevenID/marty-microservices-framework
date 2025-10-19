"""
Simplified test configuration for MMF framework.

Demonstrates the comprehensive testing strategy without problematic imports.
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Test configuration
TEST_CONFIG = {
    "environment": "test",
    "debug": True,
    "log_level": "DEBUG",
    "service_name": "test-service",
}


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path


    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def test_config():
    """Provide test configuration."""
    return TEST_CONFIG.copy()


@pytest.fixture
async def mock_message_bus():
    """Provide a mock message bus for unit tests."""
    bus = MagicMock()
    bus.service_name = "test-service"
    bus.handlers = {}
    bus.is_running = False
    bus.start = MagicMock(return_value=asyncio.coroutine(lambda: None)())
    bus.stop = MagicMock(return_value=asyncio.coroutine(lambda: None)())
    bus.publish = MagicMock(return_value=asyncio.coroutine(lambda msg: True)())
    return bus


@pytest.fixture
async def mock_event_bus():
    """Provide a mock event bus for unit tests."""
    bus = MagicMock()
    bus.service_name = "test-service"
    bus.handlers = {}
    bus.subscriptions = {}
    bus.is_running = False
    bus.start = MagicMock(return_value=asyncio.coroutine(lambda: None)())
    bus.stop = MagicMock(return_value=asyncio.coroutine(lambda: None)())
    bus.publish = MagicMock(return_value=asyncio.coroutine(lambda evt: None)())
    return bus


@pytest.fixture
def mock_metrics_collector():
    """Provide a mock metrics collector for unit tests."""
    collector = MagicMock()
    collector.increment_counter = MagicMock()
    collector.record_histogram = MagicMock()
    collector.record_gauge = MagicMock()
    collector.get_metrics = MagicMock(return_value={})
    return collector


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.slow = pytest.mark.slow
pytest.mark.performance = pytest.mark.performance


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests with minimal external dependencies")
    config.addinivalue_line("markers", "integration: Integration tests with real services")
    config.addinivalue_line("markers", "e2e: End-to-end tests with complete workflows")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")
    config.addinivalue_line("markers", "performance: Performance and load tests")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on location."""
    for item in items:
        # Add markers based on test file location
        if "unit/" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration/" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e/" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment for all tests."""

    # Set test environment variables
    original_env = {}
    test_env_vars = {"ENVIRONMENT": "test", "DEBUG": "true", "LOG_LEVEL": "DEBUG"}

    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    # Restore original environment
    for key, original_value in original_env.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value
