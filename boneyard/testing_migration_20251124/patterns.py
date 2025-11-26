"""
DRY testing infrastructure for enterprise microservices.

Provides reusable test patterns, fixtures, and utilities for comprehensive testing
of microservices with database, events, and external dependencies.
"""

import asyncio
import builtins
import logging
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from marty_msf.framework.events import BaseEvent, EventHandler
from marty_msf.observability.monitoring import MetricsCollector
from mmf_new.core.infrastructure.database import BaseModel

logger = logging.getLogger(__name__)


class TestDatabaseManager:
    """Test database manager with in-memory SQLite."""

    def __init__(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_tables(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.create_all)

    async def drop_tables(self):
        """Drop all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(BaseModel.metadata.drop_all)

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get test database session."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def cleanup(self):
        """Cleanup database."""
        await self.engine.dispose()


class TestEventCollector(EventHandler):
    """Test event handler that collects events for assertion."""

    def __init__(self, event_types: builtins.list[str] | None = None):
        self.events: builtins.list[BaseEvent] = []
        self._event_types = event_types or []

    async def handle(self, event: BaseEvent) -> None:
        """Collect events."""
        self.events.append(event)

    async def can_handle(self, event: BaseEvent) -> bool:
        """Check if this handler can handle the event."""
        return not self._event_types or event.event_type in self._event_types

    @property
    def event_types(self) -> builtins.list[str]:
        """Return event types this handler processes."""
        return self._event_types

    def get_events_of_type(self, event_type: str) -> builtins.list[BaseEvent]:
        """Get events of specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def assert_event_published(self, event_type: str, count: int = 1) -> None:
        """Assert that an event was published."""
        events = self.get_events_of_type(event_type)
        assert len(events) == count, f"Expected {count} {event_type} events, got {len(events)}"

    def clear(self) -> None:
        """Clear collected events."""
        self.events.clear()


class ServiceTestMixin:
    """Mixin class providing common test patterns for services."""

    def setup_service_test_environment(self, service_name: str) -> builtins.dict[str, Any]:
        """Set up standardized test environment for a service."""
        return {
            "service_name": service_name,
            "environment": "testing",
            "debug": True,
            "database_url": "sqlite+aiosqlite:///:memory:",
        }

    def create_mock_dependencies(self, service_name: str) -> builtins.dict[str, Mock]:
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


class AsyncTestCase:
    """Base class for async test cases."""

    @pytest.fixture(autouse=True)
    async def setup_async_test(self):
        """Setup async test environment."""
        # Disable logging during tests
        logging.getLogger("src.framework").setLevel(logging.WARNING)

        # Setup test database
        self.test_db = TestDatabaseManager()
        await self.test_db.create_tables()

        # Setup test event bus (mocked)
        self.test_event_bus = AsyncMock()

        # Setup event collector
        self.event_collector = TestEventCollector()

        # Setup test metrics (mocked)
        self.test_metrics = Mock()

        yield

        # Cleanup
        await self.test_db.cleanup()


# Pytest fixtures
@pytest_asyncio.fixture
async def test_database():
    """Provide test database."""
    db = TestDatabaseManager()
    await db.create_tables()
    try:
        yield db
    finally:
        await db.cleanup()


@pytest_asyncio.fixture
async def test_session(test_database):
    """Provide test database session."""
    async with test_database.get_session() as session:
        yield session


@pytest_asyncio.fixture
async def test_event_bus():
    """Provide test event bus."""
    bus = AsyncMock()
    yield bus


@pytest_asyncio.fixture
async def event_collector(test_event_bus):
    """Provide event collector."""
    collector = TestEventCollector()
    yield collector


@pytest.fixture
def test_metrics():
    """Provide test metrics collector."""
    return Mock()


@pytest.fixture
def mock_external_service():
    """Provide mock external service."""
    mock = AsyncMock()
    mock.health_check.return_value = True
    mock.process_request.return_value = {"status": "success"}
    return mock


# Test utilities
def create_test_config(**overrides) -> builtins.dict[str, Any]:
    """Create test configuration with overrides."""
    config = {
        "service_name": "test_service",
        "environment": "testing",
        "debug": True,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "log_level": "WARNING",
    }
    config.update(overrides)
    return config


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
) -> bool:
    """Wait for a condition to become true."""

    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        await asyncio.sleep(interval)
    return False


class MockRepository:
    """Mock repository for testing."""

    def __init__(self):
        self._data: builtins.dict[Any, Any] = {}
        self._next_id = 1

    async def get_by_id(self, id: Any) -> Any | None:
        """Get entity by ID."""
        return self._data.get(id)

    async def get_all(self, limit: int = 100, offset: int = 0) -> builtins.list[Any]:
        """Get all entities."""
        items = list(self._data.values())
        return items[offset : offset + limit]

    async def create(self, entity: Any) -> Any:
        """Create entity."""
        if not hasattr(entity, "id") or entity.id is None:
            entity.id = self._next_id
            self._next_id += 1
        self._data[entity.id] = entity
        return entity

    async def update(self, entity: Any) -> Any:
        """Update entity."""
        if hasattr(entity, "id") and entity.id in self._data:
            self._data[entity.id] = entity
        return entity

    async def delete(self, id: Any) -> bool:
        """Delete entity."""
        if id in self._data:
            del self._data[id]
            return True
        return False

    async def count(self) -> int:
        """Count entities."""
        return len(self._data)

    def clear(self) -> None:
        """Clear all data."""
        self._data.clear()
        self._next_id = 1


# Integration test utilities
class IntegrationTestBase(AsyncTestCase, ServiceTestMixin):
    """Base class for integration tests."""

    async def setup_integration_test(self, service_config: builtins.dict[str, Any]):
        """Setup integration test environment."""
        # Override in subclasses

    async def teardown_integration_test(self):
        """Teardown integration test environment."""
        # Override in subclasses


# Performance test utilities
class PerformanceTestMixin:
    """Mixin for performance testing."""

    async def measure_execution_time(self, operation: Callable) -> float:
        """Measure operation execution time."""

        start_time = time.time()
        await operation()
        return time.time() - start_time

    async def run_load_test(
        self,
        operation: Callable,
        concurrent_requests: int = 10,
        total_requests: int = 100,
    ) -> builtins.dict[str, Any]:
        """Run a simple load test."""

        start_time = time.time()

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrent_requests)

        async def run_single_request():
            async with semaphore:
                return await operation()

        # Run all requests
        tasks = [run_single_request() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()

        # Analyze results
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful
        total_time = end_time - start_time

        return {
            "total_requests": total_requests,
            "successful": successful,
            "failed": failed,
            "total_time": total_time,
            "requests_per_second": total_requests / total_time,
            "average_time": total_time / total_requests,
        }


# Markers for different test types
def unit_test(func):
    """Mark test as unit test."""
    return pytest.mark.unit(func)


def integration_test(func):
    """Mark test as integration test."""
    return pytest.mark.integration(func)


def performance_test(func):
    """Mark test as performance test."""
    return pytest.mark.performance(func)


def slow_test(func):
    """Mark test as slow test."""
    return pytest.mark.slow(func)
