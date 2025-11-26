"""
Pytest configuration for the framework testing infrastructure.

This module configures pytest with appropriate markers, fixtures,
and test collection rules for microservices testing.
"""

import asyncio
from collections.abc import Generator

import pytest


# Configure pytest async
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    # Register custom markers
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "slow: mark test as slow test")
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")

    # Add custom test paths
    config.addinivalue_line("testpaths", "tests")
    config.addinivalue_line("testpaths", "src/framework/testing/examples.py")


def pytest_collection_modifyitems(config, items):  # pylint: disable=unused-argument
    """Modify test collection to add default markers and organize tests."""
    for item in items:
        # Add unit marker if no other test type marker present
        test_markers = [mark.name for mark in item.iter_markers()]
        if not any(
            marker in test_markers for marker in ["unit", "integration", "performance", "e2e"]
        ):
            item.add_marker(pytest.mark.unit)

        # Add slow marker for performance tests
        if "performance" in test_markers:
            item.add_marker(pytest.mark.slow)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()


def pytest_runtest_setup(item):
    """Setup for each test run."""
    # Skip slow tests unless explicitly requested
    if "slow" in [mark.name for mark in item.iter_markers()]:
        if not item.config.getoption("--run-slow"):
            pytest.skip("need --run-slow option to run")


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="run slow tests including performance tests",
    )
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests",
    )
    parser.addoption("--unit-only", action="store_true", default=False, help="run only unit tests")


def pytest_ignore_collect(path, config):
    """Ignore certain files during collection."""
    # Ignore example files unless explicitly running examples
    if "examples.py" in str(path) and not config.getoption("--collect-only"):
        return True
    return False
