"""
Test utilities and helpers for MMF framework testing.

Provides reusable utilities, fixtures, and helpers to ensure consistency
across all test types while minimizing mocking.
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
import redis
import yaml
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from marty_msf.framework.config import FrameworkConfig
from marty_msf.framework.events import Event, EventBus
from marty_msf.framework.messaging import Message, MessageBus
from mmf_new.core.infrastructure.database import DatabaseManager as DatabaseConnection


class TestServiceManager:
    """
    Manages test services and their lifecycle.
    Provides real implementations over mocks where possible.
    """

    def __init__(self):
        self.services = {}
        self.containers = {}
        self.cleanup_tasks = []

    async def create_message_bus(self, service_name: str = None) -> MessageBus:
        """Create a real message bus instance for testing."""
        service_name = service_name or f"test-service-{uuid.uuid4().hex[:8]}"
        bus = MessageBus(service_name=service_name)

        self.services[f"message_bus_{service_name}"] = bus
        self.cleanup_tasks.append(lambda: bus.stop())

        return bus

    async def create_event_bus(self, service_name: str = None) -> EventBus:
        """Create a real event bus instance for testing."""
        service_name = service_name or f"test-service-{uuid.uuid4().hex[:8]}"
        bus = EventBus(service_name=service_name)

        self.services[f"event_bus_{service_name}"] = bus
        self.cleanup_tasks.append(lambda: bus.stop())

        return bus

    async def create_database_connection(self, container: PostgresContainer) -> DatabaseConnection:
        """Create a real database connection for testing."""
        connection_url = container.get_connection_url()
        db = DatabaseConnection(connection_url)

        await db.connect()
        self.services["database"] = db
        self.cleanup_tasks.append(lambda: db.disconnect())

        return db

    async def create_redis_client(self, container: RedisContainer):
        """Create a real Redis client for testing."""
        redis_url = container.get_connection_url()
        client = redis.from_url(redis_url)

        self.services["redis"] = client
        self.cleanup_tasks.append(lambda: client.close())

        return client

    async def cleanup(self):
        """Clean up all managed services."""
        for cleanup_task in reversed(self.cleanup_tasks):
            try:
                if asyncio.iscoroutinefunction(cleanup_task):
                    await cleanup_task()
                else:
                    cleanup_task()
            except Exception as e:
                print(f"Cleanup error: {e}")

        self.services.clear()
        self.containers.clear()
        self.cleanup_tasks.clear()


class MessageCapture:
    """
    Utility for capturing and asserting on messages/events.
    Uses real message bus with capture handlers.
    """

    def __init__(self):
        self.captured_messages = []
        self.captured_events = []

    async def message_handler(self, message: Message) -> bool:
        """Handler that captures messages for testing."""
        self.captured_messages.append(message)
        return True

    async def event_handler(self, event: Event) -> None:
        """Handler that captures events for testing."""
        self.captured_events.append(event)

    def get_messages_by_type(self, message_type: str) -> list[Message]:
        """Get captured messages by type."""
        return [msg for msg in self.captured_messages if msg.type == message_type]

    def get_events_by_type(self, event_type: str) -> list[Event]:
        """Get captured events by type."""
        return [evt for evt in self.captured_events if evt.type == event_type]

    def assert_message_sent(self, message_type: str, data: dict[str, Any] = None):
        """Assert that a message of given type was sent."""
        messages = self.get_messages_by_type(message_type)
        assert len(messages) > 0, f"No messages of type '{message_type}' were captured"

        if data:
            matching_messages = [
                msg for msg in messages if all(msg.data.get(k) == v for k, v in data.items())
            ]
            assert len(matching_messages) > 0, f"No messages with matching data found: {data}"

    def assert_event_published(self, event_type: str, data: dict[str, Any] = None):
        """Assert that an event of given type was published."""
        events = self.get_events_by_type(event_type)
        assert len(events) > 0, f"No events of type '{event_type}' were captured"

        if data:
            matching_events = [
                evt for evt in events if all(evt.data.get(k) == v for k, v in data.items())
            ]
            assert len(matching_events) > 0, f"No events with matching data found: {data}"

    def clear(self):
        """Clear all captured messages and events."""
        self.captured_messages.clear()
        self.captured_events.clear()


class DatabaseTestHelper:
    """
    Database testing utilities for setup, cleanup, and assertions.
    Uses real database connections.
    """

    def __init__(self, db_connection: DatabaseConnection):
        self.db = db_connection
        self.test_tables = set()

    async def create_test_table(self, table_name: str, schema: str):
        """Create a test table with given schema."""
        await self.db.execute(f"DROP TABLE IF EXISTS {table_name}")
        await self.db.execute(schema)
        self.test_tables.add(table_name)

    async def insert_test_data(self, table_name: str, data: list[dict[str, Any]]):
        """Insert test data into a table."""
        if not data:
            return

        # Build insert query from first record
        columns = list(data[0].keys())
        placeholders = ", ".join([f"${i + 1}" for i in range(len(columns))])
        query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

        for record in data:
            values = [record[col] for col in columns]
            await self.db.execute(query, *values)

    async def assert_table_count(self, table_name: str, expected_count: int):
        """Assert the number of records in a table."""
        count = await self.db.fetch_val(f"SELECT COUNT(*) FROM {table_name}")
        assert count == expected_count, (
            f"Expected {expected_count} records in {table_name}, got {count}"
        )

    async def assert_record_exists(self, table_name: str, conditions: dict[str, Any]):
        """Assert that a record exists with given conditions."""
        where_clause = " AND ".join([f"{k} = ${i + 1}" for i, k in enumerate(conditions.keys())])
        query = f"SELECT COUNT(*) FROM {table_name} WHERE {where_clause}"
        values = list(conditions.values())

        count = await self.db.fetch_val(query, *values)
        assert count > 0, f"No record found in {table_name} with conditions {conditions}"

    async def get_test_data(
        self, table_name: str, conditions: dict[str, Any] = None
    ) -> list[dict[str, Any]]:
        """Get test data from a table."""
        if conditions:
            where_clause = " AND ".join(
                [f"{k} = ${i + 1}" for i, k in enumerate(conditions.keys())]
            )
            query = f"SELECT * FROM {table_name} WHERE {where_clause}"
            values = list(conditions.values())
            return await self.db.fetch_all(query, *values)
        else:
            return await self.db.fetch_all(f"SELECT * FROM {table_name}")

    async def cleanup_test_tables(self):
        """Clean up all test tables."""
        for table_name in self.test_tables:
            try:
                await self.db.execute(f"DROP TABLE IF EXISTS {table_name}")
            except Exception as e:
                print(f"Error dropping table {table_name}: {e}")

        self.test_tables.clear()


class RedisTestHelper:
    """
    Redis testing utilities for setup, cleanup, and assertions.
    Uses real Redis connections.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self.test_keys = set()

    async def set_test_data(self, key: str, value: Any, **kwargs):
        """Set test data in Redis."""
        if isinstance(value, dict | list):
            value = json.dumps(value)

        await self.redis.set(key, value, **kwargs)
        self.test_keys.add(key)

    async def get_test_data(self, key: str) -> Any:
        """Get test data from Redis."""
        value = await self.redis.get(key)
        if value is None:
            return None

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    async def assert_key_exists(self, key: str):
        """Assert that a key exists in Redis."""
        exists = await self.redis.exists(key)
        assert exists, f"Key '{key}' does not exist in Redis"

    async def assert_key_value(self, key: str, expected_value: Any):
        """Assert the value of a Redis key."""
        actual_value = await self.get_test_data(key)
        assert actual_value == expected_value, f"Expected {expected_value}, got {actual_value}"

    async def assert_list_length(self, key: str, expected_length: int):
        """Assert the length of a Redis list."""
        length = await self.redis.llen(key)
        assert length == expected_length, f"Expected list length {expected_length}, got {length}"

    async def cleanup_test_keys(self):
        """Clean up all test keys."""
        if self.test_keys:
            await self.redis.delete(*self.test_keys)
        self.test_keys.clear()


class ConfigTestHelper:
    """
    Configuration testing utilities.
    """

    @staticmethod
    def create_test_config(**overrides) -> FrameworkConfig:
        """Create a test configuration with overrides."""
        default_config = {
            "service_name": "test-service",
            "environment": "test",
            "debug": True,
            "log_level": "DEBUG",
            "port": 8080,
        }

        default_config.update(overrides)
        return FrameworkConfig.from_dict(default_config)

    @staticmethod
    @contextmanager
    def environment_variables(**env_vars):
        """Context manager for temporary environment variables."""
        original_env = {}

        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = str(value)

        try:
            yield
        finally:
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value

    @staticmethod
    def create_temp_config_file(config_data: dict[str, Any], file_format: str = "yaml") -> Path:
        """Create a temporary configuration file."""
        suffix = f".{file_format}"
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)

        if file_format == "yaml":
            yaml.dump(config_data, temp_file)
        elif file_format == "json":
            json.dump(config_data, temp_file)
        else:
            raise ValueError(f"Unsupported format: {file_format}")

        temp_file.close()
        return Path(temp_file.name)


class WorkflowTestHelper:
    """
    Helper for testing complex workflows and patterns.
    """

    def __init__(self, service_manager: TestServiceManager):
        self.service_manager = service_manager
        self.workflow_steps = []
        self.workflow_data = {}

    def track_step(self, step_name: str, data: dict[str, Any] = None):
        """Track a workflow step for verification."""
        self.workflow_steps.append(
            {
                "step": step_name,
                "data": data or {},
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

    def assert_workflow_completed(self, expected_steps: list[str]):
        """Assert that all expected workflow steps were executed."""
        actual_steps = [step["step"] for step in self.workflow_steps]

        for expected_step in expected_steps:
            assert expected_step in actual_steps, (
                f"Workflow step '{expected_step}' was not executed"
            )

    def assert_step_order(self, step1: str, step2: str):
        """Assert that step1 happened before step2."""
        step1_idx = next((i for i, s in enumerate(self.workflow_steps) if s["step"] == step1), None)
        step2_idx = next((i for i, s in enumerate(self.workflow_steps) if s["step"] == step2), None)

        assert step1_idx is not None, f"Step '{step1}' not found"
        assert step2_idx is not None, f"Step '{step2}' not found"
        assert step1_idx < step2_idx, f"Step '{step1}' should occur before '{step2}'"

    def get_step_data(self, step_name: str) -> dict[str, Any]:
        """Get data from a specific workflow step."""
        step = next((s for s in self.workflow_steps if s["step"] == step_name), None)
        assert step is not None, f"Step '{step_name}' not found"
        return step["data"]

    def clear_workflow(self):
        """Clear workflow tracking data."""
        self.workflow_steps.clear()
        self.workflow_data.clear()


class MockExternalServices:
    """
    Minimal mocking for external services only when real implementations
    are not feasible in tests.
    """

    def __init__(self):
        self.mocks = {}

    @contextmanager
    def mock_http_service(self, base_url: str, responses: dict[str, Any]):
        """Mock external HTTP service calls."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Set up responses
            for endpoint, response_data in responses.items():
                mock_response = Mock()
                mock_response.status_code = response_data.get("status_code", 200)
                mock_response.json.return_value = response_data.get("json", {})
                mock_response.text = response_data.get("text", "")

                if endpoint.startswith("GET "):
                    mock_instance.get.return_value = mock_response
                elif endpoint.startswith("POST "):
                    mock_instance.post.return_value = mock_response
                elif endpoint.startswith("PUT "):
                    mock_instance.put.return_value = mock_response
                elif endpoint.startswith("DELETE "):
                    mock_instance.delete.return_value = mock_response

            self.mocks[base_url] = mock_instance
            yield mock_instance

    @contextmanager
    def mock_file_system(self, file_contents: dict[str, str]):
        """Mock file system operations for external file dependencies."""
        with patch("builtins.open") as mock_open:

            def open_side_effect(filename, mode="r", *args, **kwargs):
                if filename in file_contents:
                    mock_file = Mock()
                    if "r" in mode:
                        mock_file.read.return_value = file_contents[filename]
                        mock_file.__enter__.return_value = mock_file
                        mock_file.__exit__.return_value = None
                    return mock_file
                else:
                    # Fall back to real file operations for non-mocked files
                    return open(filename, mode, *args, **kwargs)

            mock_open.side_effect = open_side_effect
            yield mock_open


# Factory functions for common test objects
def create_test_message(
    message_type: str = "test.message", data: dict[str, Any] = None, **kwargs
) -> Message:
    """Create a test message with sensible defaults."""
    return Message(
        id=kwargs.get("id", f"msg-{uuid.uuid4().hex[:8]}"),
        type=message_type,
        data=data or {"test": True},
        correlation_id=kwargs.get("correlation_id"),
        source=kwargs.get("source", "test-service"),
        destination=kwargs.get("destination"),
    )


def create_test_event(
    event_type: str = "test.event", data: dict[str, Any] = None, **kwargs
) -> Event:
    """Create a test event with sensible defaults."""
    return Event(
        id=kwargs.get("id", f"evt-{uuid.uuid4().hex[:8]}"),
        type=event_type,
        data=data or {"test": True},
        source=kwargs.get("source", "test-service"),
        correlation_id=kwargs.get("correlation_id"),
        version=kwargs.get("version", 1),
    )


async def create_test_service(
    service_name: str, service_type: str = "fastapi", temp_dir: Path = None
) -> Path:
    """Create a test service in a temporary directory."""

    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp())

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "marty_mmf.cli",
            "create",
            "service",
            "--name",
            service_name,
            "--type",
            service_type,
            "--output",
            str(temp_dir),
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create test service: {result.stderr}")

    return temp_dir / service_name


async def cleanup_test_service(service_path: Path):
    """Clean up a test service directory."""

    if service_path.exists():
        shutil.rmtree(service_path)


# Pytest fixtures that use these utilities
@pytest.fixture
async def service_manager():
    """Fixture providing a test service manager."""
    manager = TestServiceManager()
    yield manager
    await manager.cleanup()


@pytest.fixture
async def message_capture():
    """Fixture providing message capture utilities."""
    capture = MessageCapture()
    yield capture
    capture.clear()


@pytest.fixture
async def db_helper(real_database_connection):
    """Fixture providing database test utilities."""
    helper = DatabaseTestHelper(real_database_connection)
    yield helper
    await helper.cleanup_test_tables()


@pytest.fixture
async def redis_helper(real_redis_client):
    """Fixture providing Redis test utilities."""
    helper = RedisTestHelper(real_redis_client)
    yield helper
    await helper.cleanup_test_keys()


@pytest.fixture
async def workflow_helper(service_manager):
    """Fixture providing workflow test utilities."""
    helper = WorkflowTestHelper(service_manager)
    yield helper
    helper.clear_workflow()


@pytest.fixture
def mock_external():
    """Fixture providing external service mocking utilities."""
    return MockExternalServices()


@pytest.fixture
def temp_service_dir():
    """Fixture providing a temporary directory for test services."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir

    if temp_dir.exists():
        shutil.rmtree(temp_dir)
